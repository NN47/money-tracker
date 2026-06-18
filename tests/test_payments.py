import unittest
from unittest.mock import patch

from handlers.payments import build_dashboard_reply_markup


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


if __name__ == "__main__":
    unittest.main()
