from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.sweet_spot_aggregation import (
    extract_sweet_spot_reference_features,
    precompute_sweet_spot_aggregation,
)


def _feature_history() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["IONQ", "QS", "AMPX", "IONQ"],
            "as_of_date": ["2024-10-09", "2025-06-27", "2025-07-09", "2024-10-10"],
            "price_short": [1.0, 1.1, 1.2, 9.9],
            "price_mid": [0.2, 0.3, 0.4, 9.9],
            "price_l_long": [2.0, 2.1, 2.2, 9.9],
            "vol_short": [1.5, 1.6, 1.7, 9.9],
            "vol_mid": [0.5, 0.6, 0.7, 9.9],
            "vol_l_long": [2.5, 2.6, 2.7, 9.9],
        }
    )


def test_extract_sweet_spot_reference_features_selects_requested_pairs() -> None:
    out = extract_sweet_spot_reference_features(
        _feature_history(),
        sweet_spot_pairs=[
            ("ionq", "2024-10-09"),
            ("AMPX", "2025-07-09"),
        ],
    )

    assert list(out["symbol"]) == ["AMPX", "IONQ"]
    assert list(out["as_of_date"]) == ["2025-07-09", "2024-10-09"]
    assert list(out["price_short"]) == [1.2, 1.0]


def test_extract_sweet_spot_reference_features_fails_when_pair_missing() -> None:
    try:
        extract_sweet_spot_reference_features(
            _feature_history(),
            sweet_spot_pairs=[("IONQ", "2024-10-09"), ("MISSING", "2024-10-09")],
        )
    except ValueError as exc:
        assert "missing sweet spot rows" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing sweet spot pair")


def test_precompute_sweet_spot_aggregation_builds_reference_ranges() -> None:
    artifacts = precompute_sweet_spot_aggregation(
        _feature_history(),
        sweet_spot_pairs=[
            ("IONQ", "2024-10-09"),
            ("QS", "2025-06-27"),
            ("AMPX", "2025-07-09"),
        ],
    )

    assert list(artifacts.reference_frame["symbol"]) == ["AMPX", "IONQ", "QS"]
    assert artifacts.native_ranges["price_short"] == {"lower": 1.0, "upper": 1.2}
    assert artifacts.native_ranges["vol_l_long"] == {"lower": 2.5, "upper": 2.7}
