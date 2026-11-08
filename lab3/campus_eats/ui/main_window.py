"""界面主壳：登录 → 按角色装配视图；QTimer 驱动调度器与界面刷新。

对应组件图客户端层的四个端：界面只经网关调用服务（gateway.require），
订单状态等业务写操作一律发生在服务层；QTimer 在 GUI 线程内周期执行
scheduler.run_due()，超时规则与界面刷新同频，避免跨线程更新控件。
调度心跳吞掉单次异常以免界面停摆，属既定取舍。
"""
# pylint: disable=broad-exception-caught

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from campus_eats.models.enums import Role
from campus_eats.ui import theme
from campus_eats.ui.admin_view import AdminView
from campus_eats.ui.customer_view import CustomerView
from campus_eats.ui.login import LoginWindow
from campus_eats.ui.merchant_view import MerchantView
from campus_eats.ui.rider_view import RiderView

REFRESH_MS = 1000


def run_ui(app) -> int:
    """启动 Qt 事件循环；返回退出码。"""
    qt_app = QApplication.instance() or QApplication([])
    qt_app.setStyleSheet(theme.QSS)
    login = LoginWindow(app, on_login=lambda account: _enter(app, account, login))
    login.show()
    return qt_app.exec()


def _enter(app, account, login) -> None:
    """登录成功：关登录页，开对应角色窗口。"""
    login.close()
    shell = RoleShell(app, account)
    shell.show()
    app.current_shell = shell                    # 供登出后回到登录页


class RoleShell(QWidget):
    """角色窗口外壳：顶部状态条 + 角色视图 + 调度心跳。"""

    def __init__(self, app, account) -> None:
        """按角色装配视图并启动定时器。"""
        super().__init__()
        self._app = app
        self._account = account
        self.setObjectName("Root")
        self.setWindowTitle(f"校园食光 · {account.role.label}端 · {account.name}")
        self.resize(1180, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        info = QWidget()
        info.setObjectName("Root")
        row = QHBoxLayout(info)
        row.setContentsMargins(20, 6, 20, 6)
        self.clock_label = QLabel()
        self.clock_label.setObjectName("Hint")
        row.addStretch(1)
        row.addWidget(self.clock_label)
        root.addWidget(info)

        if account.role is Role.CUSTOMER:
            self.view = CustomerView(app, account, self._logout)
        elif account.role is Role.MERCHANT:
            self.view = MerchantView(app, account, self._logout)
        elif account.role is Role.RIDER:
            self.view = RiderView(app, account, self._logout)
        else:
            self.view = AdminView(app, account, self._logout)
        root.addWidget(self.view, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(REFRESH_MS)
        self._tick()

    def _tick(self) -> None:
        """每秒：驱动调度器 + 刷新界面 + 更新时钟显示。"""
        try:
            self._app.scheduler.run_due()
        except Exception:                        # pylint: disable=broad-exception-caught
            pass                                 # 界面心跳不因单次调度异常中断
        now = self._app.clock.now()
        self.clock_label.setText(f"服务端时间 {now:%Y-%m-%d %H:%M:%S}"
                                 "（演示模式 60 倍加速）"
                                 if hasattr(self._app.clock, "_speed")
                                 else f"服务端时间 {now:%Y-%m-%d %H:%M:%S}")
        self.view.refresh()

    def _logout(self) -> None:
        """登出：关当前窗口，回登录页。"""
        self._timer.stop()
        self._app.gateway.logout()
        self.close()
        login = LoginWindow(self._app,
                            on_login=lambda account: _enter(self._app, account, login))
        login.show()
