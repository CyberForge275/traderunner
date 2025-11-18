import csv
import sys
from pathlib import Path

import pandas as pd

from axiom_bt.engines.replay_engine import Costs, simulate_insidebar_from_orders
from axiom_bt.runner import main as runner_main
from core.settings import DEFAULT_INITIAL_CASH


def _create_sample_data(data_dir: Path, data_dir_m1: Path, symbol: str = "TEST") -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    data_dir_m1.mkdir(parents=True, exist_ok=True)

    ts_m1 = pd.date_range("2025-01-01 00:00", periods=60, freq="min", tz="UTC")
    base = 100 + pd.Series(range(len(ts_m1)), index=ts_m1) * 0.2
    prices_m1 = pd.DataFrame(
        {
            "Open": base,
            "High": base + 0.3,
            "Low": base - 0.3,
            "Close": base + 0.1,
            "Volume": 1000,
        },
        index=ts_m1,
    )
    prices_m1.to_parquet(data_dir_m1 / f"{symbol}.parquet")

    prices_m5 = prices_m1.resample("5min").agg(
        {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
    )
    prices_m5.to_parquet(data_dir / f"{symbol}.parquet")


def _create_orders_csv(path: Path, symbol: str = "TEST") -> None:
    headers = [
        "valid_from",
        "valid_to",
        "symbol",
        "side",
        "order_type",
        "price",
        "stop_loss",
        "take_profit",
        "qty",
        "tif",
        "oco_group",
        "source",
    ]
    rows = [
        [
            "2025-01-01T00:00:00+00:00",
            "2025-01-01T09:00:00+00:00",
            symbol,
            "BUY",
            "STOP",
            101.0,
            99.0,
            103.0,
            1.0,
            "DAY",
            "grp1",
            "test",
        ]
    ]

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def test_simulate_insidebar_from_orders(tmp_path):
    data_dir = tmp_path / "data_m5"
    data_dir_m1 = tmp_path / "data_m1"
    orders_csv = tmp_path / "orders.csv"
    _create_sample_data(data_dir, data_dir_m1)
    _create_orders_csv(orders_csv)

    result = simulate_insidebar_from_orders(
        orders_csv=orders_csv,
        data_path=data_dir,
        tz="UTC",
        costs=Costs(fees_bps=2.0, slippage_bps=1.0),
        initial_cash=DEFAULT_INITIAL_CASH,
        data_path_m1=data_dir_m1,
    )

    assert not result["filled_orders"].empty
    assert not result["trades"].empty
    assert "metrics" in result
    assert result["metrics"]["num_trades"] == 1
    filled = result["filled_orders"].iloc[0]
    assert filled["entry_ts"] != filled["exit_ts"]
    orders_snapshot = result["orders"]
    assert "filled" in orders_snapshot.columns
    assert orders_snapshot["filled"].isin([True, False]).all()
    required_cost_cols = [
        "fees_entry",
        "fees_exit",
        "fees_total",
        "slippage_entry",
        "slippage_exit",
        "slippage_total",
    ]
    trades_df = result["trades"]
    for col in required_cost_cols:
        assert col in result["filled_orders"].columns
        assert col in trades_df.columns


def test_runner_cli(tmp_path, monkeypatch):
    data_dir = tmp_path / "data_m5"
    data_dir_m1 = tmp_path / "data_m1"
    orders_csv = tmp_path / "orders.csv"
    _create_sample_data(data_dir, data_dir_m1)
    _create_orders_csv(orders_csv)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "name: test_run",
                "engine: replay",
                "mode: insidebar_intraday",
                f"orders_source_csv: {orders_csv}",
                "data:",
                f"  path: {data_dir}",
                f"  path_m1: {data_dir_m1}",
                "  tz: UTC",
                "costs:",
                "  fees_bps: 2.0",
                "  slippage_bps: 1.0",
                f"initial_cash: {DEFAULT_INITIAL_CASH}",
            ]
        )
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(Path.cwd() / "src"))

    argv = ["prog", "--config", str(config_path)]
    monkeypatch.setattr(sys, "argv", argv)
    assert runner_main() == 0

    backtests_dir = Path("artifacts/backtests")
    assert backtests_dir.exists()
    run_dirs = list(backtests_dir.glob("run_*"))
    assert run_dirs
    orders_csv = run_dirs[0] / "orders.csv"
    assert orders_csv.exists()
    saved_orders = pd.read_csv(orders_csv)
    assert "filled" in saved_orders.columns
