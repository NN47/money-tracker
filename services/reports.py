from datetime import date, timedelta

from database import dict_cursor, get_connection
from services.recurring_payments import fetch_today_recurring_payments, split_by_payment_status

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


def _fetch_main_data():
    today = date.today()
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
        cur.execute("SELECT title, amount, day_of_month FROM recurring_operations WHERE is_active=TRUE ORDER BY day_of_month, id LIMIT 10")
        recurring = cur.fetchall()
        cur.close()
    return today, income, expense, payments, recurring


def build_dashboard() -> str:
    today, income, expense, payments, recurring = _fetch_main_data()
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
    if payments:
        lines.extend([f"{r['payment_date'].strftime('%d.%m')} — {r['title']} — {money(float(r['amount']))} ₽" for r in payments])
    else:
        lines.append(f"Нет неоплаченных платежей на {UPCOMING_PAYMENTS_DAYS} дней")
    lines.append("")
    lines.append("🔁 Постоянные операции:")
    if recurring:
        lines.extend([f"{r['day_of_month']} число — {r['title']} — {money(float(r['amount']))} ₽" for r in recurring])
    else:
        lines.append("Нет активных постоянных операций")
    return "\n".join(lines)


def build_summary_report() -> str:
    today, income, expense, payments, _ = _fetch_main_data()
    balance = income - expense
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute("SELECT type, amount, category, operation_date FROM transactions ORDER BY operation_date DESC, id DESC LIMIT 10")
        tx = cur.fetchall()
        cur.close()
    lines = ["📊 Отчёт", "", f"Период: {today.strftime('%m.%Y')}", f"Доходы: {money(income)} ₽", f"Расходы: {money(expense)} ₽", f"Баланс: {money(balance)} ₽", "", "Последние 10 операций:"]
    if tx:
        for row in tx:
            sign = "+" if row["type"] == "income" else "-"
            lines.append(f"{row['operation_date'].strftime('%d.%m')} {sign}{money(float(row['amount']))} ₽ — {row['category']}")
    else:
        lines.append("Операций пока нет")
    lines.append("")
    lines.append(f"Ближайшие платежи на {UPCOMING_PAYMENTS_DAYS} дней:")
    if payments:
        lines.extend([f"{r['payment_date'].strftime('%d.%m')} — {r['title']} — {money(float(r['amount']))} ₽" for r in payments[:10]])
    else:
        lines.append("Нет неоплаченных платежей")
    return "\n".join(lines)
