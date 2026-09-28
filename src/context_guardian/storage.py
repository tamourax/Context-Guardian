"""SQLite persistence, migrations, and append-only journal."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .protocol import GuardianError, canonical_json, new_id, sha256_text, utc_now

SCHEMA_VERSION = 1
DB_RELATIVE_PATH = Path(".context-guardian") / "guardian.sqlite3"


class Store:
    def __init__(self, project_root: Path, *, create: bool = False) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.data_dir = self.project_root / ".context-guardian"
        self.db_path = self.data_dir / "guardian.sqlite3"
        if create:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists() and not create:
            raise GuardianError("NOT_INITIALIZED", f"Context Guardian is not initialized in {self.project_root}.")
        self.conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.execute("PRAGMA synchronous = FULL")
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @contextmanager
    def atomic(self) -> Iterator[None]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

    def _migrate(self) -> None:
        version = int(self.conn.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise GuardianError("SCHEMA_VERSION_UNSUPPORTED", f"Database schema {version} is newer than supported schema {SCHEMA_VERSION}.")
        if version == 0:
            self.conn.execute("PRAGMA journal_mode = WAL")
            with self.atomic():
                self.conn.executescript(
                    """
                    CREATE TABLE metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE tasks (
                        task_id TEXT PRIMARY KEY,
                        objective TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    );
                    CREATE TABLE context_items (
                        item_id TEXT PRIMARY KEY,
                        task_id TEXT,
                        type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        protection TEXT NOT NULL,
                        lifecycle TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                    );
                    CREATE INDEX context_items_task_lifecycle ON context_items(task_id, lifecycle);
                    CREATE INDEX context_items_type ON context_items(type);
                    CREATE TABLE checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        task_id TEXT,
                        parent_checkpoint_id TEXT,
                        created_at TEXT NOT NULL,
                        policy_version TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                    );
                    CREATE INDEX checkpoints_task_created ON checkpoints(task_id, created_at);
                    CREATE TABLE events (
                        event_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        source TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    );
                    CREATE INDEX events_name_time ON events(name, occurred_at);
                    CREATE TABLE transactions (
                        transaction_id TEXT PRIMARY KEY,
                        request_id TEXT NOT NULL UNIQUE,
                        operation TEXT NOT NULL,
                        state TEXT NOT NULL,
                        plan_json TEXT NOT NULL,
                        snapshot_json TEXT,
                        result_json TEXT,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        rolled_back_by TEXT
                    );
                    CREATE TABLE requests (
                        request_id TEXT PRIMARY KEY,
                        command TEXT NOT NULL,
                        request_hash TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE journal (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id TEXT,
                        event TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        detail_json TEXT NOT NULL,
                        previous_hash TEXT NOT NULL,
                        entry_hash TEXT NOT NULL
                    );
                    CREATE TRIGGER journal_append_only_update
                    BEFORE UPDATE ON journal BEGIN SELECT RAISE(ABORT, 'journal is append-only'); END;
                    CREATE TRIGGER journal_append_only_delete
                    BEFORE DELETE ON journal BEGIN SELECT RAISE(ABORT, 'journal is append-only'); END;
                    """
                )
                self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                self.set_meta("project_id", new_id("prj"))
                self.set_meta("project_root", str(self.project_root))
                self.set_meta("created_at", utc_now())
                self.set_meta("policy_version", "v1.0")
                self.set_meta("mode", "observe")
                self.append_journal(None, "project.initialized", {"project_id": self.get_meta("project_id")})
        elif version != SCHEMA_VERSION:
            raise GuardianError("SCHEMA_VERSION_UNSUPPORTED", f"No migration path from schema {version}.")

    @staticmethod
    def _dump(value: Any) -> str:
        return canonical_json(value)

    @staticmethod
    def _load(value: str | None, default: Any = None) -> Any:
        return json.loads(value) if value is not None else default

    def set_meta(self, key: str, value: Any) -> None:
        self.conn.execute(
            "INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, self._dump(value)),
        )

    def get_meta(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return self._load(row[0], default) if row else default

    def save_task(self, task: dict[str, Any]) -> None:
        self.conn.execute(
            """INSERT INTO tasks(task_id,objective,status,created_at,updated_at,payload_json)
               VALUES(?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET
               objective=excluded.objective,status=excluded.status,updated_at=excluded.updated_at,payload_json=excluded.payload_json""",
            (task["task_id"], task["objective"], task["status"], task["created_at"], task["updated_at"], self._dump(task)),
        )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT payload_json FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return self._load(row[0]) if row else None

    def list_tasks(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute("SELECT payload_json FROM tasks WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()
        else:
            rows = self.conn.execute("SELECT payload_json FROM tasks ORDER BY updated_at DESC").fetchall()
        return [self._load(row[0]) for row in rows]

    def save_item(self, item: dict[str, Any]) -> None:
        self.conn.execute(
            """INSERT INTO context_items(item_id,task_id,type,content,protection,lifecycle,created_at,payload_json)
               VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(item_id) DO UPDATE SET
               task_id=excluded.task_id,type=excluded.type,content=excluded.content,
               protection=excluded.protection,lifecycle=excluded.lifecycle,
               created_at=excluded.created_at,payload_json=excluded.payload_json""",
            (item["item_id"], item.get("task_id"), item["type"], item["content"], item["protection"],
             item["lifecycle"], item["created_at"], self._dump(item)),
        )

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT payload_json FROM context_items WHERE item_id=?", (item_id,)).fetchone()
        return self._load(row[0]) if row else None

    def list_items(self, *, task_id: str | None = None, include_archived: bool = False) -> list[dict[str, Any]]:
        clauses: list[str] = []
        args: list[Any] = []
        if task_id is not None:
            clauses.append("task_id=?")
            args.append(task_id)
        if not include_archived:
            clauses.append("lifecycle!='ARCHIVED'")
        query = "SELECT payload_json FROM context_items"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at,item_id"
        return [self._load(row[0]) for row in self.conn.execute(query, args).fetchall()]

    def save_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        self.conn.execute(
            """INSERT INTO checkpoints(checkpoint_id,task_id,parent_checkpoint_id,created_at,policy_version,payload_json)
               VALUES(?,?,?,?,?,?)""",
            (checkpoint["checkpoint_id"], checkpoint.get("task_id"), checkpoint.get("parent_checkpoint_id"),
             checkpoint["created_at"], checkpoint.get("policy_version", "v1.0"), self._dump(checkpoint)),
        )

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT payload_json FROM checkpoints WHERE checkpoint_id=?", (checkpoint_id,)).fetchone()
        return self._load(row[0]) if row else None

    def list_checkpoints(self, *, task_id: str | None = None) -> list[dict[str, Any]]:
        if task_id:
            rows = self.conn.execute("SELECT payload_json FROM checkpoints WHERE task_id=? ORDER BY created_at DESC", (task_id,)).fetchall()
        else:
            rows = self.conn.execute("SELECT payload_json FROM checkpoints ORDER BY created_at DESC").fetchall()
        return [self._load(row[0]) for row in rows]

    def save_event(self, name: str, source: str, payload: dict[str, Any], *, event_id: str | None = None, occurred_at: str | None = None) -> str:
        event_id = event_id or new_id("evt")
        occurred_at = occurred_at or utc_now()
        self.conn.execute(
            "INSERT INTO events(event_id,name,occurred_at,source,payload_json) VALUES(?,?,?,?,?)",
            (event_id, name, occurred_at, source, self._dump(payload)),
        )
        self.append_journal(None, "event.recorded", {"event_id": event_id, "name": name, "source": source})
        return event_id

    def list_events(self, *, name: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if name:
            rows = self.conn.execute("SELECT * FROM events WHERE name=? ORDER BY occurred_at DESC LIMIT ?", (name, limit)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM events ORDER BY occurred_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"event_id": row["event_id"], "name": row["name"], "occurred_at": row["occurred_at"],
                 "source": row["source"], "payload": self._load(row["payload_json"])} for row in rows]

    def save_transaction(self, transaction: dict[str, Any]) -> None:
        self.conn.execute(
            """INSERT INTO transactions(transaction_id,request_id,operation,state,plan_json,snapshot_json,result_json,
               created_at,expires_at,updated_at,rolled_back_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(transaction_id) DO UPDATE SET state=excluded.state,snapshot_json=excluded.snapshot_json,
               result_json=excluded.result_json,updated_at=excluded.updated_at,rolled_back_by=excluded.rolled_back_by""",
            (transaction["transaction_id"], transaction["request_id"], transaction["operation"], transaction["state"],
             self._dump(transaction["plan"]), self._dump(transaction.get("snapshot")) if transaction.get("snapshot") is not None else None,
             self._dump(transaction.get("result")) if transaction.get("result") is not None else None,
             transaction["created_at"], transaction["expires_at"], transaction["updated_at"], transaction.get("rolled_back_by")),
        )

    def get_transaction(self, transaction_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM transactions WHERE transaction_id=?", (transaction_id,)).fetchone()
        return self._transaction_row(row) if row else None

    def get_transaction_by_request(self, request_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM transactions WHERE request_id=?", (request_id,)).fetchone()
        return self._transaction_row(row) if row else None

    def _transaction_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "transaction_id": row["transaction_id"], "request_id": row["request_id"],
            "operation": row["operation"], "state": row["state"], "plan": self._load(row["plan_json"]),
            "snapshot": self._load(row["snapshot_json"]), "result": self._load(row["result_json"]),
            "created_at": row["created_at"], "expires_at": row["expires_at"],
            "updated_at": row["updated_at"], "rolled_back_by": row["rolled_back_by"],
        }

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT command,request_hash,result_json,created_at FROM requests WHERE request_id=?", (request_id,)).fetchone()
        if not row:
            return None
        return {"request_id": request_id, "command": row["command"], "request_hash": row["request_hash"],
                "result": self._load(row["result_json"]), "created_at": row["created_at"]}

    def remember_request(self, request_id: str, command: str, result: dict[str, Any], request_payload: Any) -> None:
        request_hash = sha256_text(self._dump({"command": command, "payload": request_payload}))
        self.conn.execute(
            "INSERT INTO requests(request_id,command,request_hash,result_json,created_at) VALUES(?,?,?,?,?)",
            (request_id, command, request_hash, self._dump(result), utc_now()),
        )

    def append_journal(self, transaction_id: str | None, event: str, detail: dict[str, Any]) -> str:
        row = self.conn.execute("SELECT entry_hash FROM journal ORDER BY sequence DESC LIMIT 1").fetchone()
        previous_hash = row[0] if row else "0" * 64
        occurred_at = utc_now()
        detail_json = self._dump(detail)
        entry_hash = sha256_text(self._dump({
            "transaction_id": transaction_id,
            "event": event,
            "occurred_at": occurred_at,
            "detail_json": detail_json,
            "previous_hash": previous_hash,
        }))
        self.conn.execute(
            "INSERT INTO journal(transaction_id,event,occurred_at,detail_json,previous_hash,entry_hash) VALUES(?,?,?,?,?,?)",
            (transaction_id, event, occurred_at, detail_json, previous_hash, entry_hash),
        )
        return entry_hash

    def verify_journal(self) -> dict[str, Any]:
        rows = self.conn.execute("SELECT * FROM journal ORDER BY sequence").fetchall()
        previous = "0" * 64
        for row in rows:
            expected = sha256_text(self._dump({
                "transaction_id": row["transaction_id"],
                "event": row["event"],
                "occurred_at": row["occurred_at"],
                "detail_json": row["detail_json"],
                "previous_hash": previous,
            }))
            if row["previous_hash"] != previous or row["entry_hash"] != expected:
                return {"status": "fail", "checked_entries": row["sequence"] - 1, "corrupt_sequence": row["sequence"]}
            previous = row["entry_hash"]
        return {"status": "pass", "checked_entries": len(rows), "head_hash": previous}

    def journal_entries(self, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM journal ORDER BY sequence DESC LIMIT ?", (limit,)).fetchall()
        return [{"sequence": row["sequence"], "transaction_id": row["transaction_id"], "event": row["event"],
                 "occurred_at": row["occurred_at"], "detail": self._load(row["detail_json"]),
                 "previous_hash": row["previous_hash"], "entry_hash": row["entry_hash"]} for row in rows]
