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
    back_kb,
    calendar_kb,
    category_choice_back_kb,
    date_choice_back_kb,
    main_menu_kb,
    section_menu_kb,
    skip_comment_back_kb,
)
from services.currencies import extract_currency
from services.dates import parse_transaction_date
from services.users import get_user_default_currency
from handlers.home import send_main_screen
from services.reports import build_summary_report, fetch_categories, fetch_recent_transactions

router = Router()

AMOUNT_PROMPT = (
    "Введите сумму. Если валюту не указать, операция будет записана в валюте по умолчанию. "
    "Изменить валюту можно в ⚙️ Настройках."
)


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


def parse_amount_text(raw: str) -> tuple[float, str | None, str]:
    currency, cleaned = extract_currency(raw)
    parts = cleaned.split(maxsplit=1)
    if not parts:
        raise ValueError
    amount = parse_money(parts[0])
    tail = parts[1].strip() if len(parts) > 1 else ""
    return amount, currency, tail


def parse_date_ru(raw: str) -> date:
    return parse_transaction_date(raw)


async def _back_to_home(message: Message, state: FSMContext):
    await send_main_screen(message, state)


@router.message(F.text == CANCEL_TEXT)
async def cancel_any(message: Message, state: FSMContext):
    await _back_to_home(message, state)


@router.message(
    StateFilter(
        TransactionStates.waiting_amount,
        TransactionStates.waiting_category,
        TransactionStates.waiting_date_choice,
        TransactionStates.waiting_manual_date,
        TransactionStates.waiting_comment,
    ),
    F.text == BACK_TEXT,
)
async def back_any(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == TransactionStates.waiting_amount.state:
        data = await state.get_data()
        if data.get("type") == "expense":
            await expense_section(message, state)
        elif data.get("type") == "income":
            await income_section(message, state)
        else:
            await _back_to_home(message, state)
        return

    if current_state == TransactionStates.waiting_category.state:
        await state.set_state(TransactionStates.waiting_amount)
        await message.answer(AMOUNT_PROMPT, reply_markup=back_kb())
        return

    if current_state == TransactionStates.waiting_date_choice.state:
        await state.set_state(TransactionStates.waiting_category)
        await _ask_category(message, state)
        return

    if current_state == TransactionStates.waiting_manual_date.state:
        await state.set_state(TransactionStates.waiting_date_choice)
        await message.answer("Дата операции:", reply_markup=date_choice_back_kb())
        return

    if current_state == TransactionStates.waiting_comment.state:
        await state.set_state(TransactionStates.waiting_date_choice)
        await message.answer("Дата операции:", reply_markup=date_choice_back_kb())
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
    await message.answer(AMOUNT_PROMPT, reply_markup=back_kb())


@router.message(F.text == "💰 Доходы")
async def income_section(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(report_scope="income")
    transactions = fetch_recent_transactions(tx_type="income")
    await message.answer(build_summary_report(transactions=transactions, tx_type="income"), reply_markup=section_menu_kb("income"), parse_mode="HTML")


@router.message(F.text == "💸 Расходы")
async def expense_section(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(report_scope="expense")
    transactions = fetch_recent_transactions(tx_type="expense")
    await message.answer(build_summary_report(transactions=transactions, tx_type="expense"), reply_markup=section_menu_kb("expense"), parse_mode="HTML")


@router.message(F.text.in_({"➕ Доход", "➕ Добавить доход"}))
async def add_income(message: Message, state: FSMContext):
    await _start_transaction(message, state, "income")


@router.message(F.text.in_({"➖ Расход", "➖ Добавить расход"}))
async def add_expense(message: Message, state: FSMContext):
    await _start_transaction(message, state, "expense")


@router.callback_query(F.data.startswith("quick_tx:"))
async def quick_transaction(callback: CallbackQuery, state: FSMContext):
    tx_type = callback.data.split(":", maxsplit=1)[1]
    if tx_type not in {"income", "expense"}:
        await callback.answer("Не понял тип операции", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await _start_transaction(callback.message, state, tx_type)


async def _ask_category(message: Message, state: FSMContext, prompt: str = "Выберите категорию кнопкой или введите новую текстом:"):
    data = await state.get_data()
    categories = [row["category"] for row in fetch_categories(tx_type=data.get("type"))]
    await message.answer(prompt, reply_markup=category_choice_back_kb(categories))


@router.message(TransactionStates.waiting_amount)
async def transaction_amount(message: Message, state: FSMContext):
    try:
        amount, extracted_currency, category = parse_amount_text(message.text or "")
    except Exception:
        await message.answer("Введите корректную сумму больше 0. Например: 12 500,50 или 500 грн продукты")
        return
    default_currency = get_user_default_currency(message.from_user.id if message.from_user else None)
    currency = extracted_currency or default_currency or "RUB"
    await state.update_data(amount=amount, currency=currency)
    if category:
        await state.update_data(category=category)
        await state.set_state(TransactionStates.waiting_date_choice)
        await message.answer("Дата операции:", reply_markup=date_choice_back_kb())
        return
    await state.set_state(TransactionStates.waiting_category)
    await _ask_category(message, state)


@router.message(TransactionStates.waiting_category)
async def transaction_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if category == "✏️ Новая категория":
        await message.answer("Введите новую категорию:", reply_markup=back_kb())
        return
    if not category:
        await message.answer("Категория не может быть пустой.")
        return
    await state.update_data(category=category)
    await state.set_state(TransactionStates.waiting_date_choice)
    await message.answer("Дата операции:", reply_markup=date_choice_back_kb())


@router.message(TransactionStates.waiting_date_choice)
async def transaction_date_choice(message: Message, state: FSMContext):
    if message.text == "Сегодня":
        await state.update_data(operation_date=date.today().isoformat())
        await state.set_state(TransactionStates.waiting_comment)
        await message.answer("Введите комментарий или нажмите «Пропустить».", reply_markup=skip_comment_back_kb())
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
            reply_markup=skip_comment_back_kb(),
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
    await message.answer("Введите комментарий или нажмите «Пропустить».", reply_markup=skip_comment_back_kb())


@router.message(TransactionStates.waiting_comment)
async def transaction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = None if message.text == "Пропустить" else message.text.strip()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO transactions(type, amount, currency, category, comment, operation_date)
            VALUES(%s, %s, %s, %s, %s, %s)
            """,
            (data["type"], data["amount"], data.get("currency") or "RUB", data["category"], comment, data["operation_date"]),
        )
        cur.close()
    await message.answer("Сохранено ✅")
    await _back_to_home(message, state)
