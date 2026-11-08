"""应用服务层：网关、八个领域服务、时钟与定时任务调度。

对应实验二组件图的应用服务层 + API 网关 + 定时任务调度。
"""

from campus_eats.services.aftersale_service import AftersaleService
from campus_eats.services.audit_service import AuditService
from campus_eats.services.catalog_service import CatalogService, DishView
from campus_eats.services.clock import Clock, DemoClock, FakeClock, SystemClock
from campus_eats.services.config import (
    ACCEPT_TIMEOUT_MINUTES, AUTO_COMPLETE_HOURS, DELIVERY_FEE_FEN,
    DISPATCH_TIMEOUT_MINUTES, PAY_TIMEOUT_MINUTES, REFUND_AUTO_AGREE_HOURS,
    REMARK_MAX_LEN,
)
from campus_eats.services.context import ServiceContext
from campus_eats.services.dispatch_service import DispatchService
from campus_eats.services.gateway import Gateway
from campus_eats.services.ids import new_token, next_no
from campus_eats.services.order_service import CartLineView, OrderService
from campus_eats.services.payment_service import PaymentService
from campus_eats.services.scheduler import Scheduler
from campus_eats.services.shop_service import ShopService
from campus_eats.services.user_service import UserService

__all__ = [
    "AftersaleService", "AuditService",
    "CatalogService", "DishView",
    "Clock", "DemoClock", "FakeClock", "SystemClock",
    "ACCEPT_TIMEOUT_MINUTES", "AUTO_COMPLETE_HOURS", "DELIVERY_FEE_FEN",
    "DISPATCH_TIMEOUT_MINUTES", "PAY_TIMEOUT_MINUTES", "REFUND_AUTO_AGREE_HOURS",
    "REMARK_MAX_LEN",
    "ServiceContext", "DispatchService", "Gateway",
    "new_token", "next_no",
    "CartLineView", "OrderService", "PaymentService",
    "Scheduler", "ShopService", "UserService",
]
