# Award Travel Value Scanner

A Python CLI for comparing award-flight redemptions against comparable cash fares using cents per point (CPP).

Redemptions above the configured CPP threshold are marked as high value. The current implementation uses the Seats.aero API for award-flight data and a configurable flight-search API for cash prices.

## Requirements

- Python 3.10 or newer
- A Seats.aero API key
- Access to a cash-price flight-search API that returns a `cash_price` field

## Installation

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

The editable install registers the `award-scan` command and makes future source
changes available immediately without reinstalling the package.

## Configuration

Set these environment variables before running a live scan:

```bash
export SEATS_AERO_API_KEY="your-seats-aero-key"
export CASH_PRICE_API_KEY="your-cash-price-api-key"
export CASH_PRICE_API_URL="https://your-flight-search-provider.example/v1/search"
```

The cash-price endpoint must accept `origin`, `destination`, and `date` query parameters and return JSON in this shape:

```json
{"cash_price": "500.00"}
```

The CLI does not print or commit API keys.

## Usage

Run a scan with the default business cabin and a 2.0 CPP high-value cutoff:

```bash
award-scan --origin ORD --dest LHR --date 2026-10-15
```

Choose another cabin and CPP threshold:

```bash
award-scan \
  --origin ORD \
  --dest LHR \
  --date 2026-10-15 \
  --cabin economy \
  --min-cpp 2.5
```

Supported cabins are `economy`, `business`, and `first`. Airport codes must be three-letter IATA-style codes, and dates use `YYYY-MM-DD` format.

The output includes the route and date, comparable cash price, award miles required, calculated CPP, configured transfer partners, and value classification.

## CPP Calculation

CPP is calculated as:

```text
(cash price - taxes and fees) / award miles required * 100
```

The current transfer-ratio configuration includes American Express Membership Rewards, Chase Ultimate Rewards, and Capital One Miles at 1:1.

## Tests and Quality Checks

Run the full test suite:

```bash
python3 -m pytest -q
```

Run formatting and lint checks:

```bash
ruff format --check .
ruff check .
```

All external API calls are mocked in the tests, so the test suite does not require live credentials or network access.

## Continuous Integration

GitHub Actions is configured to run formatting checks, Ruff linting, and pytest on pushes and pull requests targeting `main`.
