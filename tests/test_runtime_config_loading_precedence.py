from __future__ import annotations

from pathlib import Path

import pytest


def test_runtime_config_precedence_cli_over_env(tmp_path: Path, monkeypatch):
    from core.settings.runtime_config import load_runtime_config

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        """
paths:
  marketdata_data_root: /var/lib/trading/marketdata
  trading_artifacts_root: /var/lib/trading/artifacts
services:
  marketdata_stream_url: http://127.0.0.1:8090
runtime:
  pipeline_consumer_only: true
  pipeline_auto_ensure_bars: false
""".strip()
    )

    monkeypatch.setenv("MARKETDATA_DATA_ROOT", "/tmp/env-marketdata")
    monkeypatch.setenv("TRADING_ARTIFACTS_ROOT", "/tmp/env-artifacts")

    rc = load_runtime_config(config_path=cfg)
    assert rc.paths.marketdata_data_root == Path("/var/lib/trading/marketdata")
    assert rc.paths.trading_artifacts_root == Path("/var/lib/trading/artifacts")


def test_runtime_config_uses_env_fallback_when_file_missing(monkeypatch):
    from core.settings.runtime_config import load_runtime_config

    monkeypatch.setenv("MARKETDATA_DATA_ROOT", "/tmp/env-marketdata")
    monkeypatch.setenv("TRADING_ARTIFACTS_ROOT", "/tmp/env-artifacts")
    rc = load_runtime_config(config_path=None, search_paths=[])

    assert str(rc.paths.marketdata_data_root) == "/tmp/env-marketdata"
    assert str(rc.paths.trading_artifacts_root) == "/tmp/env-artifacts"
