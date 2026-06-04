from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from database import dict_cursor, get_connection

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
DEFAULT_PAYMENT_CATEGORY = "Платежи"


def moscow_today() -> date:
    return datetime.now(MOSCOW_TZ).date()


def fetch_today_recurring_payments(payment_date: date | None = None):
    today = payment_date or moscow_today()
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT
                ro.id,
                ro.title,
                ro.type,
                ro.amount,
                ro.category,
                ro.day_of_month,
                l.id AS log_id,
                l.transaction_id
            FROM recurring_operations ro
            LEFT JOIN recurring_payments_log l
                ON l.recurring_operation_id = ro.id
               AND l.payment_date = %s
            WHERE ro.is_active = TRUE
              AND ro.type IN ('payment', 'expense')
              AND ro.day_of_month = %s
            ORDER BY ro.id
            """,
            (today, today.day),
        )
        rows = cur.fetchall()
        cur.close()
    return rows


def split_by_payment_status(rows):
    unpaid = [row for row in rows if row["log_id"] is None]
    paid = [row for row in rows if row["log_id"] is not None]
    return unpaid, paid


def fetch_unpaid_today_recurring_payments(payment_date: date | None = None):
    rows = fetch_today_recurring_payments(payment_date)
    unpaid, _ = split_by_payment_status(rows)
    return unpaid


def mark_recurring_payment_paid(recurring_operation_id: int, payment_date: date | None = None) -> str:
    today = payment_date or moscow_today()
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT id, title, amount, category
            FROM recurring_operations
            WHERE id = %s
              AND is_active = TRUE
              AND type IN ('payment', 'expense')
              AND day_of_month = %s
            """,
            (recurring_operation_id, today.day),
        )
        operation = cur.fetchone()
        if not operation:
            cur.close()
            return "not_due"

        cur.execute(
            """
            INSERT INTO recurring_payments_log(recurring_operation_id, payment_date)
            VALUES(%s, %s)
            ON CONFLICT (recurring_operation_id, payment_date) DO NOTHING
            RETURNING id
            """,
            (recurring_operation_id, today),
        )
        log = cur.fetchone()
        if not log:
            cur.close()
            return "already_paid"

        category = operation["category"] or DEFAULT_PAYMENT_CATEGORY
        amount = operation["amount"]
        if isinstance(amount, Decimal):
            amount = str(amount)

        cur.execute(
            """
            INSERT INTO transactions(type, amount, category, comment, operation_date)
            VALUES('expense', %s, %s, %s, %s)
            RETURNING id
            """,
            (amount, category, operation["title"], today),
        )
        transaction_id = cur.fetchone()["id"]
        cur.execute(
            """
            UPDATE recurring_payments_log
            SET transaction_id = %s
            WHERE id = %s
            """,
            (transaction_id, log["id"]),
        )
        cur.close()
    return "paid"
