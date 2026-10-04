"""Exercise the offline CLI through its process boundary."""

import csv
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HEADER = "invoice_id,customer,currency,amount\n"
REPORT_HEADER = "customer,currency,total\n"


class CLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "invoices.csv"

    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "invoice_totals", *map(str, arguments)],
            cwd=ROOT,
            capture_output=True,
            timeout=10,
        )

    def run_input(self, contents):
        self.path.write_bytes(contents.encode("utf-8") if isinstance(contents, str) else contents)
        return self.run_cli(self.path)

    def assert_success(self, result, expected):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout.decode("utf-8"), expected)

    def assert_invalid(self, result, field, reason, position=None):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, b"")
        diagnostic = result.stderr.decode("utf-8")
        self.assertIn(str(self.path), diagnostic)
        self.assertIn(field, diagnostic)
        self.assertIn(reason, diagnostic)
        if position is not None:
            self.assertIn(f"line {position}", diagnostic)
        self.assertNotIn("Traceback", diagnostic)

    def test_sample_report(self):
        self.assert_success(
            self.run_cli(ROOT / "sample_invoices.csv"),
            REPORT_HEADER + "Example Bakery,USD,0.25\nExample Studio,EUR,8.40\n",
        )

    def test_groups_sort_by_original_customer_and_currency(self):
        self.assert_success(self.run_input(HEADER + (
            "1,Zebra,USD,2.00\n"
            "2,Ada,USD,0.10\n"
            "3,Ada,EUR,8.40\n"
            "4,Ada,USD,0.20\n"
            "5,Ada,USD,-0.05\n"
            "6, Ada ,USD,3.00\n"
            "7,ada,USD,4.00\n"
            "8,Ada,usd,5.00\n"
            "9,Ada, USD ,6.00\n"
        )), REPORT_HEADER + (
            " Ada ,USD,3.00\n"
            "Ada, USD ,6.00\n"
            "Ada,EUR,8.40\n"
            "Ada,USD,0.25\n"
            "Ada,usd,5.00\n"
            "Zebra,USD,2.00\n"
            "ada,USD,4.00\n"
        ))

    def test_credit_zero_and_parser_supported_amounts(self):
        self.assert_success(self.run_input(HEADER + (
            "1,Negative,USD,-12.34\n"
            "2,Zero,USD,-0.00\n"
            "3,Cancel,USD,5\n"
            "4,Cancel,USD,-5.000\n"
            "5,Scientific,USD,1e-2\n"
            "6,Scientific,USD, 5 \n"
        )), REPORT_HEADER + (
            "Cancel,USD,0.00\nNegative,USD,-12.34\nScientific,USD,5.01\nZero,USD,0.00\n"
        ))

    def test_large_totals_keep_every_cent(self):
        self.assert_success(self.run_input(HEADER + (
            "1,Large,USD,99999999999999999999999999.99\n"
            "2,Large,USD,99999999999999999999999999.99\n"
            "3,Large,USD,0.01\n"
            "4,Large,USD,-0.02\n"
        )), REPORT_HEADER + "Large,USD,199999999999999999999999999.97\n")

    def test_quoted_unicode_names_and_embedded_newlines_round_trip(self):
        records = io.StringIO(newline="")
        writer = csv.writer(records)
        writer.writerow(["invoice_id", "customer", "currency", "amount"])
        writer.writerow(["1", 'Éclair, "Paris"', "EUR", "1.23"])
        writer.writerow(["2", "Line\nBreak", "USD", "4.56"])
        writer.writerow(["3", "Carriage\rReturn", "USD", "7.89"])
        result = self.run_input(records.getvalue())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(list(csv.reader(io.StringIO(result.stdout.decode("utf-8"), newline=""))), [
            ["customer", "currency", "total"],
            ["Carriage\rReturn", "USD", "7.89"],
            ["Line\nBreak", "USD", "4.56"],
            ['Éclair, "Paris"', "EUR", "1.23"],
        ])

    def test_reordered_headers_and_unique_additional_columns(self):
        self.assert_success(self.run_input(
            "memo,amount,currency,customer,invoice_id\nunused,2.50,EUR,Ada,1\n"
        ), REPORT_HEADER + "Ada,EUR,2.50\n")

    def test_missing_duplicate_and_bom_headers(self):
        for header, reason in [
            ("invoice_id,customer,amount\n", "missing"),
            ("invoice_id,customer,currency,amount,amount\n", "duplicate"),
            ("invoice_id,customer,currency,amount,memo,memo\n", "duplicate"),
            ("\ufeff" + HEADER, "missing"),
        ]:
            with self.subTest(header=header):
                self.assert_invalid(self.run_input(header), "header", reason, 1)

    def test_duplicate_ids_fail_even_across_groups(self):
        for row in ["1,Ada,USD,2\n", "1,Bob,EUR,-1\n"]:
            with self.subTest(row=row):
                result = self.run_input(HEADER + "1,Ada,USD,1\n" + row)
                self.assert_invalid(result, "invoice_id", "duplicate", 3)
                self.assertIn("line 2", result.stderr.decode("utf-8"))

    def test_invoice_ids_preserve_exact_identity(self):
        self.assert_success(self.run_input(HEADER + (
            "1,Ada,USD,1\n 1 ,Ada,USD,2\n"
        )), REPORT_HEADER + "Ada,USD,3.00\n")

    def test_blank_and_whitespace_only_required_values(self):
        for field, column in [("invoice_id", 0), ("customer", 1), ("currency", 2)]:
            for blank in ["", " \t "]:
                with self.subTest(field=field, blank=blank):
                    values = ["2", "Ada", "USD", "2.00"]
                    values[column] = blank
                    result = self.run_input(HEADER + "1,Ada,USD,1\n" + ",".join(values) + "\n")
                    self.assert_invalid(result, field, "blank", 3)

    def test_invalid_final_amount_leaves_stdout_empty(self):
        for amount, reason in [
            ("", "invalid"), ("bad", "invalid"),
            ("NaN", "finite"), ("sNaN", "finite"),
            ("Infinity", "finite"), ("-Infinity", "finite"),
            ("1.005", "fractional"), ("-0.001", "fractional"),
            ("1e100", "invalid"),
        ]:
            with self.subTest(amount=amount):
                result = self.run_input(HEADER + f"1,Ada,USD,1\n2,Ada,USD,{amount}\n")
                self.assert_invalid(result, "amount", reason, 3)

    def test_short_long_and_blank_rows_fail(self):
        for record in ["2,Ada,USD\n", "2,Ada,USD,2,extra\n", "\n"]:
            with self.subTest(record=record):
                result = self.run_input(HEADER + "1,Ada,USD,1\n" + record)
                self.assert_invalid(result, "row", "columns", 3)

    def test_empty_file_fails_and_header_only_succeeds(self):
        self.assert_invalid(self.run_input(""), "header", "missing", 1)
        self.assert_success(self.run_input(HEADER), REPORT_HEADER)

    def test_malformed_final_csv_fails_before_output(self):
        result = self.run_input(HEADER + '1,Ada,USD,1\n2,"unfinished,USD,2\n')
        self.assert_invalid(result, "CSV", "unexpected end", 3)

    def test_multiline_positions_use_record_start(self):
        result = self.run_input(HEADER + '1,"Line\nBreak",USD,1\n2,"Other\nName",USD,bad\n')
        self.assert_invalid(result, "amount", "invalid", 4)

    def test_duplicate_id_first_occurrence_after_multiline_record(self):
        result = self.run_input(HEADER + '1,"Line\nBreak",USD,1\n2,Ada,USD,1\n2,Bob,EUR,2\n')
        self.assert_invalid(result, "invoice_id", "duplicate", 5)
        self.assertIn("line 4", result.stderr.decode("utf-8"))

    def test_invalid_utf8_after_valid_rows_has_no_report(self):
        result = self.run_input((HEADER + "1,Ada,USD,1\n").encode("utf-8") + b"2,\xff,USD,2\n")
        self.assert_invalid(result, "encoding", "byte")

    def test_missing_and_unreadable_paths_fail_cleanly(self):
        self.assert_invalid(self.run_cli(self.path), "file", "No such")
        self.path.mkdir()
        self.assert_invalid(self.run_cli(self.path), "file", "directory")

    def test_command_misuse(self):
        for arguments in [[], ["one.csv", "two.csv"], ["--help"], ["-invoices.csv"]]:
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"arguments", result.stderr)
                self.assertIn(b"usage: python3 -m invoice_totals <CSV-file-path>", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
