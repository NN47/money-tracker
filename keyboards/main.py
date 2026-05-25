from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💼 Главный экран")],
            [KeyboardButton(text="➕ Доход"), KeyboardButton(text="➖ Расход")],
            [KeyboardButton(text="📅 Предстоящий платёж")],
            [KeyboardButton(text="🔁 Постоянная операция")],
            [KeyboardButton(text="📊 Отчёт")],
        ],
        resize_keyboard=True,
    )


def skip_comment_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустить")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def date_choice_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Сегодня")], [KeyboardButton(text="Ввести дату")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def recurring_type_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Доход"), KeyboardButton(text="Расход"), KeyboardButton(text="Платёж")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def payment_done_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Оплачено", callback_data=f"pay_done:{payment_id}")]]
    )
