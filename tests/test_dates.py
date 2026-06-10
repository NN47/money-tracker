from datetime import date
import unittest

from services.dates import parse_future_date, parse_transaction_date
from services.reports import _format_transaction_date, month_bounds


class DateParsingTest(unittest.TestCase):
    def test_transaction_short_date_uses_current_year_even_when_past(self):
        self.assertEqual(
            parse_transaction_date("07.06", today=date(2026, 6, 10)),
            date(2026, 6, 7),
        )

    def test_future_short_date_rolls_past_date_to_next_year(self):
        self.assertEqual(
            parse_future_date("07.06", today=date(2026, 6, 10)),
            date(2027, 6, 7),
        )

    def test_relative_transaction_date_still_supported(self):
        self.assertEqual(
            parse_transaction_date("через 3 дня", today=date(2026, 6, 10)),
            date(2026, 6, 13),
        )

    def test_report_shows_year_for_transactions_outside_current_period(self):
        start, end = month_bounds(date(2026, 6, 10))
        self.assertEqual(_format_transaction_date(date(2026, 6, 7), start, end), "07.06")
        self.assertEqual(_format_transaction_date(date(2027, 6, 7), start, end), "07.06.2027")


if __name__ == "__main__":
    unittest.main()
