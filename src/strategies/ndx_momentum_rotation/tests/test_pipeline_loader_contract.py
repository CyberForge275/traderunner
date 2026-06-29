from __future__ import annotations

from axiom_bt.pipeline.strategy_config_loader import load_strategy_params_from_ssot


def test_pipeline_loader_supports_ndx_momentum_rotation() -> None:
    cfg = load_strategy_params_from_ssot("ndx_momentum_rotation", "1.0.0")
    assert cfg["strategy_id"] == "ndx_momentum_rotation"
    assert cfg["core"]["topk"] == 5


def test_pipeline_loader_existing_insidebar_unchanged() -> None:
    cfg = load_strategy_params_from_ssot("insidebar_intraday", "1.0.0")
    assert cfg["strategy_id"] == "insidebar_intraday"
    assert "core" in cfg
