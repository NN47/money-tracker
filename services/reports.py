from calendar import monthrange
from datetime import date, timedelta
import html

from database import dict_cursor, get_connection
from services.recurring_payments import fetch_today_recurring_payments, moscow_today, split_by_payment_status

UPCOMING_PAYMENTS_DAYS = 10


def money(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", " ")
    if formatted.endswith(".00"):
        return formatted[:-3]
    return formatted.rstrip("0").rstrip(".")


def month_bounds(today: date):
    start = today.replace(day=1)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    return start, nxt


def _next_recurring_date(day_of_month: int | None, today: date) -> date | None:
    if not day_of_month:
        return None

    year = today.year
    month = today.month
    for _ in range(24):
        days_in_month = monthrange(year, month)[1]
        if day_of_month <= days_in_month:
            candidate = date(year, month, day_of_month)
            if candidate >= today:
                return candidate
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return None


def upcoming_recurring_payments(rows, today: date, horizon: date):
    upcoming = []
    for row in rows:
        next_date = _next_recurring_date(row.get("day_of_month"), today)
        if next_date is None or next_date > horizon:
            continue
        item = dict(row)
        item["payment_date"] = next_date
        upcoming.append(item)
    return sorted(upcoming, key=lambda row: (row["payment_date"], row["id"]))


def _fetch_main_data():
    today = moscow_today()
    start, nxt = month_bounds(today)
    horizon = today + timedelta(days=UPCOMING_PAYMENTS_DAYS)
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute("SELECT COALESCE(SUM(amount),0) total FROM transactions WHERE type='income' AND operation_date >= %s AND operation_date < %s", (start, nxt))
        income = float(cur.fetchone()["total"])
        cur.execute("SELECT COALESCE(SUM(amount),0) total FROM transactions WHERE type='expense' AND operation_date >= %s AND operation_date < %s", (start, nxt))
        expense = float(cur.fetchone()["total"])
        cur.execute("SELECT id, title, amount, payment_date FROM scheduled_payments WHERE is_paid=FALSE AND payment_date BETWEEN %s AND %s ORDER BY payment_date LIMIT 10", (today, horizon))
        payments = cur.fetchall()
        cur.execute("SELECT id, title, type, amount, day_of_month FROM recurring_operations WHERE is_active=TRUE AND type IN ('payment', 'expense') ORDER BY day_of_month, id")
        payable_recurring = cur.fetchall()
        cur.execute("SELECT id, title, amount, day_of_month FROM recurring_operations WHERE is_active=TRUE ORDER BY day_of_month NULLS LAST, id LIMIT 10")
        active_recurring = cur.fetchall()
        cur.close()
    recurring_upcoming = upcoming_recurring_payments(payable_recurring, today, horizon)[:10]
    return today, income, expense, payments, recurring_upcoming, active_recurring


def build_dashboard() -> str:
    today, income, expense, payments, recurring, active_recurring = _fetch_main_data()
    today_recurring = fetch_today_recurring_payments()
    unpaid_today, paid_today = split_by_payment_status(today_recurring)
    balance = income - expense
    lines = [
        "💼 Главный экран",
        "",
        f"📊 {today.strftime('%B %Y').capitalize()}",
        f"Доходы: {money(income)} ₽",
        f"Расходы: {money(expense)} ₽",
        f"Баланс: {money(balance)} ₽",
    ]
    if unpaid_today:
        lines.extend(["", "🔥 Сегодня к оплате:"])
        lines.extend([f"• {r['title']} — {money(float(r['amount']))} ₽" for r in unpaid_today])
    if paid_today:
        lines.extend(["", "✅ Сегодня оплачено:"])
        lines.extend([f"• {r['title']} — {money(float(r['amount']))} ₽" for r in paid_today])
    lines.extend(["", "📅 Ближайшие платежи:"])
    upcoming_payments = sorted([*payments, *recurring], key=lambda row: (row["payment_date"], row["id"]))[:10]
    if upcoming_payments:
        for r in upcoming_payments:
            recurring_mark = " 🔁" if "day_of_month" in r else ""
            lines.append(f"{r['payment_date'].strftime('%d.%m')} — {r['title']} — {money(float(r['amount']))} ₽{recurring_mark}")
    else:
        lines.append(f"Нет неоплаченных платежей на {UPCOMING_PAYMENTS_DAYS} дней")
    lines.append("")
    lines.append("🔁 Постоянные операции:")
    if active_recurring:
        lines.extend([f"{r['day_of_month']} число — {r['title']} — {money(float(r['amount']))} ₽" for r in active_recurring])
    else:
        lines.append("Нет активных постоянных операций")
    return "\n".join(lines)


def _format_transaction_date(operation_date: date, period_start: date, period_end: date) -> str:
    if period_start <= operation_date < period_end:
        return operation_date.strftime("%d.%m")
    return operation_date.strftime("%d.%m.%Y")


def fetch_recent_transactions(limit: int = 10):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT id, type, amount, category, comment, operation_date
            FROM transactions
            ORDER BY operation_date DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        )
        tx = cur.fetchall()
        cur.close()
    return tx


def _format_transaction_line(row, start: date, end: date) -> str:
    sign = "+" if row["type"] == "income" else "-"
    tx_date = _format_transaction_date(row["operation_date"], start, end)
    category = html.escape(row["category"] or "Без категории")
    comment = f" — {html.escape(row['comment'])}" if row.get("comment") else ""
    return f"{tx_date} <b>{sign}{money(float(row['amount']))} ₽</b> — {category}{comment}"


def build_summary_report(transactions=None) -> str:
    today, income, expense, payments, recurring, _ = _fetch_main_data()
    balance = income - expense
    tx = fetch_recent_transactions() if transactions is None else transactions
    start, nxt = month_bounds(today)
    lines = [
        "📊 <b>Отчёт</b>",
        "",
        f"<b>Период:</b> {today.strftime('%m.%Y')}",
        f"<b>Доходы:</b> {money(income)} ₽",
        f"<b>Расходы:</b> {money(expense)} ₽",
        f"<b>Баланс:</b> {money(balance)} ₽",
        "",
        "<b>Последние 10 операций:</b>",
    ]
    if tx:
        for row in tx:
            lines.append(_format_transaction_line(row, start, nxt))
    else:
        lines.append("Операций пока нет")
    lines.append("")
    lines.append(f"<b>Ближайшие платежи на {UPCOMING_PAYMENTS_DAYS} дней:</b>")
    upcoming_payments = sorted([*payments, *recurring], key=lambda row: (row["payment_date"], row["id"]))[:10]
    if upcoming_payments:
        for r in upcoming_payments:
            recurring_mark = " 🔁" if "day_of_month" in r else ""
            lines.append(f"{r['payment_date'].strftime('%d.%m')} — {html.escape(r['title'])} — <b>{money(float(r['amount']))} ₽</b>{recurring_mark}")
    else:
        lines.append("Нет неоплаченных платежей")
    return "\n".join(lines)


def build_transactions_report(limit: int = 50, transactions=None) -> str:
    today = date.today()
    start, nxt = month_bounds(today)
    tx = fetch_recent_transactions(limit=limit) if transactions is None else transactions
    lines = ["📋 <b>Все операции</b>", ""]
    if not tx:
        lines.append("Операций пока нет")
        return "\n".join(lines)
    for row in tx:
        lines.append(_format_transaction_line(row, start, nxt))
    return "\n".join(lines)
