"""Streamlit dashboard for the Award Travel Value Scanner."""

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import TypedDict

import requests
import streamlit as st

import scanner

CARD_ECOSYSTEMS: dict[str, tuple[str, str]] = {
    "amex_membership_rewards": (
        "Amex Platinum / Gold",
        "American Express Membership Rewards",
    ),
    "chase_ultimate_rewards": (
        "Chase Sapphire Preferred",
        "Chase Ultimate Rewards",
    ),
    "capital_one_miles": (
        "Capital One Venture X",
        "Capital One Miles",
    ),
}


class ScanResult(TypedDict):
    """Normalized award result prepared for display."""

    program: str
    points: int
    taxes_and_fees: Decimal
    cash_price: Decimal
    cpp: Decimal
    transfer_currency: str


@st.cache_data(ttl=3600, show_spinner=False)
def load_scan_results(
    origin: str,
    destination: str,
    travel_date: str,
    cabin: str,
    seats_api_key: str,
    cash_api_key: str,
    cash_price_endpoint: str,
) -> list[ScanResult]:
    """Fetch and value award options, cached for one hour."""
    awards = scanner.fetch_award_flights(
        departure=origin,
        arrival=destination,
        travel_date=travel_date,
        api_key=seats_api_key,
        cabin=cabin,
    )
    cash_price = scanner.fetch_cash_price(
        departure=origin,
        arrival=destination,
        travel_date=travel_date,
        api_key=cash_api_key,
        endpoint=cash_price_endpoint,
    )
    return [_normalize_award(award, cash_price) for award in awards]


def _normalize_award(award: dict[str, object], cash_price: Decimal) -> ScanResult:
    """Convert a provider record into values needed by the dashboard."""
    points_value = award.get("points_required", award.get("miles"))
    if points_value is None:
        raise ValueError("award response is missing points_required")
    points = int(points_value)
    taxes_and_fees = Decimal(str(award.get("taxes_and_fees", "0")))
    cpp = scanner.calculate_cpp(cash_price, taxes_and_fees, points)
    return {
        "program": str(award.get("program", award.get("airline", "Unknown program"))),
        "points": points,
        "taxes_and_fees": taxes_and_fees,
        "cash_price": cash_price,
        "cpp": cpp,
        "transfer_currency": str(award.get("transfer_currency", "")),
    }


def _render_transfer_tags(currency: str) -> None:
    """Render the premium-card ecosystems for a transfer currency."""
    card_name, currency_name = CARD_ECOSYSTEMS.get(
        currency, ("Transfer mapping unavailable", currency or "Unknown currency")
    )
    st.markdown(
        f'<span class="tag">{card_name}</span>'
        f'<span class="tag tag-muted">{currency_name}</span>',
        unsafe_allow_html=True,
    )


def _render_result_card(result: ScanResult, min_cpp: float) -> None:
    """Render one award option as a compact metric card."""
    cpp = result["cpp"]
    is_high_value = cpp > Decimal(str(min_cpp))
    value_label = "HIGH VALUE" if is_high_value else "STANDARD"
    value_class = "high-value" if is_high_value else "standard-value"
    st.markdown('<div class="result-card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="card-heading"><strong>{result["program"]}</strong>'
        f'<span class="value-pill {value_class}">{value_label}</span></div>',
        unsafe_allow_html=True,
    )
    metrics = st.columns(3)
    metrics[0].metric("CPP", f"{cpp:.2f}")
    metrics[1].metric("Award miles", f"{result['points']:,}")
    metrics[2].metric("Cash price", f"${result['cash_price']:.2f}")
    _render_transfer_tags(result["transfer_currency"])
    st.markdown("</div>", unsafe_allow_html=True)


