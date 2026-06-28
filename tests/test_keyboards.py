from datetime import date
import unittest

from keyboards.main import (
    BACK_TEXT,
    CANCEL_TEXT,
    HOME_TEXT,
    main_menu_kb,
    back_kb,
    calendar_back_kb,
    calendar_kb,
    recurring_day_choice_kb,
    recurring_due_kb,
    recurring_edit_fields_kb,
    recurring_payments_actions_kb,
    report_transactions_kb,
    section_menu_kb,
    skip_comment_back_kb,
)


class MainMenuKeyboardTest(unittest.TestCase):
    def test_main_menu_keyboard_uses_requested_two_button_rows(self):
        keyboard = main_menu_kb()
        button_rows = [[button.text for button in row] for row in keyboard.keyboard]

        self.assertEqual(
            button_rows,
            [
                ["💰 Доходы", "💸 Расходы"],
                ["📅 Календарь", "📊 Отчёт"],
                ["💼 Главный экран", "⚙️ Настройки"],
            ],
        )


class CalendarKeyboardTest(unittest.TestCase):
    def test_calendar_reply_keyboard_contains_context_buttons(self):
        keyboard = calendar_back_kb()

        self.assertEqual(len(keyboard.keyboard), 1)
        self.assertEqual(len(keyboard.keyboard[0]), 2)
        self.assertEqual(keyboard.keyboard[0][0].text, BACK_TEXT)
        self.assertEqual(keyboard.keyboard[0][1].text, HOME_TEXT)

    def test_calendar_inline_keyboard_has_navigation_without_close_button(self):
        keyboard = calendar_kb("tx", 2026, 6)
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("⬅️ Пред.", button_texts)
        self.assertIn("След. ➡️", button_texts)
        self.assertNotIn("Закрыть", button_texts)

    def test_calendar_inline_keyboard_marks_event_days(self):
        keyboard = calendar_kb("events", 2026, 6, marked_days={12})
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("12 •", button_texts)
        self.assertNotIn("12", button_texts)

    def test_calendar_inline_keyboard_marks_income_and_expense_days(self):
        keyboard = calendar_kb("events", 2026, 6, marked_days={10: "🟢", 12: "🔴", 15: "🟢🔴"})
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("10 🟢", button_texts)
        self.assertIn("12 🔴", button_texts)
        self.assertIn("15 🟢🔴", button_texts)

    def test_calendar_inline_keyboard_omits_trailing_empty_cells(self):
        keyboard = calendar_kb("events", 2026, 6)
        june_29_row = next(row for row in keyboard.inline_keyboard if row[0].text == "29")

        self.assertEqual([button.text for button in june_29_row], ["29", "30"])


class BackKeyboardTest(unittest.TestCase):
    def test_back_keyboard_contains_back_instead_of_cancel(self):
        keyboard = back_kb()
        button_texts = [button.text for row in keyboard.keyboard for button in row]

        self.assertEqual(button_texts, [BACK_TEXT])
        self.assertNotIn(CANCEL_TEXT, button_texts)

    def test_back_keyboard_can_show_input_placeholder(self):
        keyboard = back_kb(input_field_placeholder="Например: 8500 ₽")

        self.assertEqual(keyboard.input_field_placeholder, "Например: 8500 ₽")

    def test_transaction_comment_keyboard_uses_back_button(self):
        keyboard = skip_comment_back_kb()
        button_texts = [button.text for row in keyboard.keyboard for button in row]

        self.assertIn("Пропустить", button_texts)
        self.assertIn(BACK_TEXT, button_texts)
        self.assertNotIn(CANCEL_TEXT, button_texts)


class SectionMenuKeyboardTest(unittest.TestCase):
    def test_expense_section_menu_uses_requested_rows(self):
        keyboard = section_menu_kb("expense")

        self.assertEqual([[button.text for button in row] for row in keyboard.keyboard], [
            ["➖ Добавить расход"],
            ["🔁 Регулярные платежи"],
            ["📊 Отчёт", "📂 Категории"],
            [BACK_TEXT],
        ])


class ReportKeyboardTest(unittest.TestCase):
    def test_report_transactions_keyboard_starts_with_edit_button_for_scope(self):
        keyboard = report_transactions_kb(
            [
                {
                    "id": 7,
                    "type": "expense",
                    "amount": 10000,
                    "category": "Кредит",
                    "operation_date": date(2026, 6, 17),
                }
            ],
            scope="expense",
        )

        self.assertEqual(keyboard.inline_keyboard[0][0].text, "✏️ Редактировать")
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "report_edit_recent:expense")
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, "report_tx:7")

    def test_report_transactions_keyboard_can_hide_edit_button(self):
        keyboard = report_transactions_kb(
            [
                {
                    "id": 7,
                    "type": "expense",
                    "amount": 10000,
                    "category": "Кредит",
                    "operation_date": date(2026, 6, 17),
                }
            ],
            include_edit_button=False,
        )

        self.assertEqual(len(keyboard.inline_keyboard), 1)
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "report_tx:7")

    def test_report_transactions_keyboard_is_empty_without_transactions(self):
        self.assertIsNone(report_transactions_kb([]))


class RecurringPaymentsKeyboardTest(unittest.TestCase):
    def test_recurring_day_choice_keyboard_is_compact_day_picker(self):
        keyboard = recurring_day_choice_kb()

        self.assertEqual([[button.text for button in row] for row in keyboard.inline_keyboard[:5]], [
            ["1", "2", "3", "4", "5", "6", "7"],
            ["8", "9", "10", "11", "12", "13", "14"],
            ["15", "16", "17", "18", "19", "20", "21"],
            ["22", "23", "24", "25", "26", "27", "28"],
            ["29", "30", "31"],
        ])
        self.assertEqual(keyboard.inline_keyboard[-1][0].text, CANCEL_TEXT)
        self.assertEqual(keyboard.inline_keyboard[-1][0].callback_data, "cancel_recurring_day")
        self.assertNotIn("⬅️ Пред.", [button.text for row in keyboard.inline_keyboard for button in row])
        self.assertNotIn("След. ➡️", [button.text for row in keyboard.inline_keyboard for button in row])

    def test_recurring_payments_actions_contains_only_edit_buttons(self):
        keyboard = recurring_payments_actions_kb([{"id": 1, "title": "Сбер кредит"}])
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertEqual(button_texts, ["✏️ Редактировать: Сбер кредит"])

    def test_recurring_due_keyboard_contains_only_paid_buttons(self):
        keyboard = recurring_due_kb([{"id": 1, "title": "Сбер"}])
        buttons = [button for row in keyboard.inline_keyboard for button in row]

        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].text, "✅ Оплатил: Сбер")
        self.assertEqual(buttons[0].callback_data, "pay_recurring:1")

    def test_recurring_due_keyboard_includes_payment_date_when_available(self):
        keyboard = recurring_due_kb([{"id": 1, "title": "Сбер", "payment_date": date(2026, 6, 16)}])
        buttons = [button for row in keyboard.inline_keyboard for button in row]

        self.assertEqual(buttons[0].callback_data, "pay_recurring:1:2026-06-16")

    def test_recurring_edit_menu_contains_delete_button(self):
        keyboard = recurring_edit_fields_kb(1)
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

        self.assertIn("delete_recurring:1", callbacks)


if __name__ == "__main__":
    unittest.main()
