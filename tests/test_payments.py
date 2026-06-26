import unittest
from unittest.mock import patch

from handlers.payments import build_dashboard_reply_markup, build_recurring_operation_details


class DashboardReplyMarkupTest(unittest.TestCase):
    def test_dashboard_reply_markup_keeps_quick_actions_before_due_payments(self):
        keyboard = build_dashboard_reply_markup(
            scheduled_payments=[{"id": 7, "title": "Разовый платёж"}],
            unpaid_operations=[{"id": 3, "title": "Кредит", "payment_date": None}],
        )

        self.assertEqual(keyboard.inline_keyboard[0][0].text, "+")
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "quick_tx:income")
        self.assertEqual(keyboard.inline_keyboard[0][1].text, "-")
        self.assertEqual(keyboard.inline_keyboard[0][1].callback_data, "quick_tx:expense")
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, "pay_done:7")
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, "pay_recurring:3")

    def test_dashboard_reply_markup_fetches_due_payments_by_default(self):
        with patch("handlers.payments.fetch_unpaid_due_scheduled_payments", return_value=[]) as scheduled, patch(
            "handlers.payments.fetch_unpaid_due_recurring_payments", return_value=[]
        ) as recurring:
            keyboard = build_dashboard_reply_markup()

        scheduled.assert_called_once_with()
        recurring.assert_called_once_with()
        self.assertEqual(len(keyboard.inline_keyboard), 1)
        self.assertEqual([button.text for button in keyboard.inline_keyboard[0]], ["+", "-"])


class RecurringOperationDetailsTest(unittest.TestCase):
    def test_recurring_operation_details_contains_all_editable_fields(self):
        text = build_recurring_operation_details(
            {
                "id": 1,
                "title": "Сбер",
                "type": "payment",
                "amount": 12345.67,
                "category": "Кредит",
                "day_of_month": 15,
                "frequency": "monthly",
                "comment": "Ипотека",
            }
        )

        self.assertIn("Редактируем регулярный платёж «Сбер».", text)
        self.assertIn("Текущие данные:", text)
        self.assertIn("• Название: Сбер", text)
        self.assertIn("• Тип: платёж", text)
        self.assertIn("• Сумма: 12 345.67 ₽", text)
        self.assertIn("• Категория: Кредит", text)
        self.assertIn("• День месяца: 15 число", text)
        self.assertIn("• Частота: ежемесячно", text)
        self.assertIn("• Комментарий: Ипотека", text)
        self.assertTrue(text.endswith("Что хотите изменить?"))


if __name__ == "__main__":
    unittest.main()
