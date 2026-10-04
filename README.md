# Invoice totals — disposable test project

This public repository is a synthetic business fixture for development workflow validation. It contains no real invoices, customers, credentials or production data.

Requires Python 3.12 or newer and the standard library only. Run from the checkout:

```sh
python3 -m invoice_totals sample_invoices.csv
python3 -m unittest discover -s tests -v
```

The command reads one UTF-8 CSV file and writes totals by the exact original customer name and currency. Negative credit notes offset invoices; currencies are kept separate without conversion. The sample report is:

```csv
customer,currency,total
Example Bakery,USD,0.25
Example Studio,EUR,8.40
```

## Input and output

Require exact `invoice_id`, `customer`, `currency`, and `amount` headers in any order. Unique additional columns are allowed; missing or duplicate headers fail. Every data record must have the same width as the header. Standard comma-delimited CSV quoting supports commas, quotes, and embedded newlines. No dialect detection or UTF-8 BOM removal occurs.

Invoice IDs, customers, and currencies must not be blank or whitespace-only. Original strings are preserved, including surrounding whitespace: `Ada` and ` Ada ` are different customers, and `USD` and `usd` are different currencies. Repeated exact invoice IDs fail the entire file, even across customers or currencies.

The existing decimal parser accepts finite whole-cent amounts, including integer values and scientific notation. Malformed, nonfinite, fractional-cent, and parser-rejected large amounts fail without rounding. Accepted amounts are accumulated in integer cents, keeping large totals exact. Output is sorted by original customer, then currency, with fixed two-place totals and LF record terminators. Zero-total groups remain in the report.

An empty file fails for a missing header. A valid header-only file produces only the report header. Blank, short, or long data records fail. A normal final newline is accepted.

## Errors and saving a report

Success exits 0 with empty stderr. Invalid input exits 1 with a diagnostic identifying the file, available line or decoder-byte position, field, and reason. Missing/unreadable files, invalid UTF-8, malformed CSV, and invalid final rows leave stdout empty. The command validates the entire input, prepares the report, and closes the input before publishing it. Memory grows with invoice IDs, groups, and the prepared report. An output-device failure during final publication cannot roll back bytes already written.

Exactly one path is required. Missing/extra arguments and flag-like arguments exit 2 with usage on stderr. Prefix a filename beginning with `-` with a directory, such as `./-invoices.csv`.

For ordinary redirection:

```sh
python3 -m invoice_totals sample_invoices.csv > totals.csv
```

The shell creates or truncates `totals.csv` before the command runs, so an input failure leaves that file empty. To preserve an existing report on failure, choose a separate temporary output name and replace the report only on success:

```sh
python3 -m invoice_totals sample_invoices.csv > totals.new.csv && mv totals.new.csv totals.csv
```

Use an output path different from the input CSV. See [the requirements](docs/PRD.md), [architecture](docs/architecture.md), and [design record](docs/specs/2026-10-04-invoice-totals.md).

## Library usage

The two independent library APIs exchange mappings of exact `(customer, currency)` strings to Python integer cents. They preserve original spelling and whitespace, keep currencies separate, and retain negative and zero totals.

For already-computed totals, use the JSON serializer directly:

```python
from invoice_totals.json_output import totals_to_json

text = totals_to_json({("示例客户", "CNY"): 125})
# '[{"customer":"示例客户","currency":"CNY","total":"1.25"}]'
```

`totals_to_json(totals)` accepts a mapping with two-string tuple keys and values of exact type `int`. It rejects booleans, integer subclasses, floats, Decimal values, and coercible strings with `TypeError`; invalid mapping/key types or shapes also raise `TypeError`. Blank or whitespace-only customer/currency strings raise `ValueError`. No coercion or rounding occurs.

The returned JSON is compact, without a trailing newline, and sorted by original customer then currency. Each object has `customer`, `currency`, and `total` fields in that order. Amounts are exact two-place strings, including `"-0.01"` and `"0.00"`, with no integer magnitude limit imposed by this API. Unicode stays visible and quotes/control characters are escaped. An empty mapping returns exactly `"[]"`. The function does not mutate its input, read files, or publish output.

To aggregate multiple CSV files, then serialize the result:

```python
from invoice_totals.batch import aggregate_csv_files
from invoice_totals.json_output import totals_to_json

totals = aggregate_csv_files(["sample_invoices.csv"])
text = totals_to_json(totals)
# '[{"customer":"Example Bakery","currency":"USD","total":"0.25"},{"customer":"Example Studio","currency":"EUR","total":"8.40"}]'
```

`aggregate_csv_files(paths)` returns integer-cent totals for the supplied CSV paths; an empty iterable returns `{}`. The JSON API also works with precomputed mappings from other sources and does not import or execute the batch API. These library calls add no command flags or CLI output modes.
