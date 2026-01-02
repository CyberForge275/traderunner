"""
Validated configuration for InsideBar strategy.

This config is used by BOTH backtest and live trading.
"""
from __future__ import annotations

import yaml
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import time

import pandas as pd


@dataclass
class SessionFilter:
    """Session time windows for signal filtering.

    Allows filtering signals to only those generated within specific
    time windows (e.g., 15:00-17:00 CET trading hours).
    """
    windows: List[Tuple[time, time]] = field(default_factory=list)

    @classmethod
    def from_strings(cls, session_strings: List[str]) -> "SessionFilter":
        """Parse session strings like ['15:00-16:00', '16:00-17:00'].

        Args:
            session_strings: List of time range strings in format "HH:MM-HH:MM"

        Returns:
            SessionFilter instance with parsed time windows

        Example:
            >>> sf = SessionFilter.from_strings(["15:00-16:00", "16:00-17:00"])
            >>> len(sf.windows)
            2
        """
        windows = []
        for s in session_strings:
            start_str, end_str = s.strip().split("-")
            h1, m1 = map(int, start_str.split(":"))
            h2, m2 = map(int, end_str.split(":"))
            windows.append((time(h1, m1), time(h2, m2)))
        return cls(windows=windows)

    def to_strings(self) -> List[str]:
        """Convert SessionFilter back to list of strings for YAML serialization.

        Returns:
            List of time range strings in format "HH:MM-HH:MM"

        Example:
            >>> sf = SessionFilter.from_strings(["15:00-16:00"])
            >>> sf.to_strings()
            ['15:00-16:00']
        """
        result = []
        for start, end in self.windows:
            start_str = f"{start.hour:02d}:{start.minute:02d}"
            end_str = f"{end.hour:02d}:{end.minute:02d}"
            result.append(f"{start_str}-{end_str}")
        return result

    def is_in_session(self, timestamp: pd.Timestamp, tz: str = "Europe/Berlin") -> bool:
        """Check if timestamp falls within any session window (timezone-aware).

        Args:
            timestamp: Timestamp to check (tz-aware or naive)
            tz: Target timezone for session check (default: Europe/Berlin)

        Returns:
            True if timestamp is within any session window,
            False otherwise

        Note:
            CRITICAL FIX: Naive timestamps are assumed to be UTC (EODHD convention).
            Always converts to target timezone before extracting time to prevent
            checking UTC time against timezone-specific windows.
        """
        if not self.windows:
            return False  # No windows = reject all (ALWAYS ON enforcement)

        # CRITICAL FIX: Handle naive timestamps
        # EODHD intraday data comes as naive timestamps in UTC
        if timestamp.tz is None:
            timestamp = timestamp.tz_localize("UTC")

        # CRITICAL: Always convert to target timezone before extracting time
        # This prevents checking UTC time (14:15) against NY windows (14:00-15:00)
        # Example: 14:15 UTC → 09:15 EST (correctly rejected for 10:00-11:00 window)
        ts_tz = timestamp.tz_convert(tz)

        # Extract local time and check windows
        t = ts_tz.time()
        for start, end in self.windows:
            if start <= t < end:
                return True

        return False

    def get_session_index(self, timestamp: pd.Timestamp, tz: str = "Europe/Berlin") -> Optional[int]:
        """Return session index (0, 1, ...) or None if outside all sessions.

        Args:
            timestamp: Timestamp to check
            tz: Target timezone for session check

        Returns:
            Session index or None
        """
        if not self.windows:
            return None

        # Convert to target timezone
        if timestamp.tz is None:
            ts_tz = timestamp.tz_localize("UTC").tz_convert(tz)
        else:
            ts_tz = timestamp.tz_convert(tz)

        t = ts_tz.time()
        for idx, (start, end) in enumerate(self.windows):
            if start <= t < end:
                return idx
        return None

    def get_session_end(self, timestamp: pd.Timestamp, tz: str = "Europe/Berlin") -> Optional[pd.Timestamp]:
        """Return session end timestamp or None if outside sessions.

        Args:
            timestamp: Timestamp to check
            tz: Target timezone for session check

        Returns:
            End timestamp of current session or None
        """
        if not self.windows:
            return None

        # Convert to target timezone
        if timestamp.tz is None:
            ts_tz = timestamp.tz_localize("UTC").tz_convert(tz)
        else:
            ts_tz = timestamp.tz_convert(tz)

        t = ts_tz.time()
        for start, end in self.windows:
            if start <= t < end:
                # Construct end timestamp on same date
                return ts_tz.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
        return None

    def get_session_start(self, timestamp: pd.Timestamp, tz: str = "Europe/Berlin") -> Optional[pd.Timestamp]:
        """Return session start timestamp or None if outside sessions.

        Args:
            timestamp: Timestamp to check
            tz: Target timezone for session check

        Returns:
            Start timestamp of current session or None
        """
        if not self.windows:
            return None

        # Convert to target timezone
        if timestamp.tz is None:
            ts_tz = timestamp.tz_localize("UTC").tz_convert(tz)
        else:
            ts_tz = timestamp.tz_convert(tz)

        t = ts_tz.time()
        for start, end in self.windows:
            if start <= t < end:
                return ts_tz.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
        return None


