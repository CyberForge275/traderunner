"""OHLCV Provider Contract - Protocol and request/response data classes.

This module defines the contract for OHLCV data providers with strict warmup validation:
- Full-Load (start=None, end=None) MUST have warmup_bars=None
- Window-Load (start/end set) MUST have explicit warmup_bars (0 allowed)
- Partial windows (only start OR end) are forbidden
- warmup_bars < 0 is forbidden

This ensures the UI layer cannot accidentally "guess" warmup values, which must
be determined by the Strategy/Runner layer only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, Tuple, List
import pandas as pd


@dataclass
class OhlcvRequest:
    """Request for OHLCV data with warmup validation.
    
    Attributes:
        symbol: Stock symbol (e.g., "PLTR")
        timeframe: Timeframe (M1/M5/M15/H1/D1)
        tz: Timezone for output (default: None = provider default)
        start: Optional window start (must be set with end)
        end: Optional window end (must be set with start)
        warmup_bars: Warmup bar count (MUST be None for Full-Load, explicit for Window-Load)
        session_mode: Session filter mode (None = provider default)
        allow_partial: Allow partial data (default: False)
    """
    symbol: str
    timeframe: str
    tz: Optional[str] = None
    
    # Optional window
    start: Optional[pd.Timestamp] = None
    end: Optional[pd.Timestamp] = None
    
    # Warmup validation (CRITICAL)
    warmup_bars: Optional[int] = None
    
    # Other params
    session_mode: Optional[str] = None  # None = use provider default (axiom_bt uses "rth")
    allow_partial: bool = False
    
    def validate(self) -> None:
        """Enforce warmup rules.
        
        Raises:
            ValueError: If validation fails
        """
        # Helper: Ensure timestamp is pandas-coercible
        def _ensure_timestamp(val, name: str):
            if val is None:
                return
            try:
                pd.Timestamp(val)
            except Exception as e:
                raise ValueError(
                    f"{name} must be pandas-coercible (datetime/pd.Timestamp/ISO string), "
                    f"got {type(val).__name__}"
                ) from e
        
        # Validate timestamp types
        _ensure_timestamp(self.start, "start")
        _ensure_timestamp(self.end, "end")
        
        # Rule 1: Partial window forbidden
        if (self.start is None) != (self.end is None):
            raise ValueError(
                "Invalid request: start/end must both be set or both None. "
                f"Got start={self.start}, end={self.end}"
            )
        
        # Rule 2: Full-Load MUST NOT have warmup
        is_full_load = self.start is None and self.end is None
        if is_full_load and self.warmup_bars is not None:
            raise ValueError(
                "Invalid request: Full-Load (no start/end) MUST have warmup_bars=None. "
                f"Got warmup_bars={self.warmup_bars}. "
                "Warmup is a Strategy concern, not UI concern."
            )
        
        # Rule 3: Window-Load MUST have warmup (0 allowed)
        if not is_full_load and self.warmup_bars is None:
            raise ValueError(
                "Invalid request: Window-Load (start/end set) MUST have explicit warmup_bars. "
                f"Got start={self.start}, end={self.end}, warmup_bars=None. "
                "Set warmup_bars=0 if no warmup is needed."
            )
        
        # Rule 4: warmup_bars >= 0
        if self.warmup_bars is not None and self.warmup_bars < 0:
            raise ValueError(
                f"Invalid request: warmup_bars must be >= 0, got {self.warmup_bars}"
            )


@dataclass
class OhlcvMeta:
    """Metadata from OHLCV provider.
    
    Attributes:
        provider_id: Provider identifier (e.g., "axiom_bt", "marketstream_http")
        source_effective: Effective data source (e.g., "IntradayStore", "marketstream-service")
        row_count_total: Total rows returned
        warnings: List of warnings (e.g., fallback occurred)
    """
    provider_id: str
    source_effective: str
    row_count_total: int
    warnings: List[str] = field(default_factory=list)


class OhlcvProvider(Protocol):
    """Protocol for OHLCV data providers.
    
    All providers must implement get_ohlcv() which:
    1. Validates the request via req.validate()
    2. Fetches OHLCV data
    3. Returns (DataFrame, Metadata)
    """
    
    def get_ohlcv(self, req: OhlcvRequest) -> Tuple[pd.DataFrame, OhlcvMeta]:
        """Get OHLCV data for the given request.
        
        Args:
            req: OhlcvRequest (will be validated)
        
        Returns:
            Tuple of (DataFrame, OhlcvMeta)
            DataFrame has:
            - index: timestamp (tz-aware)
            - columns: open, high, low, close, volume
        
        Raises:
            ValueError: If request validation fails
            FileNotFoundError: If data not available
            Exception: Provider-specific errors
        """
        ...
