"""购物车、订单、支付、退款与配送任务的仓储实现。

时间约定：实体的时间字段一律由服务层按服务端时钟（REQ-027）赋值，
仓储只负责 ISO 字符串序列化；ISO 字符串按字典序即时间序，供调度扫描比较。
"""

from campus_eats.models.cart_order import Cart, CartItem, Order, OrderItem
from campus_eats.models.delivery import DeliveryTask
from campus_eats.models.enums import OrderStatus, PayStatus, RefundStatus, RefundType, TaskStatus
from campus_eats.models.payment_refund import Payment, Refund
from campus_eats.repositories.database import Database, parse_dt


class CartRepository:
    """购物车仓储：整块读写（条目数量很小，整存整取最简单且不易错）。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def get_or_create(self, customer_id: int) -> Cart:
        """取顾客购物车，无则建空车；连同条目一并加载。"""
        row = self._db.query_one("SELECT * FROM cart WHERE customer_id=?", (customer_id,))
        if not row:
            cart_id = self._db.execute(
                "INSERT INTO cart (customer_id, shop_id) VALUES (?,NULL)", (customer_id,))
            return Cart(cart_id=cart_id, customer_id=customer_id)
        cart = Cart(cart_id=row["cart_id"], customer_id=customer_id, shop_id=row["shop_id"])
        for r in self._db.query_all(
                "SELECT * FROM cart_item WHERE cart_id=? ORDER BY item_id", (row["cart_id"],)):
            cart.items.append(CartItem(item_id=r["item_id"], cart_id=r["cart_id"],
                                       dish_id=r["dish_id"], dish_name=r["dish_name"],
                                       icon=r["icon"], added_price_fen=r["added_price_fen"],
                                       qty=r["qty"]))
        return cart

    def save(self, cart: Cart) -> None:
        """整块保存购物车：更新店铺归属，重写全部条目。"""
        assert cart.cart_id is not None
        self._db.execute("UPDATE cart SET shop_id=? WHERE cart_id=?",
                         (cart.shop_id, cart.cart_id))
        self._db.execute("DELETE FROM cart_item WHERE cart_id=?", (cart.cart_id,))
        for item in cart.items:
            item.cart_id = cart.cart_id
            item.item_id = self._db.execute(
                "INSERT INTO cart_item (cart_id, dish_id, dish_name, icon, added_price_fen,"
                " qty) VALUES (?,?,?,?,?,?)",
                (cart.cart_id, item.dish_id, item.dish_name, item.icon,
                 item.added_price_fen, item.qty))


class OrderRepository:
    """订单仓储：明细快照随订单一次写入，之后不可变（REQ-009）。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def _to_order(self, row) -> Order:
        """行转订单实体（含明细）。"""
        order = Order(order_id=row["order_id"], order_no=row["order_no"],
                      customer_id=row["customer_id"], shop_id=row["shop_id"],
                      status=OrderStatus(row["status"]),
                      goods_amount_fen=row["goods_amount_fen"],
                      delivery_fee_fen=row["delivery_fee_fen"],
                      pay_amount_fen=row["pay_amount_fen"],
                      refunded_fen=row["refunded_fen"],
                      submit_token=row["submit_token"],
                      building_code=row["building_code"],
                      address_text=row["address_text"], phone=row["phone"],
                      remark=row["remark"], cancel_reason=row["cancel_reason"],
                      created_at=parse_dt(row["created_at"]),
                      pay_deadline=parse_dt(row["pay_deadline"]),
                      accept_deadline=parse_dt(row["accept_deadline"]),
                      delivered_at=parse_dt(row["delivered_at"]),
                      completed_at=parse_dt(row["completed_at"]),
                      cancelled_at=parse_dt(row["cancelled_at"]))
        for r in self._db.query_all(
                "SELECT * FROM order_item WHERE order_id=? ORDER BY item_id",
                (row["order_id"],)):
            order.items.append(OrderItem(item_id=r["item_id"], order_id=r["order_id"],
                                         dish_id=r["dish_id"], dish_name=r["dish_name"],
                                         unit_price_fen=r["unit_price_fen"], qty=r["qty"]))
        return order

    def add(self, order: Order) -> int:
        """写入订单与明细快照，回填 order_id 与明细 item_id。"""
        assert order.created_at is not None, "created_at 必须由服务层按服务端时钟设置"
        order.order_id = self._db.execute(
            "INSERT INTO orders (order_no, customer_id, shop_id, status, goods_amount_fen,"
            " delivery_fee_fen, pay_amount_fen, refunded_fen, submit_token, building_code,"
            " address_text, phone, remark, cancel_reason, created_at, pay_deadline,"
            " accept_deadline, delivered_at, completed_at, cancelled_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (order.order_no, order.customer_id, order.shop_id, order.status.value,
             order.goods_amount_fen, order.delivery_fee_fen, order.pay_amount_fen,
             order.refunded_fen, order.submit_token, order.building_code,
             order.address_text, order.phone, order.remark, order.cancel_reason,
             order.created_at.isoformat(), _fmt(order.pay_deadline),
             _fmt(order.accept_deadline), _fmt(order.delivered_at), _fmt(order.completed_at),
             _fmt(order.cancelled_at)))
        for item in order.items:
            item.order_id = order.order_id
            item.item_id = self._db.execute(
                "INSERT INTO order_item (order_id, dish_id, dish_name, unit_price_fen, qty)"
                " VALUES (?,?,?,?,?)",
                (order.order_id, item.dish_id, item.dish_name, item.unit_price_fen, item.qty))
        return order.order_id

    def get(self, order_id: int) -> Order | None:
        """按主键查订单（含明细）。"""
        row = self._db.query_one("SELECT * FROM orders WHERE order_id=?", (order_id,))
        return self._to_order(row) if row else None

    def find_by_no(self, order_no: str) -> Order | None:
        """按订单号查（幂等命中用）。"""
        row = self._db.query_one("SELECT * FROM orders WHERE order_no=?", (order_no,))
        return self._to_order(row) if row else None

    def find_by_token(self, token: str) -> Order | None:
        """按提交令牌查（REQ-024 幂等）。"""
        row = self._db.query_one("SELECT * FROM orders WHERE submit_token=?", (token,))
        return self._to_order(row) if row else None

    def update(self, order: Order) -> None:
        """持久化订单可变字段：状态、期限、退款累计、取消原因。明细不更新。"""
        self._db.execute(
            "UPDATE orders SET status=?, refunded_fen=?, cancel_reason=?, pay_deadline=?,"
            " accept_deadline=?, delivered_at=?, completed_at=?, cancelled_at=?"
            " WHERE order_id=?",
            (order.status.value, order.refunded_fen, order.cancel_reason,
             _fmt(order.pay_deadline), _fmt(order.accept_deadline), _fmt(order.delivered_at),
             _fmt(order.completed_at), _fmt(order.cancelled_at), order.order_id))

    def list_by_customer(self, customer_id: int) -> list[Order]:
        """顾客的订单，新单在前。"""
        rows = self._db.query_all(
            "SELECT * FROM orders WHERE customer_id=? ORDER BY order_id DESC", (customer_id,))
        return [self._to_order(r) for r in rows]

    def list_by_shop(self, shop_id: int) -> list[Order]:
        """店铺的订单，新单在前（商家工作台）。"""
        rows = self._db.query_all(
            "SELECT * FROM orders WHERE shop_id=? ORDER BY order_id DESC", (shop_id,))
        return [self._to_order(r) for r in rows]

    def list_by_status(self, status: OrderStatus) -> list[Order]:
        """按状态列订单（管理端干预列表）。"""
        rows = self._db.query_all(
            "SELECT * FROM orders WHERE status=? ORDER BY order_id DESC", (status.value,))
        return [self._to_order(r) for r in rows]

    def list_unpaid_before(self, deadline_text: str) -> list[Order]:
        """待支付且已过支付期限的订单（REQ-010 超时扫描）。"""
        rows = self._db.query_all(
            "SELECT * FROM orders WHERE status=? AND pay_deadline IS NOT NULL"
            " AND pay_deadline<=?", (OrderStatus.PENDING_PAY.value, deadline_text))
        return [self._to_order(r) for r in rows]

    def list_unaccepted_before(self, deadline_text: str) -> list[Order]:
        """待接单且已过接单期限的订单（REQ-015 超时扫描）。"""
        rows = self._db.query_all(
            "SELECT * FROM orders WHERE status=? AND accept_deadline IS NOT NULL"
            " AND accept_deadline<=?", (OrderStatus.PENDING_ACCEPT.value, deadline_text))
        return [self._to_order(r) for r in rows]

    def list_delivered_before(self, deadline_text: str) -> list[Order]:
        """已送达且超过确认期限的订单（REQ-013 两小时自动完成扫描）。"""
        rows = self._db.query_all(
            "SELECT * FROM orders WHERE status=? AND delivered_at IS NOT NULL"
            " AND delivered_at<=?", (OrderStatus.DELIVERED.value, deadline_text))
        return [self._to_order(r) for r in rows]


