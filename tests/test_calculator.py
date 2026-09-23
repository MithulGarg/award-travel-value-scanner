"""Tests for award travel CPP calculations and transfer partner ratios."""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from scanner import (
    TRANSFER_RATIOS,
    calculate_cpp,
    classify_redemption,
    fetch_award_flights,
    fetch_cash_price,
)


def test_calculate_cpp_subtracts_taxes_before_dividing_by_points() -> None:
    """Calculate CPP from the net cash value of an award redemption."""
    cpp = calculate_cpp(
        cash_price=Decimal("500.00"),
        taxes_and_fees=Decimal("50.00"),
        points_required=25_000,
    )

    assert cpp == Decimal("1.80")


def test_calculate_cpp_rounds_to_two_decimal_places() -> None:
    """Round repeating CPP values to two decimal places."""
    cpp = calculate_cpp(
        cash_price=Decimal("401.00"),
        taxes_and_fees=Decimal("50.00"),
        points_required=10_000,
    )

    assert cpp == Decimal("3.51")


@pytest.mark.parametrize("points_required", [0, -1])
def test_calculate_cpp_rejects_non_positive_points(points_required: int) -> None:
    """Reject redemptions that cannot produce a meaningful CPP value."""
    with pytest.raises(ValueError, match="points_required"):
        calculate_cpp(Decimal("500.00"), Decimal("50.00"), points_required)


def test_calculate_cpp_rejects_taxes_above_cash_price() -> None:
    """Reject a redemption whose eligible cash value would be negative."""
    with pytest.raises(ValueError, match="taxes_and_fees"):
        calculate_cpp(Decimal("50.00"), Decimal("75.00"), 10_000)


def test_calculate_cpp_rejects_negative_money_values() -> None:
    """Reject negative cash prices and taxes or fees."""
    with pytest.raises(ValueError, match="cash_price"):
        calculate_cpp(Decimal("-1.00"), Decimal("0.00"), 10_000)

    with pytest.raises(ValueError, match="taxes_and_fees"):
        calculate_cpp(Decimal("100.00"), Decimal("-1.00"), 10_000)


@pytest.mark.parametrize(
    ("cpp", "expected_label"),
    [
        (Decimal("2.01"), "High Value"),
        (Decimal("2.00"), "Standard Value"),
        (Decimal("1.99"), "Standard Value"),
    ],
)
def test_classify_redemption_uses_strict_high_value_threshold(
    cpp: Decimal, expected_label: str
) -> None:
    """Only CPP strictly greater than 2.0 receives the high-value label."""
    assert classify_redemption(cpp) == expected_label


@pytest.mark.parametrize(
    ("currency", "expected_ratio"),
    [
        ("amex_membership_rewards", Decimal("1.00")),
        ("chase_ultimate_rewards", Decimal("1.00")),
        ("capital_one_miles", Decimal("1.00")),
    ],
)
def test_transfer_ratios_for_supported_programs(
    currency: str, expected_ratio: Decimal
) -> None:
    """Verify the configured transfer ratio for each supported currency."""
    assert TRANSFER_RATIOS[currency] == expected_ratio


def test_transfer_ratios_contain_only_supported_programs() -> None:
    """Keep the initial transfer configuration limited to the requested programs."""
    assert set(TRANSFER_RATIOS) == {
        "amex_membership_rewards",
        "chase_ultimate_rewards",
        "capital_one_miles",
    }


def test_fetch_award_flights_calls_seats_aero_with_search_parameters() -> None:
    """Request award data using the Seats.aero API contract."""
    response = Mock()
    response.json.return_value = {"data": [{"airline": "AA", "miles": 25_000}]}

    with patch("scanner.requests.get", return_value=response) as mock_get:
        flights = fetch_award_flights(
            departure="JFK",
            arrival="LHR",
            travel_date="2026-10-15",
            api_key="seats-test-key",
        )

    mock_get.assert_called_once_with(
        "https://api.seats.aero/v1/search",
        params={
            "origin_airport": "JFK",
            "destination_airport": "LHR",
            "start_date": "2026-10-15",
            "end_date": "2026-10-15",
            "take": 100,
        },
        headers={"X-API-Key": "seats-test-key"},
        timeout=10,
    )
    response.raise_for_status.assert_called_once_with()
    assert flights == [{"airline": "AA", "miles": 25_000}]


def test_fetch_award_flights_accepts_list_response() -> None:
    """Support a direct list response from a compatible award provider."""
    response = Mock()
    response.json.return_value = [{"airline": "BA", "miles": 30_000}]

    with patch("scanner.requests.get", return_value=response):
        flights = fetch_award_flights(
            departure="JFK",
            arrival="LHR",
            travel_date="2026-10-15",
            api_key="seats-test-key",
        )

    assert flights == [{"airline": "BA", "miles": 30_000}]


def test_fetch_cash_price_uses_configured_flight_search_endpoint() -> None:
    """Fetch and convert the comparable cash fare to Decimal."""
    response = Mock()
    response.json.return_value = {"cash_price": "512.45"}

    with patch("scanner.requests.get", return_value=response) as mock_get:
        cash_price = fetch_cash_price(
            departure="JFK",
            arrival="LHR",
            travel_date="2026-10-15",
            api_key="cash-test-key",
            endpoint="https://cash.example.test/v1/search",
        )

    mock_get.assert_called_once_with(
        "https://cash.example.test/v1/search",
        params={
            "origin": "JFK",
            "destination": "LHR",
            "date": "2026-10-15",
        },
        headers={"Authorization": "Bearer cash-test-key"},
        timeout=10,
    )
    response.raise_for_status.assert_called_once_with()
    assert cash_price == Decimal("512.45")


def test_fetch_cash_price_requires_a_cash_api_endpoint() -> None:
    """Fail clearly when no cash-fare provider endpoint is configured."""
    with pytest.raises(ValueError, match="endpoint"):
        fetch_cash_price(
            departure="JFK",
            arrival="LHR",
            travel_date="2026-10-15",
            api_key="cash-test-key",
            endpoint="",
        )
