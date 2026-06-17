import unittest
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from services.recurring_payments import DEFAULT_PAYMENT_CATEGORY, mark_scheduled_payment_paid


class FakeCursor:
    def __init__(self, update_row):
        self.update_row = update_row
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        if len(self.calls) == 1:
            return self.update_row
        return None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def cursor(self, *args, **kwargs):
        return self.cursor_obj

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@contextmanager
def fake_connection(cursor):
    yield FakeConnection(cursor)


class MarkScheduledPaymentPaidTest(unittest.TestCase):
    def test_marks_payment_paid_and_adds_expense(self):
        cursor = FakeCursor({"title": "Интернет", "amount": Decimal("1234.50"), "comment": "до 20 числа"})

        with patch("services.recurring_payments.get_connection", lambda: fake_connection(cursor)), patch(
            "services.recurring_payments.dict_cursor", lambda conn: conn.cursor()
        ), patch("services.recurring_payments.moscow_today", return_value=date(2026, 6, 17)):
            result = mark_scheduled_payment_paid(7)

        self.assertEqual(result, {"status": "paid", "title": "Интернет"})
        self.assertIn("AND is_paid = FALSE", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (7,))
        self.assertIn("INSERT INTO transactions", cursor.calls[1][0])
        self.assertEqual(
            cursor.calls[1][1],
            ("1234.50", DEFAULT_PAYMENT_CATEGORY, "Интернет", date(2026, 6, 17)),
        )

    def test_does_not_add_expense_when_payment_not_found_or_already_paid(self):
        cursor = FakeCursor(None)

        with patch("services.recurring_payments.get_connection", lambda: fake_connection(cursor)), patch(
            "services.recurring_payments.dict_cursor", lambda conn: conn.cursor()
        ):
            result = mark_scheduled_payment_paid(7)

        self.assertEqual(result, {"status": "not_found"})
        self.assertEqual(len(cursor.calls), 1)


if __name__ == "__main__":
    unittest.main()
