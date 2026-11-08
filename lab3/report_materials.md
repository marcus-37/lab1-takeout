# 实验三报告素材包（纯客观事实，不含论述）

> 用途：撰写报告时的查证与引用底料。本文件只汇总开发过程中已经产生的
> 客观数据、出处索引与自查问题清单；**刻意不包含**成段论述、章节草稿与
> 结论性分析——那些是报告正文，按要求应由作者本人撰写。
> 数据均可用所附命令复现。

## 1. 规模数据（复现：python build/count_lines.py）

| 目录 | 文件数 | 总行数 | 代码行（token 口径，去空行与纯注释） |
| --- | --- | --- | --- |
| campus_eats | 44 | 5789 | 4417 |
| tests | 7 | 868 | 717 |
| scripts | 1 | 282 | 231 |
| 合计 | 52 | 6939 | 5365 |

## 2. 验证结果（每项一条命令可复现）

- pytest：63 passed（约 16.7s，含 200 线程并发用例）——`python -m pytest`
- pylint：10.00/10——`python -m pylint campus_eats`（禁用 5 项及逐条理由见 `.pylintrc`）
- 端到端验收：32 项全过——`python scripts/e2e_check.py`
- 并发验收数字：库存 10、200 并发提交 → 成功订单恰好 10、available=0、reserved_qty=10、sold_qty=0（未支付）

## 3. 提交历史（git log --oneline，报告"Git 管理"章节素材）

| 提交 | 内容 |
| --- | --- |
| d8bd71f | 实验三脚手架：依赖清单、包骨架、pylint 配置、AI 记录 |
| 4906424 | 领域模型层：类图六包逐一映射（状态机迁移表、每日库存、金额工具） |
| be11f3d | 消除两处 pylint 告警 |
| c8fba63 | SQLite 仓储层（修复子类 role 默认值缺陷） |
| a7a35c4 | 应用服务层：网关/八服务/时钟/调度器/种子，e2e 32 项通过 |
| b2f5278 | PySide6 界面：登录 + 四角色端 |
| fe3ae0d | pytest 套件 63 项 + 两个统计缺陷修复 |
| 7949c53 | 按实现回改实验二类图并重渲染（lab2 目录） |
| 1029c55 | 报告管线、代码量统计、打包脚本 |

远程：github.com/marcus-37/lab1-takeout，main 分支；标签 lab1-ai-draft / lab1-final 未动。

## 4. 目录结构 ↔ UML 对应（"UML 如何转换为代码"章节素材）

| UML 图 | 代码位置 | 对应关系 |
| --- | --- | --- |
| 类图六包 | campus_eats/models/（7 文件） | account / shop_dish / cart_order / payment_refund / delivery / audit + enums |
| 组件图应用服务层 | campus_eats/services/（12 文件） | GW=gateway，8 个领域服务，SCH=scheduler，时钟=clock，上下文=context |
| 组件图基础设施层 | campus_eats/repositories/（6 文件） | MySQL→SQLite（Database 单连接+锁），OSS→emoji 图标字段 |
| 客户端层四端 | campus_eats/ui/（7 文件） | customer/merchant/rider/admin 视图 + login + 主壳 + theme |
| 状态图 | models/cart_order.py 的 LEGAL_TRANSITIONS | 迁移表逐条对应状态图箭头 |
| 时序图 | services/order_service.submit_order / payment_service.pay | alt 分支逐一落地 |

组件图服务间箭头的代码衔接机制：见 `app.py` 装配段（set_payment_service /
set_order_service / on_order_ready 回调 / set_dependencies）。

## 5. 设计-实现差异（实验二报告第 6 章约定"以实现为准回改设计"；类图已更新，提交 7949c53）

