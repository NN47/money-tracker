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
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    type TEXT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    category TEXT,
                    comment TEXT,
                    operation_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_payments (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    payment_date DATE NOT NULL,
                    is_paid BOOLEAN DEFAULT FALSE,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS recurring_operations (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    category TEXT,
                    day_of_month INTEGER,
                    frequency TEXT NOT NULL DEFAULT 'monthly',
                    is_active BOOLEAN DEFAULT TRUE,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        finally:
            cur.close()


def dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
