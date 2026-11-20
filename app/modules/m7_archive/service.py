from time import perf_counter_ns

from app.codec import digest
from app.errors import DomainError
from app.pipeline import evaluate
from app.records import token
from .manifest import create


def execute(ledger, source):
    start = perf_counter_ns()
    result = evaluate(source)
    manifest = create(source, result, (perf_counter_ns() - start) // 1_000_000)
    snapshot = {"id": manifest["id"], "manifest": manifest, "result": result}
    saved, reused = ledger.save(manifest["id"], source, snapshot)
    if saved["manifest"]["digest"] != manifest["digest"]:
        raise DomainError("REPLAY_MISMATCH", "重算摘要不一致，请复核规则版本", 409)
    return {**saved, "reused": reused}


def rerun(ledger, ident):
    source, previous = ledger.read(ident)
    result = evaluate(source)
    if digest(result) != previous["manifest"]["digest"]:
        raise DomainError("REPLAY_MISMATCH", "重跑结果与归档不一致", 409)
    return {**previous, "reused": True}


def sign(ledger, ident, body):
    _, previous = ledger.read(ident)
    if not token(body.get("reviewer")):
        raise DomainError("REVIEWER_REQUIRED", "请输入签收人")
    if previous["manifest"]["digest"] != body.get("digest"):
        raise DomainError("STALE_DIGEST", "摘要已变化，请重新打开凭证", 409)
    receipt = {"reviewer": body["reviewer"].strip(), "digest": body["digest"],
               "id": ident, "balance": previous["result"]["reconcile"]["status"]}
    return ledger.sign(ident, receipt)
