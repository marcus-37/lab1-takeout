"""店铺、菜品与每日库存的仓储实现。"""

from datetime import date

from campus_eats.models.enums import DishStatus, ShopStatus
from campus_eats.models.shop_dish import DailyStock, Dish, Shop
from campus_eats.repositories.database import Database, parse_dt


class ShopRepository:
    """店铺的增查改。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def _to_shop(self, row) -> Shop:
        """行转店铺实体。"""
        return Shop(shop_id=row["shop_id"], merchant_id=row["merchant_id"],
                    name=row["name"], category=row["category"], area_code=row["area_code"],
                    address_text=row["address_text"], license_no=row["license_no"],
                    status=ShopStatus(row["status"]), review_reason=row["review_reason"],
                    open_time=row["open_time"], close_time=row["close_time"],
                    created_at=parse_dt(row["created_at"]))

    def add(self, shop: Shop) -> int:
        """新增店铺，回填 shop_id。created_at 须由服务层按服务端时钟设置。"""
        assert shop.created_at is not None, "created_at 必须由服务层按服务端时钟设置"
        shop.shop_id = self._db.execute(
            "INSERT INTO shop (merchant_id, name, category, area_code, address_text,"
            " license_no, status, review_reason, open_time, close_time, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (shop.merchant_id, shop.name, shop.category, shop.area_code, shop.address_text,
             shop.license_no, shop.status.value, shop.review_reason, shop.open_time,
             shop.close_time, shop.created_at.isoformat()))
        return shop.shop_id

    def get(self, shop_id: int) -> Shop | None:
        """按主键查店铺。"""
        row = self._db.query_one("SELECT * FROM shop WHERE shop_id=?", (shop_id,))
        return self._to_shop(row) if row else None

    def get_by_merchant(self, merchant_id: int) -> Shop | None:
        """查商家名下店铺（商家与店铺一一对应，REQ-001）。"""
        row = self._db.query_one("SELECT * FROM shop WHERE merchant_id=?", (merchant_id,))
        return self._to_shop(row) if row else None

    def list_by_status(self, status: ShopStatus) -> list[Shop]:
        """按状态列店铺（入驻审核列表用）。"""
        rows = self._db.query_all(
            "SELECT * FROM shop WHERE status=? ORDER BY shop_id", (status.value,))
        return [self._to_shop(r) for r in rows]

    def list_operating(self) -> list[Shop]:
        """顾客可见的店铺：营业中与休息中；平台关闭不可浏览（REQ-003）。"""
        rows = self._db.query_all(
            "SELECT * FROM shop WHERE status IN (?, ?) ORDER BY shop_id",
            (ShopStatus.OPEN.value, ShopStatus.RESTING.value))
        return [self._to_shop(r) for r in rows]

    def update(self, shop: Shop) -> None:
        """持久化店铺可变字段（状态、驳回原因、营业时间）。"""
        self._db.execute(
            "UPDATE shop SET name=?, status=?, review_reason=?, open_time=?, close_time=?"
            " WHERE shop_id=?",
            (shop.name, shop.status.value, shop.review_reason, shop.open_time,
             shop.close_time, shop.shop_id))


class DishRepository:
    """菜品与销量的仓储。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def _to_dish(self, row) -> Dish:
        """行转菜品实体。"""
        return Dish(dish_id=row["dish_id"], shop_id=row["shop_id"], name=row["name"],
                    price_fen=row["price_fen"], icon=row["icon"],
                    status=DishStatus(row["status"]), daily_qty=row["daily_qty"],
                    sales_count=row["sales_count"], created_at=parse_dt(row["created_at"]))

    def add(self, dish: Dish) -> int:
        """新增菜品，回填 dish_id。created_at 须由服务层按服务端时钟设置。"""
        assert dish.created_at is not None, "created_at 必须由服务层按服务端时钟设置"
        dish.dish_id = self._db.execute(
            "INSERT INTO dish (shop_id, name, price_fen, icon, status, daily_qty,"
            " sales_count, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (dish.shop_id, dish.name, dish.price_fen, dish.icon, dish.status.value,
             dish.daily_qty, dish.sales_count, dish.created_at.isoformat()))
        return dish.dish_id

    def get(self, dish_id: int) -> Dish | None:
        """按主键查菜品。"""
        row = self._db.query_one("SELECT * FROM dish WHERE dish_id=?", (dish_id,))
        return self._to_dish(row) if row else None

    def list_by_shop(self, shop_id: int, include_off: bool = False) -> list[Dish]:
        """列店铺菜品；默认只列上架，商家管理页传 include_off=True 看全部。"""
        if include_off:
            rows = self._db.query_all(
                "SELECT * FROM dish WHERE shop_id=? ORDER BY dish_id", (shop_id,))
        else:
            rows = self._db.query_all(
                "SELECT * FROM dish WHERE shop_id=? AND status=? ORDER BY dish_id",
                (shop_id, DishStatus.ON.value))
        return [self._to_dish(r) for r in rows]

    def search_on_shelf(self, keyword: str, shop_ids: list[int]) -> list[Dish]:
        """在可见店铺范围内按菜名关键字搜索上架菜品（REQ-006）。"""
        if not shop_ids:
            return []
        marks = ",".join("?" * len(shop_ids))
        rows = self._db.query_all(
            f"SELECT * FROM dish WHERE shop_id IN ({marks}) AND status=? AND name LIKE ?"
            " ORDER BY sales_count DESC", (*shop_ids, DishStatus.ON.value, f"%{keyword}%"))
        return [self._to_dish(r) for r in rows]

    def update(self, dish: Dish) -> None:
        """持久化菜品可变字段（价格、状态、每日份数、销量）。"""
        self._db.execute(
            "UPDATE dish SET name=?, price_fen=?, icon=?, status=?, daily_qty=?,"
            " sales_count=? WHERE dish_id=?",
            (dish.name, dish.price_fen, dish.icon, dish.status.value, dish.daily_qty,
             dish.sales_count, dish.dish_id))


