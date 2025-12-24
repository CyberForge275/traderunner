"""Verification script for Rudometkin MOC Strategy."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.strategies.rudometkin_moc.strategy import RudometkinMOCStrategy

def generate_synthetic_data(length=300):
    """Generate synthetic OHLCV data."""
    dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(length)]

    # Create a trend
    t = np.linspace(0, 20, length) # Steeper slope
    trend = 100 + t * 5  # Strong upward trend

    # Add noise
    noise = np.random.normal(0, 0.5, length) # Less noise for cleaner trend (higher ADX)

    # Create price series
    close = trend + noise

    # Create a dip for Long setup (Day 250)
    # Drop close significantly relative to open
    # Ensure it stays above SMA200.
    # SMA200 at 250 will be approx average of prices from 50 to 250.
    # With linear trend 100 to 200 (approx), avg is 150.
    # Wait, t goes 0 to 20. Trend 100 to 200.
    # At 250 (5/6 of length), t is approx 16. Trend is 100 + 80 = 180.
    # SMA200 will be lower.

    close[250] = close[249] * 0.96 # 4% drop

    # Create a spike for Short setup (Day 280)
    close[280] = close[279] * 1.10

    open_p = close * 1.01 # Open slightly higher usually
    open_p[250] = close[249] # Open high on dip day

    high = np.maximum(open_p, close) * 1.01
    low = np.minimum(open_p, close) * 0.99
    volume = np.random.randint(1000, 10000, length)

    df = pd.DataFrame({
        "timestamp": dates,
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    })

    return df

def verify():
    print("Generating synthetic data...")
    df = generate_synthetic_data()

    print("Initializing strategy...")
    strategy = RudometkinMOCStrategy()

    print("Running generate_signals...")
    signals = strategy.generate_signals(df, "TEST", {})

    print(f"Generated {len(signals)} signals.")

    for sig in signals:
        print(f"\nSignal: {sig.signal_type} at {sig.timestamp}")
        print(f"  Entry: {sig.entry_price:.2f}")
        print(f"  Metadata: {sig.metadata}")

    # Debug: Check indicators around event days
    print("\n--- Debug: Day 250 (Long Setup Attempt) ---")
    # We need to access the internal dataframe with indicators.
    # Since generate_signals doesn't return it, we'll hack it by calling _calc_indicators directly here for debug.

    # Re-calculate indicators using the strategy method
    df_debug = strategy._calc_indicators(df.copy(), 5, 200, 2, 2, 100)

    row_250 = df_debug.iloc[250]
    print(f"Close: {row_250['close']:.2f}, SMA200: {row_250['sma200']:.2f}")
    print(f"ADX: {row_250['adx']:.2f} (Thresh: 35)")
    print(f"Dip: {(row_250['open'] - row_250['close']) / row_250['open']:.4f} (Thresh: 0.03)")

    print("\n--- Debug: Day 280 (Short Setup Attempt) ---")
    row_280 = df_debug.iloc[280]
    print(f"Close: {row_280['close']:.2f}")
    print(f"ADX: {row_280['adx']:.2f} (Thresh: 35)")
    print(f"CRSI: {row_280['crsi']:.2f} (Thresh: 70)")
    print(f"ATR40/C: {row_280['atr40']/row_280['close']:.4f}")

    has_long = any(s.signal_type == "LONG" for s in signals)
    has_short = any(s.signal_type == "SHORT" for s in signals)

    if has_long:
        print("\n✅ Long signal verified.")
    else:
        print("\n❌ Long signal missing.")

    if has_short:
        print("✅ Short signal verified.")
    else:
        print("❌ Short signal missing.")

if __name__ == "__main__":
    verify()
