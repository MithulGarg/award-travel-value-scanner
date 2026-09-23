# Award Travel Value Scanner

## Goal

Build a Python CLI that evaluates mock award-flight options for a route and travel date, calculates cents per point (CPP), and identifies redemptions above 2.0 CPP as `High Value`.

The first implementation will use deterministic mock data behind interfaces that can later be replaced with live airline, award-search, and cash-fare providers.

## Proposed Architecture

The application will use a small layered design:

1. **CLI layer** parses and validates user input, invokes the application service, and formats results for terminal output.
2. **Application layer** coordinates the search request, mock award-flight lookup, CPP calculation, partner enrichment, and high-value classification.
3. **Domain layer** defines typed models and pure valuation rules.
4. **Infrastructure layer** supplies mock flight data and the transferable-points partner configuration.
5. **Test layer** verifies pure calculations, validation, configuration behavior, orchestration, and CLI output without network calls.

The domain and application layers should not depend on a specific CLI framework or external API client.

## Proposed File Structure

```text
award-travel-helper/
├── PLAN.md
├── pyproject.toml                 # Project metadata, CLI entry point, pytest, ruff
├── README.md                      # Installation and usage documentation
├── src/
│   └── award_travel_scanner/
│       ├── __init__.py
│       ├── __main__.py            # Enables: python -m award_travel_scanner
│       ├── cli.py                 # Argument parser and terminal presentation
│       ├── models.py              # Typed domain models
│       ├── valuation.py           # Pure CPP and value-tier calculations
│       ├── partners.py            # Transfer-partner configuration and lookup
│       ├── services.py            # Search and valuation orchestration
│       └── mock_data.py            # Deterministic mock award-flight provider
└── tests/
    ├── test_valuation.py
    ├── test_partners.py
    ├── test_services.py
    └── test_cli.py
```

The package can begin with mock data only. A future provider module can implement the same lookup protocol without changing the valuation rules or CLI contract.

## Domain Models

Use typed dataclasses or equivalent standard-library models:

- `SearchRequest`
  - `departure: str`
  - `arrival: str`
  - `date: date`
- `AwardFlight`
  - `program: str`
  - `transfer_partner: str | None`
  - `points_required: int`
  - `taxes_and_fees: Decimal`
  - `cash_price: Decimal`
  - optional itinerary details such as flight number, cabin, and departure time
- `ValuationResult`
  - the source `AwardFlight`
  - `cpp: Decimal`
  - `value_label: str` (`High Value` or another defined label)
- `PartnerProgram`
  - `currency`: one of `amex_membership_rewards`, `chase_ultimate_rewards`, or `capital_one_miles`
  - transfer partner name
  - transfer ratio, initially represented as points received per one source point
  - optional notes or supported program metadata

Airport codes should be normalized to uppercase and validated as three-letter IATA-style codes at the CLI/service boundary. Dates should be parsed as ISO-8601 `YYYY-MM-DD` values.

## Required Functions

### `cli.py`

- `build_parser() -> ArgumentParser`
  - Defines required `--departure`, `--arrival`, and `--date` options.
- `main(argv: Sequence[str] | None = None) -> int`
  - Parses arguments, constructs a `SearchRequest`, invokes the application service, and renders results.
- `format_results(results: Sequence[ValuationResult]) -> str`
  - Produces stable, readable terminal output including route, date, program, points, cash cost, CPP, and value label.

### `models.py`

- Typed constructors or factory validation for `SearchRequest`, `AwardFlight`, and `ValuationResult`.
- Keep model validation focused on invariants such as positive points and non-negative monetary values.

### `valuation.py`

- `calculate_cpp(cash_price: Decimal, taxes_and_fees: Decimal, points_required: int) -> Decimal`
  - Formula: `((cash_price - taxes_and_fees) / points_required) * 100`.
  - Return a consistently rounded decimal value, such as two decimal places.
  - Reject zero or negative points and negative eligible cash value.
- `classify_value(cpp: Decimal, threshold: Decimal = Decimal("2.0")) -> str`
  - Returns `High Value` when CPP is strictly greater than 2.0; exactly 2.0 is not high value.
- `evaluate_award(flight: AwardFlight) -> ValuationResult`
  - Calculates CPP and applies the value classification.

### `partners.py`

