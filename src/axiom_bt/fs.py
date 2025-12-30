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
    import re

    # Check if name already starts with a timestamp pattern (YYMMDD_HHMMSS)
    # Example: "251208_114207_new13" should not get another timestamp prefix
    timestamp_pattern = re.compile(r'^\d{6}_\d{6}')
    safe = "".join(c for c in name if c.isalnum() or c in ("_", "-")) or "run"

    if timestamp_pattern.match(safe):
        # Name already has timestamp, use it as-is with just "run_" prefix
        run_dir = BACKTESTS / f"run_{safe}"
    else:
        # Name doesn't have timestamp, add one
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = BACKTESTS / f"run_{timestamp}_{safe}"

    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
