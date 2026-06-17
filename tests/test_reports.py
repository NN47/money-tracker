from datetime import date
import unittest
from unittest.mock import patch

from services.reports import _next_recurring_date, build_dashboard, build_summary_report, format_russian_month_year, upcoming_recurring_payments


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


class OverduePaymentsReportTest(unittest.TestCase):
    def test_summary_report_shows_overdue_payments(self):
        main_data = (
            date(2026, 6, 17),
            0,
            0,
            [{"id": 2, "title": "Разовый", "amount": 500, "payment_date": date(2026, 6, 15)}],
            [{"id": 1, "title": "Кредит", "amount": 1000, "day_of_month": 16, "payment_date": date(2026, 6, 16)}],
            [],
            [],
            [],
        )

        with patch("services.reports._fetch_main_data", return_value=main_data):
            text = build_summary_report(transactions=[])

        self.assertIn("<b>⚠️ Просроченные платежи:</b>", text)
        self.assertIn("16.06.2026 — Кредит — <b>1 000 ₽</b> 🔁", text)
        self.assertIn("15.06.2026 — Разовый — <b>500 ₽</b>", text)

    def test_dashboard_shows_overdue_payments(self):
        main_data = (
            date(2026, 6, 17),
            0,
            0,
            [],
            [{"id": 1, "title": "Кредит", "amount": 1000, "day_of_month": 16, "payment_date": date(2026, 6, 16)}],
            [],
            [],
            [],
        )

        with patch("services.reports._fetch_main_data", return_value=main_data), patch(
            "services.reports.fetch_today_recurring_payments", return_value=[]
        ):
            text = build_dashboard()

        self.assertIn("<b>⚠️ Просроченные платежи:</b>", text)
        self.assertIn("<b>📅 Платежи в ближайшие 10 дней:</b>", text)
        self.assertNotIn("📅 Ближайшие платежи:", text)
        self.assertIn("16.06.2026 — Кредит — <b>1 000 ₽</b> 🔁", text)


if __name__ == "__main__":
    unittest.main()
