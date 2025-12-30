from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


class ArtifactMissing(Exception):
    pass


@dataclass
class RunArtifacts:
    run_dir: Path
    trades: Optional[pd.DataFrame]
    orders: Optional[pd.DataFrame]
    evidence: Optional[pd.DataFrame]
    bars_exec: Optional[pd.DataFrame]
    bars_signal: Optional[pd.DataFrame]
    diagnostics: Optional[dict]


class TradeRepository:
    def __init__(self, artifacts_root: Path = Path("artifacts/backtests")):
        self.artifacts_root = artifacts_root

    def _run_dir(self, run_id: str) -> Path:
        return self.artifacts_root / run_id

    def load_trades(self, run_id: str) -> Optional[pd.DataFrame]:
        path = self._run_dir(run_id) / "trades.csv"
        if not path.exists():
            return None
        return pd.read_csv(path)

    def load_orders(self, run_id: str) -> Optional[pd.DataFrame]:
        path = self._run_dir(run_id) / "orders.csv"
        if not path.exists():
            return None
        return pd.read_csv(path)

    def load_evidence(self, run_id: str) -> Optional[pd.DataFrame]:
        path = self._run_dir(run_id) / "trade_evidence.csv"
        if not path.exists():
            return None
        return pd.read_csv(path)

    def load_diagnostics(self, run_id: str) -> Optional[dict]:
        path = self._run_dir(run_id) / "diagnostics.json"
        if not path.exists():
            return None
        import json
        return json.loads(path.read_text())

    def load_bars_exec(self, run_id: str) -> Optional[pd.DataFrame]:
        bars_dir = self._run_dir(run_id) / "bars"
        if not bars_dir.exists():
            return None
        for path in sorted(bars_dir.glob("bars_exec_*_rth.parquet")):
            try:
                return pd.read_parquet(path)
            except Exception:
                continue
        return None

    def load_bars_signal(self, run_id: str) -> Optional[pd.DataFrame]:
        bars_dir = self._run_dir(run_id) / "bars"
        if not bars_dir.exists():
            return None
        for path in sorted(bars_dir.glob("bars_signal_*_rth.parquet")):
            try:
                return pd.read_parquet(path)
            except Exception:
                continue
        return None

    def load_all(self, run_id: str) -> RunArtifacts:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            raise ArtifactMissing(f"run_dir not found: {run_dir}")
        return RunArtifacts(
            run_dir=run_dir,
            trades=self.load_trades(run_id),
            orders=self.load_orders(run_id),
            evidence=self.load_evidence(run_id),
            bars_exec=self.load_bars_exec(run_id),
            bars_signal=self.load_bars_signal(run_id),
            diagnostics=self.load_diagnostics(run_id),
        )
