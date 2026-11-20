# 团餐备份调度板

供中央厨房调度员按发餐波次查订单分配、改签争议、车辆余位与备用餐用量。点选订单可核对实际装车批号和替代批准行。

## 启动

```sh
docker compose up --build
```

打开 `http://localhost:18448`。切换排练用的干净样例与现场样例，或导入同结构的 JSON。计算发餐后，可在交接签单中重跑、签收和下载证据。SQLite 命名卷保存运行和签单记录。API 说明见 `/docs`。

宿主安装 `requirements.txt` 后执行 `uvicorn app.main:app --port 18448` 或 `pytest -q`。容器内测试执行 `docker compose exec -T app pytest -q`。字段见 [数据字典](docs/DATA-DICTIONARY.md)，规则及测试见 [深度登记](docs/DEPTH.md)。

## 故障救援

发餐归档后若有车辆故障，在调度板「故障救援」选择故障车并按需填写备用车（结构同 `trips`），先 `POST /api/runs/{id}/rescues/preview` 预览，确认装载记录与可用餐数对账相符，再 `POST /api/runs/{id}/rescues` 发布可发布救援记录。记录列明受影响订单改到哪辆车、装哪些批号，以及原车和接运车的份数与未送达量。同一故障重试复用原记录，不会重复占位或重复耗餐。
