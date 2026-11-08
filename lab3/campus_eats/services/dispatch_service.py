"""配送调度服务（对应组件图 DISP，REQ-012/013/016）。

与订单服务的边界（组件图 DISP -> ORD 回写订单状态）：本服务只改配送任务，
订单状态一律通过注入的订单服务窄接口回写。
"""

from datetime import timedelta

from campus_eats.models.account import Account
from campus_eats.models.cart_order import Order
from campus_eats.models.delivery import DeliveryTask
from campus_eats.models.enums import Role, TaskStatus
from campus_eats.models.errors import PermissionDeniedError, ValidationError
from campus_eats.services.audit_service import AuditService
from campus_eats.services.config import DISPATCH_TIMEOUT_MINUTES
from campus_eats.services.context import ServiceContext


class DispatchService:
    """派单、拒单、改派、送达、配送异常处置。"""

    def __init__(self, context: ServiceContext, audit: AuditService) -> None:
        """绑定上下文与审计；orders 由装配层注入。"""
        self._ctx = context
        self._audit = audit
        self._orders = None

    def set_order_service(self, order_service) -> None:
        """装配期注入订单服务。"""
        self._orders = order_service

    # ---------- 任务生成（ORD -> DISP） ----------

    def create_task(self, order: Order) -> DeliveryTask:
        """出餐后为订单建配送任务：进本片区待分配队列（REQ-012）。"""
        shop = self._ctx.repos.shops.get(order.shop_id)
        task = DeliveryTask(order_id=order.order_id, order_no=order.order_no,
                            status=TaskStatus.WAIT_ASSIGN,
                            area_code=shop.area_code if shop else "",
                            pickup_text=shop.address_text if shop else "",
                            dropoff_text=order.address_text,
                            assigned_at=self._ctx.clock.now().replace(microsecond=0))
        self._ctx.repos.tasks.add(task)
        self._audit.record(None, "TASK", task.task_id, f"任务 {order.order_no}",
                           "生成配送任务", after=TaskStatus.WAIT_ASSIGN.label)
        self._audit.notify(self._admin_id(), "有待派送任务",
                           f"订单 {order.order_no} 待指派骑手")
        return task

    # ---------- 管理员操作 ----------

    def assign(self, operator: Account, task_id: int, rider_id: int) -> DeliveryTask:
        """管理员指派骑手（REQ-012）：骑手须在线且片区匹配；同一订单
        不会同时指派两人（任务状态机 + 全局锁保证）。
        """
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可派单")
        with self._ctx.lock:
            task = self._require_task(task_id)
            rider = self._require_rider(rider_id)
            if not rider.online:
                raise ValidationError(f"骑手 {rider.name} 当前不在线")
            if rider.area_code != task.area_code:
                raise ValidationError(f"骑手 {rider.name} 属于 {rider.area_code} 片区，"
                                      f"任务在 {task.area_code} 片区")
            before = task.status.label
            task.assign(rider_id, rider.name)
            task.assigned_at = self._ctx.clock.now().replace(microsecond=0)
            self._ctx.repos.tasks.update(task)
            self._audit.record(operator, "TASK", task_id, f"任务 {task.order_no}",
                               "派单", before=before,
                               after=f"指派给 {rider.name}")
            self._audit.notify(rider_id, "收到配送任务",
                               f"订单 {task.order_no}，取餐 {task.pickup_text}")
            return task

    def reassign(self, operator: Account, task_id: int, rider_id: int,
                 reason: str) -> DeliveryTask:
        """管理员改派（REQ-012/016）：须填写原因；配送异常或待分配任务可改派。"""
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可改派")
        if not reason.strip():
            raise ValidationError("改派必须填写原因")
        with self._ctx.lock:
            task = self._require_task(task_id)
            rider = self._require_rider(rider_id)
            if not rider.online:
                raise ValidationError(f"骑手 {rider.name} 当前不在线")
            if rider.area_code != task.area_code:
                raise ValidationError(f"骑手 {rider.name} 属于 {rider.area_code} 片区，"
                                      f"任务在 {task.area_code} 片区")
            old_rider = task.rider_name or "（无）"
            was_exception = task.status is TaskStatus.EXCEPTION
            task.reassign(rider_id, rider.name, reason)
            task.assigned_at = self._ctx.clock.now().replace(microsecond=0)
            self._ctx.repos.tasks.update(task)
            self._audit.record(operator, "TASK", task_id, f"任务 {task.order_no}",
                               "改派", before=f"{task.status.label} 骑手:{old_rider}",
                               after=f"改派给 {rider.name}", reason=reason)
            if was_exception:
                self._orders.mark_delivering(task.order_id,
                                             f"管理员改派给 {rider.name}")
            self._audit.notify(rider_id, "收到配送任务",
                               f"订单 {task.order_no}（改派），取餐 {task.pickup_text}")
            return task

    def cancel_by_admin(self, operator: Account, task_id: int, reason: str) -> None:
        """管理员处置配送异常——取消并全额退款（REQ-016）。

        订单取消与退款由订单服务完成；任务转异常留档。
        """
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可处置异常任务")
        with self._ctx.lock:
            task = self._require_task(task_id)
            if task.status is not TaskStatus.EXCEPTION:
                raise ValidationError("仅配送异常的任务可走取消处置")
            task.fail_reason = f"{task.fail_reason}；管理员处置：取消退款"
            self._ctx.repos.tasks.update(task)
            order = self._ctx.repos.orders.get(task.order_id)
            self._orders.cancel(order.order_id, f"配送异常处置：{reason.strip()}",
                                refund_fen=order.pay_amount_fen, operator=operator)

    # ---------- 骑手操作 ----------

    def accept_task(self, rider: Account, task_id: int) -> DeliveryTask:
        """骑手接受任务：任务配送中，订单回写为配送中（REQ-012）。

        异常改派后的首次接受，订单已由改派动作转为配送中，回写幂等跳过。
        """
        with self._ctx.lock:
            task = self._require_task(task_id)
            if task.rider_id != rider.account_id:
                raise PermissionDeniedError("该任务未指派给你")
            before = task.status.label
            task.accept()
            self._ctx.repos.tasks.update(task)
            order = self._ctx.repos.orders.get(task.order_id)
            if order.status.value in ("待配送", "配送异常"):
                self._orders.mark_delivering(order.order_id, rider.name)
            self._audit.record(rider, "TASK", task_id, f"任务 {task.order_no}",
                               "接受任务", before=before, after=task.status.label)
            self._audit.notify(order.customer_id, "骑手已接单配送",
                               f"订单 {task.order_no} 配送中")
            return task

    def reject_task(self, rider: Account, task_id: int, reason: str = "") -> DeliveryTask:
        """骑手拒绝任务：回到待分配，等待管理员重新派单（REQ-012）。"""
        with self._ctx.lock:
            task = self._require_task(task_id)
            if task.rider_id != rider.account_id:
                raise PermissionDeniedError("该任务未指派给你")
            before = task.status.label
            task.reject()
            if reason.strip():
                task.fail_reason = f"骑手拒单：{reason.strip()}"
            self._ctx.repos.tasks.update(task)
            self._audit.record(rider, "TASK", task_id, f"任务 {task.order_no}",
                               "拒绝任务", before=before, after=task.status.label,
                               reason=reason)
            self._audit.notify(self._admin_id(), "骑手拒单，请重新派单",
                               f"订单 {task.order_no} 已被 {rider.name} 拒绝"
                               + (f"（{reason.strip()}）" if reason.strip() else ""))
            return task

    def finish_task(self, rider: Account, task_id: int) -> DeliveryTask:
        """骑手确认送达：任务完成，订单回写已送达（REQ-013）。"""
        with self._ctx.lock:
            task = self._require_task(task_id)
            if task.rider_id != rider.account_id:
                raise PermissionDeniedError("该任务未指派给你")
            task.finish()
            task.completed_at = self._ctx.clock.now().replace(microsecond=0)
            self._ctx.repos.tasks.update(task)
            order = self._ctx.repos.orders.get(task.order_id)
            self._orders.mark_delivered(order.order_id, rider.name)
            self._audit.record(rider, "TASK", task_id, f"任务 {task.order_no}",
                               "确认送达", after=task.status.label)
            self._audit.notify(order.customer_id, "订单已送达",
                               f"订单 {task.order_no} 已送达，请确认收货")
            return task

    def report_exception(self, rider: Account, task_id: int, reason: str,
                         detail: str = "") -> DeliveryTask:
        """骑手上报配送失败（REQ-016）：原因限定三类；订单挂起进管理员队列。"""
        with self._ctx.lock:
            task = self._require_task(task_id)
            if task.rider_id != rider.account_id:
                raise PermissionDeniedError("该任务未指派给你")
            task.report_exception(reason)
            if detail.strip():
                task.fail_reason = f"{task.fail_reason}（{detail.strip()}）"
            self._ctx.repos.tasks.update(task)
            order = self._ctx.repos.orders.get(task.order_id)
            self._orders.mark_exception(order.order_id, reason)
            self._audit.record(rider, "TASK", task_id, f"任务 {task.order_no}",
                               "上报配送异常", after=task.status.label, reason=reason)
            self._audit.notify(self._admin_id(), "配送异常待处置",
                               f"订单 {task.order_no}：{reason}")
            self._audit.notify(order.customer_id, "配送出现异常",
                               f"订单 {task.order_no}：{reason}，平台正在处置")
            return task

    # ---------- 查询 ----------

    def list_rider_tasks(self, rider: Account) -> list[DeliveryTask]:
        """骑手当前任务（不含已完成/异常）。"""
        return self._ctx.repos.tasks.list_by_rider(rider.account_id)

    def list_wait_assign(self, operator: Account) -> list[DeliveryTask]:
        """管理端待分配队列。"""
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可查看待分配队列")
        return self._ctx.repos.tasks.list_by_status(TaskStatus.WAIT_ASSIGN)

    def list_exceptions(self, operator: Account) -> list[DeliveryTask]:
        """管理端配送异常队列（REQ-016 挂起任务）。"""
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可查看异常队列")
        return self._ctx.repos.tasks.list_by_status(TaskStatus.EXCEPTION)

    def list_online_riders(self) -> list:
        """在线骑手（派单界面用）。"""
        return [r for r in self._ctx.repos.accounts.list_by_role(Role.RIDER)
                if r.online]

    def set_rider_online(self, rider: Account, online: bool) -> None:
        """骑手上线 / 下线。"""
        with self._ctx.lock:
            rider.online = online
            self._ctx.repos.accounts.update(rider)

    def dispatch_timeouts(self) -> list:
        """出餐后长时间无人接单的任务转异常挂起（状态图「配送超时」）。"""
        cutoff = (self._ctx.clock.now()
                  - timedelta(minutes=DISPATCH_TIMEOUT_MINUTES)).isoformat()
        stale = []
        with self._ctx.lock:
            for task in self._ctx.repos.tasks.list_by_status(TaskStatus.WAIT_ASSIGN):
                if task.assigned_at and task.assigned_at.isoformat() <= cutoff:
                    task.mark_timeout()
                    self._ctx.repos.tasks.update(task)
                    order = self._ctx.repos.orders.get(task.order_id)
                    self._orders.mark_exception(order.order_id, "配送超时")
                    self._audit.notify(self._admin_id(), "配送超时待处置",
                                       f"订单 {task.order_no} 长时间无人接单")
                    stale.append(task)
        return stale

    # ---------- 内部 ----------

    def _require_task(self, task_id: int) -> DeliveryTask:
        """取任务或抛错。"""
        task = self._ctx.repos.tasks.get(task_id)
        if task is None:
            raise ValidationError("配送任务不存在")
        return task

    def _require_rider(self, rider_id: int):
        """取骑手账号或抛错。"""
        rider = self._ctx.repos.accounts.get(rider_id)
        if rider is None or rider.role is not Role.RIDER:
            raise ValidationError("骑手不存在")
        return rider

    def _admin_id(self) -> int | None:
        """任一管理员的账号 id（通知收件人）。"""
        admins = self._ctx.repos.accounts.list_by_role(Role.ADMIN)
        return admins[0].account_id if admins else None
