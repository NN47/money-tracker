from datetime import date, datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database import get_connection
from keyboards.main import date_choice_kb, main_menu_kb, skip_comment_kb

router = Router()


class TransactionStates(StatesGroup):
    waiting_amount = State()
    waiting_category = State()
    waiting_date_choice = State()
    waiting_manual_date = State()
    waiting_comment = State()


def parse_money(raw: str) -> float:
    amount = float(raw.replace(" ", "").replace(",", "."))
    if amount <= 0:
        raise ValueError
    return round(amount, 2)


def parse_date_ru(raw: str) -> date:
    return datetime.strptime(raw, "%d.%m.%Y").date()


async def _start_transaction(message: Message, state: FSMContext, tx_type: str):
    await state.clear()
    await state.update_data(type=tx_type)
    await state.set_state(TransactionStates.waiting_amount)
    await message.answer("Введите сумму операции:")


@router.message(F.text == "➕ Доход")
async def add_income(message: Message, state: FSMContext):
    await _start_transaction(message, state, "income")


@router.message(F.text == "➖ Расход")
async def add_expense(message: Message, state: FSMContext):
    await _start_transaction(message, state, "expense")


@router.message(TransactionStates.waiting_amount)
async def transaction_amount(message: Message, state: FSMContext):
    try:
        amount = parse_money(message.text)
    except Exception:
        await message.answer("Введите корректную сумму больше 0. Например: 12500.50")
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
    await state.set_state(TransactionStates.waiting_date_choice)
    await message.answer("Дата операции:", reply_markup=date_choice_kb())


@router.message(TransactionStates.waiting_date_choice)
async def transaction_date_choice(message: Message, state: FSMContext):
    if message.text == "Сегодня":
        await state.update_data(operation_date=date.today().isoformat())
        await state.set_state(TransactionStates.waiting_comment)
        await message.answer("Введите комментарий или нажмите «Пропустить».", reply_markup=skip_comment_kb())
        return
    if message.text == "Ввести дату":
        await state.set_state(TransactionStates.waiting_manual_date)
        await message.answer("Введите дату в формате ДД.ММ.ГГГГ")
        return
    await message.answer("Выберите: «Сегодня» или «Ввести дату».")


@router.message(TransactionStates.waiting_manual_date)
async def transaction_manual_date(message: Message, state: FSMContext):
    try:
        op_date = parse_date_ru(message.text.strip())
    except Exception:
        await message.answer("Некорректная дата. Формат: ДД.ММ.ГГГГ")
        return
    await state.update_data(operation_date=op_date.isoformat())
    await state.set_state(TransactionStates.waiting_comment)
    await message.answer("Введите комментарий или нажмите «Пропустить».", reply_markup=skip_comment_kb())


@router.message(TransactionStates.waiting_comment)
async def transaction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = None if message.text == "Пропустить" else message.text.strip()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO transactions(type, amount, category, comment, operation_date)
            VALUES(%s, %s, %s, %s, %s)
            """,
            (data["type"], data["amount"], data["category"], comment, data["operation_date"]),
        )
        cur.close()
    await state.clear()
    await message.answer("Операция сохранена ✅", reply_markup=main_menu_kb())
