# 校园食光 —— 外卖点餐与配送系统（实验三实现）

按实验二 UML 设计实现的桌面应用：顾客点餐、商家接单、骑手配送、管理员审核与干预，
覆盖实验一需求中 24 条已确认需求（REQ-020/021 两条非功能性能指标除外，见实验报告说明）。

## 技术栈

- Python 3.10+，PySide6 桌面界面，SQLite 持久化，pytest 单元测试，pylint 风格检查
- 架构与实验二组件图对应：UI（客户端层）→ gateway（API 网关）→ services（应用服务层）
  → repositories（基础设施层，SQLite 代替设计中的 MySQL）

## 环境准备

```powershell
cd lab3
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 运行

```powershell
.venv\Scripts\python -m campus_eats          # 正常模式，真实时钟
.venv\Scripts\python -m campus_eats --demo   # 演示模式：时间加速 60 倍（1 秒 = 1 分钟）
```

首次运行自动建库（`campus_eats.db`）并写入种子数据（四类角色账号、店铺、菜品、楼栋列表）。
演示模式下，「30 分钟未支付取消」「10 分钟未接单取消」「2 小时自动完成」等定时规则
约 30 秒 / 10 秒 / 2 分钟即可观察到，便于验收与演示。

## 测试与风格检查

```powershell
.venv\Scripts\python -m pytest -q                       # 63 项测试
.venv\Scripts\python -m pylint campus_eats              # 风格检查，当前 10.00/10
.venv\Scripts\python scripts/e2e_check.py               # 32 项端到端验收（含并发）
```

## 代码量统计（实验报告引用，`build/count_lines.py` 可复现）

| 目录 | 文件数 | 总行数 | 代码行（去空行与注释） |
| --- | --- | --- | --- |
| campus_eats | 44 | 5789 | 4417 |
| tests | 7 | 868 | 717 |
| scripts | 1 | 282 | 231 |
| **合计** | **52** | **6939** | **5365** |

## 目录结构

```
campus_eats/
├── models/         领域模型（与实验二类图六包一一对应）
├── repositories/   SQLite 仓储层
├── services/       应用服务层：网关、八个领域服务、时钟、定时任务
├── ui/             PySide6 界面（登录 + 四角色端）
├── app.py          组装根：建库、种子数据、依赖注入、启动
└── seed.py         种子数据
tests/              pytest 测试
build/              报告构建脚本（复用实验二流水线）
ai_log.md           大模型辅助开发过程记录
```

## 关键设计约定（与实验二一致）

1. 金额一律以 int 存「分」，任何环节不用浮点（REQ-022）。
2. 订单状态只允许 `order_service` 修改，其他服务与 UI 一律通过接口回写。
3. 库存按「菜品 + 日期」记录 totalQty / reservedQty / soldQty（REQ-005）。
4. 提交订单携带一次性令牌，重复提交返回首次结果（REQ-024）。
5. 全系统以服务端时钟为唯一时间基准（REQ-027），时钟经 `clock.py` 注入，可加速。
