# Rudometkin MOC Long/Short RealTest Script — Human Readable Translation

This document translates the original RealTest script `rudometkin_moc_long_short.rts.txt` into prose so that the strategy can be reviewed without knowledge of the RealTest language. The script implements Alexei Rudometkin’s Market-On-Close mean-reversion system with coordinated long and short components.

---

## 1. Data & Test Settings

| Setting | Value | Notes |
| --- | --- | --- |
| `DataFile` | `Polygon.rtd` | Use Polygon-sourced end-of-day data. |
| `StartDate` | `1/1/2007` | First trading day considered in the backtest. |
| `EndDate` | `Latest` | Run through the most recent available bar. |
| `BarSize` | `Daily` | Work on daily bars. |
| `UseAvailableBars` | `False` | Require complete history for indicators (no partial bars). |
| `AccountSize` | `100000` | Reference equity for sizing in RealTest. |
| `TestName` | `"poly"` | Run label. |

> _The commented “Import” block shows the original author used Norgate data and the Russell 1000 membership list while exporting a RealTest data file. The active `Settings` section re-runs the script against Polygon data._

---

## 2. User Parameters

| Parameter | Default | Meaning |
| --- | --- | --- |
| `entry_stretch1` | `0.035` | Long limit order is placed 3.5 % below today’s close. |
| `entry_stretch2` | `0.05` | Short limit order is placed 5 % above today’s close. |
| `maxpos` | `10` | Cap on concurrent positions across both directions. |

These values can be optimised or overridden in RealTest; we mirror them in the Python implementation.

---

## 3. Indicator & Universe Definitions (Data Section)

The `Data:` block defines reusable series that are evaluated on every bar per symbol.

| Symbol | Expression | Human Description |
| --- | --- | --- |
| `adx5` | `adx(5)` | Five-day Average Directional Index. Measures trend strength. |
| `atr2` | `atr(2)` | Two-day Average True Range (Wilder smoothing). Very short-term volatility. |
| `atr10` | `atr(10)` | Ten-day ATR. Used in long-rank scoring. |
| `atr40` | `atr(40)` | Forty-day ATR. Used for position sizing and short filters. |
| `crsi2` | `CRSI(100,2,2)` | Connors RSI: price RSI length 2, streak RSI length 2, 100-day percent-rank window. |
| `roc5` | `roc(c,5)` | Five-day rate of change in percent. |
| `sma200` | `Avg(c, 200)` | 200-day simple moving average of the close. |
| `universe` | `InRUI and C >= 10 and Avg(V,50) >= 1000000` | Russell 1000 membership, price ≥ $10, and 50-day average volume ≥ 1 M shares. |

From these primitives the script defines two setups:

### 3.1 Long Setup (`setup1`)
- Must be in the `universe` filter.
- Close above the 200-day SMA (stock in an uptrend).
- ADX above 35 (trend strength / high volatility).
- Intraday drop greater than 3 %: `(Open - Close) / Open > 0.03`.

Associated values:
- `score1`: ranking metric = `atr10 / Close` (daily volatility scaled by price). Higher values are prioritised when capital is limited.
- `price1`: next-day limit buy price = `Close * (1 - entry_stretch1)`.

### 3.2 Short Setup (`setup2`)
- Must be in the `universe` filter.
- ADX above 35 (parabolic move requirement).
- Connors RSI above 70 (overbought condition combining price RSI, streak RSI, percent-rank).
- Volatility guardrails:
  - `atr40 / Close` between 1 % and 10 %.
  - `atr2 / Close` between 1 % and 20 %.

Associated values:
- `score2`: ranking metric = `roc5` (5-day momentum; higher ranks favour stronger blow-offs).
- `price2`: next-day limit sell price = `Close * (1 + entry_stretch2)`.

---

## 4. Portfolio Template & Risk Controls

`Template: common` acts like a reusable configuration block referenced by both strategy legs.

| Field | Value | Interpretation |
| --- | --- | --- |
| `Quantity` | `S.Alloc * 0.5 * 0.01 / atr40` | Shares sized so that each position risks 1 % of half the allocated capital, scaled by ATR(40). |
| `QtyType` | `Shares` | Quantity is share count, not dollars. |
| `ExitRule` | `1` | Forces an unconditional exit after one bar. |
| `ExitTime` | `ThisClose` | Exit occurs on the close of the entry day (Market-On-Close). |
| `MaxPositions` | `maxpos` | Maximum concurrent trades across both directions. |
| `Commission` | `Max(0.005 * Shares, 1)` | Pay $0.005 per share with a $1 minimum per order. |

Additional guardrails:
- `Combined: MaxSameSym: 1` ensures no symbol is traded concurrently on both sides.

> _The commented `EntrySkip` line hints at limiting to one signal per day across templates, but it is disabled in the provided script._

---

## 5. Strategy Blocks

Two strategy declarations reuse the shared `common` template:

### 5.1 `Strategy: moc_long`
- `Side: long`
- `EntrySetup: setup1`
- `SetupScore: score1` (higher `atr10/close` ranks earlier when capital limited).
- `EntryLimit: price1` (limit buy at 3.5 % discount by default).

### 5.2 `Strategy: moc_short`
- `Side: short`
- `EntrySetup: setup2`
- `SetupScore: score2` (higher five-day ROC ranks first).
- `EntryLimit: price2` (limit sell 5 % above close by default).

Shared behaviour from the template means both legs:
- Place the order for the next session.
- Exit at the market-on-close of the entry session regardless of profit/loss.
- Size trades inversely proportional to 40-day ATR.
- Obey the global position cap and commission schedule.

---

## 6. Execution Flow Summary

1. **Universe filter** narrows symbols to liquid Russell 1000 names above $10.
2. **Indicator calculations** supply trend (ADX, SMA200), volatility (multiple ATR horizons), momentum (ROC5), and Connors RSI readings.
3. On any bar where a setup is true, the script prepares a **next-day limit order**:
   - Long: buy the crash at a 3.5 % discount.
   - Short: sell the spike at a 5 % premium.
4. Shares are sized so that 1 % of half the capital is risked per trade, given the 40-day ATR.
5. If the order fills, the position is exited at the **same day’s close (MOC)**.
6. No symbol can have more than one simultaneous position from this system.

---

## 7. Considerations for the Python Port

- **Universe Membership**: The RealTest script references the `InRUI` flag provided by Norgate. In Python we require either a similar boolean column or a configuration override; otherwise only the price and liquidity rules can be enforced.
- **Connors RSI**: RealTest’s `CRSI(100,2,2)` maps to “100-bar percent rank, 2-period price RSI, 2-period streak RSI”. Any implementation must respect that argument order.
- **Limit Orders & MOC Exit**: Signals should expose the limit entry price and include metadata indicating that the exit is `MOC` so the execution layer can replicate RealTest behaviour.
- **Position Sizing**: The original template sizes by ATR(40). Our Python backtester should provide compatible sizing logic or document any deviations.

This translation should give strategy developers a precise blueprint to validate or modify the Python implementation without needing to read the RealTest script directly.
