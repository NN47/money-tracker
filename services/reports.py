from calendar import monthrange
from datetime import date, timedelta
import html

from database import dict_cursor, get_connection
from services.currencies import format_amount, format_money
from services.recurring_payments import (
    fetch_unpaid_due_recurring_payments,
    moscow_today,
)

UPCOMING_PAYMENTS_DAYS = 10

RUSSIAN_MONTHS = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}


def format_russian_month_year(value: date) -> str:
    return f"{RUSSIAN_MONTHS[value.month].capitalize()} {value.year}"


def money(value: float) -> str:
    return format_amount(value)


def money_currency(value: float, currency: str | None = None) -> str:
    return format_money(value, currency)


def _totals_by_currency(rows) -> dict[str, float]:
    return {row["currency"] or "RUB": float(row["total"] or 0) for row in rows}


def _ensure_totals(totals) -> dict[str, float]:
    if isinstance(totals, dict):
        return totals
    return {"RUB": float(totals or 0)}


def _format_totals(totals: dict[str, float]) -> str:
    totals = _ensure_totals(totals)
    if not totals:
        return money_currency(0, "RUB")
    return ", ".join(money_currency(amount, currency) for currency, amount in sorted(totals.items()))


def _subtract_totals(income: dict[str, float], expense: dict[str, float]) -> dict[str, float]:
    income = _ensure_totals(income)
    expense = _ensure_totals(expense)
    currencies = set(income) | set(expense)
    return {currency: income.get(currency, 0) - expense.get(currency, 0) for currency in currencies}


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


def _paid_payment_dates(row) -> set[date]:
    return {payment_date for payment_date in row.get("paid_payment_dates") or [] if payment_date}


def upcoming_recurring_payments(rows, today: date, horizon: date):
    upcoming = []
    for row in rows:
        next_date = _next_recurring_date(row.get("day_of_month"), today)
        if next_date is None or next_date > horizon:
            continue
        if next_date in _paid_payment_dates(row):
            continue
        item = dict(row)
        item["payment_date"] = next_date
        item.pop("paid_payment_dates", None)
        upcoming.append(item)
    return sorted(upcoming, key=lambda row: (row["payment_date"], row["id"]))


def _overdue_recurring_payments(today: date):
    return [row for row in fetch_unpaid_due_recurring_payments(today) if row.get("payment_date") and row["payment_date"] < today]


def _format_payment_line(row, *, include_year: bool = False) -> str:
    date_format = "%d.%m.%Y" if include_year else "%d.%m"
    recurring_mark = " 🔁" if "day_of_month" in row else ""
    return (
        f"{row['payment_date'].strftime(date_format)} — {html.escape(row['title'])} — "
        f"<b>{money_currency(float(row['amount']), row.get('currency'))}</b>{recurring_mark}"
    )


def _person_filter_sql(person_id: int | None, prefix: str = "") -> tuple[str, list]:
    column = f"{prefix}person_id" if prefix else "person_id"
    if person_id is not None:
        return f" AND {column} = %s", [person_id]
    table_prefix = prefix.rstrip(".")
    person_alias = "p" if not table_prefix else f"{table_prefix}_person"
    return (
        f" AND ({column} IS NULL OR EXISTS (SELECT 1 FROM persons {person_alias} WHERE {person_alias}.id = {column} AND {person_alias}.include_in_budget = TRUE))",
        [],
    )


def _person_title(person_name: str | None) -> list[str]:
    return [f"📁 <b>{html.escape(person_name)}</b>", "", f"Фильтр: 📁 {html.escape(person_name)}", ""] if person_name else []


