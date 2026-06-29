from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.feature_contract import (
    FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
    normalize_feature_frame,
)


def test_normalize_feature_frame_uppercases_symbols_and_coerces_types() -> None:
    raw = pd.DataFrame(
        {
            "symbol": ["aapl", "msft"],
            "as_of_date": ["2026-04-21T00:00:00Z", "2026-04-21"],
            "price_short": ["1.1", 1.2],
            "price_mid": [0.2, "0.3"],
            "price_l_long": [2.1, "2.2"],
            "vol_short": [1.5, "1.6"],
            "vol_mid": [0.5, "0.6"],
            "vol_l_long": [2.5, "2.6"],
        }
    )

    out = normalize_feature_frame(raw, frame_name="candidate_features")

    assert list(out.columns) == [*IDENTIFIER_COLUMNS, *FEATURE_COLUMNS]
    assert list(out["symbol"]) == ["AAPL", "MSFT"]
    assert list(out["as_of_date"]) == ["2026-04-21", "2026-04-21"]
    assert out["price_short"].tolist() == [1.1, 1.2]
    assert out["vol_l_long"].tolist() == [2.5, 2.6]


def test_normalize_feature_frame_rejects_missing_columns() -> None:
    bad = pd.DataFrame({"symbol": ["AAPL"], "as_of_date": ["2026-04-21"]})

    try:
        normalize_feature_frame(bad, frame_name="reference_features")
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing columns")


def test_normalize_feature_frame_rejects_duplicate_symbol_date_pairs() -> None:
    dup = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL"],
            "as_of_date": ["2026-04-21", "2026-04-21"],
            "price_short": [1.1, 1.2],
            "price_mid": [0.2, 0.3],
            "price_l_long": [2.1, 2.2],
            "vol_short": [1.5, 1.6],
            "vol_mid": [0.5, 0.6],
            "vol_l_long": [2.5, 2.6],
        }
    )

    try:
        normalize_feature_frame(dup, frame_name="candidate_features")
    except ValueError as exc:
        assert "duplicate symbol/as_of_date rows" in str(exc)
    else:
        raise AssertionError("expected ValueError for duplicate keys")
