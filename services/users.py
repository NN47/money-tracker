from database import dict_cursor, get_connection
from services.currencies import DEFAULT_CURRENCY, SUPPORTED_CURRENCIES


def normalize_currency(currency: str | None) -> str:
    value = (currency or DEFAULT_CURRENCY).upper()
    return value if value in SUPPORTED_CURRENCIES else DEFAULT_CURRENCY


def get_or_create_user(telegram_id: int | None) -> dict:
    if telegram_id is None:
        return {"telegram_id": None, "default_currency": DEFAULT_CURRENCY}
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            INSERT INTO users(telegram_id, default_currency)
            VALUES(%s, %s)
            ON CONFLICT (telegram_id) DO UPDATE SET telegram_id = EXCLUDED.telegram_id
            RETURNING telegram_id, default_currency
            """,
            (telegram_id, DEFAULT_CURRENCY),
        )
        row = cur.fetchone()
        cur.close()
    return row


def get_user_default_currency(telegram_id: int | None) -> str:
    return normalize_currency(get_or_create_user(telegram_id).get("default_currency"))


def set_user_default_currency(telegram_id: int | None, currency: str) -> str:
    normalized = normalize_currency(currency)
    if telegram_id is None:
        return normalized
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users(telegram_id, default_currency)
            VALUES(%s, %s)
            ON CONFLICT (telegram_id) DO UPDATE SET default_currency = EXCLUDED.default_currency
            """,
            (telegram_id, normalized),
        )
        cur.close()
    return normalized
