import os
from pathlib import Path
from time import time

import pandas as pd

from axiom_bt.maintenance import (
    cleanup_artifacts,
    cleanup_backtests,
    cleanup_data,
    cleanup_orders,
)


def _touch(path: Path, offset_seconds: int) -> None:
    stamp = time() - offset_seconds
    os.utime(path, (stamp, stamp))


def test_cleanup_backtests_retains_latest(tmp_path):
    runs_dir = tmp_path / "backtests"
    runs_dir.mkdir()

    created = []
    for idx in range(5):
        run = runs_dir / f"run_2024010{idx}_demo"
        run.mkdir()
        (run / "manifest.json").write_text("{}")
        _touch(run, offset_seconds=idx * 60)
        created.append(run)

    removed = cleanup_backtests(retain=2, backtests_dir=runs_dir)
    assert len(removed) == 3
    assert all(not path.exists() for path in removed)
    remaining = [p for p in runs_dir.iterdir()]
    assert len(remaining) == 2


def test_cleanup_backtests_respects_age(tmp_path):
    runs_dir = tmp_path / "backtests"
    runs_dir.mkdir()

    recent = runs_dir / "run_recent"
    recent.mkdir()
    (recent / "manifest.json").write_text("{}")
    _touch(recent, offset_seconds=60)

    old = runs_dir / "run_old"
    old.mkdir()
    (old / "manifest.json").write_text("{}")
    _touch(old, offset_seconds=90 * 86400)

    removed = cleanup_backtests(retain=0, older_than_days=30, backtests_dir=runs_dir)
    assert removed == [old]
    assert not old.exists()
    assert recent.exists()


def test_cleanup_orders_skips_current(tmp_path):
    orders_dir = tmp_path / "orders"
    orders_dir.mkdir()
    current = orders_dir / "current_orders.csv"
    current.write_text("id,qty\n")

    older = []
    for idx in range(4):
        path = orders_dir / f"orders_2024010{idx}.csv"
        path.write_text("symbol,qty\nTSLA,1\n")
        _touch(path, offset_seconds=idx * 60)
        older.append(path)

    removed = cleanup_orders(retain=1, orders_dir=orders_dir)
    assert len(removed) == 3
    assert current.exists()
    assert all(not path.exists() for path in removed)


def test_cleanup_data_removes_unlisted(tmp_path):
    data_dir = tmp_path / "data_m5"
    data_dir.mkdir()
    for symbol in ("TSLA", "AAPL", "MSFT"):
        df = pd.DataFrame({"Close": [1, 2, 3]})
        df.to_parquet(data_dir / f"{symbol}.parquet")

    removed = cleanup_data("M5", keep_symbols=["TSLA"], data_dir=data_dir)
    removed_names = sorted(path.stem for path in removed)
    assert removed_names == ["AAPL", "MSFT"]
    assert (data_dir / "TSLA.parquet").exists()


def test_cleanup_artifacts_wrapper(tmp_path):
    runs_dir = tmp_path / "backtests"
    runs_dir.mkdir()
    run = runs_dir / "run_old"
    run.mkdir()
    _touch(run, offset_seconds=90 * 86400)

    orders_dir = tmp_path / "orders"
    orders_dir.mkdir()
    order_file = orders_dir / "orders_20240101.csv"
    order_file.write_text("symbol,qty\n")

    data_dir = tmp_path / "data_m5"
    data_dir.mkdir()
    df = pd.DataFrame({"Close": [1, 2]})
    df.to_parquet(data_dir / "AAPL.parquet")

    report = cleanup_artifacts(
        retain_runs=0,
        retain_orders=0,
        keep_symbols=["TSLA"],
        data_timeframe="M5",
        older_than_days=30,
        dry_run=False,
        backtests_dir=runs_dir,
        orders_dir=orders_dir,
        data_dir=data_dir,
    )

    assert run in report.removed_runs
    assert order_file in report.removed_orders
    assert (data_dir / "AAPL.parquet") in report.removed_data
