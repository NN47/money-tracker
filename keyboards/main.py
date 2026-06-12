import calendar

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

CANCEL_TEXT = "❌ Отмена"
BACK_TEXT = "⬅️ Назад"
MAIN_MENU_TEXTS = {
    "💼 Главный экран",
    "➕ Доход",
    "➖ Расход",
    "🔁 Регулярные платежи",
    "➕ Добавить платеж",
    "📅 Календарь",
    "📊 Отчёт",
}


def calendar_back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BACK_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


MONTH_NAMES = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}
WEEKDAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def _calendar_callback(prefix: str, action: str, year: int, month: int, day: int = 0) -> str:
    return f"cal:{prefix}:{action}:{year}:{month}:{day}"


def calendar_kb(prefix: str, year: int, month: int, marked_days: set[int] | None = None) -> InlineKeyboardMarkup:
    marked_days = marked_days or set()
    previous_year, previous_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    rows = [
        [
            InlineKeyboardButton(
                text=f"{MONTH_NAMES[month]} {year}",
                callback_data=_calendar_callback(prefix, "noop", year, month),
            )
        ],
        [
            InlineKeyboardButton(
                text=weekday,
                callback_data=_calendar_callback(prefix, "noop", year, month),
            )
            for weekday in WEEKDAY_NAMES
        ],
    ]

    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        rows.append(
            [
                InlineKeyboardButton(
                    text=(f"• {day}" if day in marked_days else str(day)) if day else " ",
                    callback_data=_calendar_callback(
                        prefix,
                        "select" if day else "noop",
                        year,
                        month,
                        day,
                    ),
                )
                for day in week
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="◀️",
                callback_data=_calendar_callback(prefix, "month", previous_year, previous_month),
            ),
            InlineKeyboardButton(
                text="▶️",
                callback_data=_calendar_callback(prefix, "month", next_year, next_month),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💼 Главный экран")],
            [KeyboardButton(text="➕ Доход"), KeyboardButton(text="➖ Расход")],
            [KeyboardButton(text="🔁 Регулярные платежи")],
            [KeyboardButton(text="📅 Календарь")],
            [KeyboardButton(text="📊 Отчёт")],
        ],
        resize_keyboard=True,
    )


def recurring_payments_actions_kb(operations) -> InlineKeyboardMarkup | None:
    rows = []
    for operation in operations:
        operation_id = operation["id"]
        title = operation["title"]
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✏️ Редактировать: {title}",
                    callback_data=f"edit_recurring:{operation_id}",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 Удалить: {title}",
                    callback_data=f"delete_recurring:{operation_id}",
                )
            ]
        )
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def recurring_delete_confirm_kb(operation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, удалить",
                    callback_data=f"confirm_delete_recurring:{operation_id}",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"cancel_delete_recurring:{operation_id}",
                ),
            ]
        ]
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
