"""登录窗口：手机号 + 密码，顾客可自助注册（REQ-001）。

界面动作统一捕获业务异常转为弹窗提示，属界面层约定。
"""
# pylint: disable=broad-exception-caught

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)


class LoginWindow(QWidget):
    """登录 + 顾客注册入口；登录成功回调 on_login(account)。"""

    def __init__(self, app, on_login) -> None:
        """绑定应用与登录成功回调。"""
        super().__init__()
        self._app = app
        self._on_login = on_login
        self.setObjectName("Root")
        self.setWindowTitle("校园食光 · 登录")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 44, 36, 28)
        layout.setSpacing(12)

        title = QLabel("校园食光")
        title.setObjectName("AppTitle")
        subtitle = QLabel("外卖点餐与配送系统 · 实验三实现")
        subtitle.setObjectName("Hint")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(16)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("手机号")
        self.password = QLineEdit()
        self.password.setPlaceholderText("密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.phone)
        layout.addWidget(self.password)

        login_btn = QPushButton("登 录")
        login_btn.setObjectName("Primary")
        login_btn.clicked.connect(self._do_login)
        layout.addWidget(login_btn)

        register_btn = QPushButton("顾客注册")
        register_btn.clicked.connect(self._do_register)
        layout.addWidget(register_btn)

        hint = QLabel("演示账号（密码均为 123456）：\n"
                      "顾客 13800000001 · 商家 13900000001\n"
                      "骑手 13700000001 · 管理员 13600000001")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

    def _do_login(self) -> None:
        """执行登录并回调。"""
        try:
            account = self._app.gateway.login(self.phone.text().strip(),
                                              self.password.text())
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "登录失败", str(exc))
            return
        self._on_login(account)

    def _do_register(self) -> None:
        """弹出顾客注册对话框。"""
        dlg = _RegisterDialog(self._app, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.phone.setText(dlg.phone.text())
            self.password.setFocus()


class _RegisterDialog(QDialog):
    """顾客注册：手机号 / 密码 / 姓名。"""

    def __init__(self, app, parent) -> None:
        """绑定应用。"""
        super().__init__(parent)
        self._app = app
        self.setWindowTitle("顾客注册")
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("11 位手机号")
        self.password = QLineEdit()
        self.password.setPlaceholderText("至少 6 位")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.name = QLineEdit()
        self.name.setPlaceholderText("姓名")
        form = QFormLayout(self)
        form.addRow("手机号", self.phone)
        form.addRow("密码", self.password)
        form.addRow("姓名", self.name)
        buttons = QHBoxLayout()
        submit = QPushButton("注册")
        submit.setObjectName("Primary")
        submit.clicked.connect(self._submit)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(submit)
        buttons.addWidget(cancel)
        form.addRow(buttons)

    def _submit(self) -> None:
        """提交注册。"""
        try:
            self._app.users.register_customer(
                self.phone.text().strip(), self.password.text(),
                self.name.text())
        except Exception as exc:  # noqa: BLE001 界面层统一转提示
            QMessageBox.warning(self, "注册失败", str(exc))
            return
        self.accept()
