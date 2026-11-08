"""操作记录与站内通知的仓储实现。"""

from campus_eats.models.audit import Notification, OperationLog
from campus_eats.repositories.database import Database, parse_dt


class LogRepository:
    """操作记录仓储：只新增、只查询，不提供修改与删除（REQ-017）。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def add(self, log: OperationLog) -> int:
        """写入操作记录，回填 log_id。"""
        assert log.created_at is not None, "created_at 必须由服务层按服务端时钟设置"
        log.log_id = self._db.execute(
            "INSERT INTO operation_log (operator_id, operator_name, target_type, target_id,"
            " target_desc, action, before_value, after_value, reason, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (log.operator_id, log.operator_name, log.target_type, log.target_id,
             log.target_desc, log.action, log.before_value, log.after_value, log.reason,
             log.created_at.isoformat()))
        return log.log_id

    def query(self, target_type: str | None = None, target_id: int | None = None,
              operator_id: int | None = None) -> list[OperationLog]:
        """按对象、操作人组合查询记录，新的在前（REQ-017 多维查询）。"""
        sql = "SELECT * FROM operation_log"
        conds, params = [], []
        if target_type:
            conds.append("target_type=?")
            params.append(target_type)
        if target_id is not None:
            conds.append("target_id=?")
            params.append(target_id)
        if operator_id is not None:
            conds.append("operator_id=?")
            params.append(operator_id)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY log_id DESC LIMIT 500"
        rows = self._db.query_all(sql, tuple(params))
        return [
            OperationLog(log_id=r["log_id"], operator_id=r["operator_id"],
                         operator_name=r["operator_name"], target_type=r["target_type"],
                         target_id=r["target_id"], target_desc=r["target_desc"],
                         action=r["action"], before_value=r["before_value"],
                         after_value=r["after_value"], reason=r["reason"],
                         created_at=parse_dt(r["created_at"]))
            for r in rows
        ]


class NotificationRepository:
    """站内通知仓储。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def add(self, notification: Notification) -> int:
        """写入通知，回填 notification_id。"""
        assert notification.created_at is not None
        notification.notification_id = self._db.execute(
            "INSERT INTO notification (receiver_id, title, content, read_flag, created_at)"
            " VALUES (?,?,?,?,?)",
            (notification.receiver_id, notification.title, notification.content,
             int(notification.read_flag), notification.created_at.isoformat()))
        return notification.notification_id

    def list_by_receiver(self, receiver_id: int, unread_only: bool = False) -> list[Notification]:
        """某人的通知，新的在前；unread_only=True 只看未读。"""
        if unread_only:
            rows = self._db.query_all(
                "SELECT * FROM notification WHERE receiver_id=? AND read_flag=0"
                " ORDER BY notification_id DESC", (receiver_id,))
        else:
            rows = self._db.query_all(
                "SELECT * FROM notification WHERE receiver_id=?"
                " ORDER BY notification_id DESC", (receiver_id,))
        return [
            Notification(notification_id=r["notification_id"], receiver_id=r["receiver_id"],
                         title=r["title"], content=r["content"], read_flag=bool(r["read_flag"]),
                         created_at=parse_dt(r["created_at"]))
            for r in rows
        ]

    def mark_read(self, notification_id: int) -> None:
        """标记已读。"""
        self._db.execute("UPDATE notification SET read_flag=1 WHERE notification_id=?",
                         (notification_id,))
