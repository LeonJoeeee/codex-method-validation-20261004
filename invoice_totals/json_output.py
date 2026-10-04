"""Serialize precomputed integer-cent totals without invoice ingestion."""

from collections.abc import Mapping
import json


def _format_cents(cents: int) -> str:
    whole, fraction = divmod(abs(cents), 100)
    chunks = []
    # Each converted chunk stays below Python's integer-string digit limit.
    while whole >= 1_000_000_000:
        whole, chunk = divmod(whole, 1_000_000_000)
        chunks.append(f"{chunk:09d}")
    digits = str(whole) + "".join(reversed(chunks))
    sign = "-" if cents < 0 else ""
    return f"{sign}{digits}.{fraction:02d}"


def totals_to_json(totals: Mapping[tuple[str, str], int]) -> str:
    """Return compact Unicode JSON sorted by original customer and currency.

    Keys must be two-string tuples with nonblank customer and currency;
    values must have exact type int. Invalid types raise TypeError, and
    blank strings raise ValueError. The input is never mutated.
    """
    if not isinstance(totals, Mapping):
        raise TypeError("totals must be a mapping")

    entries = []
    for key, cents in totals.items():
        if (not isinstance(key, tuple) or len(key) != 2
                or not all(isinstance(part, str) for part in key)):
            raise TypeError("each key must be a (customer, currency) tuple of two strings")
        customer, currency = key
        if not customer.strip():
            raise ValueError("customer must not be blank or whitespace-only")
        if not currency.strip():
            raise ValueError("currency must not be blank or whitespace-only")
        if type(cents) is not int:
            raise TypeError("integer cents must have exact type int")
        entries.append((customer, currency, cents))

    rows = [
        {"customer": customer, "currency": currency, "total": _format_cents(cents)}
        for customer, currency, cents in sorted(entries, key=lambda entry: entry[:2])
    ]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
