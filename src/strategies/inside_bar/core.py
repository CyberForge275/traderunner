"""
InsideBar Strategy Core Logic - SINGLE SOURCE OF TRUTH

Critical: This module contains ALL pattern detection and signal generation logic.
It is used by BOTH backtesting and live trading adapters.

Zero-deviation requirement: Any change here must maintain 100% parity
between backtest and live trading results.

Version: 2.0.0
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from pathlib import Path
import hashlib
import pandas as pd

# Import config classes from config module
from .config import InsideBarConfig
from .models import RawSignal
from .indicators import calculate_atr as _calculate_atr
from .pattern_detection import detect_inside_bars as _detect_inside_bars
from .session_logic import generate_signals as _generate_signals


# ══════════════════════════════════════════════════════════════════════
# VERSION METADATA
# ══════════════════════════════════════════════════════════════════════

__version__ = "2.0.0"
__strategy_name__ = "InsideBar"


def _get_core_checksum() -> str:
    """
    Calculate SHA256 checksum of this core.py file.

    This ensures we can verify which exact version of the code
    generated a signal, even if version tags don't change.

    Returns:
        First 16 characters of SHA256 hash
    """
    try:
        core_path = Path(__file__)
        with open(core_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return "unknown"


STRATEGY_VERSION = __version__
STRATEGY_NAME = __strategy_name__
CORE_CHECKSUM = _get_core_checksum()



class InsideBarCore:
    """
    Core InsideBar strategy logic.

    Design Principles:
    1. Deterministic - same input always produces same output
    2. Stateless - no side effects
    3. Testable - pure functions
    4. Format-agnostic - returns raw data structures

    Usage:
        config = InsideBarConfig(
            inside_bar_definition_mode="mb_body_oc__ib_hl",
            atr_period=14,
            risk_reward_ratio=2.0,
        )
        core = InsideBarCore(config)
        signals = core.process_data(df, symbol='APP')
    """

    def __init__(self, config: InsideBarConfig):
        """
        Initialize with validated config.

        Args:
            config: InsideBarConfig instance
        """
        config.validate()
        self.config = config

    @property
    def version(self) -> str:
        """Strategy version string."""
        return STRATEGY_VERSION

    @property
    def metadata(self) -> dict:
        """
        Strategy metadata including version and checksum.

        Returns:
            Dictionary with name, version, checksum, and file path
        """
        return {
            "name": STRATEGY_NAME,
            "version": STRATEGY_VERSION,
            "checksum": CORE_CHECKSUM,
            "file": __file__
        }

    def calculate_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Average True Range (ATR).

        ATR measures market volatility and is used for:
        1. Filtering minimum mother bar size
        2. Risk management (not directly, but informational)

        Args:
            df: DataFrame with columns: open, high, low, close

        Returns:
            DataFrame with added columns:
            - prev_close: Previous candle close
            - tr1, tr2, tr3: True Range components
            - true_range: Maximum of tr1, tr2, tr3
            - atr: Rolling average of true_range
        """
        return _calculate_atr(df, atr_period=self.config.atr_period)

    def detect_inside_bars(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect inside bar patterns.

        Inside Bar Definition:
        - Current candle's high is AT OR BELOW previous candle's high (inclusive mode)
        - Current candle's low is AT OR ABOVE previous candle's low (inclusive mode)
        - OR strictly inside (strict mode)

        Mother Bar:
        - The candle immediately before the inside bar
        - Its high and low define breakout levels

        Args:
            df: DataFrame with OHLC data and 'atr' column

        Returns:
            DataFrame with added columns:
            - prev_high: Previous candle high
            - prev_low: Previous candle low
            - prev_range: Previous candle range
            - is_inside_bar: Boolean mask
            - mother_bar_high: High of mother bar (NaN if not inside)
            - mother_bar_low: Low of mother bar (NaN if not inside)
        """
        return _detect_inside_bars(df, self.config)

    def generate_signals(
        self,
        df: pd.DataFrame,
        symbol: str,
        tracer: Optional[Callable[[Dict[str, Any]], None]] = None,
        debug_file: Optional[Path] = None,
    ) -> List[RawSignal]:
        return _generate_signals(
            df,
            symbol,
            self.config,
            tracer=tracer,
            debug_file=debug_file,
        )

    def process_data(
        self,
        df: pd.DataFrame,
        symbol: str,
        tracer: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[RawSignal]:
        """
        Complete pipeline: Input data → Signals.

        This is the main entry point for both adapters.

        Pipeline:
        1. Validate input data
        2. Calculate ATR
        3. Detect inside bars
        4. Generate breakout signals
        5. Apply session filtering (if configured)

        Args:
            df: DataFrame with OHLC data
                Required columns: timestamp, open, high, low, close
                Optional: volume
            symbol: Trading symbol

        Returns:
            List of RawSignal objects (filtered by session if configured)

        Raises:
            ValueError: If required columns are missing
        """
        # Validate required columns
        required = ['timestamp', 'open', 'high', 'low', 'close']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Ensure DataFrame is sorted by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Pipeline: Calculate ATR, detect patterns, generate signals
        df = self.calculate_atr(df)
        df = self.detect_inside_bars(df)
        signals = self.generate_signals(df, symbol, tracer=tracer)

        # Apply session filtering if configured
        if self.config.session_filter is not None:
            session_tz = getattr(self.config, 'session_timezone', None) or "Europe/Berlin"

            # DEBUG: Print final filter application
            print("\n" + "="*70)
            print("[FINAL_FILTER_APPLY]")
            print(f"  signals_before: {len(signals)}")
            print(f"  session_tz: {session_tz}")
            print(f"  session_windows: {self.config.session_filter.to_strings()}")
            print("="*70)

            # DEBUG: Log final filter application
            if tracer:
                tracer({
                    'event': 'final_filter_apply',
                    'signals_before': len(signals),
                    'session_tz': session_tz,
                    'session_windows': self.config.session_filter.to_strings()
                })

            filtered_signals = []
            for sig in signals:
                # Ensure timestamp is a pd.Timestamp
                ts = pd.to_datetime(sig.timestamp)

                # DEBUG: Print timestamp details BEFORE filter check
                print(f"\n[FILTER_CHECK] Checking signal:")
                print(f"  sig.timestamp: {sig.timestamp} (type={type(sig.timestamp).__name__})")
                print(f"  after pd.to_datetime: {ts} (tz={ts.tz})")
                if ts.tz:
                    ts_local = ts.tz_convert(session_tz)
                    print(f"  converted to {session_tz}: {ts_local} (time={ts_local.time()})")
                else:
                    print(f"  WARNING: Timestamp has no timezone!")

                in_session = self.config.session_filter.is_in_session(ts, session_tz)

                print(f"  in_session result: {in_session}")
                print(f"  side: {sig.side}")

                # DEBUG: Log each filter decision
                if tracer:
                    ts_local = ts.tz_convert(session_tz).strftime('%H:%M')
                    tracer({
                        'event': 'final_filter_check',
                        'ts': ts.isoformat(),
                        'ts_local': ts_local,
                        'in_session': in_session,
                        'side': sig.side
                    })

                if in_session:
                    filtered_signals.append(sig)
                    print(f"  ✅ ACCEPTED")
                else:
                    print(f"  ❌ REJECTED (outside session)")

            # DEBUG: Print final filter result
            print("\n" + "="*70)
            print("[FINAL_FILTER_RESULT]")
            print(f"  signals_after: {len(filtered_signals)}")
            print(f"  filtered_out: {len(signals) - len(filtered_signals)}")
            print("="*70 + "\n")

            if tracer:
                tracer({
                    'event': 'final_filter_result',
                    'signals_after': len(filtered_signals),
                    'filtered_out': len(signals) - len(filtered_signals)
                })

            return filtered_signals

        return signals
