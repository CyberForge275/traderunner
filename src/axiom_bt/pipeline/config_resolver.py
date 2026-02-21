"""Backtest config resolver (SSOT for effective params and sources)."""

from __future__ import annotations

from dataclasses import dataclass
import copy
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass(frozen=True)
class ResolveResult:
    resolved: Dict[str, Any]
    sources: Dict[str, str]
    unknown_keys: List[str]


def load_base_config(path: str | Path) -> Dict[str, Any]:
    """Load base config from JSON or YAML file."""
    p = Path(path)
    text = p.read_text()
    if p.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    return data or {}


def resolve_config(
    base: Dict[str, Any] | None,
    overrides: Dict[str, Dict[str, Any]] | None,
    defaults: Dict[str, Any] | None,
) -> ResolveResult:
    """Resolve effective config using deterministic precedence."""
    resolved = copy.deepcopy(defaults or {})
    sources: Dict[str, str] = {}
    unknown_keys: List[str] = []

    def _flatten_paths(d: Dict[str, Any], prefix: str = "") -> List[str]:
        out: List[str] = []
        for key, value in d.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                out.extend(_flatten_paths(value, path))
            else:
                out.append(path)
        return out

    def _assign(path: str, value: Any, source: str) -> None:
        keys = path.split(".")
        cursor = resolved
        for key in keys[:-1]:
            current = cursor.get(key)
            if not isinstance(current, dict):
                cursor[key] = {}
            cursor = cursor[key]
        cursor[keys[-1]] = value
        sources[path] = source

    def _apply_patch(patch: Dict[str, Any], source: str, prefix: str = "") -> None:
        for key, value in patch.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                _apply_patch(value, source, path)
            else:
                _assign(path, value, source)

    for path in _flatten_paths(resolved):
        sources[path] = "default"

    precedence: List[tuple[str, Dict[str, Any] | None]] = [
        ("base", base),
        ("ui", (overrides or {}).get("ui")),
        ("cli", (overrides or {}).get("cli")),
        ("spyder", (overrides or {}).get("spyder")),
    ]
    for source, patch in precedence:
        if patch:
            _apply_patch(patch, source)

    costs = resolved.get("costs")
    if not isinstance(costs, dict):
        costs = {}
        resolved["costs"] = costs
        sources["costs"] = "default"

    if "fees_bps" in costs:
        commission_source = sources.get("costs.commission_bps")
        fees_source = sources.get("costs.fees_bps")
        if "commission_bps" not in costs or commission_source == "default":
            costs["commission_bps"] = costs["fees_bps"]
            if fees_source:
                sources["costs.commission_bps"] = fees_source

    if "commission_bps" in costs:
        costs["fees_bps"] = costs["commission_bps"]
        sources["costs.fees_bps"] = "derived"

    for key in ("commission_bps", "slippage_bps"):
        if key in costs:
            try:
                value = float(costs[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid costs.{key}: {costs[key]!r}") from exc
            if value < 0:
                raise ValueError(f"costs.{key} must be >= 0")
            costs[key] = value

    allowed_costs = {
        "commission_bps",
        "fees_bps",
        "slippage_bps",
        "price_semantics",
        "price_source",
    }
    for key in costs.keys():
        if key not in allowed_costs:
            unknown_keys.append(f"costs.{key}")

    execution = resolved.get("execution")
    if execution is None:
        execution = {}
        resolved["execution"] = execution
        sources["execution"] = "default"
    if not isinstance(execution, dict):
        raise ValueError("execution must be a mapping")

    mode = execution.get("same_bar_resolution_mode")
    if mode is not None:
        allowed_modes = {"legacy", "no_fill", "m1_probe_then_no_fill"}
        if str(mode) not in allowed_modes:
            raise ValueError(
                f"invalid execution.same_bar_resolution_mode: {mode!r} "
                f"(allowed: {sorted(allowed_modes)})"
            )
        execution["same_bar_resolution_mode"] = str(mode)

    probe_tf = execution.get("intrabar_probe_timeframe")
    if probe_tf is not None:
        if str(probe_tf).upper() != "M1":
            raise ValueError(
                f"invalid execution.intrabar_probe_timeframe: {probe_tf!r} (allowed: 'M1')"
            )
        execution["intrabar_probe_timeframe"] = "M1"

    allowed_execution = {
        "allow_same_bar_exit",
        "same_bar_resolution_mode",
        "intrabar_probe_timeframe",
        "intrabar_probe_enabled",
    }
    for key in execution.keys():
        if key not in allowed_execution:
            unknown_keys.append(f"execution.{key}")

    return ResolveResult(resolved=resolved, sources=sources, unknown_keys=sorted(set(unknown_keys)))
