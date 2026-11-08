"""仓储聚合：把全部仓储打包为一个对象注入服务层。"""

from dataclasses import dataclass, field

from campus_eats.repositories.accounts import AccountRepository, BuildingRepository
from campus_eats.repositories.audit import LogRepository, NotificationRepository
from campus_eats.repositories.catalog import DishRepository, ShopRepository, StockRepository
from campus_eats.repositories.database import Database
from campus_eats.repositories.orders import (
    CartRepository, OrderRepository, PaymentRepository, RefundRepository, TaskRepository,
)


@dataclass
class RepoBundle:
    """全部仓储的集合，服务层通过它访问持久化。"""

    db: Database
    accounts: AccountRepository = field(init=False)
    buildings: BuildingRepository = field(init=False)
    shops: ShopRepository = field(init=False)
    dishes: DishRepository = field(init=False)
    stocks: StockRepository = field(init=False)
    carts: CartRepository = field(init=False)
    orders: OrderRepository = field(init=False)
    payments: PaymentRepository = field(init=False)
    refunds: RefundRepository = field(init=False)
    tasks: TaskRepository = field(init=False)
    logs: LogRepository = field(init=False)
    notifications: NotificationRepository = field(init=False)

    def __post_init__(self) -> None:
        """按同一数据库连接实例化各仓储。"""
        self.accounts = AccountRepository(self.db)
        self.buildings = BuildingRepository(self.db)
        self.shops = ShopRepository(self.db)
        self.dishes = DishRepository(self.db)
        self.stocks = StockRepository(self.db)
        self.carts = CartRepository(self.db)
        self.orders = OrderRepository(self.db)
        self.payments = PaymentRepository(self.db)
        self.refunds = RefundRepository(self.db)
        self.tasks = TaskRepository(self.db)
        self.logs = LogRepository(self.db)
        self.notifications = NotificationRepository(self.db)


def open_repos(path: str) -> RepoBundle:
    """打开（或创建）数据库并返回仓储聚合。

    path 为 ":memory:" 时得到互相隔离的内存库，单元测试使用。
    """
    return RepoBundle(Database(path))
