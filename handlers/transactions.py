from datetime import date

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import get_connection
from keyboards.main import (
    BACK_TEXT,
    CANCEL_TEXT,
    MAIN_MENU_TEXTS,
    calendar_back_kb,
    calendar_kb,
    cancel_kb,
    date_choice_kb,
    main_menu_kb,
    skip_comment_kb,
)
from services.dates import parse_transaction_date
from services.reports import build_dashboard

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
    return parse_transaction_date(raw)


async def _back_to_home(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(build_dashboard())
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


@router.message(F.text == CANCEL_TEXT)
async def cancel_any(message: Message, state: FSMContext):
    await _back_to_home(message, state)


@router.message(F.text == BACK_TEXT)
async def back_any(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await _back_to_home(message, state)


@router.message(
    StateFilter(
        TransactionStates.waiting_amount,
        TransactionStates.waiting_category,
        TransactionStates.waiting_date_choice,
        TransactionStates.waiting_manual_date,
        TransactionStates.waiting_comment,
    ),
    F.text.in_(MAIN_MENU_TEXTS),
)
async def menu_during_transaction(message: Message, state: FSMContext):
    await state.clear()


async def _start_transaction(message: Message, state: FSMContext, tx_type: str):
    await state.clear()
    await state.update_data(type=tx_type)
    await state.set_state(TransactionStates.waiting_amount)
    await message.answer("Введите сумму операции:", reply_markup=cancel_kb())


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
        await message.answer("Введите корректную сумму больше 0. Например: 12 500,50")
        return
    await state.update_data(amount=amount)
    await state.set_state(TransactionStates.waiting_category)
    await message.answer("Введите категорию:", reply_markup=cancel_kb())


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
        today = date.today()
        await state.set_state(TransactionStates.waiting_manual_date)
        await message.answer(
            "Выберите дату в календаре или введите вручную: завтра, через 10 дней, 10.06 или 10.06.2026",
            reply_markup=calendar_back_kb(),
        )
        await message.answer("Календарь операций:", reply_markup=calendar_kb("tx", today.year, today.month))
        return
    await message.answer("Выберите: «Сегодня» или «Ввести дату».")


@router.callback_query(F.data.startswith("cal:tx:"))
async def transaction_calendar(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    try:
        _, _, action, year_raw, month_raw, day_raw = parts
        year = int(year_raw)
        month = int(month_raw)
        day = int(day_raw)
    except (ValueError, IndexError):
        await callback.answer("Не понял дату", show_alert=True)
        return

    if action == "noop":
        await callback.answer()
        return

    if action == "month":
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=calendar_kb("tx", year, month))
        await callback.answer()
        return

    if action != "select":
        await callback.answer()
        return

    try:
        op_date = date(year, month, day)
    except ValueError:
        await callback.answer("Не понял дату", show_alert=True)
        return

    await state.update_data(operation_date=op_date.isoformat())
    await state.set_state(TransactionStates.waiting_comment)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"Дата операции: {op_date.strftime('%d.%m.%Y')}\nВведите комментарий или нажмите «Пропустить».",
            reply_markup=skip_comment_kb(),
        )
    await callback.answer("Дата выбрана")


@router.message(TransactionStates.waiting_manual_date)
async def transaction_manual_date(message: Message, state: FSMContext):
    try:
        op_date = parse_date_ru(message.text.strip())
    except Exception:
        await message.answer("Не понял дату. Можно так: завтра, через 10 дней, 10.06 или 10.06.2026")
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
    await message.answer("Сохранено ✅")
    await _back_to_home(message, state)
