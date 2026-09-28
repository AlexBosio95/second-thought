import json
import sqlite3
from pathlib import Path
from typing import Any

class AuditStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS audit (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, record TEXT NOT NULL)")

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def save(self, record: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO audit VALUES (?, ?, ?)",
                       (record["id"], record["timestamp"], json.dumps(record, allow_nan=False)))

    def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT record FROM audit ORDER BY timestamp DESC LIMIT ? OFFSET ?", (limit, offset))
            return [json.loads(row[0]) for row in rows]

    def get(self, audit_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT record FROM audit WHERE id = ?", (audit_id,)).fetchone()
            return json.loads(row[0]) if row else None
