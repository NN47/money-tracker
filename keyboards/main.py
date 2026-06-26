import calendar
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

CANCEL_TEXT = "❌ Отмена"
BACK_TEXT = "⬅️ Назад"
HOME_TEXT = "🏠 Главное меню"
MAIN_MENU_TEXTS = {
    "💼 Главный экран",
    HOME_TEXT,
    "💰 Доходы",
    "💸 Расходы",
    "➕ Доход",
    "➖ Расход",
    "➕ Добавить доход",
    "➖ Добавить расход",
    "🔁 Регулярные доходы",
    "🔁 Регулярные платежи",
    "➕ Добавить регулярный доход",
    "➕ Добавить платеж",
    "📅 Календарь",
    "📊 Отчёт",
    "📊 Отчёт по доходам",
    "📊 Отчёт по расходам",
    "📂 Категории",
    "⚙️ Настройки",
    "💱 Валюта по умолчанию",
}


def calendar_back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BACK_TEXT), KeyboardButton(text=HOME_TEXT)]],
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


def _format_calendar_day(day: int, mark: str | None, is_today: bool) -> str:
    text = f"{day} {mark}" if mark else str(day)
    if is_today:
        return f"📍 {text}"
    return text


def calendar_kb(
    prefix: str,
    year: int,
    month: int,
    marked_days: set[int] | dict[int, str] | None = None,
) -> InlineKeyboardMarkup:
    marked_days = marked_days or set()
    day_marks = marked_days if isinstance(marked_days, dict) else {day: "•" for day in marked_days}
    today = date.today()
    previous_year, previous_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    rows = [
        [
            InlineKeyboardButton(
                text=f"🗓 {MONTH_NAMES[month].upper()} {year}",
                callback_data=_calendar_callback(prefix, "noop", year, month),
            )
        ],
        [
            InlineKeyboardButton(
                text=f"▪️{weekday}",
                callback_data=_calendar_callback(prefix, "noop", year, month),
            )
            for weekday in WEEKDAY_NAMES
        ],
    ]

    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row = []
        for day in week:
            if not day:
                if row:
                    continue
                row.append(
                    InlineKeyboardButton(
                        text="·",
                        callback_data=_calendar_callback(prefix, "noop", year, month),
                    )
                )
                continue

            row.append(
                InlineKeyboardButton(
                    text=_format_calendar_day(day, day_marks.get(day), today == date(year, month, day)),
                    callback_data=_calendar_callback(prefix, "select", year, month, day),
                )
            )
        if row:
            rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Пред.",
                callback_data=_calendar_callback(prefix, "month", previous_year, previous_month),
            ),
            InlineKeyboardButton(
                text="След. ➡️",
                callback_data=_calendar_callback(prefix, "month", next_year, next_month),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Доходы"), KeyboardButton(text="💸 Расходы")],
            [KeyboardButton(text="📅 Календарь"), KeyboardButton(text="📊 Отчёт")],
            [KeyboardButton(text="💼 Главный экран"), KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )


def dashboard_actions_kb(extra_rows: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="+", callback_data="quick_tx:income"),
            InlineKeyboardButton(text="-", callback_data="quick_tx:expense"),
        ]
    ]
    if extra_rows:
        rows.extend(extra_rows)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def section_menu_kb(kind: str) -> ReplyKeyboardMarkup:
    if kind == "income":
        rows = [
            [KeyboardButton(text="➕ Добавить доход")],
            [KeyboardButton(text="📊 Отчёт по доходам")],
            [KeyboardButton(text="📂 Категории")],
            [KeyboardButton(text="🔁 Регулярные доходы")],
            [KeyboardButton(text=BACK_TEXT)],
        ]
    else:
        rows = [
            [KeyboardButton(text="➖ Добавить расход")],
            [KeyboardButton(text="📊 Отчёт по расходам")],
            [KeyboardButton(text="📂 Категории")],
            [KeyboardButton(text="🔁 Регулярные платежи")],
            [KeyboardButton(text=BACK_TEXT)],
        ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


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
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def recurring_edit_fields_kb(operation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Сумма", callback_data=f"edit_recurring_field:{operation_id}:amount"),
                InlineKeyboardButton(text="📂 Категория", callback_data=f"edit_recurring_field:{operation_id}:category"),
            ],
            [
                InlineKeyboardButton(text="📝 Название", callback_data=f"edit_recurring_field:{operation_id}:title"),
                InlineKeyboardButton(text="📅 День", callback_data=f"edit_recurring_field:{operation_id}:day"),
            ],
            [
                InlineKeyboardButton(text="💬 Комментарий", callback_data=f"edit_recurring_field:{operation_id}:comment"),
                InlineKeyboardButton(text="↔️ Тип", callback_data=f"edit_recurring_field:{operation_id}:type"),
            ],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_recurring:{operation_id}")],
        ]
    )


