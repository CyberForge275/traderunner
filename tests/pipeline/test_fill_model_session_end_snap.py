import pandas as pd

from axiom_bt.pipeline.fill_model import generate_fills


def test_session_end_snap_exit_when_valid_to_missing_bar():
    bars = pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2025-05-01 14:40:00+00:00"),
                pd.Timestamp("2025-05-01 14:45:00+00:00"),
                pd.Timestamp("2025-05-01 14:50:00+00:00"),
                pd.Timestamp("2025-05-01 15:10:00+00:00"),
            ],
            "open": [3.40, 3.40, 3.41, 3.40],
            "high": [3.42, 3.41, 3.41, 3.40],
            "low": [3.39, 3.39, 3.40, 3.35],
            "close": [3.41, 3.40, 3.41, 3.35],
        }
    )

    events_intent = pd.DataFrame(
        [
            {
                "template_id": "ib_HYMC_20250501_144000_BUY",
                "symbol": "HYMC",
                "side": "BUY",
                "signal_ts": pd.Timestamp("2025-05-01 14:40:00+00:00"),
                "entry_price": 3.41,
                "stop_price": 1.00,
                "take_profit_price": 10.00,
                "order_valid_to_ts": pd.Timestamp("2025-05-01 15:00:00+00:00"),
                "oco_group_id": "grp_1",
            }
        ]
    )

    fills_art = generate_fills(events_intent, bars, order_validity_policy="session_end")
    fills = fills_art.fills

    session_end = fills[fills["reason"] == "session_end"].iloc[0]
    assert session_end["fill_ts"] == pd.Timestamp("2025-05-01 14:50:00+00:00")
    assert session_end["fill_price"] == 3.41

    assert fills_art.gap_stats["session_end_snap_count"] == 1
    assert fills_art.gap_stats["bars_gap_max_seconds"] >= 1200
    assert fills_art.gap_stats["bars_gap_count_gt_2x_median"] == 1
