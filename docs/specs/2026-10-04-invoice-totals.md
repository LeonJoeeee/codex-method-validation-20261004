# Invoice CSV totals design

Status: draft

## Purpose and scope

The accounts team needs an offline command that replaces weekly manual invoice addition with a CSV totals report. The synthetic `sample_invoices.csv` is the acceptance fixture. The confirmed issue contract is authoritative; this spec records its design and routine edge-case decisions for independent challenge before implementation.

Use Python 3.12 or newer and the standard library only. Keep repository documentation and source identifiers in English. Implement the existing `python3 -m invoice_totals` entry point without flags, persistence, dependencies, currency conversion, extra output modes, or release/version manifests.

## Command and observable contract

Invoke `python3 -m invoice_totals <CSV-file-path>` with exactly one positional path. No arguments, extra arguments, or flag-like arguments are command misuse: exit 2, print a usage diagnostic on stderr, and leave stdout empty. A path whose name begins with `-` can be passed with a directory prefix, for example `./-invoices.csv`.

Read UTF-8 text with `newline=""` for the CSV module. Accept the standard comma-delimited CSV dialect, including quoted commas, embedded newlines, and escaped double quotes; use `csv.reader(..., strict=True)` so parsing errors such as an unterminated quoted field fail. Do not sniff dialects or strip a UTF-8 byte-order mark. Headers are exact strings, so a BOM preceding `invoice_id` makes that required header missing.

On success exit 0, keep stderr empty, and emit CSV with exactly `customer,currency,total` as the header. Sort by original customer string, then original currency string, using Python's case-sensitive string order. Serialize with `csv.writer` for correct quoting and `lineterminator="\n"` for deterministic bytes. Totals always have exactly two decimal places, including `0.00`, and no extra summary rows appear.

The sample command must produce exactly:

```csv
customer,currency,total
Example Bakery,USD,0.25
Example Studio,EUR,8.40
```

Practical usage is `python3 -m invoice_totals sample_invoices.csv > totals.csv`. Shell redirection creates or truncates the destination before the command runs; an input failure therefore leaves that destination empty. For users preserving an earlier report, document an example that redirects to a temporary filename and replaces the final report only if the command succeeds.

On an input error exit 1, print one concise diagnostic on stderr, and emit no bytes on stdout. Validate the entire input and prepare the complete output in memory before any stdout write. This guarantee covers invalid input, not operating-system failures during the final write to the consumer; such a write failure cannot roll back bytes already consumed.

## Validation decisions

- The first CSV record is the header. Require `invoice_id`, `customer`, `currency`, and `amount`, located by name rather than position. Reuse `parse_headers` unchanged: duplicate names anywhere in the header fail, required names must match exactly, and unique additional columns are allowed.
- An empty file fails because it has no header. A valid header with no data records succeeds and emits only `customer,currency,total\n`.
- Every data record must have exactly the header's column count, including any additional columns. Short, long, and blank records fail instead of being skipped. A conventional final newline is a record terminator, not a blank record.
- `invoice_id`, `customer`, and `currency` must each contain at least one non-whitespace character. Use stripping only for the blankness check; preserve the original strings. Do not trim, case-fold, normalize, or infer any values.
- Track invoice IDs by their exact original strings across the entire file. A repeated ID fails even if its customer, currency, or amount differs. IDs such as `INV-1` and ` INV-1 ` are distinct under this rule. No deduplication occurs.
- Group by the exact `(customer, currency)` pair. Preserve surrounding customer whitespace when the name is nonblank. Currency values remain opaque, case-sensitive strings, without a code allowlist or conversion.
- Reuse `parse_amount` unchanged. Its existing `Decimal(value.strip())` and cent quantization determine accepted text and magnitude. Finite whole-cent values, integers, trailing zeroes, and scientific notation accepted by that parser remain accepted; malformed, nonfinite, fractional-cent, and parser-rejected magnitudes fail. Do not add an independent amount grammar or round rejected amounts.
- Negative amounts offset positive amounts in their group. Retain groups whose total is zero. Render numeric zero as `0.00`, including cancellation and negative zero.

## Components and data flow

Keep the existing `invoice_totals/headers.py` and `invoice_totals/money.py` contracts. Add one focused `invoice_totals/report.py` module for ingestion, validation, aggregation, and prepared report serialization. Keep `invoice_totals/__main__.py` responsible for argument count, file opening, stderr diagnostics, process status, and the final stdout write.

