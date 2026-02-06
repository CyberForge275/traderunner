# OCO Architecture Evidence (SSOT → Intent → Fill → Execution)

| Statement | True/False | Evidence (File:Line) | Comment |
|---|---|---|---|
| A1) Strategy builds SignalFrame only (no fills/trades) | True | src/strategies/inside_bar/__init__.py:129-206 | Signals mapped into SignalFrame; no fill/trade artifacts in strategy layer. |
| A2) events_intent built once from signals_frame, then frozen | True | src/axiom_bt/pipeline/signals.py:64-189 | generate_intent builds events_intent from signals_frame and logs intent_frozen. |
| A3) Trigger scan/fills only in fill_model using entry_price | True | src/axiom_bt/pipeline/fill_model.py:65-215 | generate_fills scans bars and uses entry_price for trigger/price. |
| A4) Trades only from signal_fill, cancel/ambiguous ignored | True | src/axiom_bt/pipeline/execution.py:62-84 | entry_fills filtered by reason==signal_fill; exits filtered to stop_loss/take_profit/session_end. |
| A5) Netting enforced in fill layer (not strategy) | True | src/axiom_bt/pipeline/fill_model.py:120-165 | netting block emits order_rejected_netting_open_position; strategy no longer suppresses. |
| A6) signal_ts is next bar after IB | True | src/strategies/inside_bar/session_logic.py:150-161 | RawSignal.timestamp set to ib_ts + timeframe_minutes. |
