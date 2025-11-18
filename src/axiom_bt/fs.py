from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict

ROOT = Path(".")
ART = ROOT / "artifacts"
BACKTESTS = ART / "backtests"
DATA = ART / "data"
DATA_M1 = ART / "data_m1"
DATA_M5 = ART / "data_m5"
DATA_M15 = ART / "data_m15"
DATA_D1 = ART / "data_d1"
UNIVERSE = ART / "universe"
LOGS = ART / "logs"


def ensure_layout() -> Dict[str, str]:
    for directory in [ART, BACKTESTS, DATA, DATA_M1, DATA_M5, DATA_M15, DATA_D1, UNIVERSE, LOGS]:
        directory.mkdir(parents=True, exist_ok=True)
    return {"artifacts": str(ART), "backtests": str(BACKTESTS)}


def new_run_dir(name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c for c in name if c.isalnum() or c in ("_", "-")) or "run"
    run_dir = BACKTESTS / f"run_{timestamp}_{safe}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
