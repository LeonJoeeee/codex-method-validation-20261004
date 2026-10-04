"""Parse finite invoice amounts without silently rounding fractional cents."""

from decimal import Decimal, InvalidOperation


def parse_amount(value: str) -> Decimal:
    try:
        amount = Decimal(value.strip())
        if not amount.is_finite():
            raise ValueError("invoice amount must be finite")
        cents = amount.quantize(Decimal("0.01"))
        if amount != cents:
            raise ValueError("invoice amount has fractional cents")
        return cents
    except InvalidOperation as error:
        raise ValueError("invalid invoice amount") from error