def _fetch_main_data(person_id: int | None = None, report_date: date | None = None):
    today = report_date or moscow_today()
    start, nxt = month_bounds(today)
    horizon = today + timedelta(days=UPCOMING_PAYMENTS_DAYS)
    with get_connection() as conn:
        cur = dict_cursor(conn)
        person_filter, person_params = _person_filter_sql(person_id)
        cur.execute("SELECT COALESCE(currency, 'RUB') currency, COALESCE(SUM(amount),0) total FROM transactions WHERE type='income' AND operation_date >= %s AND operation_date < %s" + person_filter + " GROUP BY COALESCE(currency, 'RUB')", (start, nxt, *person_params))
        income = _totals_by_currency(cur.fetchall())
        cur.execute("SELECT COALESCE(currency, 'RUB') currency, COALESCE(SUM(amount),0) total FROM transactions WHERE type='expense' AND operation_date >= %s AND operation_date < %s" + person_filter + " GROUP BY COALESCE(currency, 'RUB')", (start, nxt, *person_params))
        expense = _totals_by_currency(cur.fetchall())
        if person_id is None:
            cur.execute("SELECT id, title, amount, payment_date FROM scheduled_payments WHERE is_paid=FALSE AND payment_date < %s ORDER BY payment_date, id LIMIT 10", (today,))
            overdue_payments = cur.fetchall()
            cur.execute("SELECT id, title, amount, payment_date FROM scheduled_payments WHERE is_paid=FALSE AND payment_date BETWEEN %s AND %s ORDER BY payment_date LIMIT 10", (today, horizon))
            payments = cur.fetchall()
            cur.execute(
                """
                SELECT
                    ro.id,
                    ro.title,
                    ro.type,
                    ro.amount,
                    ro.day_of_month,
                    COALESCE(
                        array_agg(l.payment_date ORDER BY l.payment_date)
                            FILTER (WHERE l.payment_date IS NOT NULL),
                        ARRAY[]::date[]
                    ) AS paid_payment_dates
                FROM recurring_operations ro
                LEFT JOIN recurring_payments_log l
                    ON l.recurring_operation_id = ro.id
                   AND l.payment_date BETWEEN %s AND %s
                WHERE ro.is_active=TRUE
                  AND ro.type IN ('payment', 'expense')
                GROUP BY ro.id, ro.title, ro.type, ro.amount, ro.day_of_month
                ORDER BY ro.day_of_month, ro.id
                """,
                (today, horizon),
            )
            payable_recurring = cur.fetchall()
        else:
            overdue_payments = []
            payments = []
            payable_recurring = []
        cur.close()
    overdue_recurring = _overdue_recurring_payments(today) if person_id is None else []
    recurring_upcoming = upcoming_recurring_payments(payable_recurring, today, horizon)[:10]
    return today, income, expense, overdue_payments, overdue_recurring, payments, recurring_upcoming


def build_dashboard(person_id: int | None = None, person_name: str | None = None) -> str:
    today, income, expense, _overdue_payments, _overdue_recurring, payments, recurring = _fetch_main_data(person_id=person_id)
    balance = _subtract_totals(income, expense)
    lines = [
        *_person_title(person_name),
        "💼 Главный экран",
        "",
        f"📊 <b>{format_russian_month_year(today)}</b>",
        f"💰 <b>Доходы:</b> <b>{_format_totals(income)}</b>",
        f"💸 <b>Расходы:</b> <b>{_format_totals(expense)}</b>",
        f"⚖️ <b>Баланс:</b> <b>{_format_totals(balance)}</b>",
    ]
    upcoming_payments = [] if person_id is not None else sorted([*payments, *recurring], key=lambda row: (row["payment_date"], row["id"]))[:10]
    if upcoming_payments:
        lines.extend(["", "<b>📅 Платежи в ближайшие 10 дней:</b>"])
        for r in upcoming_payments:
            lines.append(_format_payment_line(r))
    else:
        lines.extend(["", "<b>📅 Платежей в ближайшие 10 дней нет</b>"])
    return "\n".join(lines)


def _format_transaction_date(operation_date: date, period_start: date, period_end: date) -> str:
    if period_start <= operation_date < period_end:
        return operation_date.strftime("%d.%m")
    return operation_date.strftime("%d.%m.%Y")


def fetch_recent_transactions(limit: int = 10, tx_type: str | None = None, person_id: int | None = None):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        params: list = []
        type_filter = ""
        where = []
        if tx_type:
            where.append("type = %s")
            params.append(tx_type)
        if person_id is not None:
            where.append("person_id = %s")
            params.append(person_id)
        else:
            where.append("(person_id IS NULL OR EXISTS (SELECT 1 FROM persons p WHERE p.id = transactions.person_id AND p.include_in_budget = TRUE))")
        type_filter = "WHERE " + " AND ".join(where) if where else ""
        params.append(limit)
        cur.execute(
            f"""
            SELECT id, type, amount, COALESCE(currency, 'RUB') currency, category, comment, operation_date
            FROM transactions
            {type_filter}
            ORDER BY operation_date DESC, id DESC
            LIMIT %s
            """,
            params,
        )
        tx = cur.fetchall()
        cur.close()
    return tx



