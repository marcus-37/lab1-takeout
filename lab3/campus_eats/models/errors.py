"""领域异常。

服务层与领域模型用这些异常表达业务规则失败；网关与界面层捕获后转为
用户可读的提示。禁止用通用 Exception 传递业务错误，保证错误可分类处理。
"""


class DomainError(Exception):
    """业务规则错误的基类，message 面向用户可读。"""


class PermissionDeniedError(DomainError):
    """越权访问、未登录或账号状态不允许该操作（REQ-001）。"""


class IllegalTransitionError(DomainError):
    """订单或配送任务的状态迁移不符合状态机（实验二状态图）。"""


class InsufficientBalanceError(DomainError):
    """钱包余额不足以完成支付（REQ-010）。"""


class OutOfStockError(DomainError):
    """菜品当日库存不足或已售罄（REQ-005）。"""


class CartShopMismatchError(DomainError):
    """购物车只能包含同一店铺的菜品，跨店加购被拒绝（REQ-007）。"""


class ValidationError(DomainError):
    """输入不合法：价格、电话格式、地址范围、备注长度等（REQ-004/008）。"""


class ConflictError(DomainError):
    """并发或重复提交冲突：重复审核、重复支付、令牌重放等（REQ-024）。"""
