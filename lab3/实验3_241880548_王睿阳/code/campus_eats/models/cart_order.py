"""购物车与订单模块的领域模型，对应类图「购物车与订单」包。

Order.transit_to 是订单状态机的唯一迁移入口，合法迁移表按实验二状态图
逐条登记；订单服务是唯一调用方，其余服务与界面一律不得触碰 status。
"""

from dataclasses import dataclass, field
from datetime import datetime

from campus_eats.models.enums import OrderStatus
from campus_eats.models.errors import CartShopMismatchError, IllegalTransitionError, ValidationError

# 合法状态迁移表（以实验二状态图为权威）：
# 待支付   -> 待接单（支付成功）/ 已取消（顾客取消、30 分钟超时）
# 待接单   -> 制作中（商家接单）/ 已取消（拒单、10 分钟超时、顾客取消全额退款）
# 制作中   -> 待配送（出餐）/ 已取消（顾客申请且商家同意，未出餐）
# 待配送   -> 配送中（骑手接受任务）/ 配送异常（配送超时挂起）
# 配送中   -> 已送达（骑手确认）/ 配送异常（上报三类原因之一）
# 配送异常 -> 配送中（管理员改派）/ 已取消（管理员核实后全额退款）
# 已送达   -> 已完成（顾客确认或 2 小时自动完成）
# 已完成 / 已取消为终态，不再迁出。
LEGAL_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING_PAY: frozenset({OrderStatus.PENDING_ACCEPT, OrderStatus.CANCELLED}),
    OrderStatus.PENDING_ACCEPT: frozenset({OrderStatus.COOKING, OrderStatus.CANCELLED}),
    OrderStatus.COOKING: frozenset({OrderStatus.PENDING_DELIVERY, OrderStatus.CANCELLED}),
    OrderStatus.PENDING_DELIVERY: frozenset(
        {OrderStatus.DELIVERING, OrderStatus.DELIVERY_EXCEPTION}),
    OrderStatus.DELIVERING: frozenset({OrderStatus.DELIVERED, OrderStatus.DELIVERY_EXCEPTION}),
    OrderStatus.DELIVERY_EXCEPTION: frozenset(
        {OrderStatus.DELIVERING, OrderStatus.CANCELLED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.COMPLETED}),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


@dataclass
class CartItem:
    """购物车条目：added_price_fen 为加购时价格，仅用于展示（REQ-007）。

    订单价格以提交时刻快照为准（REQ-009），加购价不参与金额计算。
    """

    item_id: int | None = None
    cart_id: int | None = None
    dish_id: int | None = None
    dish_name: str = ""
    icon: str = "🍽"
    added_price_fen: int = 0
    qty: int = 1

    def amount_fen(self) -> int:
        """条目小计（加购价 × 数量）。"""
        return self.added_price_fen * self.qty


@dataclass
class Cart:
    """单店购物车：一个购物车只能包含同一店铺的菜品（REQ-007）。

    跨店加购在领域层直接拒绝，由界面层决定提示「清空或取消」的交互。
    """

    cart_id: int | None = None
    customer_id: int | None = None
    shop_id: int | None = None
    items: list[CartItem] = field(default_factory=list)

    def add_item(self, shop_id: int, item: CartItem) -> None:
        """加入条目；购物车已有其他店铺商品时抛 CartShopMismatchError。"""
        if not self.items:
            self.shop_id = shop_id
        elif self.shop_id != shop_id:
            raise CartShopMismatchError("购物车只能包含同一店铺的菜品，请先清空或取消")
        self.items.append(item)

    def clear(self) -> None:
        """清空购物车并解除店铺归属。"""
        self.items.clear()
        self.shop_id = None

    def total_fen(self) -> int:
        """商品合计（不含配送费）。"""
        return sum(item.amount_fen() for item in self.items)


@dataclass
class OrderItem:
    """订单明细快照：单价在提交时刻固化，改价不覆盖历史（REQ-009）。"""

    item_id: int | None = None
    order_id: int | None = None
    dish_id: int | None = None
    dish_name: str = ""
    unit_price_fen: int = 0
    qty: int = 1

    def amount_fen(self) -> int:
        """明细金额 = 快照单价 × 数量（REQ-022）。"""
        return self.unit_price_fen * self.qty


@dataclass
class Order:
    """订单聚合根：金额、地址、快照与状态（REQ-008~014、024）。"""

    order_id: int | None = None
    order_no: str = ""
    customer_id: int | None = None
    shop_id: int | None = None
    status: OrderStatus = OrderStatus.PENDING_PAY
    items: list[OrderItem] = field(default_factory=list)
    goods_amount_fen: int = 0
    delivery_fee_fen: int = 0
    pay_amount_fen: int = 0
    refunded_fen: int = 0          # 累计已退（部分退款可多次，REQ-022 对账用）
    submit_token: str = ""
    building_code: str = ""        # 预设楼栋编号（只能选不能输，REQ-008）
    address_text: str = ""
    phone: str = ""
    remark: str = ""
    cancel_reason: str = ""
    created_at: datetime | None = None
    pay_deadline: datetime | None = None       # 30 分钟未支付自动取消（REQ-010）
    accept_deadline: datetime | None = None    # 10 分钟未接单自动取消（REQ-015）
    delivered_at: datetime | None = None       # 已送达时刻，2 小时自动完成基准（REQ-013）
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None

    def settle_amounts(self, delivery_fee_fen: int) -> None:
        """按明细快照计算并固化三笔金额：商品合计、配送费、应付（REQ-022）。"""
        self.goods_amount_fen = sum(item.amount_fen() for item in self.items)
        self.delivery_fee_fen = delivery_fee_fen
        self.pay_amount_fen = self.goods_amount_fen + self.delivery_fee_fen

    def transit_to(self, next_status: OrderStatus, operator: str) -> None:
        """状态机唯一迁移入口：合法迁移表之外的变更一律拒绝。

        operator 仅进入异常信息；完整留痕（前后值、原因）由订单服务写操作记录。
        """
        if next_status not in LEGAL_TRANSITIONS[self.status]:
            raise IllegalTransitionError(
                f"订单 {self.order_no} 不允许从「{self.status.label}」变更为"
                f"「{next_status.label}」（操作人：{operator}）")
        self.status = next_status

    def assert_phone_valid(self) -> None:
        """联系电话格式校验：11 位数字且以 1 开头（REQ-008）。"""
        if not (len(self.phone) == 11 and self.phone.isdigit() and self.phone[0] == "1"):
            raise ValidationError("联系电话格式不合法")
