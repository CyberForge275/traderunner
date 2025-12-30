"""
Architecture Test: Callback Module Imports
===========================================

Ensures all critical callback modules are importable without errors.
This prevents ImportError issues from reaching production.

Critical for CI/CD: If a callback module has a broken import (e.g., importing
a non-existent function), this test will fail locally before deployment.
"""

import pytest
import importlib
import sys


def test_chart_callbacks_importable():
    """Test that chart_callbacks module can be imported without errors."""
    try:
        import trading_dashboard.callbacks.chart_callbacks
        # If we get here, import succeeded
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import chart_callbacks: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error importing chart_callbacks: {e}")


def test_pre_papertrade_callbacks_importable():
    """Test that pre_papertrade_callbacks module can be imported without errors."""
    try:
        # This might not exist yet, so we'll make it optional
        importlib.import_module('trading_dashboard.callbacks.pre_papertrade_callbacks')
        assert True
    except ModuleNotFoundError:
        # Module doesn't exist yet - skip test
        pytest.skip("pre_papertrade_callbacks module not yet implemented")
    except ImportError as e:
        pytest.fail(f"Failed to import pre_papertrade_callbacks: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error importing pre_papertrade_callbacks: {e}")


def test_all_callback_modules_importable():
    """Test that all callback modules in the callbacks directory are importable."""
    from pathlib import Path

    # Find all Python files in callbacks directory
    callbacks_dir = Path(__file__).parents[2] / "trading_dashboard" / "callbacks"

    if not callbacks_dir.exists():
        pytest.skip("Callbacks directory not found")

    callback_files = list(callbacks_dir.glob("*_callbacks.py"))

    if not callback_files:
        pytest.skip("No callback files found")

    failed_imports = []

    for callback_file in callback_files:
        module_name = f"trading_dashboard.callbacks.{callback_file.stem}"

        try:
            importlib.import_module(module_name)
        except ImportError as e:
            failed_imports.append((module_name, str(e)))
        except Exception as e:
            # Other exceptions (AttributeError, etc.) also indicate problems
            failed_imports.append((module_name, f"{type(e).__name__}: {str(e)}"))

    if failed_imports:
        error_msg = "Failed to import callback modules:\n"
        for module, error in failed_imports:
            error_msg += f"  - {module}: {error}\n"
        pytest.fail(error_msg)


def test_candles_repository_has_required_functions():
    """Test that candles repository has all required functions."""
    from trading_dashboard.repositories import candles

    # Functions that MUST exist
    required_functions = [
        'get_candle_data',
        'get_live_candle_data',
        'check_live_data_availability',
    ]

    missing = []
    for func_name in required_functions:
        if not hasattr(candles, func_name):
            missing.append(func_name)

    if missing:
        pytest.fail(f"Missing required functions in candles repository: {missing}")


def test_no_dead_imports_in_chart_callbacks():
    """Test that chart_callbacks doesn't import non-existent functions."""
    import trading_dashboard.callbacks.chart_callbacks as chart_callbacks

    # This test will fail at import time if there are broken imports
    # If we get here, all imports succeeded
    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
