"""Core calculations for the Award Travel Value Scanner."""

from decimal import ROUND_HALF_UP, Decimal
from typing import cast

import requests

SEATS_AERO_SEARCH_URL = "https://api.seats.aero/v1/search"
REQUEST_TIMEOUT_SECONDS = 10

TRANSFER_RATIOS: dict[str, Decimal] = {
    "amex_membership_rewards": Decimal("1.00"),
    "chase_ultimate_rewards": Decimal("1.00"),
    "capital_one_miles": Decimal("1.00"),
}


def calculate_cpp(
    cash_price: Decimal,
    taxes_and_fees: Decimal,
    points_required: int,
) -> Decimal:
    """Calculate cents per point for an award redemption.

    Args:
        cash_price: Comparable cash price for the itinerary in dollars.
        taxes_and_fees: Out-of-pocket taxes and fees in dollars.
        points_required: Number of points required for the redemption.

    Returns:
        CPP rounded to two decimal places using half-up rounding.

    Raises:
        ValueError: If any monetary value is negative, taxes exceed the cash
            price, or the redemption requires no positive number of points.
    """
    if cash_price < 0:
        raise ValueError("cash_price must not be negative")
    if taxes_and_fees < 0:
        raise ValueError("taxes_and_fees must not be negative")
    if points_required <= 0:
        raise ValueError("points_required must be greater than zero")
    if taxes_and_fees > cash_price:
        raise ValueError("taxes_and_fees cannot exceed cash_price")

    cpp = (cash_price - taxes_and_fees) / Decimal(points_required) * 100
    return cpp.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def classify_redemption(cpp: Decimal) -> str:
    """Classify a redemption based on its CPP value.

    Args:
        cpp: Cents per point for the redemption.

    Returns:
        ``High Value`` for CPP strictly greater than 2.0; otherwise
        ``Standard Value``.
    """
    if cpp > Decimal("2.0"):
        return "High Value"
    return "Standard Value"


def fetch_award_flights(
    departure: str,
    arrival: str,
    travel_date: str,
    api_key: str,
    endpoint: str = SEATS_AERO_SEARCH_URL,
) -> list[dict[str, object]]:
    """Fetch award-flight options from Seats.aero.

    Args:
        departure: Three-letter departure airport code.
        arrival: Three-letter arrival airport code.
        travel_date: Travel date in ``YYYY-MM-DD`` format.
        api_key: Seats.aero API key.
        endpoint: Seats.aero search endpoint, overridable for testing.

    Returns:
        Award-flight records returned by the provider.

    Raises:
        requests.HTTPError: If the provider returns an HTTP error response.
        ValueError: If the provider returns an unsupported response shape.
    """
    response = requests.get(
        endpoint,
        params={
            "origin_airport": departure,
            "destination_airport": arrival,
            "start_date": travel_date,
            "end_date": travel_date,
            "take": 100,
        },
        headers={"X-API-Key": api_key},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return _extract_records(response.json())


def fetch_cash_price(
    departure: str,
    arrival: str,
    travel_date: str,
    api_key: str,
    endpoint: str,
) -> Decimal:
    """Fetch a comparable cash fare from a flight-search API.

    Args:
        departure: Three-letter departure airport code.
        arrival: Three-letter arrival airport code.
        travel_date: Travel date in ``YYYY-MM-DD`` format.
        api_key: Flight-search API key.
        endpoint: Configured flight-search price endpoint.

    Returns:
        Comparable cash fare in dollars.

    Raises:
        requests.HTTPError: If the provider returns an HTTP error response.
        ValueError: If the endpoint is missing or the response has no valid
            ``cash_price`` value.
    """
    if not endpoint:
        raise ValueError("cash price API endpoint is required")

    response = requests.get(
        endpoint,
        params={
            "origin": departure,
            "destination": arrival,
            "date": travel_date,
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "cash_price" not in payload:
        raise ValueError("cash price response must contain cash_price")

    try:
        return Decimal(str(payload["cash_price"]))
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ValueError("cash_price must be a valid number") from error


def _extract_records(payload: object) -> list[dict[str, object]]:
    """Extract award records from a list or a response containing ``data``."""
    if isinstance(payload, dict):
        payload = payload.get("data")
    if not isinstance(payload, list) or not all(
        isinstance(record, dict) for record in payload
    ):
        raise ValueError("award response must be a list or contain a data list")
    return cast(list[dict[str, object]], payload)
