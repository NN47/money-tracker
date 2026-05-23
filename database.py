import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras


def _get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL не найден. Укажите его в .env")
    return database_url


@contextmanager
def get_connection():
    conn = psycopg2.connect(_get_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS participants (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    participant_id INTEGER REFERENCES participants(id) ON DELETE CASCADE,
                    type TEXT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    category TEXT,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    participant_id INTEGER REFERENCES participants(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    due_date DATE NOT NULL,
                    is_paid BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        finally:
            cur.close()


def dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
