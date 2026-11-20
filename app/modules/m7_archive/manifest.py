from datetime import datetime, timezone

from app.codec import digest
from app.config import RULESET


def create(source, result, elapsed_ms):
    source_sha256 = digest(source)
    run_id = digest({"source_sha256": source_sha256, "ruleset": RULESET})
    return {"id": run_id, "batch": source["batch"], "at": source["at"],
            "ruleset": RULESET, "source_sha256": source_sha256, "digest": digest(result),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "elapsed_ms": elapsed_ms, "parameters": {"as_of": source["at"]},
            "input_counts": {key: len(value) for key, value in source.items() if isinstance(value, list)}}
