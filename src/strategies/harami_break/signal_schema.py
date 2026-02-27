"""Harami strategy-owned SignalFrame schema (versioned SSOT)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, List

import yaml

from axiom_bt.contracts.signal_frame_contract_v1 import ColumnSpec, SignalFrameSchemaV1


def _schema_v1_0_0() -> SignalFrameSchemaV1:
    base: List[ColumnSpec] = [
        ColumnSpec("timestamp", "datetime64[ns, UTC]", False, "base"),
        ColumnSpec("symbol", "string", False, "base"),
        ColumnSpec("open", "float64", False, "base"),
        ColumnSpec("high", "float64", False, "base"),
        ColumnSpec("low", "float64", False, "base"),
        ColumnSpec("close", "float64", False, "base"),
        ColumnSpec("volume", "float64", True, "base"),
    ]
    generic: List[ColumnSpec] = [
        ColumnSpec("timeframe", "string", False, "generic"),
        ColumnSpec("strategy_id", "string", False, "generic"),
        ColumnSpec("strategy_version", "string", False, "generic"),
        ColumnSpec("strategy_tag", "string", False, "generic"),
    ]
    strategy_cols: List[ColumnSpec] = [
        ColumnSpec("prev_high", "float64", True, "indicator"),
        ColumnSpec("prev_low", "float64", True, "indicator"),
        ColumnSpec("prev_open", "float64", True, "indicator"),
        ColumnSpec("prev_close", "float64", True, "indicator"),
        ColumnSpec("mother_body_fraction", "float64", False, "indicator"),
        ColumnSpec("mother_body_ok", "bool", False, "indicator"),
        ColumnSpec("mother_bar_ts", "datetime64[ns, UTC]", True, "indicator"),
        ColumnSpec("is_inside_bar", "bool", False, "indicator"),
        ColumnSpec("is_motherbar", "bool", False, "indicator"),
        ColumnSpec("armed", "bool", False, "indicator"),
        ColumnSpec("mother_bar_high", "float64", True, "indicator"),
        ColumnSpec("mother_bar_low", "float64", True, "indicator"),
        ColumnSpec("armed_from_ts", "datetime64[ns, UTC]", True, "indicator"),
        ColumnSpec("valid_until_ts", "datetime64[ns, UTC]", True, "indicator"),
        ColumnSpec("valid_window_ok", "bool", False, "indicator"),
        ColumnSpec("long_trigger_price", "float64", True, "indicator"),
        ColumnSpec("short_trigger_price", "float64", True, "indicator"),
    ]
    return SignalFrameSchemaV1(
        strategy_id="harami_break_intraday",
        strategy_tag="hb",
        version="1.0.0",
        required_base=base,
        required_generic=generic,
        required_strategy=strategy_cols,
    )


SCHEMA_BUILDERS: Dict[str, Callable[[], SignalFrameSchemaV1]] = {
    "v1_0_0": _schema_v1_0_0,
}


@lru_cache(maxsize=1)
def _load_schema_refs_by_version() -> Dict[str, str]:
    cfg_path = Path(__file__).resolve().parent / "harami_break_intraday.yaml"
    with cfg_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    versions = payload.get("versions")
    if not isinstance(versions, dict) or not versions:
        raise ValueError("harami_break_intraday.yaml missing 'versions' mapping")
    refs: Dict[str, str] = {}
    for version, node in versions.items():
        if not isinstance(node, dict):
            raise ValueError(f"invalid version node for {version}: expected mapping")
        if "signal_schema_ref" not in node:
            raise ValueError(
                f"signal_schema_ref missing for version {version} (SSOT: set in YAML)"
            )
        ref = node["signal_schema_ref"]
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError(
                f"invalid signal_schema_ref for version {version}: expected non-empty string"
            )
        refs[str(version)] = ref.strip()
    return refs


def get_signal_frame_schema(strategy_version: str) -> SignalFrameSchemaV1:
    refs = _load_schema_refs_by_version()
    version = str(strategy_version)
    if version not in refs:
        raise ValueError(
            f"Unknown harami schema version '{strategy_version}'. Available: {sorted(refs.keys())}"
        )
    ref = refs[version]
    if ref not in SCHEMA_BUILDERS:
        raise ValueError(
            f"Unknown harami schema ref '{ref}' for version '{strategy_version}'. "
            f"Available refs: {sorted(SCHEMA_BUILDERS.keys())}"
        )
    return SCHEMA_BUILDERS[ref]()
