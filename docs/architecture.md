# Current architecture

`invoice_totals/headers.py` maps required CSV column names to positions and rejects missing or duplicate headers. `invoice_totals/money.py` turns amount text into `Decimal` values with cent precision and rejects malformed, nonfinite or fractional-cent amounts.

`invoice_totals/__main__.py` contains the reserved command entry point. It returns success without output; CSV ingestion, aggregation and reporting have not been designed or implemented.

`tests/test_helpers.py` covers the existing parser contracts. The project has no external services or dependencies. Future report calculations and output formatting can remain separate responsibilities; their interfaces follow the settled business reporting contract.
