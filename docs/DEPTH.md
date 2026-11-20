# 深度登记 · 团餐备份调度板

- 规模：中型
- 核心规则：先配不可替换餐，再分配允许替代的订单。组内按最早到站时限处理。每份餐同时扣减批号库存和本车容量。
- 使用者：中央食堂调度员按波次检查配送不足、争议改签、备用耗用与交接记录。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 团餐订单 | 按截点确认改签链与实际应送数 | `GET /api/orders/{sample}` | `app/modules/m1_orders/service.py` | `tests/test_orders.py` |
| M2 套餐替代 | 查看可替代餐与被隔离的环 | `GET /api/substitutions/{sample}` | `app/modules/m2_substitutions/graph.py` | `tests/test_substitutions.py` |
| M3 到站窗口 | 核对同波次、同站的交接时间 | `GET /api/windows/{sample}` | `app/modules/m3_windows/service.py` | `tests/test_windows.py` |
| M4 装车容量 | 检查车次计划和到站资格 | `GET /api/capacity/{sample}` | `app/modules/m4_capacity/service.py` | `tests/test_capacity.py` |
| M5 备用递补 | 展开每次实发车辆、批号与替代证据 | `GET /api/allocation/{sample}` | `app/modules/m5_allocation/dispatch.py` | `tests/test_allocation.py` |
| M6 份数对账 | 复核订单、库存和车载三账 | `GET /api/reconcile/{sample}` | `app/modules/m6_reconcile/totals.py` | `tests/test_reconcile.py` |
| M7 交接签单 | 冻结输入、重跑、签单和下载 | `POST /api/runs` | `app/modules/m7_archive/service.py` | `tests/test_archive.py` |

## 陷阱登记

| 陷阱 | 现象 | 朴素结果 | 处理 | 实现 | 测试 |
|---|---|---|---|---|---|
| TRAP-07 | 修改记录缺上版字段 | 当初版或报错 | 保留已声明量并转争议 | `app/modules/m1_orders/revisions.py` | `tests/test_orders.py::test_incomplete_order_keeps_declared_quantity` |
| TRAP-11 | 脏样例订单重传的时区不同 | 两份应送 | 归一 UTC 秒核对内容 | `app/modules/m1_orders/service.py` | `tests/test_orders.py::test_duplicate_at_utc_same_second` |
| TRAP-13 | 改签消息先于旧版送达 | 拒收或回退 | 按链和时间采信 | `app/modules/m1_orders/service.py` | `tests/test_orders.py::test_revision_sorted_even_when_row_arrives_first` |
| TRAP-14 | 同一改签版本有不同份数 | 后写覆盖 | 保留上个唯一版本份数到争议 | `app/modules/m1_orders/service.py` | `tests/test_orders.py::test_conflicting_revision_preserves_previous_count` |
| TRAP-18 | 订单数组为空 | 空批也显示对平 | 保持待复核 | `app/modules/m6_reconcile/totals.py` | `tests/test_reconcile.py::test_empty_orders_require_review` |
| TRAP-19 | 锁定与弹性订单争车辆和原餐 | 锁定餐被低优先级消耗 | 锁定组优先，其次按截止时间 | `app/modules/m5_allocation/dispatch.py` | `tests/test_allocation.py::test_locked_demands_precede_earlier_flexible_demands` |
| TRAP-20 | 脏样例备用菜替代环 | 循环替换 | 识别强连通环并隔离关联边 | `app/modules/m2_substitutions/graph.py` | `tests/test_substitutions.py::test_cycle_is_removed_from_approved_edges` |
| TRAP-21 | 只有一向通过过敏原审批 | 误作双向许可 | 只认有向批准边 | `app/modules/m2_substitutions/service.py` | `tests/test_substitutions.py::test_edges_are_directional` |
| TRAP-23 | 到站时恰好窗口关闭 | 本车错误占量 | 半开窗口 | `app/modules/m4_capacity/service.py` | `tests/test_windows.py::test_arrival_at_cutoff_is_not_on_time` |
| TRAP-25 | 同站同波次两条有效窗 | 任取其一并发餐 | 两条都隔离，订单转争议 | `app/modules/m3_windows/service.py` | `tests/test_windows.py::test_multiple_windows_same_wave_quarantine_orders` |
| TRAP-26 | 交接签单持旧摘要 | 签到错误快照 | 返回摘要冲突 | `app/modules/m7_archive/service.py` | `tests/test_archive.py::test_signature_requires_current_digest` |
