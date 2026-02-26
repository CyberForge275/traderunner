"""
Test order validity precedence rules.
"""
import pandas as pd
import pytest

from trade.validity import calculate_validity_window
from strategies.inside_bar.config import SessionFilter


class TestValidityPrecedence:
    def test_fixed_bars_uses_timeframe_and_bar_count(self):
        signal_ts = pd.Timestamp("2025-01-15 10:00:00", tz="America/New_York")
        session_filter = SessionFilter.from_strings(["09:30-16:00"])

        valid_from, valid_to = calculate_validity_window(
            signal_ts=signal_ts,
            timeframe_minutes=5,
            session_filter=session_filter,
            session_timezone="America/New_York",
            validity_policy="fixed_bars",
            validity_minutes=999,
            validity_bars=3,
            valid_from_policy="signal_ts",
        )

        delta_minutes = (valid_to - valid_from).total_seconds() / 60
        assert delta_minutes == 15

    def test_fixed_minutes_ignores_timeframe(self):
        signal_ts = pd.Timestamp("2025-01-15 10:00:00", tz="America/New_York")
        session_filter = SessionFilter.from_strings(["09:30-16:00"])

        valid_from, valid_to = calculate_validity_window(
            signal_ts=signal_ts,
            timeframe_minutes=999,
            session_filter=session_filter,
            session_timezone="America/New_York",
            validity_policy="fixed_minutes",
            validity_minutes=60,
            validity_bars=5,
            valid_from_policy="signal_ts",
        )

        delta_minutes = (valid_to - valid_from).total_seconds() / 60
        assert delta_minutes == 60

    def test_legacy_policy_name_is_rejected(self):
        signal_ts = pd.Timestamp("2025-01-15 10:00:00", tz="America/New_York")
        session_filter = SessionFilter.from_strings(["09:30-16:00"])

        with pytest.raises(ValueError, match="Unknown validity_policy"):
            calculate_validity_window(
                signal_ts=signal_ts,
                timeframe_minutes=5,
                session_filter=session_filter,
                session_timezone="America/New_York",
                validity_policy="legacy_policy_name",
                validity_minutes=60,
                validity_bars=1,
                valid_from_policy="signal_ts",
            )


class TestValidityBoundaries:
    def test_inside_bar_spec_validates_ranges(self):
        from strategies.config.specs.inside_bar_spec import InsideBarSpec

        spec = InsideBarSpec()
        core = {
            "inside_bar_definition_mode": "mb_body_oc__ib_hl",
            "atr_period": 8,
            "risk_reward_ratio": 2.0,
            "min_mother_bar_size": 0.5,
            "breakout_confirmation": True,
            "inside_bar_mode": "inclusive",
            "session_timezone": "America/New_York",
            "session_mode": "rth",
            "session_filter": ["09:30-16:00"],
            "timeframe_minutes": 5,
            "valid_from_policy": "signal_ts",
            "order_validity_policy": "fixed_minutes",
            "order_validity_minutes": 61,
            "order_validity_bars": 1,
            "stop_cap_atr": 2.0,
            "max_position_pct": 100.0,
        }
        with pytest.raises(ValueError, match="order_validity_minutes"):
            spec.validate_core("x", core)

        core["order_validity_minutes"] = 30
        core["order_validity_bars"] = 11
        with pytest.raises(ValueError, match="order_validity_bars"):
            spec.validate_core("x", core)
