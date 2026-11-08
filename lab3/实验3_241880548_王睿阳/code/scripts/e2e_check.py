# -*- coding: utf-8 -*-
"""端到端验收脚本（开发期手工冒烟，后续收编为 pytest 套件）。

覆盖：种子 → 登录 → 浏览/搜索 → 购物车跨店拦截 → 下单（幂等/快照/预占）
→ 余额不足 → 充值 → 支付（幂等）→ 接单 → 出餐 → 派单（片区校验/拒单/改派）
→ 送达 → 确认收货；30 分钟未支付、10 分钟未接单、24 小时退款超时三条定时
规则；部分退款；配送异常处置；跨日库存重置；REQ-023 并发 200 抢 10 份。
"""

import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from campus_eats.app import App
from campus_eats.models.account import Customer, hash_password
from campus_eats.models.enums import OrderStatus, TaskStatus
from campus_eats.services.clock import FakeClock

PASS = 0


def check(cond, msg):
    """断言并计数。"""
    global PASS
    assert cond, f"验收失败：{msg}"
    PASS += 1
    print(f"  ok {PASS:02d} {msg}")


def expect_error(fn, keyword, msg):
    """断言 fn 抛出的异常包含关键字。"""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 验收脚本需要捕获业务异常
        assert keyword in str(exc), f"验收失败：{msg}（实际异常：{exc}）"
        return
    raise AssertionError(f"验收失败：{msg}（未抛出异常）")


