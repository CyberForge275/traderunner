# Rudometkin MOC (Market On Close) Strategy

## Overview
This strategy, developed by Alexei Rudometkin, is a mean-reversion system that trades both long and short sides of the market. It looks for overextended moves (high ADX, deep pullbacks) and places limit orders to catch a "snap back" move, exiting at the close of the entry day.

## Strategy Logic

### Universe Selection
- **Index**: Russell 1000 (`InRUI`)
- **Price**: Close >= $10
- **Liquidity**: Average Daily Volume (50-day) >= 1,000,000

### Long Strategy (`moc_long`)
**Concept**: Catch a falling knife in a strong trend.

1.  **Setup Conditions**:
    - **Trend**: Price is above the 200-day SMA (`Close > SMA200`).
    - **Volatility/Trend Strength**: ADX(5) > 35 (Market is moving fast).
    - **Pullback**: A significant intraday drop today: `(Open - Close) / Open > 3%`.

2.  **Ranking**:
    - Higher volatility is better: Rank by `ATR(10) / Close`.

3.  **Entry**:
    - Place a **Limit Buy** order for the next day at `Current Close * (1 - 3.5%)`.
    - This is a deep discount entry (catching a crash).

4.  **Exit**:
    - Market On Close (MOC) of the entry day (1-day hold).

### Short Strategy (`moc_short`)
**Concept**: Fade a parabolic move.

1.  **Setup Conditions**:
    - **Trend Strength**: ADX(5) > 35.
    - **Overbought**: Connors RSI (2,2,100) > 70.
    - **Volatility Filters**:
        - `ATR(40) / Close` between 1% and 10%.
        - `ATR(2) / Close` between 1% and 20%.

2.  **Ranking**:
    - Momentum: Rank by 5-day Rate of Change (`ROC(5)`).

3.  **Entry**:
    - Place a **Limit Sell** order for the next day at `Current Close * (1 + 5%)`.
    - Selling into a massive spike.

4.  **Exit**:
    - Market On Close (MOC) of the entry day.

## Parameters
| Parameter | Default | Description |
| :--- | :--- | :--- |
| `entry_stretch1` | 0.035 (3.5%) | Buy limit discount for Long strategy |
| `entry_stretch2` | 0.05 (5.0%) | Sell limit premium for Short strategy |
| `maxpos` | 10 | Maximum number of simultaneous positions |

## Indicators Used
- **SMA**: Simple Moving Average
- **ADX**: Average Directional Index (measures trend strength, not direction)
- **ATR**: Average True Range (measures volatility)
- **CRSI**: Connors RSI (composite of RSI, Up/Down Streak, and Percent Rank)
- **ROC**: Rate of Change
