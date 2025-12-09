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
    
    def is_in_session(self, timestamp: pd.Timestamp) -> bool:
        """Check if timestamp falls within any session window.
        
        Args:
            timestamp: Timestamp to check
            
        Returns:
            True if timestamp is within any session window,
            True if no windows defined (no filtering),
            False otherwise
        """
        if not self.windows:
            return True  # No filter = all times valid
        
        t = timestamp.time()
        for start, end in self.windows:
            if start <= t < end:
                return True
        return False


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
