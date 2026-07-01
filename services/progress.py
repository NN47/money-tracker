from calendar import monthrange
from datetime import date

from database import dict_cursor, get_connection
from services.recurring_payments import moscow_today
from services.reports import month_bounds, _format_totals, _subtract_totals
from services.texts import PROGRESS_TEXTS

MOTIVATION_EVERY = 3


def month_summary(person_id: int | None = None):
    today = moscow_today()
    start, nxt = month_bounds(today)
    if person_id is not None:
        person_sql = " AND person_id = %s"
        params = [start, nxt, person_id]
    else:
        person_sql = " AND (person_id IS NULL OR EXISTS (SELECT 1 FROM persons p WHERE p.id = transactions.person_id AND p.include_in_budget = TRUE))"
        params = [start, nxt]
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT type, COALESCE(currency,'RUB') currency, COALESCE(SUM(amount),0) total, COUNT(*) count
            FROM transactions
            WHERE operation_date >= %s AND operation_date < %s
            """
            + person_sql
            + " GROUP BY type, COALESCE(currency,'RUB')",
            params,
        )
        rows = cur.fetchall()
        cur.close()
    income, expense, count = {}, {}, 0
    for row in rows:
        target = income if row["type"] == "income" else expense
        target[row["currency"]] = float(row["total"] or 0)
        count += int(row["count"] or 0)
    return income, expense, _subtract_totals(income, expense), count


def build_month_summary(person_id: int | None = None) -> str:
    income, expense, balance, _count = month_summary(person_id)
    t = PROGRESS_TEXTS
    return "\n".join(
        [
            t["month_summary_title"],
            t["month_summary_income"].format(income=_format_totals(income)),
            t["month_summary_expense"].format(expense=_format_totals(expense)),
            t["month_summary_balance"].format(balance=_format_totals(balance)),
        ]
    )


def _unlock_once(user_id: int | None, key: str) -> bool:
    if user_id is None:
        return False
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user_achievements(user_id, achievement_key) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (user_id, key),
        )
        unlocked = cur.rowcount > 0
        cur.close()
    return unlocked


def total_operations() -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM transactions")
        count = int(cur.fetchone()[0])
        cur.close()
    return count


def progress_after_operation(user_id: int | None, person_id: int | None = None) -> str:
    _income, _expense, _balance, month_count = month_summary(person_id)
    total_count = total_operations()
    t = PROGRESS_TEXTS
    lines = [build_month_summary(person_id)]
    achievements = []
    achievement_rules = [
        ("first_operation", total_count >= 1),
        ("100_operations", total_count >= 100),
    ]
    for key, condition in achievement_rules:
        if condition and _unlock_once(user_id, key):
            achievements.append(t[f"achievement_{key}"])
    if achievements:
        lines.extend(["", *achievements])
    if month_count and month_count % MOTIVATION_EVERY == 0:
        lines.extend(["", t["motivation_operations"].format(count=month_count)])
    elif total_count % 5 == 0:
        lines.extend(["", t["motivation_accuracy"]])
    return "\n".join(lines)


def _paid_payment_dates(row) -> set[date]:
    return {payment_date for payment_date in row.get("paid_payment_dates") or [] if payment_date}


def _next_recurring_candidate(row, today: date) -> dict | None:
    day = row.get("day_of_month")
    if not day:
        return None
    paid_payment_dates = _paid_payment_dates(row)
    year, month = today.year, today.month
    for _ in range(24):
        days_in_month = monthrange(year, month)[1]
        if day <= days_in_month:
            candidate = date(year, month, day)
            if candidate >= today and candidate not in paid_payment_dates:
                item = dict(row)
                item["payment_date"] = candidate
                item.pop("paid_payment_dates", None)
                return item
        month = 1 if month == 12 else month + 1
        year += 1 if month == 1 else 0
    return None


def fetch_next_payment():
    today = moscow_today()
    horizon = today.replace(year=today.year + 2)
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT id, title, amount, payment_date
            FROM scheduled_payments
            WHERE is_paid=FALSE AND payment_date >= %s
            ORDER BY payment_date, id
            LIMIT 1
            """,
            (today,),
        )
        scheduled = cur.fetchone()
        cur.execute(
            """
            SELECT
                ro.id,
                ro.title,
                ro.amount,
                ro.day_of_month,
                COALESCE(
                    array_agg(l.payment_date ORDER BY l.payment_date)
                        FILTER (WHERE l.payment_date IS NOT NULL),
                    '{}'
                ) AS paid_payment_dates
            FROM recurring_operations ro
            LEFT JOIN recurring_payments_log l
                ON l.recurring_operation_id = ro.id
               AND l.payment_date BETWEEN %s AND %s
            WHERE ro.is_active=TRUE
              AND ro.type IN ('payment','expense')
            GROUP BY ro.id, ro.title, ro.amount, ro.day_of_month
            """,
            (today, horizon),
        )
        recurring = [_next_recurring_candidate(row, today) for row in cur.fetchall()]
        cur.close()
    candidates = [row for row in [scheduled, *recurring] if row and row["payment_date"] <= horizon]
    return sorted(candidates, key=lambda row: (row["payment_date"], row["id"]))[0] if candidates else None


def _days_word(days: int) -> str:
    if 11 <= days % 100 <= 14:
        return "дней"
    if days % 10 == 1:
        return "день"
    if 2 <= days % 10 <= 4:
        return "дня"
    return "дней"


def days_until_next_payment_text() -> str:
    row = fetch_next_payment()
    if not row:
        return "платежей нет"
    days = (row["payment_date"] - moscow_today()).days
    if days <= 1:
        return "завтра"
    return f"через {days} {_days_word(days)}"
