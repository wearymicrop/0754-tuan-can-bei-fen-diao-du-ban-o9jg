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
