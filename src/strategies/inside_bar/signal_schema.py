"""InsideBar strategy-owned SignalFrame schema (versioned SSOT).

All signal/indicator column definitions live here (not in pipeline/hooks/contracts).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Dict, List

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


SCHEMAS: Dict[str, SignalFrameSchemaV1] = {
    "1.0.0": _schema_v1_0_0(),
    "1.0.1": _schema_v1_0_0(),  # Same schema, only tunable params differ
    "1.0.2": _schema_v1_0_2(),  # OCO two-leg support (oco_group_id)
    "1.0.3": _schema_v1_0_2(),  # Same signal-frame contract as v1.0.2
}


def get_signal_frame_schema(strategy_version: str) -> SignalFrameSchemaV1:
    """Return schema for a given strategy_version or raise ValueError."""
    if strategy_version not in SCHEMAS:
        raise ValueError(
            f"Unknown insidebar schema version '{strategy_version}'. Available: {sorted(SCHEMAS.keys())}"
        )
    return SCHEMAS[strategy_version]


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