Proposed report interface: `prepare_report(stream: TextIO, source: str) -> str`. It reads the CSV records, obtains named column positions from `parse_headers`, validates row shape and values, accumulates totals, and returns the complete report text. An `InvoiceInputError` carries a ready diagnostic for domain and CSV failures. Filesystem and UTF-8 decoding exceptions are caught at the CLI boundary and translated to the same concise error style.

Use integer cents for aggregation rather than adding `Decimal` values under a finite decimal context. Convert each already-parsed cent-precision value to integer cents from its `Decimal.as_tuple()` digits, sign, and exponent, without multiplication or quantization that could round. Add Python integers per group. Format totals using sign and integer quotient/remainder, so a sum exceeding the amount parser's individual precision remains exact. This preserves the existing parser while preventing precision loss in totals.

Build the output using `io.StringIO` and `csv.writer` after all input has been consumed successfully. The CLI performs its single report write only after `prepare_report` returns and the input context has closed successfully. Memory grows with distinct invoice IDs, grouping pairs, the largest CSV record, and the prepared report; no input-size limit or streaming output is introduced.

Alternatives considered: streaming output violates the invalid-final-row requirement; accumulating `Decimal` directly requires precision management that integer cents avoids. The selected design fits the small offline command without additional layers or storage.

## Diagnostics and failure boundaries

Diagnostics identify the supplied file path, available position, field, and reason. For ordinary row errors, use the physical starting line of the CSV record; track this before reading each record because quoted fields may span lines. Header errors identify line 1 and the header field. Row-width errors identify the record start and `row`. A repeated ID diagnostic identifies `invoice_id`, its value, and the first occurrence's starting line.

For `csv.Error`, report the reader's available physical line and `CSV`, including the parsing reason. For UTF-8 errors, identify `encoding` and the decoder's available byte position with its reason, without claiming a file-global offset that buffered decoding cannot establish. For filesystem errors, identify `file` and the OS reason; no row position exists. Command misuse identifies `arguments` and includes `usage: python3 -m invoice_totals <CSV-file-path>`.

Catch anticipated `ValueError` from helpers, `csv.Error`, `UnicodeDecodeError`, and `OSError` at their appropriate boundaries. Do not blanket-catch programming errors or produce tracebacks for expected input failures. Input-open, input-read, and input-close failures all occur before report publication. Document and test these distinct boundaries without introducing recovery modes.

## Verification and documentation

Preserve all existing helper tests. Add subprocess-based end-to-end tests in `tests/test_cli.py` using temporary synthetic files, checking exit status, stdout, and stderr. The matrix must cover:

- The exact sample report; customer/currency isolation; negative credits; `0.10 + 0.20`; exact large totals beyond default decimal addition precision; zero and negative-zero rendering; fixed cents.
- Original customer spelling and surrounding whitespace; exact currency and invoice-ID identity; deterministic customer/currency sorting; quoted commas, quotes, and embedded newlines.
- Reordered headers; unique extra columns; missing and duplicate headers; duplicate invoice IDs within and across groups.
- Empty and header-only files; short, long, and blank records; blank and whitespace-only IDs, customers, and currencies.
- Malformed, nonfinite, and fractional-cent amounts; parser-supported spelling such as scientific notation; invalid last data rows and malformed final CSV with empty stdout.
- Missing and unreadable files; invalid UTF-8 after valid records; CSV parsing errors and multiline line positions; zero or extra arguments and flag-like misuse. Unreadable-file tests should use a directory path or controlled failing input stream rather than relying only on permission bits that privileged users can bypass. Controlled stream failures can exercise otherwise nondeterministic read/close errors.

Run the complete suite from the repository root: `python3 -m unittest discover -s tests -v`. Run `python3 -m invoice_totals sample_invoices.csv` separately and retain its exact stdout, stderr, and exit status. Keep program behavior verified against the complete confirmed contract, not only the acceptance fixture.

Update `README.md`, `docs/PRD.md`, and `docs/architecture.md` together with implementation to describe the settled behavior, errors, empty-input decisions, CSV syntax, exact grouping, and practical redirection. This spec is the design record; the issue/PR carries execution state and evidence.

## Implementation sequence after the pre-code challenge

1. Add failing CLI tests for the sample, aggregation, output preparation, validation, and error cases; run them to record the expected failure against the empty entry point.
2. Implement the report preparation module and CLI boundary, retaining helper behavior and adding meaningful precision/error-boundary tests where subprocess coverage cannot directly induce the condition.
3. Update the existing documentation, inspect the complete diff against this spec and the issue, and run the full suite and exact sample CLI on the final state.
4. Return an issue-linked PR with original evidence and tree accounting. Independent Goal/Floor review and CI on the exact integration identity remain integration gates owned by the orchestrator.
