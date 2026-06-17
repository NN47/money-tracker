import asyncio
import logging
from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import dict_cursor, get_connection
from keyboards.main import (
    BACK_TEXT,
    CANCEL_TEXT,
    MAIN_MENU_TEXTS,
    calendar_back_kb,
    calendar_kb,
    cancel_kb,
    dashboard_actions_kb,
    main_menu_kb,
    payment_done_kb,
    recurring_delete_confirm_kb,
    recurring_due_kb,
    recurring_edit_fields_kb,
    recurring_payments_actions_kb,
    recurring_payments_menu_kb,
    recurring_type_edit_kb,
    recurring_type_kb,
    skip_comment_kb,
)
from services.calendar_events import (
    build_calendar_day_events,
    fetch_calendar_day_events,
    fetch_calendar_marked_days,
)
from services.dates import parse_future_date
from services.recurring_payments import (
    deactivate_recurring_operation,
    fetch_active_recurring_operation,
    fetch_all_active_recurring_operations,
    fetch_unpaid_due_recurring_payments,
    mark_recurring_payment_paid,
    mark_scheduled_payment_paid,
    moscow_today,
    update_recurring_operation,
)
from services.reports import build_dashboard, money

router = Router()
logger = logging.getLogger(__name__)

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


class RecurringEditStates(StatesGroup):
    waiting_title = State()
    waiting_amount = State()
    waiting_day = State()
    waiting_category = State()
    waiting_comment = State()


async def send_callback_message(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    if callback.message:
        try:
            await callback.message.answer(text, reply_markup=reply_markup)
            return
        except Exception:
            logger.exception("Failed to send callback reply in chat; falling back to private message")
    await callback.bot.send_message(callback.from_user.id, text, reply_markup=reply_markup)


async def remove_inline_keyboard(callback: CallbackQuery) -> None:
    if not callback.message:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception("Failed to remove inline keyboard after callback %s", callback.data)


def parse_money(raw: str) -> float:
    amount = float(raw.replace(" ", "").replace(",", "."))
    if amount <= 0:
        raise ValueError
    return round(amount, 2)


def parse_flexible_date(raw: str) -> date:
    return parse_future_date(raw)


async def _back_to_home(message: Message, state: FSMContext):
    await state.clear()
    unpaid_operations = fetch_unpaid_due_recurring_payments()
    due_kb = recurring_due_kb(unpaid_operations)
    extra_rows = due_kb.inline_keyboard if due_kb else None
    await message.answer(build_dashboard(), reply_markup=dashboard_actions_kb(extra_rows))
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


def calendar_events_kb(year: int, month: int):
    marked_days = fetch_calendar_marked_days(year, month)
    return calendar_kb("events", year, month, marked_days)


def recurring_kind_for_type(op_type: str | None) -> str:
    return "income" if op_type == "income" else "payment"


def build_recurring_operations_section(operations, kind: str = "payment") -> str:
    if not operations:
        if kind == "income":
            return "Регулярные доходы пока не добавлены. Нажмите «➕ Добавить регулярный доход», чтобы создать первый."
        return "Регулярные платежи пока не добавлены. Нажмите «➕ Добавить платеж», чтобы создать первый."

    type_labels = {
        "income": "доход",
        "expense": "расход",
        "payment": "платёж",
    }
    lines = ["🔁 Регулярные доходы:" if kind == "income" else "🔁 Регулярные платежи:"]
    for operation in operations:
        day = operation["day_of_month"]
        day_text = f"{day} число" if day else "без даты"
        type_text = type_labels.get(operation["type"], operation["type"])
        category = operation["category"] or "без категории"
        lines.append(
            f"• {day_text} — {operation['title']} — {money(float(operation['amount']))} ₽ "
            f"({type_text}, {category})"
        )
    return "\n".join(lines)


async def send_recurring_operations_section(message: Message, kind: str = "payment") -> None:
    operations = fetch_all_active_recurring_operations()
    if kind == "income":
        operations = [row for row in operations if row["type"] == "income"]
    else:
        operations = [row for row in operations if row["type"] in {"expense", "payment"}]
    await message.answer(
        build_recurring_operations_section(operations, kind=kind),
        reply_markup=recurring_payments_actions_kb(operations),
    )
    menu_title = "Меню регулярных доходов:" if kind == "income" else "Меню регулярных платежей:"
    await message.answer(menu_title, reply_markup=recurring_payments_menu_kb(kind))


def build_recurring_payment_notification(operations) -> str:
    today = moscow_today()
    has_overdue = any(row.get("payment_date") and row["payment_date"] < today for row in operations)
    lines = ["🔥 Вы не оплатили:" if has_overdue else "🔥 Сегодня к оплате:"]
    for row in operations:
        payment_date = row.get("payment_date")
        date_label = f" за {payment_date.strftime('%d.%m.%Y')}" if payment_date and payment_date < today else ""
        lines.append(f"• {row['title']}{date_label} — {money(float(row['amount']))} ₽")
    return "\n".join(lines)


async def send_recurring_payment_notification(bot: Bot, chat_id: int, operation_ids: list[int] | None = None) -> None:
    operations = fetch_unpaid_due_recurring_payments()
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
        RecurringEditStates.waiting_title,
        RecurringEditStates.waiting_amount,
        RecurringEditStates.waiting_day,
        RecurringEditStates.waiting_category,
        RecurringEditStates.waiting_comment,
    ),
    F.text == BACK_TEXT,
)
async def back_any(message: Message, state: FSMContext):
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
        RecurringEditStates.waiting_title,
        RecurringEditStates.waiting_amount,
        RecurringEditStates.waiting_day,
        RecurringEditStates.waiting_category,
        RecurringEditStates.waiting_comment,
    ),
    F.text.in_(MAIN_MENU_TEXTS),
)
async def menu_during_fsm(message: Message, state: FSMContext):
    await state.clear()


