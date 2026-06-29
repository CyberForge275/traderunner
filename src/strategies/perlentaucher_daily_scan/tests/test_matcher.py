from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.matcher import match_candidates
from strategies.perlentaucher_daily_scan.reference_set import build_reference_set


def _reference_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["IONQ", "QS", "AMPX"],
            "price_short": [1.00, 1.10, 1.20],
            "price_mid": [0.20, 0.22, 0.24],
            "price_l_long": [2.00, 2.10, 2.20],
            "vol_short": [1.50, 1.60, 1.70],
            "vol_mid": [0.50, 0.55, 0.60],
            "vol_l_long": [2.50, 2.60, 2.70],
        }
    )


def test_match_candidates_ranks_best_native_matches_deterministically() -> None:
    candidates = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "TSLA"],
            "price_short": [1.11, 3.5, 1.05],
            "price_mid": [0.21, 0.9, 0.23],
            "price_l_long": [2.08, 5.0, 2.02],
            "vol_short": [1.59, 8.0, 1.54],
            "vol_mid": [0.54, 2.0, 0.52],
            "vol_l_long": [2.61, 8.0, 2.53],
        }
    )

    out = match_candidates(
        candidates,
        build_reference_set(_reference_features()),
        match_mode="price_vol",
        max_candidates=2,
    )

    assert list(out["symbol"]) == ["AAPL", "TSLA", "MSFT"]
    assert list(out["candidate_rank"])[:2] == [1.0, 2.0]
    assert out.loc[out["symbol"] == "AAPL", "eligibility_reason"].iloc[0] == "MATCHED"
    assert out.loc[out["symbol"] == "TSLA", "eligibility_reason"].iloc[0] == "MATCHED"
    assert out.loc[out["symbol"] == "MSFT", "eligibility_reason"].iloc[0] == "NO_MATCH"


def test_match_candidates_supports_zscore_mode() -> None:
    candidates = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "price_short": [1.15, 9.5],
            "price_mid": [0.23, 9.5],
            "price_l_long": [2.15, 9.5],
            "vol_short": [1.65, 9.5],
            "vol_mid": [0.57, 9.5],
            "vol_l_long": [2.65, 9.5],
        }
    )

    out = match_candidates(
        candidates,
        build_reference_set(_reference_features()),
        match_mode="zscore",
        max_candidates=10,
    )

    assert out.loc[out["symbol"] == "AAPL", "candidate_rank"].iloc[0] == 1.0
    assert out.loc[out["symbol"] == "AAPL", "eligibility_reason"].iloc[0] == "MATCHED"
    assert out.loc[out["symbol"] == "MSFT", "eligibility_reason"].iloc[0] == "NO_MATCH"
