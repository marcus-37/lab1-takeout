"""定时任务调度（对应组件图 SCH）。

四条自动规则 + 每日库存重置（REQ-005/010/013/015/026）：
- 30 分钟未支付取消并释放库存；
- 10 分钟未接单取消并全额退款；
- 已送达 2 小时未确认自动完成；
- 取消申请 24 小时未处理自动同意退款；
- 跨日后为全部菜品物化当日库存行（次日零点重置的落点）。

run_due() 供测试直接调用（配合 FakeClock 精确控制）；start() 起后台线程
每秒扫描一次，演示加速时钟下超时规则几十秒内即可观察。
"""

import threading
import traceback

from campus_eats.services.audit_service import AuditService
from campus_eats.services.context import ServiceContext


class Scheduler:
    """到期任务扫描器：规则执行与线程循环分离，便于测试。"""

    def __init__(self, context: ServiceContext, audit: AuditService,
                 order_service, dispatch_service, aftersale_service,
                 catalog_service) -> None:
        """绑定上下文与四个被调度服务的引用。"""
        self._ctx = context
        self._audit = audit
        self._orders = order_service
        self._dispatch = dispatch_service
        self._aftersale = aftersale_service
        self._catalog = catalog_service
        self._last_reset_date = context.clock.now().date()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def run_due(self) -> dict:
        """执行全部到期任务，返回各类计数（测试断言与界面状态栏用）。"""
        stats = {
            "unpaid_cancelled": len(self._orders.cancel_unpaid_timeouts()),
            "unaccepted_cancelled": len(self._orders.cancel_unaccepted_timeouts()),
            "auto_completed": len(self._orders.auto_complete_timeouts()),
            "auto_agreed_refunds": len(self._aftersale.auto_agree_timeouts()),
            "dispatch_timeouts": len(self._dispatch.dispatch_timeouts()),
            "stocks_reset": 0,
        }
        stats["stocks_reset"] = self._reset_stocks_if_new_day()
        return stats

    def _reset_stocks_if_new_day(self) -> int:
        """跨日零点为全部上架菜品物化当日库存行（SCH -> CAT，REQ-005）。"""
        today = self._ctx.clock.now().date()
        if today == self._last_reset_date:
            return 0
        created = 0
        with self._ctx.lock:
            for dish in self._catalog.list_all_dishes():
                self._ctx.repos.stocks.get_or_create(dish.dish_id, today,
                                                     dish.daily_qty)
                created += 1
        self._last_reset_date = today
        return created

    def start(self) -> None:
        """启动后台扫描线程（守护线程，进程退出自动结束）。"""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="campus-eats-scheduler")
        self._thread.start()

    def stop(self) -> None:
        """停止后台线程。"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    def _loop(self) -> None:
        """每秒扫描一次；演示加速时钟下 1 秒 = 1 分钟业务时间。"""
        while not self._stop_event.wait(1.0):
            try:
                self.run_due()
            except Exception:                  # pylint: disable=broad-exception-caught
                traceback.print_exc()          # 调度线程不允许因单次异常死亡
