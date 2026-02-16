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

    if "commission_bps" not in costs and "fees_bps" in costs:
        costs["commission_bps"] = costs["fees_bps"]
        if "costs.fees_bps" in sources:
            sources["costs.commission_bps"] = sources["costs.fees_bps"]

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

    return ResolveResult(resolved=resolved, sources=sources, unknown_keys=sorted(set(unknown_keys)))
