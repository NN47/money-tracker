from datetime import date
import unittest

from services.reports import _next_recurring_date, format_russian_month_year, upcoming_recurring_payments


class RussianMonthFormattingTest(unittest.TestCase):
    def test_formats_june_in_russian(self):
        self.assertEqual(format_russian_month_year(date(2026, 6, 15)), "Июнь 2026")


class UpcomingRecurringPaymentsTest(unittest.TestCase):
    def test_next_recurring_date_uses_current_month_when_day_is_ahead(self):
        self.assertEqual(_next_recurring_date(20, date(2026, 6, 15)), date(2026, 6, 20))

    def test_next_recurring_date_rolls_to_next_month_when_day_has_passed(self):
        self.assertEqual(_next_recurring_date(10, date(2026, 6, 15)), date(2026, 7, 10))

    def test_next_recurring_date_skips_months_without_requested_day(self):
        self.assertEqual(_next_recurring_date(31, date(2026, 6, 15)), date(2026, 7, 31))

    def test_upcoming_recurring_payments_filters_by_horizon_and_sorts(self):
        rows = [
            {"id": 2, "title": "too late", "amount": 100, "day_of_month": 30},
            {"id": 1, "title": "soon", "amount": 100, "day_of_month": 16},
            {"id": 3, "title": "today", "amount": 100, "day_of_month": 15},
        ]

        result = upcoming_recurring_payments(rows, date(2026, 6, 15), date(2026, 6, 25))

        self.assertEqual([row["title"] for row in result], ["today", "soon"])
        self.assertEqual(result[0]["payment_date"], date(2026, 6, 15))
        self.assertEqual(result[1]["payment_date"], date(2026, 6, 16))


if __name__ == "__main__":
    unittest.main()
