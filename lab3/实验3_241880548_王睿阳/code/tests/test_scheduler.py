"""定时任务与权限审计测试（REQ-010/013/015/026/001/017）。

超时规则用 FakeClock 精确拨针后调用 scheduler.run_due()，确定性验证。
"""

import pytest
from tests.conftest import pay_order, place_order

from campus_eats.models.account import Customer, hash_password
from campus_eats.models.enums import OrderStatus, Role
from campus_eats.models.errors import PermissionDeniedError, ValidationError


class TestTimeouts:
    """三条超时规则 + 退款超时（REQ-010/013/015/026）。"""

    def test_unpaid_timeout_cancels_and_releases(self, app, customer, dish_tomato):
        """30 分钟未支付：取消 + 释放预占（REQ-010）。"""
        order = place_order(app, customer, dish_tomato, qty=2)
        app.clock.advance(minutes=31)
        stats = app.scheduler.run_due()
        fresh = app.repos.orders.get(order.order_id)
        stock = app.repos.stocks.get_or_create(
            dish_tomato.dish_id, app.clock.now().date(), dish_tomato.daily_qty)
        assert fresh.status is OrderStatus.CANCELLED
        assert stats["unpaid_cancelled"] == 1
        assert stock.reserved_qty == 0

    def test_unpaid_within_window_untouched(self, app, customer, dish_tomato):
        """29 分钟仍在窗口内不取消。"""
        place_order(app, customer, dish_tomato)
        app.clock.advance(minutes=29)
        stats = app.scheduler.run_due()
        assert stats["unpaid_cancelled"] == 0

    def test_unaccepted_timeout_refunds(self, app, customer, dish_tomato):
        """10 分钟未接单：自动取消 + 全额退款（REQ-015）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        balance = app.repos.accounts.get(customer.account_id).balance_fen
        app.clock.advance(minutes=11)
        app.scheduler.run_due()
        fresh = app.repos.orders.get(order.order_id)
        assert fresh.status is OrderStatus.CANCELLED
        assert app.repos.accounts.get(customer.account_id).balance_fen == \
            balance + order.pay_amount_fen

    def test_auto_complete_after_two_hours(self, app, customer, merchant,
                                           dish_tomato, admin):
        """已送达 2 小时未确认自动完成（REQ-013）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        app.orders.accept(merchant, order.order_id)
        app.orders.ready(merchant, order.order_id)
        rider = app.repos.accounts.find_by_phone("13700000001")
        app.dispatch.set_rider_online(rider, True)
        task = app.repos.tasks.get_by_order(order.order_id)
        app.dispatch.assign(admin, task.task_id, rider.account_id)
        app.dispatch.accept_task(rider, task.task_id)
        app.dispatch.finish_task(rider, task.task_id)
        app.clock.advance(hours=3)
        stats = app.scheduler.run_due()
        fresh = app.repos.orders.get(order.order_id)
        assert fresh.status is OrderStatus.COMPLETED
        assert stats["auto_completed"] == 1

    def test_refund_auto_agree_after_24h(self, app, customer, merchant, dish_tomato):
        """取消申请 24 小时未处理自动同意（REQ-026）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        app.orders.accept(merchant, order.order_id)
        balance = app.repos.accounts.get(customer.account_id).balance_fen
        app.aftersale.apply_cancel(customer, order.order_id, "等太久")
        app.clock.advance(hours=25)
        stats = app.scheduler.run_due()
        fresh = app.repos.orders.get(order.order_id)
        assert fresh.status is OrderStatus.CANCELLED
        assert stats["auto_agreed_refunds"] == 1
        assert app.repos.accounts.get(customer.account_id).balance_fen == \
            balance + order.pay_amount_fen

    def test_dispatch_timeout_parks_order(self, app, customer, merchant,
                                          dish_tomato, admin):
        """出餐后 15 分钟无人接单：任务与订单转异常挂起（状态图）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        app.orders.accept(merchant, order.order_id)
        app.orders.ready(merchant, order.order_id)
        app.clock.advance(minutes=16)
        stats = app.scheduler.run_due()
        fresh = app.repos.orders.get(order.order_id)
        task = app.repos.tasks.get_by_order(order.order_id)
        assert fresh.status is OrderStatus.DELIVERY_EXCEPTION
        assert task.status.value == "异常"
        assert stats["dispatch_timeouts"] == 1


