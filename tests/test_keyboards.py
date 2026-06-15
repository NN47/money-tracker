import unittest

from keyboards.main import (
    BACK_TEXT,
    calendar_back_kb,
    calendar_kb,
    recurring_due_kb,
    recurring_edit_fields_kb,
    recurring_payments_actions_kb,
)


class CalendarKeyboardTest(unittest.TestCase):
    def test_calendar_reply_keyboard_contains_only_back_button(self):
        keyboard = calendar_back_kb()

        self.assertEqual(len(keyboard.keyboard), 1)
        self.assertEqual(len(keyboard.keyboard[0]), 1)
        self.assertEqual(keyboard.keyboard[0][0].text, BACK_TEXT)

    def test_calendar_inline_keyboard_has_navigation_without_close_button(self):
        keyboard = calendar_kb("tx", 2026, 6)
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("◀️", button_texts)
        self.assertIn("▶️", button_texts)
        self.assertNotIn("Закрыть", button_texts)

    def test_calendar_inline_keyboard_marks_event_days(self):
        keyboard = calendar_kb("events", 2026, 6, marked_days={12})
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("• 12", button_texts)
        self.assertNotIn("12", button_texts)

    def test_calendar_inline_keyboard_marks_income_and_expense_days(self):
        keyboard = calendar_kb("events", 2026, 6, marked_days={10: "+", 12: "-", 15: "±"})
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("+ 10", button_texts)
        self.assertIn("- 12", button_texts)
        self.assertIn("± 15", button_texts)


class RecurringPaymentsKeyboardTest(unittest.TestCase):
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

    def test_recurring_edit_menu_contains_delete_button(self):
        keyboard = recurring_edit_fields_kb(1)
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

        self.assertIn("delete_recurring:1", callbacks)


if __name__ == "__main__":
    unittest.main()