def recurring_type_edit_kb(operation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Доход", callback_data=f"edit_recurring_type:{operation_id}:income"),
                InlineKeyboardButton(text="➖ Расход", callback_data=f"edit_recurring_type:{operation_id}:expense"),
            ],
            [InlineKeyboardButton(text="💳 Платёж", callback_data=f"edit_recurring_type:{operation_id}:payment")],
        ]
    )


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


def recurring_payments_menu_kb(kind: str = "payment") -> ReplyKeyboardMarkup:
    if kind == "income":
        rows = [
            [KeyboardButton(text="➕ Добавить регулярный доход")],
            [KeyboardButton(text=BACK_TEXT)],
            [KeyboardButton(text="📊 Отчёт по доходам")],
        ]
    else:
        rows = [
            [KeyboardButton(text="➕ Добавить платеж")],
            [KeyboardButton(text=BACK_TEXT)],
            [KeyboardButton(text="📊 Отчёт по расходам")],
        ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def with_cancel_kb(*rows: list[KeyboardButton]) -> ReplyKeyboardMarkup:
    keyboard_rows = [list(row) for row in rows]
    keyboard_rows.append([KeyboardButton(text=CANCEL_TEXT)])
    return ReplyKeyboardMarkup(keyboard=keyboard_rows, resize_keyboard=True, one_time_keyboard=True)


def with_back_kb(*rows: list[KeyboardButton]) -> ReplyKeyboardMarkup:
    keyboard_rows = [list(row) for row in rows]
    keyboard_rows.append([KeyboardButton(text=BACK_TEXT)])
    return ReplyKeyboardMarkup(keyboard=keyboard_rows, resize_keyboard=True, one_time_keyboard=True)


def skip_comment_kb() -> ReplyKeyboardMarkup:
    return with_cancel_kb([KeyboardButton(text="Пропустить")])


def skip_comment_back_kb() -> ReplyKeyboardMarkup:
    return with_back_kb([KeyboardButton(text="Пропустить")])


def date_choice_kb() -> ReplyKeyboardMarkup:
    return with_cancel_kb([KeyboardButton(text="Сегодня")], [KeyboardButton(text="Ввести дату")])


def date_choice_back_kb() -> ReplyKeyboardMarkup:
    return with_back_kb([KeyboardButton(text="Сегодня")], [KeyboardButton(text="Ввести дату")])


def recurring_type_kb() -> ReplyKeyboardMarkup:
    return with_cancel_kb(
        [KeyboardButton(text="Доход"), KeyboardButton(text="Расход"), KeyboardButton(text="Платёж")]
    )


def category_choice_kb(categories) -> ReplyKeyboardMarkup:
    rows = []
    for index in range(0, len(categories), 2):
        rows.append([KeyboardButton(text=category) for category in categories[index : index + 2]])
    rows.append([KeyboardButton(text="✏️ Новая категория")])
    return with_cancel_kb(*rows)


def category_choice_back_kb(categories) -> ReplyKeyboardMarkup:
    rows = []
    for index in range(0, len(categories), 2):
        rows.append([KeyboardButton(text=category) for category in categories[index : index + 2]])
    rows.append([KeyboardButton(text="✏️ Новая категория")])
    return with_back_kb(*rows)


def payment_done_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Оплачено", callback_data=f"pay_done:{payment_id}")]]
    )


