"""并发测试：REQ-023 库存不超卖 + REQ-024 令牌幂等并发。"""

import threading

from campus_eats.models.enums import OrderStatus
from tests.conftest import place_order


def _register_many(app, admin, count):
    """注册 count 个余额充足的并发顾客。"""
    users = [app.users.register_customer(f"135{i:08d}", "123456", f"并发{i}")
             for i in range(count)]
    return users


class TestConcurrency:
    """REQ-005/023：并发下单不超卖。"""

    def test_200_threads_race_for_10_stock(self, app, admin, merchant):
        """库存 10，200 并发提交：恰好 10 单成功、库存归零不为负。"""
        dish = app.catalog.add_dish(merchant, "限量蛋糕", "9.99", 10, "🍰")
        users = _register_many(app, admin, 200)
        barrier = threading.Barrier(200)
        success, lock = [], threading.Lock()

        def rush(user):
            """单个并发用户：加购 + 提交。"""
            barrier.wait()
            try:
                app.orders.add_to_cart(user, dish.shop_id, dish.dish_id)
                placed = app.orders.submit_order(user, app.orders.fresh_token(),
                                                 "A01", user.phone)
                with lock:
                    success.append(placed.order_id)
            except Exception:            # pylint: disable=broad-exception-caught
                pass                     # 售罄即预期失败

        threads = [threading.Thread(target=rush, args=(u,)) for u in users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        stock = app.repos.stocks.get_or_create(
            dish.dish_id, app.clock.now().date(), 10)
        assert len(set(success)) == 10, f"应恰好 10 单，实际 {len(set(success))}"
        assert stock.available() == 0
        assert stock.reserved_qty == 10 and stock.sold_qty == 0   # 均未支付

    def test_concurrent_pay_single_deduction(self, app, customer, dish_tomato):
        """并发重复支付同一订单：余额只扣一次（REQ-010 幂等）。"""
        order = place_order(app, customer, dish_tomato)
        balance = app.repos.accounts.get(customer.account_id).balance_fen
        barrier = threading.Barrier(8)
        results, lock = [], threading.Lock()

        def pay():
            """并发支付。"""
            barrier.wait()
            payment = app.payments.pay(customer, order.order_id)
            with lock:
                results.append(payment.payment_id)

        threads = [threading.Thread(target=pay) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(set(results)) == 1
        assert app.repos.accounts.get(customer.account_id).balance_fen == \
            balance - order.pay_amount_fen

    def test_timeout_vs_pay_race_single_outcome(self, app, customer, dish_tomato):
        """超时取消与支付并发：只允许一种结果（REQ-010 边界）。"""
        order = place_order(app, customer, dish_tomato)
        app.clock.advance(minutes=30)            # 恰在超时边界
        balance = app.repos.accounts.get(customer.account_id).balance_fen
        outcome = []

        def do_pay():
            """支付线程。"""
            try:
                app.payments.pay(customer, order.order_id)
                outcome.append("paid")
            except Exception:                    # pylint: disable=broad-exception-caught
                outcome.append("pay-failed")

        def do_timeout():
            """超时线程。"""
            app.orders.cancel_unpaid_timeouts()
            outcome.append("timeout")

        payer = threading.Thread(target=do_pay)
        timer = threading.Thread(target=do_timeout)
        payer.start()
        timer.start()
        payer.join()
        timer.join()

        fresh = app.repos.orders.get(order.order_id)
        paid_amount = order.pay_amount_fen
        current_balance = app.repos.accounts.get(customer.account_id).balance_fen
        if fresh.status is OrderStatus.PENDING_ACCEPT:
            assert outcome.count("paid") == 1
            assert current_balance == balance - paid_amount
        else:
            assert fresh.status is OrderStatus.CANCELLED
            assert current_balance == balance
        # 关键不变量：余额变化与订单状态一一对应，不出现"扣款且取消退款"叠加
        delta = current_balance - balance
        assert delta in (-paid_amount, 0)
