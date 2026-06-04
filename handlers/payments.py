import asyncio
import re
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import dict_cursor, get_connection
from keyboards.main import CANCEL_TEXT, MAIN_MENU_TEXTS, cancel_kb, main_menu_kb, payment_done_kb, recurring_due_kb, recurring_type_kb, skip_comment_kb
from services.recurring_payments import fetch_unpaid_today_recurring_payments, mark_recurring_payment_paid
from services.reports import build_dashboard, money

router = Router()

OWNER_TELEGRAM_ID: int | None = None


def configure_owner(owner_telegram_id: int | None) -> None:
    global OWNER_TELEGRAM_ID
    OWNER_TELEGRAM_ID = owner_telegram_id



class ScheduledPaymentStates(StatesGroup):
    waiting_title = State()
    waiting_amount = State()
    waiting_date = State()
    waiting_comment = State()


class RecurringStates(StatesGroup):
    waiting_type = State()
    waiting_title = State()
    waiting_amount = State()
    waiting_day = State()
    waiting_category = State()
    waiting_comment = State()


def parse_money(raw: str) -> float:
    amount = float(raw.replace(" ", "").replace(",", "."))
    if amount <= 0:
        raise ValueError
    return round(amount, 2)


def parse_flexible_date(raw: str) -> date:
    text = raw.strip().lower()
    if text == "сегодня":
        return date.today()
    if text == "завтра":
        return date.today() + timedelta(days=1)
    m = re.fullmatch(r"через\s+(\d+)\s+дн(?:я|ей)?", text)
    if m:
        return date.today() + timedelta(days=int(m.group(1)))
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        pass
    dm = datetime.strptime(text, "%d.%m").date().replace(year=date.today().year)
    if dm < date.today():
        dm = dm.replace(year=dm.year + 1)
    return dm


async def _back_to_home(message: Message, state: FSMContext):
    await state.clear()
    unpaid_operations = fetch_unpaid_today_recurring_payments()
    await message.answer(build_dashboard(), reply_markup=recurring_due_kb(unpaid_operations))
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


def build_recurring_payment_notification(operations) -> str:
    lines = ["🔥 Сегодня к оплате:"]
    lines.extend([f"• {row['title']} — {money(float(row['amount']))} ₽" for row in operations])
    return "\n".join(lines)


async def send_recurring_payment_notification(bot: Bot, chat_id: int, operation_ids: list[int] | None = None) -> None:
    operations = fetch_unpaid_today_recurring_payments()
    if operation_ids is not None:
        allowed_ids = set(operation_ids)
        operations = [row for row in operations if row["id"] in allowed_ids]
    if not operations:
        return
    await bot.send_message(
        chat_id,
        build_recurring_payment_notification(operations),
        reply_markup=recurring_due_kb(operations),
    )


async def remind_later(bot: Bot, chat_id: int, operation_id: int, delay_seconds: int = 3600) -> None:
    await asyncio.sleep(delay_seconds)
    await send_recurring_payment_notification(bot, chat_id, [operation_id])


@router.message(F.text == CANCEL_TEXT)
async def cancel_any(message: Message, state: FSMContext):
    await _back_to_home(message, state)


@router.message(
    StateFilter(
        ScheduledPaymentStates.waiting_title,
        ScheduledPaymentStates.waiting_amount,
        ScheduledPaymentStates.waiting_date,
        ScheduledPaymentStates.waiting_comment,
        RecurringStates.waiting_type,
        RecurringStates.waiting_title,
        RecurringStates.waiting_amount,
        RecurringStates.waiting_day,
        RecurringStates.waiting_category,
        RecurringStates.waiting_comment,
    ),
    F.text.in_(MAIN_MENU_TEXTS),
)
async def menu_during_fsm(message: Message, state: FSMContext):
    await state.clear()


@router.message(F.text == "📅 Предстоящий платёж")
async def payment_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ScheduledPaymentStates.waiting_title)
    await message.answer("Введите название платежа:", reply_markup=cancel_kb())


@router.message(ScheduledPaymentStates.waiting_title)
async def payment_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(ScheduledPaymentStates.waiting_amount)
    await message.answer("Введите сумму:", reply_markup=cancel_kb())


@router.message(ScheduledPaymentStates.waiting_amount)
async def payment_amount(message: Message, state: FSMContext):
    try:
        amount = parse_money(message.text)
    except Exception:
        await message.answer("Введите корректную сумму больше 0.")
        return
    await state.update_data(amount=amount)
    await state.set_state(ScheduledPaymentStates.waiting_date)
    await message.answer("Введите дату: завтра, через 10 дней, 10.06 или 10.06.2026", reply_markup=cancel_kb())


@router.message(ScheduledPaymentStates.waiting_date)
async def payment_date(message: Message, state: FSMContext):
    try:
        payment_date = parse_flexible_date(message.text)
    except ValueError:
        await message.answer("Не понял дату. Можно так: завтра, через 10 дней, 10.06 или 10.06.2026")
        return
    await state.update_data(payment_date=payment_date.isoformat())
    await state.set_state(ScheduledPaymentStates.waiting_comment)
    await message.answer("Введите комментарий или нажмите «Пропустить».", reply_markup=skip_comment_kb())


