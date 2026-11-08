"""订单与支付领域测试：购物车隔离、令牌幂等、快照、余额（REQ-007~010/024）。"""

import pytest
from tests.conftest import pay_order, place_order

from campus_eats.models.account import Customer, hash_password
from campus_eats.models.enums import OrderStatus
from campus_eats.models.errors import (
    CartShopMismatchError, ConflictError, InsufficientBalanceError, OutOfStockError,
    ValidationError,
)
from campus_eats.services.config import DELIVERY_FEE_FEN


class TestCart:
    """购物车（REQ-007）。"""

    def test_cross_shop_rejected(self, app, customer, dish_tomato, merchant):
        """跨店加购被拒，异常信息含清空提示。"""
        other_shop = next(s for s in app.shops.list_operating()
                          if s.shop_id != dish_tomato.shop_id)
        other_dish = app.catalog.list_shop_dishes(other_shop.shop_id)[0].dish
        app.orders.add_to_cart(customer, dish_tomato.shop_id, dish_tomato.dish_id)
        with pytest.raises(CartShopMismatchError):
            app.orders.add_to_cart(customer, other_shop.shop_id, other_dish.dish_id)

    def test_total_accumulates(self, app, customer, dish_tomato):
        """合计 = Σ(加购价 × 数量)。"""
        app.orders.add_to_cart(customer, dish_tomato.shop_id, dish_tomato.dish_id, 2)
        cart, _ = app.orders.view_cart(customer)
        assert cart.total_fen() == dish_tomato.price_fen * 2


class TestSubmitOrder:
    """下单（REQ-008/009/024）。"""

    def test_snapshot_amounts(self, app, customer, dish_tomato):
        """应付 = 商品快照合计 + 配送费；明细按提交时刻价格固化。"""
        order = place_order(app, customer, dish_tomato, qty=2)
        assert order.goods_amount_fen == dish_tomato.price_fen * 2
        assert order.delivery_fee_fen == DELIVERY_FEE_FEN
        assert order.pay_amount_fen == dish_tomato.price_fen * 2 + DELIVERY_FEE_FEN

    def test_price_change_does_not_affect_order(self, app, customer, merchant,
                                                dish_tomato):
        """提交后商家改价，订单金额保持快照（REQ-009）。"""
        order = place_order(app, customer, dish_tomato)
        before = order.pay_amount_fen
        app.catalog.change_price(merchant, dish_tomato.dish_id, "99.00")
        fresh = app.repos.orders.get(order.order_id)
        assert fresh.pay_amount_fen == before
        assert fresh.items[0].unit_price_fen == dish_tomato.price_fen

    def test_building_out_of_range_rejected(self, app, customer, dish_tomato):
        """范围外楼栋直接拦截（REQ-008）。"""
        app.orders.add_to_cart(customer, dish_tomato.shop_id, dish_tomato.dish_id)
        with pytest.raises(ValidationError, match="配送范围"):
            app.orders.submit_order(customer, app.orders.fresh_token(), "X99",
                                    "13800000001")

    def test_bad_phone_rejected(self, app, customer, dish_tomato):
        """电话格式不合法不允许提交（REQ-008）。"""
        with pytest.raises(ValidationError, match="电话"):
            place_order(app, customer, dish_tomato, phone="12345")

    def test_remark_truncated(self, app, customer, dish_tomato):
        """备注超 100 字截断（REQ-008）。"""
        order = place_order(app, customer, dish_tomato, phone="13800000001")
        long_remark = "辣" * 150
        app.orders.clear_cart(customer)
        app.orders.add_to_cart(customer, dish_tomato.shop_id, dish_tomato.dish_id)
        order2 = app.orders.submit_order(customer, app.orders.fresh_token(), "A01",
                                         "13800000001", long_remark)
        assert len(order2.remark) == 100
        assert order.order_no != order2.order_no

    def test_token_idempotent_retry(self, app, customer, dish_tomato):
        """同一令牌重复提交返回首次订单，不产生新单（REQ-024）。"""
        app.orders.add_to_cart(customer, dish_tomato.shop_id, dish_tomato.dish_id)
        token = app.orders.fresh_token()
        first = app.orders.submit_order(customer, token, "A01", "13800000001")
        second = app.orders.submit_order(customer, token, "A01", "13800000001")
        assert first.order_id == second.order_id
        assert len(app.repos.orders.list_by_customer(customer.account_id)) == 1

    def test_token_replay_with_new_content_rejected(self, app, customer, dish_tomato):
        """旧令牌 + 变化内容不得下单；首单取消后旧令牌不复活订单（REQ-024）。"""
        app.orders.add_to_cart(customer, dish_tomato.shop_id, dish_tomato.dish_id)
        token = app.orders.fresh_token()
        first = app.orders.submit_order(customer, token, "A01", "13800000001")
        app.aftersale.cancel_by_customer(customer, first.order_id)
        # 空购物车 + 旧令牌：视为重试，返回原单，不产生新单、不复活
        retry = app.orders.submit_order(customer, token, "A01", "13800000001")
        assert retry.order_id == first.order_id
        assert app.repos.orders.get(first.order_id).status is OrderStatus.CANCELLED
        # 内容变化 + 旧令牌：重放，要求换新令牌
        app.orders.add_to_cart(customer, dish_tomato.shop_id, dish_tomato.dish_id, 3)
        with pytest.raises(ConflictError):
            app.orders.submit_order(customer, token, "A01", "13800000001")

    def test_stock_reserved_then_sold(self, app, customer, dish_tomato):
        """下单预占 → 支付转已售，两阶段不重复（REQ-005）。"""
        order = place_order(app, customer, dish_tomato, qty=3)
        stock = app.repos.stocks.get_or_create(
            dish_tomato.dish_id, app.clock.now().date(), dish_tomato.daily_qty)
        assert stock.reserved_qty == 3 and stock.sold_qty == 0
        pay_order(app, customer, order)
        stock = app.repos.stocks.get_or_create(
            dish_tomato.dish_id, app.clock.now().date(), dish_tomato.daily_qty)
        assert stock.reserved_qty == 0 and stock.sold_qty == 3

    def test_shortage_flagged_before_submit(self, app, customer, dish_tomato):
        """剩余不足在购物车视图即标记失效，提交拦截并说明（REQ-005/007）。"""
        other = app.users.register_customer("13500000001", "123456", "第二顾客")
        app.orders.add_to_cart(customer, dish_tomato.shop_id, dish_tomato.dish_id, 38)
        first = app.orders.submit_order(customer, app.orders.fresh_token(), "A01",
                                        "13800000001")
        app.orders.clear_cart(customer)
        app.orders.add_to_cart(other, dish_tomato.shop_id, dish_tomato.dish_id, 5)
        _, lines = app.orders.view_cart(other)
        assert lines[0].invalid_reason == "仅剩 2 份"
        with pytest.raises(ValidationError, match="失效"):
            app.orders.submit_order(other, app.orders.fresh_token(), "A01",
                                    other.phone)
        stock = app.repos.stocks.get_or_create(
            dish_tomato.dish_id, app.clock.now().date(), dish_tomato.daily_qty)
        assert stock.reserved_qty == 38
        assert first is not None

    def test_multi_line_same_dish_rollback(self, app, customer, merchant):
        """同一菜品拆两行下单，第二行预占失败时第一行回滚（REQ-005）。"""
        dish = app.catalog.add_dish(merchant, "限量饭", "5.00", 10)
        app.orders.add_to_cart(customer, dish.shop_id, dish.dish_id, 6)
        app.orders.add_to_cart(customer, dish.shop_id, dish.dish_id, 6)
        with pytest.raises(OutOfStockError):
            app.orders.submit_order(customer, app.orders.fresh_token(), "A01",
                                    "13800000001")
        stock = app.repos.stocks.get_or_create(dish.dish_id, app.clock.now().date(), 10)
        assert stock.reserved_qty == 0, "失败的整单必须全部回滚，不得留下部分预占"


