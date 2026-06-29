from __future__ import annotations

from strategies.perlentaucher_daily_scan.marketdata_handoff import (
    REQUIRED_FEATURE_COLUMNS,
    REQUIRED_OHLCV_COLUMNS,
    build_marketdata_handoff_payload,
)


def test_build_marketdata_handoff_payload_exposes_resolved_request_and_contract() -> None:
    payload = build_marketdata_handoff_payload(
        date_from="2026-04-21",
        date_to="2026-04-21",
        params={"min_history_days": 107},
    )

    assert payload["request"]["market"] == "US"
    assert payload["request"]["asset_class"] == "stock"
    assert payload["request"]["date_from"] == "2025-10-27"
    assert payload["request"]["date_to"] == "2026-04-21"
    assert payload["request"]["lookback_days"] == 107
    assert payload["request"]["fetch_calendar_days"] == 177
    assert payload["request"]["symbol_mode"] == "ALL"
    assert payload["input_contract"]["required_ohlcv_columns"] == list(REQUIRED_OHLCV_COLUMNS)
    assert payload["output_contract"]["required_feature_columns"] == list(REQUIRED_FEATURE_COLUMNS)


def test_build_marketdata_handoff_payload_preserves_longer_history() -> None:
    payload = build_marketdata_handoff_payload(
        date_from="2025-10-01",
        date_to="2026-04-21",
        params={"min_history_days": 140},
    )

    assert payload["request"]["date_from"] == "2025-09-03"
    assert payload["request"]["lookback_days"] == 140
    assert payload["request"]["fetch_calendar_days"] == 231
