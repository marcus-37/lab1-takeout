"""配送调度与售后仲裁测试（REQ-011/012/014/016/026）。"""

import pytest
from tests.conftest import pay_order, place_order

from campus_eats.models.enums import OrderStatus, RefundStatus, TaskStatus
from campus_eats.models.errors import PermissionDeniedError, ValidationError


def rider_online(app, phone="13700000001"):
    """取一个在线的同片区骑手（张记小炒在 A 片区）。"""
    rider = app.repos.accounts.find_by_phone(phone)
    app.dispatch.set_rider_online(rider, True)
    return rider


def ready_task(app, customer, merchant, dish):
    """接单 → 出餐，返回订单与任务。"""
    order = pay_order(app, customer, place_order(app, customer, dish))
    app.orders.accept(merchant, order.order_id)
    app.orders.ready(merchant, order.order_id)
    task = app.repos.tasks.get_by_order(order.order_id)
    return order, task


class TestMerchantOps:
    """商家接单、拒单、出餐（REQ-011）。"""

    def test_accept_then_ready(self, app, customer, merchant, dish_tomato):
        """接单转制作中，出餐转待配送并生成任务。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        app.orders.accept(merchant, order.order_id)
        assert app.repos.orders.get(order.order_id).status is OrderStatus.COOKING
        app.orders.ready(merchant, order.order_id)
        assert app.repos.orders.get(order.order_id).status is \
            OrderStatus.PENDING_DELIVERY
        assert app.repos.tasks.get_by_order(order.order_id) is not None

    def test_reject_requires_reason_and_refunds(self, app, customer, merchant,
                                                dish_tomato):
        """拒单必须填原因，退款入账（REQ-011/014）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        balance = app.repos.accounts.get(customer.account_id).balance_fen
        with pytest.raises(ValidationError, match="原因"):
            app.orders.reject(merchant, order.order_id, "  ")
        app.orders.reject(merchant, order.order_id, "菜品售完")
        assert app.repos.orders.get(order.order_id).status is OrderStatus.CANCELLED
        assert app.repos.accounts.get(customer.account_id).balance_fen == \
            balance + order.pay_amount_fen

    def test_rider_cannot_accept_order(self, app, customer, merchant, dish_tomato):
        """商家接口被越权调用直接拒绝（REQ-001）。"""
        rider = rider_online(app)
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        with pytest.raises(PermissionDeniedError):
            app.orders.accept(rider, order.order_id)


class TestDispatch:
    """派单、拒单、改派、异常（REQ-012/016）。"""

    def test_assign_area_mismatch_rejected(self, app, customer, merchant,
                                           dish_tomato, admin):
        """跨片区派单被拒（REQ-012）。"""
        order, task = ready_task(app, customer, merchant, dish_tomato)
        rider_b = app.repos.accounts.find_by_phone("13700000002")
        app.dispatch.set_rider_online(rider_b, True)
        with pytest.raises(ValidationError, match="片区"):
            app.dispatch.assign(admin, task.task_id, rider_b.account_id)

    def test_offline_rider_rejected(self, app, customer, merchant, dish_tomato,
                                    admin):
        """不在线的骑手不可被派单（REQ-012）。"""
        order, task = ready_task(app, customer, merchant, dish_tomato)
        rider = rider_online(app)
        app.dispatch.set_rider_online(rider, False)
        with pytest.raises(ValidationError, match="不在线"):
            app.dispatch.assign(admin, task.task_id, rider.account_id)

    def test_reject_back_to_pool_then_reassign(self, app, customer, merchant,
                                               dish_tomato, admin):
        """骑手拒单回待分配，可改派给同片区其他在线骑手（REQ-012）。"""
        order, task = ready_task(app, customer, merchant, dish_tomato)
        rider = rider_online(app)
        app.dispatch.assign(admin, task.task_id, rider.account_id)
        app.dispatch.reject_task(rider, task.task_id, "临时有事")
        task = app.repos.tasks.get(task.task_id)
        assert task.status is TaskStatus.WAIT_ASSIGN
        other = rider_online(app, "13700000003")
        app.dispatch.reassign(admin, task.task_id, other.account_id, "换人")
        app.dispatch.accept_task(other, task.task_id)
        assert app.repos.orders.get(order.order_id).status is OrderStatus.DELIVERING

    def test_reassign_requires_reason(self, app, customer, merchant, dish_tomato,
                                      admin):
        """改派必须填写原因（REQ-012）。"""
        order, task = ready_task(app, customer, merchant, dish_tomato)
        rider = rider_online(app)
        app.dispatch.assign(admin, task.task_id, rider.account_id)
        other = rider_online(app, "13700000003")
        with pytest.raises(ValidationError, match="原因"):
            app.dispatch.reassign(admin, task.task_id, other.account_id, " ")

    def test_delivery_exception_and_admin_cancel(self, app, customer, merchant,
                                                 dish_tomato, admin):
        """上报异常挂起 → 管理员取消并全额退款（REQ-016）。"""
        order, task = ready_task(app, customer, merchant, dish_tomato)
        rider = rider_online(app)
        app.dispatch.assign(admin, task.task_id, rider.account_id)
        app.dispatch.accept_task(rider, task.task_id)
        balance = app.repos.accounts.get(customer.account_id).balance_fen
        with pytest.raises(ValidationError, match="仅限"):
            app.dispatch.report_exception(rider, task.task_id, "不想送了")
        app.dispatch.report_exception(rider, task.task_id, "联系不上顾客")
        assert app.repos.orders.get(order.order_id).status is \
            OrderStatus.DELIVERY_EXCEPTION
        app.dispatch.cancel_by_admin(admin, task.task_id, "确认无法送达")
        fresh = app.repos.orders.get(order.order_id)
        assert fresh.status is OrderStatus.CANCELLED
        assert app.repos.accounts.get(customer.account_id).balance_fen == \
            balance + order.pay_amount_fen