@router.message(F.text == "📅 Календарь")
async def calendar_events_start(message: Message, state: FSMContext):
    await state.clear()
    today = date.today()
    await message.answer(
        "📅 Календарь событий. Дни с событиями отмечены точкой. Выберите дату, чтобы посмотреть детали.",
        reply_markup=main_menu_kb(),
    )
    await message.answer("Календарь:", reply_markup=calendar_events_kb(today.year, today.month))


@router.callback_query(F.data.startswith("cal:events:"))
async def calendar_events(callback: CallbackQuery):
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
            await callback.message.edit_reply_markup(reply_markup=calendar_events_kb(year, month))
        await callback.answer()
        return

    if action != "select":
        await callback.answer()
        return

    try:
        selected_date = date(year, month, day)
    except ValueError:
        await callback.answer("Не понял дату", show_alert=True)
        return

    events = fetch_calendar_day_events(selected_date)
    await send_callback_message(callback, build_calendar_day_events(selected_date, events), reply_markup=main_menu_kb())
    await callback.answer("События загружены")


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
    today = date.today()
    await state.set_state(ScheduledPaymentStates.waiting_date)
    await message.answer(
        "Выберите дату платежа в календаре или введите вручную: завтра, через 10 дней, 10.06 или 10.06.2026",
        reply_markup=calendar_back_kb(),
    )
    await message.answer("Календарь платежей:", reply_markup=calendar_kb("pay", today.year, today.month))


