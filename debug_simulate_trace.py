"""
Debug script to trace exactly where simulate_insidebar_from_orders fails.
"""
import sys
sys.path.insert(0, 'src')

from pathlib import Path
import pandas as pd
from axiom_bt.engines.replay_engine import Costs
import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

# Manually inline the simulation to trace
orders_csv = Path('artifacts/backtests/251219_162524_TSLA_6d/orders.csv')
data_path = Path('artifacts/data_m5/TSLA.parquet')
data_path_m1 = Path('artifacts/data_m1/TSLA.parquet')
tz = 'America/New_York'

print("\n" + "="*60)
print("SCHRITT 1: IST-ANALYSE - DETAILLIERTES TRACING")
print("="*60 + "\n")

# Load orders
orders = pd.read_csv(orders_csv)
print(f"✓ Loaded {len(orders)} orders")

# Convert datetime
for col in ['valid_from', 'valid_to']:
    orders[col] = pd.to_datetime(orders[col], utc=True)
print(f"✓ Converted datetime columns (tz: {orders['valid_from'].dt.tz})")

# Timezone conversion
for col in ['valid_from', 'valid_to']:
    if orders[col].dt.tz is None:
        orders[col] = orders[col].dt.tz_localize(tz)
        print(f"  Localized {col} to {tz}")
    else:
        orders[col] = orders[col].dt.tz_convert(tz)
        print(f"  Converted {col} to {tz}")

print(f"  After conversion - tz: {orders['valid_from'].dt.tz}")

# Filter STOP orders
ib_orders = orders.query('order_type == "STOP"').copy()
print(f"✓ Filtered to {len(ib_orders)} STOP orders")

if ib_orders.empty:
    print("❌ BUG FOUND: All orders filtered out!")
    sys.exit(1)

# Load M1 data
from axiom_bt.engines.replay_engine import _derive_m1_dir, _resolve_symbol_path, _ensure_dtindex_and_ohlcv

m1_dir = Path(data_path_m1) if data_path_m1 else _derive_m1_dir(data_path)
print(f"✓ M1 directory: {m1_dir}")

# Process symbol
symbol = "TSLA"
file_path, used_m1 = _resolve_symbol_path(symbol, m1_dir, data_path)
print(f"✓ Data file: {file_path} (M1: {used_m1})")

ohlcv = pd.read_parquet(file_path)
ohlcv = _ensure_dtindex_and_ohlcv(ohlcv, tz)
ohlcv = ohlcv.sort_index()

print(f"✓ OHLCV loaded: {len(ohlcv)} rows")
print(f"  Index tz: {ohlcv.index.tz}")
print(f"  Range: {ohlcv.index.min()} → {ohlcv.index.max()}")
print()

# Try first order
from axiom_bt.engines.replay_engine import _first_touch_entry

row = ib_orders.iloc[0]
side = "BUY" if row["side"] == "BUY" else "SELL"
entry_price = float(row["price"])
valid_from = pd.to_datetime(row["valid_from"]).tz_convert(tz)
valid_to = pd.to_datetime(row["valid_to"]).tz_convert(tz)

print(f"Testing first order:")
print(f"  Symbol: {row['symbol']}")
print(f"  Side: {side}")
print(f"  Entry price: {entry_price}")
print(f"  Window: {valid_from} → {valid_to}")
print(f"  valid_from type: {type(valid_from)}, tz: {valid_from.tz}")
print(f"  valid_to type: {type(valid_to)}, tz: {valid_to.tz}")
print()

# Call _first_touch_entry
entry_ts = _first_touch_entry(ohlcv, side, entry_price, valid_from, valid_to)

if entry_ts is None:
    print("❌ BUG FOUND: _first_touch_entry returned None!")
    # Debug why
    window = ohlcv.loc[(ohlcv.index >= valid_from) & (ohlcv.index <= valid_to)]
    print(f"   Window has {len(window)} rows")
    if not window.empty:
        print(f"   Window range: {window.index.min()} → {window.index.max()}")
        if side == "BUY":
            hit = window[window["High"] >= entry_price]
        else:
            hit = window[window["Low"] <= entry_price]
        print(f"   Hit candles: {len(hit)}")
else:
    print(f"✓ Entry would fill at: {entry_ts}")
    print()
    print("→ So the individual functions work!")
    print("→ Bug must be in the loop or OCO handling!")