@router.message(ScheduledPaymentStates.waiting_comment)
async def payment_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = None if message.text == "Пропустить" else message.text.strip()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO scheduled_payments(title, amount, payment_date, comment, is_paid) VALUES(%s, %s, %s, %s, FALSE)",
            (data["title"], data["amount"], data["payment_date"], comment),
        )
        cur.close()
    await message.answer("Сохранено ✅")
    await _back_to_home(message, state)


@router.callback_query(F.data.startswith("pay_done:"))
async def payment_mark_done(callback: CallbackQuery):
    payment_id = int(callback.data.split(":")[1])
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE scheduled_payments SET is_paid = TRUE WHERE id = %s", (payment_id,))
        cur.close()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Платёж отмечен как оплаченный")


@router.callback_query(F.data.startswith("pay_recurring:"))
async def recurring_payment_mark_paid(callback: CallbackQuery):
    operation_id = int(callback.data.split(":", maxsplit=1)[1])
    result = mark_recurring_payment_paid(operation_id)
    status = result["status"]

    if status == "paid":
        title = result["title"]
        await callback.answer(f"Платёж «{title}» записан в расходы ✅")
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
            unpaid_operations = fetch_unpaid_today_recurring_payments()
            await callback.message.answer(
                f"Платёж «{title}» записан в расходы ✅",
                reply_markup=main_menu_kb(),
            )
            await callback.message.answer(build_dashboard(), reply_markup=recurring_due_kb(unpaid_operations))
        return

    if status == "already_paid":
        await callback.answer("Этот платёж уже учтён сегодня ✅", show_alert=True)
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
            unpaid_operations = fetch_unpaid_today_recurring_payments()
            await callback.message.answer(build_dashboard(), reply_markup=recurring_due_kb(unpaid_operations))
        return

    await callback.answer("Этот платёж не найден или отключён", show_alert=True)


@router.callback_query(F.data.startswith("remind_recurring:"))
async def recurring_payment_remind_later(callback: CallbackQuery):
    operation_id = int(callback.data.split(":", maxsplit=1)[1])
    chat_id = OWNER_TELEGRAM_ID or callback.from_user.id
    asyncio.create_task(remind_later(callback.bot, chat_id, operation_id))
    await callback.answer("Напомню через час ⏰")


@router.message(F.text == "🔁 Постоянная операция")
async def recurring_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(RecurringStates.waiting_type)
    await message.answer("Выберите тип операции:", reply_markup=recurring_type_kb())


@router.message(RecurringStates.waiting_type)
async def recurring_type(message: Message, state: FSMContext):
    mapping = {"Доход": "income", "Расход": "expense", "Платёж": "payment"}
    op_type = mapping.get(message.text)
    if not op_type:
        await message.answer("Выберите тип кнопкой: Доход / Расход / Платёж")
        return
    await state.update_data(type=op_type)
    await state.set_state(RecurringStates.waiting_title)
    await message.answer("Введите название:", reply_markup=cancel_kb())


@router.message(RecurringStates.waiting_title)
async def recurring_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(RecurringStates.waiting_amount)
    await message.answer("Введите сумму:", reply_markup=cancel_kb())


@router.message(RecurringStates.waiting_amount)
async def recurring_amount(message: Message, state: FSMContext):
    try:
        amount = parse_money(message.text)
    except Exception:
        await message.answer("Введите корректную сумму больше 0.")
        return
    await state.update_data(amount=amount)
    await state.set_state(RecurringStates.waiting_day)
    await message.answer("Введите день месяца (1-31):", reply_markup=cancel_kb())


@router.message(RecurringStates.waiting_day)
async def recurring_day(message: Message, state: FSMContext):
    try:
        day = int(message.text)
        if day < 1 or day > 31:
            raise ValueError
    except Exception:
        await message.answer("Введите число от 1 до 31.")
        return
    await state.update_data(day_of_month=day)
    await state.set_state(RecurringStates.waiting_category)
    await message.answer("Введите категорию:", reply_markup=cancel_kb())


@router.message(RecurringStates.waiting_category)
async def recurring_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("Категория не может быть пустой.")
        return
    await state.update_data(category=category)
    await state.set_state(RecurringStates.waiting_comment)
    await message.answer("Введите комментарий или «Пропустить».", reply_markup=skip_comment_kb())


@router.message(RecurringStates.waiting_comment)
async def recurring_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = None if message.text == "Пропустить" else message.text.strip()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO recurring_operations(title, type, amount, category, day_of_month, frequency, comment)
            VALUES(%s, %s, %s, %s, %s, 'monthly', %s)
            """,
            (data["title"], data["type"], data["amount"], data["category"], data["day_of_month"], comment),
        )
        cur.close()
    await message.answer("Сохранено ✅")
    await _back_to_home(message, state)


@router.message(F.text == "📅 Ближайшие платежи")
async def list_payments(message: Message):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute("SELECT id, title, amount, payment_date FROM scheduled_payments WHERE is_paid = FALSE ORDER BY payment_date ASC LIMIT 10")
        rows = cur.fetchall()
        cur.close()
    if not rows:
        await message.answer("Нет ближайших неоплаченных платежей.")
        return
    for row in rows:
        txt = f"{row['payment_date'].strftime('%d.%m')} — {row['title']} — {money(float(row['amount']))} ₽"
        await message.answer(txt, reply_markup=payment_done_kb(row['id']))
