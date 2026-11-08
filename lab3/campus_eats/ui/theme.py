"""界面主题：QSS 样式与通用小部件工厂。

视觉与实验二 UI 稿一致：主色橙 #FF6B2C、背景灰 #F5F6F8、圆角 12px、
微软雅黑。界面只经网关调服务，本文件不含业务逻辑。
"""

PRIMARY = "#FF6B2C"
PRIMARY_DARK = "#E5551A"
BG = "#F5F6F8"
CARD = "#FFFFFF"
TEXT = "#2B2F36"
TEXT_LIGHT = "#8A93A0"
DANGER = "#D93026"
OK_GREEN = "#1E9E62"

QSS = f"""
* {{
    font-family: "Microsoft YaHei", "SimHei", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QWidget#Root {{ background: {BG}; }}
QLabel#AppTitle {{ font-size: 22px; font-weight: 700; color: {PRIMARY}; }}
QLabel#H1 {{ font-size: 18px; font-weight: 700; }}
QLabel#H2 {{ font-size: 15px; font-weight: 700; }}
QLabel#Hint {{ color: {TEXT_LIGHT}; font-size: 12px; }}
QLabel#Money {{ color: {DANGER}; font-weight: 700; }}
QLabel#StatusOpen {{ color: {OK_GREEN}; font-weight: 700; }}
QLabel#StatusRest {{ color: {TEXT_LIGHT}; font-weight: 700; }}
QLabel#Badge {{
    background: #FFF0E8; color: {PRIMARY_DARK};
    border-radius: 8px; padding: 2px 10px; font-size: 12px;
}}
QFrame#Card {{
    background: {CARD}; border: 1px solid #ECEEF2; border-radius: 12px;
}}
QPushButton {{
    background: {CARD}; border: 1px solid #D9DEE7; border-radius: 9px;
    padding: 7px 16px;
}}
QPushButton:hover {{ border-color: {PRIMARY}; color: {PRIMARY_DARK}; }}
QPushButton#Primary {{
    background: {PRIMARY}; border: none; color: white; font-weight: 700;
    padding: 9px 20px;
}}
QPushButton#Primary:hover {{ background: {PRIMARY_DARK}; }}
QPushButton#Primary:disabled {{ background: #F3B598; color: #FFF7F3; }}
QPushButton#Danger {{
    background: white; border: 1px solid {DANGER}; color: {DANGER};
}}
QPushButton#Danger:hover {{ background: #FDEDEC; }}
QLineEdit, QComboBox, QTextEdit, QSpinBox {{
    background: white; border: 1px solid #D9DEE7; border-radius: 9px;
    padding: 7px 10px; selection-background-color: {PRIMARY};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {PRIMARY}; }}
QTableWidget {{
    background: white; border: 1px solid #ECEEF2; border-radius: 10px;
    gridline-color: #F0F2F6;
}}
QHeaderView::section {{
    background: #F7F8FA; border: none; border-bottom: 1px solid #ECEEF2;
    padding: 6px; font-weight: 700;
}}
QTabWidget::pane {{ border: 1px solid #ECEEF2; border-radius: 10px; background: white; }}
QTabBar::tab {{
    background: transparent; padding: 8px 18px; color: {TEXT_LIGHT};
}}
QTabBar::tab:selected {{ color: {PRIMARY}; font-weight: 700;
    border-bottom: 2px solid {PRIMARY}; }}
QListWidget {{ background: white; border: 1px solid #ECEEF2; border-radius: 10px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: #D9DEE7; border-radius: 4px; }}
"""


def yuan(fen: int) -> str:
    """分 -> "¥x.xx" 显示文本。"""
    from campus_eats.models.money import fen_to_yuan  # 局部导入避免 models↔ui 环

    return f"¥{fen_to_yuan(fen)}"