- `TRANSFER_PARTNERS: Mapping[str, tuple[PartnerProgram, ...]]`
  - Configuration map for:
    - American Express Membership Rewards
    - Chase Ultimate Rewards
    - Capital One Miles
- `get_transfer_partners(currency: str) -> tuple[PartnerProgram, ...]`
  - Returns configured partners or a clear error for an unsupported currency.
- `get_supported_currencies() -> tuple[str, ...]`
  - Exposes the supported transferable-points currencies for validation and help text.

Initial configuration should be explicit and easy to extend. Since this is a mock-data phase, partner names and ratios should be treated as configuration fixtures rather than claims about current transfer promotions.

### `mock_data.py`

- `get_mock_award_flights(request: SearchRequest) -> list[AwardFlight]`
  - Returns deterministic options for the requested route/date.
  - Includes at least one result below or equal to 2.0 CPP and one result above 2.0 CPP so classification is exercised.
  - Does not perform network or file I/O.

### `services.py`

- `scan_award_value(request: SearchRequest) -> list[ValuationResult]`
  - Gets mock flights, evaluates each redemption, and returns results sorted by descending CPP.
- A provider protocol such as `AwardFlightProvider` may be introduced if it keeps dependency injection straightforward for tests and future live integrations.

## CPP and High-Value Rules

For each redemption:

```text
eligible_cash_value = cash fare - taxes and fees
CPP = (eligible_cash_value / points required) * 100
```

Example:

```text
cash fare:       $500.00
fees:             $50.00
points required: 25,000
CPP:             (($500.00 - $50.00) / 25,000) * 100 = 1.80
```

Classification uses a strict comparison:

- `cpp > 2.0`: `High Value`
- `cpp <= 2.0`: `Standard Value`

The implementation should use `Decimal`, not binary floating point, for currency and CPP calculations.

## CLI Contract

Example invocation:

```bash
python -m award_travel_scanner --departure JFK --arrival LHR --date 2026-10-15
```

Expected behavior:

- Normalize airport codes to uppercase.
- Reject malformed airport codes and invalid dates with a concise usage error and non-zero exit code.
- Print all matching mock redemptions with points, taxes/fees, CPP, and value label.
- Make the `High Value` label visible for every redemption above 2.0 CPP.
- Return zero when the request is valid, including when no mock results are found; return non-zero for invalid input or operational errors.

## Test Suite Plan

All tests should be deterministic and must not call live APIs, databases, or external files.

### `tests/test_valuation.py`

- Calculates CPP using cash fare, taxes, and points.
- Rounds CPP consistently.
- Rejects zero and negative points.
- Rejects a cash fare below taxes and fees.
- Classifies CPP strictly above 2.0 as `High Value`.
- Confirms exactly 2.0 CPP is not `High Value`.
- Evaluates a complete `AwardFlight` into a `ValuationResult`.

### `tests/test_partners.py`

- Confirms all three required currencies are present.
- Confirms each currency returns a non-empty partner configuration.
- Confirms partner ratios and names are represented in the expected typed shape.
- Rejects an unsupported currency with a clear exception.

### `tests/test_services.py`

- Scans a valid request and returns evaluated results.
- Confirms results are sorted by descending CPP.
- Confirms mock data includes both standard and high-value classifications.
- Uses an injected fake provider to test orchestration independently from mock fixture details.
- Confirms an empty provider response returns an empty result list.

### `tests/test_cli.py`

- Parses a valid route and ISO date.
- Normalizes lowercase airport codes.
- Rejects malformed airport codes and invalid dates.
- Verifies successful output includes CPP and `High Value` when applicable.
- Verifies invalid input returns a non-zero exit code and useful error text.

## Validation and Tooling

- Use `pytest` for the test suite.
- Use `ruff check --fix .` and `ruff format .` after implementation changes.
- Keep public functions fully type hinted and add Google-style docstrings according to the repository's Python standards.
- Add only standard-library dependencies initially; a CLI framework can be introduced later if argument handling becomes more complex.

## Implementation Sequence After Approval

1. Add package metadata and the source/test directories.
2. Write valuation and partner tests first.
3. Implement typed models, valuation rules, partner configuration, and mock provider.
4. Add service orchestration and CLI formatting.
5. Run focused tests, then the full pytest suite and Ruff checks.
6. Update `README.md` with installation, invocation, sample output, and the mock-data limitation.

No Python source files will be created until this plan is approved.
