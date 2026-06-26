import unittest

from services.currencies import extract_currency, format_money


class CurrencyExtractionTest(unittest.TestCase):
    def test_extracts_russian_currency_and_preserves_description(self):
        self.assertEqual(extract_currency("500 грн продукты"), ("UAH", "500 продукты"))

    def test_extracts_english_currency(self):
        self.assertEqual(extract_currency("20 dollar кафе"), ("USD", "20 кафе"))

    def test_extracts_cis_currency(self):
        self.assertEqual(extract_currency("1500 тенге такси"), ("KZT", "1500 такси"))

    def test_returns_none_without_currency(self):
        self.assertEqual(extract_currency("500 такси"), (None, "500 такси"))


class CurrencyFormattingTest(unittest.TestCase):
    def test_formats_known_currency_with_symbol(self):
        self.assertEqual(format_money(78972, "RUB"), "78 972 ₽")
        self.assertEqual(format_money(20.5, "USD"), "20.5 $")

    def test_formats_unknown_currency_with_iso_code(self):
        self.assertEqual(format_money(100, "BTC"), "100 BTC")


if __name__ == "__main__":
    unittest.main()
