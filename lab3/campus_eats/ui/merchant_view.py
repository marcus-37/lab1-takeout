"""商家端视图：订单工作台 + 菜品与库存（对应实验二 UI 稿 6～7 屏）。

工作台按「待接单 / 制作中 / 履约中」分区，含退款申请处理与部分退款；
菜品页把「今日份数 / 已预占 / 已售」拆成三列（实验二审查结论），
并提供改价、上下架、每日份数与营业状态切换、当日统计（REQ-025）。
界面动作统一捕获业务异常转为弹窗提示，属界面层约定。
"""
# pylint: disable=broad-exception-caught

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from campus_eats.models.enums import OrderStatus
from campus_eats.models.money import yuan_to_fen
from campus_eats.ui.customer_view import _ask_text
from campus_eats.ui.theme import yuan


class MerchantView(QWidget):
    """商家主视图。"""

    def __init__(self, app, account, on_logout) -> None:
        """绑定应用、商家账号与登出回调。"""
        super().__init__()
        self._app = app
        self._me = account
        self._on_logout = on_logout

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._topbar())
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.pages.addWidget(self._build_orders_page())
        self.pages.addWidget(self._build_dishes_page())
        self.refresh()

    def _topbar(self) -> QWidget:
        """顶部：标题 + 页签 + 营业状态 + 登出。"""
        bar_widget = QWidget()
        bar_widget.setObjectName("Root")
        row = QHBoxLayout(bar_widget)
        row.setContentsMargins(20, 12, 20, 12)
        title = QLabel("校园食光 · 商家端")
        title.setObjectName("H1")
        row.addWidget(title)
        row.addSpacing(16)
        orders_tab = QPushButton("订单工作台")
        orders_tab.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        dishes_tab = QPushButton("菜品与库存")
        dishes_tab.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        row.addWidget(orders_tab)
        row.addWidget(dishes_tab)
        row.addStretch(1)
        self.status_label = QLabel()
        row.addWidget(self.status_label)
        self.toggle_btn = QPushButton()
        self.toggle_btn.clicked.connect(self._toggle_open)
        row.addWidget(self.toggle_btn)
        logout = QPushButton("退出登录")
        logout.clicked.connect(self._on_logout)
        row.addWidget(logout)
        return bar_widget

    # ---------- 页面一：订单工作台 ----------

    def _build_orders_page(self) -> QWidget:
        """三区工作台 + 待处理退款申请。"""
        page = QWidget()
        cols = QHBoxLayout(page)
        cols.setContentsMargins(20, 8, 20, 16)
        cols.setSpacing(12)
        self.pending_col = _order_column("待接单（10 分钟未接自动取消）")
        self.cooking_col = _order_column("制作中")
        self.fulfilling_col = _order_column("待配送 / 配送中 / 已送达")
        cols.addWidget(self.pending_col["box"])
        cols.addWidget(self.cooking_col["box"])
        cols.addWidget(self.fulfilling_col["box"])

        refund_box, refund_layout = _section("退款申请（24 小时未处理自动同意）")
        self.refund_col = {"box": refund_box, "col": refund_layout}
        cols.addWidget(refund_box)
        return page

    def _build_dishes_page(self) -> QWidget:
        """菜品与库存页：统计条 + 表格 + 操作区。"""
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 8, 20, 16)
        stats = QHBoxLayout()
        self.stats_label = QLabel()
        self.stats_label.setObjectName("H2")
        stats.addWidget(self.stats_label)
        stats.addStretch(1)
        add_dish = QPushButton("新增菜品")
        add_dish.setObjectName("Primary")
        add_dish.clicked.connect(self._add_dish)
        stats.addWidget(add_dish)
        col.addLayout(stats)

        self.dish_table = QTableWidget(0, 7)
        self.dish_table.setHorizontalHeaderLabels(
            ["菜品", "价格", "状态", "每日份数", "已预占", "已售", "操作"])
        self.dish_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.dish_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        col.addWidget(self.dish_table, 1)
        hint = QLabel("说明：改价只影响之后的订单（历史快照不变，REQ-009）；"
                      "修改每日份数不影响当日已占用的库存；"
                      "预占 = 待支付订单占用，支付后转已售（REQ-005）。")
        hint.setObjectName("Hint")
        col.addWidget(hint)
        return page

    # ---------- 刷新 ----------

    def refresh(self) -> None:
        """刷新工作台、菜品表与统计（QTimer 周期调用）。"""
        try:
            shop = self._app.shops.get_own_shop(self._me)
        except Exception:  # noqa: BLE001 未开店商家
            self.status_label.setText("尚未提交入驻申请")
            return
        self.status_label.setText(f"{shop.name} · {shop.status.label}")
        self.toggle_btn.setText("转休息" if shop.status.label == "营业中" else "申请开业")
        self.toggle_btn.setEnabled(shop.status.label in ("营业中", "休息中"))
        self._refresh_orders()
        self._refresh_dishes()

    def _refresh_orders(self) -> None:
        """按状态分区渲染订单卡片与退款申请。"""
        columns = (self.pending_col, self.cooking_col, self.fulfilling_col,
                   self.refund_col)
        for column in columns:
            _clear_layout(column["col"])
        for order in self._app.orders.list_shop_orders(self._me):
            if order.status is OrderStatus.PENDING_ACCEPT:
                self.pending_col["col"].addWidget(self._pending_card(order))
            elif order.status is OrderStatus.COOKING:
                self.cooking_col["col"].addWidget(self._cooking_card(order))
            elif order.status in (OrderStatus.PENDING_DELIVERY, OrderStatus.DELIVERING,
                                  OrderStatus.DELIVERED, OrderStatus.DELIVERY_EXCEPTION):
                self.fulfilling_col["col"].addWidget(self._fulfill_card(order))
        for refund in self._app.payments.list_pending_refunds(self._me):
            self.refund_col["col"].addWidget(self._refund_card(refund))
        for column in columns:
            column["col"].addStretch(1)

    def _pending_card(self, order) -> QWidget:
        """待接单卡片：接单 / 拒单。"""
        card = _order_card(order, f"{yuan(order.pay_amount_fen)} · "
                                  f"{order.address_text}")
        row = QHBoxLayout()
        accept = QPushButton("接单")
        accept.setObjectName("Primary")
        accept.clicked.connect(lambda: self._act(
            lambda: self._app.orders.accept(self._me, order.order_id)))
        reject = QPushButton("拒单")
        reject.setObjectName("Danger")
        reject.clicked.connect(lambda: self._reject(order))
        row.addWidget(accept)
        row.addWidget(reject)
        card.layout().addLayout(row)
        return card

    def _cooking_card(self, order) -> QWidget:
        """制作中卡片：出餐 / 部分退款 / 同意取消。"""
        card = _order_card(order, f"{yuan(order.pay_amount_fen)} · "
                                  f"已退 {yuan(order.refunded_fen)}")
        row = QHBoxLayout()
        ready = QPushButton("出餐")
        ready.setObjectName("Primary")
        ready.clicked.connect(lambda: self._act(
            lambda: self._app.orders.ready(self._me, order.order_id)))
        partial = QPushButton("部分退款")
        partial.clicked.connect(self._partial(order))
        row.addWidget(ready)
        row.addWidget(partial)
        card.layout().addLayout(row)
        return card

    def _fulfill_card(self, order) -> QWidget:
        """履约中卡片：展示任务归属与状态。"""
        task = self._app.repos.tasks.get_by_order(order.order_id)
        rider = task.rider_name if task and task.rider_name else "待指派"
        return _order_card(order, f"骑手：{rider}")

    def _refund_card(self, refund) -> QWidget:
        """待处理取消申请卡片。"""
        card = QWidget()
        card.setObjectName("Card")
        col = QVBoxLayout(card)
        title = QLabel(f"{refund.order_no}")
        title.setObjectName("H2")
        col.addWidget(title)
        col.addWidget(QLabel(f"{refund.reason}\n申请退款 {yuan(refund.amount_fen)}"))
        row = QHBoxLayout()
        agree = QPushButton("同意")
        agree.setObjectName("Primary")
        agree.clicked.connect(lambda: self._act(
            lambda: self._app.aftersale.handle_cancel_apply(
                self._me, refund.refund_id, True)))
        deny = QPushButton("拒绝")
        deny.setObjectName("Danger")
        deny.clicked.connect(lambda: self._deny_refund(refund))
        row.addWidget(agree)
        row.addWidget(deny)
        col.addLayout(row)
        return card

    def _refresh_dishes(self) -> None:
        """菜品与库存三列表格（份数 / 预占 / 已售）。"""
        rows = self._app.catalog.list_own_stocks(self._me)
        self.dish_table.setRowCount(len(rows))
        stats = self._app.payments.merchant_daily_stats(self._me)
        self.stats_label.setText(
            f"今日：{stats['order_count']} 单 · 营业额 {yuan(stats['revenue_fen'])}"
            "（实收口径，退款扣减，REQ-025）")
        for i, (dish, stock) in enumerate(rows):
            self.dish_table.setItem(i, 0, QTableWidgetItem(
                f"{dish.icon} {dish.name}"))
            self.dish_table.setItem(i, 1, QTableWidgetItem(yuan(dish.price_fen)))
            self.dish_table.setItem(i, 2, QTableWidgetItem(dish.status.label))
            self.dish_table.setItem(i, 3, QTableWidgetItem(str(stock.total_qty)))
            self.dish_table.setItem(i, 4, QTableWidgetItem(str(stock.reserved_qty)))
            self.dish_table.setItem(i, 5, QTableWidgetItem(str(stock.sold_qty)))
            ops = QWidget()
            row = QHBoxLayout(ops)
            row.setContentsMargins(2, 2, 2, 2)
            price_btn = QPushButton("改价")
            price_btn.clicked.connect(self._change_price(dish))
            toggle = QPushButton("下架" if dish.status.label == "上架" else "上架")
            toggle.clicked.connect(lambda _=False, d=dish: self._toggle_dish(d))
            qty_btn = QPushButton("份数")
            qty_btn.clicked.connect(self._change_qty(dish))
            for btn in (price_btn, toggle, qty_btn):
                row.addWidget(btn)
            self.dish_table.setCellWidget(i, 6, ops)

    # ---------- 动作 ----------

    def _act(self, fn) -> None:
        """执行动作并把异常转为提示。"""
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "操作失败", str(exc))
        self.refresh()

    def _reject(self, order) -> None:
        """拒单：必须填原因。"""
        reason, ok = _ask_text(self, "拒单", "拒单必须填写原因（REQ-011）：")
        if not ok or not reason:
            return
        self._act(lambda: self._app.orders.reject(self._me, order.order_id, reason))

    def _partial(self, order):
        """部分退款：金额 + 原因。"""
        def _do():
            text, ok = _ask_text(self, "部分退款",
                                 "输入退款金额（元，配送费不退，REQ-014）：")
            if not ok or not text:
                return

            amount = yuan_to_fen(text)
            reason, ok2 = _ask_text(self, "部分退款原因", "原因：")
            if not ok2:
                return
            self._app.orders.refund_partial(order.order_id, amount, reason, self._me)
        return _do

    def _deny_refund(self, refund) -> None:
        """拒绝取消申请。"""
        reason, ok = _ask_text(self, "拒绝退款", "拒绝必须说明原因：")
        if not ok or not reason:
            return
        self._act(lambda: self._app.aftersale.handle_cancel_apply(
            self._me, refund.refund_id, False, reason))

    def _toggle_open(self) -> None:
        """开业 / 转休息。"""
        try:
            shop = self._app.shops.get_own_shop(self._me)
            if shop.status.label == "营业中":
                self._app.shops.rest(self._me)
            else:
                self._app.shops.open(self._me)
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "操作失败", str(exc))
        self.refresh()

    def _add_dish(self) -> None:
        """新增菜品对话框。"""
        dlg = QDialog(self)
        dlg.setWindowTitle("新增菜品")
        form = QFormLayout(dlg)
        name = QLineEdit()
        price = QLineEdit()
        price.setPlaceholderText("如 12.50")
        qty = QLineEdit("30")
        icon = QLineEdit("🍽")
        form.addRow("名称", name)
        form.addRow("价格（元）", price)
        form.addRow("每日份数", qty)
        form.addRow("图标", icon)
        submit = QPushButton("保存")
        submit.setObjectName("Primary")
        submit.clicked.connect(dlg.accept)
        form.addRow(submit)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._app.catalog.add_dish(self._me, name.text().strip(),
                                       price.text().strip(), int(qty.text()),
                                       icon.text() or "🍽")
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "保存失败", str(exc))
        self.refresh()

    def _change_price(self, dish):
        """改价对话框（REQ-009 留痕）。"""
        def _do():
            text, ok = _ask_text(self, "改价",
                                 f"{dish.name} 现价 {yuan(dish.price_fen)}，"
                                 "输入新价格（元）：")
            if not ok or not text:
                return
            self._act(lambda: self._app.catalog.change_price(
                self._me, dish.dish_id, text))
        return _do

    def _change_qty(self, dish):
        """修改每日份数。"""
        def _do():
            text, ok = _ask_text(self, "每日份数",
                                 f"{dish.name} 当前每日 {dish.daily_qty} 份，"
                                 "输入新份数（次日生效，当日已占用不变）：")
            if not ok or not text:
                return
            self._act(lambda: self._app.catalog.set_daily_qty(
                self._me, dish.dish_id, int(text)))
        return _do

    def _toggle_dish(self, dish) -> None:
        """上架 / 下架。"""
        def _do():
            if dish.status.label == "上架":
                self._app.catalog.take_off(self._me, dish.dish_id)
            else:
                self._app.catalog.put_on(self._me, dish.dish_id)
        self._act(_do)