def _fmt(value) -> str | None:
    """datetime 转 ISO 字符串，None 透传。"""
    return value.isoformat() if value else None


class PaymentRepository:
    """支付流水仓储：一单最多一条成功流水。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def add(self, payment: Payment) -> int:
        """写入支付流水，回填 payment_id。"""
        assert payment.paid_at is not None
        payment.payment_id = self._db.execute(
            "INSERT INTO payment (pay_no, order_id, order_no, amount_fen, status, paid_at)"
            " VALUES (?,?,?,?,?,?)",
            (payment.pay_no, payment.order_id, payment.order_no, payment.amount_fen,
             payment.status.value, payment.paid_at.isoformat()))
        return payment.payment_id

    def find_by_order(self, order_id: int) -> Payment | None:
        """查订单的首条成功流水（重复支付返回首次结果，REQ-010/024）。"""
        row = self._db.query_one(
            "SELECT * FROM payment WHERE order_id=? ORDER BY payment_id", (order_id,))
        if not row:
            return None
        return Payment(payment_id=row["payment_id"], pay_no=row["pay_no"],
                       order_id=row["order_id"], order_no=row["order_no"],
                       amount_fen=row["amount_fen"], status=PayStatus(row["status"]),
                       paid_at=parse_dt(row["paid_at"]))


class RefundRepository:
    """退款记录仓储：只新增与状态流转，不删除（REQ-017 精神）。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def _to_refund(self, row) -> Refund:
        """行转退款实体。"""
        return Refund(refund_id=row["refund_id"], refund_no=row["refund_no"],
                      order_id=row["order_id"], order_no=row["order_no"],
                      amount_fen=row["amount_fen"], type=RefundType(row["type"]),
                      status=RefundStatus(row["status"]), reason=row["reason"],
                      requested_by=row["requested_by"],
                      created_at=parse_dt(row["created_at"]),
                      settled_at=parse_dt(row["settled_at"]))

    def add(self, refund: Refund) -> int:
        """写入退款记录，回填 refund_id。"""
        assert refund.created_at is not None
        refund.refund_id = self._db.execute(
            "INSERT INTO refund (refund_no, order_id, order_no, amount_fen, type, status,"
            " reason, requested_by, created_at, settled_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (refund.refund_no, refund.order_id, refund.order_no, refund.amount_fen,
             refund.type.value, refund.status.value, refund.reason, refund.requested_by,
             refund.created_at.isoformat(), _fmt(refund.settled_at)))
        return refund.refund_id

    def update(self, refund: Refund) -> None:
        """持久化退款状态与落定时间。"""
        self._db.execute(
            "UPDATE refund SET status=?, settled_at=? WHERE refund_id=?",
            (refund.status.value, _fmt(refund.settled_at), refund.refund_id))

    def get(self, refund_id: int) -> Refund | None:
        """按主键查退款。"""
        row = self._db.query_one("SELECT * FROM refund WHERE refund_id=?", (refund_id,))
        return self._to_refund(row) if row else None

    def list_by_order(self, order_id: int) -> list[Refund]:
        """订单的全部退款记录（对账用，REQ-022）。"""
        rows = self._db.query_all(
            "SELECT * FROM refund WHERE order_id=? ORDER BY refund_id", (order_id,))
        return [self._to_refund(r) for r in rows]

    def list_pending_before(self, deadline_text: str) -> list[Refund]:
        """待处理且超过商家处理期限的退款申请（REQ-026 二十四小时自动同意）。"""
        rows = self._db.query_all(
            "SELECT * FROM refund WHERE status=? AND created_at<=?",
            (RefundStatus.PENDING.value, deadline_text))
        return [self._to_refund(r) for r in rows]


