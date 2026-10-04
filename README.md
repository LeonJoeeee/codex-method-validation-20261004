# Invoice totals — disposable test project

This public repository is a synthetic business fixture for development workflow validation. It contains no real invoices, customers, credentials or production data.

An accounts team exports CSV invoices with `invoice_id,customer,currency,amount` columns and wants a small command-line report of totals. The current project provides header and decimal amount parsers. The command entry point exists but does not read invoices or emit a report yet.

Requires Python 3.12 or newer, with no third-party dependencies.

```sh
python3 -m unittest discover -s tests -v
python3 -m invoice_totals
```

`sample_invoices.csv` is a small synthetic export. Reporting scope, grouping and the output contract still need a business decision; see `docs/PRD.md` for the starting context and `docs/architecture.md` for the current structure.
