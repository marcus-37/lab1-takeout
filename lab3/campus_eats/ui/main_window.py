"""界面入口占位：UI 阶段替换为 PySide6 主窗口。"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from campus_eats.app import App

from campus_eats.models.enums import Role


def run_ui(app: "App") -> None:
    """启动界面（当前为占位，仅打印可用演示账号）。"""
    print("【UI 未实现】服务层装配完成，可用演示账号（密码 123456）：")
    for role in (Role.CUSTOMER, Role.MERCHANT, Role.RIDER, Role.ADMIN):
        for account in app.repos.accounts.list_by_role(role):
            print(f"  {role.label}  {account.phone}  {account.name}")
