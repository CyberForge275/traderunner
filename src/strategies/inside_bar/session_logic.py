from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from .config import SessionFilter, InsideBarConfig
from .models import RawSignal


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

    def _session_key_for(ts: pd.Timestamp, session_idx: int) -> tuple:
        try:
            return session_filter.get_session_key(ts, session_tz)  # type: ignore[attr-defined]
        except AttributeError:
            session_start = session_filter.get_session_start(ts, session_tz)
            return (session_idx, session_start)

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

    # Breakout confirmation (optional; if True, only trigger if close confirms)
    breakout_confirmation = getattr(config, 'breakout_confirmation', True)

    # Session / order validity
    validity_policy = getattr(config, 'order_validity_policy', 'session_end')
    validity_minutes = getattr(config, 'order_validity_minutes', 60)

    # Trigger policy
    trigger_must_be_in_session = getattr(config, 'trigger_must_be_within_session', True)

    # Risk management
    max_risk = getattr(config, 'stop_distance_cap_ticks', 40) * getattr(config, 'tick_size', 0.01)

    # Main loop
    for idx, current in df.iterrows():
        ts = pd.to_datetime(current['timestamp'])
        if ts.tzinfo is None:
            ts = ts.tz_localize('UTC')

        session_idx = session_filter.get_session_index(ts, session_tz)

        # Skip if not in any session
        if session_idx is None:
            continue
        session_key = _session_key_for(ts, session_idx)

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
                    'atr': float(atr_val)
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
                if entry_mode == "mother_bar":
                    entry_long = levels['mother_high']
                    entry_short = levels['mother_low']
                else:  # inside_bar
                    entry_long = levels['ib_high']
                    entry_short = levels['ib_low']

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

                # Long leg SL/TP with cap
                sl_long = levels['mother_low']
                initial_risk_long = entry_long - sl_long
                if initial_risk_long <= 0:
                    emit({
                        'event': 'signal_rejected',
                        'reason': 'non_positive_risk',
                        'idx': int(idx),
                        'entry': entry_long,
                        'sl': sl_long,
                        'side': 'BUY'
                    })
                    state['done'] = True
                    continue
                effective_risk_long = initial_risk_long
                stop_cap_applied_long = False
                if initial_risk_long > max_risk:
                    sl_long = entry_long - max_risk
                    effective_risk_long = max_risk
                    stop_cap_applied_long = True
                tp_long = entry_long + (effective_risk_long * config.risk_reward_ratio)

                # Short leg SL/TP with cap
                sl_short = levels['mother_high']
                initial_risk_short = sl_short - entry_short
                if initial_risk_short <= 0:
                    emit({
                        'event': 'signal_rejected',
                        'reason': 'non_positive_risk',
                        'idx': int(idx),
                        'entry': entry_short,
                        'sl': sl_short,
                        'side': 'SELL'
                    })
                    state['done'] = True
                    continue
                effective_risk_short = initial_risk_short
                stop_cap_applied_short = False
                if initial_risk_short > max_risk:
                    sl_short = entry_short + max_risk
                    effective_risk_short = max_risk
                    stop_cap_applied_short = True
                tp_short = entry_short - (effective_risk_short * config.risk_reward_ratio)

                # Emit two legs (BUY + SELL) for OCO
                signals.append(
                    RawSignal(
                        timestamp=signal_ts,
                        side='BUY',
                        entry_price=entry_long,
                        stop_loss=sl_long,
                        take_profit=tp_long,
                        metadata={
                            'pattern': 'inside_bar_breakout',
                            'session_key': str(session_key),
                            'ib_idx': state['ib_idx'],
                            'entry_mode': entry_mode,
                            'stop_cap_applied': stop_cap_applied_long,
                            'initial_risk': initial_risk_long,
                            'effective_risk': effective_risk_long,
                            'mother_high': levels['mother_high'],
                            'mother_low': levels['mother_low'],
                            'atr': levels['atr'],
                            'symbol': symbol
                        }
                    )
                )
                signals.append(
                    RawSignal(
                        timestamp=signal_ts,
                        side='SELL',
                        entry_price=entry_short,
                        stop_loss=sl_short,
                        take_profit=tp_short,
                        metadata={
                            'pattern': 'inside_bar_breakout',
                            'session_key': str(session_key),
                            'ib_idx': state['ib_idx'],
                            'entry_mode': entry_mode,
                            'stop_cap_applied': stop_cap_applied_short,
                            'initial_risk': initial_risk_short,
                            'effective_risk': effective_risk_short,
                            'mother_high': levels['mother_high'],
                            'mother_low': levels['mother_low'],
                            'atr': levels['atr'],
                            'symbol': symbol
                        }
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
            if entry_mode == "mother_bar":
                entry_long = levels['mother_high']
                entry_short = levels['mother_low']
            else:  # inside_bar
                entry_long = levels['ib_high']
                entry_short = levels['ib_low']

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
                # Calculate SL with cap
                sl = levels['mother_low']
                initial_risk = entry_long - sl

                if initial_risk <= 0:
                    emit({
                        'event': 'signal_rejected',
                        'reason': 'non_positive_risk',
                        'idx': int(idx),
                        'entry': entry_long,
                        'sl': sl
                    })
                    continue

                # === SL CAP ===
                effective_risk = initial_risk
                stop_cap_applied = False

                if initial_risk > max_risk:
                    sl = entry_long - max_risk
                    effective_risk = max_risk
                    stop_cap_applied = True

                tp = entry_long + (effective_risk * config.risk_reward_ratio)

                signal = RawSignal(
                    timestamp=ts,
                    side='BUY',
                    entry_price=entry_long,
                    stop_loss=sl,
                    take_profit=tp,
                    metadata={
                        'pattern': 'inside_bar_breakout',
                        'session_key': str(session_key),
                        'ib_idx': state['ib_idx'],
                        'entry_mode': entry_mode,
                        'stop_cap_applied': stop_cap_applied,
                        'initial_risk': initial_risk,
                        'effective_risk': effective_risk,
                        'mother_high': levels['mother_high'],
                        'mother_low': levels['mother_low'],
                        'atr': levels['atr'],
                        'symbol': symbol
                    }
                )
                signals.append(signal)
                state['done'] = True
                signals_per_session[session_key] = signals_per_session.get(session_key, 0) + 1

                # === NETTING: Calculate position open_until (conservative) ===
                if validity_policy == 'session_end':
                    netting_open_until = session_filter.get_session_end(ts, session_tz)
                elif validity_policy == 'one_bar':
                    # Assume M5 timeframe (5 minutes)
                    # TODO: Make timeframe configurable if needed
                    netting_open_until = ts + pd.Timedelta(minutes=5)
                elif validity_policy == 'fixed_minutes':
                    netting_open_until = ts + pd.Timedelta(minutes=validity_minutes)
                    # Clamp to session_end (don't extend beyond session)
                    session_end = session_filter.get_session_end(ts, session_tz)
                    if session_end and netting_open_until > session_end:
                        netting_open_until = session_end
                else:
                    # Fallback: session_end
                    netting_open_until = session_filter.get_session_end(ts, session_tz)

                emit({
                    'event': 'signal_generated',
                    'side': 'BUY',
                    'session_key': str(session_key),
                    'entry': entry_long,
                    'sl': sl,
                    'tp': tp,
                    'stop_cap_applied': stop_cap_applied
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
                # Calculate SL with cap
                sl = levels['mother_high']
                initial_risk = sl - entry_short

                if initial_risk <= 0:
                    emit({
                        'event': 'signal_rejected',
                        'reason': 'non_positive_risk',
                        'idx': int(idx),
                        'entry': entry_short,
                        'sl': sl
                    })
                    continue

                # === SL CAP ===
                effective_risk = initial_risk
                stop_cap_applied = False

                if initial_risk > max_risk:
                    sl = entry_short + max_risk
                    effective_risk = max_risk
                    stop_cap_applied = True

                tp = entry_short - (effective_risk * config.risk_reward_ratio)

                signal = RawSignal(
                    timestamp=ts,
                    side='SELL',
                    entry_price=entry_short,
                    stop_loss=sl,
                    take_profit=tp,
                    metadata={
                        'pattern': 'inside_bar_breakout',
                        'session_key': str(session_key),
                        'ib_idx': state['ib_idx'],
                        'entry_mode': entry_mode,
                        'stop_cap_applied': stop_cap_applied,
                        'initial_risk': initial_risk,
                        'effective_risk': effective_risk,
                        'mother_high': levels['mother_high'],
                        'mother_low': levels['mother_low'],
                        'atr': levels['atr'],
                        'symbol': symbol
                    }
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
                    'stop_cap_applied': stop_cap_applied
                })

    return signals
