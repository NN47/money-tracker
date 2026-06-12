from __future__ import annotations

from calendar import monthrange
from datetime import date

from database import dict_cursor, get_connection
from services.reports import money

OPERATION_TYPE_LABELS = {
    "income": "доход",
    "expense": "расход",
    "payment": "платёж",
}


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        return start, date(year + 1, 1, 1)
    return start, date(year, month + 1, 1)


def fetch_calendar_marked_days(year: int, month: int) -> set[int]:
    start, end = month_bounds(year, month)
    _, days_in_month = monthrange(year, month)

    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT DISTINCT EXTRACT(DAY FROM payment_date)::int AS day
            FROM scheduled_payments
            WHERE payment_date >= %s
              AND payment_date < %s
            """,
            (start, end),
        )
        scheduled_days = {row["day"] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT DISTINCT EXTRACT(DAY FROM operation_date)::int AS day
            FROM transactions
            WHERE operation_date >= %s
              AND operation_date < %s
            """,
            (start, end),
        )
        transaction_days = {row["day"] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT DISTINCT day_of_month AS day
            FROM recurring_operations
            WHERE is_active = TRUE
              AND day_of_month BETWEEN 1 AND %s
            """,
            (days_in_month,),
        )
        recurring_days = {row["day"] for row in cur.fetchall()}
        cur.close()

    return scheduled_days | transaction_days | recurring_days


def fetch_calendar_day_events(day: date) -> dict[str, list]:
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT id, title, amount, is_paid, comment
            FROM scheduled_payments
            WHERE payment_date = %s
            ORDER BY is_paid, id
            """,
            (day,),
        )
        scheduled = cur.fetchall()

        cur.execute(
            """
            SELECT id, title, type, amount, category, comment
            FROM recurring_operations
            WHERE is_active = TRUE
              AND day_of_month = %s
            ORDER BY id
            """,
            (day.day,),
        )
        recurring = cur.fetchall()

        cur.execute(
            """
            SELECT id, type, amount, category, comment
            FROM transactions
            WHERE operation_date = %s
            ORDER BY id DESC
            """,
            (day,),
        )
        transactions = cur.fetchall()
        cur.close()

    return {
        "scheduled": scheduled,
        "recurring": recurring,
        "transactions": transactions,
    }


def has_calendar_events(events: dict[str, list]) -> bool:
    return any(events.values())


def _append_comment(line: str, comment: str | None) -> str:
    if not comment:
        return line
    return f"{line} — {comment}"


def build_calendar_day_events(day: date, events: dict[str, list]) -> str:
    lines = [f"📅 События на {day.strftime('%d.%m.%Y')}:"]

    if not has_calendar_events(events):
        lines.append("Событий нет.")
        return "\n".join(lines)

    scheduled = events["scheduled"]
    if scheduled:
        lines.extend(["", "🗓 Предстоящие платежи:"])
        for row in scheduled:
            status = "оплачен" if row["is_paid"] else "не оплачен"
            line = f"• {row['title']} — {money(float(row['amount']))} ₽ ({status})"
            lines.append(_append_comment(line, row.get("comment")))

    recurring = events["recurring"]
    if recurring:
        lines.extend(["", "🔁 Регулярные события:"])
        for row in recurring:
            type_text = OPERATION_TYPE_LABELS.get(row["type"], row["type"])
            category = row["category"] or "без категории"
            line = f"• {row['title']} — {money(float(row['amount']))} ₽ ({type_text}, {category})"
            lines.append(_append_comment(line, row.get("comment")))

    transactions = events["transactions"]
    if transactions:
        lines.extend(["", "💸 Операции:"])
        for row in transactions:
            sign = "+" if row["type"] == "income" else "-"
            category = row["category"] or "без категории"
            line = f"• {sign}{money(float(row['amount']))} ₽ — {category}"
            lines.append(_append_comment(line, row.get("comment")))

    return "\n".join(lines)

