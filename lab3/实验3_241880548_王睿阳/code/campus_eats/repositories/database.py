"""SQLite 数据库连接与建表。

对应组件图基础设施层的数据库：原型以单文件 SQLite 代替 MySQL，经仓储层隔离，
业务代码不直接书写 SQL。单连接 + 进程内互斥锁保证跨线程（界面线程、调度线程、
并发测试）安全；每次写操作在锁内提交，保证单操作原子性（REQ-023）。
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
    account_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    phone         TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT '正常',
    balance_fen   INTEGER NOT NULL DEFAULT 0,
    license_no    TEXT,
    online        INTEGER NOT NULL DEFAULT 0,
    area_code     TEXT NOT NULL DEFAULT '',
    admin_level   INTEGER,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shop (
    shop_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id  INTEGER NOT NULL,
    name         TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT '',
    area_code    TEXT NOT NULL DEFAULT '',
    address_text TEXT NOT NULL DEFAULT '',
    license_no   TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT '待审核',
    review_reason TEXT NOT NULL DEFAULT '',
    open_time    TEXT NOT NULL DEFAULT '10:00',
    close_time   TEXT NOT NULL DEFAULT '22:00',
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dish (
    dish_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id     INTEGER NOT NULL,
    name        TEXT NOT NULL,
    price_fen   INTEGER NOT NULL,
    icon        TEXT NOT NULL DEFAULT '🍽',
    status      TEXT NOT NULL DEFAULT '上架',
    daily_qty   INTEGER NOT NULL DEFAULT 0,
    sales_count INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_stock (
    stock_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    dish_id       INTEGER NOT NULL,
    stock_date    TEXT NOT NULL,
    total_qty     INTEGER NOT NULL DEFAULT 0,
    reserved_qty  INTEGER NOT NULL DEFAULT 0,
    sold_qty      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (dish_id, stock_date)
);
CREATE TABLE IF NOT EXISTS cart (
    cart_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL UNIQUE,
    shop_id     INTEGER
);
CREATE TABLE IF NOT EXISTS cart_item (
    item_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id         INTEGER NOT NULL,
    dish_id         INTEGER NOT NULL,
    dish_name       TEXT NOT NULL,
    icon            TEXT NOT NULL DEFAULT '🍽',
    added_price_fen INTEGER NOT NULL,
    qty             INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    order_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no          TEXT NOT NULL UNIQUE,
    customer_id       INTEGER NOT NULL,
    shop_id           INTEGER NOT NULL,
    status            TEXT NOT NULL,
    goods_amount_fen  INTEGER NOT NULL,
    delivery_fee_fen  INTEGER NOT NULL,
    pay_amount_fen    INTEGER NOT NULL,
    refunded_fen      INTEGER NOT NULL DEFAULT 0,
    submit_token      TEXT NOT NULL DEFAULT '',
    building_code     TEXT NOT NULL DEFAULT '',
    address_text      TEXT NOT NULL DEFAULT '',
    phone             TEXT NOT NULL DEFAULT '',
    remark            TEXT NOT NULL DEFAULT '',
    cancel_reason     TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,
    pay_deadline      TEXT,
    accept_deadline   TEXT,
    delivered_at      TEXT,
    completed_at      TEXT,
    cancelled_at      TEXT
);
CREATE TABLE IF NOT EXISTS order_item (
    item_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id       INTEGER NOT NULL,
    dish_id        INTEGER NOT NULL,
    dish_name      TEXT NOT NULL,
    unit_price_fen INTEGER NOT NULL,
    qty            INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS payment (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pay_no     TEXT NOT NULL UNIQUE,
    order_id   INTEGER NOT NULL,
    order_no   TEXT NOT NULL,
    amount_fen INTEGER NOT NULL,
    status     TEXT NOT NULL,
    paid_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refund (
    refund_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    refund_no    TEXT NOT NULL UNIQUE,
    order_id     INTEGER NOT NULL,
    order_no     TEXT NOT NULL,
    amount_fen   INTEGER NOT NULL,
    type         TEXT NOT NULL,
    status       TEXT NOT NULL,
    reason       TEXT NOT NULL DEFAULT '',
    requested_by TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    settled_at   TEXT
);
CREATE TABLE IF NOT EXISTS delivery_task (
    task_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL,
    order_no     TEXT NOT NULL,
    rider_id     INTEGER,
    rider_name   TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL,
    area_code    TEXT NOT NULL DEFAULT '',
    pickup_text  TEXT NOT NULL DEFAULT '',
    dropoff_text TEXT NOT NULL DEFAULT '',
    fail_reason  TEXT NOT NULL DEFAULT '',
    assigned_at  TEXT,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS operation_log (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id   INTEGER,
    operator_name TEXT NOT NULL DEFAULT '',
    target_type   TEXT NOT NULL,
    target_id     INTEGER,
    target_desc   TEXT NOT NULL DEFAULT '',
    action        TEXT NOT NULL,
    before_value  TEXT NOT NULL DEFAULT '',
    after_value   TEXT NOT NULL DEFAULT '',
    reason        TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    receiver_id     INTEGER NOT NULL,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    read_flag       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS building (
    code     TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    in_range INTEGER NOT NULL DEFAULT 1
);
"""


def parse_dt(text: str | None) -> datetime | None:
    """ISO 字符串转 datetime，空值返回 None（各仓储共用）。"""
    if not text:
        return None
    return datetime.fromisoformat(text)


def fmt_dt(value: datetime | None) -> str | None:
    """datetime 转 ISO 字符串，None 透传（各仓储共用）。"""
    return value.isoformat() if value else None


class Database:
    """持有 SQLite 连接与跨线程互斥锁，仓储层经由它执行全部 SQL。"""

    def __init__(self, path: str) -> None:
        """打开（或创建）数据库并确保全部表存在。

        path 传 ":memory:" 时为纯内存库，测试用它获得互相隔离的全新状态。
        """
        self._lock = threading.RLock()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """执行写语句并提交，返回 lastrowid。调用方必须已持有业务视角的语义保证。"""
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid or 0

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        """查询单行，无结果返回 None。"""
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """查询多行。"""
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        """关闭连接（应用退出时调用）。"""
        with self._lock:
            self._conn.close()
