"""Offline invoice CSV totals command."""

import sys

from invoice_totals.report import InvoiceInputError, prepare_report


def main() -> int:
    arguments = sys.argv[1:]
    if len(arguments) != 1 or arguments[0].startswith("-"):
        print("arguments: usage: python3 -m invoice_totals <CSV-file-path>", file=sys.stderr)
        return 2

    source = arguments[0]
    try:
        with open(source, encoding="utf-8", newline="") as stream:
            report = prepare_report(stream, source)
    except InvoiceInputError as error:
        print(error, file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        print(
            f"{source}: encoding: invalid UTF-8 at decoder byte {error.start}: {error.reason}",
            file=sys.stderr,
        )
        return 1
    except OSError as error:
        print(f"{source}: file: {error}", file=sys.stderr)
        return 1

    try:
        sys.stdout.write(report)
        sys.stdout.flush()
    except OSError as error:
        print(f"{source}: output: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
