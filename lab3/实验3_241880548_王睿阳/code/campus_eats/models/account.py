"""用户与权限模块的领域模型，对应类图「用户与权限」包。

类图差异：类图把 login/logout 画在 Account 上；实现中登录需要访问仓储、
密码校验与会话管理，故移入 UserService，Account 只保留纯状态判断。
"""

import hashlib
import hmac
from abc import ABC
from dataclasses import dataclass
from datetime import datetime

from campus_eats.models.enums import AccountStatus, Role
from campus_eats.models.money import assert_positive_fen


def hash_password(phone: str, password: str) -> str:
    """密码散列：PBKDF2-HMAC-SHA256，以账号手机号作盐。

    原型不做登录失败锁定与密码修改，散列迭代 10 万次防止库文件被拖走后
    被彩虹表直接还原；更严格的口令策略见实验报告说明。
    """
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), phone.encode("utf-8"), 100_000)
    return digest.hex()


def verify_password(phone: str, password: str, password_hash: str) -> bool:
    """校验密码是否与存储散列一致，使用恒定时间比较。"""
    return hmac.compare_digest(hash_password(phone, password), password_hash)


@dataclass
class Account(ABC):
    """四类角色账号的抽象基类（REQ-001）。"""

    phone: str = ""
    name: str = ""
    password_hash: str = ""
    role: Role = Role.CUSTOMER
    status: AccountStatus = AccountStatus.NORMAL
    account_id: int | None = None
    created_at: datetime | None = None

    def is_enabled(self) -> bool:
        """账号是否可用：封禁后任何角色均不能登录（REQ-001）。"""
        return self.status is AccountStatus.NORMAL


@dataclass
class Customer(Account):
    """顾客：钱包余额支付，余额以分存储（REQ-010）。"""

    role: Role = Role.CUSTOMER
    balance_fen: int = 0

    def recharge(self, amount_fen: int) -> None:
        """充值：金额必须为正，直接累加余额。"""
        assert_positive_fen(amount_fen, "充值")
        self.balance_fen += amount_fen

    def deduct(self, amount_fen: int) -> bool:
        """扣减余额：充足则扣除并返回 True，不足返回 False 且不扣（REQ-010）。"""
        assert_positive_fen(amount_fen, "支付")
        if self.balance_fen < amount_fen:
            return False
        self.balance_fen -= amount_fen
        return True


@dataclass
class Merchant(Account):
    """商家：账号与店铺一一对应，本期不设店员子账号（REQ-001）。"""

    role: Role = Role.MERCHANT
    license_no: str = ""


@dataclass
class Rider(Account):
    """配送人员：平台自营骑手，按片区接收派单（REQ-012）。

    类图差异：类图把 acceptTask 画在 Rider 上；接单需要联动配送任务与
    订单状态回写，故移入 DispatchService。
    """

    role: Role = Role.RIDER
    online: bool = False
    area_code: str = ""


@dataclass
class Admin(Account):
    """平台管理员：可审核入驻、干预订单、封禁账号（REQ-026）。"""

    role: Role = Role.ADMIN
    admin_level: int = 1
