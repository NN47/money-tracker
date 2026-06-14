import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import dict_cursor, get_connection
from keyboards.main import (
    BACK_TEXT,
    main_menu_kb,
    report_delete_confirm_kb,
    report_edit_fields_kb,
    report_menu_kb,
    report_transactions_kb,
    transaction_type_edit_kb,
)
from services.dates import parse_transaction_date
from services.reports import (
    build_dashboard,
    build_summary_report,
    build_transactions_report,
    fetch_recent_transactions,
    money,
)

router = Router()


class ReportTransactionStates(StatesGroup):
    waiting_amount = State()
    waiting_category = State()
    waiting_date = State()
    waiting_comment = State()


EDIT_FIELD_PROMPTS = {
    "amount": "Введите новую сумму:",
    "category": "Введите новую категорию:",
    "date": "Введите дату операции: сегодня, вчера, 10.06 или 10.06.2026",
    "comment": "Введите новый комментарий или «Пропустить».",
}

EDIT_FIELD_STATES = {
    "amount": ReportTransactionStates.waiting_amount,
    "category": ReportTransactionStates.waiting_category,
    "date": ReportTransactionStates.waiting_date,
    "comment": ReportTransactionStates.waiting_comment,
}


def _type_label(tx_type: str) -> str:
    return "доход" if tx_type == "income" else "расход"


def _format_transaction_details(transaction) -> str:
    sign = "+" if transaction["type"] == "income" else "-"
    comment = transaction.get("comment") or "без комментария"
    return (
        f"<b>{html.escape(_type_label(transaction['type']).capitalize())}</b>\n"
        f"Сумма: <b>{sign}{money(float(transaction['amount']))} ₽</b>\n"
        f"Категория: <b>{html.escape(transaction['category'] or 'Без категории')}</b>\n"
        f"Дата: <b>{transaction['operation_date'].strftime('%d.%m.%Y')}</b>\n"
        f"Комментарий: {html.escape(comment)}"
    )


def _parse_money(raw: str) -> float:
    amount = float(raw.replace(" ", "").replace(",", "."))
    if amount <= 0:
        raise ValueError
    return round(amount, 2)


async def _send_report(message: Message) -> None:
    transactions = fetch_recent_transactions()
    await message.answer("Меню отчёта:", reply_markup=report_menu_kb())
    await message.answer(
        build_summary_report(transactions=transactions),
        reply_markup=report_transactions_kb(transactions),
        parse_mode="HTML",
    )


@router.message(F.text == "📊 Отчёт")
async def report(message: Message, state: FSMContext):
    await state.clear()
    await _send_report(message)


@router.message(F.text == "📋 Все операции")
async def all_transactions(message: Message, state: FSMContext):
    await state.clear()
    transactions = fetch_recent_transactions(limit=50)
    await message.answer(
        build_transactions_report(transactions=transactions),
        reply_markup=report_transactions_kb(transactions),
        parse_mode="HTML",
    )


