from __future__ import annotations

from pathlib import Path

import pytest


def test_runtime_config_missing_paths_raises(tmp_path: Path):
    from core.settings.runtime_config import RuntimeConfigError, load_runtime_config

    cfg = tmp_path / "broken.yaml"
    cfg.write_text("services:\n  marketdata_stream_url: http://127.0.0.1:8090\n")

    with pytest.raises(RuntimeConfigError):
        load_runtime_config(config_path=cfg, search_paths=[], strict=True)


def test_runtime_config_rejects_relative_paths(tmp_path: Path):
    from core.settings.runtime_config import RuntimeConfigError, load_runtime_config

    cfg = tmp_path / "bad-path.yaml"
    cfg.write_text(
        """
paths:
  marketdata_data_root: ./relative
  trading_artifacts_root: /var/lib/trading/artifacts
""".strip()
    )

    with pytest.raises(RuntimeConfigError):
        load_runtime_config(config_path=cfg, search_paths=[])
