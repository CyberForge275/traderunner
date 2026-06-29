"""Strategy-specific debug artifact helpers (skeleton)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .warnings import BacktestValidity


@dataclass(frozen=True)
class DebugArtifacts:
    monthly_ranking_snapshots: pd.DataFrame
    regime_series: pd.DataFrame
    warnings: list[dict[str, str]]
    validity: BacktestValidity


def build_empty_debug_artifacts(validity: BacktestValidity) -> DebugArtifacts:
    return DebugArtifacts(
        monthly_ranking_snapshots=pd.DataFrame(),
        regime_series=pd.DataFrame(),
        warnings=[],
        validity=validity,
    )
