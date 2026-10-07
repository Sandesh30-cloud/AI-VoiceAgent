from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_initialized = False


def _connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str) -> None:
    global _initialized
    with _lock:
        conn = _connect(path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calls (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    caller TEXT,
                    reason TEXT,
                    urgency TEXT,
                    callback TEXT,
                    transcript TEXT,
                    duration_seconds REAL,
                    metrics_json TEXT,
                    estimated_cost_usd REAL,
                    ended_reason TEXT,
                    is_spam INTEGER DEFAULT 0,
                    summary_json TEXT
                )
                """
            )
            conn.commit()
            _initialized = True
        finally:
            conn.close()


def save_call(path: str, record: dict[str, Any]) -> None:
    init_db(path)
    payload = {
        "id": record["id"],
        "created_at": record.get("created_at")
        or datetime.now(timezone.utc).isoformat(),
        "caller": record.get("caller"),
        "reason": record.get("reason"),
        "urgency": record.get("urgency"),
        "callback": record.get("callback"),
        "transcript": json.dumps(record.get("transcript") or [], ensure_ascii=False),
        "duration_seconds": record.get("duration_seconds"),
        "metrics_json": json.dumps(record.get("metrics") or {}, ensure_ascii=False),
        "estimated_cost_usd": record.get("estimated_cost_usd"),
        "ended_reason": record.get("ended_reason"),
        "is_spam": 1 if record.get("is_spam") else 0,
        "summary_json": json.dumps(record, ensure_ascii=False, default=str),
    }
    with _lock:
        conn = _connect(path)
        try:
            conn.execute(
                """
                INSERT INTO calls (
                    id, created_at, caller, reason, urgency, callback, transcript,
                    duration_seconds, metrics_json, estimated_cost_usd,
                    ended_reason, is_spam, summary_json
                ) VALUES (
                    :id, :created_at, :caller, :reason, :urgency, :callback, :transcript,
                    :duration_seconds, :metrics_json, :estimated_cost_usd,
                    :ended_reason, :is_spam, :summary_json
                )
                ON CONFLICT(id) DO UPDATE SET
                    caller=excluded.caller,
                    reason=excluded.reason,
                    urgency=excluded.urgency,
                    callback=excluded.callback,
                    transcript=excluded.transcript,
                    duration_seconds=excluded.duration_seconds,
                    metrics_json=excluded.metrics_json,
                    estimated_cost_usd=excluded.estimated_cost_usd,
                    ended_reason=excluded.ended_reason,
                    is_spam=excluded.is_spam,
                    summary_json=excluded.summary_json
                """,
                payload,
            )
            conn.commit()
            logger.info("call_saved", extra={"call_id": record["id"]})
        finally:
            conn.close()


def get_call(path: str, call_id: str) -> dict[str, Any] | None:
    init_db(path)
    conn = _connect(path)
    try:
        row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