def _order_column(title: str) -> dict:
    """建一个订单分区列，返回（容器, 内容布局）。"""
    box, col = _section(title)
    return {"box": box, "col": col}


def _section(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    """带标题的分区容器。"""
    box = QGroupBox(title)
    col = QVBoxLayout(box)
    col.setSpacing(8)
    return box, col


def _order_card(order, subtitle: str) -> QWidget:
    """订单卡片骨架：标题行 + 副标题。"""
    card = QWidget()
    card.setObjectName("Card")
    col = QVBoxLayout(card)
    col.setContentsMargins(12, 8, 12, 8)
    head = QHBoxLayout()
    no = QLabel(order.order_no.split("-")[-1] + " " + order.status.label)
    no.setObjectName("H2")
    amount = QLabel(yuan(order.pay_amount_fen))
    amount.setObjectName("Money")
    head.addWidget(no)
    head.addStretch(1)
    head.addWidget(amount)
    col.addLayout(head)
    col.addWidget(QLabel(subtitle))
    items = "；".join(f"{it.dish_name}×{it.qty}" for it in order.items)
    items_label = QLabel(items)
    items_label.setObjectName("Hint")
    col.addWidget(items_label)
    return card


def _clear_layout(layout) -> None:
    """清空布局内的所有控件。"""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
