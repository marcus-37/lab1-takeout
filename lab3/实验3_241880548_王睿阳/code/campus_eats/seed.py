"""种子数据：首次建库时写入演示账号、店铺、菜品与预设楼栋。

通过服务层写入而非直插数据库——种子过程本身就是对装配链路的第一次
全链路验证（申请→审核→开业→上菜→设置库存）。
"""

from campus_eats.models.account import (
    Admin, Customer, Merchant, Rider, hash_password,
)
from campus_eats.models.delivery import Building
from campus_eats.services.audit_service import AuditService
from campus_eats.services.catalog_service import CatalogService
from campus_eats.services.context import ServiceContext
from campus_eats.services.shop_service import ShopService

# 演示账号统一密码，报告与 README 中说明
DEMO_PASSWORD = "123456"

BUILDINGS = [
    ("A01", "梧桐苑 1 栋", True), ("A02", "梧桐苑 2 栋", True),
    ("A03", "梧桐苑 3 栋", True), ("B01", "听雨轩 1 栋", True),
    ("B02", "听雨轩 2 栋", True), ("C01", "教工宿舍 1 栋", True),
    ("X99", "东区校外公寓", False),        # 配送范围外（REQ-008 验收用）
]


def seed(context: ServiceContext) -> None:
    """写入种子数据；数据库已有账号时跳过（幂等）。"""
    if context.repos.accounts.find_by_phone("13600000001") is not None:
        return
    now = context.clock.now().replace(microsecond=0)
    shops = ShopService(context, AuditService(context))
    catalog = CatalogService(context, AuditService(context))

    admin = Admin(phone="13600000001", name="平台管理员",
                  password_hash=hash_password("13600000001", DEMO_PASSWORD),
                  created_at=now)
    context.repos.accounts.add(admin)

    customers = [
        ("13800000001", "王小阳", 8800),
        ("13800000002", "李知恩", 120_00),
    ]
    for phone, name, balance in customers:
        context.repos.accounts.add(Customer(
            phone=phone, name=name,
            password_hash=hash_password(phone, DEMO_PASSWORD),
            balance_fen=balance, created_at=now))

    for merchant_row in _merchants():
        _seed_merchant(context, shops, catalog, admin, merchant_row, now)

    riders = [
        ("13700000001", "骑手小陈", "A"),
        ("13700000002", "骑手老周", "B"),
        ("13700000003", "骑手小吴", "A"),
    ]
    for phone, name, area in riders:
        context.repos.accounts.add(Rider(
            phone=phone, name=name,
            password_hash=hash_password(phone, DEMO_PASSWORD),
            area_code=area, created_at=now))

    for code, name, in_range in BUILDINGS:
        context.repos.buildings.add(Building(code=code, name=name,
                                             in_range=in_range))


def _merchants() -> list:
    """演示商家与菜品清单。"""
    return [
        ("13900000001", "张记小炒", "家常菜", "A", "桂花园商铺 12 号",
         "LIC-2026-001",
         [("番茄炒蛋", "15.00", 40, "🍅"), ("鱼香肉丝", "22.00", 30, "🥢"),
          ("紫菜蛋花汤", "8.50", 50, "🥣")]),
        ("13900000002", "面面俱到", "面食", "B", "桂花园商铺 3 号",
         "LIC-2026-002",
         [("牛肉拉面", "18.00", 60, "🍜"), ("炸酱面", "14.00", 40, "🍲"),
          ("凉拌黄瓜", "6.00", 30, "🥒")]),
    ]


def _seed_merchant(context: ServiceContext, shops, catalog, admin,
                   row: tuple, now) -> None:
    """写入一个商家：账号 → 申请 → 审核 → 开业 → 上菜。"""
    phone, shop_name, category, area, address, lic, dishes = row
    merchant = Merchant(phone=phone, name=f"{shop_name}·店长",
                        password_hash=hash_password(phone, DEMO_PASSWORD),
                        license_no=lic, created_at=now)
    context.repos.accounts.add(merchant)
    shop = shops.apply(merchant, shop_name, category, area, address, lic)
    shops.review(admin, shop.shop_id, approve=True)
    shops.open(merchant)
    for dish_name, price, qty, icon in dishes:
        catalog.add_dish(merchant, dish_name, price, qty, icon)
