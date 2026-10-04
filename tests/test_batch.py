"""Exercise atomic library aggregation across caller-ordered invoice files."""

from contextlib import redirect_stderr, redirect_stdout
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from invoice_totals.batch import aggregate_csv_files
from invoice_totals.report import InvoiceInputError


HEADER = "invoice_id,customer,currency,amount\n"
VALID = HEADER + "1,Ada,USD,1\n"


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.prior = self.write("prior.csv", VALID)

    def write(self, name, contents):
        path = self.root / name
        path.write_bytes(contents.encode("utf-8") if isinstance(contents, str) else contents)
        return path

    def aggregate(self, paths):
        stdout, stderr = io.StringIO(), io.StringIO()
        before = sorted(self.root.iterdir())
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                return aggregate_csv_files(paths)
        finally:
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(sorted(self.root.iterdir()), before)

    def invalid(self, path, field, reason, line=None, cause=None):
        with self.assertRaises(InvoiceInputError) as caught:
            self.aggregate([self.prior, path])
        diagnostic = str(caught.exception)
        self.assertIn(str(path), diagnostic)
        self.assertIn(field, diagnostic)
        self.assertIn(reason, diagnostic)
        if line is not None:
            self.assertIn(f"line {line}", diagnostic)
        if cause is not None:
            self.assertIsInstance(caught.exception.__cause__, cause)
        return diagnostic

    def test_multiple_files_keep_currencies_customers_and_credits_exact(self):
        first = self.write("first.csv", HEADER + "a,Zebra,USD,2\nb,Ada,USD,0.10\nc,Ada,EUR,8.40\n")
        second = self.write("second.csv", HEADER + "d,Ada,USD,0.20\ne,Ada,USD,-0.05\nf,Bob,USD,-1.23\n")
        totals = self.aggregate(iter([str(first), second]))
        self.assertEqual(totals, {("Ada", "EUR"): 840, ("Ada", "USD"): 25,
                                  ("Bob", "USD"): -123, ("Zebra", "USD"): 200})
        self.assertEqual(list(totals), [("Ada", "EUR"), ("Ada", "USD"),
                                       ("Bob", "USD"), ("Zebra", "USD")])
        self.assertTrue(all(type(value) is int for value in totals.values()))

    def test_large_totals_retain_every_cent_across_files(self):
        first = self.write("first.csv", HEADER + "a,Large,USD,99999999999999999999999999.99\n")
        second = self.write("second.csv", HEADER + "b,Large,USD,99999999999999999999999999.99\nc,Large,USD,0.01\nd,Large,USD,-0.02\n")
        self.assertEqual(self.aggregate([first, second]), {("Large", "USD"): 19999999999999999999999999997})

    def test_original_strings_exact_ids_zero_and_supported_amounts(self):
        first = self.write("first.csv", HEADER + "a, Ada , USD ,5\n a , Ada , USD ,-5.000\nx,Ada,usd,-0.00\n")
        second = self.write("second.csv", HEADER + "b,Ada,USD,1e-2\nc,ada,USD, 5 \n")
        self.assertEqual(self.aggregate([first, second]), {
            (" Ada ", " USD "): 0, ("Ada", "USD"): 1,
            ("Ada", "usd"): 0, ("ada", "USD"): 500,
        })

    def test_quotes_unicode_and_line_breaks_are_preserved(self):
        data = io.StringIO(newline="")
        writer = csv.writer(data)
        writer.writerow(["invoice_id", "customer", "currency", "amount"])
        writer.writerow(['ID,"\nA', 'Éclair, "Paris"\r\nBakery', "E\nUR", "1.23"])
        path = self.write("quotes.csv", data.getvalue())
        self.assertEqual(self.aggregate([path]), {('Éclair, "Paris"\r\nBakery', "E\nUR"): 123})

    def test_reordered_headers_and_extra_columns(self):
        path = self.write("reordered.csv", "memo,amount,currency,customer,invoice_id\nx,2.50,EUR,Ada,other\n")
        self.assertEqual(self.aggregate([self.prior, path]), {("Ada", "EUR"): 250, ("Ada", "USD"): 100})

    def test_empty_and_header_only_batches_return_fresh_empty_dicts(self):
        first = self.aggregate([])
        first[("changed", "USD")] = 1
        self.assertEqual(self.aggregate(iter(())), {})
        a = self.write("a.csv", HEADER)
        b = self.write("b.csv", "amount,customer,currency,invoice_id,extra\n")
        self.assertEqual(self.aggregate([a, b, a]), {})

    def test_duplicates_across_groups_and_repeated_paths_include_both_locations(self):
        other = self.write("other.csv", HEADER + "1,Bob,EUR,bad\n")
        for path in (other, self.prior):
            with self.subTest(path=path):
                diagnostic = self.invalid(path, "invoice_id", "duplicate", 2)
                self.assertIn(f"first occurrence at {self.prior}: line 2", diagnostic)
                self.assertNotIn("amount:", diagnostic)

    def test_duplicate_locations_use_physical_record_starts_in_both_files(self):
        first = self.write("first.csv", HEADER + 'a,"Line\nBreak",USD,1\nshared,"First\nName",USD,2\n')
        second = self.write("second.csv", HEADER + 'b,"Other\nName",USD,3\nshared,"Second\nName",EUR,4\n')
        with self.assertRaises(InvoiceInputError) as caught:
            self.aggregate([first, second])
        self.assertIn(f"{second}: line 4: invoice_id:", str(caught.exception))
        self.assertIn(f"first occurrence at {first}: line 4", str(caught.exception))

    def test_duplicate_within_file_includes_both_source_locations(self):
        path = self.write("same.csv", HEADER + "same,Ada,USD,1\nsame,Bob,EUR,2\n")
        diagnostic = self.invalid(path, "invoice_id", "duplicate", 3)
        self.assertIn(f"first occurrence at {path}: line 2", diagnostic)

    def test_header_failures_after_valid_prior_file(self):
        for text, reason in [("", "missing"), ("invoice_id,customer,amount\n", "missing"),
                             (HEADER.rstrip() + ",amount\n", "duplicate"),
                             (HEADER.rstrip() + ",memo,memo\n", "duplicate"),
                             ("\ufeff" + HEADER, "missing")]:
            with self.subTest(text=text):
                path = self.write("bad.csv", text)
                self.invalid(path, "header", reason, 1, None if not text else ValueError)

    def test_invalid_widths_after_valid_rows(self):
        for row in ("short,Ada,USD\n", "long,Ada,USD,1,extra\n", "\n"):
            with self.subTest(row=row):
                path = self.write("bad.csv", HEADER + "good,Ada,USD,1\n" + row)
                self.invalid(path, "row", "columns", 3)

    def test_blank_values_after_valid_rows(self):
        for field, column in (("invoice_id", 0), ("customer", 1), ("currency", 2)):
            for blank in ("", " \t "):
                with self.subTest(field=field, blank=blank):
                    values = ["other", "Ada", "USD", "1"]
                    values[column] = blank
                    path = self.write("bad.csv", HEADER + "good,Ada,USD,1\n" + ",".join(values) + "\n")
                    self.invalid(path, field, "blank", 3)

    def test_amount_failures_after_valid_rows_preserve_causes(self):
        for value, reason in (("", "invalid"), ("bad", "invalid"), ("NaN", "finite"),
                              ("sNaN", "finite"), ("Infinity", "finite"), ("-Infinity", "finite"),
                              ("1.005", "fractional"), ("-0.001", "fractional"), ("1e100", "invalid")):
            with self.subTest(value=value):
                path = self.write("bad.csv", HEADER + f"good,Ada,USD,1\nother,Ada,USD,{value}\n")
                self.invalid(path, "amount", reason, 3, ValueError)

    def test_invalid_amount_record_position_after_multiline_rows(self):
        path = self.write("bad.csv", HEADER + 'good,"Line\nBreak",USD,1\nother,"Other\nName",USD,bad\n')
        self.invalid(path, "amount", "invalid", 4)

    def test_csv_and_encoding_failures_after_valid_prior_file(self):
        path = self.write("bad.csv", HEADER + 'good,Ada,USD,1\nother,"unfinished,USD,2\n')
        self.invalid(path, "CSV", "unexpected end", 3, csv.Error)
        path = self.write("bad.csv", (HEADER + "good,Ada,USD,1\n").encode() + b"other,\xff,USD,2\n")
        self.invalid(path, "encoding", "decoder byte", cause=UnicodeDecodeError)

    def test_missing_directory_and_nul_paths_are_file_errors(self):
        self.invalid(self.root / "missing.csv", "file", "No such", cause=OSError)
        self.invalid(self.root, "file", "directory", cause=OSError)
        self.invalid("invalid\x00.csv", "file", "null", cause=ValueError)

    def test_read_and_close_failures_after_prior_file_preserve_causes(self):
        class ReadFailure(io.StringIO):
            def __next__(self):
                if self.tell() == len(self.getvalue()):
                    raise OSError("synthetic read failure")
                return super().__next__()

        class CloseFailure(io.StringIO):
            def close(self):
                super().close()
                raise OSError("synthetic close failure")

        real_open = open
        for cls, reason in ((ReadFailure, "read failure"), (CloseFailure, "close failure")):
            with self.subTest(failure=cls.__name__):
                stream = cls(HEADER + "other,Ada,USD,2\n")

                def controlled_open(path, **kwargs):
                    return stream if path == "synthetic.csv" else real_open(path, **kwargs)

                with patch("builtins.open", side_effect=controlled_open):
                    self.invalid("synthetic.csv", "file", reason, cause=OSError)
                self.assertTrue(stream.closed)

    def test_file_closes_before_next_path_is_requested_and_return(self):
        streams = [io.StringIO(VALID), io.StringIO(HEADER + "other,Ada,USD,2\n")]

        def paths():
            yield "first.csv"
            self.assertTrue(streams[0].closed)
            yield "second.csv"
            self.assertTrue(streams[1].closed)

        with patch("builtins.open", side_effect=streams):
            self.assertEqual(self.aggregate(paths()), {("Ada", "USD"): 300})
        self.assertTrue(all(stream.closed for stream in streams))

    def test_argument_type_misuse_is_type_error(self):
        class BytesPath:
            def __fspath__(self):
                return b"bytes.csv"

        for paths in ("file.csv", self.prior, b"file.csv", None, 42,
                      [42], [None], [b"bytes.csv"], [BytesPath()], [object()]):
            with self.subTest(paths=paths):
                with self.assertRaises(TypeError):
                    self.aggregate(paths)

    def test_iterator_and_path_conversion_errors_are_not_reclassified(self):
        for error in (OSError("iterator failure"), ValueError("iterator failure"), RuntimeError("iterator failure")):
            with self.subTest(error=error):
                def paths():
                    yield self.prior
                    raise error

                with self.assertRaises(type(error)) as caught:
                    self.aggregate(paths())
                self.assertIs(caught.exception, error)

        error = OSError("path conversion failure")

        class BrokenPath:
            def __fspath__(self):
                raise error

        with self.assertRaises(OSError) as caught:
            self.aggregate([self.prior, BrokenPath()])
        self.assertIs(caught.exception, error)

    def test_calls_have_independent_state_after_success_and_failure(self):
        first = self.aggregate([self.prior])
        first[("Ada", "USD")] = 999
        first[("Extra", "EUR")] = 1
        self.assertEqual(self.aggregate([self.prior]), {("Ada", "USD"): 100})
        self.invalid(self.prior, "invoice_id", "duplicate")
        self.assertEqual(self.aggregate([self.prior]), {("Ada", "USD"): 100})


if __name__ == "__main__":
    unittest.main()
