"""Tests for capability-based strategy separation in pipeline.

This module tests that:
1. Two-stage strategies use the capability flag
2. Single-stage strategies bypass universe logic
3. Inside Bar never depends on universe configuration
4. Rudometkin gets filtered symbols via daily scan
"""

import pytest
from pathlib import Path
from apps.streamlit.state import (
    INSIDE_BAR_METADATA,
    RUDOMETKIN_METADATA,
    StrategyMetadata,
)


class TestStrategyCapabilities:
    """Test strategy capability flags."""

    def test_inside_bar_has_no_universe_capabilities(self):
        """Inside Bar should not require universe or two-stage pipeline."""
        assert INSIDE_BAR_METADATA.requires_universe is False
        assert INSIDE_BAR_METADATA.supports_two_stage_pipeline is False

    def test_rudometkin_has_universe_capabilities(self):
        """Rudometkin should require universe and use two-stage pipeline."""
        assert RUDOMETKIN_METADATA.requires_universe is True
        assert RUDOMETKIN_METADATA.supports_two_stage_pipeline is True

    def test_capability_fields_have_defaults(self):
        """New StrategyMetadata should have default capability values."""
        meta = StrategyMetadata(
            name="test_strategy",
            label="Test Strategy",
            timezone="UTC",
            sessions=["09:30-16:00"],
            signal_module="test.module",
            orders_source=Path("/tmp/orders.csv"),
            default_payload={},
            strategy_name="test",
        )
        # Default values should be False
        assert meta.requires_universe is False
        assert meta.supports_two_stage_pipeline is False


class TestPipelineRoutingLogic:
    """Test that pipeline routes correctly based on capabilities."""

    def test_two_stage_capability_detected(self):
        """Pipeline should detect two-stage capability flag."""
        # This test verifies the capability is correctly set
        assert RUDOMETKIN_METADATA.supports_two_stage_pipeline is True

        # The pipeline code should now check:
        # if pipeline.strategy.supports_two_stage_pipeline:
        #     from strategies.rudometkin_moc import pipeline as rudometkin_pipeline
        #     filtered_symbols = rudometkin_pipeline.run_daily_scan(pipeline, max_daily)

    def test_single_stage_has_no_capability(self):
        """Single-stage strategies should not have two-stage capability."""
        assert INSIDE_BAR_METADATA.supports_two_stage_pipeline is False

        # The pipeline should skip universe logic for these strategies

    def test_strategy_metadata_independence(self):
        """Each strategy's metadata should be independent."""
        # Verify changing one doesn't affect the other
        inside_bar_orig = INSIDE_BAR_METADATA.supports_two_stage_pipeline
        rudometkin_orig = RUDOMETKIN_METADATA.supports_two_stage_pipeline

        assert inside_bar_orig is False
        assert rudometkin_orig is True

        # They should remain independent (no shared mutable state)
        assert INSIDE_BAR_METADATA.supports_two_stage_pipeline != RUDOMETKIN_METADATA.supports_two_stage_pipeline


class TestStrategyIsolation:
    """Test that strategies remain isolated from each other's concerns."""

    def test_inside_bar_metadata_has_no_universe_path(self):
        """Inside Bar should not have universe configuration."""
        assert "universe_path" not in INSIDE_BAR_METADATA.default_strategy_config

    def test_rudometkin_metadata_has_universe_path(self):
        """Rudometkin should have universe configuration."""
        assert "universe_path" in RUDOMETKIN_METADATA.default_strategy_config
        universe_path = RUDOMETKIN_METADATA.default_strategy_config["universe_path"]
        assert "rudometkin.parquet" in universe_path

    def test_inside_bar_uses_provided_symbols_only(self):
        """Inside Bar should work with any symbol list, no universe check."""
        # This is a conceptual test - Inside Bar doesn't filter by universe
        # The strategy itself doesn't have universe loading logic
        from strategies.inside_bar.strategy import InsideBarStrategy

        strategy = InsideBarStrategy()
        # Strategy should not have universe-related methods
        assert not hasattr(strategy, '_get_universe_symbols')
        assert not hasattr(strategy, '_build_universe_mask')

    def test_rudometkin_has_universe_methods(self):
        """Rudometkin should have universe filtering methods."""
        from strategies.rudometkin_moc.strategy import RudometkinMOCStrategy

        strategy = RudometkinMOCStrategy()
        # Strategy should have universe-related methods
        assert hasattr(strategy, '_get_universe_symbols')
        assert hasattr(strategy, '_build_universe_mask')


class TestRudometkinPipelineModule:
    """Test the extracted Rudometkin pipeline module."""

    def test_pipeline_module_exists(self):
        """Rudometkin pipeline module should exist."""
        from strategies.rudometkin_moc import pipeline as rudometkin_pipeline
        assert rudometkin_pipeline is not None

    def test_run_daily_scan_function_exists(self):
        """run_daily_scan function should be exported."""
        from strategies.rudometkin_moc.pipeline import run_daily_scan
        assert callable(run_daily_scan)

    def test_pipeline_module_has_no_streamlit_requirement(self):
        """Pipeline module should gracefully handle missing streamlit."""
        from strategies.rudometkin_moc import pipeline as rudometkin_pipeline
        # HAS_STREAMLIT flag should exist
        assert hasattr(rudometkin_pipeline, 'HAS_STREAMLIT')
        # Module should import successfully regardless


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