def _render_styles() -> None:
    """Apply the dashboard's visual language."""
    st.markdown(
        """
        <style>
        .stApp { background: #f5f1e8; }
        [data-testid="stSidebar"] { background: #152d32; }
        [data-testid="stSidebar"] * { color: #f5f1e8; }
        .eyebrow { color: #be5b3f; font-size: 0.78rem; font-weight: 700;
            letter-spacing: 0.08em; text-transform: uppercase; }
        .hero-title { color: #152d32; font-family: Georgia, serif;
            font-size: 3rem; line-height: 1.05; margin: 0.2rem 0 0.5rem; }
        .hero-copy { color: #5b6662; font-size: 1.05rem; margin-bottom: 1.5rem; }
        .result-card { background: #fffdf8; border: 1px solid #ded7c9;
            border-radius: 8px; padding: 1.1rem 1.25rem; margin: 0.8rem 0;
            box-shadow: 0 8px 24px rgba(21, 45, 50, 0.07); }
        .card-heading { align-items: center; color: #152d32; display: flex;
            font-size: 1.08rem; justify-content: space-between; margin-bottom: 0.6rem; }
        .value-pill, .tag { border-radius: 999px; display: inline-block;
            font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em;
            margin-right: 0.35rem; padding: 0.28rem 0.55rem; }
        .high-value { background: #f3c969; color: #432d0c; }
        .standard-value { background: #e8e4da; color: #5b6662; }
        .tag { background: #dbe9e4; color: #1c5148; margin-top: 0.8rem; }
        .tag-muted { background: #eee9de; color: #6d665b; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Render the award travel scanner dashboard."""
    st.set_page_config(
        page_title="Award Travel Value Scanner",
        page_icon="✦",
        layout="wide",
    )
    _render_styles()

    with st.sidebar:
        st.markdown("## Scan controls")
        origin = st.text_input("Origin", value="ORD", max_chars=3).strip().upper()
        destination = (
            st.text_input("Destination", value="LHR", max_chars=3).strip().upper()
        )
        travel_date = st.date_input("Date", value=datetime.now(timezone.utc).date())
        cabin = st.selectbox("Cabin", options=scanner.SUPPORTED_CABINS, index=1)
        min_cpp = st.slider(
            "Minimum CPP cutoff",
            min_value=0.0,
            max_value=10.0,
            value=2.0,
            step=0.1,
            format="%.1f CPP",
        )
        run_scan = st.button(
            "Search award space", type="primary", use_container_width=True
        )
        st.caption("Results are cached for 1 hour to reduce API requests.")

    st.markdown('<div class="eyebrow">Award intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        '<h1 class="hero-title">Find the points worth keeping.</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="hero-copy">Compare award redemptions against cash fares and surface the routes that earn their place in your wallet.</p>',
        unsafe_allow_html=True,
    )

    if not run_scan:
        st.info("Choose your route and press Search award space to begin.")
        return
    if origin == destination:
        st.error("Origin and destination must be different airports.")
        return
    if len(origin) != 3 or len(destination) != 3:
        st.error("Origin and destination must be three-letter airport codes.")
        return

    try:
        with st.spinner("Searching award space and cash fares..."):
            results = load_scan_results(
                origin,
                destination,
                travel_date.isoformat(),
                cabin,
                os.getenv("SEATS_AERO_API_KEY", ""),
                os.getenv("CASH_PRICE_API_KEY", ""),
                os.getenv("CASH_PRICE_API_URL", ""),
            )
    except requests.ConnectionError as error:
        st.error("The award API could not be reached from this machine.")
        st.info(
            "DNS or network access to api.seats.aero failed. Check your internet "
            "connection, VPN, firewall, or DNS settings, then retry."
        )
        st.caption(str(error))
        return
    except requests.HTTPError as error:
        st.error("An external API rejected the request.")
        st.info(
            "Check SEATS_AERO_API_KEY, CASH_PRICE_API_KEY, and the cash-price "
            "endpoint configuration."
        )
        st.caption(str(error))
        return
    except (KeyError, ValueError, requests.RequestException) as error:
        st.error(f"Scan failed: {error}")
        st.info("Check the provider response and cash-price endpoint configuration.")
        return

    st.subheader(f"{origin} to {destination} · {travel_date.isoformat()}")
    st.caption(f"{len(results)} award option(s) found · {cabin.title()} cabin")
    for result in sorted(results, key=lambda item: item["cpp"], reverse=True):
        _render_result_card(result, min_cpp)


if __name__ == "__main__":
    main()
