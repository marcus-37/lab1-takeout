"""店铺与菜品模块的领域模型，对应类图「店铺与菜品」包。"""

from dataclasses import dataclass
from datetime import date, datetime

from campus_eats.models.enums import DishStatus, ShopStatus
from campus_eats.models.errors import IllegalTransitionError, ValidationError, OutOfStockError
from campus_eats.models.money import assert_positive_fen


@dataclass
class Shop:
    """店铺：商家与店铺一一对应（REQ-001/002/003）。

    类图差异：类图只有营业三态；实现按 REQ-002 补充待审核/已驳回前置态，
    并补充 area_code（按片区派单，REQ-012）与 address_text（骑手取餐地址）。
    """

    shop_id: int | None = None
    merchant_id: int | None = None
    name: str = ""
    category: str = ""
    area_code: str = ""
    address_text: str = ""
    license_no: str = ""
    status: ShopStatus = ShopStatus.PENDING_REVIEW
    review_reason: str = ""          # 驳回原因（REQ-002：驳回须填写原因）
    open_time: str = "10:00"
    close_time: str = "22:00"
    created_at: datetime | None = None

    def open(self) -> None:
        """商家开业：仅休息中可转营业中（REQ-003）。"""
        if self.status is not ShopStatus.RESTING:
            raise IllegalTransitionError(f"店铺「{self.name}」当前{self.status.label}，不能开业")
        self.status = ShopStatus.OPEN

    def rest(self) -> None:
        """商家休息：仅营业中可转休息中；存量订单不受影响（REQ-003）。"""
        if self.status is not ShopStatus.OPEN:
            raise IllegalTransitionError(f"店铺「{self.name}」当前{self.status.label}，不能休息")
        self.status = ShopStatus.RESTING

    def close_by_platform(self, reason: str) -> None:
        """平台强制关店：任何非待审核状态可转平台关闭，须记录原因（REQ-026）。"""
        if self.status is ShopStatus.PENDING_REVIEW:
            raise IllegalTransitionError("待审核的申请不能直接强制关闭，应走驳回")
        if not reason.strip():
            raise ValidationError("强制关店必须填写原因")
        self.status = ShopStatus.PLATFORM_CLOSED
        self.review_reason = reason


@dataclass
class Dish:
    """菜品：一菜一价，无规格无加料（REQ-004）。

    类图差异：补充 shop_id 归属、daily_qty 商家每日供应份数设置
    （库存按日物化为 DailyStock 行，REQ-005）、sales_count 销量（REQ-006 排序）、
    icon 占位（对象存储以 emoji 色块代替，REQ-027 不接外部存储）。
    """

    dish_id: int | None = None
    shop_id: int | None = None
    name: str = ""
    price_fen: int = 0
    icon: str = "🍽"
    status: DishStatus = DishStatus.ON
    daily_qty: int = 0
    sales_count: int = 0
    created_at: datetime | None = None

    def change_price(self, new_price_fen: int) -> None:
        """改价：必须为正数；只影响之后的订单，历史快照不覆盖（REQ-009）。"""
        assert_positive_fen(new_price_fen, "菜品价格")
        self.price_fen = new_price_fen

    def put_on(self) -> None:
        """上架：店铺是否允许营业由服务层校验，领域只改自身状态（REQ-004）。"""
        self.status = DishStatus.ON

    def take_off(self) -> None:
        """下架：购物车中的该菜品条目将标记失效并在下单时拦截（REQ-004/007）。"""
        self.status = DishStatus.OFF


@dataclass
class DailyStock:
    """每日库存：按「菜品 + 日期」一行（REQ-005）。

    可用 = 总量 - 预占 - 已售。提交订单 reserve，超时未支付 release，
    支付成功 confirm；并发不超卖由服务层互斥锁与本类的原子判断共同保证（REQ-023）。
    """

    stock_id: int | None = None
    dish_id: int | None = None
    stock_date: date | None = None
    total_qty: int = 0
    reserved_qty: int = 0
    sold_qty: int = 0

    def available(self) -> int:
        """当前可下单份数。"""
        return self.total_qty - self.reserved_qty - self.sold_qty

    def reserve(self, qty: int) -> bool:
        """预占 qty 份；可用不足返回 False 且不做部分预占（REQ-005/023）。"""
        if qty <= 0 or self.available() < qty:
            return False
        self.reserved_qty += qty
        return True

    def release(self, qty: int) -> None:
        """释放超时未支付或取消订单的预占（REQ-005/010/014）。"""
        if qty <= 0 or qty > self.reserved_qty:
            raise ValidationError("释放数量超出当前预占")
        self.reserved_qty -= qty

    def confirm(self, qty: int) -> None:
        """支付成功后预占转为已售（REQ-005/010）。"""
        if qty <= 0 or qty > self.reserved_qty:
            raise ValidationError("确认数量超出当前预占")
        self.reserved_qty -= qty
        self.sold_qty += qty

    def assert_can_release_all(self) -> None:
        """供超时任务自查：预占为正才需要释放。"""
        if self.reserved_qty < 0:
            raise OutOfStockError("库存数据异常：预占为负")
