import unittest
from datetime import date
from unittest.mock import patch

from services.progress import _next_recurring_candidate, days_until_next_payment_text


class DaysUntilNextPaymentTextTest(unittest.TestCase):
    def test_formats_due_today_as_tomorrow_after_payment_done(self):
        with patch("services.progress.moscow_today", return_value=date(2026, 6, 29)), patch(
            "services.progress.fetch_next_payment",
            return_value={"payment_date": date(2026, 6, 29)},
        ):
            self.assertEqual(days_until_next_payment_text(), "завтра")

    def test_formats_due_tomorrow_as_tomorrow(self):
        with patch("services.progress.moscow_today", return_value=date(2026, 6, 29)), patch(
            "services.progress.fetch_next_payment",
            return_value={"payment_date": date(2026, 6, 30)},
        ):
            self.assertEqual(days_until_next_payment_text(), "завтра")

    def test_formats_later_payment_with_preposition(self):
        with patch("services.progress.moscow_today", return_value=date(2026, 6, 29)), patch(
            "services.progress.fetch_next_payment",
            return_value={"payment_date": date(2026, 7, 2)},
        ):
            self.assertEqual(days_until_next_payment_text(), "через 3 дня")

    def test_formats_later_payment_with_singular_day(self):
        with patch("services.progress.moscow_today", return_value=date(2026, 6, 29)), patch(
            "services.progress.fetch_next_payment",
            return_value={"payment_date": date(2026, 7, 20)},
        ):
            self.assertEqual(days_until_next_payment_text(), "через 21 день")

    def test_formats_missing_payment(self):
        with patch("services.progress.fetch_next_payment", return_value=None):
            self.assertEqual(days_until_next_payment_text(), "платежей нет")


class NextRecurringCandidateTest(unittest.TestCase):
    def test_skips_paid_payment_date_and_returns_next_month(self):
        row = {
            "id": 1,
            "title": "Яндекс кредит",
            "amount": 37054,
            "day_of_month": 29,
            "paid_payment_dates": [date(2026, 6, 29)],
        }

        result = _next_recurring_candidate(row, date(2026, 6, 29))

        self.assertEqual(result["payment_date"], date(2026, 7, 29))
        self.assertNotIn("paid_payment_dates", result)

    def test_keeps_unpaid_payment_due_today(self):
        row = {"id": 1, "title": "Кредит", "amount": 1000, "day_of_month": 29, "paid_payment_dates": []}

        result = _next_recurring_candidate(row, date(2026, 6, 29))

        self.assertEqual(result["payment_date"], date(2026, 6, 29))


if __name__ == "__main__":
    unittest.main()
