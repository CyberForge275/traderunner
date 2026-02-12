from __future__ import annotations

import importlib
from pathlib import Path


def test_artifacts_root_resolved_from_runtime_config(tmp_path: Path, monkeypatch):
    from core.settings.runtime_config import reset_runtime_config_for_tests
    from axiom_bt.pipeline.paths import get_artifacts_root

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        """
paths:
  marketdata_data_root: /var/lib/trading/marketdata
  trading_artifacts_root: /var/lib/trading/artifacts
""".strip()
    )
    monkeypatch.setenv("TRADING_CONFIG", str(cfg))
    monkeypatch.delenv("TRADING_ARTIFACTS_ROOT", raising=False)
    monkeypatch.delenv("TRADERUNNER_ARTIFACTS_ROOT", raising=False)

    reset_runtime_config_for_tests()
    assert get_artifacts_root() == Path("/var/lib/trading/artifacts")


def test_dashboard_config_backtests_dir_resolved_from_runtime_config(tmp_path: Path, monkeypatch):
    from core.settings.runtime_config import reset_runtime_config_for_tests
    from src.core.settings.config import reset_settings

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        """
paths:
  marketdata_data_root: /var/lib/trading/marketdata
  trading_artifacts_root: /var/lib/trading/artifacts
""".strip()
    )
    monkeypatch.setenv("TRADING_CONFIG", str(cfg))
    monkeypatch.delenv("TRADING_ARTIFACTS_ROOT", raising=False)
    monkeypatch.delenv("TRADERUNNER_ARTIFACTS_ROOT", raising=False)

    reset_runtime_config_for_tests()
    reset_settings()

    import trading_dashboard.config as dashboard_config

    dashboard_config = importlib.reload(dashboard_config)
    assert dashboard_config.BACKTESTS_DIR == Path("/var/lib/trading/artifacts/backtests")