class TestAftersale:
    """取消、退款与仲裁（REQ-014/026）。"""

    def test_cancel_before_pay_releases_stock(self, app, customer, dish_tomato):
        """待支付取消：不退款、释放预占库存（REQ-014/005）。"""
        order = place_order(app, customer, dish_tomato, qty=2)
        app.aftersale.cancel_by_customer(customer, order.order_id)
        stock = app.repos.stocks.get_or_create(
            dish_tomato.dish_id, app.clock.now().date(), dish_tomato.daily_qty)
        assert app.repos.orders.get(order.order_id).status is OrderStatus.CANCELLED
        assert stock.reserved_qty == 0

    def test_cancel_after_accept_needs_merchant(self, app, customer, merchant,
                                                dish_tomato):
        """制作中不能自行取消，须走申请-同意（REQ-014）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        app.orders.accept(merchant, order.order_id)
        with pytest.raises(ValidationError, match="商家同意"):
            app.aftersale.cancel_by_customer(customer, order.order_id)

    def test_partial_refund_rules(self, app, customer, merchant, dish_tomato):
        """部分退款：金额受可退上限约束，配送费不退（REQ-014/022）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        app.orders.accept(merchant, order.order_id)
        too_much = order.pay_amount_fen            # 含配送费 → 超上限
        with pytest.raises(ValidationError, match="可退"):
            app.orders.refund_partial(order.order_id, too_much, "漏做", merchant)
        app.orders.refund_partial(order.order_id, 500, "漏做一份", merchant)
        fresh = app.repos.orders.get(order.order_id)
        assert fresh.status is OrderStatus.COOKING      # 自环不改状态
        assert fresh.refunded_fen == 500
        refunds = app.payments.list_refunds(order.order_id)
        assert refunds[0].type.value == "部分退款"

    def test_force_refund_rejected_on_completed(self, app, customer, merchant,
                                                dish_tomato, admin):
        """已完成订单不开放强制退款（REQ-026）。"""
        order, task = ready_task(app, customer, merchant, dish_tomato)
        rider = rider_online(app)
        app.dispatch.assign(admin, task.task_id, rider.account_id)
        app.dispatch.accept_task(rider, task.task_id)
        app.dispatch.finish_task(rider, task.task_id)
        app.orders.confirm_receipt(customer, order.order_id)
        with pytest.raises(ValidationError, match="不开放"):
            app.aftersale.force_refund(admin, order.order_id, "争议")

    def test_customer_cannot_force_refund(self, app, customer, dish_tomato):
        """强制退款是管理员专属能力（REQ-026/001）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        with pytest.raises(PermissionDeniedError):
            app.aftersale.force_refund(customer, order.order_id, "试试")

    def test_pending_refund_lifecycle(self, app, customer, merchant, dish_tomato):
        """制作中取消申请：待处理 → 商家拒绝 → 订单继续履约（REQ-014）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        app.orders.accept(merchant, order.order_id)
        app.aftersale.apply_cancel(customer, order.order_id, "等太久了")
        pending = [r for r in app.payments.list_refunds(order.order_id)
                   if r.status is RefundStatus.PENDING]
        assert len(pending) == 1
        app.aftersale.handle_cancel_apply(merchant, pending[0].refund_id, False,
                                          "已在出锅")
        fresh = app.repos.orders.get(order.order_id)
        assert fresh.status is OrderStatus.COOKING
        assert fresh.refunded_fen == 0
        refunds = app.payments.list_refunds(order.order_id)
        assert refunds[-1].status is RefundStatus.REJECTED
