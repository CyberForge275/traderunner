from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import yaml
import re
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._-]+$")

from core.settings import (
    DEFAULT_INITIAL_CASH,
    DEFAULT_RISK_PCT,
    INSIDE_BAR_DEFAULTS,
    INSIDE_BAR_SESSIONS,
    INSIDE_BAR_TIMEZONE,
)


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class FetchConfig:
    symbols: List[str]
    timeframe: str
    start: Optional[str]
    end: Optional[str]
    use_sample: bool
    force_refresh: bool
    data_dir: Path
    data_dir_m1: Path
    _needs_force: bool = field(default=False, init=False, repr=False)

    def symbols_to_fetch(self) -> List[str]:
        if self.force_refresh:
            self._needs_force = True
            return list(self.symbols)

        self._needs_force = False
        pending: List[str] = []
        for symbol in self.symbols:
            status = self._coverage_status(symbol)
            if status in {"missing", "stale"}:
                pending.append(symbol)
                if status == "stale":
                    self._needs_force = True
        return pending

    def needs_force_refresh(self) -> bool:
        return self._needs_force

    def _coverage_status(self, symbol: str) -> str:
        primary = self.data_dir_m1 / f"{symbol}.parquet"
        path = primary if primary.exists() else self.data_dir / f"{symbol}.parquet"
        if not path.exists():
            return "missing"
        if not self.start and not self.end:
            return "ok"
        try:
            index = pd.read_parquet(path, columns=["Close"]).index
        except Exception:
            return "stale"
        if index.empty:
            return "stale"

        min_date = index.min().date()
        max_date = index.max().date()
        if self.start and min_date > pd.Timestamp(self.start).date():
            return "stale"
        if self.end and max_date < pd.Timestamp(self.end).date():
            return "stale"
        return "ok"


@dataclass
class StrategyMetadata:
    name: str
    label: str
    timezone: str
    sessions: List[str]
    signal_module: str
    orders_source: Path
    default_payload: Dict
    default_sizing: Optional[Dict] = None


INSIDE_BAR_METADATA = StrategyMetadata(
    name=INSIDE_BAR_DEFAULTS.name,
    label="Inside Bar Intraday",
    timezone=INSIDE_BAR_DEFAULTS.timezone,
    sessions=INSIDE_BAR_DEFAULTS.sessions,
    signal_module="signals.cli_inside_bar",
    orders_source=ROOT / "artifacts" / "signals" / "current_signals_ib.csv",
    default_payload={
        "engine": "replay",
        "mode": INSIDE_BAR_DEFAULTS.name,
        "data": {"tz": INSIDE_BAR_TIMEZONE},
        "costs": INSIDE_BAR_DEFAULTS.costs,
        "initial_cash": INSIDE_BAR_DEFAULTS.initial_cash,
    },
    default_sizing={
        "mode": "risk",
        "risk_pct": INSIDE_BAR_DEFAULTS.risk_pct,
        "min_qty": INSIDE_BAR_DEFAULTS.min_qty,
    },
)


STRATEGY_REGISTRY: Dict[str, StrategyMetadata] = {
    INSIDE_BAR_METADATA.name: INSIDE_BAR_METADATA,
}

STRATEGY_DOCS: Dict[str, Path] = {
    INSIDE_BAR_METADATA.name: ROOT / "docs" / "inside_bar_strategy.pdf",
}


@dataclass
class PipelineConfig:
    run_name: str
    fetch: FetchConfig
    symbols: List[str]
    strategy: StrategyMetadata
    config_path: Optional[str]
    config_payload: Optional[Dict]


def collect_symbols(selection: Iterable[str], free_text: str) -> Tuple[List[str], List[str]]:
    symbols = {sym.strip().upper() for sym in selection if sym}
    if free_text:
        tokens = [token.strip().upper() for token in free_text.replace("\n", ",").split(",") if token.strip()]
        symbols.update(tokens)

    errors: List[str] = []
    valid_symbols = sorted(sym for sym in symbols if sym)
    invalid = [sym for sym in valid_symbols if not SYMBOL_PATTERN.fullmatch(sym)]
    if invalid:
        errors.append(f"Invalid symbol format: {', '.join(invalid)}")
    valid_symbols = [sym for sym in valid_symbols if sym not in invalid]
    if not valid_symbols:
        errors.append("Select or enter at least one valid symbol.")
    return valid_symbols, errors


def validate_date_range(start: Optional[str], end: Optional[str]) -> List[str]:
    errors: List[str] = []
    if start and end:
        try:
            start_ts = pd.Timestamp(start)
            end_ts = pd.Timestamp(end)
            if start_ts > end_ts:
                errors.append(f"Date range invalid: start {start} is after end {end}.")
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Invalid date range ({start} → {end}): {exc}")
    return errors


def parse_yaml_config(path_str: str) -> Tuple[Optional[str], Optional[Dict], List[str]]:
    errors: List[str] = []
    payload: Optional[Dict] = None
    if not path_str:
        errors.append("Provide a YAML config path.")
        return None, None, errors

    path = Path(path_str)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        errors.append(f"Config file not found: {path}")
        return str(path), None, errors

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.append(f"Failed to parse YAML: {exc}")
        return str(path), None, errors

    if not isinstance(raw, dict):
        errors.append("YAML root must be a mapping of parameters.")
    else:
        payload = raw

    return str(path), payload, errors
