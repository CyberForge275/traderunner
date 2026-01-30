import pandas as pd

from axiom_bt.pipeline.execution import execute


def _bars_with_session_end(entry_ts: pd.Timestamp, exit_ts: pd.Timestamp) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [entry_ts, exit_ts],
            "open": [100.0, 110.0],
            "high": [100.0, 110.0],
            "low": [100.0, 110.0],
            "close": [100.0, 110.0],
            "volume": [1.0, 1.0],
        }
    )


def test_execution_fallback_to_session_end():
    entry_ts = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")  # 10:35 NY
    session_end_ts = pd.Timestamp("2025-04-03 19:00:00", tz="UTC")  # 15:00 NY
    bars = _bars_with_session_end(entry_ts, session_end_ts)

    fills = pd.DataFrame(
        {
            "template_id": ["t1"],
            "symbol": ["HOOD"],
            "fill_ts": [entry_ts],
            "fill_price": [100.0],
            "reason": ["signal_fill"],
        }
    )
    intents = pd.DataFrame(
        {
            "template_id": ["t1"],
            "side": ["BUY"],
            "exit_ts": [pd.NaT],
            "exit_reason": [pd.NA],
        }
    )

    exec_art = execute(
        fills,
        intents,
        bars,
        initial_cash=1000.0,
        compound_enabled=False,
        order_validity_policy="session_end",
        session_timezone="America/New_York",
        session_filter=["09:30-11:00", "14:00-15:00"],
    )

    trades = exec_art.trades
    assert trades.loc[0, "template_id"] == "t1"
    assert pd.to_datetime(trades.loc[0, "exit_ts"], utc=True) == session_end_ts
    assert pd.to_datetime(trades.loc[0, "entry_ts"], utc=True) == entry_ts
    assert trades.loc[0, "reason"] == "session_end"
    assert trades.loc[0, "exit_ts"] != trades.loc[0, "entry_ts"]


def test_execution_missing_params_raises():
    entry_ts = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")
    bars = _bars_with_session_end(entry_ts, entry_ts)

    fills = pd.DataFrame(
        {
            "template_id": ["t1"],
            "symbol": ["HOOD"],
            "fill_ts": [entry_ts],
            "fill_price": [100.0],
            "reason": ["signal_fill"],
        }
    )
    intents = pd.DataFrame(
        {
            "template_id": ["t1"],
            "side": ["BUY"],
            "exit_ts": [pd.NaT],
            "exit_reason": [pd.NA],
        }
    )

    try:
        execute(
            fills,
            intents,
            bars,
            initial_cash=1000.0,
            compound_enabled=False,
            order_validity_policy=None,
            session_timezone=None,
            session_filter=None,
        )
    except ValueError as exc:
        assert "exit_ts missing" in str(exc) or "session_end fallback" in str(exc)
    else:
        assert False, "Expected ValueError for missing validity/session params"
