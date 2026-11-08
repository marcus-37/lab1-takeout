"""服务端时钟（REQ-027：全系统以服务器时间为唯一时间基准）。

三种实现：
- SystemClock 真实时间，正常运行；
- DemoClock 加速时钟（默认 1 秒 = 1 分钟），演示与人工验收超时规则；
- FakeClock 手动拨针，单元测试确定性构造「30 分钟前」等时刻。

所有服务与定时任务一律从注入的 clock 取当前时间，禁止直接调 datetime.now()。
"""

import threading
from datetime import datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """时钟协议：只有 now() 一个方法。"""

    def now(self) -> datetime:
        """返回当前服务端时间。"""
        ...


class SystemClock:
    """真实系统时钟。"""

    def now(self) -> datetime:
        """当前本地时间。"""
        return datetime.now()


class DemoClock:
    """加速时钟：真实时间流逝 speed 倍映射为业务时间。

    speed=60 时 1 秒真实时间 = 1 分钟业务时间，30 分钟支付超时约 30 秒
    即可观察到，便于课堂演示；计时起点取构造时刻，保证 now() 单调。
    """

    def __init__(self, speed: int = 60, start: datetime | None = None) -> None:
        """speed 为加速倍数，start 为业务时间起点（默认当前真实时间）。"""
        self._speed = speed
        self._real_start = datetime.now()
        self._biz_start = start or self._real_start

    def now(self) -> datetime:
        """按加速倍数换算后的业务时间。"""
        elapsed = datetime.now() - self._real_start
        return self._biz_start + elapsed * self._speed


class FakeClock:
    """测试用时钟：从给定时刻起，只能被 advance 显式拨动。"""

    def __init__(self, start: datetime) -> None:
        """start 为测试设定的初始时刻。"""
        self._current = start
        self._lock = threading.Lock()

    def now(self) -> datetime:
        """返回被拨到的时刻。"""
        with self._lock:
            return self._current

    def advance(self, **kwargs) -> datetime:
        """向前拨动时钟（如 advance(minutes=31)），返回拨后时刻。"""
        with self._lock:
            self._current += timedelta(**kwargs)
            return self._current


def deadline(now: datetime, minutes: int = 0, hours: int = 0) -> datetime:
    """按服务端时间计算期限（now + hours/minutes）。"""
    return now + timedelta(minutes=minutes, hours=hours)
