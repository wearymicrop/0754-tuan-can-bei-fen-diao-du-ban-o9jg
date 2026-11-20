import json

from .clock import instant
from .codec import canonical
from .config import MAX_ROWS, ROOT, SAMPLES
from .errors import DomainError
from .records import entry, token


def validate(document, tables):
    if not isinstance(document, dict) or set(document) != {"batch", "at", *tables}:
        raise DomainError("BAD_SCHEMA", "批次字段错误，请对照样例")
    if not token(document["batch"]):
        raise DomainError("BAD_BATCH", "请输入批次号")
    try:
        instant(document["at"])
        encoded = canonical(document).encode("utf-8")
    except (ValueError, RecursionError) as error:
        raise DomainError("BAD_VALUE", "请检查日期和数据格式") from error
    if len(encoded) > 3_000_000:
        raise DomainError("SOURCE_LIMIT", "批次超过三兆字节", 413)
    for name in tables:
        rows = document[name]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise DomainError("BAD_TABLE", f"{name} 必须为记录数组")
        if len(rows) > MAX_ROWS:
            raise DomainError("ROW_LIMIT", f"{name} 超过行数上限", 413)
    return document


def load_sample(name):
    if name not in SAMPLES:
        raise DomainError("UNKNOWN_SAMPLE", "找不到指定样例", 404)
    return json.loads((ROOT / "sample_data" / f"{name}.json").read_text(encoding="utf-8-sig"))


def choose(body):
    if set(body) == {"sample"} and isinstance(body["sample"], str):
        return load_sample(body["sample"])
    if set(body) == {"source"}:
        return body["source"]
    raise DomainError("CHOOSE_SOURCE", "请选择样例或上传一份批次")


def lines(document, table):
    return (entry(table, number, row) for number, row in enumerate(document[table], 1))
