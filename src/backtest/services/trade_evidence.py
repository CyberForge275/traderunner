"""Trade evidence generation utilities.

Provides deterministic, audit-friendly evidence for trades using run-local
artifacts. This module is pure business logic (no Dash/Plotly) and can be
used both from the backtest runner and the Trade Inspector service.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


class EvidenceFlag(str, Enum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class ProofStatus(str, Enum):
    PROVEN = "PROVEN"
    PARTIAL = "PARTIAL"
    NO_PROOF = "NO_PROOF"


@dataclass
class TradeEvidence:
    trade_id: int
    entry_exec_proven: EvidenceFlag
    exit_exec_proven: EvidenceFlag
    order_validity_holds: EvidenceFlag
    signal_recalc_match: EvidenceFlag
    rth_compliant: EvidenceFlag
    data_slice_integrity: str
    proof_status: ProofStatus
    fail_reasons: List[str]
    proving_bar_ts_entry: Optional[pd.Timestamp]
    proving_bar_ts_exit: Optional[pd.Timestamp]


def _is_rth(ts: pd.Timestamp) -> bool:
    if ts is None or not isinstance(ts, pd.Timestamp):
        return False
    ts_local = ts.tz_convert(ts.tzname() or "America/New_York") if ts.tzinfo else ts
    hhmm = ts_local.hour * 60 + ts_local.minute
    return 9 * 60 + 30 <= hhmm <= 16 * 60


def _load_exec_bars(run_dir: Path) -> Optional[pd.DataFrame]:
    bars_dir = run_dir / "bars"
    if not bars_dir.exists():
        return None
    for path in sorted(bars_dir.glob("bars_exec_*_rth.parquet")):
        try:
            df = pd.read_parquet(path)
            return df
        except Exception:
            continue
    return None


def _proof_entry_exit(trade_row: pd.Series, bars: pd.DataFrame) -> Dict[str, object]:
    entry_ts = pd.to_datetime(trade_row.get("entry_ts"), utc=True, errors="coerce")
    exit_ts = pd.to_datetime(trade_row.get("exit_ts"), utc=True, errors="coerce")
    side = str(trade_row.get("side", "")).upper()
    entry_price = float(trade_row.get("entry_price", float("nan")))
    exit_price = float(trade_row.get("exit_price", float("nan")))

    entry_ok = EvidenceFlag.UNKNOWN
    exit_ok = EvidenceFlag.UNKNOWN
    entry_bar_ts = None
    exit_bar_ts = None

    if bars is not None and not bars.empty:
        bars_idx = pd.to_datetime(bars.index, utc=True, errors="coerce")
        if entry_ts is not None and not pd.isna(entry_ts):
            pos = bars_idx.searchsorted(entry_ts, side="right") - 1
            if pos >= 0:
                bar = bars.iloc[pos]
                if bar["low"] <= entry_price <= bar["high"]:
                    entry_ok = EvidenceFlag.YES
                    entry_bar_ts = bars_idx[pos]
                else:
                    entry_ok = EvidenceFlag.NO
        if exit_ts is not None and not pd.isna(exit_ts):
            pos = bars_idx.searchsorted(exit_ts, side="right") - 1
            if pos >= 0:
                bar = bars.iloc[pos]
                if bar["low"] <= exit_price <= bar["high"]:
                    exit_ok = EvidenceFlag.YES
                    exit_bar_ts = bars_idx[pos]
                else:
                    exit_ok = EvidenceFlag.NO

    return {
        "entry_ok": entry_ok,
        "exit_ok": exit_ok,
        "entry_bar_ts": entry_bar_ts,
        "exit_bar_ts": exit_bar_ts,
    }


def generate_trade_evidence(run_dir: Path) -> Optional[pd.DataFrame]:
    """Generate trade evidence for a run directory.

    Returns a DataFrame (also written to trade_evidence.csv) or None if
    required inputs are missing.
    """

    trades_path = run_dir / "trades.csv"
    if not trades_path.exists():
        return None

    try:
        trades = pd.read_csv(trades_path)
    except Exception:
        return None

    bars = _load_exec_bars(run_dir)
    has_bars = bars is not None and not bars.empty

    records: List[Dict[str, object]] = []
    for idx, row in trades.iterrows():
        proof = _proof_entry_exit(row, bars) if has_bars else {
            "entry_ok": EvidenceFlag.UNKNOWN,
            "exit_ok": EvidenceFlag.UNKNOWN,
            "entry_bar_ts": None,
            "exit_bar_ts": None,
        }

        rth_flag = EvidenceFlag.UNKNOWN
        if has_bars and proof["entry_bar_ts"] is not None and proof["exit_bar_ts"] is not None:
            rth_flag = EvidenceFlag.YES if _is_rth(proof["entry_bar_ts"]) and _is_rth(proof["exit_bar_ts"]) else EvidenceFlag.NO

        data_integrity = "OK" if has_bars else "MISSING_BARS"
        if data_integrity != "OK":
            proof_status = ProofStatus.NO_PROOF
            fail_reasons = ["missing_exec_bars"]
        else:
            fail_reasons = []
            proof_status = ProofStatus.PROVEN if proof["entry_ok"] == EvidenceFlag.YES and proof["exit_ok"] == EvidenceFlag.YES else ProofStatus.PARTIAL
            if proof_status != ProofStatus.PROVEN:
                fail_reasons.append("entry_exit_not_proven")

        record = {
            "trade_id": idx,
            "entry_exec_proven": proof["entry_ok"].value if isinstance(proof["entry_ok"], EvidenceFlag) else str(proof["entry_ok"]),
            "exit_exec_proven": proof["exit_ok"].value if isinstance(proof["exit_ok"], EvidenceFlag) else str(proof["exit_ok"]),
            "order_validity_holds": EvidenceFlag.UNKNOWN.value,
            "signal_recalc_match": EvidenceFlag.UNKNOWN.value,
            "rth_compliant": rth_flag.value if isinstance(rth_flag, EvidenceFlag) else str(rth_flag),
            "data_slice_integrity": data_integrity,
            "proof_status": proof_status.value if isinstance(proof_status, ProofStatus) else str(proof_status),
            "fail_reasons": ";".join(fail_reasons),
            "proving_bar_ts_entry": proof["entry_bar_ts"].isoformat() if isinstance(proof["entry_bar_ts"], pd.Timestamp) else None,
            "proving_bar_ts_exit": proof["exit_bar_ts"].isoformat() if isinstance(proof["exit_bar_ts"], pd.Timestamp) else None,
        }
        records.append(record)

    df = pd.DataFrame(records)
    out_path = run_dir / "trade_evidence.csv"
    df.to_csv(out_path, index=False)
    return df
