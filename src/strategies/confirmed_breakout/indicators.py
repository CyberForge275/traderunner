from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_atr(df: pd.DataFrame, atr_period: int) -> pd.DataFrame:
    """
    Calculate Average True Range (ATR).

    Args:
        df: DataFrame with columns: open, high, low, close
        atr_period: rolling window for ATR

    Returns:
        DataFrame with added columns:
        - prev_close: Previous candle close
        - tr1, tr2, tr3: True Range components
        - true_range: Maximum of tr1, tr2, tr3
        - atr: Rolling average of true_range
    """
    df = df.copy()

    # Previous candle close (needed for TR calculation)
    df["prev_close"] = df["close"].shift(1)

    # True Range components:
    # TR1 = High - Low (current range)
    df["tr1"] = df["high"] - df["low"]

    # TR2 = |High - Previous Close| (gap up)
    df["tr2"] = np.abs(df["high"] - df["prev_close"])

    # TR3 = |Low - Previous Close| (gap down)
    df["tr3"] = np.abs(df["low"] - df["prev_close"])

    # True Range = max(TR1, TR2, TR3)
    df["true_range"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

    # ATR = Simple Moving Average of True Range
    df["atr"] = df["true_range"].rolling(
        window=atr_period,
        min_periods=atr_period
    ).mean()

    return df
