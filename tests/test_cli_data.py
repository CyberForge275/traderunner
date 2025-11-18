from pathlib import Path

import pandas as pd

from axiom_bt.cli_data import cmd_ensure_intraday, cmd_fetch_daily
from axiom_bt.fs import DATA_D1, DATA_M1, DATA_M15, DATA_M5


class Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_cmd_ensure_intraday_sample(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    args = Args(
        symbols="TEST",
        universe_file=None,
        exchange="US",
        tz="UTC",
        start=None,
        end=None,
        force=True,
        generate_m15=True,
        use_sample=True,
    )

    assert cmd_ensure_intraday(args) == 0

    m1_path = DATA_M1 / "TEST.parquet"
    m5_path = DATA_M5 / "TEST.parquet"
    m15_path = DATA_M15 / "TEST.parquet"

    for path in (m1_path, m5_path, m15_path):
        assert path.exists()
        df = pd.read_parquet(path)
        assert not df.empty


def test_cmd_fetch_daily_sample(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    args = Args(
        symbols="TEST",
        universe_file=None,
        exchange="US",
        tz="UTC",
        start="2024-01-01",
        end="2024-01-10",
        use_sample=True,
    )

    assert cmd_fetch_daily(args) == 0

    d1_path = DATA_D1 / "TEST.parquet"
    assert d1_path.exists()
    df = pd.read_parquet(d1_path)
    assert not df.empty
