from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.reference_set import (
    FEATURE_COLUMNS,
    build_reference_set,
)


def test_build_reference_set_computes_native_and_zscore_ranges() -> None:
    reference_features = pd.DataFrame(
        {
            "symbol": ["IONQ", "QS", "AMPX"],
            "price_short": [0.9, 1.1, 1.3],
            "price_mid": [0.2, 0.3, 0.4],
            "price_l_long": [1.8, 2.0, 2.2],
            "vol_short": [1.5, 1.7, 1.9],
            "vol_mid": [0.4, 0.6, 0.8],
            "vol_l_long": [2.5, 2.7, 2.9],
        }
    )

    out = build_reference_set(reference_features)

    assert list(out.reference_frame["symbol"]) == ["IONQ", "QS", "AMPX"]
    assert set(out.native_ranges) == set(FEATURE_COLUMNS)
    assert out.native_ranges["price_short"] == {"lower": 0.9, "upper": 1.3}
    assert out.native_ranges["vol_l_long"] == {"lower": 2.5, "upper": 2.9}

    price_short_mean = reference_features["price_short"].mean()
    price_short_std = reference_features["price_short"].std()
    assert out.zscore_ranges["price_short"]["lower"] == price_short_mean - 3.5 * price_short_std
    assert out.zscore_ranges["price_short"]["upper"] == price_short_mean + 3.5 * price_short_std


def test_build_reference_set_requires_all_feature_columns() -> None:
    bad = pd.DataFrame({"symbol": ["IONQ"], "price_short": [1.0]})

    try:
        build_reference_set(bad)
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing feature columns")
