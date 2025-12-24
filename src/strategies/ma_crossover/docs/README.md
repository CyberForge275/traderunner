# MA Crossover Strategy Documentation

## Overview

The Moving Average Crossover strategy generates trade signals based on the crossover of two exponential moving averages (EMAs).

## Strategy Logic

### Entry Criteria

**Moving Averages**:
- Fast EMA: 12-period
- Slow EMA: 26-period

**Trade Signals**:
- **BUY**: Fast EMA crosses above Slow EMA (bullish crossover)
- **SELL**: Fast EMA crosses below Slow EMA (bearish crossover)

### Position Sizing

- Default: 100 shares per trade
- Configurable in strategy config

### Risk Management

**Stop Loss**:
- BUY: Recent swing low or % below entry
- SELL: Recent swing high or % above entry

**Take Profit**:
- 2:1 Risk/Reward ratio (configurable)

### Session Filtering

- **RTH Only**: Regular trading hours (9:30 AM - 4:00 PM ET)
- Configurable for extended hours

## Configuration

Key parameters:
```python
fast_period = 12     # Fast EMA period
slow_period = 26     # Slow EMA period
timeframe = "M5"     # 5-minute bars
risk_reward = 2.0    # R:R ratio
```

## Files

- **[`core.py`](../core.py)**: Strategy logic
- **[`config.py`](../config.py)**: Configuration
- **[`strategy.py`](../strategy.py)**: Backtest adapter
- **[`tests/`](../tests/)**: Test suite

## Testing

Run tests:
```bash
pytest src/strategies/ma_crossover/tests/ -v
```

## Performance Metrics

*(To be updated after backtesting)*

- Win Rate: TBD
- Average R:R: 2.0 (by design)
- Best Markets: Trending markets
- Worst Markets: Choppy/ranging markets

## Known Limitations

1. **Lagging Indicator**: EMAs lag price action
2. **Choppy Markets**: Many false signals in ranging markets
3. **Whipsaws**: Multiple crossovers in consolidation

## Improvements Backlog

- [ ] Add trend filter (200 SMA)
- [ ] Volume confirmation
- [ ] MACD histogram filter
- [ ] Adaptive periods based on volatility

## Version History

- **v1.0**: Initial implementation
- Status: Development

---

*Last updated: 2025-12-11*
