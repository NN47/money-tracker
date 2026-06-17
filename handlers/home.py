from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.types import Message

from database import dict_cursor, get_connection
from keyboards.main import dashboard_actions_kb, main_menu_kb, recurring_due_kb
from services.recurring_payments import fetch_unpaid_due_recurring_payments, moscow_today
from services.reports import build_dashboard


def fetch_unpaid_due_scheduled_payments():
    today = moscow_today()
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            """
            SELECT id, title
            FROM scheduled_payments
            WHERE is_paid = FALSE
              AND payment_date <= %s
            ORDER BY payment_date, id
            LIMIT 10
            """,
            (today,),
        )
        rows = cur.fetchall()
        cur.close()
    return rows


def dashboard_due_action_rows(scheduled_payments, recurring_operations):
    rows = [
        [InlineKeyboardButton(text=f"✅ Оплатил: {payment['title']}", callback_data=f"pay_done:{payment['id']}")]
        for payment in scheduled_payments
    ]
    due_kb = recurring_due_kb(recurring_operations)
    if due_kb:
        rows.extend(due_kb.inline_keyboard)
    return rows or None


async def send_main_screen(message: Message, state: FSMContext) -> None:
    await state.clear()
    scheduled_payments = fetch_unpaid_due_scheduled_payments()
    unpaid_operations = fetch_unpaid_due_recurring_payments()
    extra_rows = dashboard_due_action_rows(scheduled_payments, unpaid_operations)
    await message.answer(build_dashboard(), reply_markup=dashboard_actions_kb(extra_rows), parse_mode="HTML")
    await message.answer("Главное меню:", reply_markup=main_menu_kb())
