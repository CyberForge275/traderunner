import json
import pandas as pd

from axiom_bt.full_backtest_runner import write_trades_artifacts
from axiom_bt.metrics import compose_metrics
from axiom_bt.compat.trades_contract import REQUIRED_UI_COLUMNS


def test_write_trades_artifacts_title_case(tmp_path):
    trades_df_raw = pd.DataFrame(
        [
            {
                "Entry Time": "2026-01-01T10:00:00Z",
                "Exit Time": "2026-01-01T10:05:00Z",
                "Symbol": "AAA",
                "Side": "BUY",
                "Entry Price": 100.0,
                "Exit Price": 101.0,
                "Qty": 10,
                "PnL": 10.0,
                "Exit Reason": "time_exit",
                "Return %": 0.01,
            },
            {
                "Entry Time": "2026-01-02T10:00:00Z",
                "Exit Time": "2026-01-02T10:05:00Z",
                "Symbol": "BBB",
                "Side": "SELL",
                "Entry Price": 50.0,
                "Exit Price": 49.5,
                "Qty": 20,
                "PnL": -10.0,
                "Exit Reason": "time_exit",
                "Return %": -0.01,
            },
        ]
    )

    artifacts = []
    trades_ui = write_trades_artifacts(trades_df_raw, tmp_path, artifacts)

    trades_csv = tmp_path / "trades.csv"
    raw_csv = tmp_path / "trades_compound.csv"

    assert trades_csv.exists()
    assert raw_csv.exists()
    assert list(trades_ui.columns[: len(REQUIRED_UI_COLUMNS)]) == REQUIRED_UI_COLUMNS
    assert len(trades_ui) == 2


def test_write_trades_artifacts_empty(tmp_path):
    trades_df_raw = pd.DataFrame()
    artifacts = []

    trades_ui = write_trades_artifacts(trades_df_raw, tmp_path, artifacts)

    trades_csv = tmp_path / "trades.csv"
    raw_csv = tmp_path / "trades_compound.csv"

    assert trades_csv.exists()
    assert not raw_csv.exists()
    assert trades_ui.empty
    assert list(trades_ui.columns) == REQUIRED_UI_COLUMNS


def test_compose_metrics_uses_normalized_trades(tmp_path):
    # Minimal equity curve
    equity_df = pd.DataFrame(
        {
            "ts": ["2026-01-01T10:00:00Z", "2026-01-01T10:05:00Z"],
            "equity": [10000.0, 10020.0],
        }
    )

    trades_ui = pd.DataFrame(
        {
            "symbol": ["AAA"],
            "side": ["BUY"],
            "qty": [10],
            "entry_ts": ["2026-01-01T10:00:00Z"],
            "entry_price": [100.0],
            "exit_ts": ["2026-01-01T10:05:00Z"],
            "exit_price": [102.0],
            "pnl": [20.0],
            "reason": ["time_exit"],
        }
    )

    metrics = compose_metrics(trades_ui, equity_df, initial_cash=10000.0)

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))

    assert metrics_path.exists()
    assert metrics["num_trades"] == 1
    assert metrics["win_rate"] == 1.0
    assert metrics["final_cash"] == 10020.0
