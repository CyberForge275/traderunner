import os
from pathlib import Path

import pandas as pd
import pytest


def _write_dummy_parquet(path: Path) -> None:
    df = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.5],
            "Volume": [1000],
        },
        index=pd.date_range(start="2025-01-01", periods=1, freq="1min", tz="UTC"),
    )
    df.to_parquet(path)


def test_offline_mode_blocks_network_calls(tmp_path, monkeypatch):
    from src.axiom_bt.data import eodhd_fetch

    monkeypatch.setenv("EODHD_OFFLINE", "1")
    cached = tmp_path / "TEST.parquet"
    _write_dummy_parquet(cached)

    def _boom(*_args, **_kwargs):
        raise AssertionError("Network call should not happen in offline mode")

    monkeypatch.setattr(eodhd_fetch, "_request", _boom)
    path = eodhd_fetch.fetch_intraday_1m_to_parquet(
        symbol="TEST",
        exchange="US",
        out_dir=tmp_path,
        filter_rth=False,
    )
    assert path == cached


def test_network_blocked_raises_actionable_error(monkeypatch):
    from src.axiom_bt.data.eodhd_fetch import _request, NetworkUnavailableError

    class _DummySocket:
        def __init__(self, *args, **kwargs):
            raise OSError("Operation not permitted")

    monkeypatch.setattr("src.axiom_bt.data.eodhd_fetch.socket.socket", _DummySocket)
    with pytest.raises(NetworkUnavailableError) as exc:
        _request("https://eodhd.com/api/intraday/TEST.US", {"api_token": "x", "interval": "1m"})
    assert "Network disabled in this runner" in str(exc.value)
