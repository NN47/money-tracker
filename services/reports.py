from database import dict_cursor, get_connection


def build_summary_report() -> str:
    with get_connection() as conn:
        cur = dict_cursor(conn)
        try:
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM transactions WHERE type = 'income'")
            income = float(cur.fetchone()["total"])
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM transactions WHERE type = 'expense'")
            expense = float(cur.fetchone()["total"])
            cur.execute(
                """
                SELECT p.name, COALESCE(SUM(CASE WHEN t.type='income' THEN t.amount ELSE -t.amount END), 0) as balance
                FROM participants p
                LEFT JOIN transactions t ON t.participant_id = p.id
                GROUP BY p.id, p.name
                ORDER BY p.id
                """
            )
            participants = cur.fetchall()
            cur.execute(
                """
                SELECT title, due_date
                FROM payments
                WHERE is_paid = FALSE
                ORDER BY due_date ASC
                LIMIT 5
                """
            )
            payments = cur.fetchall()
        finally:
            cur.close()

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
        lines.extend([f"{row['name']} — {float(row['balance']):.2f} ₽" for row in participants])
    else:
        lines.append("Нет данных")

    lines.append("")
    lines.append("Ближайшие платежи:")
    if payments:
        for row in payments:
            due = row["due_date"].strftime("%d.%m")
            lines.append(f"{due} — {row['title']}")
    else:
        lines.append("Нет ближайших платежей")

    return "\n".join(lines)
