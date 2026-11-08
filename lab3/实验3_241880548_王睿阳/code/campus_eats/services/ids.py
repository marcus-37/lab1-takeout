"""业务单号生成：订单号、支付流水号、退款单号。

格式：日期时间 + 4 位日内序号（如 20261108143025-0007），
时钟来自注入的 Clock，保证演示/测试模式下生成的号与业务时间一致；
序号在锁内自增，并发下不重复。
"""

import itertools
import secrets
import threading

_counter = itertools.count(1)
_lock = threading.Lock()


def next_no(clock, prefix: str = "") -> str:
    """生成一个业务单号（prefix 可为空或单类前缀）。"""
    stamp = clock.now().strftime("%Y%m%d%H%M%S")
    with _lock:
        seq = next(_counter) % 10000
    return f"{prefix}{stamp}-{seq:04d}"


def new_token() -> str:
    """生成一次性提交令牌（REQ-024）：32 位十六进制随机串。"""
    return secrets.token_hex(16)