class TestPayment:
    """余额支付（REQ-010）。"""

    def _poor_customer(self, app, balance=1):
        poor = Customer(phone="13599999999", name="穷顾客",
                        password_hash=hash_password("13599999999", "123456"),
                        balance_fen=balance, created_at=app.clock.now())
        app.repos.accounts.add(poor)
        return app.repos.accounts.find_by_phone("13599999999")

    def test_insufficient_balance(self, app, customer, dish_tomato):
        """余额不足不能支付，订单保持待支付（REQ-010）。"""
        poor = self._poor_customer(app)
        order = place_order(app, poor, dish_tomato, phone=poor.phone)
        with pytest.raises(InsufficientBalanceError):
            app.payments.pay(poor, order.order_id)
        assert app.repos.orders.get(order.order_id).status.value == "待支付"

    def test_double_pay_single_deduction(self, app, customer, dish_tomato):
        """重复支付只扣一次款、返回首次流水（REQ-010/024）。"""
        order = place_order(app, customer, dish_tomato)
        balance = app.repos.accounts.get(customer.account_id).balance_fen
        first = app.payments.pay(customer, order.order_id)
        second = app.payments.pay(customer, order.order_id)
        assert first.payment_id == second.payment_id
        assert app.repos.accounts.get(customer.account_id).balance_fen == \
            balance - order.pay_amount_fen

    def test_balance_never_negative(self, app, dish_tomato):
        """扣款后余额不为负（REQ-022）。"""
        order_budget = 500
        poor = self._poor_customer(app, balance=order_budget)
        order = place_order(app, poor, dish_tomato, phone=poor.phone)
        with pytest.raises(InsufficientBalanceError):
            app.payments.pay(poor, order.order_id)
        assert app.repos.accounts.get(poor.account_id).balance_fen == order_budget
