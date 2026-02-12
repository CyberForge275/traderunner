from __future__ import annotations

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
