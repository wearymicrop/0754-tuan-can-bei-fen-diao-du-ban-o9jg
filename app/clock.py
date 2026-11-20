from datetime import datetime, timezone


def instant(value):
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("时间须带时区偏移")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.microsecond:
        raise ValueError("时间须带时区偏移并精确到秒")
    return int(parsed.timestamp())


def utc(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")
