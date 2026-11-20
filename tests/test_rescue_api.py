"""M8 故障救援 API：发布门、幂等重试、多故障车占位与持久化。"""
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app


BACKUP = {
    "truck": "备-甲", "wave": "午线", "capacity": 60,
    "departure": "2026-11-20T11:50:00+08:00",
    "stops": [
        {"station": "创客园", "eta": "2026-11-20T11:58:00+08:00"},
        {"station": "运动馆", "eta": "2026-11-20T12:05:00+08:00"},
    ],
}


def start_run(client):
    return client.post("/api/runs", json={"sample": "dirty"}).json()["id"]


def test_preview_does_not_persist(client):
    run_id = start_run(client)
    response = client.post(f"/api/runs/{run_id}/rescues/preview",
                           json={"failed_truck": "柿-03", "backup": BACKUP})
    assert response.status_code == 200 and response.json()["status"] == "MATCHED"
    assert client.get(f"/api/runs/{run_id}/rescues").json() == {"run_id": run_id, "rescues": []}


def test_publish_then_retry_reuses_record_without_double_booking(client):
    run_id = start_run(client)
    payload = {"failed_truck": "柿-03", "backup": BACKUP}
    first = client.post(f"/api/runs/{run_id}/rescues", json=payload)
    second = client.post(f"/api/runs/{run_id}/rescues", json=payload)
    assert first.status_code == 200 and first.json()["reused"] is False
    assert second.status_code == 200 and second.json()["reused"] is True
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["moves"] == second.json()["moves"]
    assert len(client.get(f"/api/runs/{run_id}/rescues").json()["rescues"]) == 1


def test_drifting_retry_is_conflict_not_a_second_occupancy(client):
    run_id = start_run(client)
    client.post(f"/api/runs/{run_id}/rescues", json={"failed_truck": "柿-03", "backup": BACKUP})
    changed = {"failed_truck": "柿-03", "backup": {**BACKUP, "capacity": 70}}
    response = client.post(f"/api/runs/{run_id}/rescues", json=changed)
    assert response.status_code == 409 and response.json()["code"] == "RESCUE_TAKEN"
    assert len(client.get(f"/api/runs/{run_id}/rescues").json()["rescues"]) == 1


def test_second_failed_truck_sees_capacity_already_taken(client):
    run_id = start_run(client)
    first = client.post(f"/api/runs/{run_id}/rescues",
                        json={"failed_truck": "柿-03", "backup": BACKUP}).json()
    # 柿-04 的 10 个余位已被第一笔救援占用。
    helper = next(v for v in first["vehicles"] if v["truck"] == "柿-04")
    assert helper["remaining_capacity"] == 18
    second = client.post(f"/api/runs/{run_id}/rescues", json={"failed_truck": "柿-05"}).json()
    # 后线无可用接运车：芦港会堂 13 份由柿-06 接走，其余未送达；不会重复占用柿-04。
    assert all(move["to_truck"] != "柿-04" for move in second["moves"])
    assert {r["failed_truck"] for r in client.get(f"/api/runs/{run_id}/rescues").json()["rescues"]} == {
        "柿-03", "柿-05"}


def test_concurrent_retries_store_one_rescue(client):
    run_id = start_run(client)
    payload = {"failed_truck": "柿-03", "backup": BACKUP}
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(
            lambda _: client.post(f"/api/runs/{run_id}/rescues", json=payload), range(4)))
    assert all(item.status_code == 200 for item in responses)
    assert sum(item.json()["reused"] for item in responses) == 3
    assert len({item.json()["id"] for item in responses}) == 1


def test_rescue_roundtrip_after_reopen(tmp_path):
    path = tmp_path / "rescue.sqlite3"
    with TestClient(create_app(path)) as first:
        run_id = start_run(first)
        published = first.post(f"/api/runs/{run_id}/rescues",
                               json={"failed_truck": "柿-03", "backup": BACKUP}).json()
    with TestClient(create_app(path)) as reopened:
        loaded = reopened.get(f"/api/runs/{run_id}/rescues/柿-03").json()
        assert loaded["id"] == published["id"] and loaded["moves"] == published["moves"]


def test_invalid_requests_are_rejected(client):
    run_id = start_run(client)
    assert client.post(f"/api/runs/{run_id}/rescues", json={}).status_code == 422
    missing = client.post(f"/api/runs/{run_id}/rescues",
                          json={"failed_truck": "幽灵车", "backup": BACKUP})
    assert missing.status_code == 404 and missing.json()["code"] == "RESCUE_TRUCK_UNKNOWN"
    bad_backup = client.post(f"/api/runs/{run_id}/rescues/preview",
                             json={"failed_truck": "柿-03", "backup": {"truck": "坏车"}})
    assert bad_backup.status_code == 422 and bad_backup.json()["code"] == "BACKUP_SCHEMA"
    assert client.get(f"/api/runs/{run_id}/rescues/柿-09").status_code == 404


def test_published_record_carries_publishable_audit_fields(client):
    run_id = start_run(client)
    record = client.post(f"/api/runs/{run_id}/rescues",
                         json={"failed_truck": "柿-03", "backup": BACKUP}).json()
    assert record["batch"] and record["id"] and record["generated_at"]
    move = record["moves"][0]
    assert {"order", "lot", "from_truck", "to_truck", "qty", "arrival",
            "order_line", "stock_line", "trip_line", "window_line"} <= set(move)
    failed = next(v for v in record["vehicles"] if v["role"] == "failed")
    assert failed["undelivered"] == failed["original_loaded"] - failed["rescued_loaded"]
