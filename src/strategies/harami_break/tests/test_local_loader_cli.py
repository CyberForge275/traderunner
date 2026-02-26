import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from strategies.harami_break.local_loader_cli import (
    build_ensure_request,
    load_local_dataframe,
    normalize_date_window,
)


def test_build_ensure_request_requires_session_mode():
    core = {
        "timeframe_minutes": 5,
        "session_timezone": "America/New_York",
    }
    with pytest.raises(ValueError, match="session_mode"):
        build_ensure_request(
            symbol="HOOD",
            start_date=dt.date(2026, 1, 2),
            end_date=dt.date(2026, 1, 3),
            core=core,
            data_root=Path("/tmp"),
        )


def test_load_local_dataframe_reads_derived_parquet(tmp_path: Path):
    symbol = "HOOD"
    tf_minutes = 5
    parquet_path = tmp_path / "derived" / "tf_m5" / f"{symbol}.parquet"
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    src = pd.DataFrame(
        {
            "ts": [1735770600, 1735770900],
            "open": [10.0, 10.2],
            "high": [10.3, 10.4],
            "low": [9.9, 10.1],
            "close": [10.2, 10.3],
        }
    )
    src.to_parquet(parquet_path, index=False)

    out = load_local_dataframe(
        symbol=symbol,
        timeframe_minutes=tf_minutes,
        data_root=tmp_path,
    )

    assert len(out) == 2
    assert "timestamp" in out.columns
    assert out["timestamp"].dtype.kind == "M"


def test_normalize_date_window_clamps_end_to_yesterday():
    start, end = normalize_date_window(
        start_date=dt.date(2026, 2, 1),
        end_date=dt.date(2026, 2, 26),
        today=dt.date(2026, 2, 26),
    )
    assert start == dt.date(2026, 2, 1)
    assert end == dt.date(2026, 2, 25)
