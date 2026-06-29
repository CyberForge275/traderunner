from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from strategies.ndx_momentum_rotation.universe import (
    UniverseProviderNotImplementedError,
    load_universe_snapshot,
    resolve_valid_symbols_for_date,
)


def _write_daily_universe(path: Path) -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "AAPL", "NVDA"],
            "Date": [
                "2026-03-24",
                "2026-03-24",
                "2026-03-25",
                "2026-03-25",
            ],
            "Open": [1.0, 2.0, 1.1, 3.0],
            "High": [1.0, 2.0, 1.1, 3.0],
            "Low": [1.0, 2.0, 1.1, 3.0],
            "Close": [1.0, 2.0, 1.1, 3.0],
            "Volume": [10.0, 20.0, 11.0, 30.0],
        }
    )
    frame.to_parquet(path, index=False)


def test_resolve_valid_symbols_for_date_intersects_members_with_available_bars(
    tmp_path: Path,
) -> None:
    daily_path = tmp_path / "stocks_data.parquet"
    _write_daily_universe(daily_path)

    out = resolve_valid_symbols_for_date(
        as_of_date="2026-03-25",
        members=["AAPL", "MSFT", "NVDA"],
        daily_bars_path=daily_path,
    )

    assert out == ["AAPL", "NVDA"]



def test_load_universe_snapshot_current_members_via_marketdata_stream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daily_path = tmp_path / "stocks_data.parquet"
    _write_daily_universe(daily_path)

    captured: dict[str, object] = {}

    class _ClientStub:
        def __init__(self, *args, **kwargs) -> None:
            captured["init_kwargs"] = kwargs

        def fetch_universe_members(self, req):
            captured["request"] = req.to_json()
            return {
                "status": "ok",
                "data": [
                    {"symbol": "MSFT", "valid_from": "2026-03-24", "valid_to": "2026-03-24", "source": "current_members"},
                    {"symbol": "AAPL", "valid_from": "2026-03-24", "valid_to": "2026-03-24", "source": "current_members"},
                    {"symbol": "FAKE", "valid_from": "2026-03-24", "valid_to": "2026-03-24", "source": "current_members"},
                ],
            }

    monkeypatch.setattr("strategies.ndx_momentum_rotation.universe.MarketdataStreamClient", _ClientStub)

    snap = load_universe_snapshot(
        as_of_date="2026-03-24",
        survivorship_mode="current_members",
        daily_bars_path=daily_path,
    )

    assert captured["request"] == {
        "universe": "NDX",
        "as_of_date": "2026-03-24",
        "survivorship_mode": "current_members",
    }
    assert snap.members == ["AAPL", "MSFT"]
    assert snap.source == "marketdata_stream:NDX"


def test_load_universe_snapshot_pit_members_fails_fast() -> None:
    with pytest.raises(UniverseProviderNotImplementedError):
        load_universe_snapshot(
            as_of_date="2026-03-24",
            survivorship_mode="pit_members",
        )


def test_load_universe_snapshot_requires_daily_bars_path() -> None:
    with pytest.raises(ValueError, match="daily_bars_path"):
        load_universe_snapshot(
            as_of_date="2026-03-24",
            survivorship_mode="current_members",
        )
