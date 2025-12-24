# Inside Bar Strategy - Live Paper Trading Integration

> **Last Updated**: 2025-12-05
> **Config Location**: `droid/shared-config/strategy_params.yaml`
> **Current RRR**: 1.0 (matches backtest)

## Overview

This document explains how the Inside Bar strategy adapts from backtesting to live paper trading with real-time WebSocket data, including:
1. Mother Bar detection from live ticks
2. Buy/Sell order triggering
3. Stop Loss (SL) and Take Profit (TP) management strategies

---

## System Architecture

```
┌──────────────────────┐
│ marketdata-stream    │
│ (WebSocket Provider) │
└──────┬───────────────┘
       │ Market Data Events (tick-by-tick)
       ▼
┌──────────────────────┐
│  CandleAggregator    │  ← Real-time M5 candles
│  (M1, M5, M15 etc.)  │
└──────┬───────────────┘
       │ Candle Completion Events
       ▼
┌──────────────────────┐
│  InsideBarStrategy   │  ← Detect inside bars & breakouts
│  (Pattern Detection) │
└──────┬───────────────┘
       │ Signals (LONG/SHORT + entry/SL/TP)
       ▼
┌──────────────────────┐
│ PaperTradingAdapter  │  ← Transform to order intents
└──────┬───────────────┘
       │ HTTP POST (order intent)
       ▼
┌──────────────────────┐
│ automatictrader-api  │  ← Idempotency & planning
│ (FastAPI + Worker)   │
└──────┬───────────────┘
       │
       ├─────────────────┐
       ▼                 ▼
  [Bracket Orders]  [Local Monitor]
  in IB TWS         via WebSocket
```

---

## Part 1: Mother Bar Detection from WebSocket Data

###  1.1 WebSocket → Candles Pipeline

**Data Flow:**

```python
# marketdata-stream receives tick data
MarketDataEvent:
  symbol = "AAPL"
  price = 227.35
  volume = 100
  ts = 2024-11-28T15:32:12Z

    ↓ (CandleAggregator.on_event)

# Aggregator creates M5 candles
Candle (M5):
  symbol = "AAPL"
  interval = "M5"
  open = 227.30
  high = 227.45
  low = 227.25
  close = 227.35
  volume = 15000
  timestamp = 1732805400000  # 15:30:00
  complete = True  # ← Candle just closed!
```

**Implementation (already exists):**

