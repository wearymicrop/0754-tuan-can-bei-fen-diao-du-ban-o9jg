# 数据字典

顶层 `batch` 是调度批次号，`at` 是带偏移、精确到秒的计划截点。数量一律为整份。数组保留原始顺序，数据行号从 1 起计。

| 数组 | 字段 | 规则 |
|---|---|---|
| `orders` | `order`、`revision`、`supersedes`、`issued`、`station`、`wave`、`meal`、`qty`、`locked`、`status` | 初版 `revision=1`、`supersedes=null`。撤单 `status=cancelled` 时为 0 份。互斥或断链取最近可采信份数计争议。没有可采信版时用同订单最大申报份数挂账。 |
| `substitutions` | `requested`、`spare` | 仅允许从原餐到批准备用餐的直接有向边。涉环品项的连入、连出边全部隔离。 |
| `windows` | `wave`、`station`、`start`、`end` | 波次和站点共同确定唯一交接窗，使用 `[start,end)`。 |
| `trips` | `truck`、`wave`、`capacity`、`departure`、`stops` | 同批次每辆车一趟。`stops` 为顺序的 `station`、`eta` 记录。同车容量由各站共享。 |
| `stock` | `lot`、`meal`、`qty`、`kind`、`ready`、`expires` | `regular` 为常规餐，`spare` 为备用餐。出发时须已就绪，到站时间严格早于过期。互斥备用批号取最大申报份数挂隔离账。 |

分配按锁定、交接窗口结束时间和订单编号排序。每笔先用原餐常规货，再用同餐品备用货，最后使用直接批准的替代餐。组内选用尽早到期的批号，再选可用车辆中最早到站的一辆。可在多车和多批号间拆单。系统输出既定优先级下的可复算排程，未执行全局重排优化。

应送等于实发、缺配与争议。备用申报等于实发、截点结余、截点过期、隔离。已在截点可用但到站会失效的餐保留在截点结余。无订单号或库存批号的行单独隔离，未放入业务合计。每次装车记录订单、车次、窗口、批号和批准行。
