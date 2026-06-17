import unittest

from handlers.home import dashboard_due_action_rows


class DashboardDueActionRowsTest(unittest.TestCase):
    def test_includes_scheduled_and_recurring_payment_actions(self):
        rows = dashboard_due_action_rows(
            [{"id": 7, "title": "Разовый платёж"}],
            [{"id": 3, "title": "Кредит", "payment_date": None}],
        )

        self.assertEqual(rows[0][0].text, "✅ Оплатил: Разовый платёж")
        self.assertEqual(rows[0][0].callback_data, "pay_done:7")
        self.assertEqual(rows[1][0].text, "✅ Оплатил: Кредит")
        self.assertEqual(rows[1][0].callback_data, "pay_recurring:3")

    def test_returns_none_without_due_payments(self):
        self.assertIsNone(dashboard_due_action_rows([], []))


if __name__ == "__main__":
    unittest.main()
