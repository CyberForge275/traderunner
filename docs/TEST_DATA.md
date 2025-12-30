# Test Data for traderunner

This directory contains sample datasets in `/data/samples/` for testing and development. These lightweight datasets enable external AI agents and developers to work on the codebase without requiring full production data.

## Quick Start

Generate test datasets:
```bash
python3 scripts/generate_test_data.py
```

## Datasets Created

- **`data/samples/rudometkin_test.parquet`** - Daily OHLCV data (8 symbols, 1 year)
- **`data/samples/m1_candles/`** - 1-minute candles (AAPL, MSFT, TSLA, 5 days)
- **`data/samples/m5_candles/`** - 5-minute candles (resampled from M1)
- **`data/samples/m15_candles/`** - 15-minute candles (resampled from M1)

See complete documentation in the test data generation script.

---

**For external AI agents (e.g., Jules from Google):**

The test datasets are committed to the repository for easy access. Use them for:
- Strategy development and testing
- Unit test fixtures
- Code verification without downloading production data
- Quick iteration on features

**Note:** Test data is synthetic and not suitable for production trading.
