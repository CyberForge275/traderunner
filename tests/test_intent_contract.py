import pandas as pd
import logging

from axiom_bt.artifacts.intent_contract import sanitize_intent


def test_intent_drops_forbidden_columns():
    intent = {
        "template_id": "t1",
        "signal_ts": "2025-01-01 14:25:00+00:00",
        "entry_price": 10.0,
        "exit_ts": "2025-01-01 15:00:00+00:00",
        "exit_reason": "session_end",
        "dbg_exit_ts_ny": "2025-01-01 10:00:00-04:00",
        "dbg_trigger_ts": "2025-01-01 14:25:00+00:00",
        "fill_price": 10.5,
    }
    out = sanitize_intent(
        intent,
        intent_generated_ts=pd.to_datetime("2025-01-01 14:25:00+00:00"),
        strict=False,
    )
    assert "exit_ts" not in out
    assert "exit_reason" not in out
    assert "dbg_exit_ts_ny" not in out
    assert "dbg_trigger_ts" not in out
    assert "fill_price" not in out


def test_intent_future_timestamp_violation_strict():
    intent = {
        "template_id": "t1",
        "signal_ts": "2025-01-01 14:25:00+00:00",
        "entry_price": 10.0,
        "dbg_inside_ts": "2025-01-01 14:25:00+00:00",
        "dbg_valid_to_ts_utc": "2025-01-01 15:00:00+00:00",
    }
    # allowed scheduled validity should not raise
    out = sanitize_intent(
        intent,
        intent_generated_ts=pd.to_datetime("2025-01-01 14:25:00+00:00"),
        strict=True,
    )
    assert "dbg_valid_to_ts_utc" in out


def test_intent_drops_unknown_keys():
    intent = {
        "template_id": "t1",
        "signal_ts": "2025-01-01 14:25:00+00:00",
        "entry_price": 10.0,
        "unknown_key": "x",
    }
    out = sanitize_intent(
        intent,
        intent_generated_ts=pd.to_datetime("2025-01-01 14:25:00+00:00"),
        strict=False,
    )
    assert "unknown_key" not in out


def test_intent_contract_sanitizable_cases_log_info_not_error(caplog):
    intent = {
        "template_id": "t1",
        "signal_ts": "2025-01-01 14:25:00+00:00",
        "entry_price": 10.0,
        "dbg_trigger_ts": "2025-01-01 14:25:00+00:00",  # forbidden -> removed
        "dbg_inside_ts": "2025-01-01 14:30:00+00:00",  # future ts, strict=False
    }
    caplog.set_level(logging.INFO, logger="axiom_bt.artifacts.intent_contract")
    sanitize_intent(
        intent,
        intent_generated_ts=pd.to_datetime("2025-01-01 14:25:00+00:00"),
        strict=False,
    )
    error_msgs = [r.message for r in caplog.records if r.levelno >= logging.ERROR]
    assert not any("intent_contract_violation" in m for m in error_msgs)
    assert not any("intent_contract_future_ts" in m for m in error_msgs)
