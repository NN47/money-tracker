from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from database import get_connection, now_iso
from keyboards.main import main_menu_kb, skip_comment_kb

router = Router()


class TransactionStates(StatesGroup):
    waiting_participant_id = State()
    waiting_type = State()
    waiting_amount = State()
    waiting_category = State()
    waiting_comment = State()


def transaction_type_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💰 Доход"), KeyboardButton(text="💸 Расход")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(F.text == "➕ Добавить операцию")
async def add_transaction_start(message: Message, state: FSMContext):
    with get_connection() as conn:
        participants = conn.execute("SELECT id, name FROM participants ORDER BY id").fetchall()
    if not participants:
        await message.answer("Сначала добавьте участников в разделе «👥 Участники».", reply_markup=main_menu_kb())
        return
    text = "Выберите участника, отправив его ID:\n" + "\n".join(
        f"{p['id']}. {p['name']}" for p in participants
    )
    await state.set_state(TransactionStates.waiting_participant_id)
    await message.answer(text)


@router.message(TransactionStates.waiting_participant_id)
async def transaction_choose_participant(message: Message, state: FSMContext):
    try:
        participant_id = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Введите корректный ID участника.")
        return
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM participants WHERE id = ?", (participant_id,)).fetchone()
    if not row:
        await message.answer("Участник не найден. Введите ID ещё раз.")
        return
    await state.update_data(participant_id=participant_id)
    await state.set_state(TransactionStates.waiting_type)
    await message.answer("Выберите тип операции:", reply_markup=transaction_type_kb())


@router.message(TransactionStates.waiting_type)
async def transaction_choose_type(message: Message, state: FSMContext):
    mapping = {"💰 Доход": "income", "💸 Расход": "expense"}
    tx_type = mapping.get(message.text)
    if not tx_type:
        await message.answer("Нажмите кнопку: 💰 Доход или 💸 Расход.")
        return
    await state.update_data(type=tx_type)
    await state.set_state(TransactionStates.waiting_amount)
    await message.answer("Введите сумму:")


@router.message(TransactionStates.waiting_amount)
async def transaction_amount(message: Message, state: FSMContext):
    raw = message.text.replace(",", ".")
    try:
        amount = float(raw)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        await message.answer("Введите корректную сумму больше 0.")
        return
    await state.update_data(amount=amount)
    await state.set_state(TransactionStates.waiting_category)
    await message.answer("Введите категорию:")


@router.message(TransactionStates.waiting_category)
async def transaction_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("Категория не может быть пустой.")
        return
    await state.update_data(category=category)
    await state.set_state(TransactionStates.waiting_comment)
    await message.answer("Введите комментарий или нажмите «Пропустить».", reply_markup=skip_comment_kb())


@router.message(TransactionStates.waiting_comment)
async def transaction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = None if message.text == "Пропустить" else message.text.strip()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transactions(participant_id, type, amount, category, comment, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                data["participant_id"],
                data["type"],
                data["amount"],
                data["category"],
                comment,
                now_iso(),
            ),
        )
    await state.clear()
    await message.answer("Операция сохранена ✅", reply_markup=main_menu_kb())
