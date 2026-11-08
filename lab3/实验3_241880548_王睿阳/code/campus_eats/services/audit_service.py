"""审计与通知服务（对应组件图 AUDIT）。

REQ-017：审核入驻、驳回、强制关店、封禁账号、改价、接单、拒单、派单、
改派、配送异常处理、强制退款等操作须记录操作人、时间、对象、动作、
变更前后值与原因；记录只可新增，不可修改或删除。
"""

from campus_eats.models.audit import Notification, OperationLog
from campus_eats.services.context import ServiceContext


class AuditService:
    """操作留痕与站内通知，被其余服务组合调用。"""

    def __init__(self, context: ServiceContext) -> None:
        """绑定服务上下文。"""
        self._ctx = context

    def record(self, operator, target_type: str, target_id, target_desc: str,
               action: str, before: str = "", after: str = "", reason: str = "") -> None:
        """写一条操作记录。

        在持有上下文锁的业务流程内调用（调用方已持锁）；写入失败抛出的
        异常会让整个业务操作失败，对应「记录写入失败时该业务操作不得
        提交成功」（REQ-017）。
        """
        now = self._ctx.clock.now()
        self._ctx.repos.logs.add(OperationLog(
            operator_id=getattr(operator, "account_id", None),
            operator_name=getattr(operator, "name", "系统"),
            target_type=target_type, target_id=target_id, target_desc=target_desc,
            action=action, before_value=before, after_value=after, reason=reason,
            created_at=now))

    def notify(self, receiver_id: int | None, title: str, content: str = "") -> None:
        """给某账号发一条站内通知。receiver_id 为空时静默跳过（种子数据外角色）。"""
        if receiver_id is None:
            return
        self._ctx.repos.notifications.add(Notification(
            receiver_id=receiver_id, title=title, content=content,
            created_at=self._ctx.clock.now()))

    def query_logs(self, target_type: str | None = None, target_id: int | None = None,
                   operator_id: int | None = None):
        """按对象 / 操作人查询记录（REQ-017 多维查询）。"""
        return self._ctx.repos.logs.query(
            target_type=target_type, target_id=target_id, operator_id=operator_id)

    def list_notifications(self, receiver_id: int, unread_only: bool = False):
        """某账号的站内通知。"""
        return self._ctx.repos.notifications.list_by_receiver(receiver_id, unread_only)

    def mark_read(self, notification_id: int) -> None:
        """标记通知已读。"""
        self._ctx.repos.notifications.mark_read(notification_id)
