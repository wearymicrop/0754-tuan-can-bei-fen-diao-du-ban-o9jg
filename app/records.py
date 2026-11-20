from collections import Counter, defaultdict


def entry(table, line, row):
    return {"table": table, "line": line, "raw": row}


def issue(source, code, detail):
    return {**source, "code": code, "detail": detail}


def report(rows, issues, **extra):
    return {"rows": rows, "issues": issues,
            "reasons": dict(sorted(Counter(item["code"] for item in issues).items())), **extra}


def group_by(rows, *keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return groups


def integer(value, minimum=0, maximum=10**9):
    return type(value) is int and minimum <= value <= maximum


def token(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 100
