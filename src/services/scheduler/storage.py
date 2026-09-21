"""
scheduler/storage.py
====================
Persistence layer for the Jaldhrishti reminder system.

Tables
------
loan_schedules      -- one row per quarterly instalment per user
reminder_log        -- tracks which quarters have already been notified
uploaded_documents  -- stores Telegram file_ids (no further processing)

The DB path comes from src.config.settings: explicit environment override,
existing legacy database, then data/output/jaldhrishti.db for new checkouts.
"""

from contextlib import contextmanager
import json
import sqlite3
from datetime import date
from pathlib import Path


def _add_months(d: date, months: int) -> date:
    """Add `months` calendar months to `d`, clamping the day if needed
    (e.g. Jan 31 + 1 month -> Feb 28/29)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    days_in_month = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(d.day, days_in_month[month - 1])
    return date(year, month, day)

from src.config.settings import database_path

DB_PATH: str = database_path()


def _connect() -> sqlite3.Connection:
    """Return a connection with dict-like row_factory."""
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _transaction():
    """Commit/rollback and always close the connection (including on Windows)."""
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


_DDL = """
CREATE TABLE IF NOT EXISTS loan_schedules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id             INTEGER NOT NULL,
    quarter             INTEGER NOT NULL,
    emi                 REAL    NOT NULL,
    due_date            TEXT    NOT NULL,
    start_date          TEXT    NOT NULL,
    financial_plan_json TEXT    NOT NULL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (chat_id, quarter)
);
CREATE TABLE IF NOT EXISTS reminder_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    quarter     INTEGER NOT NULL,
    reminded_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (chat_id, quarter)
);
CREATE TABLE IF NOT EXISTS uploaded_documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    file_id     TEXT    NOT NULL,
    uploaded_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db() -> None:
    """Create all required tables if they do not already exist. Idempotent."""
    with _transaction() as conn:
        conn.executescript(_DDL)


def save_user_loan(chat_id: int, financial_plan: dict, start_date: str) -> None:
    """
    Persist a loan repayment schedule.

    Parameters
    ----------
    chat_id        : Telegram chat / user ID.
    financial_plan : Dict (or JSON string) from the financial engine. Must
                     contain ``repayment_schedule`` -- a list of dicts, each
                     with ``quarter`` (int) and ``emi`` (float). A
                     ``due_date`` (YYYY-MM-DD) per item is optional — the
                     financial engine only outputs quarter numbers, not
                     calendar dates, so if it's missing we compute it here
                     as start_date + quarter*3 months.
    start_date     : ISO-8601 loan origination date, e.g. "2026-01-01".

    Each quarter becomes one row in loan_schedules.
    On conflict (chat_id, quarter) the row is updated in-place (idempotent).
    """
    if isinstance(financial_plan, str):
        financial_plan = json.loads(financial_plan)
    schedule = financial_plan.get("repayment_schedule", [])
    if not schedule:
        raise ValueError("financial_plan must contain a non-empty repayment_schedule list.")

    origin = date.fromisoformat(start_date)
    plan_json = json.dumps(financial_plan, ensure_ascii=False)
    rows = [
        (chat_id, int(item["quarter"]), float(item["emi"]),
         item.get("due_date") or _add_months(origin, int(item["quarter"]) * 3).isoformat(),
         start_date, plan_json)
        for item in schedule
    ]
    sql = """INSERT INTO loan_schedules
                 (chat_id, quarter, emi, due_date, start_date, financial_plan_json)
             VALUES (?, ?, ?, ?, ?, ?)
             ON CONFLICT(chat_id, quarter) DO UPDATE SET
                 emi=excluded.emi,
                 due_date=excluded.due_date,
                 start_date=excluded.start_date,
                 financial_plan_json=excluded.financial_plan_json,
                 created_at=datetime('now')"""
    with _transaction() as conn:
        conn.executemany(sql, rows)


def get_due_today() -> list:
    """
    Return every instalment due TODAY that has NOT yet been reminded.

    Returns
    -------
    list[dict]
        [{"chat_id": int, "quarter": int, "emi": float, "due_date": str}, ...]
    """
    today = date.today().isoformat()
    sql = """SELECT ls.chat_id, ls.quarter, ls.emi, ls.due_date
             FROM loan_schedules ls
             WHERE ls.due_date = ?
               AND NOT EXISTS (
                   SELECT 1 FROM reminder_log rl
                   WHERE rl.chat_id = ls.chat_id AND rl.quarter = ls.quarter
               )
             ORDER BY ls.chat_id, ls.quarter"""
    with _transaction() as conn:
        rows = conn.execute(sql, (today,)).fetchall()
    return [dict(row) for row in rows]


def mark_reminded(chat_id: int, quarter: int) -> None:
    """Record that the reminder for `quarter` was sent to `chat_id`. Idempotent."""
    with _transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO reminder_log (chat_id, quarter) VALUES (?, ?)",
            (chat_id, quarter),
        )


def save_uploaded_document(chat_id: int, file_id: str) -> None:
    """Store a Telegram file_id uploaded by the user. No further processing."""
    with _transaction() as conn:
        conn.execute(
            "INSERT INTO uploaded_documents (chat_id, file_id) VALUES (?, ?)",
            (chat_id, file_id),
        )
