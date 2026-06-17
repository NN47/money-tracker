from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from database import dict_cursor, get_connection

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
DEFAULT_PAYMENT_CATEGORY = "Платежи"


def moscow_today() -> date:
    return datetime.now(MOSCOW_TZ).date()


def fetch_all_active_recurring_operations():
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT id, title, type, amount, category, day_of_month, frequency, comment
            FROM recurring_operations
            WHERE is_active = TRUE
            ORDER BY day_of_month NULLS LAST, id
            """
        )
        rows = cur.fetchall()
        cur.close()
    return rows


def fetch_active_recurring_operation(recurring_operation_id: int):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT id, title, type, amount, category, day_of_month, frequency, comment
            FROM recurring_operations
            WHERE id = %s
              AND is_active = TRUE
            """,
            (recurring_operation_id,),
        )
        row = cur.fetchone()
        cur.close()
    return row


def update_recurring_operation(
    recurring_operation_id: int,
    title: str,
    op_type: str,
    amount: float,
    category: str,
    day_of_month: int,
    comment: str | None,
) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE recurring_operations
            SET title = %s,
                type = %s,
                amount = %s,
                category = %s,
                day_of_month = %s,
                comment = %s
            WHERE id = %s
              AND is_active = TRUE
            """,
            (title, op_type, amount, category, day_of_month, comment, recurring_operation_id),
        )
        updated = cur.rowcount > 0
        cur.close()
    return updated


def deactivate_recurring_operation(recurring_operation_id: int):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            UPDATE recurring_operations
            SET is_active = FALSE
            WHERE id = %s
              AND is_active = TRUE
            RETURNING title
            """,
            (recurring_operation_id,),
        )
        row = cur.fetchone()
        cur.close()
    return row


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


def fetch_unpaid_due_recurring_payments(payment_date: date | None = None):
    """Return active recurring payments due on or before the selected date and not yet paid.

    Each returned row contains ``payment_date`` so overdue callback buttons can mark the
    exact missed payment date as paid instead of creating a log for today.
    """
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
                due.payment_date
            FROM recurring_operations ro
            JOIN LATERAL (
                SELECT generated_day::date AS payment_date
                FROM generate_series(ro.created_at::date, %s::date, interval '1 day') AS generated_day
                WHERE EXTRACT(DAY FROM generated_day)::int = ro.day_of_month
            ) due ON TRUE
            LEFT JOIN recurring_payments_log l
                ON l.recurring_operation_id = ro.id
               AND l.payment_date = due.payment_date
            WHERE ro.is_active = TRUE
              AND ro.type IN ('payment', 'expense')
              AND l.id IS NULL
            ORDER BY due.payment_date, ro.id
            """,
            (today,),
        )
        rows = cur.fetchall()
        cur.close()
    return rows


def mark_recurring_payment_paid(recurring_operation_id: int, payment_date: date | None = None) -> dict:
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
            FOR UPDATE
            """,
            (recurring_operation_id,),
        )
        operation = cur.fetchone()
        if not operation:
            cur.close()
            return {"status": "not_found"}

        cur.execute(
            """
            SELECT id
            FROM recurring_payments_log
            WHERE recurring_operation_id = %s
              AND payment_date = %s
            """,
            (recurring_operation_id, today),
        )
        if cur.fetchone():
            cur.close()
            return {"status": "already_paid", "title": operation["title"]}

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
            INSERT INTO recurring_payments_log(recurring_operation_id, payment_date, transaction_id)
            VALUES(%s, %s, %s)
            """,
            (recurring_operation_id, today, transaction_id),
        )
        cur.close()
    return {"status": "paid", "title": operation["title"]}
