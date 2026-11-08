"""领域模型层：与实验二类图的六个包一一对应。

每张 UML 类图对应一个模块；与类图的差异都在各模块 docstring 与字段注释中
逐条说明，收尾时统一回改实验二类图。
"""

from campus_eats.models.account import (
    Account, Admin, Customer, Merchant, Rider, hash_password, verify_password,
)
from campus_eats.models.audit import Notification, OperationLog
from campus_eats.models.cart_order import (
    LEGAL_TRANSITIONS, Cart, CartItem, Order, OrderItem,
)
from campus_eats.models.delivery import TASK_LEGAL_TRANSITIONS, Building, DeliveryTask
from campus_eats.models.enums import (
    AccountStatus, DishStatus, OrderStatus, PayStatus, RefundStatus, RefundType, Role,
    ShopStatus, TaskStatus,
)
from campus_eats.models.errors import (
    CartShopMismatchError, ConflictError, DomainError, IllegalTransitionError,
    InsufficientBalanceError, OutOfStockError, PermissionDeniedError, ValidationError,
)
from campus_eats.models.money import assert_positive_fen, fen_to_yuan, yuan_to_fen
from campus_eats.models.payment_refund import Payment, Refund
from campus_eats.models.shop_dish import DailyStock, Dish, Shop

__all__ = [
    "Account", "Admin", "Customer", "Merchant", "Rider",
    "hash_password", "verify_password",
    "Notification", "OperationLog",
    "LEGAL_TRANSITIONS", "Cart", "CartItem", "Order", "OrderItem",
    "TASK_LEGAL_TRANSITIONS", "Building", "DeliveryTask",
    "AccountStatus", "DishStatus", "OrderStatus", "PayStatus", "RefundStatus",
    "RefundType", "Role", "ShopStatus", "TaskStatus",
    "CartShopMismatchError", "ConflictError", "DomainError", "IllegalTransitionError",
    "InsufficientBalanceError", "OutOfStockError", "PermissionDeniedError",
    "ValidationError",
    "assert_positive_fen", "fen_to_yuan", "yuan_to_fen",
    "Payment", "Refund",
    "DailyStock", "Dish", "Shop",
]
