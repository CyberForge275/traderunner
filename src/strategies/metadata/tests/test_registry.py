"""
Unit Tests for StrategyRegistry
================================

Comprehensive tests for singleton registry including thread-safety.
"""

import pytest
import threading
from pathlib import Path
import tempfile
import time

from src.strategies.metadata.registry import StrategyRegistry
from src.strategies.metadata.schema import (
    StrategyMetadata,
    StrategyCapabilities,
    DataRequirements,
    DeploymentEnvironment,
)


@pytest.fixture
def registry():
    """Fresh registry for each test."""
    # Reset singleton
    StrategyRegistry.reset_instance()
    reg = StrategyRegistry()
    reg.clear()
    return reg


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    return StrategyMetadata(
        strategy_id="test_strategy_v1",
        canonical_name="test_strategy",
        display_name="Test Strategy",
        version="1.0.0",
        description="Test strategy for unit tests",
        capabilities=StrategyCapabilities(
            supports_live_trading=True,
            supports_backtest=True,
            supports_pre_papertrade=True,
        ),
        data_requirements=DataRequirements(
            required_timeframes=["M5"],
            min_history_days=30,
        ),
        config_class_path="test.Config",
        default_parameters={"param1": 123},
        signal_module_path="test.signals",
        core_module_path="test.core",
    )


class TestSingletonPattern:
    """Test singleton behavior."""

    def test_singleton_same_instance(self):
        """Multiple calls return same instance."""
        StrategyRegistry.reset_instance()
        reg1 = StrategyRegistry()
        reg2 = StrategyRegistry()
        assert reg1 is reg2

    def test_singleton_state_shared(self, registry, sample_metadata):
        """State is shared across instances."""
        reg1 = registry
        reg1.register(sample_metadata)

        reg2 = StrategyRegistry()
        assert reg2.count() == 1
        assert reg2.exists("test_strategy_v1")


class TestRegistration:
    """Test strategy registration."""

    def test_register_valid_strategy(self, registry, sample_metadata):
        """Register valid strategy succeeds."""
        registry.register(sample_metadata)
        assert registry.count() == 1
        assert registry.exists("test_strategy_v1")

    def test_register_duplicate_fails(self, registry, sample_metadata):
        """Registering duplicate strategy_id fails."""
        registry.register(sample_metadata)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(sample_metadata)

    def test_register_invalid_metadata_fails(self, registry):
        """Registering invalid metadata fails during creation."""
        # Invalid metadata fails on creation (in __post_init__)
        with pytest.raises(ValueError, match="Invalid strategy_id"):
            invalid = StrategyMetadata(
                strategy_id="invalid!@#",  # Invalid characters
                canonical_name="test",
                display_name="Test",
                version="1.0.0",
                description="Test",
                capabilities=StrategyCapabilities(
                    supports_backtest=True,
                    supports_live_trading=False,
                    supports_pre_papertrade=False,
                ),
                data_requirements=DataRequirements(
                    required_timeframes=["M5"],
                    min_history_days=30,
                ),
                config_class_path="test.Config",
                default_parameters={},
                signal_module_path="test.signals",
                core_module_path="test.core",
            )


class TestRetrieval:
    """Test strategy retrieval."""

    def test_get_existing_strategy(self, registry, sample_metadata):
        """Get returns registered strategy."""
        registry.register(sample_metadata)
        retrieved = registry.get("test_strategy_v1")
        assert retrieved.strategy_id == "test_strategy_v1"

    def test_get_nonexistent_fails(self, registry):
        """Get raises KeyError for missing strategy."""
        with pytest.raises(KeyError, match="not found"):
            registry.get("nonexistent")

    def test_get_or_none(self, registry, sample_metadata):
        """get_or_none returns None for missing."""
        assert registry.get_or_none("nonexistent") is None

        registry.register(sample_metadata)
        assert registry.get_or_none("test_strategy_v1") is not None

    def test_list_all(self, registry, sample_metadata):
        """list_all returns all strategies."""
        assert registry.list_all() == []

        registry.register(sample_metadata)
        all_strategies = registry.list_all()
        assert len(all_strategies) == 1
        assert all_strategies[0].strategy_id == "test_strategy_v1"

    def test_list_ids(self, registry, sample_metadata):
        """list_ids returns all IDs."""
        assert registry.list_ids() == []

        registry.register(sample_metadata)
        ids = registry.list_ids()
        assert ids == ["test_strategy_v1"]


class TestUpdate:
    """Test strategy updates."""

    def test_update_existing_strategy(self, registry, sample_metadata):
        """Update modifies existing strategy."""
        registry.register(sample_metadata)

        # Modify and update
        sample_metadata.description = "Updated description"
        registry.update(sample_metadata)

        retrieved = registry.get("test_strategy_v1")
        assert retrieved.description == "Updated description"

    def test_update_nonexistent_fails(self, registry, sample_metadata):
        """Update raises ValueError for missing strategy."""
        with pytest.raises(ValueError, match="not found"):
            registry.update(sample_metadata)


