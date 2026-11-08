"""骑手端视图：任务列表 + 配送异常上报（对应实验二 UI 稿 8～9 屏）。

首屏展示今日完成单量与收入（REQ-025 按单 4 元口径）、在线开关与
待接受 / 配送中任务；异常上报原因限定三选一（REQ-016）。
界面动作统一捕获业务异常转为弹窗提示，属界面层约定。
"""
# pylint: disable=broad-exception-caught

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from campus_eats.models.enums import TaskStatus
from campus_eats.ui.customer_view import _ask_text
from campus_eats.ui.theme import yuan

FAIL_REASONS = ("联系不上顾客", "地址错误", "无人收货")


class RiderView(QWidget):
    """骑手主视图。"""

    def __init__(self, app, account, on_logout) -> None:
        """绑定应用、骑手账号与登出回调。"""
        super().__init__()
        self._app = app
        self._me = account
        self._on_logout = on_logout

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._topbar())
        self.task_col = QVBoxLayout()
        self.task_col.setSpacing(8)
        holder = QWidget()
        holder.setLayout(self.task_col)
        scroll_area = QWidget()
        col = QVBoxLayout(scroll_area)
        col.setContentsMargins(20, 8, 20, 16)
        col.addWidget(holder)
        col.addStretch(1)
        root.addWidget(scroll_area, 1)
        self.refresh()

    def _topbar(self) -> QWidget:
        """顶部：标题 + 今日数据 + 在线开关 + 登出。"""
        bar_widget = QWidget()
        bar_widget.setObjectName("Root")
        row = QHBoxLayout(bar_widget)
        row.setContentsMargins(20, 12, 20, 12)
        title = QLabel("校园食光 · 骑手端")
        title.setObjectName("H1")
        row.addWidget(title)
        row.addStretch(1)
        self.stats_label = QLabel()
        row.addWidget(self.stats_label)
        self.online_btn = QPushButton()
        self.online_btn.setObjectName("Primary")
        self.online_btn.clicked.connect(self._toggle_online)
        row.addWidget(self.online_btn)
        logout = QPushButton("退出登录")
        logout.clicked.connect(self._on_logout)
        row.addWidget(logout)
        return bar_widget

    def refresh(self) -> None:
        """刷新今日数据与任务列表（QTimer 周期调用）。"""
        stats = self._app.payments.rider_daily_stats(self._me)
        self.stats_label.setText(
            f"今日完成 {stats['done_count']} 单 · 收入 {yuan(stats['income_fen'])}"
            "（按单 4 元，口径待确认，REQ-025）")
        self.online_btn.setText("下线" if self._me.online else "上线接单")
        self.online_btn.setEnabled(True)
        while self.task_col.count():
            item = self.task_col.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        tasks = self._app.repos.tasks.list_by_rider(self._me.account_id)
        if not tasks:
            empty = QLabel("暂无任务" + ("" if self._me.online else "（上线后管理员才能派单给你）"))
            empty.setObjectName("Hint")
            self.task_col.addWidget(empty)
        for task in tasks:
            self.task_col.addWidget(self._task_card(task))
        self.task_col.addStretch(1)

    def _task_card(self, task) -> QWidget:
        """一张任务卡：状态、取送地址、动作。"""
        card = QWidget()
        card.setObjectName("Card")
        col = QVBoxLayout(card)
        col.setContentsMargins(16, 10, 16, 10)
        head = QHBoxLayout()
        no = QLabel(f"订单 {task.order_no}")
        no.setObjectName("H2")
        status = QLabel(task.status.label)
        status.setObjectName("Badge")
        head.addWidget(no)
        head.addWidget(status)
        head.addStretch(1)
        col.addLayout(head)
        col.addWidget(QLabel(f"取餐：{task.pickup_text}　→　送达：{task.dropoff_text}"
                             f"　（片区 {task.area_code}）"))
        row = QHBoxLayout()
        if task.status is TaskStatus.WAIT_ACCEPT:
            accept = QPushButton("接受任务")
            accept.setObjectName("Primary")
            accept.clicked.connect(lambda: self._act(
                lambda: self._app.dispatch.accept_task(self._me, task.task_id)))
            reject = QPushButton("拒绝")
            reject.setObjectName("Danger")
            reject.clicked.connect(self._reject(task))
            row.addWidget(accept)
            row.addWidget(reject)
        elif task.status is TaskStatus.DELIVERING:
            done = QPushButton("确认送达")
            done.setObjectName("Primary")
            done.clicked.connect(lambda: self._act(
                lambda: self._app.dispatch.finish_task(self._me, task.task_id)))
            fail = QPushButton("上报配送失败")
            fail.setObjectName("Danger")
            fail.clicked.connect(self._report(task))
            row.addWidget(done)
            row.addWidget(fail)
        row.addStretch(1)
        col.addLayout(row)
        return card

    def _act(self, fn) -> None:
        """执行动作并把异常转为提示。"""
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "操作失败", str(exc))
        self.refresh()

    def _toggle_online(self) -> None:
        """上线 / 下线。"""
        self._app.dispatch.set_rider_online(self._me, not self._me.online)
        self.refresh()

    def _reject(self, task):
        """拒绝任务：填写原因留痕。"""
        def _do():
            reason, ok = _ask_text(self, "拒绝任务", "拒绝原因（管理员可见并重新派单）：")
            if not ok:
                return
            self._app.dispatch.reject_task(self._me, task.task_id, reason)
        return _do

    def _report(self, task):
        """异常上报：原因三选一 + 补充说明。"""
        def _do():
            reason, ok = _ask_text(
                self, "上报配送失败",
                "原因（三选一，直接填写）：\n" + "\n".join(FAIL_REASONS))
            if not ok or reason not in FAIL_REASONS:
                if ok:
                    QMessageBox.warning(self, "原因不合法",
                                        "仅限：联系不上顾客 / 地址错误 / 无人收货")
                return
            detail, ok2 = _ask_text(self, "补充说明", "补充说明（可留空）：")
            if not ok2:
                return
            self._app.dispatch.report_exception(self._me, task.task_id, reason, detail)
        return _do
