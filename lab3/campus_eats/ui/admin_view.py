"""管理端视图：入驻审核、派单与异常处置、订单干预、账号封禁、操作记录。

对应实验二 UI 稿 10～11 屏：审核列表带资质与原因必填；干预页把订单信息、
处置动作与操作记录放在一起（REQ-017 留痕字段直接可见）。
界面动作统一经 _act 兜底业务异常并转为弹窗提示，属界面层约定。
"""
# pylint: disable=broad-exception-caught

from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from campus_eats.models.enums import OrderStatus, Role
from campus_eats.ui.customer_view import _ask_text
from campus_eats.ui.theme import yuan


class AdminView(QWidget):
    """管理员主视图：两页签。"""

    def __init__(self, app, account, on_logout) -> None:
        """绑定应用、管理员账号与登出回调。"""
        super().__init__()
        self._app = app
        self._me = account
        self._on_logout = on_logout

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        bar_widget = QWidget()
        bar_widget.setObjectName("Root")
        row = QHBoxLayout(bar_widget)
        row.setContentsMargins(20, 12, 20, 12)
        title = QLabel("校园食光 · 平台管理端")
        title.setObjectName("H1")
        row.addWidget(title)
        review_tab = QPushButton("入驻审核")
        review_tab.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        ops_tab = QPushButton("派单与干预")
        ops_tab.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        row.addWidget(review_tab)
        row.addWidget(ops_tab)
        row.addStretch(1)
        logout = QPushButton("退出登录")
        logout.clicked.connect(self._on_logout)
        row.addWidget(logout)
        root.addWidget(bar_widget)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.pages.addWidget(self._build_review_page())
        self.pages.addWidget(self._build_ops_page())
        self.refresh()

    # ---------- 页面一：入驻审核 ----------

    def _build_review_page(self) -> QWidget:
        """待审核申请表：通过 / 驳回（原因必填）。"""
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 8, 20, 16)
        self.review_table = QTableWidget(0, 5)
        self.review_table.setHorizontalHeaderLabels(
            ["店铺", "商家", "类目 / 片区", "执照号", "操作"])
        self.review_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.review_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        col.addWidget(QLabel("待审核入驻申请（REQ-002：通过转休息中，驳回必须填原因）"))
        col.addWidget(self.review_table, 1)
        return page

    def _refresh_review(self) -> None:
        """渲染待审核列表。"""
        pending = self._app.shops.list_pending(self._me)
        self.review_table.setRowCount(len(pending))
        for i, shop in enumerate(pending):
            merchant = self._app.repos.accounts.get(shop.merchant_id)
            self.review_table.setItem(i, 0, QTableWidgetItem(shop.name))
            self.review_table.setItem(i, 1, QTableWidgetItem(
                merchant.name if merchant else "-"))
            self.review_table.setItem(i, 2, QTableWidgetItem(
                f"{shop.category} · 片区 {shop.area_code}"))
            self.review_table.setItem(i, 3, QTableWidgetItem(shop.license_no))
            ops = QWidget()
            row = QHBoxLayout(ops)
            row.setContentsMargins(2, 2, 2, 2)
            approve = QPushButton("通过")
            approve.setObjectName("Primary")
            approve.clicked.connect(lambda _=False, s=shop: self._act(
                lambda: self._app.shops.review(self._me, s.shop_id, True)))
            reject = QPushButton("驳回")
            reject.setObjectName("Danger")
            reject.clicked.connect(lambda _=False, s=shop: self._reject_shop(s))
            row.addWidget(approve)
            row.addWidget(reject)
            self.review_table.setCellWidget(i, 4, ops)

    def _reject_shop(self, shop) -> None:
        """驳回入驻：原因必填（REQ-002）。"""
        reason, ok = _ask_text(self, "驳回申请", f"驳回「{shop.name}」的原因：")
        if not ok or not reason:
            return
        self._act(lambda: self._app.shops.review(self._me, shop.shop_id,
                                                 False, reason))

    # ---------- 页面二：派单与干预 ----------

    def _build_ops_page(self) -> QWidget:
        """派单区 + 异常队列 + 订单干预 + 操作记录。"""
        page = QWidget()
        cols = QHBoxLayout(page)
        cols.setContentsMargins(20, 8, 20, 16)
        cols.setSpacing(12)

        left = QVBoxLayout()
        left.addWidget(QLabel("待派送任务（REQ-012：指派在线同片区骑手）"))
        self.assign_list = QVBoxLayout()
        self.assign_list.setSpacing(8)
        left.addLayout(self.assign_list)
        left.addStretch(1)
        left.addWidget(QLabel("配送异常待处置（REQ-016：改派或取消退款）"))
        self.exception_list = QVBoxLayout()
        self.exception_list.setSpacing(8)
        left.addLayout(self.exception_list)
        left.addStretch(1)
        left_col = QWidget()
        left_col.setLayout(left)
        cols.addWidget(left_col, 5)

        mid = QVBoxLayout()
        mid.addWidget(QLabel("争议订单强制退款（REQ-026：已完成订单不开放）"))
        self.order_list = QVBoxLayout()
        self.order_list.setSpacing(8)
        mid.addLayout(self.order_list)
        mid.addStretch(1)
        mid_col = QWidget()
        mid_col.setLayout(mid)
        cols.addWidget(mid_col, 5)

        right = QVBoxLayout()
        right.addWidget(QLabel("账号封禁（REQ-026）"))
        self.ban_list = QVBoxLayout()
        self.ban_list.setSpacing(8)
        right.addLayout(self.ban_list)
        right.addStretch(1)
        right.addWidget(QLabel("操作记录（REQ-017：只增不删改）"))
        self.log_table = QTableWidget(0, 5)
        self.log_table.setHorizontalHeaderLabels(
            ["时间", "操作人", "动作", "对象", "原因 / 变更"])
        self.log_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        right.addWidget(self.log_table, 1)
        right_col = QWidget()
        right_col.setLayout(right)
        cols.addWidget(right_col, 6)
        return page

    # ---------- 刷新 ----------

    def refresh(self) -> None:
        """刷新两页（QTimer 周期调用）。"""
        self._refresh_review()
        self._refresh_ops()

    def _refresh_ops(self) -> None:
        """派单队列、异常队列、争议订单、封禁列表、操作记录。"""
        for layout in (self.assign_list, self.exception_list, self.order_list,
                       self.ban_list):
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()

        riders = [r for r in self._app.repos.accounts.list_by_role(Role.RIDER)
                  if r.online]
        for task in self._app.dispatch.list_wait_assign(self._me):
            self.assign_list.addWidget(self._assign_card(task, riders))
        if not self._app.dispatch.list_wait_assign(self._me):
            empty = QLabel("暂无待派送任务")
            empty.setObjectName("Hint")
            self.assign_list.addWidget(empty)

        for task in self._app.dispatch.list_exceptions(self._me):
            self.exception_list.addWidget(self._exception_card(task))

        for status in (OrderStatus.DELIVERING, OrderStatus.DELIVERED):
            for order in self._app.orders.list_by_status(status):
                self.order_list.addWidget(self._intervene_card(order))

        for account in self._app.repos.accounts.list_by_role(Role.RIDER):
            self.ban_list.addWidget(self._ban_card(account, "骑手"))
        for account in self._app.repos.accounts.list_by_role(Role.MERCHANT):
            self.ban_list.addWidget(self._ban_card(account, "商家"))

        logs = self._app.audit.query_logs()
        self.log_table.setRowCount(min(len(logs), 30))
        for i, log in enumerate(logs[:30]):
            self.log_table.setItem(i, 0, QTableWidgetItem(
                log.created_at.strftime("%m-%d %H:%M") if log.created_at else ""))
            self.log_table.setItem(i, 1, QTableWidgetItem(log.operator_name))
            self.log_table.setItem(i, 2, QTableWidgetItem(log.action))
            self.log_table.setItem(i, 3, QTableWidgetItem(
                f"{log.target_type} {log.target_desc}"))
            change = log.reason or f"{log.before_value} → {log.after_value}"
            self.log_table.setItem(i, 4, QTableWidgetItem(change))

    def _assign_card(self, task, riders) -> QWidget:
        """待派送任务卡：按骑手逐个指派。"""
        card = QWidget()
        card.setObjectName("Card")
        col = QVBoxLayout(card)
        col.setContentsMargins(12, 8, 12, 8)
        col.addWidget(QLabel(f"{task.order_no} · {task.pickup_text} → {task.dropoff_text}"
                             f"（片区 {task.area_code}）"))
        row = QHBoxLayout()
        if not riders:
            row.addWidget(QLabel("暂无在线骑手"))
        for rider in riders:
            if rider.area_code != task.area_code:
                continue
            btn = QPushButton(f"派给 {rider.name}")
            btn.clicked.connect(lambda _=False, t=task, r=rider: self._act(
                lambda: self._app.dispatch.assign(self._me, t.task_id, r.account_id)))
            row.addWidget(btn)
        row.addStretch(1)
        col.addLayout(row)
        return card

    def _exception_card(self, task) -> QWidget:
        """异常任务卡：改派 / 取消退款。"""
        card = QWidget()
        card.setObjectName("Card")
        col = QVBoxLayout(card)
        col.setContentsMargins(12, 8, 12, 8)
        col.addWidget(QLabel(f"{task.order_no} · {task.fail_reason or '配送异常'}"))
        row = QHBoxLayout()
        riders = [r for r in self._app.repos.accounts.list_by_role(Role.RIDER)
                  if r.online and r.area_code == task.area_code
                  and r.account_id != task.rider_id]
        for rider in riders:
            btn = QPushButton(f"改派 {rider.name}")
            btn.clicked.connect(lambda _=False, t=task, r=rider: self._reassign(t, r))
            row.addWidget(btn)
        cancel = QPushButton("取消并全额退款")
        cancel.setObjectName("Danger")
        cancel.clicked.connect(lambda _=False, t=task: self._cancel_task(t))
        row.addWidget(cancel)
        row.addStretch(1)
        col.addLayout(row)
        return card

    def _intervene_card(self, order) -> QWidget:
        """争议订单卡：强制退款入口。"""
        card = QWidget()
        card.setObjectName("Card")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 8, 12, 8)
        info = QLabel(f"{order.order_no} · {order.status.label} · "
                      f"{yuan(order.pay_amount_fen)}")
        row.addWidget(info, 1)
        refund = QPushButton("强制退款")
        refund.setObjectName("Danger")
        refund.clicked.connect(lambda _=False, o=order: self._force_refund(o))
        row.addWidget(refund)
        return card

    def _ban_card(self, account, role_text: str) -> QWidget:
        """账号封禁卡。"""
        card = QWidget()
        card.setObjectName("Card")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 6, 12, 6)
        status = "已封禁" if account.status.label == "已封禁" else "正常"
        row.addWidget(QLabel(f"{role_text} {account.name}（{account.phone}）· {status}"))
        row.addStretch(1)
        if account.status.label == "已封禁":
            unban = QPushButton("解封")
            unban.clicked.connect(lambda _=False, a=account: self._act(
                lambda: self._app.users.set_banned(self._me, a.account_id, False)))
            row.addWidget(unban)
        else:
            ban = QPushButton("封禁")
            ban.setObjectName("Danger")
            ban.clicked.connect(lambda _=False, a=account: self._ban(a))
            row.addWidget(ban)
        return card

    # ---------- 动作 ----------

    def _act(self, fn) -> None:
        """执行动作并把异常转为提示。"""
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "操作失败", str(exc))
        self.refresh()

    def _reassign(self, task, rider) -> None:
        """改派：原因必填（REQ-012/016）。"""
        reason, ok = _ask_text(self, "改派",
                               f"改派给 {rider.name} 的原因（必填）：")
        if not ok or not reason:
            return
        self._act(lambda: self._app.dispatch.reassign(
            self._me, task.task_id, rider.account_id, reason))

    def _cancel_task(self, task) -> None:
        """异常处置——取消退款。"""
        reason, ok = _ask_text(self, "取消并退款", f"取消 {task.order_no} 的原因：")
        if not ok or not reason:
            return
        self._act(lambda: self._app.dispatch.cancel_by_admin(
            self._me, task.task_id, reason))

    def _force_refund(self, order) -> None:
        """强制退款：原因必填（REQ-026）。"""
        reason, ok = _ask_text(self, "强制退款",
                               f"对 {order.order_no} 强制退款的原因：")
        if not ok or not reason:
            return
        self._act(lambda: self._app.aftersale.force_refund(
            self._me, order.order_id, reason))

    def _ban(self, account) -> None:
        """封禁：原因必填。"""
        reason, ok = _ask_text(self, "封禁账号",
                               f"封禁 {account.name}（{account.phone}）的原因：")
        if not ok or not reason:
            return
        self._act(lambda: self._app.users.set_banned(
            self._me, account.account_id, True, reason))
