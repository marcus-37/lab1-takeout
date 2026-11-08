"""审计与通知模块的领域模型，对应类图「审计与通知」包。"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class OperationLog:
    """操作记录：只新增、不可修改或删除（REQ-017）。

    记录操作人、时间、对象、动作、变更前后值与原因，保留至少三个月
    （原型以 SQLite 文件整体保留）。
    """

    log_id: int | None = None
    operator_id: int | None = None
    operator_name: str = ""
    target_type: str = ""          # ORDER / SHOP / DISH / ACCOUNT / TASK / REFUND
    target_id: int | None = None
    target_desc: str = ""          # 对象摘要，如 "订单 20261108..."
    action: str = ""               # 接单 / 改价 / 封禁 / 派单 / 改派 …
    before_value: str = ""
    after_value: str = ""
    reason: str = ""
    created_at: datetime | None = None


@dataclass
class Notification:
    """站内通知：状态变化与退款等事件通知相关方（REQ-015/016/026）。"""

    notification_id: int | None = None
    receiver_id: int | None = None
    title: str = ""
    content: str = ""
    read_flag: bool = False
    created_at: datetime | None = None
