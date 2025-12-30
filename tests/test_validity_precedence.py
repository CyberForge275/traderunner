"""
Test order validity precedence rules.

Ensures that validity_policy parameter correctly determines which
duration parameters are used (timeframe_minutes vs validity_minutes).
"""
import pandas as pd
import pytest
from datetime import timedelta

from trade.validity import calculate_validity_window
from strategies.inside_bar.config import SessionFilter


class TestValidityPrecedence:
    """Test that validity policies use correct precedence for duration parameters."""
    
    def test_one_bar_ignores_validity_minutes(self):
        """Verify one_bar policy uses timeframe_minutes, ignoring validity_minutes."""
        signal_ts = pd.Timestamp("2025-01-15 10:00:00", tz="America/New_York")
        session_filter = SessionFilter.from_strings(["09:30-16:00"])
        
        # Set validity_minutes to unrealistic value (999) to prove it's ignored
        valid_from, valid_to = calculate_validity_window(
            signal_ts=signal_ts,
            timeframe_minutes=5,
            session_filter=session_filter,
            session_timezone="America/New_York",
            validity_policy="one_bar",
            validity_minutes=999,  # Should be IGNORED
            valid_from_policy="signal_ts"
        )
        
        # Verify delta equals timeframe, not validity_minutes
        delta_minutes = (valid_to - valid_from).total_seconds() / 60
        assert delta_minutes == 5, \
            f"one_bar policy should use timeframe_minutes=5, got {delta_minutes} minutes"
        assert delta_minutes != 999, \
            "one_bar policy should NOT use validity_minutes=999"
    
    def test_fixed_minutes_ignores_timeframe(self):
        """Verify fixed_minutes policy uses validity_minutes, ignoring timeframe."""
        signal_ts = pd.Timestamp("2025-01-15 10:00:00", tz="America/New_York")
        session_filter = SessionFilter.from_strings(["09:30-16:00"])
        
        # Set timeframe to unrealistic value (999) to prove it's ignored
        valid_from, valid_to = calculate_validity_window(
            signal_ts=signal_ts,
            timeframe_minutes=999,  # Should be IGNORED
            session_filter=session_filter,
            session_timezone="America/New_York",
            validity_policy="fixed_minutes",
            validity_minutes=60,
            valid_from_policy="signal_ts"
        )
        
        # Verify delta equals validity_minutes, not timeframe
        delta_minutes = (valid_to - valid_from).total_seconds() / 60
        assert delta_minutes == 60, \
            f"fixed_minutes policy should use validity_minutes=60, got {delta_minutes} minutes"
        assert delta_minutes != 999, \
            "fixed_minutes policy should NOT use timeframe_minutes=999"
    
    def test_one_bar_various_timeframes(self):
        """Verify one_bar works correctly for M1, M5, M15 timeframes."""
        signal_ts = pd.Timestamp("2025-01-15 10:00:00", tz="America/New_York")
        session_filter = SessionFilter.from_strings(["09:30-16:00"])
        
        test_cases = [
            (1, "M1"),
            (5, "M5"),
            (15, "M15"),
            (60, "H1"),
        ]
        
        for timeframe_min, label in test_cases:
            valid_from, valid_to = calculate_validity_window(
                signal_ts=signal_ts,
                timeframe_minutes=timeframe_min,
                session_filter=session_filter,
                session_timezone="America/New_York",
                validity_policy="one_bar",
                validity_minutes=999,  # Always ignored
                valid_from_policy="signal_ts"
            )
            
            delta_minutes = (valid_to - valid_from).total_seconds() / 60
            assert delta_minutes == timeframe_min, \
                f"{label}: Expected {timeframe_min} minutes, got {delta_minutes}"
    
    def test_session_end_ignores_both_durations(self):
        """Verify session_end policy ignores both timeframe and validity_minutes."""
        # Signal 30 minutes before session end
        signal_ts = pd.Timestamp("2025-01-15 15:30:00", tz="America/New_York")
        session_filter = SessionFilter.from_strings(["09:30-16:00"])
        
        valid_from, valid_to = calculate_validity_window(
            signal_ts=signal_ts,
            timeframe_minutes=999,  # Should be IGNORED
            session_filter=session_filter,
            session_timezone="America/New_York",
            validity_policy="session_end",
            validity_minutes=999,  # Should be IGNORED
            valid_from_policy="signal_ts"
        )
        
        # Verify delta equals time to session end (30 minutes), not 999
        delta_minutes = (valid_to - valid_from).total_seconds() / 60
        assert delta_minutes == 30, \
            f"session_end should use session boundary, got {delta_minutes} minutes"
        assert delta_minutes != 999, \
            "session_end should NOT use timeframe_minutes or validity_minutes"
        
        # Verify valid_to is exactly at session end (16:00)
        expected_end = pd.Timestamp("2025-01-15 16:00:00", tz="America/New_York")
        assert valid_to == expected_end, \
            f"session_end should end at 16:00, got {valid_to}"


class TestValidityPrecedenceDocumentation:
    """Test that precedence rules are clearly documented."""
    
    def test_precedence_table(self):
        """Document expected precedence for each policy (for reference)."""
        precedence_table = {
            "one_bar": {
                "uses_timeframe_minutes": True,
                "uses_validity_minutes": False,
                "uses_session_filter": False,
            },
            "fixed_minutes": {
                "uses_timeframe_minutes": False,
                "uses_validity_minutes": True,
                "uses_session_filter": False,  # (optional clamp)
            },
            "session_end": {
                "uses_timeframe_minutes": False,
                "uses_validity_minutes": False,
                "uses_session_filter": True,
            },
        }
        
        # This test serves as documentation - always passes
        assert precedence_table is not None
        
        # Verify all policies are covered
        expected_policies = {"one_bar", "fixed_minutes", "session_end"}
        assert set(precedence_table.keys()) == expected_policies
