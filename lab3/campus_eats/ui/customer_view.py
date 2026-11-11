"""顾客端视图：店铺列表、店铺详情与购物车、确认订单、我的订单。

对应实验二 UI 稿 2～5 屏的信息结构：店铺卡片承载营业状态、菜品行显示
剩余份数与售罄标记、确认订单页前置地址范围与价格锁定、订单列表可取消/
支付/确认收货并查看退款记录。
界面动作统一捕获业务异常转为弹窗提示，属界面层约定。
"""
# pylint: disable=broad-exception-caught

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from campus_eats.models.enums import OrderStatus
from campus_eats.ui.theme import yuan


class CustomerView(QWidget):
    """顾客主视图：导航 + 三个页面。"""

    def __init__(self, app, account, on_logout) -> None:
        """绑定应用、当前顾客与登出回调。"""
        super().__init__()
        self._app = app
        self._me = account
        self._on_logout = on_logout
        self._current_shop = None
        self._token = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        topbar = self._topbar()
        root.addWidget(topbar)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.pages.addWidget(self._build_shop_list())
        self.pages.addWidget(self._build_shop_detail())
        self.pages.addWidget(self._build_orders())
        self.refresh()

    # ---------- 顶部 ----------

    def _topbar(self) -> QWidget:
        """顶部：标题 + 顾客信息 + 登出。"""
        bar_widget = QWidget()
        bar_widget.setObjectName("Root")
        row = QHBoxLayout(bar_widget)
        row.setContentsMargins(20, 12, 20, 12)
        title = QLabel("校园食光 · 顾客端")
        title.setObjectName("H1")
        row.addWidget(title)
        row.addStretch(1)
        self.balance_label = QLabel()
        row.addWidget(self.balance_label)
        recharge = QPushButton("充值 ¥20")
        recharge.clicked.connect(self._recharge)
        row.addWidget(recharge)
        orders_btn = QPushButton("我的订单")
        orders_btn.clicked.connect(lambda: self.pages.setCurrentIndex(2))
        row.addWidget(orders_btn)
        logout = QPushButton("退出登录")
        logout.clicked.connect(self._on_logout)
        row.addWidget(logout)
        return bar_widget

    # ---------- 页面一：店铺列表 ----------

    def _build_shop_list(self) -> QWidget:
        """店铺列表页：搜索框 + 排序 + 卡片栅格。"""
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 8, 20, 16)
        tools = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索菜品名，回车搜索（REQ-006）")
        self.search_box.returnPressed.connect(self.refresh)
        self.sort_box = QComboBox()
        self.sort_box.addItems(["综合排序", "销量优先"])
        self.sort_box.currentIndexChanged.connect(self.refresh)
        tools.addWidget(self.search_box, 1)
        tools.addWidget(self.sort_box)
        col.addLayout(tools)

        self.shop_cards = QWidget()
        self.shop_grid = QGridLayout(self.shop_cards)
        self.shop_grid.setSpacing(12)
        col.addWidget(self.shop_cards)
        col.addStretch(1)
        return page

    # ---------- 页面二：店铺详情 ----------

    def _build_shop_detail(self) -> QWidget:
        """店铺详情：菜品列表 + 底部购物车条。"""
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 8, 20, 12)
        self.shop_head = QLabel()
        self.shop_head.setObjectName("H1")
        col.addWidget(self.shop_head)
        self.dish_list = QVBoxLayout()
        col.addLayout(self.dish_list)
        col.addStretch(1)

        cart_bar_widget = QWidget()
        cart_bar_widget.setObjectName("Card")
        row = QHBoxLayout(cart_bar_widget)
        row.setContentsMargins(16, 10, 16, 10)
        self.cart_label = QLabel()
        row.addWidget(self.cart_label, 1)
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_cart)
        row.addWidget(clear_btn)
        checkout = QPushButton("去结算")
        checkout.setObjectName("Primary")
        checkout.clicked.connect(self._open_checkout)
        row.addWidget(checkout)
        col.addWidget(cart_bar_widget)
        return page

    # ---------- 页面三：我的订单 ----------

    def _build_orders(self) -> QWidget:
        """订单列表：状态、金额与可用操作。"""
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 8, 20, 16)
        head = QHBoxLayout()
        title = QLabel("我的订单")
        title.setObjectName("H1")
        back = QPushButton("返回店铺列表")
        back.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(back)
        col.addLayout(head)
        self.order_cards = QVBoxLayout()
        col.addLayout(self.order_cards)
        col.addStretch(1)
        return page

    # ---------- 刷新 ----------

    def refresh(self) -> None:
        """按当前页刷新数据（QTimer 周期调用）。"""
        me = self._app.gateway.current()
        self.balance_label.setText(f"余额 {yuan(me.balance_fen)}")
        index = self.pages.currentIndex()
        if index == 0:
            self._refresh_shops()
        elif index == 1:
            self._refresh_shop_detail()
        else:
            self._refresh_orders()

    def _refresh_shops(self) -> None:
        """店铺列表 / 搜索结果。"""
        keyword = self.search_box.text().strip()
        while self.shop_grid.count():
            item = self.shop_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        if keyword:
            results = self._app.catalog.search(keyword)
            for i, (view, shop) in enumerate(results):
                self.shop_grid.addWidget(self._shop_card(
                    shop, f"{view.dish.name} · {yuan(view.dish.price_fen)}"
                          f" · {'售罄' if view.sold_out else f'余{view.available_qty}份'}",
                    keyword_hint=keyword), i // 2, i % 2)
            if not results:
                empty = QLabel("没有找到相关菜品")
                empty.setObjectName("Hint")
                self.shop_grid.addWidget(empty, 0, 0)
            return
        shops = self._app.shops.list_operating()
        for i, shop in enumerate(shops):
            self.shop_grid.addWidget(self._shop_card(shop), i // 2, i % 2)

    def _shop_card(self, shop, subtitle: str = "", keyword_hint: str = "") -> QWidget:
        """一张店铺卡片。"""
        card = QWidget()
        card.setObjectName("Card")
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        left = QVBoxLayout()
        name = QLabel(shop.name)
        name.setObjectName("H2")
        left.addWidget(name)
        left.addWidget(QLabel(subtitle or f"{shop.category} · {shop.address_text}"
                              f" · 片区 {shop.area_code}"))
        row.addLayout(left, 1)
        mid = QVBoxLayout()
        status = QLabel(shop.status.label)
        status.setObjectName("StatusOpen" if shop.status.label == "营业中"
                            else "StatusRest")
        mid.addWidget(status)
        badge = QLabel("搜索结果" if keyword_hint else "")
        badge.setObjectName("Badge")
        mid.addWidget(badge)
        row.addLayout(mid)
        enter = QPushButton("进店点餐" if shop.status.label == "营业中" else "仅可浏览")
        enter.setObjectName("Primary")
        enter.clicked.connect(lambda: self._enter_shop(shop.shop_id))
        row.addWidget(enter)
        return card

    def _enter_shop(self, shop_id: int) -> None:
        """进店：切到详情页。"""
        self._current_shop = shop_id
        self.pages.setCurrentIndex(1)
        self._refresh_shop_detail()

    def _refresh_shop_detail(self) -> None:
        """店铺菜品 + 购物车条。"""
        shop = self._app.shops.get_shop(self._current_shop)
        self.shop_head.setText(f"{shop.name} · {shop.status.label}")
        while self.dish_list.count():
            item = self.dish_list.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        for view in self._app.catalog.list_shop_dishes(self._current_shop):
            self.dish_list.addWidget(self._dish_row(view, shop))
        cart, lines = self._app.orders.view_cart(self._me)
        total = cart.total_fen()
        count = sum(line.item.qty for line in lines)
        self.cart_label.setText(f"购物车：{count} 件 · 合计 {yuan(total)}"
                                f"（配送费 {yuan(300)} 另计）")

    def _dish_row(self, view, shop) -> QWidget:
        """一行菜品：图标、名称、价格、份数、加购。"""
        row = QWidget()
        row.setObjectName("Card")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(14, 8, 14, 8)
        icon = QLabel(view.dish.icon)
        icon.setStyleSheet("font-size: 22px;")
        lay.addWidget(icon)
        info = QVBoxLayout()
        name = QLabel(f"{view.dish.name}（月售 {view.dish.sales_count}）")
        name.setObjectName("H2")
        info.addWidget(name)
        note = (f"{yuan(view.dish.price_fen)} · 今日剩余 {view.available_qty} 份"
                if not view.sold_out else f"{yuan(view.dish.price_fen)} · 今日已售罄")
        hint = QLabel(note)
        hint.setObjectName("Hint")
        info.addWidget(hint)
        lay.addLayout(info, 1)
        add = QPushButton("加入购物车")
        add.setObjectName("Primary")
        add.setEnabled(shop.status.label == "营业中" and not view.sold_out)
        add.clicked.connect(lambda: self._add(view.dish.dish_id))
        lay.addWidget(add)
        return row

    def _add(self, dish_id: int) -> None:
        """加购；跨店冲突时提供「清空并加入」。"""
        try:
            self._app.orders.add_to_cart(self._me, self._current_shop, dish_id)
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            if "同一店铺" in str(exc):
                answer = QMessageBox.question(
                    self, "跨店加购",
                    "购物车只能包含同一店铺的菜品（REQ-007）。\n清空购物车并加入本品？")
                if answer == QMessageBox.StandardButton.Yes:
                    self._app.orders.force_add_to_cart(self._me, self._current_shop,
                                                       dish_id)
            else:
                QMessageBox.warning(self, "加购失败", str(exc))
        self._refresh_shop_detail()

    def _clear_cart(self) -> None:
        """清空购物车。"""
        self._app.orders.clear_cart(self._me)
        self._refresh_shop_detail()

    # ---------- 确认订单 ----------

    def _open_checkout(self) -> None:
        """确认订单对话框：楼栋下拉（只可选）、电话、备注、提交并支付。"""
        cart, lines = self._app.orders.view_cart(self._me)
        if not cart.items:
            QMessageBox.information(self, "购物车为空", "先去加点好吃的吧")
            return
        invalid = [line for line in lines if not line.valid]
        if invalid:
            names = "、".join(line.item.dish_name for line in invalid)
            QMessageBox.warning(self, "菜品已失效",
                                f"以下菜品已失效，请移除后重试：{names}")
            return
        dlg = _CheckoutDialog(self._app, self._me, cart, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._app.orders.clear_cart(self._me)
            self.pages.setCurrentIndex(2)
            self._refresh_orders()

    # ---------- 我的订单 ----------

    def _refresh_orders(self) -> None:
        """订单列表与可用操作。"""
        while self.order_cards.count():
            item = self.order_cards.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        orders = self._app.orders.list_customer_orders(self._me.account_id)
        if not orders:
            empty = QLabel("还没有订单")
            empty.setObjectName("Hint")
            self.order_cards.addWidget(empty)
        for order in orders:
            self.order_cards.addWidget(self._order_card(order))

    def _order_card(self, order) -> QWidget:
        """一张订单卡片：明细、状态、金额、操作按钮。"""
        card = QWidget()
        card.setObjectName("Card")
        col = QVBoxLayout(card)
        col.setContentsMargins(16, 10, 16, 10)
        head = QHBoxLayout()
        title = QLabel(f"订单 {order.order_no}")
        title.setObjectName("H2")
        status = QLabel(order.status.label)
        status.setObjectName("Badge")
        amount = QLabel(yuan(order.pay_amount_fen))
        amount.setObjectName("Money")
        head.addWidget(title)
        head.addWidget(status)
        head.addStretch(1)
        head.addWidget(amount)
        col.addLayout(head)
        items = "；".join(f"{it.dish_name}×{it.qty}"
                          for it in order.items)
        detail = QLabel(f"{items} · {order.address_text}")
        detail.setObjectName("Hint")
        col.addWidget(detail)
        if order.status is OrderStatus.PENDING_PAY and order.pay_deadline:
            deadline = order.pay_deadline.strftime("%H:%M")
            col.addWidget(QLabel(f"需在 {deadline} 前完成支付，超时自动取消"))
        if order.cancel_reason:
            col.addWidget(QLabel(f"取消原因：{order.cancel_reason}"))
        actions = QHBoxLayout()
        if order.status is OrderStatus.PENDING_PAY:
            pay = QPushButton("余额支付")
            pay.setObjectName("Primary")
            pay.clicked.connect(lambda: self._pay(order))
            actions.addWidget(pay)
            cancel = QPushButton("取消订单")
            cancel.setObjectName("Danger")
            cancel.clicked.connect(lambda: self._cancel(order))
            actions.addWidget(cancel)
        elif order.status is OrderStatus.PENDING_ACCEPT:
            cancel = QPushButton("取消订单（全额退款）")
            cancel.setObjectName("Danger")
            cancel.clicked.connect(lambda: self._cancel(order))
            actions.addWidget(cancel)
        elif order.status is OrderStatus.COOKING:
            apply_btn = QPushButton("申请取消退款")
            apply_btn.setObjectName("Danger")
            apply_btn.clicked.connect(lambda: self._apply_cancel(order))
            actions.addWidget(apply_btn)
        elif order.status is OrderStatus.DELIVERED:
            confirm = QPushButton("确认收货")
            confirm.setObjectName("Primary")
            confirm.clicked.connect(lambda: self._confirm(order))
            actions.addWidget(confirm)
        refunds = self._app.payments.list_refunds(order.order_id)
        if refunds:
            text = "；".join(f"{r.type.label} {yuan(r.amount_fen)}（{r.status.label}）"
                             for r in refunds)
            col.addWidget(QLabel(f"退款记录：{text}"))
        actions.addStretch(1)
        col.addLayout(actions)
        return card

    # ---------- 动作 ----------

    def _pay(self, order) -> None:
        """余额支付。"""
        try:
            self._app.payments.pay(self._me, order.order_id)
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "支付失败", str(exc))
        self.refresh()

    def _cancel(self, order) -> None:
        """自行取消（待支付 / 待接单）。"""
        try:
            self._app.aftersale.cancel_by_customer(self._me, order.order_id)
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "取消失败", str(exc))
        self.refresh()

    def _apply_cancel(self, order) -> None:
        """制作中申请取消退款。"""
        reason, ok = _ask_text(self, "申请取消退款", "请填写原因（商家 24 小时未处理将自动同意）")
        if not ok:
            return
        try:
            self._app.aftersale.apply_cancel(self._me, order.order_id, reason)
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "申请失败", str(exc))
        self.refresh()

    def _confirm(self, order) -> None:
        """确认收货。"""
        try:
            self._app.orders.confirm_receipt(self._me, order.order_id)
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "操作失败", str(exc))
        self.refresh()

    def _recharge(self) -> None:
        """充值 ¥20（演示用，不接真实支付）。"""
        admin = self._app.repos.accounts.find_by_phone("13600000001")
        self._app.users.recharge(admin, self._me.account_id, 2000)
        self.refresh()


