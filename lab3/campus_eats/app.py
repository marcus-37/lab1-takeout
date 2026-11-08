"""应用装配根：建库、种子数据、服务装配、调度器与界面启动。

装配关系与组件图一致：客户端层（ui）只经网关（gateway）访问应用服务层
（services），服务层经仓储（repositories）访问 SQLite；定时调度注入四个
被驱动服务；跨服务引用（支付回写订单、配送回写订单、售后调用两者、
出餐生成任务）全部在此装配，服务之间不相互构造。
"""

import argparse
import os

from campus_eats.repositories import open_repos
from campus_eats.ui.main_window import run_ui
from campus_eats.seed import seed
from campus_eats.services.audit_service import AuditService
from campus_eats.services.aftersale_service import AftersaleService
from campus_eats.services.catalog_service import CatalogService
from campus_eats.services.clock import DemoClock, SystemClock
from campus_eats.services.context import ServiceContext
from campus_eats.services.dispatch_service import DispatchService
from campus_eats.services.gateway import Gateway
from campus_eats.services.order_service import OrderService
from campus_eats.services.payment_service import PaymentService
from campus_eats.services.scheduler import Scheduler
from campus_eats.services.shop_service import ShopService
from campus_eats.services.user_service import UserService

DB_FILENAME = "campus_eats.db"


class App:
    """组装完成的应用对象：聚合全部服务供界面与测试使用。"""

    def __init__(self, db_path: str, demo: bool = False, clock=None) -> None:
        """打开数据库、装配服务。

        clock 可注入 FakeClock（测试）或 DemoClock（demo=True 时自动创建），
        缺省为真实系统时钟。
        """
        if clock is not None:
            self.clock = clock
        elif demo:
            self.clock = DemoClock(speed=60)
        else:
            self.clock = SystemClock()
        self.repos = open_repos(db_path)
        self.ctx = ServiceContext(self.repos, self.clock)

        self.audit = AuditService(self.ctx)
        self.users = UserService(self.ctx)
        self.shops = ShopService(self.ctx, self.audit)
        self.catalog = CatalogService(self.ctx, self.audit)
        self.orders = OrderService(self.ctx, self.audit)
        self.payments = PaymentService(self.ctx, self.audit)
        self.dispatch = DispatchService(self.ctx, self.audit)
        self.aftersale = AftersaleService(self.ctx, self.audit)

        # 跨服务接线（对应组件图服务间箭头）
        self.orders.set_payment_service(self.payments)
        self.payments.set_order_service(self.orders)
        self.dispatch.set_order_service(self.orders)
        self.aftersale.set_dependencies(self.orders, self.payments)
        self.orders.on_order_ready = self.dispatch.create_task   # ORD -> DISP

        self.scheduler = Scheduler(self.ctx, self.audit, self.orders,
                                   self.dispatch, self.aftersale, self.catalog)
        self.gateway = Gateway(self.users)

        seed(self.ctx)

    def close(self) -> None:
        """停调度、关数据库。"""
        self.scheduler.stop()
        self.repos.db.close()


def build_argparser() -> argparse.ArgumentParser:
    """命令行参数：--demo 开启时间加速，--memory 使用内存数据库。"""
    parser = argparse.ArgumentParser(prog="campus_eats", description="校园食光")
    parser.add_argument("--demo", action="store_true",
                        help="演示模式：时间加速 60 倍（1 秒 = 1 分钟）")
    parser.add_argument("--memory", action="store_true",
                        help="使用内存数据库（不落盘，用于快速体验）")
    return parser


def main() -> int:
    """程序入口：装配应用并启动 PySide6 界面。"""
    args = build_argparser().parse_args()
    db_path = ":memory:" if args.memory else os.path.abspath(DB_FILENAME)
    app = App(db_path, demo=args.demo)
    app.scheduler.start()

    try:
        run_ui(app)
    finally:
        app.close()
    return 0
