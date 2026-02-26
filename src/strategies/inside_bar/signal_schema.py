"""InsideBar strategy-owned SignalFrame schema (versioned SSOT).

All signal/indicator column definitions live here (not in pipeline/hooks/contracts).
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from dataclasses import asdict
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

    indicators: List[ColumnSpec] = [
        ColumnSpec("atr", "float64", False, "indicator"),
        ColumnSpec("inside_bar", "bool", False, "indicator"),
        ColumnSpec("mother_high", "float64", True, "indicator"),
        ColumnSpec("mother_low", "float64", True, "indicator"),
        ColumnSpec("breakout_long", "bool", False, "indicator"),
        ColumnSpec("breakout_short", "bool", False, "indicator"),
    ]

    signals: List[ColumnSpec] = [
        ColumnSpec("signal_side", "string", True, "signal"),
        ColumnSpec("signal_reason", "string", True, "signal"),
        ColumnSpec("entry_price", "float64", True, "signal"),
        ColumnSpec("stop_price", "float64", True, "signal"),
        ColumnSpec("take_profit_price", "float64", True, "signal"),
        ColumnSpec("template_id", "string", True, "signal"),
        ColumnSpec("exit_ts", "datetime64[ns, UTC]", True, "signal"),
        ColumnSpec("exit_reason", "string", True, "signal"),
    ]

    # Generic/metadata columns
    generic: List[ColumnSpec] = [
        ColumnSpec("timeframe", "string", False, "generic"),
        ColumnSpec("strategy_id", "string", False, "generic"),
        ColumnSpec("strategy_version", "string", False, "generic"),
        ColumnSpec("strategy_tag", "string", False, "generic"),
    ]

    return SignalFrameSchemaV1(
        strategy_id="insidebar_intraday",
        strategy_tag="ib",
        version="1.0.0",
        required_base=base,
        required_generic=generic,
        required_strategy=indicators + signals,
    )


def _schema_v1_0_2() -> SignalFrameSchemaV1:
    """Schema v1.0.2: add oco_group_id for two-leg OCO intents."""
    base = _schema_v1_0_0().required_base
    indicators = _schema_v1_0_0().required_strategy[:6]
    signals = [
        ColumnSpec("signal_side", "string", True, "signal"),
        ColumnSpec("signal_reason", "string", True, "signal"),
        ColumnSpec("entry_price", "float64", True, "signal"),
        ColumnSpec("stop_price", "float64", True, "signal"),
        ColumnSpec("take_profit_price", "float64", True, "signal"),
        ColumnSpec("template_id", "string", True, "signal"),
        ColumnSpec("exit_ts", "datetime64[ns, UTC]", True, "signal"),
        ColumnSpec("exit_reason", "string", True, "signal"),
        ColumnSpec("oco_group_id", "string", True, "signal"),
    ]
    generic = _schema_v1_0_0().required_generic
    return SignalFrameSchemaV1(
        strategy_id="insidebar_intraday",
        strategy_tag="ib",
        version="1.0.2",
        required_base=base,
        required_generic=generic,
        required_strategy=indicators + signals,
    )


SCHEMA_BUILDERS: Dict[str, Callable[[], SignalFrameSchemaV1]] = {
    "v1_0_0": _schema_v1_0_0,
    "v1_0_2": _schema_v1_0_2,
}


@lru_cache(maxsize=1)
def _load_schema_refs_by_version() -> Dict[str, str]:
    cfg_path = Path(__file__).resolve().parent / "insidebar_intraday.yaml"
    return _load_schema_refs_from_yaml(cfg_path)


def _load_schema_refs_from_yaml(cfg_path: Path) -> Dict[str, str]:
    if not cfg_path.exists():
        raise ValueError(f"inside_bar config missing: {cfg_path}")

    with cfg_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    versions = payload.get("versions")
    if not isinstance(versions, dict) or not versions:
        raise ValueError("insidebar_intraday.yaml missing 'versions' mapping")

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
    """Resolve schema by strategy_version -> signal_schema_ref (YAML SSOT)."""
    refs = _load_schema_refs_by_version()
    version = str(strategy_version)
    if version not in refs:
        raise ValueError(
            f"Unknown insidebar schema version '{strategy_version}'. Available: {sorted(refs.keys())}"
        )

    ref = refs[version]
    if ref not in SCHEMA_BUILDERS:
        raise ValueError(
            f"Unknown insidebar schema ref '{ref}' for version '{strategy_version}'. "
            f"Available refs: {sorted(SCHEMA_BUILDERS.keys())}"
        )
    return SCHEMA_BUILDERS[ref]()


def schema_fingerprint(schema: SignalFrameSchemaV1) -> str:
    """Return sha256 fingerprint of schema (canonical JSON order)."""
    payload = {
        "strategy_id": schema.strategy_id,
        "strategy_tag": schema.strategy_tag,
        "version": schema.version,
        "columns": [asdict(c) for c in schema.all_columns()],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()