class _CheckoutDialog(QDialog):
    """确认订单：楼栋下拉、电话、备注；提交即锁价并预占库存（REQ-008/009）。"""

    def __init__(self, app, me, cart, parent) -> None:
        """绑定应用与顾客，展示金额明细。"""
        super().__init__(parent)
        self._app = app
        self._me = me
        self._cart = cart
        self.setWindowTitle("确认订单")
        self.setFixedWidth(440)
        col = QVBoxLayout(self)

        items = QLabel("\n".join(f"{it.dish_name} × {it.qty} = {yuan(it.added_price_fen * it.qty)}"
                                 for it in cart.items))
        items.setObjectName("H2")
        col.addWidget(items)
        preview = app.orders.preview_submit(me, "")
        col.addWidget(QLabel(f"商品合计 {yuan(preview['goods_fen'])} + 配送费 "
                             f"{yuan(preview['delivery_fen'])}（提交后价格锁定，REQ-009）"))

        form = QFormLayout()
        self.building = QComboBox()
        building_model = QStandardItemModel(self.building)
        for b in app.repos.buildings.list_all():
            item = QStandardItem(f"{b.name}（{b.code}）")
            item.setData(b.code, Qt.ItemDataRole.UserRole)
            if not b.in_range:
                item.setEnabled(False)          # 范围外楼栋禁选（REQ-008）
            building_model.appendRow(item)
        self.building.setModel(building_model)
        self.phone = QLineEdit(me.phone)
        self.remark = QTextEdit()
        self.remark.setFixedHeight(56)
        self.remark.setPlaceholderText("备注（选填，超 100 字截断）")
        form.addRow("收货楼栋", self.building)
        form.addRow("联系电话", self.phone)
        form.addRow("备注", self.remark)
        col.addLayout(form)

        self.total_label = QLabel()
        self.total_label.setObjectName("Money")
        self.building.currentIndexChanged.connect(self._update_total)
        col.addWidget(self.total_label)

        row = QHBoxLayout()
        submit = QPushButton("提交订单（预占库存并锁价）")
        submit.setObjectName("Primary")
        submit.clicked.connect(self._submit)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        row.addWidget(submit, 1)
        row.addWidget(cancel)
        col.addLayout(row)
        self._update_total()

    def _update_total(self) -> None:
        """按所选楼栋刷新金额与可达性。"""
        preview = self._app.orders.preview_submit(self._me,
                                                  self.building.currentData())
        if preview["in_range"]:
            self.total_label.setText(f"应付 {yuan(preview['total_fen'])}"
                                     f" · 余额 {yuan(self._me.balance_fen)}")
        else:
            self.total_label.setText("所选楼栋不在配送范围内")

    def _submit(self) -> None:
        """提交订单（令牌幂等，REQ-024），成功后立即引导支付。"""
        token = self._app.orders.fresh_token()
        try:
            order = self._app.orders.submit_order(
                self._me, token, self.building.currentData(),
                self.phone.text().strip(), self.remark.toPlainText().strip())
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "提交失败", str(exc))
            return
        if order.status is OrderStatus.PENDING_PAY:
            answer = QMessageBox.question(
                self, "提交成功", f"订单 {order.order_no} 已预占库存并锁价，"
                f"应付 {yuan(order.pay_amount_fen)}。\n立即余额支付？")
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    self._app.payments.pay(self._me, order.order_id)
                except Exception as exc:  # noqa: BLE001 界面层统一转提示
                    QMessageBox.warning(
                        self, "支付失败",
                        f"{exc}\n可在「我的订单」中稍后支付（30 分钟内有效）")
        self.accept()


def _ask_text(parent, title: str, label: str) -> tuple[str, bool]:
    """弹一个多行文本输入框，返回（文本, 是否确认）。"""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    col = QVBoxLayout(dlg)
    col.addWidget(QLabel(label))
    edit = QTextEdit()
    col.addWidget(edit)
    row = QHBoxLayout()
    ok = QPushButton("确定")
    ok.setObjectName("Primary")
    ok.clicked.connect(dlg.accept)
    cancel = QPushButton("取消")
    cancel.clicked.connect(dlg.reject)
    row.addWidget(ok)
    row.addWidget(cancel)
    col.addLayout(row)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return edit.toPlainText().strip(), True
    return "", False
