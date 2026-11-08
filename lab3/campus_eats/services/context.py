"""服务上下文：仓储、时钟与全局互斥锁的汇聚点。

并发模型（对应 REQ-005/010/023 的并发约束）：原型采用「全局一把大锁 +
锁内完成读-改-写」的粗粒度互斥。所有涉及库存三量、余额、状态机迁移的
服务方法都在该锁内执行读-改-写，SQLite 层另有写锁兜底单语句原子性。
原型规模下该方案足够，且比细粒度锁更容易论证正确性——这一取舍写入报告。
"""

import threading

from campus_eats.repositories.bundle import RepoBundle
from campus_eats.services.clock import Clock


class ServiceContext:
    """服务共享的运行环境。"""

    def __init__(self, repos: RepoBundle, clock: Clock) -> None:
        """绑定仓储与时钟，创建全局互斥锁。"""
        self.repos = repos
        self.clock = clock
        self.lock = threading.RLock()