def fetch_month_transactions(report_date: date, tx_type: str | None = None, person_id: int | None = None):
    start, nxt = month_bounds(report_date)
    with get_connection() as conn:
        cur = dict_cursor(conn)
        params: list = [start, nxt]
        where = ["operation_date >= %s", "operation_date < %s"]
        if tx_type:
            where.append("type = %s")
            params.append(tx_type)
        if person_id is not None:
            where.append("person_id = %s")
            params.append(person_id)
        else:
            where.append("(person_id IS NULL OR EXISTS (SELECT 1 FROM persons p WHERE p.id = transactions.person_id AND p.include_in_budget = TRUE))")
        cur.execute(
            f"""
            SELECT id, type, amount, COALESCE(currency, 'RUB') currency, category, comment, operation_date
            FROM transactions
            WHERE {" AND ".join(where)}
            ORDER BY operation_date DESC, id DESC
            """,
            params,
        )
        tx = cur.fetchall()
        cur.close()
    return tx

def _format_transaction_line(row, start: date, end: date) -> str:
    sign = "+" if row["type"] == "income" else "-"
    tx_date = _format_transaction_date(row["operation_date"], start, end)
    category = html.escape(row["category"] or "Без категории")
    comment = f" — {html.escape(row['comment'])}" if row.get("comment") else ""
    return f"<b>{tx_date}</b> <b>{sign}{money_currency(float(row['amount']), row.get('currency'))}</b> — <b>{category}</b>{comment}"


def build_summary_report(transactions=None, tx_type: str | None = None, person_id: int | None = None, person_name: str | None = None, report_date: date | None = None) -> str:
    today, income, expense, overdue_payments, overdue_recurring, payments, recurring = _fetch_main_data(person_id=person_id, report_date=report_date)
    balance = _subtract_totals(income, expense)
    tx = fetch_month_transactions(today, tx_type=tx_type, person_id=person_id) if transactions is None else transactions
    start, nxt = month_bounds(today)
    if tx_type == "income":
        title = "📊 <b>Отчёт по доходам</b>"
        total_lines = [f"💰 <b>Доходы:</b> <b>{_format_totals(income)}</b>"]
        recent_title = "<b>💵 Доходы за месяц:</b>"
    elif tx_type == "expense":
        title = "📊 <b>Отчёт по расходам</b>"
        total_lines = [f"💸 <b>Расходы:</b> <b>{_format_totals(expense)}</b>"]
        recent_title = "<b>🧾 Расходы за месяц:</b>"
    else:
        title = "📊 <b>Отчёт</b>"
        total_lines = [
            f"💰 <b>Доходы:</b> <b>{_format_totals(income)}</b>",
            f"💸 <b>Расходы:</b> <b>{_format_totals(expense)}</b>",
            f"⚖️ <b>Баланс:</b> <b>{_format_totals(balance)}</b>",
        ]
        recent_title = "<b>🧾 Операции за месяц:</b>"
    lines = [*_person_title(person_name), title, "", f"🗓 <b>Период:</b> <b>{format_russian_month_year(today)}</b>", *total_lines, "", recent_title]
    if tx:
        for row in tx:
            lines.append(_format_transaction_line(row, start, nxt))
    else:
        lines.append("Операций пока нет")
    if tx_type != "income":
        lines.append("")
        overdue = [] if person_id is not None else sorted([*overdue_payments, *overdue_recurring], key=lambda row: (row["payment_date"], row["id"]))[:10]
        if overdue:
            lines.append("<b>⚠️ Просроченные платежи:</b>")
            for r in overdue:
                lines.append(_format_payment_line(r, include_year=True))
            lines.append("")
        lines.append(f"<b>📅 Ближайшие платежи на {UPCOMING_PAYMENTS_DAYS} дней:</b>")
        upcoming_payments = [] if person_id is not None else sorted([*payments, *recurring], key=lambda row: (row["payment_date"], row["id"]))[:10]
        if upcoming_payments:
            for r in upcoming_payments:
                lines.append(_format_payment_line(r))
        else:
            lines.append("Нет платежей")
    return "\n".join(lines)



