from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from axiom_bt.pipeline.data_fetcher import MissingHistoricalDataError, ensure_and_snapshot_bars


def _mk_derived(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base = pd.Timestamp("2026-01-13 14:30:00", tz="UTC")
    rows = []
    for i in range(24):
        ts = base + pd.Timedelta(minutes=5 * i)
        rows.append(
            {
                "ts": int(ts.timestamp()),
                "open": 10 + i * 0.1,
                "high": 10.2 + i * 0.1,
                "low": 9.8 + i * 0.1,
                "close": 10.1 + i * 0.1,
                "volume": 100 + i,
            }
        )
    pd.DataFrame(rows).to_parquet(path)


def test_wrapper_raises_when_derived_missing_and_never_uses_legacy(monkeypatch, tmp_path: Path):
    from core.settings.runtime_config import reset_runtime_config_for_tests

    reset_runtime_config_for_tests()
    monkeypatch.delenv("TRADING_CONFIG", raising=False)
    monkeypatch.setenv("MARKETDATA_DATA_ROOT", str(tmp_path))

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("legacy HTTP/fallback path must not be called")

    monkeypatch.setattr("axiom_bt.intraday.fetch_intraday_1m_to_parquet", _forbidden)
    monkeypatch.setattr("axiom_bt.intraday.check_local_m1_coverage", _forbidden)

    with pytest.raises(MissingHistoricalDataError):
        ensure_and_snapshot_bars(
            run_dir=tmp_path / "run",
            symbol="HOOD",
            timeframe="M5",
            requested_end="2026-02-11",
            lookback_days=30,
            market_tz="America/New_York",
        )


def test_wrapper_loads_derived_and_writes_snapshot(monkeypatch, tmp_path: Path):
    from core.settings.runtime_config import reset_runtime_config_for_tests

    reset_runtime_config_for_tests()
    monkeypatch.delenv("TRADING_CONFIG", raising=False)
    monkeypatch.setenv("MARKETDATA_DATA_ROOT", str(tmp_path))
    derived = tmp_path / "derived" / "tf_m5" / "HOOD.parquet"
    _mk_derived(derived)

    out = ensure_and_snapshot_bars(
        run_dir=tmp_path / "run",
        symbol="HOOD",
        timeframe="M5",
        requested_end="2026-01-14",
        lookback_days=1,
        market_tz="America/New_York",
    )

    exec_path = Path(out["exec_path"])
    assert exec_path.exists()
    df = pd.read_parquet(exec_path)
    assert not df.empty
