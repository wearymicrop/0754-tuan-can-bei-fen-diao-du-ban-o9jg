from contextlib import contextmanager
import json
import sqlite3

from .codec import canonical
from .errors import DomainError


class Ledger:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, source TEXT NOT NULL, snapshot TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS signatures (
                    run_id TEXT PRIMARY KEY REFERENCES runs(id), receipt TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rescues (
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    failed_truck TEXT NOT NULL,
                    rescue_id TEXT NOT NULL,
                    record TEXT NOT NULL,
                    backup_digest TEXT,
                    PRIMARY KEY (run_id, failed_truck)
                );
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, ident, source, snapshot):
        with self.connect() as connection:
            inserted = connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?) ON CONFLICT(id) DO NOTHING",
                (ident, canonical(source), canonical(snapshot)),
            )
            row = connection.execute("SELECT snapshot FROM runs WHERE id = ?", (ident,)).fetchone()
            return json.loads(row[0]), inserted.rowcount == 0

    def read(self, ident):
        with self.connect() as connection:
            row = connection.execute("SELECT source, snapshot FROM runs WHERE id = ?", (ident,)).fetchone()
            if row is None:
                raise DomainError("RUN_NOT_FOUND", "找不到此运行", 404)
            sign = connection.execute("SELECT receipt FROM signatures WHERE run_id = ?", (ident,)).fetchone()
            snapshot = json.loads(row[1])
            return json.loads(row[0]), {**snapshot, "signature": json.loads(sign[0]) if sign else None}

    def recent(self):
        with self.connect() as connection:
            rows = connection.execute("SELECT snapshot FROM runs ORDER BY rowid DESC LIMIT 30").fetchall()
            return [json.loads(row[0])["manifest"] for row in rows]

    def sign(self, ident, receipt):
        data = canonical(receipt)
        with self.connect() as connection:
            inserted = connection.execute(
                "INSERT INTO signatures VALUES (?, ?) ON CONFLICT(run_id) DO NOTHING", (ident, data))
            saved = connection.execute("SELECT receipt FROM signatures WHERE run_id = ?", (ident,)).fetchone()[0]
            if saved != data:
                raise DomainError("ALREADY_SIGNED", "此运行已由他人签收", 409)
            return {**json.loads(saved), "reused": inserted.rowcount == 0}

    def save_rescue(self, run_id, failed_truck, rescue_id, record, backup_digest):
        """同一运行同一故障车只允许一条救援；重试返回原记录，请求漂移则冲突。"""
        import time
        for attempt in range(20):
            with self.connect() as connection:
                row = connection.execute(
                    "SELECT rescue_id, record, backup_digest FROM rescues WHERE run_id = ? AND failed_truck = ?",
                    (run_id, failed_truck)).fetchone()
                if row is not None:
                    if row[0] != rescue_id or row[2] != backup_digest:
                        raise DomainError("RESCUE_TAKEN", "该故障车已发布救援，不能重复占位或重复耗餐", 409)
                    return json.loads(row[1]), True
                try:
                    connection.execute(
                        "INSERT INTO rescues VALUES (?, ?, ?, ?, ?)",
                        (run_id, failed_truck, rescue_id, canonical(record), backup_digest))
                    return record, False
                except sqlite3.IntegrityError:
                    # 并发救援同时插入同一主键：退避后重读，由下一轮按幂等规则裁决。
                    time.sleep(0.02 * (attempt + 1))
        raise DomainError("RESCUE_BUSY", "救援并发冲突，请稍后重试", 409)

    def rescues_for_run(self, run_id):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT record FROM rescues WHERE run_id = ? ORDER BY rowid", (run_id,)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def rescue(self, run_id, failed_truck):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT record FROM rescues WHERE run_id = ? AND failed_truck = ?",
                (run_id, failed_truck)).fetchone()
            if row is None:
                raise DomainError("RESCUE_NOT_FOUND", "找不到该故障车的救援记录", 404)
            return json.loads(row[0])
