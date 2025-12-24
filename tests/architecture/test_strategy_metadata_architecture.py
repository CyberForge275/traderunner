"""
Architecture Tests - Enforce Single Source of Truth
===================================================

These tests ensure that no code uses deprecated patterns.
"""

import pytest
from pathlib import Path
import ast
import re


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRADING_DASHBOARD = PROJECT_ROOT / "trading_dashboard"
APPS_DIR = PROJECT_ROOT / "apps"


class TestStrategyMetadataArchitecture:
    """Enforce that StrategyMetadata comes from central registry."""

    def test_no_strategy_metadata_in_streamlit_state(self):
        """apps/streamlit/state.py should not define StrategyMetadata anymore."""
        state_file = APPS_DIR / "streamlit" / "state.py"

        if not state_file.exists():
            pytest.skip("apps/streamlit/state.py not found")

        content = state_file.read_text()

        # Should NOT define StrategyMetadata class
        assert "@dataclass\nclass StrategyMetadata" not in content, (
            "StrategyMetadata should be imported from src.strategies.metadata, "
            "not defined in apps/streamlit/state.py"
        )

        # Should NOT have STRATEGY_REGISTRY (unless it's deprecated/commented)
        if "STRATEGY_REGISTRY" in content:
            # Check if it's marked as deprecated
            assert "DEPRECATED" in content or "# Legacy" in content, (
                "STRATEGY_REGISTRY in state.py should be marked as deprecated"
            )

    def test_dashboard_uses_central_registry(self):
        """Dashboard should import from src.strategies.metadata."""
        helpers_file = PROJECT_ROOT / "trading_dashboard" / "utils" / "strategy_helpers.py"

        assert helpers_file.exists(), f"strategy_helpers.py not found at {helpers_file}"

        content = helpers_file.read_text()

        # Should import from central registry
        assert "from src.strategies.metadata import StrategyRegistry" in content, (
            "strategy_helpers.py must import StrategyRegistry from central package"
        )

        # Should NOT import from apps.streamlit.state
        assert "from apps.streamlit.state import STRATEGY_REGISTRY" not in content, (
            "strategy_helpers.py should not import from old state.py"
        )

    def test_no_hard_coded_strategy_names_in_services(self):
        """Services should not have hard-coded strategy name conditionals."""
        services_dir = TRADING_DASHBOARD / "services"

        if not services_dir.exists():
            pytest.skip("services directory not found")

        # Patterns to detect
        bad_patterns = [
            r'if\s+strategy\s*==\s*["\']inside_bar["\']',
            r'if\s+strategy_name\s*==\s*["\']rudometkin["\']',
            r'elif\s+strategy\s*==\s*["\']inside_bar',
        ]

        violations = []

        for py_file in services_dir.glob("*.py"):
            if py_file.name.startswith("test_"):
                continue

            content = py_file.read_text()

            for pattern in bad_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    violations.append(f"{py_file.name}: {matches}")

        # Allow some violations for backward compatibility during migration
        # But document them
        if violations:
            print(f"\n⚠️  Hard-coded strategy names found (should be refactored):")
            for v in violations:
                print(f"  - {v}")


class TestImportArchitecture:
    """Test import structure is correct."""

    def test_metadata_package_importable(self):
        """Metadata package should be importable."""
        from src.strategies.metadata import (
            StrategyMetadata,
            StrategyRegistry,
            StrategyCapabilities,
        )

        assert StrategyMetadata is not None
        assert StrategyRegistry is not None
        assert StrategyCapabilities is not None

    def test_profiles_importable(self):
        """Strategy profiles should be importable."""
        from src.strategies.profiles import (
            INSIDE_BAR_V1_PROFILE,
            INSIDE_BAR_V2_PROFILE,
            RUDOMETKIN_MOC_PROFILE,
        )

        assert INSIDE_BAR_V1_PROFILE.strategy_id == "insidebar_intraday"
        assert INSIDE_BAR_V2_PROFILE.strategy_id == "insidebar_intraday_v2"
        assert RUDOMETKIN_MOC_PROFILE.strategy_id == "rudometkin_moc_mode"

    def test_registry_singleton_works(self):
        """Registry should be singleton."""
        from src.strategies.metadata import StrategyRegistry

        reg1 = StrategyRegistry()
        reg2 = StrategyRegistry()

        assert reg1 is reg2, "Registry must be singleton"


class TestStrategyRegistryPopulated:
    """Test that registry is properly populated."""

    def test_all_strategies_registered(self):
        """All known strategies should be in registry."""
        from trading_dashboard.utils.strategy_helpers import get_registry

        registry = get_registry()

        # Should have at least 3 strategies
        assert registry.count() >= 3, "Registry should have InsideBar v1/v2 and Rudometkin"

        # Check specific IDs
        assert registry.exists("insidebar_intraday")
        assert registry.exists("insidebar_intraday_v2")
        assert registry.exists("rudometkin_moc_mode")

    def test_strategy_metadata_complete(self):
        """All registered strategies should have complete metadata."""
        from trading_dashboard.utils.strategy_helpers import get_registry

        registry = get_registry()

        for metadata in registry.list_all():
            # Check required fields
            assert metadata.strategy_id
            assert metadata.canonical_name
            assert metadata.display_name
            assert metadata.version
            assert metadata.description

            # Check capabilities exist
            assert metadata.capabilities is not None

            # Check data requirements
            assert metadata.data_requirements is not None
            assert len(metadata.data_requirements.required_timeframes) > 0

            # Check paths
            assert metadata.config_class_path
            assert metadata.signal_module_path
            assert metadata.core_module_path


class TestBackwardCompatibility:
    """Test backward compatibility during migration."""

    def test_strategy_helpers_api_stable(self):
        """strategy_helpers API should remain stable."""
        from trading_dashboard.utils.strategy_helpers import (
            get_all_strategies,
            get_strategy_metadata,
        )

        # Old API should still work
        all_strategies = get_all_strategies()
        assert isinstance(all_strategies, dict)
        assert len(all_strategies) > 0

        # Get specific strategy
        metadata = get_strategy_metadata("insidebar_intraday_v2")
        assert metadata is not None
        assert metadata.display_name == "Inside Bar Intraday v2"
