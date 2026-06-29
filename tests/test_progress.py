import unittest
from datetime import date
from unittest.mock import patch

from services.progress import days_until_next_payment_text


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


if __name__ == "__main__":
    unittest.main()
