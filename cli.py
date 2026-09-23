"""Command-line interface for the Award Travel Value Scanner."""

import os
import re
from collections.abc import Sequence
from decimal import Decimal

import click

import scanner

AIRPORT_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


@click.command(name="scan")
@click.option("--origin", required=True, help="Departure airport code.")
@click.option("--dest", required=True, help="Arrival airport code.")
@click.option(
    "--date", "travel_date", required=True, help="Travel date in YYYY-MM-DD format."
)
@click.option(
    "--cabin",
    type=click.Choice(scanner.SUPPORTED_CABINS, case_sensitive=False),
    default="business",
    show_default=True,
)
@click.option("--min-cpp", type=float, default=2.0, show_default=True)
def scan(
    origin: str,
    dest: str,
    travel_date: str,
    cabin: str,
    min_cpp: float,
) -> None:
    """Scan award flights and print their redemption value."""
    origin = _validate_airport(origin, "origin")
    dest = _validate_airport(dest, "dest")
    if origin == dest:
        raise click.BadParameter("origin and dest must be different airports")

    awards = scanner.fetch_award_flights(
        departure=origin,
        arrival=dest,
        travel_date=travel_date,
        api_key=os.getenv("SEATS_AERO_API_KEY", ""),
        cabin=cabin.lower(),
    )
    cash_price = scanner.fetch_cash_price(
        departure=origin,
        arrival=dest,
        travel_date=travel_date,
        api_key=os.getenv("CASH_PRICE_API_KEY", ""),
        endpoint=os.getenv("CASH_PRICE_API_URL", ""),
    )
    click.echo(_format_results(origin, dest, travel_date, cash_price, awards, min_cpp))


def main(args: Sequence[str] | None = None) -> int:
    """Run the scan command from a terminal or a test argument list."""
    command_args = list(args) if args is not None else None
    if command_args and command_args[0] == "scan":
        command_args = command_args[1:]
    try:
        scan.main(args=command_args, standalone_mode=False)
    except click.ClickException as error:
        error.show()
        raise SystemExit(error.exit_code) from error
    return 0


def _validate_airport(value: str, option_name: str) -> str:
    """Validate and normalize a three-letter airport code."""
    normalized = value.upper()
    if not AIRPORT_CODE_PATTERN.fullmatch(normalized):
        raise click.BadParameter(
            "must be a three-letter airport code", param_hint=f"--{option_name}"
        )
    return normalized


def _format_results(
    origin: str,
    dest: str,
    travel_date: str,
    cash_price: Decimal,
    awards: list[dict[str, object]],
    min_cpp: float,
) -> str:
    """Format route, valuation, and transfer-partner details."""
    lines = [f"Route & Date: {origin} -> {dest} | {travel_date}"]
    for award in awards:
        points = int(award["points_required"])
        taxes_and_fees = Decimal(str(award.get("taxes_and_fees", "0")))
        cpp = scanner.calculate_cpp(cash_price, taxes_and_fees, points)
        label = (
            "High Value (>2.0 CPP)" if cpp > Decimal(str(min_cpp)) else "Standard Value"
        )
        currency = str(award.get("transfer_currency", ""))
        partners = scanner.TRANSFER_PARTNERS.get(currency, ("None configured",))
        lines.extend(
            [
                f"Cash Price: ${cash_price:.2f} | Award Miles: {points:,}",
                f"CPP: {cpp:.2f} | {label}",
                f"Transfer partners: {', '.join(partners)}",
            ]
        )
    if not awards:
        lines.append("No award flights found.")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
