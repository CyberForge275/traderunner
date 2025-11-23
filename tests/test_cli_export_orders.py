from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))

from trade import cli_export_orders as exporter


def _write_signals(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def test_rudometkin_orders_generate_entry_exit(tmp_path, monkeypatch):
    orders_dir = tmp_path / "orders"
    monkeypatch.setattr(exporter, "ORDERS_DIR", orders_dir)

    signals_path = tmp_path / "signals.csv"
    _write_signals(
        signals_path,
        [
            {
                "ts": "2025-10-06T15:30:00Z",
                "Symbol": "LU",
                "long_entry": 3.859,
                "sl_long": 3.50,
                "setup": "moc_long",
            },
            {
                "ts": "2025-10-06T15:30:00Z",
                "Symbol": "ASTS",
                "short_entry": 71.145,
                "sl_short": 74.00,
                "setup": "moc_short",
            },
        ],
    )

    argv = [
        "--source",
        str(signals_path),
        "--sessions",
        "15:30-22:00",
        "--tz",
        "Europe/Berlin",
        "--strategy",
        "rudometkin_moc",
        "--sizing",
        "fixed",
        "--qty",
        "5",
        "--tick-size",
        "0.01",
        "--round-mode",
        "nearest",
        "--gtd-tz",
        "America/New_York",
    ]

    result = exporter.main(argv)
    assert result == 0

    current_orders = orders_dir / "current_orders.csv"
    assert current_orders.exists()

    orders_df = pd.read_csv(current_orders)
    # Expect 4 rows: entry+exit for long and short
    assert len(orders_df) == 4

    entry_long = orders_df.iloc[0]
    exit_long = orders_df.iloc[1]
    entry_short = orders_df.iloc[2]
    exit_short = orders_df.iloc[3]

    assert entry_long["OrderType"] == "LMT"
    assert entry_long["TimeInForce"] == "GTD"
    assert entry_long["IsExit"] == 0
    assert entry_long["Action"] == "BUY"
    assert entry_long["Quantity"] == 5
    assert float(entry_long["LmtPrice"]) == 3.86
    assert entry_long["OrderId"] == entry_long["TradeID"]

    assert exit_long["IsExit"] == 1
    assert exit_long["OrderType"] == "MOC"
    assert exit_long["ParentId"] == entry_long["OrderId"]
    assert exit_long["OcaId"] == entry_long["OrderId"]
    assert exit_long["Action"] == "SELL"

    assert entry_short["Action"] == "SELL"
    assert entry_short["Side"] == -1
    assert exit_short["Action"] == "BUY"
    assert exit_short["ParentId"] == entry_short["OrderId"]
