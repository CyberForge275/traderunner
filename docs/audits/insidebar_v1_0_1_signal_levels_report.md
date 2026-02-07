# InsideBar v1.0.1 — Entry/SL/TP Signal Logic (Read‑Only Extract)

Scope: **strategy only** (`src/strategies/inside_bar/**`).  
No code changes. This report extracts the exact signal (entry/SL/TP) logic so another system can re‑implement it from OHLCV.

## 1) Source of Truth (file/line refs)

### Entry/SL/TP calculation + two‑leg emission
- File: `src/strategies/inside_bar/session_logic.py`  
- Lines: ~173–271  
- Key logic: compute entry levels (mother/inside), apply SL cap, compute TP from risk * RRR, emit two `RawSignal` legs (BUY & SELL).

Relevant code anchors:
- `signal_ts = ib_ts + timeframe_minutes` (next bar start)  
  `session_logic.py:175–176`
- Entry mode switch:
  - `entry_mode == "mother_bar"` → entry_long=mother_high, entry_short=mother_low  
  - else `"inside_bar"` → entry_long=ib_high, entry_short=ib_low  
  `session_logic.py:177–182`
- SL/TP with cap:
  - Long SL = mother_low  
  - Short SL = mother_high  
  - Apply `stop_distance_cap_ticks * tick_size` if initial risk too large  
  - TP = entry ± (effective_risk * risk_reward_ratio)  
  `session_logic.py:197–239`
- Two legs emitted:
  - BUY: entry_long, sl_long, tp_long  
  - SELL: entry_short, sl_short, tp_short  
  `session_logic.py:241–271`

### RawSignal model constraints
- File: `src/strategies/inside_bar/models.py`  
- Lines: ~20–41  
Checks:
  - BUY: `stop_loss < entry_price < take_profit`
  - SELL: `take_profit < entry_price < stop_loss`

## 2) Pseudocode (Deterministic, CSV‑replay friendly)

Assumes you already have:
- `mother_high`, `mother_low`, `ib_high`, `ib_low`  
  (from inside‑bar detection; the detection rules are separate and not part of this report)
- `timeframe_minutes`
- Config: `entry_level_mode`, `stop_distance_cap_ticks`, `tick_size`, `risk_reward_ratio`

```
signal_ts = ib_ts + timeframe_minutes

if entry_level_mode == "mother_bar":
    entry_long  = mother_high
    entry_short = mother_low
else:  # inside_bar
    entry_long  = ib_high
    entry_short = ib_low

max_risk = stop_distance_cap_ticks * tick_size

# Long leg
sl_long = mother_low
initial_risk_long = entry_long - sl_long
if initial_risk_long <= 0:
    reject (non_positive_risk)
effective_risk_long = min(initial_risk_long, max_risk)
if initial_risk_long > max_risk:
    sl_long = entry_long - max_risk
tp_long = entry_long + (effective_risk_long * risk_reward_ratio)

# Short leg
sl_short = mother_high
initial_risk_short = sl_short - entry_short
if initial_risk_short <= 0:
    reject (non_positive_risk)
effective_risk_short = min(initial_risk_short, max_risk)
if initial_risk_short > max_risk:
    sl_short = entry_short + max_risk
tp_short = entry_short - (effective_risk_short * risk_reward_ratio)

emit BUY RawSignal:
  timestamp=signal_ts, side="BUY",
  entry_price=entry_long, stop_loss=sl_long, take_profit=tp_long

emit SELL RawSignal:
  timestamp=signal_ts, side="SELL",
  entry_price=entry_short, stop_loss=sl_short, take_profit=tp_short
```

## 3) Notes / Constraints (from code)

- **Two legs always emitted** at IB detection time (no breakout gating in strategy).  
  `session_logic.py:173–271`
- **Netting is not performed in strategy** (explicit comment).  
  `session_logic.py:195`
- **Entry/SL/TP invariants** enforced by `RawSignal` assertions.  
  `models.py:33–41`

## 4) Minimal Inputs Needed for CSV Replay

Per inside‑bar setup (one IB event):
- `ib_ts`
- `mother_high`, `mother_low`
- `ib_high`, `ib_low`
- `entry_level_mode` ("mother_bar" | "inside_bar")
- `stop_distance_cap_ticks`
- `tick_size`
- `risk_reward_ratio`
- `timeframe_minutes`

Outputs:
- Two legs: BUY and SELL with `entry_price`, `stop_loss`, `take_profit`, and `signal_ts`.
