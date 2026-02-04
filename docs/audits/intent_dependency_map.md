# Intent dependency map

Run: 260202_090827__HOOD_IB_maxLossPCT001_300d

Columns:
- template_id: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- signal_ts: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- symbol: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- side: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- entry_price: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- stop_price: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- take_profit_price: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- exit_ts: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=scheduled_at_signal_time (future), risk=potential_lookahead
- exit_reason: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=scheduled_at_signal_time (future), risk=potential_lookahead
- strategy_id: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=params, time=unknown, risk=low
- strategy_version: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=params, time=unknown, risk=low
- breakout_confirmation: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=params, time=unknown, risk=low
- dbg_signal_ts_ny: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_signal_ts_berlin: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_effective_valid_from_policy: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_valid_to_ts_utc: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=scheduled_at_signal_time (future), risk=potential_lookahead
- dbg_valid_to_ts_ny: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=scheduled_at_signal_time (future), risk=potential_lookahead
- dbg_valid_to_ts: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=scheduled_at_signal_time (future), risk=potential_lookahead
- dbg_exit_ts_ny: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=scheduled_at_signal_time (future), risk=potential_lookahead
- dbg_valid_from_ts_utc: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_valid_from_ts: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_valid_from_ts_ny: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- sig_atr: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- sig_inside_bar: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- sig_mother_high: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- sig_mother_low: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- sig_entry_price: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- sig_stop_price: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- sig_take_profit_price: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- sig_mother_ts: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- sig_inside_ts: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame, time=known_at_signal_close, risk=low
- dbg_breakout_level: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_mother_high: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_mother_low: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_mother_ts: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_inside_ts: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_trigger_ts: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=strategy_defined (often signal_ts), risk=potential_lookahead
- dbg_order_expired: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_order_expire_reason: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
- dbg_mother_range: producer=signals.generate_intent (src/axiom_bt/pipeline/signals.py:63-176), source=signals_frame/params, time=known_at_signal_close, risk=low
