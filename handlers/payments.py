import re
from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import dict_cursor, get_connection
from keyboards.main import main_menu_kb, payment_done_kb, recurring_type_kb, skip_comment_kb

router = Router()


class ScheduledPaymentStates(StatesGroup):
    waiting_title = State()
    waiting_amount = State()
    waiting_date = State()


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
    m = re.fullmatch(r"через\s+(\d+)\s+дн(?:я|ей)?", text)
    if m:
        return date.today() + timedelta(days=int(m.group(1)))
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        pass
    try:
        dm = datetime.strptime(text, "%d.%m").date()
        return dm.replace(year=date.today().year)
    except ValueError as exc:
        raise ValueError from exc


@router.message(F.text == "📅 Предстоящий платёж")
async def payment_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ScheduledPaymentStates.waiting_title)
    await message.answer("Введите название платежа:")


@router.message(ScheduledPaymentStates.waiting_title)
async def payment_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(ScheduledPaymentStates.waiting_amount)
    await message.answer("Введите сумму:")


@router.message(ScheduledPaymentStates.waiting_amount)
async def payment_amount(message: Message, state: FSMContext):
    try:
        amount = parse_money(message.text)
    except Exception:
        await message.answer("Введите корректную сумму больше 0.")
        return
    await state.update_data(amount=amount)
    await state.set_state(ScheduledPaymentStates.waiting_date)
    await message.answer("Введите дату: ДД.ММ.ГГГГ, ДД.ММ или 'через N дней'.")


@router.message(ScheduledPaymentStates.waiting_date)
async def payment_date(message: Message, state: FSMContext):
    try:
        payment_date = parse_flexible_date(message.text)
    except ValueError:
        await message.answer("Не смог распознать дату. Примеры: 10.06.2026, 10.06, через 10 дней")
        return
    data = await state.get_data()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO scheduled_payments(title, amount, payment_date, is_paid) VALUES(%s, %s, %s, FALSE)",
            (data["title"], data["amount"], payment_date.isoformat()),
        )
        cur.close()
    await state.clear()
    await message.answer("Предстоящий платёж добавлен ✅", reply_markup=main_menu_kb())


@router.callback_query(F.data.startswith("pay_done:"))
async def payment_mark_done(callback: CallbackQuery):
    payment_id = int(callback.data.split(":")[1])
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE scheduled_payments SET is_paid = TRUE WHERE id = %s", (payment_id,))
        cur.close()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Платёж отмечен как оплаченный")


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
    await message.answer("Введите название:")


@router.message(RecurringStates.waiting_title)
async def recurring_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(RecurringStates.waiting_amount)
    await message.answer("Введите сумму:")


@router.message(RecurringStates.waiting_amount)
async def recurring_amount(message: Message, state: FSMContext):
    try:
        amount = parse_money(message.text)
    except Exception:
        await message.answer("Введите корректную сумму больше 0.")
        return
    await state.update_data(amount=amount)
    await state.set_state(RecurringStates.waiting_day)
    await message.answer("Введите день месяца (1-31):")


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
    await message.answer("Введите категорию:")


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
    await state.clear()
    await message.answer("Постоянная операция сохранена ✅", reply_markup=main_menu_kb())


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
        txt = f"{row['payment_date'].strftime('%d.%m')} — {row['title']} — {float(row['amount']):,.2f} ₽"
        await message.answer(txt, reply_markup=payment_done_kb(row['id']))
