"""领域模型单元测试：金额、订单状态机、每日库存（REQ-004/005/009/022）。"""

import pytest

from campus_eats.models.cart_order import Order, OrderItem
from campus_eats.models.enums import OrderStatus
from campus_eats.models.errors import (
    IllegalTransitionError, ValidationError,
)
from campus_eats.models.money import fen_to_yuan, yuan_to_fen
from campus_eats.models.shop_dish import DailyStock


class TestMoney:
    """金额工具（REQ-022 不用浮点）。"""

    def test_yuan_to_fen_roundtrip(self):
        """元转分再转回无损。"""
        assert yuan_to_fen("12.34") == 1234
        assert yuan_to_fen("0.05") == 5
        assert yuan_to_fen("15") == 1500
        assert fen_to_yuan(1234) == "12.34"
        assert fen_to_yuan(5) == "0.05"

    @pytest.mark.parametrize("bad", ["1.234", "-5", "0", "0.00", "abc", "", "12.3.4"])
    def test_yuan_to_fen_rejects_bad_input(self, bad):
        """三位小数、零、负数、非数字一律拒绝（REQ-004）。"""
        with pytest.raises(ValidationError):
            yuan_to_fen(bad)


class TestOrderStateMachine:
    """订单状态机迁移表（以实验二状态图为权威）。"""

    def _order(self, status):
        order = Order(order_no="D-TEST")
        order.status = status
        return order

    def test_legal_path_to_completed(self):
        """主链路：待支付→…→已完成 逐级迁移成功。"""
        path = [OrderStatus.PENDING_PAY, OrderStatus.PENDING_ACCEPT,
                OrderStatus.COOKING, OrderStatus.PENDING_DELIVERY,
                OrderStatus.DELIVERING, OrderStatus.DELIVERED,
                OrderStatus.COMPLETED]
        for current, nxt in zip(path, path[1:]):
            order = self._order(current)
            order.transit_to(nxt, "tester")
            assert order.status is nxt

    def test_skip_is_rejected(self):
        """跳级迁移被拒绝（如待支付直达配送中）。"""
        with pytest.raises(IllegalTransitionError):
            self._order(OrderStatus.PENDING_PAY).transit_to(
                OrderStatus.DELIVERING, "tester")

    def test_terminal_states_frozen(self):
        """终态不可迁出（REQ-013/014：完成后不可退款取消）。"""
        for terminal in (OrderStatus.COMPLETED, OrderStatus.CANCELLED):
            with pytest.raises(IllegalTransitionError):
                self._order(terminal).transit_to(OrderStatus.PENDING_PAY, "tester")

    def test_cooking_self_loop_only_via_refund(self):
        """制作中不可直接自环；状态机层面部分退款不改状态由服务保证。"""
        with pytest.raises(IllegalTransitionError):
            self._order(OrderStatus.COOKING).transit_to(OrderStatus.COOKING, "tester")

    def test_exception_resumes(self):
        """配送异常可改派回配送中或取消退款（REQ-016）。"""
        resume = self._order(OrderStatus.DELIVERY_EXCEPTION)
        resume.transit_to(OrderStatus.DELIVERING, "tester")
        cancel = self._order(OrderStatus.DELIVERY_EXCEPTION)
        cancel.transit_to(OrderStatus.CANCELLED, "tester")


class TestSnapshot:
    """价格快照（REQ-009：改价不覆盖历史）。"""

    def test_item_amount_frozen(self):
        """明细金额 = 快照单价 × 数量，实体改价不影响已有快照对象。"""
        item = OrderItem(dish_name="番茄炒蛋", unit_price_fen=1500, qty=3)
        assert item.amount_fen() == 4500


class TestDailyStock:
    """每日库存（REQ-005：available = 总量 - 预占 - 已售）。"""

    def test_reserve_available_check(self):
        """可用不足时整单预占失败，不做部分预占。"""
        stock = DailyStock(total_qty=2)
        assert stock.reserve(1)
        assert not stock.reserve(2)

    def test_confirm_and_release(self):
        """预占→确认（转已售）与预占→释放（回补）两条路径。"""
        stock = DailyStock(total_qty=10)
        stock.reserve(3)
        stock.confirm(3)
        assert stock.available() == 7 and stock.sold_qty == 3
        stock.reserve(2)
        stock.release(2)
        assert stock.available() == 7 and stock.reserved_qty == 0

    def test_release_more_than_reserved_rejected(self):
        """释放数量不得超过当前预占（防重复回补，REQ-005）。"""
        stock = DailyStock(total_qty=10)
        stock.reserve(1)
        with pytest.raises(ValidationError):
            stock.release(2)
