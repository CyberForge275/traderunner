"""
Data frame contracts for OHLCV data validation.

Ensures strict adherence to data quality standards:
- UPPERCASE OHLCV column names
- UTC timezone-aware DatetimeIndex
- No NaNs in critical columns
- Monotonic increasing timestamps
"""

from typing import Optional, List
import pandas as pd
from decimal import Decimal


class DailyFrameSpec:
    """
    Contract specification for Daily OHLCV DataFrames.

    Requirements:
    - Columns: Open, High, Low, Close, Volume (UPPERCASE)
    - Index: UTC tz-aware DatetimeIndex
    - Monotonic increasing
    - No duplicates
    - No NaNs in O/H/L/C
    - Volume >= 0
    """

    REQUIRED_COLUMNS = ['Open', 'High', 'Low', 'Close', 'Volume']

    @classmethod
    def validate(cls, df: pd.DataFrame, strict: bool = True) -> tuple[bool, List[str]]:
        """
        Validate DataFrame against Daily contract.

        Args:
            df: DataFrame to validate
            strict: If True, raise on first violation. If False, collect all violations.

        Returns:
            (is_valid, violations) tuple
        """
        violations = []

        # Check 1: OHLCV columns present (UPPERCASE)
        missing_cols = [col for col in cls.REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            violations.append(f"Missing columns: {missing_cols}")

        # Check 2: DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            violations.append(f"Index must be DatetimeIndex, got {type(df.index).__name__}")

        # Check 3: UTC timezone-aware
        if isinstance(df.index, pd.DatetimeIndex):
            if df.index.tz is None:
                violations.append("Index must be timezone-aware (UTC)")
            elif str(df.index.tz) != 'UTC':
                violations.append(f"Index must be UTC, got {df.index.tz}")

        # Check 4: Monotonic increasing
        if isinstance(df.index, pd.DatetimeIndex) and not df.index.is_monotonic_increasing:
            violations.append("Index must be monotonic increasing")

        # Check 5: No duplicates
        if df.index.has_duplicates:
            violations.append(f"Index has {df.index.duplicated().sum()} duplicates")

        # Check 6: No NaNs in OHLC
        if not missing_cols:
            ohlc_cols = ['Open', 'High', 'Low', 'Close']
            nan_counts = df[ohlc_cols].isna().sum()
            if nan_counts.any():
                violations.append(f"NaNs found in OHLC: {nan_counts[nan_counts > 0].to_dict()}")

        # Check 7: Volume >= 0
        if 'Volume' in df.columns:
            if (df['Volume'] < 0).any():
                violations.append("Volume contains negative values")

        # Check 8: OHLC consistency (High >= max(O,C), Low <= min(O,C))
        if not missing_cols and len(df) > 0:
            high_valid = (df['High'] >= df[['Open', 'Close']].max(axis=1)).all()
            low_valid = (df['Low'] <= df[['Open', 'Close']].min(axis=1)).all()
            if not high_valid:
                violations.append("High must be >= max(Open, Close)")
            if not low_valid:
                violations.append("Low must be <= min(Open, Close)")

        is_valid = len(violations) == 0
        return is_valid, violations

    @classmethod
    def assert_valid(cls, df: pd.DataFrame) -> None:
        """Assert DataFrame is valid, raise ValueError with all violations."""
        is_valid, violations = cls.validate(df, strict=False)
        if not is_valid:
            raise ValueError(
                f"DailyFrameSpec validation failed:\n" +
                "\n".join(f"  - {v}" for v in violations)
            )


class IntradayFrameSpec:
    """
    Contract specification for Intraday (M1/M5) OHLCV DataFrames.

    Same as DailyFrameSpec, plus:
    - Session-aware (no bars outside market hours)
    - No overnight gaps within sessions
    """

    REQUIRED_COLUMNS = DailyFrameSpec.REQUIRED_COLUMNS

    @classmethod
    def validate(cls, df: pd.DataFrame,
                 calendar=None,
                 tz: str = 'UTC',
                 strict: bool = True) -> tuple[bool, List[str]]:
        """
        Validate intraday DataFrame.

        Args:
            df: DataFrame to validate
            calendar: Optional pandas_market_calendars calendar for session validation
            tz: Timezone for display (data should already be UTC)
            strict: If True, raise on first violation

        Returns:
            (is_valid, violations) tuple
        """
        # First run Daily validation
        is_valid, violations = DailyFrameSpec.validate(df, strict=False)

        # Additional intraday checks
        if calendar is not None and isinstance(df.index, pd.DatetimeIndex):
            # TODO: Implement session-aware validation
            # - Check bars only during market hours
            # - Check no overnight bars
            pass

        is_valid = len(violations) == 0
        return is_valid, violations

    @classmethod
    def assert_valid(cls, df: pd.DataFrame, calendar=None, tz: str = 'UTC') -> None:
        """Assert DataFrame is valid, raise ValueError with all violations."""
        is_valid, violations = cls.validate(df, calendar=calendar, tz=tz, strict=False)
        if not is_valid:
            raise ValueError(
                f"IntradayFrameSpec validation failed:\n" +
                "\n".join(f"  - {v}" for v in violations)
            )
