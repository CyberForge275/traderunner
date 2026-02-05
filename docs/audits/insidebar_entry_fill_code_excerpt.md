# InsideBar Entry Fill – Code Excerpts (Signal + Fill)

## Signal / Intent build (entry_price source)
```py
# src/axiom_bt/pipeline/signals.py
signal_ts = pd.to_datetime(sig["timestamp"], utc=True)
intent = {
    "template_id": str(sig["template_id"]),
    "signal_ts": signal_ts,
    "symbol": sig["symbol"],
    "side": sig["signal_side"],
    "entry_price": float(sig["entry_price"]) if pd.notna(sig["entry_price"]) else None,
    "stop_price": float(sig["stop_price"]) if pd.notna(sig["stop_price"]) else None,
    "take_profit_price": float(sig["take_profit_price"]) if pd.notna(sig["take_profit_price"]) else None,
    "strategy_id": strategy_id,
    "strategy_version": strategy_version,
}
```

## Fill model (entry stop/cross logic)
```py
# src/axiom_bt/pipeline/fill_model.py
price, reason_code = _entry_fill_stop_cross(
    side,
    float(trigger_level),
    bar,
)
logger.info(
    "actions: entry_fill_stop_cross side=%s trig=%s open=%s high=%s low=%s fill=%s reason=%s template_id=%s signal_ts=%s",
    side,
    float(trigger_level),
    float(bar.get("open", float("nan"))),
    float(bar.get("high", float("nan"))),
    float(bar.get("low", float("nan"))),
    float(price),
    reason_code,
    intent.get("template_id"),
    ts,
)
```
