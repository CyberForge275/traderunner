"""Minimal tracing helper for UI backtest call-flow (opt-in via env)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def trace_ui(
    step: str,
    *,
    run_id: Optional[str] = None,
    strategy_id: Optional[str] = None,
    strategy_version: Optional[str] = None,
    file: Optional[str] = None,
    func: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Write a single trace line if AXIOM_TRACE_UI=1."""
    if os.getenv("AXIOM_TRACE_UI") != "1":
        return

    root = Path(__file__).resolve().parents[3]
    log_path = root / "docs" / "audits" / "ui_backtest_trace.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "step": step,
        "run_id": run_id,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "file": file,
        "func": func,
        "extra": extra or {},
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
