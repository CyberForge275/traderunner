"""
Minimal tests for cache readers session_mode awareness.

Ensures critical call sites use IntradayStore.path_for with session_mode parameter.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from axiom_bt.intraday import Timeframe


class TestDataCoverageSessionAware:
    """Test that data_coverage module updated to use session-aware paths."""

    def test_data_coverage_imports_intraday_store(self):
        """Verify data_coverage now imports IntradayStore for session-aware paths."""
        import backtest.services.data_coverage as coverage_module
        import inspect

        # Check that check_coverage function source contains IntradayStore usage
        source = inspect.getsource(coverage_module.check_coverage)
        assert "IntradayStore" in source, "check_coverage should use IntradayStore"
        assert "path_for" in source, "check_coverage should use path_for method"
        assert 'session_mode="rth"' in source, "check_coverage should default to rth"

        # Same for _fetch_missing_range
        fetch_source = inspect.getsource(coverage_module._fetch_missing_range)
        assert "IntradayStore" in fetch_source, "_fetch_missing_range should use IntradayStore"
        assert "path_for" in fetch_source, "_fetch_missing_range should use path_for"
        assert 'session_mode="rth"' in fetch_source, "_fetch_missing_range should default to rth"


class TestCliDataSessionMode:
    """Test that cli_data supports --session-mode argument."""

    def test_cli_data_default_session_mode_is_rth(self):
        """Verify cli_data argparse defaults to session_mode='rth'."""
        from axiom_bt.cli_data import build_parser

        parser = build_parser()
        args = parser.parse_args(['ensure-intraday', '--symbols', 'HOOD', '--use-sample'])

        assert hasattr(args, 'session_mode')
        assert args.session_mode == 'rth'

    def test_cli_data_session_mode_all_accepted(self):
        """Verify cli_data accepts --session-mode all."""
        from axiom_bt.cli_data import build_parser

        parser = build_parser()
        args = parser.parse_args([
            'ensure-intraday',
            '--symbols', 'HOOD',
            '--session-mode', 'all',
            '--use-sample'
        ])

        assert args.session_mode == 'all'
