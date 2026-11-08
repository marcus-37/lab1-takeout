"""售后与仲裁服务（对应组件图 AFTER，REQ-014/026）。

取消规则（REQ-014）：
- 待支付 / 待接单：顾客可自行取消，全额退款到余额（未支付单只释放库存）；
- 制作中（已接单未出餐）：须商家同意方可取消退款，顾客先提申请；
- 出餐后：不可取消，仅可按菜品部分退款（配送费不退）；
- 已完成 / 已取消：终态，不再受理。

管理员仲裁（REQ-026）：强制退款、代为处置退款申请、申请超时 24 小时自动同意。
"""

from datetime import timedelta

from campus_eats.models.account import Account
from campus_eats.models.enums import OrderStatus, RefundType, Role
from campus_eats.models.errors import PermissionDeniedError, ValidationError
from campus_eats.services.audit_service import AuditService
from campus_eats.services.config import REFUND_AUTO_AGREE_HOURS
from campus_eats.services.context import ServiceContext


class AftersaleService:
    """顾客取消、退款申请与商家/管理员处置。"""

    def __init__(self, context: ServiceContext, audit: AuditService) -> None:
        """绑定上下文与审计；orders 与 payments 由装配层注入。"""
        self._ctx = context
        self._audit = audit
        self._orders = None
        self._payments = None

    def set_dependencies(self, order_service, payment_service) -> None:
        """装配期注入订单与支付服务（组件图 AFTER -> ORD / AFTER -> PAY）。"""
        self._orders = order_service
        self._payments = payment_service

    # ---------- 顾客侧 ----------

    def cancel_by_customer(self, customer: Account, order_id: int) -> None:
        """顾客自行取消：仅待支付 / 待接单可自行取消（REQ-014）。

        待支付：不涉及退款，释放预占库存；待接单：已支付，退剩余额度
        （实付减已部分退款）；不产生新退款流水时退实付全额。
        """
        order = self._get_own_order(customer, order_id)
        if order.status is OrderStatus.PENDING_PAY:
            self._orders.cancel(order_id, "顾客在支付前取消", 0, customer,
                                notify_shop=True, release_stock=True)
            return
        if order.status is OrderStatus.PENDING_ACCEPT:
            self._orders.cancel(order_id, "顾客取消（商家接单前）",
                                self._remaining_refund(order), customer)
            return
        if order.status is OrderStatus.COOKING:
            raise ValidationError("商家已接单，取消需商家同意，请提交退款申请")
        raise ValidationError(f"订单当前为「{order.status.label}」，不能取消")

    def apply_cancel(self, customer: Account, order_id: int, reason: str) -> None:
        """顾客对制作中订单提交取消申请（REQ-014）：商家 24 小时未处理自动同意。

        申请金额为可退剩余额度（实付减已退），防止部分退款后整单申请超额。
        """
        if not reason.strip():
            raise ValidationError("申请取消必须填写原因")
        order = self._get_own_order(customer, order_id)
        if order.status is not OrderStatus.COOKING:
            raise ValidationError("仅制作中的订单需要申请商家同意取消")
        remaining = self._remaining_refund(order)
        if remaining <= 0:
            raise ValidationError("订单无剩余可退金额")
        self._payments.refund_to_balance(
            order, remaining, f"顾客申请取消：{reason.strip()}",
            requested_by="顾客", refund_type=RefundType.FULL, pending=True)
        self._audit.record(customer, "ORDER", order_id, f"订单 {order.order_no}",
                           "提交取消申请", reason=reason)
        self._audit.notify(self._shop_merchant_id(order.shop_id), "收到取消申请",
                           f"订单 {order.order_no}：{reason}（24 小时未处理将自动同意）")

    # ---------- 商家侧 ----------

    def handle_cancel_apply(self, merchant: Account, refund_id: int, agree: bool,
                            reason: str = "") -> None:
        """商家处理取消申请（REQ-014）：同意则取消订单并退款；拒绝须说明原因。"""
        refund = self._ctx.repos.refunds.get(refund_id)
        if refund is None:
            raise ValidationError("退款申请不存在")
        order = self._ctx.repos.orders.get(refund.order_id)
        self._require_shop_order(merchant, order)
        self._payments.settle_refund(refund, agree, merchant, reason)
        if agree:
            self._orders.cancel(order.order_id,
                                f"商家同意取消：{reason or refund.reason}",
                                0, merchant)      # 退款已由 settle_refund 入账

    # ---------- 管理员侧（REQ-026） ----------

    def force_refund(self, operator: Account, order_id: int, reason: str) -> None:
        """管理员强制退款（REQ-026）：非终态订单取消并全额退款；已完成不开放。"""
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可强制退款")
        if not reason.strip():
            raise ValidationError("强制退款必须填写原因")
        order = self._ctx.repos.orders.get(order_id)
        if order is None:
            raise ValidationError("订单不存在")
        if order.status.is_terminal:
            raise ValidationError("已完成的订单不开放强制退款（REQ-026）")
        if order.status is OrderStatus.PENDING_PAY:
            self._orders.cancel(order_id, f"管理员强制退款：{reason.strip()}",
                                0, operator, release_stock=True)
            return
        payment = self._ctx.repos.payments.find_by_order(order_id)
        refund_fen = payment.amount_fen if payment else 0
        self._orders.cancel(order_id, f"管理员强制退款：{reason.strip()}",
                            refund_fen, operator)

    def settle_as_admin(self, operator: Account, refund_id: int, agree: bool,
                        reason: str = "") -> None:
        """管理员仲裁退款申请（REQ-026 商家长时间不处理时的仲裁入口）。"""
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可仲裁退款")
        refund = self._ctx.repos.refunds.get(refund_id)
        if refund is None:
            raise ValidationError("退款申请不存在")
        order = self._ctx.repos.orders.get(refund.order_id)
        self._payments.settle_refund(refund, agree, operator, reason)
        if agree and order.status is OrderStatus.COOKING:
            self._orders.cancel(order.order_id, "管理员仲裁：同意顾客取消", 0, operator)

    def auto_agree_timeouts(self) -> list:
        """超时 24 小时未处理的取消申请自动同意（REQ-026，调度器调用）。

        商家超时未处理自动同意后不得再撤销（REQ-026 边界）。
        """
        cutoff = (self._ctx.clock.now()
                  - timedelta(hours=REFUND_AUTO_AGREE_HOURS)).isoformat()
        agreed = []
        with self._ctx.lock:
            for refund in self._ctx.repos.refunds.list_pending_before(cutoff):
                order = self._ctx.repos.orders.get(refund.order_id)
                if order.status is not OrderStatus.COOKING:
                    continue                  # 订单已出餐等，转人工仲裁
                self._payments.settle_refund(refund, True, None,
                                             "商家 24 小时未处理，自动同意")
                self._orders.cancel(order.order_id,
                                    "商家 24 小时未处理取消申请，自动同意退款",
                                    0, None)
                agreed.append(refund)
        return agreed

    def list_customer_refunds(self, customer: Account):
        """顾客的退款申请记录。"""
        result = []
        for order in self._orders.list_customer_orders(customer.account_id):
            result.extend(self._payments.list_refunds(order.order_id))
        return result

    # ---------- 内部 ----------

    def _remaining_refund(self, order) -> int:
        """可退剩余额度 = 实付金额 - 已累计退款（REQ-022 对账约束）。"""
        payment = self._ctx.repos.payments.find_by_order(order.order_id)
        paid = payment.amount_fen if payment else 0
        return max(paid - order.refunded_fen, 0)

    def _get_own_order(self, customer: Account, order_id: int):
        """取顾客自己的订单。"""
        order = self._ctx.repos.orders.get(order_id)
        if order is None or order.customer_id != customer.account_id:
            raise ValidationError("订单不存在")
        return order

    def _require_shop_order(self, merchant: Account, order) -> None:
        """校验订单属于商家本店（REQ-001）。"""
        shop = self._ctx.repos.shops.get_by_merchant(merchant.account_id)
        if shop is None or order.shop_id != shop.shop_id:
            raise ValidationError("订单不属于本店")

    def _shop_merchant_id(self, shop_id: int) -> int | None:
        """店铺对应商家账号。"""
        shop = self._ctx.repos.shops.get(shop_id)
        return shop.merchant_id if shop else None
