import unittest

from services.currencies import extract_currency


class CurrencyExtractionTest(unittest.TestCase):
    def test_extracts_russian_currency_and_preserves_description(self):
        self.assertEqual(extract_currency("500 грн продукты"), ("UAH", "500 продукты"))

    def test_extracts_english_currency(self):
        self.assertEqual(extract_currency("20 dollar кафе"), ("USD", "20 кафе"))

    def test_extracts_cis_currency(self):
        self.assertEqual(extract_currency("1500 тенге такси"), ("KZT", "1500 такси"))

    def test_returns_none_without_currency(self):
        self.assertEqual(extract_currency("500 такси"), (None, "500 такси"))


if __name__ == "__main__":
    unittest.main()
