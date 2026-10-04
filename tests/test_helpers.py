import unittest
from decimal import Decimal

from invoice_totals.headers import parse_headers
from invoice_totals.money import parse_amount


class HeaderTests(unittest.TestCase):
    def test_maps_reordered_headers(self):
        self.assertEqual(
            parse_headers(["amount", "invoice_id", "customer", "currency"]),
            {"amount": 0, "invoice_id": 1, "customer": 2, "currency": 3},
        )

    def test_rejects_missing_required_header(self):
        with self.assertRaises(ValueError):
            parse_headers(["invoice_id", "customer", "amount"])

    def test_rejects_duplicate_header(self):
        with self.assertRaises(ValueError):
            parse_headers(["invoice_id", "customer", "currency", "amount", "amount"])


class AmountTests(unittest.TestCase):
    def test_parses_exact_decimal_and_credit(self):
        self.assertEqual(parse_amount("0.10"), Decimal("0.10"))
        self.assertEqual(parse_amount("-12.34"), Decimal("-12.34"))
        self.assertEqual(parse_amount(" 5 "), Decimal("5.00"))

    def test_rejects_nonfinite_and_malformed_values(self):
        for value in ["", "bad", "NaN", "Infinity", "-Infinity"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_amount(value)

    def test_rejects_fractional_cents(self):
        with self.assertRaises(ValueError):
            parse_amount("1.005")


if __name__ == "__main__":
    unittest.main()
