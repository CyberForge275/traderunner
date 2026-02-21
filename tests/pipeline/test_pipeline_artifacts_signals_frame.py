from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from axiom_bt.pipeline.artifacts import write_artifacts


def test_write_artifacts_persists_signals_frame_csv(tmp_path: Path) -> None:
    signals_frame = pd.DataFrame(
        [
            {
                "timestamp": "2025-01-01T14:00:00+00:00",
                "inside_bar_reject_reason": "IB_BODY_FRACTION",
                "mother_body_fraction": 0.52,
                "inside_body_fraction": 0.12,
            }
        ]
    )
    events_intent = pd.DataFrame(
        [
            {
                "template_id": "t1",
                "signal_ts": "2025-01-01T14:00:00+00:00",
                "symbol": "TEST",
                "side": "BUY",
                "entry_price": 100.0,
                "stop_price": 99.0,
                "take_profit_price": 102.0,
                "strategy_id": "insidebar_intraday",
                "strategy_version": "1.0.2",
                "sig_mother_body_fraction": 0.52,
                "sig_inside_body_fraction": 0.12,
            }
        ]
    )
    empty = pd.DataFrame()
    manifest_fields = {
        "run_id": "r1",
        "params": {},
        "artifacts_index": [],
    }
    result_fields = {"run_id": "r1", "status": "success", "details": {}}

    write_artifacts(
        tmp_path,
        signals_frame=signals_frame,
        events_intent=events_intent,
        fills=empty,
        trades=empty,
        equity_curve=empty,
        ledger=empty,
        manifest_fields=manifest_fields,
        result_fields=result_fields,
        metrics={},
    )

    signals_path = tmp_path / "signals_frame.csv"
    assert signals_path.exists()
    loaded = pd.read_csv(signals_path)
    assert "inside_bar_reject_reason" in loaded.columns
    assert "mother_body_fraction" in loaded.columns
    assert "inside_body_fraction" in loaded.columns

    manifest = json.loads((tmp_path / "run_manifest.json").read_text())
    assert "signals_frame.csv" in manifest.get("artifacts_index", [])
