from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database import get_connection
from keyboards.main import payments_menu_kb

router = Router()


class PaymentStates(StatesGroup):
    waiting_participant_id = State()
    waiting_title = State()
    waiting_amount = State()
    waiting_due_date = State()


@router.message(F.text == "💳 Платежи")
async def payments_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Раздел платежей:", reply_markup=payments_menu_kb())


@router.message(F.text == "➕ Добавить платёж")
async def payment_start(message: Message, state: FSMContext):
    with get_connection() as conn:
        participants = conn.execute("SELECT id, name FROM participants ORDER BY id").fetchall()
    if not participants:
        await message.answer("Сначала добавьте участников в разделе «👥 Участники».")
        return
    text = "Введите ID участника для платежа:\n" + "\n".join(
        f"{p['id']}. {p['name']}" for p in participants
    )
    await state.set_state(PaymentStates.waiting_participant_id)
    await message.answer(text)


@router.message(PaymentStates.waiting_participant_id)
async def payment_participant(message: Message, state: FSMContext):
    try:
        participant_id = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Введите корректный ID.")
        return
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM participants WHERE id = ?", (participant_id,)).fetchone()
    if not row:
        await message.answer("Участник не найден. Повторите ввод ID.")
        return
    await state.update_data(participant_id=participant_id)
    await state.set_state(PaymentStates.waiting_title)
    await message.answer("Введите название платежа:")


@router.message(PaymentStates.waiting_title)
async def payment_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(PaymentStates.waiting_amount)
    await message.answer("Введите сумму:")


@router.message(PaymentStates.waiting_amount)
async def payment_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        await message.answer("Введите корректную сумму больше 0.")
        return
    await state.update_data(amount=amount)
    await state.set_state(PaymentStates.waiting_due_date)
    await message.answer("Введите дату в формате ДД.ММ.ГГГГ (например, 10.06.2026):")


@router.message(PaymentStates.waiting_due_date)
async def payment_due_date(message: Message, state: FSMContext):
    raw_date = message.text.strip()
    try:
        due_dt = datetime.strptime(raw_date, "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат даты. Пример: 10.06.2026")
        return

    data = await state.get_data()
    due_date = due_dt.strftime("%Y-%m-%d")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO payments(participant_id, title, amount, due_date, is_paid)
            VALUES(?, ?, ?, ?, 0)
            """,
            (data["participant_id"], data["title"], data["amount"], due_date),
        )
    await state.clear()
    await message.answer("Платёж добавлен ✅", reply_markup=payments_menu_kb())


@router.message(F.text == "📅 Ближайшие")
async def nearest_payments(message: Message):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.title, p.amount, p.due_date, pt.name as participant_name
            FROM payments p
            LEFT JOIN participants pt ON pt.id = p.participant_id
            WHERE p.is_paid = 0
            ORDER BY p.due_date ASC
            LIMIT 10
            """
        ).fetchall()
    if not rows:
        await message.answer("Ближайших платежей нет.")
        return

    lines = ["💳 Ближайшие платежи:"]
    for row in rows:
        due = datetime.strptime(row["due_date"], "%Y-%m-%d").strftime("%d.%m")
        lines.append(f"{due} — {row['title']} ({row['amount']:.2f} ₽), {row['participant_name']}")
    await message.answer("\n".join(lines))
