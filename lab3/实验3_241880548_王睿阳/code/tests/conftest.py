"""pytest 公共夹具：内存库 + FakeClock 的装配好的 App。"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from campus_eats.app import App
from campus_eats.models.enums import OrderStatus
from campus_eats.services.clock import FakeClock

START = datetime(2026, 11, 8, 11, 0, 0)
DEMO_PWD = "123456"


@pytest.fixture()
def app():
    """每个测试一个全新内存库应用（种子已写入）。"""
    application = App(":memory:", clock=FakeClock(START))
    yield application
    application.close()


@pytest.fixture()
def admin(app):
    """管理员账号（种子第一个）。"""
    return app.repos.accounts.find_by_phone("13600000001")


@pytest.fixture()
def customer(app):
    """种子顾客王小阳。"""
    return app.repos.accounts.find_by_phone("13800000001")


@pytest.fixture()
def merchant(app):
    """张记小炒的商家账号。"""
    return app.repos.accounts.find_by_phone("13900000001")


@pytest.fixture()
def shop_a(app):
    """张记小炒店铺（A 片区，已开业）。"""
    return app.shops.get_by_name("张记小炒") if hasattr(app.shops, "get_by_name") \
        else next(s for s in app.shops.list_operating() if s.name == "张记小炒")


@pytest.fixture()
def dish_tomato(app, shop_a):
    """番茄炒蛋（¥15，日供 40）。"""
    return next(d for d in app.catalog.list_shop_dishes(shop_a.shop_id)
                if d.dish.name == "番茄炒蛋").dish


def place_order(app, customer, dish, qty=1, building="A01", phone="13800000001"):
    """加购并提交一笔待支付订单（测试便捷入口）。"""
    app.orders.add_to_cart(customer, dish.shop_id, dish.dish_id, qty)
    return app.orders.submit_order(customer, app.orders.fresh_token(), building, phone)


def pay_order(app, customer, order):
    """支付订单并断言进入待接单。"""
    app.payments.pay(customer, order.order_id)
    fresh = app.repos.orders.get(order.order_id)
    assert fresh.status is OrderStatus.PENDING_ACCEPT
    return fresh
