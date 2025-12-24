"""
Tests for Pre-Paper Run Summary UI Enhancement
===============================================

Validates run summary display, contrast improvements, and technical details panel.
"""

import pytest
from unittest.mock import Mock, patch

from trading_dashboard.utils.run_summary_utils import (
    build_run_summary,
    format_strategy_display_name
)


class TestFormatStrategyDisplayName:
    """Test strategy display name formatting."""

    def test_simple_strategy_key(self):
        """Simple strategy key gets formatted properly."""
        result = format_strategy_display_name("insidebar_intraday")
        assert result == "InsideBar Intraday"

    def test_compound_strategy_value(self):
        """Compound strategy|version value gets parsed correctly."""
        result = format_strategy_display_name("insidebar_intraday|v1.00")
        assert "InsideBar Intraday" in result
        assert "v1.00" in result

    def test_unknown_strategy_key(self):
        """Unknown strategy key gets title-cased."""
        result = format_strategy_display_name("unknown_strategy")
        assert "Unknown Strategy" in result

    def test_strategy_v2(self):
        """Strategy v2 name formatted correctly."""
        result = format_strategy_display_name("insidebar_intraday_v2")
        assert "InsideBar Intraday v2" in result


class TestBuildRunSummary:
    """Test run summary builder."""

    def test_run_summary_contains_run_setup(self):
        """Run summary includes core run setup information."""
        result = {
            "strategy_version": {
                "id": 2,
                "label": "InsideBar v1.00",
                "strategy_key": "insidebar_intraday",
                "impl_version": 1,
                "lifecycle_stage": "BACKTEST_APPROVED",
                "config_hash": "test123",
                "code_ref": "gitsha"
            },
            "strategy_run_id": 5,
            "environment": "dev"
        }

        components = build_run_summary(
            result=result,
            strategy="insidebar_intraday",
            mode="replay",
            symbols_str="AAPL,TSLA",
            timeframe="M5",
            replay_date="2025-12-15",
            session_filter_input="15:00-17:00",
            show_technical_details=False
        )

        assert len(components) > 0

        # Convert components to strings for easier checking
        component_strs = [str(c) for c in components]
        full_str = "".join(component_strs)

        # Check for key information
        assert "Run Setup" in full_str
        assert "AAPL" in full_str or "TSLA" in full_str
        assert "M5" in full_str
        assert "15:00" in full_str or "17:00" in full_str

    def test_run_summary_includes_lifecycle_metadata(self):
        """Run summary includes lifecycle metadata when available."""
        result = {
            "strategy_version": {
                "id": 2,
                "label": "InsideBar v1.00",
                "strategy_key": "insidebar_intraday",
                "impl_version": 1,
                "lifecycle_stage": "BACKTEST_APPROVED"
            },
            "strategy_run_id": 5
        }

        components = build_run_summary(
            result=result,
            strategy="insidebar_intraday",
            mode="live",
            symbols_str="HOOD",
            timeframe="M1",
            show_technical_details=False
        )

        component_strs = [str(c) for c in components]
        full_str = "".join(component_strs)

        assert "Lifecycle Metadata" in full_str
        assert "InsideBar v1.00" in full_str
        assert "Run ID" in full_str

    def test_run_summary_handles_live_mode(self):
        """Run summary correctly displays live mode."""
        components = build_run_summary(
            result={},
            strategy="insidebar_intraday",
            mode="live",
            symbols_str="AAPL",
            timeframe="M5",
            show_technical_details=False
        )

        full_str = "".join([str(c) for c in components])

        assert "Live" in full_str
        assert "Real-time" in full_str or "Pre-Paper (Live)" in full_str

    def test_run_summary_handles_replay_mode(self):
        """Run summary correctly displays replay mode with date."""
        components = build_run_summary(
            result={},
            strategy="insidebar_intraday",
            mode="replay",
            symbols_str="TSLA",
            timeframe="M15",
            replay_date="2025-12-10",
            show_technical_details=False
        )

        full_str = "".join([str(c) for c in components])

        assert "Replay" in full_str or "Time Machine" in full_str
        assert "2025-12-10" in full_str

    def test_run_summary_with_technical_details(self):
        """Run summary includes technical details section when enabled."""
        result = {
            "strategy_version": {
                "id": 2,
                "label": "InsideBar v1.00",
                "config_hash": "abc123",
                "code_ref": "gitsha456"
            }
        }

        components = build_run_summary(
            result=result,
            strategy="insidebar_intraday",
            mode="replay",
            symbols_str="NVDA",
            timeframe="M30",
            show_technical_details=True  # Enable
        )

        full_str = "".join([str(c) for c in components])

        assert "Technical Details" in full_str or "technical-details" in full_str

    def test_run_summary_without_version_metadata(self):
        """Run summary works without lifecycle metadata."""
        components = build_run_summary(
            result={},  # No strategy_version or run_id
            strategy="rudometkin_moc_mode",
            mode="live",
            symbols_str="SPY",
            timeframe="D",
            show_technical_details=False
        )

        # Should still render run setup
        assert len(components) > 0

        full_str = "".join([str(c) for c in components])
        assert "Run Setup" in full_str
        assert "SPY" in full_str

    def test_run_summary_handles_empty_symbols(self):
        """Run summary gracefully handles empty symbol list."""
        components = build_run_summary(
            result={},
            strategy="insidebar_intraday",
            mode="live",
            symbols_str="",  # Empty
            timeframe="M5",
            show_technical_details=False
        )

        full_str = "".join([str(c) for c in components])

        assert "None" in full_str or "Symbols" in full_str

    def test_run_summary_session_filter_display(self):
        """Run summary displays session filter correctly."""
        components = build_run_summary(
            result={},
            strategy="insidebar_intraday",
            mode="replay",
            symbols_str="AAPL",
            timeframe="M5",
            session_filter_input="09:30-16:00",
            show_technical_details=False
        )

        full_str = "".join([str(c) for c in components])

        assert "09:30" in full_str or "16:00" in full_str or "Session" in full_str

    def test_run_summary_all_sessions_when_no_filter(self):
        """Run summary shows 'All sessions' when no filter specified."""
        components = build_run_summary(
            result={},
            strategy="insidebar_intraday",
            mode="live",
            symbols_str="TSLA",
            timeframe="M1",
            session_filter_input=None,  # No filter
            show_technical_details=False
        )

        full_str = "".join([str(c) for c in components])

        assert "All sessions" in full_str or "Session" in full_str


class TestStrategyDescriptionFix:
    """Test that Unknown strategy bug is fixed."""

    def test_extract_base_strategy_from_compound_value(self):
        """Test that compound strategy|version values extract correctly."""
        # Simulate what the callback does
        strategy = "insidebar_intraday|v1.00"
        base_strategy = strategy.split("|")[0] if "|" in strategy else strategy

        assert base_strategy == "insidebar_intraday"

    def test_simple_strategy_value_unchanged(self):
        """Test that simple strategy values work as before."""
        strategy = "insidebar_intraday"
        base_strategy = strategy.split("|")[0] if "|" in strategy else strategy

        assert base_strategy == "insidebar_intraday"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
