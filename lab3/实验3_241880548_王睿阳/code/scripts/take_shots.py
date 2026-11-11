# -*- coding: utf-8 -*-
"""生成实验报告"编译与运行结果"一节的五张界面截图。

离屏运行真实应用（QT_QPA_PLATFORM=offscreen），按报告需要的场景摆放数据：
待接单与制作中的商家工作台、有任务的派单队列等，截图输出到 build/img/。
运行：python scripts/take_shots.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from campus_eats.app import App  # noqa: E402
from campus_eats.ui import theme  # noqa: E402
from campus_eats.ui.admin_view import AdminView  # noqa: E402
from campus_eats.ui.customer_view import CustomerView, _CheckoutDialog  # noqa: E402
from campus_eats.ui.login import LoginWindow  # noqa: E402
from campus_eats.ui.merchant_view import MerchantView  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "img")


def shot(widget, name, qt=None):
    """抓取控件画面并落盘；先强制处理延迟删除，避免旧控件残影。"""
    if qt is not None:
        qt.processEvents()
        qt.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qt.processEvents()
    path = os.path.join(OUT, name)
    widget.grab().save(path)
    print("saved", name)


def main():
    """按报告场景依序摆数据并截图。"""
    os.makedirs(OUT, exist_ok=True)
    qt = QApplication.instance() or QApplication([])
    qt.setStyleSheet(theme.QSS)
    app = App(":memory:")

    # 1. 登录页
    login = LoginWindow(app, on_login=lambda account: None)
    login.resize(420, 640)
    qt.processEvents()
    shot(login, "shot_login.png", qt)

    # 顾客端店铺详情：加购后进店，购物车条有合计
    customer = app.gateway.login("13800000001", "123456")
    cv = CustomerView(app, customer, on_logout=lambda: None)
    cv.resize(1120, 730)
    shop = next(s for s in app.shops.list_operating() if s.name == "张记小炒")
    dishes = app.catalog.list_shop_dishes(shop.shop_id)
    app.orders.add_to_cart(customer, shop.shop_id, dishes[0].dish.dish_id, 1)
    cv._enter_shop(shop.shop_id)
    qt.processEvents()
    shot(cv, "shot_shop_detail.png", qt)

    # 3. 确认订单对话框（含楼栋下拉与金额汇总）
    cart, _lines = app.orders.view_cart(customer)
    dlg = _CheckoutDialog(app, customer, cart, cv)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    dlg.resize(500, 620)
    dlg.show()
    qt.processEvents()
    shot(dlg, "shot_checkout.png", qt)
    dlg.reject()

    # 订单一：已支付待接单；订单二：已接单制作中——商家工作台两列都有卡片
    order1 = app.orders.submit_order(customer, app.orders.fresh_token(),
                                     "A01", customer.phone, "少辣")
    app.payments.pay(customer, order1.order_id)
    app.orders.add_to_cart(customer, shop.shop_id, dishes[1].dish.dish_id, 1)
    order2 = app.orders.submit_order(customer, app.orders.fresh_token(),
                                     "A02", customer.phone)
    app.payments.pay(customer, order2.order_id)
    merchant = app.gateway.login("13900000001", "123456")
    app.orders.accept(merchant, order2.order_id)
    mv = MerchantView(app, merchant, on_logout=lambda: None)
    mv.resize(1180, 740)
    mv.refresh()
    qt.processEvents()
    shot(mv, "shot_merchant.png", qt)

    # 订单二出餐生成任务，骑手上线，管理端出现待派送卡与操作记录
    app.orders.ready(merchant, order2.order_id)
    rider = app.repos.accounts.find_by_phone("13700000001")
    app.dispatch.set_rider_online(rider, True)
    admin = app.gateway.login("13600000001", "123456")
    av = AdminView(app, admin, on_logout=lambda: None)
    av.resize(1180, 740)
    av.pages.setCurrentIndex(1)
    av.refresh()
    qt.processEvents()
    shot(av, "shot_admin.png", qt)

    app.close()
    print("done ->", OUT)


if __name__ == "__main__":
    main()
