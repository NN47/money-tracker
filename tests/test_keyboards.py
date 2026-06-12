import unittest

from keyboards.main import BACK_TEXT, calendar_back_kb, calendar_kb


class CalendarKeyboardTest(unittest.TestCase):
    def test_calendar_reply_keyboard_contains_only_back_button(self):
        keyboard = calendar_back_kb()

        self.assertEqual(len(keyboard.keyboard), 1)
        self.assertEqual(len(keyboard.keyboard[0]), 1)
        self.assertEqual(keyboard.keyboard[0][0].text, BACK_TEXT)

    def test_calendar_inline_keyboard_has_navigation_without_close_button(self):
        keyboard = calendar_kb("tx", 2026, 6)
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("◀️", button_texts)
        self.assertIn("▶️", button_texts)
        self.assertNotIn("Закрыть", button_texts)


if __name__ == "__main__":
    unittest.main()
