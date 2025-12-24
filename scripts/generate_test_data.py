"""
Generate test datasets for traderunner repository.

Creates sample data for:
1. Rudometkin universe (daily data)
2. M1, M5, M15 candle data (intraday M1 data)

This test data enables external AI agents (like Jules from Google) to work on the codebase
without requiring full production datasets.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Set random seed for reproducibility
np.random.seed(42)

def generate_daily_universe_data(symbol: str, start_date: str, end_date: str, base_price: float = 150.0):
    """Generate realistic daily OHLCV data for a symbol."""
    dates = pd.bdate_range(start=start_date, end=end_date)
    n_days = len(dates)

    # Generate price movement with some trend and volatility
    returns = np.random.normal(0.0005, 0.02, n_days)  # Slight upward drift, 2% daily volatility
    prices = base_price * np.exp(np.cumsum(returns))

    # Generate OHLC with realistic intraday moves
    data = []
    for i, date in enumerate(dates):
        close_price = prices[i]
        daily_range = close_price * np.random.uniform(0.01, 0.03)  # 1-3% daily range

        # Generate Open, High, Low
        open_price = close_price * np.random.uniform(0.99, 1.01)
        high_price = max(open_price, close_price) + np.random.uniform(0, daily_range/2)
        low_price = min(open_price, close_price) - np.random.uniform(0, daily_range/2)

        # Ensure OHLC consistency
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)

        # Generate volume (higher on volatile days)
        base_volume = np.random.uniform(500000, 2000000)
        volatility_mult = abs(close_price - open_price) / open_price * 10
        volume = base_volume * (1 + volatility_mult)

        data.append({
            'ts_id': 1,
            'Date': date,
            'Open': round(open_price, 2),
            'High': round(high_price, 2),
            'Low': round(low_price, 2),
            'Close': round(close_price, 2),
            'Volume': round(volume),
            'Adj_Close': round(close_price, 2)  # Assuming no adjustments for simplicity
        })

    df = pd.DataFrame(data)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index([pd.Index([symbol] * len(df), name='Symbol'), 'Date'])

    return df

def generate_m1_candle_data(symbol: str, date: str, session_start: str = "09:30",
                             session_end: str = "16:00", base_price: float = 250.0):
    """Generate realistic M1 (1-minute) candle data for a trading session."""
    # Parse date and create timestamp range
    date_obj = pd.to_datetime(date)
    start_time = pd.Timestamp(f"{date} {session_start}", tz='America/New_York')
    end_time = pd.Timestamp(f"{date} {session_end}", tz='America/New_York')

    # Create minute-by-minute timestamps
    timestamps = pd.date_range(start=start_time, end=end_time, freq='1min')
    n_candles = len(timestamps)

    #Generate intraday price movement
    # Simulate market microstructure with mean reversion and occasional trends
    returns = np.random.normal(0, 0.0005, n_candles)  # ~3% annualized intraday vol
    prices = base_price * np.exp(np.cumsum(returns))

    data = []
    for i, ts in enumerate(timestamps):
        close_price = prices[i]

        # Smaller intraday moves
        tick_range = close_price * np.random.uniform(0.0001, 0.002)  # 0.01-0.2% per minute

        open_price = prices[i-1] if i > 0 else base_price
        high_price = max(open_price, close_price) + np.random.uniform(0, tick_range)
        low_price = min(open_price, close_price) - np.random.uniform(0, tick_range)

        # Ensure OHLC consistency
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)

        # Volume varies throughout the day (U-shaped pattern)
        hour_of_day = ts.hour + ts.minute / 60
        # Higher volume at open and close
        time_factor = 1 + 0.5 * (abs(hour_of_day - 12.5) / 3.5)
        volume = int(np.random.uniform(50, 500) * time_factor)

        data.append({
            'timestamp': ts,
            'Open': round(open_price, 2),
            'High': round(high_price, 2),
            'Low': round(low_price, 2),
            'Close': round(close_price, 2),
            'Volume': volume
        })

    df = pd.DataFrame(data)
    df = df.set_index('timestamp')

    return df

def generate_multi_symbol_universe(symbols: list, start_date: str, end_date: str):
    """Generate daily universe data for multiple symbols."""
    all_data = []
    base_prices = [150, 75, 200, 50, 180, 250, 120, 90]  # Varied base prices

    for symbol, base_price in zip(symbols, base_prices):
        df = generate_daily_universe_data(symbol, start_date, end_date, base_price)
        all_data.append(df)

    combined = pd.concat(all_data)
    return combined

def main():
    """Generate all test datasets."""
    print("Generating test datasets for traderunner...")

    # Create output directories
    test_data_dir = Path("data/samples")
    test_data_dir.mkdir(parents=True, exist_ok=True)

    # Test symbols
    test_symbols = ["AAPL", "MSFT", "TSLA", "GOOGL", "AMZN", "NVDA", "META", "NFLX"]

    # 1. Generate Rudometkin universe dataset (1 year of daily data)
    print("  Generating Rudometkin universe data...")
    end_date = "2024-11-27"
    start_date = "2023-11-27"

    universe_df = generate_multi_symbol_universe(test_symbols, start_date, end_date)
    universe_path = test_data_dir / "rudometkin_test.parquet"
    universe_df.to_parquet(universe_path)
    print(f"    ✓ Created {universe_path} ({len(universe_df)} rows, {len(test_symbols)} symbols)")

    # 2. Generate M1 candle data (5 trading days for each symbol)
    print("  Generating M1 candle data...")
    m1_dir = test_data_dir / "m1_candles"
    m1_dir.mkdir(exist_ok=True)

    # Generate for last 5 trading days
    test_dates = pd.bdate_range(end="2024-11-27", periods=5)

    for symbol in test_symbols[:3]:  # Just a few symbols to keep size manageable
        all_days = []
        base_price = {"AAPL": 250, "MSFT": 420, "TSLA": 340}.get(symbol, 200)

        for date in test_dates:
            date_str = date.strftime("%Y-%m-%d")
            df = generate_m1_candle_data(symbol, date_str, base_price=base_price)
            all_days.append(df)

        combined_m1 = pd.concat(all_days)
        m1_path = m1_dir / f"{symbol}.parquet"
        combined_m1.to_parquet(m1_path)
        print(f"    ✓ Created {m1_path} ({len(combined_m1)} M1 candles)")

    # 3. Generate M5 and M15 by resampling M1
    print("  Generating M5 and M15 candle data...")

    for timeframe, freq in [("m5", "5min"), ("m15", "15min")]:
        tf_dir = test_data_dir / f"{timeframe}_candles"
        tf_dir.mkdir(exist_ok=True)

        for parquet_file in m1_dir.glob("*.parquet"):
            m1_df = pd.read_parquet(parquet_file)

            # Resample to higher timeframe
            resampled = m1_df.resample(freq).agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()

            out_path = tf_dir / parquet_file.name
            resampled.to_parquet(out_path)
            print(f"    ✓ Created {out_path} ({len(resampled)} {timeframe.upper()} candles)")

    print("\n✅ Test dataset generation complete!")
    print(f"\nTest data location: {test_data_dir.absolute()}")
    print(f"  - Daily universe: rudometkin_test.parquet")
    print(f"  - M1 candles: m1_candles/")
    print(f"  - M5 candles: m5_candles/")
    print(f"  - M15 candles: m15_candles/")

if __name__ == "__main__":
    main()
