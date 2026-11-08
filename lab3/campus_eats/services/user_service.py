"""用户与权限服务（对应组件图 USER，REQ-001/010/026）。

类图差异：类图把 login/logout 画在 Account 上，实现移到这里——
登录需要访问仓储、校验密码并管理会话，属于服务职责。
"""

from campus_eats.models.account import (
    Account, Admin, Customer, hash_password, verify_password,
)
from campus_eats.models.audit import OperationLog
from campus_eats.models.enums import AccountStatus, Role
from campus_eats.models.errors import (
    ConflictError, PermissionDeniedError, ValidationError,
)
from campus_eats.models.money import assert_positive_fen, fen_to_yuan
from campus_eats.services.context import ServiceContext


class UserService:
    """登录鉴权、顾客注册充值、账号封禁。"""

    def __init__(self, context: ServiceContext) -> None:
        """绑定服务上下文。"""
        self._ctx = context

    def login(self, phone: str, password: str) -> Account:
        """手机号 + 密码登录。

        规约（REQ-001）：密码错误、账号不存在抛 ValidationError；
        账号已封禁抛 PermissionDeniedError——封禁账号任何角色均不能登录。
        成功返回账号（含角色），会话由网关层管理。
        """
        account = self._ctx.repos.accounts.find_by_phone(phone.strip())
        if account is None or not verify_password(phone.strip(), password,
                                                  account.password_hash):
            raise ValidationError("手机号或密码不正确")
        if not account.is_enabled():
            raise PermissionDeniedError("账号已被封禁，如有疑问请联系平台管理员")
        return account

    def register_customer(self, phone: str, password: str, name: str) -> Customer:
        """顾客自助注册：手机号唯一；新顾客赠送 2000 元演示余额便于验收。"""
        phone = phone.strip()
        if not (len(phone) == 11 and phone.isdigit() and phone[0] == "1"):
            raise ValidationError("手机号格式不合法")
        if len(password) < 6:
            raise ValidationError("密码至少 6 位")
        if not name.strip():
            raise ValidationError("姓名不能为空")
        if self._ctx.repos.accounts.find_by_phone(phone) is not None:
            raise ConflictError("该手机号已注册")
        customer = Customer(phone=phone, name=name.strip(),
                            password_hash=hash_password(phone, password),
                            balance_fen=200_000, created_at=self._ctx.clock.now())
        self._ctx.repos.accounts.add(customer)
        return customer

    def recharge(self, operator: Account, customer_id: int, amount_fen: int) -> int:
        """钱包充值：本期不接真实支付，作为演示功能存在（REQ-010 边界）。

        返回充值后余额（分）。
        """
        assert_positive_fen(amount_fen, "充值")
        with self._ctx.lock:
            customer = self._ctx.repos.accounts.get(customer_id)
            if not isinstance(customer, Customer):
                raise ValidationError("充值对象不存在或不是顾客")
            before = fen_to_yuan(customer.balance_fen)
            customer.recharge(amount_fen)
            self._ctx.repos.accounts.update(customer)
            self._ctx.repos.logs.add(OperationLog(
                operator_id=operator.account_id, operator_name=operator.name,
                target_type="ACCOUNT", target_id=customer_id,
                target_desc=f"顾客 {customer.name}", action="充值", before_value=before,
                after_value=fen_to_yuan(customer.balance_fen),
                created_at=self._ctx.clock.now()))
            return customer.balance_fen

    def get_customer(self, customer_id: int) -> Customer:
        """按 id 取顾客，类型不符抛错。"""
        account = self._ctx.repos.accounts.get(customer_id)
        if not isinstance(account, Customer):
            raise ValidationError("顾客不存在")
        return account

    def set_banned(self, operator: Account, account_id: int, banned: bool,
                   reason: str = "") -> None:
        """管理员封禁 / 解封账号（REQ-026）。"""
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可封禁账号")
        if banned and not reason.strip():
            raise ValidationError("封禁必须填写原因")
        with self._ctx.lock:
            account = self._ctx.repos.accounts.get(account_id)
            if account is None:
                raise ValidationError("账号不存在")
            if isinstance(account, Admin):
                raise ValidationError("不能封禁管理员账号")
            before = account.status.label
            account.status = AccountStatus.BANNED if banned else AccountStatus.NORMAL
            self._ctx.repos.accounts.update(account)
            self._ctx.repos.logs.add(OperationLog(
                operator_id=operator.account_id, operator_name=operator.name,
                target_type="ACCOUNT", target_id=account_id,
                target_desc=f"{account.role.label} {account.name}",
                action="封禁" if banned else "解封", before_value=before,
                after_value=account.status.label, reason=reason,
                created_at=self._ctx.clock.now()))