def fetch_categories(tx_type: str | None = None, person_id: int | None = None):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        params: list = []
        type_filter = ""
        if tx_type:
            type_filter = "AND type = %s"
            params.append(tx_type)
        person_filter = ""
        if person_id is not None:
            person_filter = "AND person_id = %s"
            params.append(person_id)
        else:
            person_filter = "AND (person_id IS NULL OR EXISTS (SELECT 1 FROM persons p WHERE p.id = transactions.person_id AND p.include_in_budget = TRUE))"
        cur.execute(
            f"""
            SELECT category, COALESCE(currency, 'RUB') currency, COUNT(*) operations_count, COALESCE(SUM(amount), 0) total
            FROM transactions
            WHERE COALESCE(NULLIF(TRIM(category), ''), '') <> ''
            {type_filter}
            {person_filter}
            GROUP BY category, COALESCE(currency, 'RUB')
            ORDER BY LOWER(category)
            """,
            params,
        )
        categories = cur.fetchall()
        cur.close()
    return categories


def fetch_category_transactions(category: str, limit: int = 50, tx_type: str | None = None, person_id: int | None = None):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        params: list = [category]
        type_filter = ""
        if tx_type:
            type_filter = "AND type = %s"
            params.append(tx_type)
        person_filter = ""
        if person_id is not None:
            person_filter = "AND person_id = %s"
            params.append(person_id)
        else:
            person_filter = "AND (person_id IS NULL OR EXISTS (SELECT 1 FROM persons p WHERE p.id = transactions.person_id AND p.include_in_budget = TRUE))"
        params.append(limit)
        cur.execute(
            f"""
            SELECT id, type, amount, COALESCE(currency, 'RUB') currency, category, comment, operation_date
            FROM transactions
            WHERE category = %s
            {type_filter}
            {person_filter}
            ORDER BY operation_date DESC, id DESC
            LIMIT %s
            """,
            params,
        )
        tx = cur.fetchall()
        cur.close()
    return tx


def build_categories_report(categories, tx_type: str | None = None) -> str:
    if tx_type == "income":
        title = "📂 <b>Категории доходов</b>"
    elif tx_type == "expense":
        title = "📂 <b>Категории расходов</b>"
    else:
        title = "📂 <b>Категории</b>"
    lines = [title, ""]
    if not categories:
        lines.append("Категорий пока нет")
        return "\n".join(lines)
    for row in categories:
        lines.append(
            f"• {html.escape(row['category'])} — {int(row['operations_count'])} опер., "
            f"<b>{money_currency(float(row['total']), row.get('currency'))}</b>"
        )
    lines.append("")
    lines.append("Откройте категорию кнопкой ниже, чтобы увидеть операции.")
    return "\n".join(lines)


def build_category_report(category: str, transactions, tx_type: str | None = None) -> str:
    today = date.today()
    start, nxt = month_bounds(today)
    if tx_type == "income":
        title = f"📂 <b>Доходы в категории: {html.escape(category)}</b>"
    elif tx_type == "expense":
        title = f"📂 <b>Расходы в категории: {html.escape(category)}</b>"
    else:
        title = f"📂 <b>Категория: {html.escape(category)}</b>"
    income = {}
    expense = {}
    for row in transactions:
        target = income if row['type'] == 'income' else expense
        currency = row.get('currency') or 'RUB'
        target[currency] = target.get(currency, 0) + float(row['amount'])
    lines = [title, ""]
    if tx_type != "expense":
        lines.append(f"<b>Доходы:</b> {_format_totals(income)}")
    if tx_type != "income":
        lines.append(f"<b>Расходы:</b> {_format_totals(expense)}")
    if tx_type is None:
        lines.append(f"<b>Баланс:</b> {_format_totals(_subtract_totals(income, expense))}")
    lines.extend(["", "<b>Операции:</b>"])
    if transactions:
        for row in transactions:
            lines.append(_format_transaction_line(row, start, nxt))
    else:
        lines.append("Операций пока нет")
    return "\n".join(lines)

def build_transactions_report(limit: int = 50, transactions=None, tx_type: str | None = None, person_id: int | None = None, person_name: str | None = None) -> str:
    today = date.today()
    start, nxt = month_bounds(today)
    tx = fetch_recent_transactions(limit=limit, tx_type=tx_type, person_id=person_id) if transactions is None else transactions
    lines = [*_person_title(person_name), "📋 <b>Все операции</b>", "", "<b>🧾 Список операций:</b>"]
    if not tx:
        lines.append("Операций пока нет")
        return "\n".join(lines)
    for row in tx:
        lines.append(_format_transaction_line(row, start, nxt))
    return "\n".join(lines)
