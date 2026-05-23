from datetime import datetime

from database import get_connection


def build_summary_report() -> str:
    with get_connection() as conn:
        income = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'income'"
        ).fetchone()[0]
        expense = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'expense'"
        ).fetchone()[0]
        participants = conn.execute(
            """
            SELECT p.name, COALESCE(SUM(CASE WHEN t.type='income' THEN t.amount ELSE -t.amount END), 0) as balance
            FROM participants p
            LEFT JOIN transactions t ON t.participant_id = p.id
            GROUP BY p.id, p.name
            ORDER BY p.id
            """
        ).fetchall()
        payments = conn.execute(
            """
            SELECT title, due_date
            FROM payments
            WHERE is_paid = 0
            ORDER BY due_date ASC
            LIMIT 5
            """
        ).fetchall()

    balance = income - expense
    lines = [
        "📊 Общий отчёт",
        "",
        "Доходы:",
        f"{income:.2f} ₽",
        "",
        "Расходы:",
        f"{expense:.2f} ₽",
        "",
        "Баланс:",
        f"{balance:.2f} ₽",
        "",
        "По участникам:",
    ]

    if participants:
        lines.extend([f"{row['name']} — {row['balance']:.2f} ₽" for row in participants])
    else:
        lines.append("Нет данных")

    lines.append("")
    lines.append("Ближайшие платежи:")
    if payments:
        for row in payments:
            due = datetime.strptime(row["due_date"], "%Y-%m-%d").strftime("%d.%m")
            lines.append(f"{due} — {row['title']}")
    else:
        lines.append("Нет ближайших платежей")

    return "\n".join(lines)
