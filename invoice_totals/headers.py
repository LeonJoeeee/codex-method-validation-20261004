"""Map the required invoice columns to their CSV positions."""


def parse_headers(fields: list[str]) -> dict[str, int]:
    if len(fields) != len(set(fields)):
        raise ValueError("duplicate invoice header")
    required = {"invoice_id", "customer", "currency", "amount"}
    missing = required.difference(fields)
    if missing:
        raise ValueError("missing invoice headers: " + ", ".join(sorted(missing)))
    return {field: position for position, field in enumerate(fields)}
