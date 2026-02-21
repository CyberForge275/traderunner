"""SSOT snapshot helpers for UI backtest callback."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore

logger = logging.getLogger(__name__)


class SnapshotValidationError(ValueError):
    """Raised when required strategy snapshot data is missing or invalid."""


def resolve_insidebar_snapshot(
    *,
    strategy_id: str,
    selected_version: Optional[str],
    snapshot: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a valid insidebar snapshot, loading defaults when needed."""
    if not selected_version:
        raise SnapshotValidationError(
            "Configuration snapshot missing. Please select Strategy and Version to load parameters first."
        )

    # Policy A: always load defaults fresh for the selected strategy version.
    defaults = StrategyConfigStore.get_defaults(strategy_id, selected_version)
    logger.info(
        "actions: ui_snapshot_defaults_loaded strategy_id=%s version=%s",
        strategy_id,
        selected_version,
    )
    return {
        "strategy_id": strategy_id,
        "version": selected_version,
        "required_warmup_bars": defaults.get("required_warmup_bars", 0),
        "core": defaults.get("core", {}),
        "tunable": defaults.get("tunable", {}),
        "strategy_finalized": defaults.get("strategy_finalized", False),
    }


def build_config_params_from_snapshot(
    *,
    strategy: str,
    version_to_use: str,
    snapshot: Optional[Dict[str, Any]],
    compound_toggle_val,
    equity_basis_val,
) -> Dict[str, Any]:
    """Build runner config params from SSOT snapshot (parity behavior)."""
    snapshot = snapshot or {}
    core = snapshot.get("core", {}) if isinstance(snapshot, dict) else {}
    tunable = snapshot.get("tunable", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(core, dict):
        core = {}
    if not isinstance(tunable, dict):
        tunable = {}

    config_params: Dict[str, Any] = {**core, **tunable}
    config_params["strategy_version"] = version_to_use

    compound_enabled = "enabled" in (compound_toggle_val or [])
    if compound_enabled:
        config_params["backtesting"] = {
            "compound_sizing": True,
            "compound_equity_basis": equity_basis_val or "cash_only",
        }
    return config_params
