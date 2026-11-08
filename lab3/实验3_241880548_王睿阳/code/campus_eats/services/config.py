"""系统级业务常量。

超时阈值等数值与实验一需求一一对应；改这里即可整体调整，
测试使用 FakeClock 时也读这些常量。
"""

# 配送费：平台一口价（实验一未约定按距离计费，取固定值并在报告说明）
DELIVERY_FEE_FEN = 300

# REQ-010：订单提交后 30 分钟未支付自动取消并释放库存
PAY_TIMEOUT_MINUTES = 30
# REQ-015：支付后商家 10 分钟内未接单自动取消
ACCEPT_TIMEOUT_MINUTES = 10
# REQ-013：已送达 2 小时未确认自动完成
AUTO_COMPLETE_HOURS = 2
# REQ-026：接单后取消申请商家 24 小时未处理自动同意退款
REFUND_AUTO_AGREE_HOURS = 24
# 状态图「待配送 --配送超时--> 配送异常」：出餐后 15 分钟无人接单挂起
DISPATCH_TIMEOUT_MINUTES = 15

# REQ-008：备注长度超限截断
REMARK_MAX_LEN = 100
# 订单号 / 流水号的随机段长度
TOKEN_BYTES = 16
