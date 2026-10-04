# Current architecture

The offline command uses Python 3.12+ and the standard library. No services, dependencies or persistent state are required.

`invoice_totals/__main__.py` validates the one-path invocation, opens UTF-8 text with CSV-compatible newline handling, and calls `prepare_report`. It closes the input before writing and flushing the complete report to stdout. Expected file/encoding/domain errors become concise stderr diagnostics and nonzero statuses; command misuse exits 2. Input failures publish no report.

`invoice_totals/report.py` exposes `prepare_report(stream: TextIO, source: str) -> str`. It reads strict comma-delimited CSV, checks record width and required nonblank values, rejects exact duplicate invoice IDs across the file, and groups by exact customer/currency strings. Physical record starts are retained for row diagnostics, including multiline CSV values. `InvoiceInputError` carries source, position, field and reason. It reuses the existing helpers without changing their contracts:

- `invoice_totals/headers.py`: named column lookup and missing/duplicate header rejection.
- `invoice_totals/money.py`: finite `Decimal` values quantized to whole cents, rejecting malformed, nonfinite, fractional-cent and unsupported-magnitude amounts.

Parsed Decimals have exponent -2. Their tuple digits/sign become Python integer cents without context-sensitive decimal arithmetic. Integer addition and quotient/remainder formatting keep totals exact even beyond the individual amount precision limit.

After all input validates, `csv.writer` serializes sorted groups into an in-memory string, with two-place totals and LF record terminators. CSV quoting preserves delimiters, quotes and embedded newlines, including carriage returns. A header-only file emits only the report header; an empty file and blank/wrong-width records fail. Memory grows with distinct invoice IDs, groups, the largest record and prepared report. The CLI's final output write is outside the input atomicity guarantee because downstream publication cannot be rolled back.

`tests/test_helpers.py` retains parser contract coverage. `tests/test_cli.py` exercises real subprocess behavior for reporting, exact values, sorting, quoting, validation, error positions and command misuse. `tests/test_io_failures.py` uses controlled streams for read/close failures and verifies input closure before publication. Run the complete suite with `python3 -m unittest discover -s tests -v`.

See [the design record](specs/2026-10-04-invoice-totals.md) for alternatives and confirmed edge cases, and [README.md](../README.md) for invocation and redirection. A failed command can truncate a directly redirected destination; use a separate output filename and success-only replacement to preserve an existing report.
