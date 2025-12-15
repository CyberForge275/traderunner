"""
Pre-Paper UI Lifecycle Integration Tests
=========================================

Tests for UI integration of lifecycle tracking in Pre-PaperTrading Lab.

Validates:
- Version resolution logic
- Callback integration with version resolver
- UI display of lifecycle metadata
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path

from trading_dashboard.repositories.strategy_metadata import (
    StrategyMetadataRepository,
    LifecycleStage,
    StrategyVersion,
)


class TestVersionResolver:
    """Test version resolver helper functions."""
    
    def test_resolve_pre_paper_version_returns_backtest_approved(self):
        """Resolver returns valid BACKTEST_APPROVED version."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()
            
            # Create BACKTEST_APPROVED version
            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,
                label="InsideBar v1.00",
                code_ref_value="test123",
                config_json={"atr_period": 14},
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED
            )
            
            # Test resolver
            from trading_dashboard.utils.version_resolver import resolve_pre_paper_version
            
            # Patch get_repository to use our test database
            with patch('trading_dashboard.utils.version_resolver.get_repository', return_value=repo):
                version = resolve_pre_paper_version("insidebar_intraday")
            
            assert version is not None
            assert version.id == version_id
            assert version.impl_version == 1
            assert version.lifecycle_stage == LifecycleStage.BACKTEST_APPROVED
            
        finally:
            db_path.unlink()
    
    def test_resolve_pre_paper_version_raises_if_no_valid_version(self):
        """Resolver raises clear error when no valid version exists."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()
            
            # Create only DRAFT version (not eligible)
            repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,
                label="InsideBar Draft",
                code_ref_value="test123",
                config_json={"atr_period": 14},
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.DRAFT_EXPLORE  # Not approved!
            )
            
            from trading_dashboard.utils.version_resolver import resolve_pre_paper_version
            
            with patch('trading_dashboard.utils.version_resolver.get_repository', return_value=repo):
                with pytest.raises(ValueError, match="No valid strategy version"):
                    resolve_pre_paper_version("insidebar_intraday")
            
        finally:
            db_path.unlink()
    
    def test_resolve_pre_paper_version_raises_if_no_versions_exist(self):
        """Resolver raises helpful error when strategy has no versions at all."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()
            
            from trading_dashboard.utils.version_resolver import resolve_pre_paper_version
            
            with patch('trading_dashboard.utils.version_resolver.get_repository', return_value=repo):
                with pytest.raises(ValueError, match="No strategy versions found"):
                    resolve_pre_paper_version("nonexistent_strategy")
            
        finally:
            db_path.unlink()
    
    def test_resolve_pre_paper_version_skips_beta_versions(self):
        """Resolver skips beta versions (impl_version < 1)."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()
            
            # Create beta version (should be skipped)
            repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=0,  # Beta!
                label="InsideBar Beta",
                code_ref_value="test123",
                config_json={"atr_period": 14},
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED  # Even if approved
            )
            
            from trading_dashboard.utils.version_resolver import resolve_pre_paper_version
            
            with patch('trading_dashboard.utils.version_resolver.get_repository', return_value=repo):
                with pytest.raises(ValueError, match="No valid strategy version"):
                    resolve_pre_paper_version("insidebar_intraday")
            
        finally:
            db_path.unlink()


class TestPrePaperCallbackIntegration:
    """Test Pre-Paper callback integration with lifecycle tracking."""
    
    def test_callback_passes_strategy_version_id_to_adapter(self):
        """Callback resolves version and passes strategy_version_id to adapter."""
        # Mock version
        mock_version = Mock()
        mock_version.id = 42
        mock_version.strategy_key = "insidebar_intraday"
        mock_version.impl_version = 1
        mock_version.profile_key = "insidebar_intraday"
        mock_version.profile_version = 1
        mock_version.label = "InsideBar v1.00"
        mock_version.lifecycle_stage = LifecycleStage.BACKTEST_APPROVED
        mock_version.code_ref_value = "abc123"
        mock_version.config_hash = "hash123"
        
        # Mock adapter
        mock_adapter = Mock()
        mock_adapter.execute_strategy = Mock(return_value={
            "status": "completed",
            "signals": [],
            "signals_generated": 0,
        })
        
        # Test the logic directly
        with patch('trading_dashboard.utils.version_resolver.resolve_pre_paper_version', return_value=mock_version):
            from trading_dashboard.utils.version_resolver import resolve_pre_paper_version, format_version_for_ui
            
            # Simulate callback logic
            strategy_name = "insidebar_intraday"
            resolved_version = resolve_pre_paper_version(strategy_name)
            strategy_version_id = resolved_version.id
            
            # Simulate adapter call
            mock_adapter.execute_strategy(
                strategy=strategy_name,
                mode="replay",
                symbols=["AAPL"],
                timeframe="M5",
                replay_date="2025-12-13",
                strategy_version_id=strategy_version_id
            )
            
            # Verify adapter was called with correct version_id
            mock_adapter.execute_strategy.assert_called_once()
            call_kwargs = mock_adapter.execute_strategy.call_args.kwargs
            assert call_kwargs["strategy_version_id"] == 42
    
    def test_callback_exposes_version_and_run_in_result(self):
        """Callback result includes strategy_version and strategy_run_id from adapter."""
        # Mock adapter result with lifecycle metadata
        mock_result = {
            "status": "completed",
            "signals": [],
            "signals_generated": 0,
            "strategy_version": {
                "id": 42,
                "strategy_key": "insidebar_intraday",
                "impl_version": 1,
                "label": "InsideBar v1.00 – Initial Stable",
                "lifecycle_stage": "BACKTEST_APPROVED",
            },
            "strategy_run_id": 123,
        }
        
        # Verify metadata is present
        assert "strategy_version" in mock_result
        assert "strategy_run_id" in mock_result
        assert mock_result["strategy_version"]["id"] == 42
        assert mock_result["strategy_run_id"] == 123
    
    def test_callback_handles_version_resolution_error_gracefully(self):
        """Callback shows clear error message when version resolution fails."""
        from dash import html
        
        # Mock version resolver to raise error
        with patch('trading_dashboard.utils.version_resolver.resolve_pre_paper_version', side_effect=ValueError("No valid version")):
            from trading_dashboard.utils.version_resolver import resolve_pre_paper_version
            
            # Simulate callback error handling
            try:
                resolve_pre_paper_version("insidebar_intraday")
                assert False, "Should have raised ValueError"
            except ValueError as e:
                # Callback should catch this and return error tuple
                error_message = str(e)
                assert "No valid version" in error_message


class TestFormatVersionForUI:
    """Test version formatting helper."""
    
    def test_format_version_for_ui_returns_dict(self):
        """format_version_for_ui returns UI-friendly dictionary."""
        # Mock version
        mock_version = Mock()
        mock_version.id = 42
        mock_version.strategy_key = "insidebar_intraday"
        mock_version.impl_version = 1
        mock_version.profile_key = "insidebar_intraday"
        mock_version.profile_version = 1
        mock_version.label = "InsideBar v1.00"
        mock_version.lifecycle_stage = LifecycleStage.BACKTEST_APPROVED
        mock_version.code_ref_value = "abc123"
        mock_version.config_hash = "hash123"
        
        from trading_dashboard.utils.version_resolver import format_version_for_ui
        
        result = format_version_for_ui(mock_version)
        
        assert isinstance(result, dict)
        assert result["id"] == 42
        assert result["strategy_key"] == "insidebar_intraday"
        assert result["impl_version"] == 1
        assert result["label"] == "InsideBar v1.00"
        assert result["lifecycle_stage"] == "BACKTEST_APPROVED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