def recurring_due_kb(operations) -> InlineKeyboardMarkup | None:
    rows = []
    for operation in operations:
        operation_id = operation["id"]
        title = operation["title"]
        payment_date = operation.get("payment_date")
        date_suffix = f":{payment_date.isoformat()}" if payment_date else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✅ Оплатил: {title}",
                    callback_data=f"pay_recurring:{operation_id}{date_suffix}",
                )
            ]
        )
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb() -> ReplyKeyboardMarkup:
    return with_cancel_kb()


def back_kb() -> ReplyKeyboardMarkup:
    return with_back_kb()


def report_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BACK_TEXT), KeyboardButton(text="📋 Все операции")],
            [KeyboardButton(text="📂 Категории")],
        ],
        resize_keyboard=True,
    )


def report_transactions_kb(transactions, scope: str = "all", include_edit_button: bool = True) -> InlineKeyboardMarkup | None:
    rows = []
    if include_edit_button:
        rows.append([InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"report_edit_recent:{scope}")])
    for row in transactions:
        sign = "+" if row["type"] == "income" else "-"
        amount = f"{float(row['amount']):,.2f}".replace(",", " ")
        if amount.endswith(".00"):
            amount = amount[:-3]
        category = row["category"] or "Без категории"
        date_text = row["operation_date"].strftime("%d.%m")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{date_text} {sign}{amount} {row.get('currency') or 'RUB'} — {category}",
                    callback_data=f"report_tx:{row['id']}",
                )
            ]
        )
    if not rows or (include_edit_button and len(rows) == 1):
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_delete_confirm_kb(transaction_id: int, include_edit: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if include_edit:
        rows.append(
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_tx:{transaction_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_tx:{transaction_id}"),
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(text="Да, удалить", callback_data=f"confirm_delete_tx:{transaction_id}"),
                InlineKeyboardButton(text="Отмена", callback_data=f"cancel_delete_tx:{transaction_id}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_edit_fields_kb(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Сумма", callback_data=f"edit_tx_field:{transaction_id}:amount"),
                InlineKeyboardButton(text="📂 Категория", callback_data=f"edit_tx_field:{transaction_id}:category"),
            ],
            [
                InlineKeyboardButton(text="📅 Дата", callback_data=f"edit_tx_field:{transaction_id}:date"),
                InlineKeyboardButton(text="💬 Комментарий", callback_data=f"edit_tx_field:{transaction_id}:comment"),
            ],
            [InlineKeyboardButton(text="↔️ Тип", callback_data=f"edit_tx_field:{transaction_id}:type")],
        ]
    )


def transaction_type_edit_kb(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Доход", callback_data=f"edit_tx_type:{transaction_id}:income"),
                InlineKeyboardButton(text="➖ Расход", callback_data=f"edit_tx_type:{transaction_id}:expense"),
            ]
        ]
    )


def report_categories_kb(categories, scope: str = "all") -> InlineKeyboardMarkup | None:
    rows = []
    from urllib.parse import quote

    for category in categories:
        encoded = quote(category, safe="")
        rows.append([InlineKeyboardButton(text=category, callback_data=f"report_cat:{scope}:{encoded}")])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💱 Валюта по умолчанию")], [KeyboardButton(text=BACK_TEXT)]],
        resize_keyboard=True,
    )


def currency_choice_kb(currencies: tuple[str, ...]) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=currency)] for currency in currencies]
    rows.append([KeyboardButton(text=BACK_TEXT)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
