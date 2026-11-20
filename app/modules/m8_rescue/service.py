from datetime import datetime, timezone

from app.clock import instant
from app.codec import digest
from app.errors import DomainError
from app.records import token
from .planner import plan


def _snapshot(ledger, run_id):
    source, snapshot = ledger.read(run_id)
    if snapshot["manifest"]["digest"] != digest(snapshot["result"]):
        raise DomainError("REPLAY_MISMATCH", "运行结果与归档摘要不一致", 409)
    return source, snapshot


def _load_context(ledger, run_id):
    source, snapshot = _snapshot(ledger, run_id)
    prior_records = ledger.rescues_for_run(run_id)
    engaged = {record["failed_truck"] for record in prior_records}
    prior_moves = [move for record in prior_records for move in record["moves"]]
    prior_backups = [record["backup"] for record in prior_records if record.get("backup")]
    return source, snapshot, engaged, prior_moves, prior_backups, prior_records


def _replan(snapshot, source, failed_truck, backup_raw, prior_records):
    # 重算某辆故障车时，只让“其它故障车”的已发布救援占位，避免本车旧移动重复扣余位。
    other = [record for record in prior_records if record["failed_truck"] != failed_truck]
    prior_moves = [move for record in other for move in record["moves"]]
    prior_backups = [record["backup"] for record in other if record.get("backup")]
    engaged = {record["failed_truck"] for record in other}
    return plan(snapshot["result"], failed_truck, instant(source["at"]), backup_raw,
                engaged, prior_backups, prior_moves)


def _backup_digest(backup_raw):
    return digest(backup_raw) if backup_raw is not None else None


def preview(ledger, run_id, failed_truck, backup_raw=None):
    source, snapshot, _engaged, _moves, _backups, prior_records = _load_context(ledger, run_id)
    # 预览不占位：即便该故障车已发布过救援，也用同一份已占用余位重算供调度页核对。
    return _replan(snapshot, source, failed_truck, backup_raw, prior_records)


def publish(ledger, run_id, failed_truck, backup_raw=None):
    if not token(failed_truck):
        raise DomainError("RESCUE_TRUCK_REQUIRED", "请指定故障车辆")
    source, snapshot, engaged, _moves, _backups, prior_records = _load_context(ledger, run_id)
    # 已发布过的故障车：只有与原请求完全一致的重试才允许复用，漂移请求由台账拒绝。
    if failed_truck in engaged and backup_raw is None:
        existing = ledger.rescue(run_id, failed_truck)
        if existing.get("backup") is not None:
            raise DomainError("RESCUE_TAKEN", "该故障车已发布救援，不能重复占位或重复耗餐", 409)
    draft = _replan(snapshot, source, failed_truck, backup_raw, prior_records)
    if draft["status"] != "MATCHED":
        raise DomainError("RESCUE_UNBALANCED", "装载记录与可用餐数对账不符，禁止发布救援", 409)
    backup_digest = _backup_digest(backup_raw)
    rescue_id = digest({
        "run_id": run_id, "failed_truck": failed_truck,
        "backup_digest": backup_digest, "ruleset": snapshot["manifest"]["ruleset"],
        "moves": [[move["order"], move["lot"], move["to_truck"], move["qty"]] for move in draft["moves"]],
    })
    record = {
        "id": rescue_id, "run_id": run_id, "batch": snapshot["manifest"]["batch"],
        "ruleset": snapshot["manifest"]["ruleset"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **draft,
    }
    saved, reused = ledger.save_rescue(run_id, failed_truck, rescue_id, record, backup_digest)
    return {**saved, "reused": reused}


def history(ledger, run_id):
    _snapshot(ledger, run_id)
    return {"run_id": run_id, "rescues": ledger.rescues_for_run(run_id)}


def read(ledger, run_id, failed_truck):
    _snapshot(ledger, run_id)
    return ledger.rescue(run_id, failed_truck)
