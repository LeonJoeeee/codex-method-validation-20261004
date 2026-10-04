"""Contract tests for independent integer-cent JSON serialization."""

from collections import UserDict
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
import io
import json
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType
import unittest
from unittest.mock import patch

from invoice_totals.json_output import totals_to_json


class JSONOutputTests(unittest.TestCase):
    def test_empty_mapping_returns_exact_empty_array(self):
        self.assertEqual(totals_to_json({}), "[]")

    def test_chinese_example_is_compact_visible_unicode(self):
        text = totals_to_json({("示例客户", "CNY"): 125})
        self.assertEqual(text, '[{"customer":"示例客户","currency":"CNY","total":"1.25"}]')
        self.assertEqual(json.loads(text), [
            {"customer": "示例客户", "currency": "CNY", "total": "1.25"},
        ])
        self.assertEqual(list(json.loads(text)[0]), ["customer", "currency", "total"])
        self.assertNotIn("\\u", text)
        self.assertFalse(text.endswith("\n"))

    def test_insertion_order_does_not_change_original_string_sorting(self):
        pairs = [
            (("客户", "CNY"), 5), (("a", "USD"), 4), (("A", "usd"), 3),
            (("A", "USD"), 2), ((" A ", "USD"), 1),
        ]
        text = totals_to_json(dict(pairs))
        self.assertEqual(text, totals_to_json(dict(reversed(pairs))))
        self.assertEqual(json.loads(text), [
            {"customer": " A ", "currency": "USD", "total": "0.01"},
            {"customer": "A", "currency": "USD", "total": "0.02"},
            {"customer": "A", "currency": "usd", "total": "0.03"},
            {"customer": "a", "currency": "USD", "total": "0.04"},
            {"customer": "客户", "currency": "CNY", "total": "0.05"},
        ])

    def test_unicode_and_whitespace_are_preserved_without_normalization(self):
        totals = {(" é 客户😀\t ", " cNy "): 10, ("é", "USD"): 20, ("e\u0301", "USD"): 30}
        text = totals_to_json(totals)
        self.assertIn("客户😀", text)
        self.assertEqual(json.loads(text), [
            {"customer": " é 客户😀\t ", "currency": " cNy ", "total": "0.10"},
            {"customer": "e\u0301", "currency": "USD", "total": "0.30"},
            {"customer": "é", "currency": "USD", "total": "0.20"},
        ])

    def test_quotes_backslashes_and_control_characters_round_trip(self):
        customer = 'A,"\\\n\r\t\b\f\x00'
        currency = 'U"S\\D\n'
        text = totals_to_json({(customer, currency): 123})
        self.assertEqual(json.loads(text), [
            {"customer": customer, "currency": currency, "total": "1.23"},
        ])
        self.assertIn('\\"', text)
        self.assertIn('\\\\', text)
        self.assertIn('\\n', text)
        self.assertIn('\\u0000', text)
        self.assertFalse(any(ord(character) < 32 for character in text))

    def test_amounts_are_exact_fixed_two_place_strings(self):
        cases = [
            (0, "0.00"), (1, "0.01"), (-1, "-0.01"), (99, "0.99"),
            (-99, "-0.99"), (100, "1.00"), (-100, "-1.00"), (125, "1.25"),
            (-12345, "-123.45"), (100000000000, "1000000000.00"),
            (99999999999, "999999999.99"),
            (12345678901234567890123456789012, "123456789012345678901234567890.12"),
        ]
        for cents, expected in cases:
            with self.subTest(cents=cents):
                row = json.loads(totals_to_json({("Customer", "USD"): cents}))[0]
                self.assertEqual(row["total"], expected)
                self.assertIsInstance(row["total"], str)
                self.assertEqual(list(row), ["customer", "currency", "total"])

    def test_huge_integer_cents_survive_digit_limit_without_global_changes(self):
        original_limit = sys.get_int_max_str_digits()
        exponent = max(original_limit, 4300) + 100
        cents = (10 ** exponent + 1000000007) * 100 + 9
        expected = "1" + "0" * (exponent - 10) + "1000000007.09"
        for value, amount in [(cents, expected), (-cents, "-" + expected)]:
            with self.subTest(negative=value < 0):
                self.assertEqual(
                    json.loads(totals_to_json({("Customer", "USD"): value}))[0]["total"],
                    amount,
                )
        self.assertEqual(sys.get_int_max_str_digits(), original_limit)

    def test_accepts_read_only_and_non_dict_mappings_without_mutation(self):
        source = {("B", "USD"): -1, ("A", "CNY"): 0}
        original = source.copy()
        for totals in [source, MappingProxyType(source), UserDict(source)]:
            with self.subTest(mapping=type(totals).__name__):
                self.assertEqual(json.loads(totals_to_json(totals)), [
                    {"customer": "A", "currency": "CNY", "total": "0.00"},
                    {"customer": "B", "currency": "USD", "total": "-0.01"},
                ])
                self.assertEqual(dict(totals), original)
                self.assertEqual(list(totals), list(original))
        self.assertEqual(source, original)

    def test_rejects_non_mapping_inputs(self):
        for totals in [None, [], [(('A', 'USD'), 1)], (), "", 1, True, set(), object()]:
            with self.subTest(input_type=type(totals).__name__), self.assertRaises(TypeError):
                totals_to_json(totals)

    def test_rejects_key_types_and_shapes_before_sorting(self):
        keys = ["A", 1, None, (), ("A",), ("A", "USD", "extra"), (1, "USD"), ("A", None)]
        for key in keys:
            with self.subTest(key=key), self.assertRaises(TypeError):
                totals_to_json({("Z", "USD"): 0, key: 1})

    def test_rejects_non_actual_integer_values_without_coercion(self):
        class DerivedInt(int):
            pass

        for cents in [True, False, 1.0, float("nan"), Decimal("1"), "125", None, DerivedInt(1)]:
            with self.subTest(value_type=type(cents).__name__), self.assertRaises(TypeError):
                totals_to_json({("Customer", "USD"): cents})

    def test_rejects_blank_names_and_currencies(self):
        for blank in ["", " ", "\t\n\r", "\u2003"]:
            for key in [(blank, "USD"), ("Customer", blank)]:
                with self.subTest(key=key), self.assertRaises(ValueError):
                    totals_to_json({key: 0})

    def test_invalid_final_entry_raises_without_mutating_input(self):
        totals = {("A", "USD"): 125, ("Z", "USD"): "bad"}
        original_items = list(totals.items())
        with self.assertRaises(TypeError):
            totals_to_json(totals)
        self.assertEqual(list(totals.items()), original_items)

    def test_calls_produce_no_stdout_stderr_or_file_access(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
                patch("builtins.open", side_effect=AssertionError("unexpected file access")), \
                patch("io.open", side_effect=AssertionError("unexpected file access")), \
                patch("os.open", side_effect=AssertionError("unexpected file access")):
            text = totals_to_json({("Customer", "USD"): 125})
            with self.assertRaises(TypeError):
                totals_to_json({("Customer", "USD"): False})
        self.assertEqual(text, '[{"customer":"Customer","currency":"USD","total":"1.25"}]')
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_fresh_import_and_execution_do_not_depend_on_ingestion(self):
        program = '''
import sys
class BlockIngestion:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"invoice_totals.batch", "invoice_totals.report", "invoice_totals.__main__",
                        "invoice_totals.headers", "invoice_totals.money"}:
            raise AssertionError("unexpected ingestion import: " + fullname)
sys.meta_path.insert(0, BlockIngestion())
from invoice_totals.json_output import totals_to_json
assert totals_to_json({("示例客户", "CNY"): 125}) == '[{"customer":"示例客户","currency":"CNY","total":"1.25"}]'
assert totals_to_json({}) == "[]"
assert "invoice_totals.batch" not in sys.modules
assert "invoice_totals.report" not in sys.modules
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", program],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