From [`candle_aggregator.py`](file:///home/mirko/data/workspace/droid/marketdata-stream/src/aggregators/candle_aggregator.py):

```python
class CandleAggregator:
    async def on_event(self, event: MarketDataEvent) -> None:
        """Process tick → update candles"""
        for interval in self.intervals:  # ["M1", "M5", "M15"]
            await self._update_candle(symbol, interval, price, volume, timestamp)

    async def _update_candle(self, symbol, interval, price, volume, timestamp_sec):
        """Creates/updates candle, triggers completion handlers"""
        # When candle period changes:
        if current candle timestamp != new candle timestamp:
            current.complete = True
            self.candle_history[symbol][interval].append(current)

            # 🔥 TRIGGER COMPLETION HANDLERS
            for handler in self.completion_handlers:
                await handler(current)  # ← Strategy listens here!
```

### 1.2 Inside Bar Detection on Live Candles

**Subscribe to candle completions:**

```python
# New component: inside_bar_live_detector.py
from marketdata_stream.aggregators import CandleAggregator
from traderunner.strategies.inside_bar import InsideBarStrategy

class InsideBarLiveDetector:
    def __init__(self, aggregator: CandleAggregator, strategy: InsideBarStrategy):
        self.aggregator = aggregator
        self.strategy = strategy
        self.candle_buffer = {}  # {symbol: deque([Candle])}

        # Subscribe to M5 candle completions
        aggregator.subscribe_completion(self.on_candle_complete)

    async def on_candle_complete(self, candle: Candle):
        """Called when M5 candle completes"""
        if candle.interval != "M5":
            return

        symbol = candle.symbol

        # Maintain rolling buffer (need 2+ candles to detect inside bar)
        if symbol not in self.candle_buffer:
            self.candle_buffer[symbol] = deque(maxlen=100)

        self.candle_buffer[symbol].append(candle)

        # Need at least 2 candles to check for inside bar
        if len(self.candle_buffer[symbol]) < 2:
            return

        # Convert to DataFrame for strategy
        df = self._candles_to_dataframe(self.candle_buffer[symbol])

        # Run inside bar detection
        signals = self.strategy.generate_signals(df, symbol, config={
            "atr_period": 14,
            "risk_reward_ratio": 1.0,  # Matches backtest
            "inside_bar_mode": "inclusive",
            "breakout_confirmation": True
        })

        # Process signals
        for signal in signals:
            await self._handle_signal(signal)

    def _candles_to_dataframe(self, candles: deque) -> pd.DataFrame:
        """Convert deque of Candle objects to DataFrame"""
        data = []
        for c in candles:
            data.append({
                'timestamp': pd.Timestamp(c.timestamp, unit='ms'),
                'open': c.open,
                'high': c.high,
                'low': c.low,
                'close': c.close,
                'volume': c.volume
            })
        return pd.DataFrame(data)

    async def _handle_signal(self, signal: Signal):
        """Send signal to paper trading adapter"""
        # Signal contains:
        # - entry_price (mother bar high/low)
        # - stop_loss (mother bar low/high)
        # - take_profit (calculated from RRR)

        logger.info(f"Signal generated: {signal.signal_type} {signal.symbol} @ {signal.entry_price}")
        # TODO: Send to automatictrader-api
```

**Mother Bar Identification:**

From the strategy code, the mother bar is the candle **immediately before** the inside bar:

```python
# From InsideBarStrategy._detect_inside_bars()
df["prev_high"] = df["high"].shift(1)  # Mother bar high
df["prev_low"] = df["low"].shift(1)    # Mother bar low

# Inside bar condition: current bar within previous bar's range
inside_mask = (df["high"] <= df["prev_high"]) & (df["low"] >= df["prev_low"])

# Store mother bar levels for breakout detection
df["mother_bar_high"] = df["prev_high"].where(inside_mask)
df["mother_bar_low"] = df["prev_low"].where(inside_mask)
```

**When does it trigger?**

```python
# From _generate_breakout_signals()
# Breakout occurs when price closes beyond mother bar
long_condition = valid_active & (df["close"] > df["mother_high_active"])
short_condition = valid_active & (df["close"] < df["mother_low_active"])

# Signal metadata includes:
signal = Signal(
    timestamp=...,
    symbol="AAPL",
    signal_type="LONG",  # or "SHORT"
    entry_price=mother_bar_high,  # Buy above mother high
    stop_loss=mother_bar_low,      # Stop below mother low
    take_profit=mother_bar_high + (risk * rrr),  # RRR-based target
    confidence=0.8,
    metadata={
        "pattern": "inside_bar_breakout",
        "mother_bar_high": 227.50,
        "mother_bar_low": 227.10,
        "atr": 1.25,
        "risk_amount": 0.40,
        "reward_amount": 0.40  # 1:1 RRR
    }
)
```

---

## Part 2: Order Triggering for Paper Trading

### 2.1 Signal → Order Intent Transformation

**Current Implementation (Paper Trading Adapter):**

From [`paper_trading_adapter.py`](file:///home/mirko/data/workspace/droid/traderunner/src/trade/paper_trading_adapter.py):

```python
def send_signal_as_intent(self, signal_row: dict) -> dict:
    """Transform traderunner signal → automatictrader order intent"""

    # Generate deterministic idempotency key (prevents duplicates)
    idem_key = self._generate_idempotency_key(signal_row)

    intent = {
        "symbol": signal_row["symbol"].upper(),
        "side": signal_row["side"].upper(),  # BUY or SELL
        "quantity": int(signal_row["qty"]),
        "order_type": signal_row.get("order_type", "LMT").upper(),
        "price": float(signal_row["price"]),  # Entry price
        "client_tag": "traderunner_inside_bar"
    }

    # POST to automatictrader-api
    resp = requests.post(
        f"{self.api_url}/api/v1/orderintents",
        json=intent,
        headers={"Idempotency-Key": idem_key}
    )
```

**What happens on automatictrader-api side:**

```python
# From automatictrader-api/worker.py

# 1. Intent stored in database (status: pending)
# 2. Worker picks it up: pending → planning
# 3. Creates order plan (validates with SPT/IB)
# 4. Status: planned → ready (if auto-promote enabled)
# 5. Status: ready → sending → sent (places order in IB)
```

### 2.2 Live Integration Flow

```python
# Complete live trading flow
class InsideBarLiveTradingSystem:
    def __init__(self):
        self.aggregator = CandleAggregator(intervals=["M5"])
        self.strategy = InsideBarStrategy()
        self.detector = InsideBarLiveDetector(self.aggregator, self.strategy)
        self.adapter = PaperTradingAdapter(api_url="http://localhost:8080")

    async def on_candle_complete(self, candle: Candle):
        """Triggered when M5 candle completes"""
        signals = await self.detector.check_for_signals(candle)

        for signal in signals:
            # Convert Signal object to order intent
            order = {
                "symbol": signal.symbol,
                "side": "BUY" if signal.signal_type == "LONG" else "SELL",
                "qty": self._calculate_position_size(signal),
                "order_type": "LMT",
                "price": signal.entry_price,
                "timestamp": signal.timestamp,
                "source": "inside_bar_live"
            }

            # Send to automatictrader-api
            result = self.adapter.send_signal_as_intent(order)
            logger.info(f"Order intent sent: {result}")
```

---

## Part 3: Stop Loss & Take Profit Management

### 🔑 Critical Decision: TWO APPROACHES

#### **Option A: Native IB Bracket Orders (RECOMMENDED)**

**Pros:**
- ✅ Executed by IB servers (continues working if your system crashes)
- ✅ Lower latency (no WebSocket monitoring loop)
- ✅ IB handles all edge cases (partial fills, price improvements, etc.)
- ✅ Reliable execution even during network issues

**Cons:**
- ❌ Less flexible (can't easily adjust based on evolving patterns)
- ❌ Requires IB API bracket order submission

**Implementation:**

```python
# In automatictrader-api/worker.py (enhanced)
def _process_ready_to_send_with_bracket(st: Storage) -> None:
    """Send main order + SL + TP as bracket order"""
    job = st.claim_ready_to_send()

    from ib_insync import IB, Stock, LimitOrder, Order

    ib = IB()
    ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)

    # Main entry order
    contract = Stock(job["symbol"], 'SMART', 'USD')
    ib.qualifyContracts(contract)

    parent_order = LimitOrder(
        action=job["side"],  # BUY or SELL
        totalQuantity=job["quantity"],
        lmtPrice=job["price"]
    )
    parent_order.orderId = ib.client.getReqId()
    parent_order.transmit = False  # Don't transmit until bracket complete

    # Stop Loss order (opposite side)
    stop_order = Order()
    stop_order.orderId = parent_order.orderId + 1
    stop_order.action = "SELL" if job["side"] == "BUY" else "BUY"
    stop_order.orderType = "STP"
    stop_order.auxPrice = job["stop_loss"]  # ← From signal metadata
    stop_order.totalQuantity = job["quantity"]
    stop_order.parentId = parent_order.orderId
    stop_order.transmit = False

    # Take Profit order (opposite side)
    profit_order = Order()
    profit_order.orderId = parent_order.orderId + 2
    profit_order.action = "SELL" if job["side"] == "BUY" else "BUY"
    profit_order.orderType = "LMT"
    profit_order.lmtPrice = job["take_profit"]  # ← From signal metadata
    profit_order.totalQuantity = job["quantity"]
    profit_order.parentId = parent_order.orderId
    profit_order.transmit = True  # Transmit entire bracket

    # Submit bracket (all 3 orders)
    parent_trade = ib.placeOrder(contract, parent_order)
    stop_trade = ib.placeOrder(contract, stop_order)
    profit_trade = ib.placeOrder(contract, profit_order)

    ib.disconnect()
```

**Data Structure Enhancement:**

```python
# Extend order intent schema in automatictrader-api
intent = {
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 10,
    "order_type": "LMT",
    "price": 227.50,  # Entry
    "stop_loss": 227.10,  # ← ADD THIS
    "take_profit": 227.90,  # ← ADD THIS
    "bracket_order": True  # ← FLAG for bracket handling
}
```

---

#### **Option B: Local WebSocket Monitor (MORE FLEXIBLE)**

**Pros:**
- ✅ Complete control over exit logic
- ✅ Can trail stops based on new inside bar formations
- ✅ Can cancel/modify based on new market data
- ✅ Can implement advanced exit rules (e.g., time-based, pattern-based)

**Cons:**
- ❌ Must run continuously (WebSocket connection required)
- ❌ Higher latency (tick → decision → order submission)
- ❌ System crash = no stop loss protection
- ❌ More complex to implement and maintain

**Implementation:**

```python
class LivePositionMonitor:
    """Monitors positions via WebSocket and triggers SL/TP locally"""

    def __init__(self, aggregator: CandleAggregator):
        self.positions = {}  # {symbol: Position}
        self.aggregator = aggregator

        # Subscribe to tick updates
        aggregator.subscribe_completion(self.on_tick)

    async def on_tick(self, event: MarketDataEvent):
        """Check if SL or TP hit on every tick"""
        symbol = event.symbol
        price = event.price

        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        # Check Stop Loss
        if position.side == "LONG" and price <= position.stop_loss:
            await self._close_position(symbol, price, "STOP_LOSS")
        elif position.side == "SHORT" and price >= position.stop_loss:
            await self._close_position(symbol, price, "STOP_LOSS")

        # Check Take Profit
        if position.side == "LONG" and price >= position.take_profit:
            await self._close_position(symbol, price, "TAKE_PROFIT")
        elif position.side == "SHORT" and price <= position.take_profit:
            await self._close_position(symbol, price, "TAKE_PROFIT")

    async def _close_position(self, symbol: str, price: float, reason: str):
        """Submit market order to close position"""
        position = self.positions[symbol]

        close_order = {
            "symbol": symbol,
            "side": "SELL" if position.side == "LONG" else "BUY",
            "qty": position.quantity,
            "order_type": "MKT",  # Market order for immediate exit
            "source": f"inside_bar_{reason.lower()}"
        }

        adapter = PaperTradingAdapter()
        result = adapter.send_signal_as_intent(close_order)

        logger.info(f"Position closed: {symbol} @ {price} ({reason})")
        del self.positions[symbol]
```

---

## Recommendation: **Hybrid Approach**

Best of both worlds:

1. **Use IB Bracket Orders for protection** (Option A)
   - Always submit SL as part of bracket
   - Protects against system failures

2. **Add WebSocket Monitor for trailing/modifications** (Option B)
   - Monitor position in real-time
   - Can modify stop loss if new inside bar forms (trailing)
   - Can take partial profits at interim levels

```python
class HybridSLTPManager:
    def __init__(self):
        self.ib_bracket = True  # Always use IB bracket
        self.monitor_enabled = True  # Monitor for trailing

    async def on_entry_filled(self, fill_event):
        """Called when entry order fills"""
        symbol = fill_event.symbol

        # IB bracket already active (SL/TP set)
        # Now monitor for trailing opportunities

        if self.monitor_enabled:
            await self.start_trailing_logic(symbol)

    async def start_trailing_logic(self, symbol):
        """Adjust SL based on new inside bars (optional enhancement)"""
        # Example: If new inside bar forms in direction of trade,
        # move stop loss to break-even or trailing level
        pass
```

---

## Summary & Architecture Recommendations

### ✅ Recommended Architecture

```
marketdata-stream (WebSocket EODHD)
    ↓ ticks
CandleAggregator (M5 candles)
    ↓ candle completion events
InsideBarLiveDetector (pattern detection)
    ↓ signals with entry/SL/TP
PaperTradingAdapter (API client)
    ↓ HTTP POST with bracket data
automatictrader-api (order management)
    ↓ IB-ready commands
Interactive Brokers TWS
    → [Bracket Order: Entry + SL + TP]
```

### 🔑 Key Implementation Steps

1. **Enhance automatictrader-api schema** to accept `stop_loss` and `take_profit`
2. **Modify worker.py** to support IB bracket order submission
3. **Create InsideBarLiveDetector** component in traderunner
4. **Include SL/TP in signal metadata** from InsideBarStrategy
5. **Update PaperTradingAdapter** to pass SL/TP to API

### 📊 Data Flow Example

```json
// Signal from InsideBarStrategy
{
  "timestamp": "2024-11-28T15:35:00Z",
  "symbol": "AAPL",
  "signal_type": "LONG",
  "entry_price": 227.50,
  "stop_loss": 227.10,
  "take_profit": 227.90,
  "confidence": 0.8,
  "metadata": {
    "pattern": "inside_bar_breakout",
    "mother_bar_high": 227.50,
    "mother_bar_low": 227.10,
    "atr": 1.25,
    "risk_amount": 0.40,
    "reward_amount": 0.80
  }
}

// Order Intent to automatictrader-api
{
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 10,
  "order_type": "LMT",
  "price": 227.50,
  "stop_loss": 227.10,      // NEW
  "take_profit": 227.90,    // NEW
  "bracket_order": true,    // NEW
  "client_tag": "inside_bar_live"
}

// IB Bracket Orders (automatic)
[
  Order(id=1, type=LMT, action=BUY,  qty=10, price=227.50, parent=None),
  Order(id=2, type=STP, action=SELL, qty=10, price=227.10, parent=1),
  Order(id=3, type=LMT, action=SELL, qty=10, price=227.90, parent=1)
]
```

---

**Next Steps:** Would you like me to implement the `InsideBarLiveDetector` component or enhance the automatictrader-api to support bracket orders?
