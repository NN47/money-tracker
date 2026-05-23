import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "data/finance.db"))


def _ensure_db_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                participant_id INTEGER,
                type TEXT,
                amount REAL,
                category TEXT,
                comment TEXT,
                created_at TEXT,
                FOREIGN KEY (participant_id) REFERENCES participants(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY,
                participant_id INTEGER,
                title TEXT,
                amount REAL,
                due_date TEXT,
                is_paid INTEGER DEFAULT 0,
                FOREIGN KEY (participant_id) REFERENCES participants(id)
            )
            """
        )


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")
