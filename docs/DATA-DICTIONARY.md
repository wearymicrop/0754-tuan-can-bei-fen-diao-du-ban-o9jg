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

## 故障救援（M8）

救援请求挂在已归档运行下：`failed_truck` 为故障车，`backup` 可省略，结构同 `trips` 行（含 `stops`）。备用车波次必须与故障车一致，出发不早于批次截点，编号不得与既有车次冲突。`POST /rescues/preview` 只试算不占位，`POST /rescues` 对账相符（`status=MATCHED`）才落库。

救援只搬运故障车上已装车的实物餐，不新占库存、不重复耗餐：每条 `moves` 行都回溯到原车一条装车记录（`order_line`、`stock_line`、`trip_line`、`window_line`），并写明接运车 `to_truck`、批号 `lot`、份数与到站。受影响订单按锁定优先、再按窗口截止、再按订单号处理，可在多车多批号间拆单；无准点接运车记 `NO_RESCUE_TRUCK`，准点车余位耗尽记 `RESCUE_FULL`，批号在接运站已失效或未就绪记 `RESCUE_LOT_UNSAFE`，相应份数进入 `undelivered_qty`。

`vehicles` 给出每辆车的角色（`failed`/`rescue`/`backup`/`idle`）、原车装载、救援接入、最终装载、余位与未送达量；故障车最终装载为 0，未送达量等于原车装载减已接运。`checks` 逐项核对订单份数对平、批号只搬运不耗餐、接运车不超载、半开窗口、批号时效与车队总数守恒。同一运行同一故障车只有一条救援：相同请求重试返回 `reused=true` 的原记录，请求漂移返回 `RESCUE_TAKEN`。