1. OrderStatus 补「配送异常」挂起态（状态图有、类图枚举漏）
2. ShopStatus 补「待审核 / 已驳回」前置态（REQ-002 入驻流程）
3. 新增 Building 预设楼栋类（REQ-008 地址白名单）
4. Refund 补 status / requestedBy 字段（24 小时自动同意需状态）
5. login/logout 从 Account 移入 UserService；Rider.acceptTask 移入 DispatchService（需要跨实体联动，画在实体上不成立）

## 6. 真实返工事件索引（详见 ai_log.md 六条记录；报告"生成内容不符合预期"章节素材）

| # | 事件 | 发现手段 | 出处 |
| --- | --- | --- | --- |
| 1 | money.py 漏 import ValidationError | pylint E0602 | ai_log §2 |
| 2 | 四类账号子类 role 默认值缺陷 | 四角色全链路冒烟 | ai_log §2 |
| 3 | .pylintrc 节名与 pylint 4.x 不匹配风险 | --generate-rcfile 核对 | ai_log §1 |
| 4 | DeliveryTask._transit 只校验不变更状态 | e2e 验收第 15 步 | ai_log §3 |
| 5 | 部分退款后整单取消超额退款 | e2e 设计推敲 | ai_log §3 |
| 6 | 变异方法接收陈旧实体覆盖新状态 | e2e → 重构按 id 现取 | ai_log §3 |
| 7 | 令牌幂等：购物车清空后重试必然失配 | e2e 第 8 步 | ai_log §3 |
| 8 | 骑手完成单统计被"未完任务"查询过滤 | pytest 写红 | ai_log §6 |
| 9 | 营业额误计未支付订单（口径错） | pytest 写红 | ai_log §6 |
| 10 | 测试假通过：重放用例用了新令牌 | 人工读断言语义发现 | ai_log §6 |

## 7. 运行与演示（"编译与运行结果"章节素材，截图请自行截取）

- 正常模式：`.venv\Scripts\python -m campus_eats`；演示模式加 `--demo`（1 秒=1 分钟）
- 演示账号（密码均 123456）：顾客 13800000001 / 商家 13900000001 / 骑手 13700000001 / 管理员 13600000001
- 建库：首次运行自动建 campus_eats.db 并写种子（2 店 6 菜 7 楼栋 3 骑手）
- 可演示的超时点：待支付 30 分钟（demo 约 30 秒）、未接单 10 分钟（约 10 秒）、退款 24 小时自动同意（demo 约 24 分钟）

## 8. 报告逐章自查问题（题目要求的五块内容 → 撰写前先能回答；只列问题，答案请基于事实自己组织）

1. **UML→代码**：类图六包各自落到哪个文件？哪些类图字段被拆成独立类（为什么）？组件图的"订单状态唯一写入口"在代码里靠什么保证？最终规模数字是多少（用第 1 节口径说明总行数与代码行的差别）？
2. **大模型辅助做了什么**：对照 ai_log 六条时间线——每条里"你"的决策点是什么（选型三次拍板、两次"继续"推进、方案否决）？实际工作流与题目提示的"需求→存根+规约→代码"相比走了什么路径（提示：实际是模型→仓储→服务，存根并入实现提交），为什么调整？
3. **不符合预期时怎么办**：第 6 节 10 件事各靠什么手段发现？归纳哪些问题静态检查抓得到、哪些必须跑起来才暴露、哪些只有靠人读断言语义才能发现？
4. **编译与运行结果**：第 7 节命令的输出与四端截图；超时规则在 demo 模式下的实际观察值。
5. **Git 管理**：第 3 节提交序列的划分意图（每层一个有意义的提交）；类图回改为何单独提交到 lab2；报告引用 prompt engineering 方法处记得按题目要求标注参考文献。

## 9. 已有可引用文件清单

- `ai_log.md`：六条 AI 使用记录（任务/产出/问题/处理四要素）
- `README.md`：运行、测试、统计表
- `build/count_lines.py` / `build/package.py` / `build/doc.py`：三个可复现脚本
- `HANDOFF.md`（仓库外）：项目级交接与约定
