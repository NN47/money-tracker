from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

CANCEL_TEXT = "❌ Отмена"
MAIN_MENU_TEXTS = {
    "💼 Главный экран",
    "➕ Доход",
    "➖ Расход",
    "🔁 Регулярные платежи",
    "➕ Добавить платеж",
    "📊 Отчёт",
}


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💼 Главный экран")],
            [KeyboardButton(text="➕ Доход"), KeyboardButton(text="➖ Расход")],
            [KeyboardButton(text="🔁 Регулярные платежи")],
            [KeyboardButton(text="📊 Отчёт")],
        ],
        resize_keyboard=True,
    )


def recurring_payments_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить платеж")],
            [KeyboardButton(text="💼 Главный экран")],
            [KeyboardButton(text="📊 Отчёт")],
        ],
        resize_keyboard=True,
    )


def with_cancel_kb(*rows: list[KeyboardButton]) -> ReplyKeyboardMarkup:
    keyboard_rows = [list(row) for row in rows]
    keyboard_rows.append([KeyboardButton(text=CANCEL_TEXT)])
    return ReplyKeyboardMarkup(keyboard=keyboard_rows, resize_keyboard=True, one_time_keyboard=True)


def skip_comment_kb() -> ReplyKeyboardMarkup:
    return with_cancel_kb([KeyboardButton(text="Пропустить")])


def date_choice_kb() -> ReplyKeyboardMarkup:
    return with_cancel_kb([KeyboardButton(text="Сегодня")], [KeyboardButton(text="Ввести дату")])


def recurring_type_kb() -> ReplyKeyboardMarkup:
    return with_cancel_kb(
        [KeyboardButton(text="Доход"), KeyboardButton(text="Расход"), KeyboardButton(text="Платёж")]
    )


def payment_done_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Оплачено", callback_data=f"pay_done:{payment_id}")]]
    )


def recurring_due_kb(operations) -> InlineKeyboardMarkup | None:
    rows = []
    for operation in operations:
        operation_id = operation["id"]
        title = operation["title"]
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✅ Оплатил: {title}",
                    callback_data=f"pay_recurring:{operation_id}",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"⏰ Напомнить: {title}",
                    callback_data=f"remind_recurring:{operation_id}",
                )
            ]
        )
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb() -> ReplyKeyboardMarkup:
    return with_cancel_kb()