def main() -> None:
    """按场景顺序执行全部验收。"""
    app = App(":memory:", clock=FakeClock(datetime(2026, 11, 8, 11, 0, 0)))
    g = app.gateway

    admin = g.login("13600000001", "123456")
    cust = g.login("13800000001", "123456")
    merch = g.login("13900000001", "123456")
    rider_a = g.login("13700000001", "123456")
    check(cust.role.label == "顾客" and merch.role.label == "商家"
          and admin.role.label == "管理员" and rider_a.role.label == "骑手",
          "四类角色登录（REQ-001）")

    shops = app.shops.list_operating()
    check(len(shops) == 2, "顾客可见两家已过审店铺（REQ-003）")
    shop_a = next(s for s in shops if s.name == "张记小炒")
    dishes = app.catalog.list_shop_dishes(shop_a.shop_id)
    check(len(dishes) == 3 and not dishes[0].sold_out, "浏览菜品带当日库存（REQ-006）")

    found = app.catalog.search("拉面")
    check(len(found) == 1 and found[0][0].dish.name == "牛肉拉面", "关键字搜索（REQ-006）")
    check(len(app.catalog.search("不存在的菜")) == 0, "搜索无结果返回空态而非报错")

    # ---- 购物车 ----
    app.orders.add_to_cart(cust, shop_a.shop_id, dishes[0].dish.dish_id, 2)
    lamian_shop = found[0][1]
    expect_error(lambda: app.orders.add_to_cart(
        cust, lamian_shop.shop_id, found[0][0].dish.dish_id),
        "同一店铺", "跨店加购被拦截（REQ-007）")
    app.orders.add_to_cart(cust, shop_a.shop_id, dishes[1].dish.dish_id)
    cart, lines = app.orders.view_cart(cust)
    check(all(ln.valid for ln in lines) and cart.total_fen() == 2 * 1500 + 2200,
          "同店加购合计正确（REQ-007）")

    # ---- 下单：地址校验 / 幂等 / 预占 ----
    token = app.orders.fresh_token()
    expect_error(lambda: app.orders.submit_order(cust, token, "X99", "13800000001"),
                 "配送范围", "范围外楼栋拦截（REQ-008）")
    order = app.orders.submit_order(cust, token, "A01", "13800000001", "少辣")
    check(order.status is OrderStatus.PENDING_PAY
          and order.pay_amount_fen == 5200 + 300,
          "下单成功：快照金额 = 商品 + 配送费（REQ-009/022）")
    again = app.orders.submit_order(cust, token, "A01", "13800000001")
    check(again.order_id == order.order_id, "同一令牌重复提交返回首单（REQ-024）")
    stock = app.repos.stocks.get_or_create(dishes[0].dish.dish_id,
                                           app.clock.now().date(), 40)
    check(stock.reserved_qty == 2 and stock.available() == 38, "库存预占 2 份（REQ-005）")

    # ---- 余额不足 → 充值 → 支付幂等 ----
    poor = Customer(phone="13899999999", name="穷顾客",
                    password_hash=hash_password("13899999999", "123456"),
                    balance_fen=1, created_at=app.clock.now())
    app.repos.accounts.add(poor)
    poor = app.repos.accounts.find_by_phone("13899999999")
    app.orders.force_add_to_cart(poor, shop_a.shop_id, dishes[2].dish.dish_id)
    poor_order = app.orders.submit_order(poor, app.orders.fresh_token(), "A02",
                                         "13899999999")
    expect_error(lambda: app.payments.pay(poor, poor_order.order_id),
                 "余额不足", "余额不足拦截（REQ-010）")
    app.users.recharge(admin, poor.account_id, 20_00)
    app.payments.pay(poor, poor_order.order_id)
    poor_order = app.repos.orders.get(poor_order.order_id)
    check(poor_order.status is OrderStatus.PENDING_ACCEPT, "充值后支付成功")

    bal_before = app.repos.accounts.get(cust.account_id).balance_fen
    app.users.recharge(admin, cust.account_id, 100_00)
    payment = app.payments.pay(cust, order.order_id)
    payment2 = app.payments.pay(cust, order.order_id)
    bal_after = app.repos.accounts.get(cust.account_id).balance_fen
    check(payment.payment_id == payment2.payment_id
          and bal_after == bal_before + 100_00 - order.pay_amount_fen,
          "重复支付只扣一次，返回首次结果（REQ-010/024）")
    stock = app.repos.stocks.get_or_create(dishes[0].dish.dish_id,
                                           app.clock.now().date(), 40)
    check(stock.reserved_qty == 0 and stock.sold_qty == 2, "支付后预占转已售（REQ-005）")

    # ---- 履约主链路：接单 → 出餐 → 派单 → 送达 → 收货 ----
    app.orders.accept(merch, order.order_id)
    check(app.orders.accept(merch, order.order_id).status is OrderStatus.COOKING,
          "重复接单幂等（REQ-011）")
    app.orders.ready(merch, order.order_id)
    task = app.repos.tasks.get_by_order(order.order_id)
    check(task is not None and task.status is TaskStatus.WAIT_ASSIGN,
          "出餐生成配送任务（ORD -> DISP）")

    rider_b = app.repos.accounts.find_by_phone("13700000002")
    app.dispatch.set_rider_online(rider_a, True)
    app.dispatch.set_rider_online(rider_b, True)
    expect_error(lambda: app.dispatch.assign(admin, task.task_id, rider_b.account_id),
                 "片区", "跨片区派单被拦截（REQ-012）")
    app.dispatch.assign(admin, task.task_id, rider_a.account_id)
    app.dispatch.reject_task(rider_a, task.task_id)
    check(app.repos.tasks.get(task.task_id).status is TaskStatus.WAIT_ASSIGN,
          "骑手拒单回待分配（REQ-012）")
    app.dispatch.assign(admin, task.task_id, rider_a.account_id)
    app.dispatch.accept_task(rider_a, task.task_id)
    check(app.repos.orders.get(order.order_id).status is OrderStatus.DELIVERING,
          "接受任务后订单配送中")
    app.dispatch.finish_task(rider_a, task.task_id)
    check(app.repos.orders.get(order.order_id).status is OrderStatus.DELIVERED,
          "骑手确认送达（REQ-013）")
    app.orders.confirm_receipt(cust, order.order_id)
    check(app.repos.orders.get(order.order_id).status is OrderStatus.COMPLETED,
          "顾客确认收货完成（REQ-013）")

    # ---- 30 分钟未支付超时 ----
    app.orders.force_add_to_cart(cust, shop_a.shop_id, dishes[0].dish.dish_id)
    o2 = app.orders.submit_order(cust, app.orders.fresh_token(), "A01", "13800000001")
    app.clock.advance(minutes=31)
    stats = app.scheduler.run_due()
    o2 = app.repos.orders.get(o2.order_id)
    check(o2.status is OrderStatus.CANCELLED and stats["unpaid_cancelled"] == 1,
          "30 分钟未支付自动取消（REQ-010）")
    stock = app.repos.stocks.get_or_create(dishes[0].dish.dish_id,
                                           app.clock.now().date(), 40)
    check(stock.reserved_qty == 0, "超时取消释放预占库存（REQ-005）")

    # ---- 10 分钟未接单超时 ----
    app.orders.force_add_to_cart(cust, shop_a.shop_id, dishes[0].dish.dish_id)
    o3 = app.orders.submit_order(cust, app.orders.fresh_token(), "A01", "13800000001")
    app.payments.pay(cust, o3.order_id)
    bal_before = app.repos.accounts.get(cust.account_id).balance_fen
    app.clock.advance(minutes=11)
    app.scheduler.run_due()
    o3 = app.repos.orders.get(o3.order_id)
    bal_after = app.repos.accounts.get(cust.account_id).balance_fen
    check(o3.status is OrderStatus.CANCELLED
          and bal_after == bal_before + o3.pay_amount_fen,
          "10 分钟未接单自动取消并全额退款（REQ-015）")

    # ---- 制作中：部分退款 + 取消申请 ----
    app.orders.force_add_to_cart(cust, shop_a.shop_id, dishes[0].dish.dish_id)
    o4 = app.orders.submit_order(cust, app.orders.fresh_token(), "A01", "13800000001")
    app.payments.pay(cust, o4.order_id)
    app.orders.accept(merch, o4.order_id)
    app.orders.refund_partial(o4.order_id, 700, "漏做半份", merch)
    o4 = app.repos.orders.get(o4.order_id)
    check(o4.refunded_fen == 700 and o4.status is OrderStatus.COOKING,
          "部分退款自环不改状态，配送费不退（REQ-014）")
    bal_before = app.repos.accounts.get(cust.account_id).balance_fen
    app.aftersale.apply_cancel(cust, o4.order_id, "不想要了")
    pending = [r for r in app.payments.list_refunds(o4.order_id)
               if r.status.value == "待处理"]
    check(len(pending) == 1 and pending[0].amount_fen == o4.pay_amount_fen - 700,
          "制作中取消申请进入待处理，金额为剩余额度")
    app.aftersale.handle_cancel_apply(merch, pending[0].refund_id, True)
    o4 = app.repos.orders.get(o4.order_id)
    bal_after = app.repos.accounts.get(cust.account_id).balance_fen
    check(o4.status is OrderStatus.CANCELLED
          and bal_after == bal_before + o4.pay_amount_fen - 700,
          "商家同意后取消并退剩余额度（REQ-014）")

    # ---- 24 小时未处理的取消申请自动同意 ----
    app.orders.force_add_to_cart(cust, shop_a.shop_id, dishes[1].dish.dish_id)
    o6 = app.orders.submit_order(cust, app.orders.fresh_token(), "A01", "13800000001")
    app.payments.pay(cust, o6.order_id)
    app.orders.accept(merch, o6.order_id)
    bal_before = app.repos.accounts.get(cust.account_id).balance_fen
    app.aftersale.apply_cancel(cust, o6.order_id, "等太久了")
    app.clock.advance(hours=25)
    app.scheduler.run_due()
    o6 = app.repos.orders.get(o6.order_id)
    bal_after = app.repos.accounts.get(cust.account_id).balance_fen
    check(o6.status is OrderStatus.CANCELLED
          and bal_after == bal_before + o6.pay_amount_fen,
          "商家 24 小时未处理，自动同意退款（REQ-026）")

    # ---- 配送异常处置 ----
    app.orders.force_add_to_cart(cust, shop_a.shop_id, dishes[0].dish.dish_id)
    o5 = app.orders.submit_order(cust, app.orders.fresh_token(), "A01", "13800000001")
    app.payments.pay(cust, o5.order_id)
    app.orders.accept(merch, o5.order_id)
    app.orders.ready(merch, o5.order_id)
    t5 = app.repos.tasks.get_by_order(o5.order_id)
    app.dispatch.assign(admin, t5.task_id, rider_a.account_id)
    app.dispatch.accept_task(rider_a, t5.task_id)
    app.dispatch.report_exception(rider_a, t5.task_id, "联系不上顾客", "电话无人接")
    t5 = app.repos.tasks.get(t5.task_id)
    check(app.repos.orders.get(o5.order_id).status is OrderStatus.DELIVERY_EXCEPTION
          and t5.status is TaskStatus.EXCEPTION, "上报配送异常挂起（REQ-016）")
    rider_c = app.repos.accounts.find_by_phone("13700000003")
    app.dispatch.set_rider_online(rider_c, True)
    app.dispatch.reassign(admin, t5.task_id, rider_c.account_id, "换人重送")
    check(app.repos.orders.get(o5.order_id).status is OrderStatus.DELIVERING,
          "管理员改派后恢复配送（REQ-016）")
    app.dispatch.accept_task(rider_c, t5.task_id)
    app.dispatch.finish_task(rider_c, t5.task_id)
    app.orders.confirm_receipt(cust, o5.order_id)
    check(app.repos.orders.get(o5.order_id).status is OrderStatus.COMPLETED,
          "异常单改派后走完履约")

    # ---- 跨日库存重置 ----
    app.clock.advance(hours=14)
    app.scheduler.run_due()
    stock_next_day = app.repos.stocks.get_or_create(dishes[0].dish.dish_id,
                                                    app.clock.now().date(), 40)
    check(stock_next_day.available() == 40, "次日零点库存按设置重置（REQ-005）")

    # ---- REQ-023 并发：库存 10，200 并发 ----
    print("  .. REQ-023 并发下单测试（200 线程抢 10 份）")
    big = app.catalog.add_dish(merch, "限量蛋糕", "9.99", 10, "🍰")
    users = [app.users.register_customer(f"135{i:08d}", "123456", f"并发{i}")
             for i in range(200)]
    barrier = threading.Barrier(200)
    success, lock = [], threading.Lock()

    def _rush(user):
        """单个并发用户：加购 + 提交。"""
        barrier.wait()
        try:
            app.orders.add_to_cart(user, big.shop_id, big.dish_id)
            placed = app.orders.submit_order(user, app.orders.fresh_token(),
                                             "A01", user.phone)
            with lock:
                success.append(placed.order_id)
        except Exception:  # noqa: BLE001 售罄即预期失败
            pass

    threads = [threading.Thread(target=_rush, args=(u,)) for u in users]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    distinct = len(set(success))
    stock = app.repos.stocks.get_or_create(big.dish_id, app.clock.now().date(), 10)
    check(distinct == 10 and stock.available() == 0 and stock.reserved_qty == 10,
          f"恰好 {distinct} 单成功、库存归零不为负（REQ-023）")

    # ---- 审计与通知 ----
    logs = app.audit.query_logs(target_type="ORDER", target_id=o5.order_id)
    check(len(logs) >= 4, "操作记录按订单可查（REQ-017）")
    notes = app.audit.list_notifications(cust.account_id)
    check(len(notes) >= 3, "站内通知已生成（REQ-015/016）")

    app.close()
    print(f"\n全部 {PASS} 项验收通过")


if __name__ == "__main__":
    main()
