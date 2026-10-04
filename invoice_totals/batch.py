"""Aggregate invoice files atomically into exact customer/currency cents."""

from collections.abc import Iterable
import os

from invoice_totals.report import InvoiceInputError, _accumulate_invoices


def aggregate_csv_files(
    paths: Iterable[str | os.PathLike[str]],
) -> dict[tuple[str, str], int]:
    """Return fresh sorted totals after all files validate and close.

    Exact invoice IDs must be unique across the entire batch. Expected
    invoice/file errors raise InvoiceInputError with their source and cause;
    argument misuse raises TypeError. Iterator/path-conversion errors propagate.
    No output is printed or written, including on failure.
    """
    if isinstance(paths, (str, bytes, os.PathLike)):
        raise TypeError("paths must be an iterable of paths, not a single path")

    totals: dict[tuple[str, str], int] = {}
    invoice_locations: dict[str, tuple[str, int]] = {}
    for path in paths:
        # Iterator advancement and path conversion are outside file wrapping.
        source = os.fspath(path)
        if not isinstance(source, str):
            raise TypeError("each path must be a string or a path-like returning a string")
        try:
            try:
                stream = open(source, encoding="utf-8", newline="")
            except ValueError as error:
                # open() rejects embedded NULs with ValueError, not OSError.
                if "\x00" not in source:
                    raise
                raise InvoiceInputError(f"{source}: file: {error}") from error
            with stream:
                _accumulate_invoices(
                    stream, source, totals, invoice_locations, include_first_source=True,
                )
        except UnicodeDecodeError as error:
            raise InvoiceInputError(
                f"{source}: encoding: invalid UTF-8 at decoder byte {error.start}: {error.reason}"
            ) from error
        except UnicodeError as error:
            raise InvoiceInputError(f"{source}: encoding: {error}") from error
        except OSError as error:
            raise InvoiceInputError(f"{source}: file: {error}") from error

    return {key: totals[key] for key in sorted(totals)}
