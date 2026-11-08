"""全链路集成测试：一笔订单从浏览到完成的完整主流程（对应时序图串测）。"""

from tests.conftest import pay_order, place_order

from campus_eats.models.enums import OrderStatus, TaskStatus
from campus_eats.services.config import DELIVERY_FEE_FEN


class TestFullChain:
    """端到端主链路。"""

    def test_browse_to_complete(self, app, customer, merchant, admin, dish_tomato):
        """浏览→搜索→加购→下单→支付→接单→出餐→派单→送达→确认收货。"""
        # 顾客侧
        shops = app.shops.list_operating()
        assert any(s.name == "张记小炒" for s in shops)
        assert any(v.dish.name == "牛肉拉面"
                   for v, _ in app.catalog.search("拉面"))
        order = place_order(app, customer, dish_tomato, qty=2)
        assert order.pay_amount_fen == dish_tomato.price_fen * 2 + DELIVERY_FEE_FEN
        pay_order(app, customer, order)

        # 商家侧
        app.orders.accept(merchant, order.order_id)
        app.orders.ready(merchant, order.order_id)
        task = app.repos.tasks.get_by_order(order.order_id)
        assert task.status is TaskStatus.WAIT_ASSIGN

        # 管理员派单 + 骑手履约
        rider = app.repos.accounts.find_by_phone("13700000001")
        app.dispatch.set_rider_online(rider, True)
        app.dispatch.assign(admin, task.task_id, rider.account_id)
        app.dispatch.accept_task(rider, task.task_id)
        app.dispatch.finish_task(rider, task.task_id)

        # 顾客确认
        app.orders.confirm_receipt(customer, order.order_id)
        fresh = app.repos.orders.get(order.order_id)
        assert fresh.status is OrderStatus.COMPLETED
        assert fresh.completed_at is not None
        assert app.repos.tasks.get(task.task_id).status is TaskStatus.FINISHED

        # 留痕与对账
        logs = app.audit.query_logs(target_type="ORDER", target_id=order.order_id)
        assert {log.action for log in logs} >= {"提交订单", "接单", "出餐", "确认收货"}
        payment = app.repos.payments.find_by_order(order.order_id)
        assert payment.amount_fen == fresh.pay_amount_fen
        stock = app.repos.stocks.get_or_create(
            dish_tomato.dish_id, app.clock.now().date(), dish_tomato.daily_qty)
        assert stock.sold_qty == 2
