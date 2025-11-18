from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def generate_demo_data(
    root: str | Path = "artifacts/demo",
    symbol: str = "TEST",
    window_days: int = 60,
) -> Path:
    root_path = Path(root)
    data_dir = root_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    end = pd.Timestamp.now(tz="UTC").floor("h")
    start = end - pd.Timedelta(days=window_days - 1)
    index = pd.date_range(start=start, end=end, freq="h", tz="UTC")

    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.4, len(index)))
    high = close + rng.normal(0.5, 0.2, len(index))
    low = close - rng.normal(0.5, 0.2, len(index))
    open_price = close + rng.normal(0, 0.2, len(index))
    volume = rng.integers(50_000, 150_000, len(index))

    ohlcv = pd.DataFrame(
        {
            "Open": open_price,
            "High": np.maximum.reduce([high, open_price, close]),
            "Low": np.minimum.reduce([low, open_price, close]),
            "Close": close,
            "Volume": volume,
        },
        index=index,
    )

    ohlcv.to_parquet(data_dir / f"{symbol}.parquet")

    order_start = (end - pd.Timedelta(days=1)).isoformat()
    order_end = (end + pd.Timedelta(hours=4)).isoformat()
    trigger_idx = -12
    entry_price = float(close[trigger_idx])
    orders_path = root_path / "orders.csv"
    root_path.mkdir(parents=True, exist_ok=True)
    orders_path.write_text(
        "\n".join(
            [
                "valid_from,valid_to,symbol,side,order_type,price,stop_loss,take_profit,qty,tif,oco_group,source",
                f"{order_start},{order_end},{symbol},BUY,STOP,{entry_price:.2f},{entry_price-2:.2f},{entry_price+3:.2f},1,DAY,grp1,demo",
            ]
        )
    )

    return root_path


if __name__ == "__main__":
    path = generate_demo_data()
    print(f"Demo data refreshed under {path}")
