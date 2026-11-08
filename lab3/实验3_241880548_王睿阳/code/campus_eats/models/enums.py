"""领域枚举。

与实验二类图的「枚举」包对应，有一处设计-实现差异：OrderStatus 依据状态图
与 REQ-016 补充了「配送异常」挂起状态（类图枚举中缺失，收尾时已回改类图）。
枚举值直接使用中文，便于持久化与界面展示，label 属性即枚举值本身。
"""

from enum import Enum, unique


@unique
class Role(Enum):
    """账号角色，四类角色权限互相隔离（REQ-001）。"""

    CUSTOMER = "顾客"
    MERCHANT = "商家"
    RIDER = "骑手"
    ADMIN = "管理员"

    @property
    def label(self) -> str:
        """界面显示名。"""
        return self.value


@unique
class AccountStatus(Enum):
    """账号状态：封禁后任何角色均不能登录（REQ-001）。"""

    NORMAL = "正常"
    BANNED = "已封禁"

    @property
    def label(self) -> str:
        """界面显示名。"""
        return self.value


@unique
class ShopStatus(Enum):
    """店铺状态。

    类图只画了营业三态（营业中/休息中/平台关闭）；实现按 REQ-002 的入驻
    审核流程补充了待审核与已驳回两个前置状态，共五态。
    """

    PENDING_REVIEW = "待审核"
    REJECTED = "已驳回"
    OPEN = "营业中"
    RESTING = "休息中"
    PLATFORM_CLOSED = "平台关闭"

    @property
    def label(self) -> str:
        """界面显示名。"""
        return self.value

    @property
    def is_operating(self) -> bool:
        """是否已通过审核进入营业三态（审核通过后初始为休息中，REQ-002）。"""
        return self in (ShopStatus.OPEN, ShopStatus.RESTING, ShopStatus.PLATFORM_CLOSED)


@unique
class DishStatus(Enum):
    """菜品上下架状态：下架菜品不可点单但购物车中保留并标记失效（REQ-004/007）。"""

    ON = "上架"
    OFF = "下架"

    @property
    def label(self) -> str:
        """界面显示名。"""
        return self.value


@unique
class OrderStatus(Enum):
    """订单状态机，以实验二状态图为权威：八个状态外加配送异常挂起态。"""

    PENDING_PAY = "待支付"
    PENDING_ACCEPT = "待接单"
    COOKING = "制作中"
    PENDING_DELIVERY = "待配送"
    DELIVERING = "配送中"
    DELIVERED = "已送达"
    COMPLETED = "已完成"
    CANCELLED = "已取消"
    DELIVERY_EXCEPTION = "配送异常"

    @property
    def label(self) -> str:
        """界面显示名。"""
        return self.value

    @property
    def is_terminal(self) -> bool:
        """是否终态：已完成与已取消不可再取消或退款（REQ-013/014）。"""
        return self in (OrderStatus.COMPLETED, OrderStatus.CANCELLED)


@unique
class PayStatus(Enum):
    """支付流水状态。

    原型中支付即时成功或失败；仅成功支付落 Payment 流水（REQ-010/022），
    失败尝试不生成流水，避免与「重复支付返回首次结果」的语义冲突。
    """

    SUCCESS = "成功"
    FAILED = "失败"

    @property
    def label(self) -> str:
        """界面显示名。"""
        return self.value


@unique
class RefundType(Enum):
    """退款类型：整单全额 / 漏做菜品部分退款（配送费不退，REQ-014）。

    管理员强制退款（REQ-026）在金额口径上是整单退款，以操作人与原因区分。
    """

    FULL = "整单退款"
    PARTIAL = "部分退款"

    @property
    def label(self) -> str:
        """界面显示名。"""
        return self.value


@unique
class RefundStatus(Enum):
    """退款状态：超时自动取消等即时退款直接落 DONE；需商家同意的先落 PENDING。"""

    PENDING = "待处理"
    DONE = "已退款"
    REJECTED = "已拒绝"

    @property
    def label(self) -> str:
        """界面显示名。"""
        return self.value


@unique
class TaskStatus(Enum):
    """配送任务状态（对应类图 DeliveryTask.status）。

    待分配 -> 已指派待接受（骑手可拒绝回到待分配）-> 配送中 ->
    已完成 / 异常（异常可改派回已指派待接受）。
    """

    WAIT_ASSIGN = "待分配"
    WAIT_ACCEPT = "待接受"
    DELIVERING = "配送中"
    EXCEPTION = "异常"
    FINISHED = "已完成"

    @property
    def label(self) -> str:
        """界面显示名。"""
        return self.value
