"""Verify input lifecycle failures that cannot be induced reliably by files."""

from contextlib import redirect_stderr, redirect_stdout
import io
import unittest
from unittest.mock import patch

from invoice_totals.__main__ import main


VALID_INPUT = "invoice_id,customer,currency,amount\n1,Ada,USD,1\n"


class ReadFailure(io.StringIO):
    def __init__(self):
        super().__init__(VALID_INPUT)
        self.records = 0

    def __next__(self):
        self.records += 1
        if self.records > 2:
            raise OSError("synthetic read failure")
        return super().__next__()


class CloseFailure(io.StringIO):
    def close(self):
        super().close()
        raise OSError("synthetic close failure")


class LifecycleTests(unittest.TestCase):
    def invoke(self, stream):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["invoice_totals", "synthetic.csv"]), \
             patch("builtins.open", return_value=stream), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            status = main()
        return status, stdout.getvalue(), stderr.getvalue()

    def test_read_failure_after_valid_row_keeps_stdout_empty(self):
        status, stdout, stderr = self.invoke(ReadFailure())
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertIn("synthetic.csv: file:", stderr)
        self.assertIn("synthetic read failure", stderr)

    def test_close_failure_keeps_stdout_empty(self):
        status, stdout, stderr = self.invoke(CloseFailure(VALID_INPUT))
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertIn("synthetic.csv: file:", stderr)
        self.assertIn("synthetic close failure", stderr)

    def test_input_is_closed_before_report_publication(self):
        stream = io.StringIO(VALID_INPUT)

        class RequireClosedInput(io.StringIO):
            def write(output, value):
                if not stream.closed:
                    raise AssertionError("report published before input closed")
                return super().write(value)

        stdout, stderr = RequireClosedInput(), io.StringIO()
        with patch("sys.argv", ["invoice_totals", "synthetic.csv"]), \
             patch("builtins.open", return_value=stream), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            status = main()
        self.assertEqual(status, 0)
        self.assertEqual(stdout.getvalue(), "customer,currency,total\nAda,USD,1.00\n")
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
