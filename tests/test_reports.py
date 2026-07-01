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

    def test_upcoming_recurring_payments_skips_paid_payment_dates(self):
        rows = [
            {
                "id": 1,
                "title": "paid today",
                "amount": 100,
                "day_of_month": 15,
                "paid_payment_dates": [date(2026, 6, 15)],
            },
            {
                "id": 2,
                "title": "unpaid tomorrow",
                "amount": 100,
                "day_of_month": 16,
                "paid_payment_dates": [date(2026, 5, 16)],
            },
        ]

        result = upcoming_recurring_payments(rows, date(2026, 6, 15), date(2026, 6, 25))

        self.assertEqual([row["title"] for row in result], ["unpaid tomorrow"])
        self.assertNotIn("paid_payment_dates", result[0])


class MonthlySummaryReportTest(unittest.TestCase):
    def test_summary_report_labels_operations_for_month(self):
        main_data = (date(2026, 5, 1), {"RUB": 1000}, {"RUB": 300}, [], [], [], [])
        transactions = [
            {
                "id": 1,
                "type": "expense",
                "amount": 300,
                "currency": "RUB",
                "category": "Еда",
                "comment": "",
                "operation_date": date(2026, 5, 20),
            }
        ]

        with patch("services.reports._fetch_main_data", return_value=main_data):
            text = build_summary_report(transactions=transactions, report_date=date(2026, 5, 1))

        self.assertIn("🗓 <b>Период:</b> <b>Май 2026</b>", text)
        self.assertIn("<b>🧾 Операции за месяц:</b>", text)
        self.assertNotIn("Последние 10", text)
        self.assertIn("<b>20.05</b> <b>-300 ₽</b> — <b>Еда</b>", text)

    def test_summary_report_hides_upcoming_payments_section(self):
        main_data = (
            date(2026, 6, 17),
            {"RUB": 1000},
            {"RUB": 300},
            [],
            [],
            [{"id": 2, "title": "Разовый", "amount": 500, "payment_date": date(2026, 6, 20)}],
            [{"id": 1, "title": "Кредит", "amount": 1000, "day_of_month": 18, "payment_date": date(2026, 6, 18)}],
        )

        with patch("services.reports._fetch_main_data", return_value=main_data):
            text = build_summary_report(transactions=[])

        self.assertNotIn("<b>📅 Ближайшие платежи на 10 дней:</b>", text)
        self.assertNotIn("Нет платежей", text)
        self.assertNotIn("Кредит", text)
        self.assertNotIn("Разовый", text)


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
        )

        with patch("services.reports._fetch_main_data", return_value=main_data):
            text = build_summary_report(transactions=[])

        self.assertIn("<b>⚠️ Просроченные платежи:</b>", text)
        self.assertIn("16.06.2026 — Кредит — <b>1 000 ₽</b> 🔁", text)
        self.assertIn("15.06.2026 — Разовый — <b>500 ₽</b>", text)

    def test_dashboard_hides_overdue_and_recurring_operations_sections(self):
        main_data = (
            date(2026, 6, 17),
            0,
            0,
            [],
            [{"id": 1, "title": "Кредит", "amount": 1000, "day_of_month": 16, "payment_date": date(2026, 6, 16)}],
            [],
            [],
        )

        with patch("services.reports._fetch_main_data", return_value=main_data):
            text = build_dashboard()

        self.assertNotIn("<b>⚠️ Просроченные платежи:</b>", text)
        self.assertNotIn("<b>🔁 Постоянные операции:</b>", text)
        self.assertIn("<b>📅 Платежей в ближайшие 10 дней нет</b>", text)


    def test_project_dashboard_hides_global_upcoming_payments(self):
        main_data = (
            date(2026, 6, 29),
            {"RUB": 115000},
            {"RUB": 0},
            [],
            [],
            [{"id": 2, "title": "Совком", "amount": 8200, "payment_date": date(2026, 6, 30)}],
            [{"id": 1, "title": "Сбер кредит", "amount": 7900, "day_of_month": 4, "payment_date": date(2026, 7, 4)}],
        )

        with patch("services.reports._fetch_main_data", return_value=main_data) as fetch_main_data:
            text = build_dashboard(person_id=7, person_name="Учеба")

        fetch_main_data.assert_called_once_with(person_id=7)
        self.assertIn("📁 <b>Учеба</b>", text)
        self.assertIn("Фильтр: 📁 Учеба", text)
        self.assertIn("💰 <b>Доходы:</b> <b>115 000 ₽</b>", text)
        self.assertNotIn("Совком", text)
        self.assertNotIn("Сбер кредит", text)

    def test_dashboard_shows_upcoming_payments_with_currency_symbol(self):
        main_data = (
            date(2026, 6, 17),
            {"RUB": 78972},
            {"RUB": 69356},
            [],
            [],
            [{"id": 2, "title": "Разовый", "amount": 500, "payment_date": date(2026, 6, 20)}],
            [{"id": 1, "title": "Кредит", "amount": 1000, "day_of_month": 18, "payment_date": date(2026, 6, 18)}],
        )

        with patch("services.reports._fetch_main_data", return_value=main_data):
            text = build_dashboard()

        self.assertIn("💰 <b>Доходы:</b> <b>78 972 ₽</b>", text)
        self.assertIn("💸 <b>Расходы:</b> <b>69 356 ₽</b>", text)
        self.assertIn("⚖️ <b>Баланс:</b> <b>9 616 ₽</b>", text)
        self.assertIn("18.06 — Кредит — <b>1 000 ₽</b> 🔁", text)
        self.assertIn("20.06 — Разовый — <b>500 ₽</b>", text)


if __name__ == "__main__":
    unittest.main()
