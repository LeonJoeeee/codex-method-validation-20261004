# Invoice totals

## Purpose

Help an accounts team replace weekly manual invoice addition with an offline CSV totals report. All repository invoices and customers are synthetic. The program runs from its checkout; no release or distribution form is defined.

## Reporting contract

Invoke `python3 -m invoice_totals <CSV-file-path>` to read UTF-8. Require exact `invoice_id`, `customer`, `currency`, and `amount` headers, locating fields by name. Allow reordered and unique extra columns; reject missing/duplicate headers and records of the wrong width.

Group by the exact original customer and currency strings. Preserve spelling and surrounding whitespace for nonblank values, keep currencies separate, and subtract negative credits. Invoice IDs, customers, and currencies must contain a non-whitespace character. Repeated exact invoice IDs invalidate the entire file, without deduplication.

Retain the existing amount parser's finite whole-cent contract, including parser-supported integer/scientific notation and magnitude limits. Malformed, nonfinite, or fractional-cent amounts fail without rounding. Sum accepted amounts exactly, including large totals. Emit `customer,currency,total` CSV, sorted by original customer and then currency, with fixed two-place totals and no summary rows. Retain zero-total groups.

## Failure and empty-input behavior

Validate all input and prepare the complete report before publication, including successfully closing the input. On invalid input exit 1, identify the file, available position, field and reason on stderr, and leave stdout empty. This includes file-access/read/close failures, decoding errors, malformed CSV and invalid final rows. Success exits 0 with empty stderr. Final output-device failures may leave bytes already consumed.

Use standard comma-delimited CSV quoting with strict parsing. An empty file fails; a valid header with no data produces only the report header. Blank, short, and long records fail. Do not sniff dialects or remove a BOM. Exactly one path is required; command misuse exits 2 with usage on stderr.

## Acceptance and constraints

`python3 -m invoice_totals sample_invoices.csv` must yield exactly:

```csv
customer,currency,total
Example Bakery,USD,0.25
Example Studio,EUR,8.40
```

Keep Python 3.12+, the standard library, and offline operation. Do not normalize names, infer/convert currencies, add persistence, flags, dependencies, or extra output modes. Full verification is `python3 -m unittest discover -s tests -v`; tests cover process output, validation, precision, quoting, positions and input lifecycle failures. [README.md](../README.md) describes practical redirection, including preserving an earlier report on failure. [The design record](specs/2026-10-04-invoice-totals.md) contains the settled decisions.
