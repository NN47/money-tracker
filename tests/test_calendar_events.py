from datetime import date
import unittest

from services.calendar_events import build_calendar_day_events, has_calendar_events, month_bounds


class CalendarEventsTest(unittest.TestCase):
    def test_month_bounds_returns_next_month_start(self):
        self.assertEqual(month_bounds(2026, 6), (date(2026, 6, 1), date(2026, 7, 1)))
        self.assertEqual(month_bounds(2026, 12), (date(2026, 12, 1), date(2027, 1, 1)))

    def test_has_calendar_events_detects_empty_payload(self):
        self.assertFalse(has_calendar_events({"scheduled": [], "recurring": [], "transactions": []}))
        self.assertTrue(has_calendar_events({"scheduled": [{"id": 1}], "recurring": [], "transactions": []}))

    def test_build_calendar_day_events_formats_all_event_types(self):
        text = build_calendar_day_events(
            date(2026, 6, 12),
            {
                "scheduled": [
                    {"id": 1, "title": "Ипотека", "amount": 1000, "is_paid": False, "comment": "банк"}
                ],
                "recurring": [
                    {
                        "id": 2,
                        "title": "Подписка",
                        "type": "payment",
                        "amount": 299,
                        "category": "Сервисы",
                        "comment": None,
                    }
                ],
                "transactions": [
                    {"id": 3, "type": "income", "amount": 5000, "category": "ЗП", "comment": None}
                ],
            },
        )

        self.assertIn("📅 События на 12.06.2026", text)
        self.assertIn("Ипотека — 1 000 ₽ (не оплачен) — банк", text)
        self.assertIn("Подписка — 299 ₽ (платёж, Сервисы)", text)
        self.assertIn("+5 000 ₽ — ЗП", text)


if __name__ == "__main__":
    unittest.main()
