"""Validate a complete invoice CSV and prepare an exact totals report."""

import csv
from decimal import Decimal
import io
from typing import TextIO

from invoice_totals.headers import parse_headers
from invoice_totals.money import parse_amount


class InvoiceInputError(ValueError):
    """An input diagnostic with its source, position, field and reason."""


def _integer_cents(amount: Decimal) -> int:
    # parse_amount returns finite Decimals quantized to exponent -2.
    parts = amount.as_tuple()
    cents = 0
    for digit in parts.digits:
        cents = cents * 10 + digit
    return -cents if parts.sign else cents


def _format_cents(cents: int) -> str:
    whole, fraction = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}{whole}.{fraction:02d}"


def _accumulate_invoices(
    stream: TextIO,
    source: str,
    totals: dict[tuple[str, str], int],
    invoice_locations: dict[str, tuple[str, int]],
    *,
    include_first_source: bool = False,
) -> None:
    """Validate one stream and accumulate into caller-owned private state."""
    reader = csv.reader(stream, strict=True)

    def invalid(line: int, field: str, reason: str) -> InvoiceInputError:
        return InvoiceInputError(f"{source}: line {line}: {field}: {reason}")

    try:
        header = next(reader, None)
        if header is None:
            raise invalid(1, "header", "missing invoice header")
        try:
            positions = parse_headers(header)
        except ValueError as error:
            raise invalid(1, "header", str(error)) from error

        while True:
            line = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            if len(row) != len(header):
                raise invalid(line, "row", f"expected {len(header)} columns, got {len(row)}")
            for field in ("invoice_id", "customer", "currency"):
                if not row[positions[field]].strip():
                    raise invalid(line, field, "must not be blank or whitespace-only")

            invoice_id = row[positions["invoice_id"]]
            if invoice_id in invoice_locations:
                first_source, first_line = invoice_locations[invoice_id]
                first_location = (
                    f"{first_source}: line {first_line}" if include_first_source
                    else f"line {first_line}"
                )
                raise invalid(
                    line, "invoice_id",
                    f"duplicate {invoice_id!r}; first occurrence at {first_location}",
                )
            invoice_locations[invoice_id] = (source, line)
            try:
                amount = parse_amount(row[positions["amount"]])
            except ValueError as error:
                raise invalid(line, "amount", str(error)) from error
            group = (row[positions["customer"]], row[positions["currency"]])
            totals[group] = totals.get(group, 0) + _integer_cents(amount)
    except csv.Error as error:
        raise invalid(max(reader.line_num, 1), "CSV", str(error)) from error


def prepare_report(stream: TextIO, source: str) -> str:
    """Read and validate every record before returning any report text."""
    totals: dict[tuple[str, str], int] = {}
    _accumulate_invoices(stream, source, totals, {})

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["customer", "currency", "total"])
    for customer, currency in sorted(totals):
        row = [customer, currency, _format_cents(totals[(customer, currency)])]
        if "\r" in customer or "\r" in currency:
            # With LF terminators, QUOTE_MINIMAL does not quote bare CR values.
            csv.writer(output, lineterminator="\n", quoting=csv.QUOTE_ALL).writerow(row)
        else:
            writer.writerow(row)
    return output.getvalue()