@router.message(F.text == BACK_TEXT)
async def report_back(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return
    await message.answer(build_dashboard(), reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("report_tx:"))
async def report_transaction_actions(callback: CallbackQuery):
    try:
        transaction_id = int(callback.data.split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        await callback.answer("Не понял операцию", show_alert=True)
        return

    transaction = _fetch_transaction(transaction_id)
    if not transaction:
        await callback.answer("Операция не найдена", show_alert=True)
        return

    await callback.answer("Операция выбрана")
    if callback.message:
        await callback.message.answer(
            _format_transaction_details(transaction),
            reply_markup=report_delete_confirm_kb(transaction_id, include_edit=True),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("edit_tx:"))
async def edit_transaction_start(callback: CallbackQuery, state: FSMContext):
    try:
        transaction_id = int(callback.data.split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        await callback.answer("Не понял операцию", show_alert=True)
        return

    transaction = _fetch_transaction(transaction_id)
    if not transaction:
        await callback.answer("Операция не найдена", show_alert=True)
        return

    await state.clear()
    await callback.answer("Редактируем операцию")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"Редактируем операцию от {transaction['operation_date'].strftime('%d.%m.%Y')}.\n"
            "Что хотите изменить?",
            reply_markup=report_edit_fields_kb(transaction_id),
        )


@router.callback_query(F.data.startswith("edit_tx_field:"))
async def edit_transaction_field(callback: CallbackQuery, state: FSMContext):
    try:
        _, transaction_id_raw, field = callback.data.split(":", maxsplit=2)
        transaction_id = int(transaction_id_raw)
    except (AttributeError, ValueError):
        await callback.answer("Не понял, что редактировать", show_alert=True)
        return

    transaction = _fetch_transaction(transaction_id)
    if not transaction:
        await callback.answer("Операция не найдена", show_alert=True)
        return

    if field == "type":
        await state.clear()
        await callback.answer("Выберите тип")
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("Выберите новый тип операции:", reply_markup=transaction_type_edit_kb(transaction_id))
        return

    if field not in EDIT_FIELD_STATES:
        await callback.answer("Такое поле нельзя изменить", show_alert=True)
        return

    await state.clear()
    await state.update_data(edit_transaction_id=transaction_id, edit_field=field)
    await state.set_state(EDIT_FIELD_STATES[field])
    await callback.answer("Введите новое значение")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(EDIT_FIELD_PROMPTS[field])


@router.callback_query(F.data.startswith("edit_tx_type:"))
async def edit_transaction_type(callback: CallbackQuery):
    try:
        _, transaction_id_raw, tx_type = callback.data.split(":", maxsplit=2)
        transaction_id = int(transaction_id_raw)
    except (AttributeError, ValueError):
        await callback.answer("Не понял тип операции", show_alert=True)
        return

    if tx_type not in {"income", "expense"}:
        await callback.answer("Не понял тип операции", show_alert=True)
        return

    if not _update_transaction_field(transaction_id, "type", tx_type):
        await callback.answer("Операция не найдена", show_alert=True)
        return

    await callback.answer("Тип сохранён")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Изменения сохранены ✅")


@router.callback_query(F.data.startswith("delete_tx:"))
async def delete_transaction_ask(callback: CallbackQuery):
    try:
        transaction_id = int(callback.data.split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        await callback.answer("Не понял операцию", show_alert=True)
        return

    transaction = _fetch_transaction(transaction_id)
    if not transaction:
        await callback.answer("Операция не найдена", show_alert=True)
        return

    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Удалить операцию «{html.escape(transaction['category'] or 'Без категории')} — "
            f"{money(float(transaction['amount']))} ₽»?",
            reply_markup=report_delete_confirm_kb(transaction_id),
        )


@router.callback_query(F.data.startswith("cancel_delete_tx:"))
async def delete_transaction_cancel(callback: CallbackQuery):
    await callback.answer("Удаление отменено")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Удаление отменено.")


@router.callback_query(F.data.startswith("confirm_delete_tx:"))
async def delete_transaction_confirm(callback: CallbackQuery):
    try:
        transaction_id = int(callback.data.split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        await callback.answer("Не понял операцию", show_alert=True)
        return

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions WHERE id = %s RETURNING category", (transaction_id,))
        deleted = cur.fetchone()
        cur.close()

    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
    if not deleted:
        await callback.answer("Операция не найдена", show_alert=True)
        return
    await callback.answer("Удалено")
    if callback.message:
        await callback.message.answer("Операция удалена 🗑")
        await callback.message.answer(
            build_summary_report(),
            reply_markup=report_transactions_kb(fetch_recent_transactions()),
            parse_mode="HTML",
        )


@router.message(ReportTransactionStates.waiting_amount)
async def edit_transaction_amount(message: Message, state: FSMContext):
    try:
        amount = _parse_money(message.text)
    except Exception:
        await message.answer("Введите корректную сумму больше 0. Например: 12 500,50")
        return
    await state.update_data(amount=amount)
    if await _finish_single_field_edit(message, state, "amount", amount):
        return
    await state.set_state(ReportTransactionStates.waiting_category)
    await message.answer("Введите новую категорию:")


@router.message(ReportTransactionStates.waiting_category)
async def edit_transaction_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("Категория не может быть пустой.")
        return
    await state.update_data(category=category)
    if await _finish_single_field_edit(message, state, "category", category):
        return
    await state.set_state(ReportTransactionStates.waiting_date)
    await message.answer("Введите дату операции: сегодня, вчера, 10.06 или 10.06.2026")


@router.message(ReportTransactionStates.waiting_date)
async def edit_transaction_date(message: Message, state: FSMContext):
    try:
        operation_date = parse_transaction_date(message.text.strip())
    except Exception:
        await message.answer("Не понял дату. Можно так: сегодня, вчера, 10.06 или 10.06.2026")
        return
    await state.update_data(operation_date=operation_date.isoformat())
    if await _finish_single_field_edit(message, state, "operation_date", operation_date.isoformat()):
        return
    await state.set_state(ReportTransactionStates.waiting_comment)
    await message.answer("Введите новый комментарий или «Пропустить».")


@router.message(ReportTransactionStates.waiting_comment)
async def edit_transaction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = None if message.text == "Пропустить" else message.text.strip()
    if await _finish_single_field_edit(message, state, "comment", comment):
        return
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE transactions
            SET amount = %s, category = %s, operation_date = %s, comment = %s
            WHERE id = %s
            """,
            (data["amount"], data["category"], data["operation_date"], comment, data["edit_transaction_id"]),
        )
        cur.close()
    await state.clear()
    await message.answer("Изменения сохранены ✅")
    await _send_report(message)


def _fetch_transaction(transaction_id: int):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute(
            "SELECT id, type, amount, category, comment, operation_date FROM transactions WHERE id = %s",
            (transaction_id,),
        )
        transaction = cur.fetchone()
        cur.close()
    return transaction


def _update_transaction_field(transaction_id: int, field: str, value) -> bool:
    allowed_fields = {"type", "amount", "category", "operation_date", "comment"}
    if field not in allowed_fields:
        raise ValueError(f"Unsupported transaction field: {field}")
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE transactions SET {field} = %s WHERE id = %s", (value, transaction_id))
        updated = cur.rowcount > 0
        cur.close()
    return updated


async def _finish_single_field_edit(message: Message, state: FSMContext, field: str, value) -> bool:
    data = await state.get_data()
    if not data.get("edit_field"):
        return False

    updated = _update_transaction_field(data["edit_transaction_id"], field, value)
    await state.clear()
    if updated:
        await message.answer("Изменения сохранены ✅")
        await _send_report(message)
    else:
        await message.answer("Операция не найдена.")
    return True