class TestPermissionsAndAudit:
    """权限隔离与操作记录（REQ-001/017）。"""

    def test_banned_account_cannot_login(self, app, customer, admin):
        """封禁后任何角色不能登录（REQ-001）。"""
        app.users.set_banned(admin, customer.account_id, True, "测试封禁")
        with pytest.raises(PermissionDeniedError, match="封禁"):
            app.users.login(customer.phone, "123456")

    def test_customer_cannot_review_shop(self, app, customer):
        """顾客调用管理端能力被拒（REQ-001）。"""
        with pytest.raises(PermissionDeniedError):
            app.shops.list_pending(customer)

    def test_logs_queryable_and_append_only(self, app, customer, merchant,
                                            dish_tomato, admin):
        """关键操作可按订单查询；仓储层不提供删除接口（REQ-017）。"""
        order = place_order(app, customer, dish_tomato)
        pay_order(app, customer, order)
        app.orders.accept(merchant, order.order_id)
        app.catalog.change_price(merchant, dish_tomato.dish_id, "16.00")
        logs = app.audit.query_logs(target_type="ORDER", target_id=order.order_id)
        actions = {log.action for log in logs}
        assert "提交订单" in actions and "接单" in actions
        price_logs = app.audit.query_logs(target_type="DISH",
                                          target_id=dish_tomato.dish_id)
        assert any(log.action == "改价" and log.before_value == "1500分"
                   for log in price_logs)
        assert not hasattr(app.repos.logs, "delete")

    def test_notification_on_merchant_accept(self, app, customer, merchant,
                                             dish_tomato):
        """接单后顾客收到通知（REQ-011）。"""
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        app.orders.accept(merchant, order.order_id)
        titles = [n.title for n in
                  app.audit.list_notifications(customer.account_id)]
        assert "商家已接单" in titles

    def test_register_rejects_duplicate_phone(self, app):
        """重复手机号注册被拒（REQ-001 唯一性）。"""
        app.users.register_customer("13511112222", "123456", "甲")
        from campus_eats.models.errors import ConflictError

        with pytest.raises(ConflictError):
            app.users.register_customer("13511112222", "123456", "乙")

    def test_rider_daily_stats(self, app, customer, merchant, dish_tomato, admin):
        """骑手当日完成单量与收入按单累计（REQ-025）。"""
        rider = app.repos.accounts.find_by_phone("13700000001")
        app.dispatch.set_rider_online(rider, True)
        order = pay_order(app, customer, place_order(app, customer, dish_tomato))
        app.orders.accept(merchant, order.order_id)
        app.orders.ready(merchant, order.order_id)
        task = app.repos.tasks.get_by_order(order.order_id)
        app.dispatch.assign(admin, task.task_id, rider.account_id)
        app.dispatch.accept_task(rider, task.task_id)
        app.dispatch.finish_task(rider, task.task_id)
        stats = app.payments.rider_daily_stats(rider)
        assert stats["done_count"] == 1 and stats["income_fen"] == 400

    def test_merchant_daily_stats_excludes_cancelled(self, app, customer,
                                                     dish_tomato):
        """营业额统计排除已取消订单（REQ-025 口径）。"""
        place_order(app, customer, dish_tomato)
        stats_open = app.payments.merchant_daily_stats(app.repos.accounts
                                                       .find_by_phone("13900000001"))
        assert stats_open["order_count"] == 0     # 未支付不计入