@dataclass
class InsideBarConfig:
    """InsideBar strategy configuration with spec-compliant defaults.

    This configuration implements the Inside Bar Strategy 1.0.0 spec with
    November-proven defaults (Europe/Berlin sessions, session-end validity).
    """
    # === Core Parameters ===
    atr_period: int = 14
    risk_reward_ratio: float = 2.0
    min_mother_bar_size: float = 0.5
    breakout_confirmation: bool = True
    inside_bar_mode: str = "inclusive"  # or "strict"

    # === Session & Timezone (ALWAYS ON) ===
    session_timezone: str = "Europe/Berlin"
    session_windows: List[str] = field(
        default_factory=lambda: ["15:00-16:00", "16:00-17:00"]
    )
    max_trades_per_session: int = 1

    # === Entry & Exit ===
    entry_level_mode: str = "mother_bar"  # or "inside_bar"
    stop_distance_cap_ticks: int = 40
    tick_size: float = 0.01

    # === Order Validity (Critical for Replay Fills) ===
    order_validity_policy: str = "session_end"
    """Order validity policy. Determines when orders expire.
    
    Options:
    - "one_bar": Expires after 1 bar (uses timeframe_minutes, IGNORES order_validity_minutes)
    - "fixed_minutes": Expires after N minutes (uses order_validity_minutes, IGNORES timeframe)
    - "session_end": Expires at session close (uses session_filter, IGNORES both)
    
    Each policy uses EXCLUSIVE parameters - no combination/fallback.
    """
    
    order_validity_minutes: int = 60
    """Duration in minutes for 'fixed_minutes' policy.
    
    IMPORTANT: This parameter is ONLY used when order_validity_policy="fixed_minutes".
    It is IGNORED when policy is "one_bar" or "session_end".
    
    Example:
        policy="one_bar" + validity_minutes=60 → order expires after 5 min (M5 timeframe)
        policy="fixed_minutes" + validity_minutes=60 → order expires after 60 min
    """
    
    valid_from_policy: str = "signal_ts"  # or "next_bar"

    # === MVP: Trigger and Netting Rules ===
    trigger_must_be_within_session: bool = True
    """Enforce trigger (breakout) must occur within session windows.
    
    When True (default): Breakout/trigger timestamp must be within session windows.
    Signal generation does NOT guarantee trigger timing - this is an additional gate.
    
    When False: Allows triggers outside session (legacy behavior, not recommended).
    """
    
    netting_mode: str = "one_position_per_symbol"
    """Position netting policy.
    
    MVP: Only "one_position_per_symbol" is supported.
    While a position is open for a symbol, no additional positions can be opened.
    
    Future: "hedging" or "pyramiding" could be added.
    """

    # === Trailing Stop (Optional) ===
    trailing_enabled: bool = False
    trailing_trigger_tp_pct: float = 0.70
    trailing_risk_remaining_pct: float = 0.50
    trailing_apply_mode: str = "next_bar"

    # === Live-specific Parameters ===
    lookback_candles: int = 50
    max_pattern_age_candles: int = 12
    max_deviation_atr: float = 3.0

    @property
    def session_filter(self) -> SessionFilter:
        """Build SessionFilter from config (always instantiated)."""
        return SessionFilter.from_strings(self.session_windows)

    def validate(self) -> None:
        """Validate configuration parameters."""
        # Core parameters
        assert self.atr_period > 0, "ATR period must be positive"
        assert self.risk_reward_ratio > 0, "Risk/reward ratio must be positive"
        assert self.min_mother_bar_size >= 0, "Min mother size must be non-negative"
        assert self.inside_bar_mode in ["inclusive", "strict"], \
            f"Invalid mode: {self.inside_bar_mode}"

        # Session enforcement (ALWAYS ON)
        assert len(self.session_windows) > 0, \
            "session_windows cannot be empty - sessions are ALWAYS ON"

        # Validate session window format
        for window in self.session_windows:
            try:
                start_str, end_str = window.strip().split("-")
                h1, m1 = map(int, start_str.split(":"))
                h2, m2 = map(int, end_str.split(":"))
                assert 0 <= h1 < 24 and 0 <= m1 < 60, f"Invalid start time in: {window}"
                assert 0 <= h2 < 24 and 0 <= m2 < 60, f"Invalid end time in: {window}"
                start_time = h1 * 60 + m1
                end_time = h2 * 60 + m2
                assert start_time < end_time, f"Start must be before end in: {window}"
            except Exception as e:
                raise ValueError(f"Invalid session window '{window}': {e}")

        # Entry and exit
        assert self.entry_level_mode in ["mother_bar", "inside_bar"], \
            f"Invalid entry_level_mode: {self.entry_level_mode}"
        assert self.max_trades_per_session > 0, "Max trades per session must be positive"
        assert self.stop_distance_cap_ticks > 0, "SL cap ticks must be positive"
        assert self.tick_size > 0, "Tick size must be positive"

        # Order validity
        assert self.order_validity_policy in ["session_end", "fixed_minutes", "one_bar"], \
            f"Invalid order_validity_policy: {self.order_validity_policy} " \
            "('instant' removed - use 'one_bar' for single-bar validity)"
        assert self.valid_from_policy in ["signal_ts", "next_bar"], \
            f"Invalid valid_from_policy: {self.valid_from_policy}"
        if self.order_validity_policy == "fixed_minutes":
            assert self.order_validity_minutes > 0, "order_validity_minutes must be positive"
        
        # MVP: Trigger and netting validations
        assert isinstance(self.trigger_must_be_within_session, bool), \
            "trigger_must_be_within_session must be bool"
        assert self.netting_mode == "one_position_per_symbol", \
            f"Invalid netting_mode: {self.netting_mode}. Only 'one_position_per_symbol' supported in MVP"
        
        # Warn if order_validity_minutes is set but will be ignored
        if self.order_validity_policy == "one_bar" and self.order_validity_minutes != 60:
            import logging
            logging.getLogger(__name__).warning(
                f"order_validity_minutes={self.order_validity_minutes} will be IGNORED "
                f"with policy='one_bar'. Orders will expire after 1 bar (timeframe duration)."
            )

        # Trailing stop
        assert self.trailing_apply_mode in ["next_bar"], \
            f"Invalid trailing_apply_mode: {self.trailing_apply_mode} (only 'next_bar' supported)"
        assert 0.0 <= self.trailing_trigger_tp_pct <= 1.0, "Trailing trigger must be in [0, 1]"
        assert 0.0 <= self.trailing_risk_remaining_pct <= 1.0, "Trailing risk pct must be in [0, 1]"

    def __post_init__(self):
        """Auto-validate after initialization."""
        self.validate()