class TestQuerying:
    """Test advanced querying."""

    def test_get_by_canonical_name(self, registry):
        """Query by canonical name returns all versions."""
        # Register v1 and v2
        v1 = StrategyMetadata(
            strategy_id="test_v1",
            canonical_name="test",
            display_name="Test v1",
            version="1.0.0",
            description="V1",
            capabilities=StrategyCapabilities(
                supports_backtest=True,
                supports_live_trading=False,
                supports_pre_papertrade=False,
            ),
            data_requirements=DataRequirements(
                required_timeframes=["M5"],
                min_history_days=30,
            ),
            config_class_path="test.Config",
            default_parameters={},
            signal_module_path="test.signals",
            core_module_path="test.core",
        )

        v2 = StrategyMetadata(
            strategy_id="test_v2",
            canonical_name="test",
            display_name="Test v2",
            version="2.0.0",
            description="V2",
            capabilities=StrategyCapabilities(
                supports_backtest=True,
                supports_live_trading=False,
                supports_pre_papertrade=False,
            ),
            data_requirements=DataRequirements(
                required_timeframes=["M5"],
                min_history_days=30,
            ),
            config_class_path="test.Config",
            default_parameters={},
            signal_module_path="test.signals",
            core_module_path="test.core",
        )

        registry.register(v1)
        registry.register(v2)

        results = registry.get_by_canonical_name("test")
        assert len(results) == 2

    def test_get_by_capability(self, registry, sample_metadata):
        """Query by capability filter."""
        registry.register(sample_metadata)

        # Find live-trading strategies
        live_strategies = registry.get_by_capability(
            lambda cap: cap.supports_live_trading
        )
        assert len(live_strategies) == 1

        # Find backtest-only
        backtest_only = registry.get_by_capability(
            lambda cap: cap.supports_backtest and not cap.supports_live_trading
        )
        assert len(backtest_only) == 0

    def test_get_for_environment(self, registry, sample_metadata):
        """Query by deployment environment."""
        registry.register(sample_metadata)

        # Compatible with live trading
        live = registry.get_for_environment(DeploymentEnvironment.LIVE_TRADING)
        assert len(live) == 1

        # Compatible with pre-papertrade
        pre_paper = registry.get_for_environment(
            DeploymentEnvironment.PRE_PAPERTRADE_LAB
        )
        assert len(pre_paper) == 1


class TestRemoval:
    """Test strategy removal."""

    def test_unregister_existing(self, registry, sample_metadata):
        """Unregister removes strategy."""
        registry.register(sample_metadata)
        assert registry.count() == 1

        registry.unregister("test_strategy_v1")
        assert registry.count() == 0

    def test_unregister_nonexistent_fails(self, registry):
        """Unregister raises KeyError for missing."""
        with pytest.raises(KeyError):
            registry.unregister("nonexistent")

    def test_clear_all(self, registry, sample_metadata):
        """Clear removes all strategies."""
        registry.register(sample_metadata)
        assert registry.count() == 1

        registry.clear()
        assert registry.count() == 0


class TestSerialization:
    """Test JSON export/import."""

    def test_export_to_json(self, registry, sample_metadata):
        """Export registry to JSON file."""
        registry.register(sample_metadata)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_path = Path(f.name)

        try:
            registry.to_json(json_path)
            assert json_path.exists()

            # Verify content
            import json
            data = json.loads(json_path.read_text())
            assert "test_strategy_v1" in data
        finally:
            json_path.unlink()

    def test_import_from_json(self, registry, sample_metadata):
        """Import strategies from JSON file."""
        # Export first
        registry.register(sample_metadata)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_path = Path(f.name)

        try:
            registry.to_json(json_path)

            # Clear and import
            registry.clear()
            assert registry.count() == 0

            registry.from_json(json_path)
            assert registry.count() == 1
            assert registry.exists("test_strategy_v1")
        finally:
            json_path.unlink()


class TestThreadSafety:
    """Test thread safety of registry."""

    def test_concurrent_registration(self, registry):
        """Concurrent registration is thread-safe."""
        errors = []

        def register_strategy(index):
            try:
                metadata = StrategyMetadata(
                    strategy_id=f"strategy_{index}",
                    canonical_name=f"strat_{index}",
                    display_name=f"Strategy {index}",
                    version="1.0.0",
                    description=f"Strategy {index}",
                    capabilities=StrategyCapabilities(
                        supports_backtest=True,
                        supports_live_trading=False,
                        supports_pre_papertrade=False,
                    ),
                    data_requirements=DataRequirements(
                        required_timeframes=["M5"],
                        min_history_days=30,
                    ),
                    config_class_path="test.Config",
                    default_parameters={},
                    signal_module_path="test.signals",
                    core_module_path="test.core",
                )
                registry.register(metadata)
            except Exception as e:
                errors.append(e)

        # Start 10 threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=register_strategy, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all
        for t in threads:
            t.join()

        # Check results
        assert len(errors) == 0, f"Errors: {errors}"
        assert registry.count() == 10

    def test_concurrent_read_write(self, registry, sample_metadata):
        """Concurrent reads and writes are thread-safe."""
        registry.register(sample_metadata)

        read_results = []
        errors = []

        def reader():
            try:
                for _ in range(100):
                    strategy = registry.get("test_strategy_v1")
                    read_results.append(strategy.strategy_id)
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(100):
                    metadata = registry.get("test_strategy_v1")
                    metadata.description = f"Updated {i}"
                    registry.update(metadata)
            except Exception as e:
                errors.append(e)

        # Start readers and writer
        threads = []
        for _ in range(5):
            t = threading.Thread(target=reader)
            threads.append(t)
            t.start()

        t = threading.Thread(target=writer)
        threads.append(t)
        t.start()

        # Wait
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(read_results) == 500  # 5 threads * 100 reads


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_registry_operations(self, registry):
        """Operations on empty registry behave correctly."""
        assert registry.count() == 0
        assert registry.list_all() == []
        assert registry.list_ids() == []
        assert registry.get_or_none("anything") is None

    def test_repr_format(self, registry, sample_metadata):
        """__repr__ is informative."""
        repr_str = repr(registry)
        assert "StrategyRegistry" in repr_str
        assert "0 strategies" in repr_str

        registry.register(sample_metadata)
        repr_str = repr(registry)
        assert "1 strategies" in repr_str
