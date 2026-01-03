
import pandas as pd
import pytest
from pathlib import Path
from axiom_bt.engines import replay_engine
import os

def test_exit_not_bounded_by_valid_to():
    """
    REGRESSION TEST: Decouple position exit from order validity.
    Ensures that a filled position remains open until market close 
    even if the entry order's valid_to timestamp has passed.
    """
    tz = "America/New_York"
    
    # 1. Create 1 day of M5 data (09:30 - 16:00)
    times = pd.date_range("2025-01-02 09:30", "2025-01-02 16:00", freq="5min", tz=tz)
    df = pd.DataFrame({
        "Open": 100.0,
        "High": 100.5,
        "Low": 99.5,
        "Close": 100.0,
        "Volume": 1000
    }, index=times)
    
    data_dir = Path("/tmp/reproduce_exit_bug_data")
    data_dir.mkdir(exist_ok=True)
    parquet_path = data_dir / "HOOD_rth.parquet"
    df.to_parquet(parquet_path)
    
    # 2. Create orders.csv
    # Signal at 10:25, valid_to is 10:30 (short window)
    orders_csv = Path("/tmp/reproduce_exit_bug_orders.csv")
    orders_df = pd.DataFrame([{
        "symbol": "HOOD",
        "side": "BUY",
        "order_type": "STOP",
        "price": 100.0,
        "stop_loss": 90.0,
        "take_profit": 110.0,
        "qty": 10,
        "valid_from": "2025-01-02 10:25:00-05:00",
        "valid_to": "2025-01-02 10:30:00-05:00",
        "oco_group": "test_oco_1"
    }])
    orders_df.to_csv(orders_csv, index=False)
    
    # 3. Simulated costs
    costs = replay_engine.Costs(fees_bps=0, slippage_bps=0)
    
    # 4. Run simulation
    result = replay_engine.simulate_insidebar_from_orders(
        orders_csv=orders_csv,
        data_path=data_dir,
        tz=tz,
        costs=costs,
        initial_cash=10000.0
    )
    
    trades = result["trades"]
    assert len(trades) == 1, "Should have 1 trade"
    
    trade = trades.iloc[0]
    exit_ts = pd.Timestamp(trade["exit_ts"])
    valid_to_ts = pd.Timestamp("2025-01-02 10:30:00-05:00")
    market_close_ts = pd.Timestamp("2025-01-02 16:00:00-05:00")
    
    # Verify separation of concerns
    assert exit_ts > valid_to_ts, f"Exit {exit_ts} must be independent of valid_to {valid_to_ts}"
    assert exit_ts == market_close_ts, f"Exit {exit_ts} should be at market close {market_close_ts}"
    
    # Cleanup temp files
    if orders_csv.exists(): orders_csv.unlink()
    if parquet_path.exists(): parquet_path.unlink()

if __name__ == "__main__":
    pytest.main([__file__])