class StockRepository:
    """每日库存的仓储：按「菜品 + 日期」一行（REQ-005）。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def _to_stock(self, row) -> DailyStock:
        """行转每日库存实体。"""
        return DailyStock(stock_id=row["stock_id"], dish_id=row["dish_id"],
                          stock_date=date.fromisoformat(row["stock_date"]),
                          total_qty=row["total_qty"], reserved_qty=row["reserved_qty"],
                          sold_qty=row["sold_qty"])

    def get_or_create(self, dish_id: int, day: date, default_total: int) -> DailyStock:
        """取当日库存行；当日首访时按商家的每日份数设置物化生成。

        「次日零点按商家设置数量重置」由日期推进 + 本方法的惰性建行实现：
        新的一天第一次访问自然拿到重置后的份数，已占用的旧库存留在旧行上。
        """
        row = self._db.query_one(
            "SELECT * FROM daily_stock WHERE dish_id=? AND stock_date=?",
            (dish_id, day.isoformat()))
        if row:
            return self._to_stock(row)
        stock = DailyStock(dish_id=dish_id, stock_date=day, total_qty=default_total)
        stock.stock_id = self._db.execute(
            "INSERT INTO daily_stock (dish_id, stock_date, total_qty, reserved_qty,"
            " sold_qty) VALUES (?,?,?,0,0)", (dish_id, day.isoformat(), default_total))
        return stock

    def update(self, stock: DailyStock) -> None:
        """持久化库存三量。"""
        self._db.execute(
            "UPDATE daily_stock SET total_qty=?, reserved_qty=?, sold_qty=? WHERE stock_id=?",
            (stock.total_qty, stock.reserved_qty, stock.sold_qty, stock.stock_id))
