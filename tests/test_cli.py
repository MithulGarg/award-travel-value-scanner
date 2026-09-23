"""Tests for the Award Travel Value Scanner command-line interface."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from cli import main

MOCK_AWARD_FLIGHTS = [
    {
        "program": "Aeroplan",
        "points_required": 20_000,
        "taxes_and_fees": Decimal("50.00"),
        "transfer_currency": "amex_membership_rewards",
    }
]
MOCK_TRANSFER_PARTNERS = {
    "amex_membership_rewards": ("Air Canada Aeroplan", "Avianca LifeMiles"),
}


def test_scan_accepts_required_route_and_date_options(capsys) -> None:
    """Accept origin, destination, and ISO date options."""
    with (
        patch("cli.scanner.fetch_award_flights", return_value=MOCK_AWARD_FLIGHTS),
        patch("cli.scanner.fetch_cash_price", return_value=Decimal("500.00")),
        patch.dict("cli.scanner.TRANSFER_PARTNERS", MOCK_TRANSFER_PARTNERS),
    ):
        exit_code = main(
            [
                "scan",
                "--origin",
                "ORD",
                "--dest",
                "LHR",
                "--date",
                "2026-10-15",
            ]
        )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ORD -> LHR" in output
    assert "2026-10-15" in output


def test_scan_uses_business_cabin_and_two_cpp_defaults(capsys) -> None:
    """Use business cabin and 2.0 CPP as defaults when flags are omitted."""
    with (
        patch(
            "cli.scanner.fetch_award_flights", return_value=MOCK_AWARD_FLIGHTS
        ) as mock_fetch_awards,
        patch("cli.scanner.fetch_cash_price", return_value=Decimal("500.00")),
        patch.dict("cli.scanner.TRANSFER_PARTNERS", MOCK_TRANSFER_PARTNERS),
    ):
        exit_code = main(
            [
                "scan",
                "--origin",
                "ORD",
                "--dest",
                "LHR",
                "--date",
                "2026-10-15",
            ]
        )

    mock_fetch_awards.assert_called_once_with(
        departure="ORD",
        arrival="LHR",
        travel_date="2026-10-15",
        api_key="",
        cabin="business",
    )
    assert exit_code == 0
    assert "High Value" in capsys.readouterr().out


def test_scan_passes_custom_cabin_and_cpp_cutoff(capsys) -> None:
    """Pass custom cabin and CPP cutoff values to the scan workflow."""
    with (
        patch(
            "cli.scanner.fetch_award_flights", return_value=MOCK_AWARD_FLIGHTS
        ) as mock_fetch_awards,
        patch("cli.scanner.fetch_cash_price", return_value=Decimal("500.00")),
        patch.dict("cli.scanner.TRANSFER_PARTNERS", MOCK_TRANSFER_PARTNERS),
    ):
        exit_code = main(
            [
                "scan",
                "--origin",
                "ORD",
                "--dest",
                "LHR",
                "--date",
                "2026-10-15",
                "--cabin",
                "economy",
                "--min-cpp",
                "2.5",
            ]
        )

    mock_fetch_awards.assert_called_once_with(
        departure="ORD",
        arrival="LHR",
        travel_date="2026-10-15",
        api_key="",
        cabin="economy",
    )
    assert exit_code == 0
    assert "Standard Value" in capsys.readouterr().out


def test_scan_prints_cpp_and_transfer_partners(capsys) -> None:
    """Print the calculated CPP and configured transfer partners."""
    with (
        patch("cli.scanner.fetch_award_flights", return_value=MOCK_AWARD_FLIGHTS),
        patch("cli.scanner.fetch_cash_price", return_value=Decimal("500.00")),
        patch.dict("cli.scanner.TRANSFER_PARTNERS", MOCK_TRANSFER_PARTNERS),
    ):
        main(
            [
                "scan",
                "--origin",
                "ORD",
                "--dest",
                "LHR",
                "--date",
                "2026-10-15",
            ]
        )

    output = capsys.readouterr().out

    assert "CPP: 2.25" in output
    assert "Transfer partners: Air Canada Aeroplan, Avianca LifeMiles" in output


@pytest.mark.parametrize(
    "arguments",
    [
        ["scan", "--dest", "LHR", "--date", "2026-10-15"],
        ["scan", "--origin", "ORD", "--date", "2026-10-15"],
        ["scan", "--origin", "ORD", "--dest", "LHR"],
    ],
)
def test_scan_missing_mandatory_option_exits_non_zero(arguments: list[str]) -> None:
    """Reject a scan command missing any mandatory route option."""
    with pytest.raises(SystemExit) as error:
        main(arguments)

    assert error.value.code != 0


@pytest.mark.parametrize(
    ("option", "value"),
    [("--origin", "CHICAGO"), ("--dest", "LONDON")],
)
def test_scan_rejects_invalid_airport_codes(option: str, value: str) -> None:
    """Reject airport values that are not three-letter IATA-style codes."""
    arguments = [
        "scan",
        "--origin",
        "ORD",
        "--dest",
        "LHR",
        "--date",
        "2026-10-15",
    ]
    arguments[arguments.index(option)] = value

    with pytest.raises(SystemExit) as error:
        main(arguments)

    assert error.value.code != 0
