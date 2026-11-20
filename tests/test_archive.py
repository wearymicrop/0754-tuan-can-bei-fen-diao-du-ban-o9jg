from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app


def start(client):
    response = client.post("/api/runs", json={"sample": "dirty"})
    assert response.status_code == 200, response.text
    return response.json()


def test_reuse_by_content(client, dirty):
    first = start(client)
    second = client.post("/api/runs", json={"source": dirty}).json()
    assert not first["reused"] and second["reused"]
    assert first["manifest"] == second["manifest"]
    assert len(client.get("/api/runs").json()["runs"]) == 1


def test_replay_uses_frozen_input(client):
    first = start(client)
    again = client.post(f'/api/runs/{first["id"]}/rerun').json()
    assert again["reused"] and again["result"] == first["result"]
    assert again["manifest"]["digest"] == first["manifest"]["digest"]


def test_attachment_contains_raw_input(client, dirty):
    first = start(client)
    response = client.get(f'/api/runs/{first["id"]}/export')
    assert "attachment" in response.headers["content-disposition"]
    assert response.json()["source"] == dirty
    assert response.json()["result"]["reconcile"] == first["result"]["reconcile"]


def test_signature_requires_current_digest(client):
    first = start(client)
    response = client.post(f'/api/runs/{first["id"]}/sign', json={"reviewer": "周洁", "digest": "旧摘要"})
    assert response.status_code == 409 and response.json()["code"] == "STALE_DIGEST"  # TRAP-26


def test_signature_replay_and_conflict(client):
    first = start(client)
    endpoint = f'/api/runs/{first["id"]}/sign'
    draft = {"reviewer": "周洁", "digest": first["manifest"]["digest"]}
    assert client.post(endpoint, json=draft).json()["reused"] is False
    assert client.post(endpoint, json=draft).json()["reused"] is True
    assert client.post(endpoint, json={**draft, "reviewer": "李颖"}).status_code == 409
    assert client.get(f'/api/runs/{first["id"]}').json()["signature"]["reviewer"] == "周洁"


def test_concurrent_writes_store_one_run(tmp_path):
    path = tmp_path / "concurrent.sqlite3"
    with TestClient(create_app(path)) as client:
        with ThreadPoolExecutor(max_workers=4) as executor:
            responses = list(executor.map(lambda _: start(client), range(4)))
        assert sum(not item["reused"] for item in responses) == 1
        assert len({item["id"] for item in responses}) == 1


def test_roundtrip_after_reopen(tmp_path):
    path = tmp_path / "restart.sqlite3"
    with TestClient(create_app(path)) as client:
        first = start(client)
        url = f'/api/runs/{first["id"]}'
        client.post(url + "/sign", json={"reviewer": "周洁", "digest": first["manifest"]["digest"]})
        frozen = client.get(url).json()
    with TestClient(create_app(path)) as reopened:
        assert reopened.get(url).json() == frozen


def test_invalid_source_leaves_ledger_empty(client):
    assert client.post("/api/runs", json={}).json()["code"] == "CHOOSE_SOURCE"
    assert client.post("/api/runs", json={"source": {"batch": "测试"}}).json()["code"] == "BAD_SCHEMA"
    assert client.get("/api/runs").json() == {"runs": []}


def test_missing_run_returns_404(client):
    response = client.get("/api/runs/missing/export")
    assert response.status_code == 404 and response.json()["code"] == "RUN_NOT_FOUND"
