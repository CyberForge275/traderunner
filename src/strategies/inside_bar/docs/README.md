# InsideBar Strategy Documentation

## Overview

The InsideBar strategy identifies inside bar patterns (bars where high/low are contained within the previous bar's range) and generates trade signals based on breakouts from these consolidation patterns.

## Strategy Logic

### Entry Criteria

**Inside Bar Pattern**:
- Current bar's high ≤ Previous bar's high
- Current bar's low ≥ Previous bar's low
- Indicates consolidation/indecision

**Trade Direction**:
- **BUY**: On breakout above mother bar high
- **SELL**: On breakdown below mother bar low

### Position Sizing

- Default: 100 shares per trade
- Configurable in `config.py`

### Risk Management

**Stop Loss**:
- BUY: Mother bar low
- SELL: Mother bar high

**Take Profit**:
- 2:1 Risk/Reward ratio (configurable)
- Calculated from entry - stop_loss distance × risk_reward_ratio

### Session Filtering

- **RTH Only**: Only trades during regular trading hours (9:30 AM - 4:00 PM ET)
- **Pre-Market**: Optional (configurable via `include_premarket`)
- **After-Hours**: Optional (configurable via `include_afterhours`)

## Configuration

See: [`config.py`](../config.py)

Key parameters:
```python
timeframe = "M5"              # 5-minute bars
risk_reward_ratio = 2.0       # 2:1 R:R
include_premarket = False     # RTH only by default
include_afterhours = False
default_quantity = 100        # shares
```

## Files

- **[`core.py`](../core.py)**: Pure strategy logic (shared between backtest & live)
- **[`config.py`](../config.py)**: Configuration dataclass
- **[`strategy.py`](../strategy.py)**: Backtest adapter
- **[`tests/`](../tests/)**: Unit & parity tests

## Testing

Run tests:
```bash
pytest src/strategies/inside_bar/tests/ -v
```

Parity test (backtest vs live):
```bash
pytest src/strategies/inside_bar/tests/test_parity.py -v
```

## Live Deployment

Strategy deployed via: `/opt/trading/marketdata-stream/config/strategy_deployments.yml`

## Performance Metrics

*(To be updated after backtesting/live runs)*

- Win Rate: TBD
- Average R:R: 2.0 (by design)
- Max Drawdown: TBD
- Sharpe Ratio: TBD

## Known Limitations

1. **False Breakouts**: Inside bars can produce false breakouts in choppy markets
2. **Trend Dependency**: Works best in trending markets
3. **Gap Risk**: No handling for large gaps (overnight/weekend)

## Improvements Backlog

- [ ] Add trend filter (only trade in direction of higher TF trend)
- [ ] Volume confirmation for breakouts
- [ ] Multiple timeframe analysis
- [ ] Dynamic position sizing based on volatility

## Version History

- **v1.0**: Initial implementation with unified core
- Parity tests: ✅ Passing
- Status: Live in Pre-PaperTrade

---

*Last updated: 2025-12-11*