@router.callback_query(F.data.startswith("cal:pay:"))
async def payment_calendar(callback: CallbackQuery, state: FSMContext):
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
            await callback.message.edit_reply_markup(reply_markup=calendar_kb("pay", year, month))
        await callback.answer()
        return

    if action != "select":
        await callback.answer()
        return

    try:
        selected_date = date(year, month, day)
    except ValueError:
        await callback.answer("Не понял дату", show_alert=True)
        return

    await state.update_data(payment_date=selected_date.isoformat())
    await state.set_state(ScheduledPaymentStates.waiting_comment)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"Дата платежа: {selected_date.strftime('%d.%m.%Y')}\nВведите комментарий или нажмите «Пропустить».",
            reply_markup=skip_comment_kb(),
        )
    await callback.answer("Дата выбрана")


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
    try:
        payment_id = int(callback.data.split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        await callback.answer("Не понял, какой платёж отметить", show_alert=True)
        return

    await callback.answer("Отмечаю платёж…")

    try:
        result = mark_scheduled_payment_paid(payment_id)
    except Exception:
        logger.exception("Failed to mark scheduled payment %s as paid", payment_id)
        await send_callback_message(callback, "Не получилось отметить платёж и записать расход. Попробуйте ещё раз.")
        return

    if result["status"] != "paid":
        await send_callback_message(callback, "Этот платёж не найден или уже оплачен.")
        return

    await remove_inline_keyboard(callback)
    await send_callback_message(
        callback,
        f"Платёж «{result['title']}» отмечен как оплаченный и записан в расходы ✅",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data.startswith("pay_recurring:"))
async def recurring_payment_mark_paid(callback: CallbackQuery):
    try:
        parts = callback.data.split(":")
        operation_id = int(parts[1])
        payment_date = date.fromisoformat(parts[2]) if len(parts) > 2 else None
    except (IndexError, ValueError):
        await callback.answer("Не понял, какой платёж отметить", show_alert=True)
        return

    await callback.answer("Записываю платёж…")

    try:
        result = mark_recurring_payment_paid(operation_id, payment_date)
    except Exception:
        logger.exception("Failed to mark recurring operation %s as paid", operation_id)
        await send_callback_message(callback, "Не получилось записать платёж в расходы. Попробуйте ещё раз.")
        return

    status = result["status"]

    if status == "paid":
        title = result["title"]
        await remove_inline_keyboard(callback)
        unpaid_operations = fetch_unpaid_due_recurring_payments()
        await send_callback_message(
            callback,
            f"Платёж «{title}» записан в расходы ✅",
            reply_markup=main_menu_kb(),
        )
        await send_callback_message(callback, build_dashboard(), reply_markup=recurring_due_kb(unpaid_operations))
        return

    if status == "already_paid":
        await remove_inline_keyboard(callback)
        unpaid_operations = fetch_unpaid_due_recurring_payments()
        await send_callback_message(callback, "Этот платёж уже учтён ✅", reply_markup=main_menu_kb())
        await send_callback_message(callback, build_dashboard(), reply_markup=recurring_due_kb(unpaid_operations))
        return

    await send_callback_message(callback, "Этот платёж не найден или отключён.")


@router.callback_query(F.data.startswith("remind_recurring:"))
async def recurring_payment_remind_later(callback: CallbackQuery):
    operation_id = int(callback.data.split(":", maxsplit=1)[1])
    chat_id = OWNER_TELEGRAM_ID or callback.from_user.id
    asyncio.create_task(remind_later(callback.bot, chat_id, operation_id))
    await callback.answer("Напомню через час ⏰")


@router.callback_query(F.data.startswith("edit_recurring:"))
async def recurring_edit_start(callback: CallbackQuery, state: FSMContext):
    try:
        operation_id = int(callback.data.split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        await callback.answer("Не понял, какой платёж редактировать", show_alert=True)
        return

    operation = fetch_active_recurring_operation(operation_id)
    if not operation:
        await callback.answer("Этот платёж не найден или уже удалён", show_alert=True)
        return

    await state.clear()
    await callback.answer("Редактируем платёж")
    await remove_inline_keyboard(callback)
    await send_callback_message(
        callback,
        f"Редактируем регулярный платёж «{operation['title']}».\nЧто хотите изменить?",
        reply_markup=recurring_edit_fields_kb(operation_id),
    )


RECURRING_EDIT_FIELD_PROMPTS = {
    "title": "Введите новое название:",
    "amount": "Введите новую сумму:",
    "day": "Введите новый день месяца (1-31):",
    "category": "Введите новую категорию:",
    "comment": "Введите новый комментарий или «Пропустить».",
}

RECURRING_EDIT_FIELD_STATES = {
    "title": RecurringEditStates.waiting_title,
    "amount": RecurringEditStates.waiting_amount,
    "day": RecurringEditStates.waiting_day,
    "category": RecurringEditStates.waiting_category,
    "comment": RecurringEditStates.waiting_comment,
}


def _update_recurring_field(operation_id: int, field: str, value) -> bool:
    operation = fetch_active_recurring_operation(operation_id)
    if not operation:
        return False

    title = operation["title"]
    op_type = operation["type"]
    amount = float(operation["amount"])
    category = operation["category"]
    day_of_month = operation["day_of_month"]
    comment = operation["comment"]

    if field == "title":
        title = value
    elif field == "type":
        op_type = value
    elif field == "amount":
        amount = value
    elif field == "category":
        category = value
    elif field == "day":
        day_of_month = value
    elif field == "comment":
        comment = value
    else:
        return False

    return update_recurring_operation(operation_id, title, op_type, amount, category, day_of_month, comment)


@router.callback_query(F.data.startswith("edit_recurring_field:"))
async def recurring_edit_field(callback: CallbackQuery, state: FSMContext):
    try:
        _, operation_id_raw, field = callback.data.split(":", maxsplit=2)
        operation_id = int(operation_id_raw)
    except (AttributeError, ValueError):
        await callback.answer("Не понял, что редактировать", show_alert=True)
        return

    if not fetch_active_recurring_operation(operation_id):
        await callback.answer("Этот платёж не найден или уже удалён", show_alert=True)
        return

    if field == "type":
        await state.clear()
        await callback.answer("Выберите тип")
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("Выберите новый тип операции:", reply_markup=recurring_type_edit_kb(operation_id))
        return

    if field not in RECURRING_EDIT_FIELD_STATES:
        await callback.answer("Такое поле нельзя изменить", show_alert=True)
        return

    await state.clear()
    await state.update_data(edit_operation_id=operation_id, edit_field=field)
    await state.set_state(RECURRING_EDIT_FIELD_STATES[field])
    await callback.answer("Введите новое значение")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(RECURRING_EDIT_FIELD_PROMPTS[field])


@router.callback_query(F.data.startswith("edit_recurring_type:"))
async def recurring_edit_type(callback: CallbackQuery):
    try:
        _, operation_id_raw, op_type = callback.data.split(":", maxsplit=2)
        operation_id = int(operation_id_raw)
    except (AttributeError, ValueError):
        await callback.answer("Не понял тип платежа", show_alert=True)
        return

    if op_type not in {"income", "expense", "payment"}:
        await callback.answer("Не понял тип платежа", show_alert=True)
        return

    if not _update_recurring_field(operation_id, "type", op_type):
        await callback.answer("Платёж не найден", show_alert=True)
        return

    await callback.answer("Тип сохранён")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Изменения сохранены ✅")
        await send_recurring_operations_section(callback.message, kind=recurring_kind_for_type(op_type))


async def _save_recurring_edited_field(message: Message, state: FSMContext, field: str, value) -> None:
    data = await state.get_data()
    operation_id = data.get("edit_operation_id")
    operation_kind = "payment"
    if not operation_id or not _update_recurring_field(operation_id, field, value):
        await message.answer("Этот платёж не найден или уже удалён.")
    else:
        updated_operation = fetch_active_recurring_operation(operation_id)
        operation_kind = recurring_kind_for_type(updated_operation["type"] if updated_operation else None)
        await message.answer("Изменения сохранены ✅")
    await state.clear()
    await send_recurring_operations_section(message, kind=operation_kind)


@router.message(RecurringEditStates.waiting_title)
async def recurring_edit_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    await _save_recurring_edited_field(message, state, "title", title)


@router.message(RecurringEditStates.waiting_amount)
async def recurring_edit_amount(message: Message, state: FSMContext):
    try:
        amount = parse_money(message.text)
    except Exception:
        await message.answer("Введите корректную сумму больше 0.")
        return
    await _save_recurring_edited_field(message, state, "amount", amount)


@router.message(RecurringEditStates.waiting_day)
async def recurring_edit_day(message: Message, state: FSMContext):
    try:
        day = int(message.text)
        if day < 1 or day > 31:
            raise ValueError
    except Exception:
        await message.answer("Введите число от 1 до 31.")
        return
    await _save_recurring_edited_field(message, state, "day", day)


@router.message(RecurringEditStates.waiting_category)
async def recurring_edit_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("Категория не может быть пустой.")
        return
    await _save_recurring_edited_field(message, state, "category", category)


@router.message(RecurringEditStates.waiting_comment)
async def recurring_edit_comment(message: Message, state: FSMContext):
    comment = None if message.text == "Пропустить" else message.text.strip()
    await _save_recurring_edited_field(message, state, "comment", comment)


@router.callback_query(F.data.startswith("delete_recurring:"))
async def recurring_delete_ask_confirmation(callback: CallbackQuery):
    try:
        operation_id = int(callback.data.split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        await callback.answer("Не понял, какой платёж удалить", show_alert=True)
        return

    operation = fetch_active_recurring_operation(operation_id)
    if not operation:
        await callback.answer("Этот платёж не найден или уже удалён", show_alert=True)
        return

    await callback.answer()
    await send_callback_message(
        callback,
        f"Вы точно хотите удалить регулярный платёж «{operation['title']}»?",
        reply_markup=recurring_delete_confirm_kb(operation_id),
    )


@router.callback_query(F.data.startswith("cancel_delete_recurring:"))
async def recurring_delete_cancel(callback: CallbackQuery):
    await callback.answer("Удаление отменено")
    await remove_inline_keyboard(callback)
    await send_callback_message(callback, "Удаление отменено.", reply_markup=main_menu_kb())


@router.callback_query(F.data.startswith("confirm_delete_recurring:"))
async def recurring_delete_confirm(callback: CallbackQuery):
    try:
        operation_id = int(callback.data.split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        await callback.answer("Не понял, какой платёж удалить", show_alert=True)
        return

    try:
        deleted = deactivate_recurring_operation(operation_id)
    except Exception:
        logger.exception("Failed to delete recurring operation %s", operation_id)
        await send_callback_message(callback, "Не получилось удалить платёж. Попробуйте ещё раз.")
        return

    await remove_inline_keyboard(callback)
    if not deleted:
        await callback.answer("Платёж не найден", show_alert=True)
        await send_callback_message(callback, "Этот платёж не найден или уже удалён.", reply_markup=main_menu_kb())
        return

    await callback.answer("Удалено")
    await send_callback_message(callback, f"Регулярный платёж «{deleted['title']}» удалён 🗑", reply_markup=main_menu_kb())
    operations = fetch_all_active_recurring_operations()
    await send_callback_message(
        callback,
        build_recurring_operations_section(operations),
        reply_markup=recurring_payments_actions_kb(operations),
    )


@router.message(F.text == "🔁 Регулярные платежи")
async def recurring_payments_section(message: Message, state: FSMContext):
    await state.clear()
    await send_recurring_operations_section(message, kind="payment")


@router.message(F.text == "🔁 Регулярные доходы")
async def recurring_incomes_section(message: Message, state: FSMContext):
    await state.clear()
    await send_recurring_operations_section(message, kind="income")


@router.message(F.text == "➕ Добавить регулярный доход")
async def recurring_income_start(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(type="income")
    await state.set_state(RecurringStates.waiting_title)
    await message.answer("Введите название:", reply_markup=cancel_kb())


@router.message(F.text == "➕ Добавить платеж")
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
    today = date.today()
    await state.set_state(RecurringStates.waiting_day)
    await message.answer(
        "Выберите день платежа в календаре или введите число месяца (1-31):",
        reply_markup=calendar_back_kb(),
    )
    await message.answer("Календарь регулярных платежей:", reply_markup=calendar_kb("rec", today.year, today.month))


@router.callback_query(F.data.startswith("cal:rec:"))
async def recurring_calendar(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    try:
        _, _, action, year_raw, month_raw, day_raw = parts
        year = int(year_raw)
        month = int(month_raw)
        day = int(day_raw)
    except (ValueError, IndexError):
        await callback.answer("Не понял день", show_alert=True)
        return

    if action == "noop":
        await callback.answer()
        return

    if action == "month":
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=calendar_kb("rec", year, month))
        await callback.answer()
        return

    if action != "select" or day < 1 or day > 31:
        await callback.answer("Выберите день месяца", show_alert=True)
        return

    await state.update_data(day_of_month=day)
    await state.set_state(RecurringStates.waiting_category)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(f"День платежа: {day}. Введите категорию:", reply_markup=cancel_kb())
    await callback.answer("День выбран")


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
    edit_operation_id = data.get("edit_operation_id")

    if edit_operation_id:
        updated = update_recurring_operation(
            edit_operation_id,
            data["title"],
            data["type"],
            data["amount"],
            data["category"],
            data["day_of_month"],
            comment,
        )
        if updated:
            await message.answer("Изменения сохранены ✅")
        else:
            await message.answer("Этот платёж не найден или уже удалён.")
    else:
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

    await state.clear()
    await send_recurring_operations_section(message, kind=recurring_kind_for_type(data.get("type")))


@router.message(F.text == "📅 Ближайшие платежи")
async def list_payments(message: Message):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute("SELECT id, title, amount, payment_date FROM scheduled_payments WHERE is_paid = FALSE ORDER BY payment_date ASC LIMIT 10")
        rows = cur.fetchall()
        cur.close()
    if not rows:
        await message.answer("Нет платежей.")
        return
    for row in rows:
        txt = f"{row['payment_date'].strftime('%d.%m')} — {row['title']} — {money(float(row['amount']))} ₽"
        await message.answer(txt, reply_markup=payment_done_kb(row['id']))
