"""商品与库存服务（对应组件图 CAT，REQ-004/005/006/009）。"""

from dataclasses import dataclass
from datetime import date

from campus_eats.models.account import Account
from campus_eats.models.enums import DishStatus, Role, ShopStatus
from campus_eats.models.errors import PermissionDeniedError, ValidationError
from campus_eats.models.money import yuan_to_fen
from campus_eats.models.shop_dish import DailyStock, Dish
from campus_eats.services.audit_service import AuditService
from campus_eats.services.context import ServiceContext


@dataclass
class DishView:
    """顾客端菜品行：菜品信息 + 当日可用份数（REQ-006 售罄标记）。"""

    dish: Dish
    available_qty: int

    @property
    def sold_out(self) -> bool:
        """当日可用份数为零即售罄（REQ-005）。"""
        return self.available_qty <= 0


class CatalogService:
    """菜品管理与库存查询。商家改价走本服务并留痕（REQ-009）。"""

    def __init__(self, context: ServiceContext, audit: AuditService) -> None:
        """绑定上下文与审计服务。"""
        self._ctx = context
        self._audit = audit

    # ---------- 商家侧 ----------

    def add_dish(self, merchant: Account, name: str, price_text: str,
                 daily_qty: int, icon: str = "🍽") -> Dish:
        """新增菜品（REQ-004）：价格为正且最多两位小数，份数为非负整数。"""
        with self._ctx.lock:
            shop = self._require_merchant_shop(merchant)
            dish = Dish(shop_id=shop.shop_id, name=name.strip(),
                        price_fen=self._parse_price(price_text),
                        icon=icon or "🍽", daily_qty=self._parse_qty(daily_qty),
                        status=DishStatus.ON, created_at=self._ctx.clock.now())
            if not dish.name:
                raise ValidationError("菜品名称不能为空")
            self._ctx.repos.dishes.add(dish)
            self._audit.record(merchant, "DISH", dish.dish_id,
                               f"{shop.name}·{dish.name}", "新增菜品",
                               after=f"{dish.price_fen}分/日供{dish.daily_qty}份")
            return dish

    def change_price(self, merchant: Account, dish_id: int, price_text: str) -> Dish:
        """改价（REQ-009）：记录改价前后价格；不影响历史订单快照。"""
        with self._ctx.lock:
            dish = self._require_merchant_dish(merchant, dish_id)
            before = dish.price_fen
            dish.change_price(self._parse_price(price_text))
            self._ctx.repos.dishes.update(dish)
            self._audit.record(merchant, "DISH", dish_id,
                               f"菜品 {dish.name}", "改价",
                               before=f"{before}分", after=f"{dish.price_fen}分")
            return dish

    def put_on(self, merchant: Account, dish_id: int) -> Dish:
        """上架菜品（REQ-004）。"""
        with self._ctx.lock:
            dish = self._require_merchant_dish(merchant, dish_id)
            dish.put_on()
            self._ctx.repos.dishes.update(dish)
            self._audit.record(merchant, "DISH", dish_id, f"菜品 {dish.name}",
                               "上架", after=DishStatus.ON.label)
            return dish

    def take_off(self, merchant: Account, dish_id: int) -> Dish:
        """下架菜品（REQ-004）：购物车中该菜品条目将在下单时拦截。"""
        with self._ctx.lock:
            dish = self._require_merchant_dish(merchant, dish_id)
            dish.take_off()
            self._ctx.repos.dishes.update(dish)
            self._audit.record(merchant, "DISH", dish_id, f"菜品 {dish.name}",
                               "下架", after=DishStatus.OFF.label)
            return dish

    def set_daily_qty(self, merchant: Account, dish_id: int, daily_qty: int) -> Dish:
        """设置每日供应份数（REQ-005）：只影响次日新库存行，
        当日已占用（预占+已售）不受影响——修改的是次日物化的总量。
        """
        with self._ctx.lock:
            dish = self._require_merchant_dish(merchant, dish_id)
            dish.daily_qty = self._parse_qty(daily_qty)
            self._ctx.repos.dishes.update(dish)
            self._audit.record(merchant, "DISH", dish_id, f"菜品 {dish.name}",
                               "设置每日份数", after=f"{dish.daily_qty}份")
            return dish

    def list_own_dishes(self, merchant: Account, include_off: bool = True) -> list[Dish]:
        """商家菜品列表（含下架）。"""
        shop = self._require_merchant_shop(merchant)
        return self._ctx.repos.dishes.list_by_shop(shop.shop_id, include_off)

    def list_own_stocks(self, merchant: Account) -> list[tuple[Dish, DailyStock]]:
        """商家当日库存视图：菜品 + 今日库存行（REQ-005 商家设置入口）。"""
        shop = self._require_merchant_shop(merchant)
        today = self._ctx.clock.now().date()
        result = []
        for dish in self._ctx.repos.dishes.list_by_shop(shop.shop_id, include_off=True):
            result.append((dish, self._ctx.repos.stocks.get_or_create(
                dish.dish_id, today, dish.daily_qty)))
        return result

    # ---------- 顾客侧 ----------

    def list_shop_dishes(self, shop_id: int) -> list[DishView]:
        """顾客浏览某店上架菜品，带当日可用份数（REQ-006）。"""
        today = self._ctx.clock.now().date()
        views = []
        for dish in self._ctx.repos.dishes.list_by_shop(shop_id, include_off=False):
            stock = self._ctx.repos.stocks.get_or_create(dish.dish_id, today,
                                                         dish.daily_qty)
            views.append(DishView(dish=dish, available_qty=stock.available()))
        return views

    def search(self, keyword: str) -> list[tuple[DishView, object]]:
        """按菜名关键字搜索全部可见店铺的上架菜品（REQ-006）。

        返回（菜品视图, 店铺）对，按销量降序；无结果返回空列表而非报错。
        """
        shop_ids = [s.shop_id for s in self._ctx.repos.shops.list_operating()]
        shops = {s.shop_id: s for s in self._ctx.repos.shops.list_operating()}
        today = self._ctx.clock.now().date()
        result = []
        for dish in self._ctx.repos.dishes.search_on_shelf(keyword.strip(), shop_ids):
            stock = self._ctx.repos.stocks.get_or_create(dish.dish_id, today,
                                                         dish.daily_qty)
            result.append((DishView(dish=dish, available_qty=stock.available()),
                           shops[dish.shop_id]))
        return result

    def available_of(self, dish_id: int, day: date | None = None) -> int:
        """某菜品当日可用份数（订单服务预占前检查用）。"""
        dish = self._ctx.repos.dishes.get(dish_id)
        if dish is None:
            return 0
        stock = self._ctx.repos.stocks.get_or_create(
            dish_id, day or self._ctx.clock.now().date(), dish.daily_qty)
        return stock.available()

    def list_all_dishes(self) -> list[Dish]:
        """全部菜品（调度器跨日库存重置用，SCH -> CAT）。"""
        return self._ctx.repos.dishes.list_all()

    # ---------- 内部 ----------

    def _parse_price(self, text: str) -> int:
        """把元的字符串转为分（REQ-004 最多两位小数）。"""
        return yuan_to_fen(text)

    @staticmethod
    def _parse_qty(daily_qty: int) -> int:
        """每日份数必须为非负整数。"""
        if not isinstance(daily_qty, int) or daily_qty < 0:
            raise ValidationError("每日供应份数必须为非负整数")
        return daily_qty

    def _require_merchant_shop(self, merchant: Account):
        """取商家已过审的店铺；未过审不能管理菜品（REQ-002/004）。"""
        if merchant.role is not Role.MERCHANT:
            raise PermissionDeniedError("只有商家账号可管理菜品")
        shop = self._ctx.repos.shops.get_by_merchant(merchant.account_id)
        if shop is None or not shop.status.is_operating:
            raise ValidationError("店铺未通过入驻审核，不能管理菜品")
        if shop.status is ShopStatus.PLATFORM_CLOSED:
            raise ValidationError("店铺已被平台关闭，不能管理菜品")
        return shop

    def _require_merchant_dish(self, merchant: Account, dish_id: int) -> Dish:
        """取本店菜品；越权操作他店菜品直接拒绝（REQ-001）。"""
        shop = self._require_merchant_shop(merchant)
        dish = self._ctx.repos.dishes.get(dish_id)
        if dish is None or dish.shop_id != shop.shop_id:
            raise ValidationError("菜品不存在或不属于本店")
        return dish
