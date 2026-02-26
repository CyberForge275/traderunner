from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from .config import SessionFilter, InsideBarConfig
from .gates import evaluate_deviation_gate
from .levels import capped_risk_levels, entry_levels
from .metadata import build_signal_metadata
from .models import RawSignal
from .session_windows import compute_netting_open_until, session_key_for


def _resolve_breakout_mode(config: InsideBarConfig) -> str:
    mode = getattr(config, "breakout_confirmation_mode", None)
    if mode:
        return str(mode).lower()
    # Legacy behavior stays touch-based unless explicitly enabled in config.
    return "touch"


def generate_signals(
    df: pd.DataFrame,
    symbol: str,
    config: InsideBarConfig,
    tracer: Optional[Callable[[Dict[str, Any]], None]] = None,
    debug_file: Optional[Path] = None,
) -> List[RawSignal]:
    """
    Generate trading signals with First-IB-per-session semantics.

    SPEC: Only the FIRST inside bar per session is traded.
    This is implemented via a session state machine.

    Args:
        df: DataFrame with inside bar detection results
            Must have: timestamp, close, high, low, is_inside_bar,
                      mother_bar_high, mother_bar_low, atr
        symbol: Trading symbol (e.g., 'TSLA')
        tracer: Optional callback for debugging/audit trail

    Returns:
        List of RawSignal objects
    """
    signals: List[RawSignal] = []

    def emit(event: Dict[str, Any]) -> None:
        if tracer is not None:
            tracer(event)

    # Get session configuration
    session_filter = config.session_filter
    if session_filter is None:
        # No session filtering - process all bars
        session_filter = SessionFilter(windows=[])

    session_tz = getattr(config, 'session_timezone', 'Europe/Berlin')

    # DEBUG: Print session config (guaranteed visible)
    print("\n" + "="*70)
    print("[SESSION_FILTER_CONFIG]")
    print(f"  session_tz: {session_tz}")
    print(f"  windows: {session_filter.to_strings() if session_filter and hasattr(session_filter, 'to_strings') else 'empty'}")
    print(f"  windows_count: {len(session_filter.windows) if session_filter else 0}")
    print("="*70 + "\n")

    # DEBUG: Log session filter configuration
    emit({
        'event': 'session_filter_config',
        'session_tz': session_tz,
        'session_windows': session_filter.to_strings() if session_filter and hasattr(session_filter, 'to_strings') else 'empty',
        'windows_count': len(session_filter.windows) if session_filter else 0
    })

    # Session state machine: {session_key: state_dict}
    session_states: Dict[tuple, Dict[str, Any]] = {}

    # Additional hard limit counter (belt-and-suspenders with state machine)
    signals_per_session: Dict[tuple, int] = {}
    max_trades = getattr(config, 'max_trades_per_session', 1)

    # Netting is enforced in fill_model (SSOT). Strategy must not suppress signals.
    netting_mode = getattr(config, 'netting_mode', 'one_position_per_symbol')
    netting_open_until: Optional[pd.Timestamp] = None

    # Inside bar detection requires these columns; ensure present
    required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'atr', 'is_inside_bar', 'mother_bar_high', 'mother_bar_low']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Entry level selection mode
    entry_mode = getattr(config, 'entry_level_mode', 'mother_bar')

    breakout_mode = _resolve_breakout_mode(config)
    max_breakout_range_bars = getattr(config, "max_breakout_range_bars", None)

    # Session / order validity
    validity_policy = getattr(config, 'order_validity_policy', 'session_end')
    validity_minutes = getattr(config, 'order_validity_minutes', 60)
    validity_bars = getattr(config, 'order_validity_bars', 1)

    # Trigger policy
    trigger_must_be_in_session = getattr(config, 'trigger_must_be_within_session', True)

    # Main loop
    for idx, current in df.iterrows():
        ts = pd.to_datetime(current['timestamp'])
        if ts.tzinfo is None:
            ts = ts.tz_localize('UTC')

        session_idx = session_filter.get_session_index(ts, session_tz)

        # Skip if not in any session
        if session_idx is None:
            continue
        session_key = session_key_for(session_filter, ts, session_tz, session_idx)

        # Initialize session state
        if session_key not in session_states:
            session_states[session_key] = {
                'armed': False,
                'done': False,
                'ib_idx': None,
                'levels': {},
            }

        state = session_states[session_key]

        # === STATE: WAITING (look for FIRST inside bar) ===
        if not state['armed'] and not state['done']:
            # Only accept inside bars where mother bar is in same session
            if current['is_inside_bar']:
                prev = df.iloc[idx - 1] if idx > 0 else None
                if prev is None:
                    continue

                # Check if previous bar (mother) is in same session
                prev_ts = pd.to_datetime(prev['timestamp'])
                if prev_ts.tzinfo is None:
                    prev_ts = prev_ts.tz_localize('UTC')

                prev_session_idx = session_filter.get_session_index(prev_ts, session_tz)
                if prev_session_idx != session_idx:
                    emit({
                        'event': 'ib_rejected',
                        'reason': 'mother_bar_outside_session',
                        'idx': int(idx),
                        'current_session': session_idx,
                        'prev_session': prev_session_idx,
                        'session_key': str(session_key)
                    })
                    continue

                # FIRST IB FOUND - ARM SESSION (SSOT: rely on is_inside_bar)
                atr_val = prev['atr'] if 'atr' in prev and pd.notna(prev['atr']) else 0.0
                state['armed'] = True
                state['ib_idx'] = idx
                state['levels'] = {
                    'mother_high': float(prev['high']),
                    'mother_low': float(prev['low']),
                    'ib_high': float(current['high']),
                    'ib_low': float(current['low']),
                    'atr': float(atr_val),
                    'mother_body_fraction': float(current.get('mother_body_fraction', 0.0)),
                    'inside_body_fraction': float(current.get('inside_body_fraction', 0.0)),
                }

                emit({
                    'event': 'ib_armed',
                    'session_key': str(session_key),
                    'ib_idx': int(idx),
                    'ib_ts': ts.isoformat(),
                    'levels': state['levels']
                })
                # NEW: Two-leg OCO signals created at IB detection (no breakout gating here)
                levels = state['levels']
                timeframe_minutes = getattr(config, "timeframe_minutes", None)
                if timeframe_minutes is None:
                    raise ValueError(
                        "timeframe_minutes missing in strategy config (SSOT required, no fallback)"
                    )
                timeframe_minutes = int(timeframe_minutes)
                signal_ts = ts + pd.Timedelta(minutes=timeframe_minutes)
                entry_long, entry_short = entry_levels(entry_mode=entry_mode, levels=levels)

                # === MAX TRADES CHECK (hard limit) ===
                if signals_per_session.get(session_key, 0) >= max_trades:
                    emit({
                        'event': 'signal_rejected',
                        'reason': 'max_trades_reached',
                        'session_key': str(session_key),
                        'count': signals_per_session[session_key]
                    })
                    state['done'] = True
                    continue

            # Netting decision handled in fill_model; do not suppress here.
                (
                    allow_long,
                    allow_short,
                    long_dev_abs,
                    short_dev_abs,
                    long_dev_atr,
                    short_dev_atr,
                    reject_events,
                ) = evaluate_deviation_gate(
                    max_dev_atr=config.max_deviation_atr,
                    atr_for_deviation=float(levels["atr"]),
                    reference_price=float(current["close"]),
                    entry_long=entry_long,
                    entry_short=entry_short,
                    idx=int(idx),
                )
                for event in reject_events:
                    emit(event)
                if reject_events and any(event.get("detail") == "atr_non_positive" for event in reject_events):
                    state["done"] = True
                    continue
                if not allow_long and not allow_short:
                    state["done"] = True
                    continue

                # Long leg SL/TP with ATR cap
                if allow_long:
                    try:
                        sl_long, tp_long, risk_raw_long, risk_cap_long, risk_eff_long, sl_was_capped_long = capped_risk_levels(
                            side="BUY",
                            entry=entry_long,
                            structure_stop=levels['mother_low'],
                            atr_value=levels['atr'],
                            stop_cap_atr=config.stop_cap_atr,
                            risk_reward_ratio=config.risk_reward_ratio,
                        )
                    except ValueError:
                        emit({
                            'event': 'signal_rejected',
                            'reason': 'non_positive_risk',
                            'idx': int(idx),
                            'entry': entry_long,
                            'sl': levels['mother_low'],
                            'side': 'BUY'
                        })
                        allow_long = False

                # Short leg SL/TP with ATR cap
                if allow_short:
                    try:
                        sl_short, tp_short, risk_raw_short, risk_cap_short, risk_eff_short, sl_was_capped_short = capped_risk_levels(
                            side="SELL",
                            entry=entry_short,
                            structure_stop=levels['mother_high'],
                            atr_value=levels['atr'],
                            stop_cap_atr=config.stop_cap_atr,
                            risk_reward_ratio=config.risk_reward_ratio,
                        )
                    except ValueError:
                        emit({
                            'event': 'signal_rejected',
                            'reason': 'non_positive_risk',
                            'idx': int(idx),
                            'entry': entry_short,
                            'sl': levels['mother_high'],
                            'side': 'SELL'
                        })
                        allow_short = False

                if not allow_long and not allow_short:
                    state["done"] = True
                    continue

                # Optional close-confirmation gate (opt-in only).
                confirmation_side: Optional[str] = None
                confirmation_ts: Optional[pd.Timestamp] = None
                confirmation_window_idx: Optional[int] = None
                expire_reason: Optional[str] = None
                if breakout_mode == "close":
                    if max_breakout_range_bars is None:
                        raise ValueError("max_breakout_range_bars required when breakout_confirmation_mode=close")
                    window = int(max_breakout_range_bars)
                    for w in range(1, window + 1):
                        probe_idx = idx + w
                        if probe_idx >= len(df):
                            break
                        probe = df.iloc[probe_idx]
                        probe_ts = pd.to_datetime(probe["timestamp"], utc=True)
                        probe_session_idx = session_filter.get_session_index(probe_ts, session_tz)
                        if probe_session_idx != session_idx:
                            break
                        close_px = float(probe["close"])
                        if allow_long and close_px > float(entry_long):
                            confirmation_side = "BUY"
                            confirmation_ts = probe_ts
                            confirmation_window_idx = w
                            break
                        if allow_short and close_px < float(entry_short):
                            confirmation_side = "SELL"
                            confirmation_ts = probe_ts
                            confirmation_window_idx = w
                            break
                    if confirmation_side is None:
                        expire_reason = "max_breakout_range"
                        emit(
                            {
                                "event": "setup_expired",
                                "reason": expire_reason,
                                "idx": int(idx),
                                "window_bars": window,
                            }
                        )
                        state["done"] = True
                        continue
                    signal_ts = confirmation_ts + pd.Timedelta(minutes=timeframe_minutes)

                # Emit legs (legacy touch mode: OCO both sides; close mode: confirmed side only)
                if allow_long and (breakout_mode != "close" or confirmation_side == "BUY"):
                    signals.append(
                        RawSignal(
                            timestamp=signal_ts,
                            side='BUY',
                            entry_price=entry_long,
                            stop_loss=sl_long,
                            take_profit=tp_long,
                            metadata=build_signal_metadata(
                                session_key=session_key,
                                ib_idx=state['ib_idx'],
                                entry_mode=entry_mode,
                                sl_was_capped=sl_was_capped_long,
                                risk_raw=risk_raw_long,
                                risk_cap=risk_cap_long,
                                risk_eff=risk_eff_long,
                                mother_high=levels['mother_high'],
                                mother_low=levels['mother_low'],
                                atr=levels['atr'],
                                symbol=symbol,
                                deviation_abs=long_dev_abs,
                                deviation_atr=long_dev_atr,
                                mother_body_fraction=levels.get('mother_body_fraction'),
                                inside_body_fraction=levels.get('inside_body_fraction'),
                                extra={
                                    "breakout_confirmation_mode": breakout_mode,
                                    "breakout_long_close_confirmed": breakout_mode == "close" and confirmation_side == "BUY",
                                    "breakout_short_close_confirmed": False,
                                    "entry_long_effective": breakout_mode != "close" or confirmation_side == "BUY",
                                    "entry_short_effective": False,
                                    "setup_armed_ts": ts,
                                    "confirm_ts": confirmation_ts,
                                    "window_idx": confirmation_window_idx,
                                    "entry_valid_from_ts": signal_ts,
                                    "setup_expire_reason": expire_reason,
                                },
                            ),
                        )
                    )
                if allow_short and (breakout_mode != "close" or confirmation_side == "SELL"):
                    signals.append(
                        RawSignal(
                            timestamp=signal_ts,
                            side='SELL',
                            entry_price=entry_short,
                            stop_loss=sl_short,
                            take_profit=tp_short,
                            metadata=build_signal_metadata(
                                session_key=session_key,
                                ib_idx=state['ib_idx'],
                                entry_mode=entry_mode,
                                sl_was_capped=sl_was_capped_short,
                                risk_raw=risk_raw_short,
                                risk_cap=risk_cap_short,
                                risk_eff=risk_eff_short,
                                mother_high=levels['mother_high'],
                                mother_low=levels['mother_low'],
                                atr=levels['atr'],
                                symbol=symbol,
                                deviation_abs=short_dev_abs,
                                deviation_atr=short_dev_atr,
                                mother_body_fraction=levels.get('mother_body_fraction'),
                                inside_body_fraction=levels.get('inside_body_fraction'),
                                extra={
                                    "breakout_confirmation_mode": breakout_mode,
                                    "breakout_long_close_confirmed": False,
                                    "breakout_short_close_confirmed": breakout_mode == "close" and confirmation_side == "SELL",
                                    "entry_long_effective": False,
                                    "entry_short_effective": breakout_mode != "close" or confirmation_side == "SELL",
                                    "setup_armed_ts": ts,
                                    "confirm_ts": confirmation_ts,
                                    "window_idx": confirmation_window_idx,
                                    "entry_valid_from_ts": signal_ts,
                                    "setup_expire_reason": expire_reason,
                                },
                            ),
                        )
                    )
                state['done'] = True
                signals_per_session[session_key] = signals_per_session.get(session_key, 0) + 1

                # Netting open window tracked in fill_model; no strategy-level suppression.

                emit({
                    'event': 'signal_generated_oco',
                    'session_key': str(session_key),
                    'entry_long': entry_long,
                    'entry_short': entry_short,
                    'sl_long': sl_long,
                    'tp_long': tp_long,
                    'sl_short': sl_short,
                    'tp_short': tp_short
                })
                continue

        # === STATE: ARMED (watch for breakout of THE FIRST IB) ===
        if state['armed'] and not state['done']:
            levels = state['levels']

            # Determine entry levels based on entry_level_mode
            entry_long, entry_short = entry_levels(entry_mode=entry_mode, levels=levels)

            # === MAX TRADES CHECK (hard limit) ===
            if signals_per_session.get(session_key, 0) >= max_trades:
                emit({
                    'event': 'signal_rejected',
                    'reason': 'max_trades_reached',
                    'session_key': str(session_key),
                    'count': signals_per_session[session_key]
                })
                state['done'] = True  # Mark session done
                continue

            # === NETTING CHECK (MVP: 1 position per symbol) ===
            if netting_mode == "one_position_per_symbol" and netting_open_until is not None:
                # Check if trigger_ts overlaps with existing position window
                if ts < netting_open_until:
                    emit({
                        'event': 'signal_rejected',
                        'reason': 'netting_blocked_position_open',
                        'netting_mode': netting_mode,
                        'symbol': symbol,
                        'trigger_ts': ts.isoformat(),
                        'open_until': netting_open_until.isoformat()
                    })
                    continue
                # else: ts >= netting_open_until, previous position window closed

            # Check LONG breakout (intraday: trigger on high)
            if current['high'] > entry_long:
                # === MVP: TRIGGER MUST BE WITHIN SESSION ===
                if trigger_must_be_in_session:
                    # Trigger timestamp = current bar timestamp (breakout confirmed on close)
                    trigger_ts = ts
                    trigger_in_session = session_filter.is_in_session(trigger_ts, session_tz)

                    if not trigger_in_session:
                        emit({
                            'event': 'signal_rejected',
                            'reason': 'trigger_outside_session',
                            'idx': int(idx),
                            'trigger_ts': trigger_ts.isoformat(),
                            'trigger_ts_local': trigger_ts.tz_convert(session_tz).strftime('%H:%M'),
                            'side': 'BUY'
                        })
                        continue
                # Calculate SL/TP with ATR cap
                try:
                    sl, tp, risk_raw, risk_cap, risk_eff, sl_was_capped = capped_risk_levels(
                        side="BUY",
                        entry=entry_long,
                        structure_stop=levels['mother_low'],
                        atr_value=levels['atr'],
                        stop_cap_atr=config.stop_cap_atr,
                        risk_reward_ratio=config.risk_reward_ratio,
                    )
                except ValueError:
                    emit({
                        'event': 'signal_rejected',
                        'reason': 'non_positive_risk',
                        'idx': int(idx),
                        'entry': entry_long,
                        'sl': levels['mother_low']
                    })
                    continue

                signal = RawSignal(
                    timestamp=ts,
                    side='BUY',
                    entry_price=entry_long,
                    stop_loss=sl,
                    take_profit=tp,
                    metadata=build_signal_metadata(
                        session_key=session_key,
                        ib_idx=state['ib_idx'],
                        entry_mode=entry_mode,
                        sl_was_capped=sl_was_capped,
                        risk_raw=risk_raw,
                        risk_cap=risk_cap,
                        risk_eff=risk_eff,
                        mother_high=levels['mother_high'],
                        mother_low=levels['mother_low'],
                        atr=levels['atr'],
                        symbol=symbol,
                    ),
                )
                signals.append(signal)
                state['done'] = True
                signals_per_session[session_key] = signals_per_session.get(session_key, 0) + 1

                # === NETTING: Calculate position open_until (conservative) ===
                netting_open_until = compute_netting_open_until(
                    validity_policy=validity_policy,
                    validity_minutes=validity_minutes,
                    validity_bars=validity_bars,
                    session_filter=session_filter,
                    ts=ts,
                    session_tz=session_tz,
                )

                emit({
                    'event': 'signal_generated',
                    'side': 'BUY',
                    'session_key': str(session_key),
                    'entry': entry_long,
                    'sl': sl,
                    'tp': tp,
                    'stop_cap_applied': sl_was_capped
                })

            # Check SHORT breakout (intraday: trigger on low)
            elif current['low'] < entry_short:
                # === MVP: TRIGGER MUST BE WITHIN SESSION ===
                if trigger_must_be_in_session:
                    trigger_ts = ts
                    trigger_in_session = session_filter.is_in_session(trigger_ts, session_tz)

                    if not trigger_in_session:
                        emit({
                            'event': 'signal_rejected',
                            'reason': 'trigger_outside_session',
                            'idx': int(idx),
                            'trigger_ts': trigger_ts.isoformat(),
                            'trigger_ts_local': trigger_ts.tz_convert(session_tz).strftime('%H:%M'),
                            'side': 'SELL'
                        })
                        continue
                # Calculate SL/TP with ATR cap
                try:
                    sl, tp, risk_raw, risk_cap, risk_eff, sl_was_capped = capped_risk_levels(
                        side="SELL",
                        entry=entry_short,
                        structure_stop=levels['mother_high'],
                        atr_value=levels['atr'],
                        stop_cap_atr=config.stop_cap_atr,
                        risk_reward_ratio=config.risk_reward_ratio,
                    )
                except ValueError:
                    emit({
                        'event': 'signal_rejected',
                        'reason': 'non_positive_risk',
                        'idx': int(idx),
                        'entry': entry_short,
                        'sl': levels['mother_high']
                    })
                    continue

                signal = RawSignal(
                    timestamp=ts,
                    side='SELL',
                    entry_price=entry_short,
                    stop_loss=sl,
                    take_profit=tp,
                    metadata=build_signal_metadata(
                        session_key=session_key,
                        ib_idx=state['ib_idx'],
                        entry_mode=entry_mode,
                        sl_was_capped=sl_was_capped,
                        risk_raw=risk_raw,
                        risk_cap=risk_cap,
                        risk_eff=risk_eff,
                        mother_high=levels['mother_high'],
                        mother_low=levels['mother_low'],
                        atr=levels['atr'],
                        symbol=symbol,
                    ),
                )
                signals.append(signal)
                state['done'] = True
                signals_per_session[session_key] = signals_per_session.get(session_key, 0) + 1

                # Netting open window tracked in fill_model; no strategy-level suppression.

                emit({
                    'event': 'signal_generated',
                    'side': 'SELL',
                    'session_key': str(session_key),
                    'entry': entry_short,
                    'sl': sl,
                    'tp': tp,
                    'stop_cap_applied': sl_was_capped
                })

    return signals
