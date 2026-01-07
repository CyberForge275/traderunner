from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from pathlib import Path

import pandas as pd

from src.backtest.services.trade_evidence import generate_trade_evidence
from trading_dashboard.repositories.trade_repository import TradeRepository, RunArtifacts


@dataclass
class TradeDetail:
    run_id: str
    trade_id: int
    trade_row: pd.Series
    orders: Optional[pd.DataFrame]
    evidence_row: Optional[pd.Series]
    exec_bars: Optional[pd.DataFrame]
    signal_bars: Optional[pd.DataFrame]


class TradeDetailService:
    def __init__(self, repo: TradeRepository):
        self.repo = repo

    def _ensure_evidence(self, artifacts: RunArtifacts) -> Optional[pd.DataFrame]:
        if artifacts.evidence is not None:
            return artifacts.evidence
        # Best-effort generation if missing
        df = generate_trade_evidence(artifacts.run_dir)
        return df

    def get_trade_detail(self, run_id: str, trade_id: int, *, window_bars: int = 80) -> Optional[TradeDetail]:
        artifacts = self.repo.load_all(run_id)
        if artifacts.trades is None or trade_id >= len(artifacts.trades):
            return None

        evidence_df = self._ensure_evidence(artifacts)
        evidence_row = None
        if evidence_df is not None and trade_id < len(evidence_df):
            evidence_row = evidence_df.iloc[trade_id]

        trade_row = artifacts.trades.iloc[trade_id]
        exec_bars = artifacts.bars_exec
        if exec_bars is not None and not exec_bars.empty:
            entry_ts = pd.to_datetime(trade_row.get("entry_ts"), utc=True, errors="coerce")
            if entry_ts is not None and not pd.isna(entry_ts):
                exec_bars = exec_bars.sort_index()
                bars_idx = pd.to_datetime(exec_bars.index, utc=True, errors="coerce")
                # find index position nearest entry
                try:
                    pos = bars_idx.get_indexer([entry_ts], method="nearest")[0]
                    start = max(pos - window_bars // 2, 0)
                    end = min(pos + window_bars // 2, len(exec_bars))
                    exec_bars = exec_bars.iloc[start:end]
                except Exception:
                    pass

        return TradeDetail(
            run_id=run_id,
            trade_id=trade_id,
            trade_row=trade_row,
            orders=artifacts.orders,
            evidence_row=evidence_row,
            exec_bars=exec_bars,
            signal_bars=artifacts.bars_signal,
        )
