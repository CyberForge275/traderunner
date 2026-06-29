from __future__ import annotations

import pandas as pd
import pytest

from strategies.ndx_momentum_rotation.ranking import select_top_n
from strategies.ndx_momentum_rotation.scoring import build_roc_scores


def _make_symbol_frame(symbol: str, closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=len(closes), freq="D", tz="UTC"),
            "symbol": symbol,
            "close": closes,
        }
    )


def test_build_roc_scores_computes_roc60_exactly() -> None:
    bars = pd.concat(
        [
            _make_symbol_frame("AAPL", [100.0] + [100.0] * 59 + [120.0]),
            _make_symbol_frame("MSFT", [100.0] + [100.0] * 59 + [110.0]),
        ],
        ignore_index=True,
    )

    out = build_roc_scores(bars, as_of_date="2026-03-02", lookback_bars=60)

    assert out["symbol"].tolist() == ["AAPL", "MSFT"]
    assert out.iloc[0]["roc60"] == pytest.approx(0.2)
    assert out.iloc[1]["roc60"] == pytest.approx(0.1)


def test_build_roc_scores_uses_market_date_boundary_not_utc_midnight() -> None:
    timestamps = pd.date_range("2026-01-25", periods=61, freq="D", tz="America/New_York")
    bars = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": "AAPL",
            "close": [100.0] + [100.0] * 59 + [120.0],
        }
    )

    out = build_roc_scores(bars, as_of_date="2026-03-26", lookback_bars=60)

    assert out.iloc[0]["close"] == pytest.approx(120.0)
    assert out.iloc[0]["roc60"] == pytest.approx(0.2)


def test_build_roc_scores_excludes_symbols_with_insufficient_history() -> None:
    bars = pd.concat(
        [
            _make_symbol_frame("AAPL", [100.0] + [100.0] * 59 + [120.0]),
            _make_symbol_frame("NVDA", [50.0] * 60),
        ],
        ignore_index=True,
    )

    out = build_roc_scores(bars, as_of_date="2026-03-02", lookback_bars=60)

    assert out["symbol"].tolist() == ["AAPL"]


def test_select_top_n_uses_deterministic_tie_break() -> None:
    scores = pd.DataFrame(
        {
            "symbol": ["MSFT", "AAPL", "NVDA"],
            "roc60": [0.1, 0.1, 0.2],
        }
    )

    out = select_top_n(scores, n=2, score_column="roc60")

    assert out["symbol"].tolist() == ["NVDA", "AAPL"]
    assert out["rank"].tolist() == [1, 2]
