import shutil
from pathlib import Path

import pandas as pd

from axiom_bt.cli_data import cmd_ensure_intraday
from axiom_bt.demo import generate_demo_data
from signals.cli_inside_bar import main as signals_main
from trade.cli_export_orders import main as orders_main


def test_pipeline_generates_orders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Prepare synthetic M1 → M5 data
    generate_demo_data(root=Path("artifacts/demo"), symbol="TEST", window_days=10)
    args = type("Args", (), {
        "symbols": "TEST",
        "universe_file": None,
        "exchange": "US",
        "tz": "UTC",
        "start": None,
        "end": None,
        "force": True,
        "generate_m15": False,
        "use_sample": True,
    })
    cmd_ensure_intraday(args)

    # Generate signals from M5 data
    signals_main([
        "--symbols", "TEST",
        "--data-path", "artifacts/data_m5",
        "--tz", "UTC",
        "--sessions", "00:00-23:59",
        "--min-master-body", "0.0",
    ])

    signals_file = Path("artifacts/signals/current_signals_ib.csv")
    assert signals_file.exists()
    signals_df = pd.read_csv(signals_file)
    expected_signal_cols = [
        "ts",
        "session_id",
        "ib",
        "ib_qual",
        "long_entry",
        "short_entry",
        "sl_long",
        "sl_short",
        "tp_long",
        "tp_short",
        "Symbol",
    ]
    assert list(signals_df.columns) == expected_signal_cols
    if not signals_df.empty:
        ts_local = pd.to_datetime(signals_df["ts"], utc=True).dt.tz_convert("Europe/Berlin")
        signals_df["session_date"] = ts_local.dt.date
        dup_counts = (
            signals_df.groupby(["Symbol", "session_date", "session_id"])
            .size()
            .max()
        )
        assert dup_counts <= 1
        signals_df.drop(columns=["session_date"], inplace=True)

    # Export orders
    orders_main([
        "--source", str(signals_file),
        "--sessions", "00:00-23:59",
        "--tz", "UTC",
    ])

    orders_file = Path("artifacts/orders/current_orders.csv")
    assert orders_file.exists()
    orders_df = pd.read_csv(orders_file)
    expected_order_cols = [
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
    assert list(orders_df.columns) == expected_order_cols
