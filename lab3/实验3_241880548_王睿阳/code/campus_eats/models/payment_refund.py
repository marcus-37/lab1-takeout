"""支付与退款模块的领域模型，对应类图「支付与退款」包。"""

from dataclasses import dataclass
from datetime import datetime

from campus_eats.models.enums import PayStatus, RefundStatus, RefundType


@dataclass
class Payment:
    """支付流水：一单最多一条成功流水（REQ-010/022）。

    重复支付请求命中已有流水时直接返回首次结果，不产生第二条（REQ-024）。
    """

    payment_id: int | None = None
    pay_no: str = ""
    order_id: int | None = None
    order_no: str = ""
    amount_fen: int = 0
    status: PayStatus = PayStatus.SUCCESS
    paid_at: datetime | None = None


@dataclass
class Refund:
    """退款记录：只新增不修改（整单/部分，REQ-014/022/026）。

    类图差异：补充 requested_by 与状态字段。超时自动取消等即时退款
    直接落 DONE；接单后需商家同意的取消申请先落 PENDING，
    商家 24 小时未处理由调度任务自动同意（REQ-026）。
    """

    refund_id: int | None = None
    refund_no: str = ""
    order_id: int | None = None
    order_no: str = ""
    amount_fen: int = 0
    type: RefundType = RefundType.FULL
    status: RefundStatus = RefundStatus.DONE
    reason: str = ""
    requested_by: str = ""         # 顾客 / 商家 / 管理员 / 系统
    created_at: datetime | None = None
    settled_at: datetime | None = None