def load_config(config_path: Path) -> dict:
    """
    Load configuration from YAML file.

    NOTE: Returns dict, not InsideBarConfig, to avoid circular imports.
    Use InsideBarConfig(**load_config(path)) to create config object.

    Args:
        config_path: Path to YAML config file

    Returns:
        InsideBarConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty config file: {config_path}")

    params = data.get('parameters', {})
    return params


def get_default_config_path() -> Path:
    """
    Get path to default config file.

    Searches in order:
    1. ~/data/workspace/droid/traderunner/config/inside_bar.yaml
    2. /opt/trading/traderunner/config/inside_bar.yaml
    3. ~/.trading/config/inside_bar.yaml

    Returns:
        Path to first config file found

    Raises:
        FileNotFoundError: If no config file found
    """
    candidates = [
        Path.home() / 'data' / 'workspace' / 'droid' / 'traderunner' / 'config' / 'inside_bar.yaml',
        Path('/opt/trading/traderunner/config/inside_bar.yaml'),
        Path.home() / '.trading' / 'config' / 'inside_bar.yaml',
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"Config file not found. Searched in:\n" +
        "\n".join(f"  - {p}" for p in candidates)
    )


def load_default_config() -> dict:
    """
    Load config from default location.

    Returns:
        Dict of configuration parameters
    """
    config_path = get_default_config_path()
    return load_config(config_path)
