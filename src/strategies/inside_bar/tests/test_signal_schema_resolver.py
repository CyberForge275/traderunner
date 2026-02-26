from __future__ import annotations

import pytest

from strategies.inside_bar.signal_schema import get_signal_frame_schema
from strategies.inside_bar.signal_schema import _load_schema_refs_from_yaml


def test_get_signal_frame_schema_supports_v105_from_yaml():
    schema = get_signal_frame_schema("1.0.5")
    names = [c.name for c in schema.required_strategy]
    assert "oco_group_id" in names


def test_get_signal_frame_schema_v103_uses_oco_schema():
    schema = get_signal_frame_schema("1.0.3")
    names = [c.name for c in schema.required_strategy]
    assert "oco_group_id" in names


def test_missing_signal_schema_ref_fails_fast(tmp_path):
    cfg = tmp_path / "insidebar_intraday.yaml"
    cfg.write_text(
        """
strategy_id: insidebar_intraday
versions:
  1.0.5:
    required_warmup_bars: 40
    core: {}
    tunable: {}
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="signal_schema_ref missing for version 1.0.5"):
        _load_schema_refs_from_yaml(cfg)
