"""仓储层：SQLite 持久化，隔离领域模型与存储细节。

单文件库代替组件图中的 MySQL；业务代码只面对实体与仓储接口，
替换为其他数据库时服务层不需要改动。
"""

from campus_eats.repositories.accounts import AccountRepository, BuildingRepository
from campus_eats.repositories.audit import LogRepository, NotificationRepository
from campus_eats.repositories.bundle import RepoBundle, open_repos
from campus_eats.repositories.catalog import DishRepository, ShopRepository, StockRepository
from campus_eats.repositories.database import Database, fmt_dt, parse_dt
from campus_eats.repositories.orders import (
    CartRepository, OrderRepository, PaymentRepository, RefundRepository, TaskRepository,
)

__all__ = [
    "AccountRepository", "BuildingRepository",
    "LogRepository", "NotificationRepository",
    "RepoBundle", "open_repos",
    "DishRepository", "ShopRepository", "StockRepository",
    "Database", "fmt_dt", "parse_dt",
    "CartRepository", "OrderRepository", "PaymentRepository", "RefundRepository",
    "TaskRepository",
]
