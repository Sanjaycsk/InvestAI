"""
SQLite state + audit store.

This is the hand-off point between the two processes:
  * the analysis job WRITES pending recommendations here, then sends the summary
  * the bot service READS a recommendation by id when you press a button, and
    UPDATES its status as it moves through approve -> simulate/execute.

Every meaningful event also lands in an append-only `audit_log` — essential for
a system that can move money. Uses the stdlib `sqlite3` (no extra dependency).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from config import config
from src.analysis.schema import Recommendation, RecStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    ticker            TEXT NOT NULL,
    payload           TEXT NOT NULL,      -- full JSON of the Recommendation
    status            TEXT NOT NULL,
    approval_token    TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    expires_at        TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    event     TEXT NOT NULL,              -- e.g. CREATED, APPROVED, SIMULATED
    ref_id    TEXT,                       -- recommendation_id, if any
    detail    TEXT
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- audit -----------------------------------------------------------
def log_event(event: str, ref_id: Optional[str] = None, detail: str = "") -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO audit_log (ts, event, ref_id, detail) VALUES (?,?,?,?)",
            (_now(), event, ref_id, detail),
        )


# ---- recommendations -------------------------------------------------
def save_recommendation(rec: Recommendation) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO recommendations
               (recommendation_id, ticker, payload, status, approval_token,
                created_at, expires_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                rec.recommendation_id,
                rec.ticker,
                rec.model_dump_json(),
                rec.status.value,
                rec.approval_token,
                rec.created_at.isoformat(),
                rec.expires_at.isoformat() if rec.expires_at else None,
            ),
        )
    log_event("CREATED", rec.recommendation_id,
              f"{rec.ticker} {rec.recommended_action.value} {rec.flag.value}")


def get_recommendation(rec_id: str) -> Optional[Recommendation]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload FROM recommendations WHERE recommendation_id = ?",
            (rec_id,),
        ).fetchone()
    if row is None:
        return None
    return Recommendation.model_validate(json.loads(row["payload"]))


def update_status(rec_id: str, status: RecStatus, detail: str = "") -> None:
    with _connect() as conn:
        # Update both the column and the embedded JSON so the two never drift.
        row = conn.execute(
            "SELECT payload FROM recommendations WHERE recommendation_id = ?",
            (rec_id,),
        ).fetchone()
        if row is None:
            return
        rec = Recommendation.model_validate(json.loads(row["payload"]))
        rec.status = status
        conn.execute(
            "UPDATE recommendations SET status = ?, payload = ? WHERE recommendation_id = ?",
            (status.value, rec.model_dump_json(), rec_id),
        )
    log_event(status.value, rec_id, detail)


def count_executions_today() -> int:
    """Real + simulated executions since UTC midnight — feeds the daily cap."""
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log "
            "WHERE event IN ('EXECUTED','SIMULATED') AND ts >= ?",
            (start,),
        ).fetchone()
    return int(row["n"]) if row else 0


def count_stop_losses_today() -> int:
    """Stop-losses fired since UTC midnight — feeds the daily circuit breaker."""
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log "
            "WHERE event = 'STOPPED_OUT' AND ts >= ?",
            (start,),
        ).fetchone()
    return int(row["n"]) if row else 0
