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
    
    def is_in_session(self, timestamp: pd.Timestamp, tz: str = "UTC") -> bool:
        """Check if timestamp falls within any session window (timezone-aware).
        
        Args:
            timestamp: Timestamp to check
            tz: Target timezone for session check (e.g., "Europe/Berlin")
            
        Returns:
            True if timestamp is within any session window,
            True if no windows defined (no filtering),
            False otherwise
        """
        if not self.windows:
            return True  # No filter = all times valid
        
        # Convert to target timezone
        if timestamp.tz is None:
            ts_tz = timestamp.tz_localize("UTC").tz_convert(tz)
        else:
            ts_tz = timestamp.tz_convert(tz)
        
        t = ts_tz.time()
        for start, end in self.windows:
            if start <= t < end:
                return True
        return False
    
    def get_session_index(self, timestamp: pd.Timestamp, tz: str = "UTC") -> Optional[int]:
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
    
    def get_session_end(self, timestamp: pd.Timestamp, tz: str = "UTC") -> Optional[pd.Timestamp]:
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
    
    def get_session_start(self, timestamp: pd.Timestamp, tz: str = "UTC") -> Optional[pd.Timestamp]:
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
    order_validity_policy: str = "session_end"  # or "fixed_minutes" | "instant"
    order_validity_minutes: int = 60  # Only for fixed_minutes policy
    valid_from_policy: str = "signal_ts"  # or "next_bar"
    
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
        assert self.atr_period > 0, "ATR period must be positive"
        assert self.risk_reward_ratio > 0, "Risk/reward ratio must be positive"
        assert self.min_mother_bar_size >= 0, "Min mother size must be non-negative"
        assert self.inside_bar_mode in ["inclusive", "strict"], \
            f"Invalid mode: {self.inside_bar_mode}"
        assert self.entry_level_mode in ["mother_bar", "inside_bar"], \
            f"Invalid entry_level_mode: {self.entry_level_mode}"
        assert self.order_validity_policy in ["session_end", "fixed_minutes", "instant"], \
            f"Invalid order_validity_policy: {self.order_validity_policy}"
        assert self.valid_from_policy in ["signal_ts", "next_bar"], \
            f"Invalid valid_from_policy: {self.valid_from_policy}"
        assert self.max_trades_per_session > 0, "Max trades per session must be positive"
        assert self.stop_distance_cap_ticks > 0, "SL cap ticks must be positive"
        assert self.tick_size > 0, "Tick size must be positive"
        assert 0.0 <= self.trailing_trigger_tp_pct <= 1.0, "Trailing trigger must be in [0, 1]"
        assert 0.0 <= self.trailing_risk_remaining_pct <= 1.0, "Trailing risk pct must be in [0, 1]"
    
    def __post_init__(self):
        """Auto-validate after initialization."""
        self.validate()


def load_config(config_path: Path):
    """
    Load configuration from YAML file.
    
    NOTE: Returns dict instead of InsideBarConfig to avoid circular import.
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
    
    # Create and validate config
    config = InsideBarConfig(**params)
    return config


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
