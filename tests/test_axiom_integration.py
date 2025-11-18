import csv
import sys
from pathlib import Path

import pandas as pd

from axiom_bt.engines.replay_engine import Costs, simulate_insidebar_from_orders
from axiom_bt.runner import main as runner_main


def _create_sample_data(data_dir: Path, symbol: str = "TEST") -> None:
    timestamps = pd.date_range("2025-01-01", periods=10, freq="h", tz="UTC")
    prices = pd.DataFrame(
        {
            "Open": [100 + i for i in range(10)],
            "High": [101 + i for i in range(10)],
            "Low": [99 + i for i in range(10)],
            "Close": [100.5 + i for i in range(10)],
            "Volume": [1000 + i * 10 for i in range(10)],
        },
        index=timestamps,
    )
    data_dir.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(data_dir / f"{symbol}.parquet")


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
    data_dir = tmp_path / "data"
    orders_csv = tmp_path / "orders.csv"
    _create_sample_data(data_dir)
    _create_orders_csv(orders_csv)

    result = simulate_insidebar_from_orders(
        orders_csv=orders_csv,
        data_path=data_dir,
        tz="UTC",
        costs=Costs(fees_bps=2.0, slippage_bps=1.0),
        initial_cash=100_000.0,
    )

    assert not result["filled_orders"].empty
    assert not result["trades"].empty
    assert "metrics" in result
    assert result["metrics"]["num_trades"] == 1


def test_runner_cli(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    orders_csv = tmp_path / "orders.csv"
    _create_sample_data(data_dir)
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
                "  tz: UTC",
                "costs:",
                "  fees_bps: 2.0",
                "  slippage_bps: 1.0",
                "initial_cash: 100000.0",
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