class TaskRepository:
    """配送任务仓储。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def _to_task(self, row) -> DeliveryTask:
        """行转配送任务实体。"""
        return DeliveryTask(task_id=row["task_id"], order_id=row["order_id"],
                            order_no=row["order_no"], rider_id=row["rider_id"],
                            rider_name=row["rider_name"],
                            status=TaskStatus(row["status"]), area_code=row["area_code"],
                            pickup_text=row["pickup_text"], dropoff_text=row["dropoff_text"],
                            fail_reason=row["fail_reason"],
                            assigned_at=parse_dt(row["assigned_at"]),
                            completed_at=parse_dt(row["completed_at"]))

    def add(self, task: DeliveryTask) -> int:
        """写入配送任务，回填 task_id。"""
        task.task_id = self._db.execute(
            "INSERT INTO delivery_task (order_id, order_no, rider_id, rider_name, status,"
            " area_code, pickup_text, dropoff_text, fail_reason, assigned_at, completed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (task.order_id, task.order_no, task.rider_id, task.rider_name,
             task.status.value, task.area_code, task.pickup_text, task.dropoff_text,
             task.fail_reason, _fmt(task.assigned_at), _fmt(task.completed_at)))
        return task.task_id

    def get(self, task_id: int) -> DeliveryTask | None:
        """按主键查任务。"""
        row = self._db.query_one("SELECT * FROM delivery_task WHERE task_id=?", (task_id,))
        return self._to_task(row) if row else None

    def get_by_order(self, order_id: int) -> DeliveryTask | None:
        """按订单查任务。"""
        row = self._db.query_one(
            "SELECT * FROM delivery_task WHERE order_id=? ORDER BY task_id", (order_id,))
        return self._to_task(row) if row else None

    def update(self, task: DeliveryTask) -> None:
        """持久化任务可变字段。"""
        self._db.execute(
            "UPDATE delivery_task SET rider_id=?, rider_name=?, status=?, fail_reason=?,"
            " assigned_at=?, completed_at=? WHERE task_id=?",
            (task.rider_id, task.rider_name, task.status.value, task.fail_reason,
             _fmt(task.assigned_at), _fmt(task.completed_at), task.task_id))

    def list_by_rider(self, rider_id: int) -> list[DeliveryTask]:
        """骑手名下未完任务，新任务在前。"""
        rows = self._db.query_all(
            "SELECT * FROM delivery_task WHERE rider_id=? AND status NOT IN (?, ?)"
            " ORDER BY task_id DESC",
            (rider_id, TaskStatus.FINISHED.value, TaskStatus.EXCEPTION.value))
        return [self._to_task(r) for r in rows]

    def list_by_status(self, status: TaskStatus) -> list[DeliveryTask]:
        """按状态列任务（待分配队列 / 异常队列）。"""
        rows = self._db.query_all(
            "SELECT * FROM delivery_task WHERE status=? ORDER BY task_id", (status.value,))
        return [self._to_task(r) for r in rows]
