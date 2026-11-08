"""配送模块的领域模型，对应类图「配送」包，另含预设楼栋（REQ-008）。"""

from dataclasses import dataclass
from datetime import datetime

from campus_eats.models.enums import TaskStatus
from campus_eats.models.errors import IllegalTransitionError, ValidationError

# 任务状态迁移表：待分配 -> 待接受 -> 配送中 -> 已完成 / 异常；
# 骑手拒绝：待接受 -> 待分配；管理员改派：已指派（含待接受）或异常 -> 待接受，
# 改派是换人不是改状态，待接受 -> 待接受 为自环（REQ-012「已指派订单可改派」）；
# 配送超时：待分配 -> 异常（挂起转管理员处置，对应状态图「配送超时」）。
TASK_LEGAL_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.WAIT_ASSIGN: frozenset({TaskStatus.WAIT_ACCEPT, TaskStatus.EXCEPTION}),
    TaskStatus.WAIT_ACCEPT: frozenset(
        {TaskStatus.DELIVERING, TaskStatus.WAIT_ASSIGN, TaskStatus.WAIT_ACCEPT}),
    TaskStatus.DELIVERING: frozenset({TaskStatus.FINISHED, TaskStatus.EXCEPTION}),
    TaskStatus.EXCEPTION: frozenset({TaskStatus.WAIT_ACCEPT}),
    TaskStatus.FINISHED: frozenset(),
}


@dataclass
class DeliveryTask:
    """配送任务：与待配送之后的订单一一对应（REQ-012/013/016）。"""

    task_id: int | None = None
    order_id: int | None = None
    order_no: str = ""
    rider_id: int | None = None
    rider_name: str = ""
    status: TaskStatus = TaskStatus.WAIT_ASSIGN
    area_code: str = ""
    pickup_text: str = ""          # 取餐地址（店铺地址）
    dropoff_text: str = ""         # 送达地址（顾客楼栋门牌）
    fail_reason: str = ""
    assigned_at: datetime | None = None
    completed_at: datetime | None = None

    def _transit(self, next_status: TaskStatus, action: str) -> None:
        """内部迁移：合法迁移表校验通过后变更状态（语义见 TASK_LEGAL_TRANSITIONS）。"""
        if next_status not in TASK_LEGAL_TRANSITIONS[self.status]:
            raise IllegalTransitionError(
                f"配送任务 {self.order_no} 不允许从「{self.status.label}」"
                f"{action}为「{next_status.label}」")
        self.status = next_status

    def assign(self, rider_id: int, rider_name: str) -> None:
        """管理员指派骑手：仅待分配可指派；同一订单不会同时指派两人由服务层互斥保证。"""
        self._transit(TaskStatus.WAIT_ACCEPT, "指派")
        self.rider_id = rider_id
        self.rider_name = rider_name

    def reject(self) -> None:
        """骑手拒绝：任务回到待分配，订单保持待配送（REQ-012）。"""
        self._transit(TaskStatus.WAIT_ASSIGN, "拒绝")
        self.rider_id = None
        self.rider_name = ""

    def accept(self) -> None:
        """骑手接受：任务进入配送中，订单由订单服务同步转配送中。"""
        self._transit(TaskStatus.DELIVERING, "接受")

    def reassign(self, rider_id: int, rider_name: str, reason: str) -> None:
        """管理员改派：待分配或异常状态可改派，须填写原因（REQ-012/016）。"""
        if not reason.strip():
            raise ValidationError("改派必须填写原因")
        self._transit(TaskStatus.WAIT_ACCEPT, "改派")
        self.rider_id = rider_id
        self.rider_name = rider_name

    def report_exception(self, reason: str) -> None:
        """骑手上报配送失败：原因限定三类（REQ-016）。"""
        allowed = ("联系不上顾客", "地址错误", "无人收货")
        if reason not in allowed:
            raise ValidationError("配送失败原因仅限：联系不上顾客、地址错误、无人收货")
        self._transit(TaskStatus.EXCEPTION, "上报")
        self.fail_reason = reason

    def mark_timeout(self) -> None:
        """调度任务标记配送超时：长时间无人接单，挂起转管理员处置（状态图）。"""
        self._transit(TaskStatus.EXCEPTION, "超时")
        self.fail_reason = "配送超时：长时间无人接单，转管理员处置"

    def finish(self) -> None:
        """骑手确认送达：任务完成，订单由订单服务转已送达。"""
        self._transit(TaskStatus.FINISHED, "完成")


@dataclass
class Building:
    """预设收货楼栋：地址只能从列表选择，不能手工输入（REQ-008/027）。

    类图差异：类图把地址压缩为 Order.addressText 一个字符串；
    实现按 REQ-008 单独建楼栋模型以支撑配送范围校验。
    """

    code: str = ""                 # 楼栋编号，如 "A03"
    name: str = ""                 # 展示名，如 "梧桐苑 3 栋"
    in_range: bool = True          # 是否在平台配送范围内
