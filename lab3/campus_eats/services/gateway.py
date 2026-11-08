"""API 网关（对应组件图 GW）：会话管理与角色鉴权。

单机同进程原型中，「路由」即对服务对象的直接引用；网关的价值收敛在
两件事上：登录会话管理，以及每个界面动作前的角色鉴权（REQ-001——
界面层不允许绕过网关直接使用服务，所有服务方法的 operator 参数都应
来自 gateway.current()）。
"""

from campus_eats.models.account import Account
from campus_eats.models.enums import Role
from campus_eats.models.errors import PermissionDeniedError
from campus_eats.services.user_service import UserService


class Gateway:
    """会话 + 鉴权入口，界面层唯一的服务访问点。"""

    def __init__(self, user_service: UserService) -> None:
        """绑定用户服务，初始无会话。"""
        self._users = user_service
        self._session: Account | None = None

    def login(self, phone: str, password: str) -> Account:
        """登录并建立会话；已登录时先登出原会话（单机单会话）。"""
        account = self._users.login(phone, password)
        self._session = account
        return account

    def logout(self) -> None:
        """登出当前会话。"""
        self._session = None

    def current(self) -> Account | None:
        """当前登录账号，未登录为 None。"""
        return self._session

    def require(self, *roles: Role) -> Account:
        """鉴权：要求已登录且角色匹配，否则抛 PermissionDeniedError（REQ-001）。

        用法：account = gateway.require(Role.CUSTOMER) 后再调用服务方法，
        保证越权访问在进入业务逻辑前被拦截。
        """
        if self._session is None:
            raise PermissionDeniedError("请先登录")
        if roles and self._session.role not in roles:
            raise PermissionDeniedError(
                f"当前角色「{self._session.role.label}」无权执行该操作")
        return self._session
