from calendar import monthrange
from datetime import date

from database import dict_cursor, get_connection
from services.recurring_payments import moscow_today
from services.reports import month_bounds, money_currency, _format_totals, _subtract_totals
from services.texts import PROGRESS_TEXTS

MOTIVATION_EVERY = 3


def ensure_progress_tables() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_progress (
                user_id BIGINT PRIMARY KEY,
                last_entry_date DATE,
                streak_days INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id BIGINT NOT NULL,
                achievement_key TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, achievement_key)
            )
            """
        )
        cur.close()


def record_accounting_day(user_id: int | None) -> int:
    if user_id is None:
        return 0
    ensure_progress_tables()
    today = moscow_today()
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            "SELECT last_entry_date, streak_days FROM user_progress WHERE user_id=%s FOR UPDATE",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            streak = 1
            cur.execute(
                "INSERT INTO user_progress(user_id,last_entry_date,streak_days) VALUES(%s,%s,%s)",
                (user_id, today, streak),
            )
        elif row["last_entry_date"] == today:
            streak = int(row["streak_days"] or 1)
        elif row["last_entry_date"] and (today - row["last_entry_date"]).days == 1:
            streak = int(row["streak_days"] or 0) + 1
            cur.execute(
                "UPDATE user_progress SET last_entry_date=%s, streak_days=%s WHERE user_id=%s",
                (today, streak, user_id),
            )
        else:
            streak = 1
            cur.execute(
                "UPDATE user_progress SET last_entry_date=%s, streak_days=%s WHERE user_id=%s",
                (today, streak, user_id),
            )
        cur.close()
    return streak


def get_streak(user_id: int | None) -> int:
    if user_id is None:
        return 0
    ensure_progress_tables()
    today = moscow_today()
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute("SELECT last_entry_date, streak_days FROM user_progress WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        cur.close()
    if not row or not row["last_entry_date"]:
        return 0
    return int(row["streak_days"] or 0) if (today - row["last_entry_date"]).days <= 1 else 0


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
    ensure_progress_tables()
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
    streak = record_accounting_day(user_id)
    _income, _expense, _balance, month_count = month_summary(person_id)
    total_count = total_operations()
    t = PROGRESS_TEXTS
    lines = [build_month_summary(person_id), "", t["streak"].format(days=streak)]
    achievements = []
    achievement_rules = [
        ("first_operation", total_count >= 1),
        ("streak_7", streak >= 7),
        ("streak_30", streak >= 30),
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
    elif streak > 1 and streak % 2 == 0:
        lines.extend(["", t["motivation_updated"]])
    return "\n".join(lines)


def _next_recurring_candidate(row, today: date) -> dict | None:
    day = row.get("day_of_month")
    if not day:
        return None
    year, month = today.year, today.month
    for _ in range(24):
        days_in_month = monthrange(year, month)[1]
        if day <= days_in_month:
            candidate = date(year, month, day)
            if candidate >= today:
                item = dict(row)
                item["payment_date"] = candidate
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
            SELECT id, title, amount, day_of_month
            FROM recurring_operations
            WHERE is_active=TRUE AND type IN ('payment','expense')
            """
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


def build_financial_order_block(user_id: int | None, person_id: int | None = None) -> str:
    t = PROGRESS_TEXTS
    _income, _expense, _balance, month_count = month_summary(person_id)
    payment = fetch_next_payment()
    lines = [t["progress_title"], t["progress_streak"].format(days=get_streak(user_id))]
    if month_count:
        lines.append(t["progress_month_operations"].format(count=month_count))
    else:
        lines.append(t["progress_no_month_operations"])
    if payment:
        lines.append(
            t["progress_next_payment"].format(
                date=payment["payment_date"].strftime("%d.%m.%Y"),
                title=payment["title"],
                amount=money_currency(float(payment["amount"])),
            )
        )
    else:
        lines.append(t["progress_no_payments"])
    return "\n".join(lines)
