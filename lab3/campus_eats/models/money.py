"""金额工具。

全系统金额一律以 int 存「分」，任何环节不使用浮点（REQ-022/027）。
元与分的转换只用字符串拆分与整数运算，杜绝二进制浮点误差。
"""

import re

from campus_eats.models.errors import ValidationError

# 合法输入：1~7 位整数，可带 1~2 位小数（价格最多两位小数，REQ-004）
_YUAN_RE = re.compile(r"^\d{1,7}(?:\.\d{1,2})?$")


def yuan_to_fen(text: str) -> int:
    """把用户输入的元字符串转为分。

    规则（REQ-004）：必须是正数，最多两位小数；"0"、"0.00"、三位小数、
    负数、空串均抛 ValidationError。
    """
    text = text.strip()
    if not _YUAN_RE.match(text):
        raise ValidationError("金额格式不合法：应为不超过两位小数的正数，如 12.34")
    yuan, _, fraction = text.partition(".")
    fraction = (fraction + "00")[:2]
    fen = int(yuan) * 100 + int(fraction)
    if fen <= 0:
        raise ValidationError("金额必须大于 0")
    return fen


def fen_to_yuan(amount_fen: int) -> str:
    """把分格式化为元的显示字符串，如 1234 -> "12.34"、5 -> "0.05"。"""
    if amount_fen < 0:
        raise ValidationError("金额不允许为负")
    yuan, fraction = divmod(amount_fen, 100)
    return f"{yuan}.{fraction:02d}"


def assert_positive_fen(amount_fen: int, what: str) -> None:
    """断言金额为正整数分，用于充值、退款等入口的自卫检查。"""
    if not isinstance(amount_fen, int) or amount_fen <= 0:
        raise ValidationError(f"{what}金额必须为正的整数分")
