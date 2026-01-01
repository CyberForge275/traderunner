# scripts/debug_inside_bar_spyder.py
"""
Spyder Debug Script für InsideBar Strategy
==========================================

Lädt Session-Config aus YAML und startet einen reproduzierbaren Backtest-Run.
Perfekt für Breakpoint-Debugging in Spyder.

Breakpoint-Stellen:
- strategies.inside_bar.config.SessionFilter.is_in_session (Session-Gating)
- strategies.inside_bar.core (Signal generation)
- trade.orders_builder (Order rejection logic)
"""
from __future__ import annotations

import os
import sys
#import json
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

# --- Optional dependency: pyyaml ---
try:
    import yaml  # type: ignore
except Exception as e:
    raise RuntimeError("PyYAML fehlt. Installiere: pip install pyyaml") from e


# =========================
# 1) SessionSpec (SSOT)
# =========================
@dataclass(frozen=True)
class SessionSpec:
    market_tz: str
    display_tz: str
    rth_start: time
    rth_end: time
    allow_premarket: bool = False
    allow_afterhours: bool = False

    def __repr__(self) -> str:
        return (
            f"SessionSpec(market_tz={self.market_tz}, display_tz={self.display_tz}, "
            f"rth={self.rth_start}-{self.rth_end}, pre={self.allow_premarket}, ah={self.allow_afterhours})"
        )


def _parse_hhmm(s: str) -> time:
    hh, mm = s.strip().split(":")
    return time(int(hh), int(mm))


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_session_spec(cfg: dict) -> SessionSpec:
    """Build SessionSpec from config.
    
    Supports both:
    - Single RTH window: rth.start/end
    - Multiple windows: windows[].start/end
    """
    s = cfg["session"]
    
    # Check if we have multiple windows or single RTH
    if "windows" in s and s["windows"]:
        # Multiple windows mode
        windows = s["windows"]
        # Use first window for SessionSpec (legacy compatibility)
        rth_start = _parse_hhmm(windows[0]["start"])
        rth_end = _parse_hhmm(windows[-1]["end"])
    else:
        # Single RTH mode
        rth_start = _parse_hhmm(s["rth"]["start"])
        rth_end = _parse_hhmm(s["rth"]["end"])
    
    return SessionSpec(
        market_tz=s["market_tz"],
        display_tz=s.get("display_tz", s["market_tz"]),
        rth_start=rth_start,
        rth_end=rth_end,
        allow_premarket=bool(s.get("allow_premarket", False)),
        allow_afterhours=bool(s.get("allow_afterhours", False)),
    )


# =========================
# 2) Repo bootstrap for Spyder
# =========================
def repo_root_from_this_file() -> Path:
    # scripts/debug_inside_bar_spyder.py -> repo root = parents[1]
    return Path(__file__).resolve().parents[1]


def ensure_src_on_path(repo_root: Path) -> None:
    """Setup PYTHONPATH for imports.
    
    CRITICAL: Only add src/ directory, NOT repo_root!
    This prevents 'src' from being imported as a top-level module,
    which causes Spyder module reload issues.
    """
    src = repo_root / "src"
    src_str = str(src)
    
    # Only add if not already present
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    
    # Also add trading_dashboard for coverage check imports
    dashboard = str(repo_root)  # trading_dashboard is at repo root level
    if dashboard not in sys.path:
        sys.path.insert(1, dashboard)  # Add after src/
    
    # Set working directory to repo root for config file access
    #import os
    os.chdir(str(repo_root))
    
    # Set environment variable for TradingSettings
    os.environ['TRADING_PROJECT_ROOT'] = str(repo_root)


# =========================
# 3) Main debug flow
# =========================
def main():
    repo = repo_root_from_this_file()
    ensure_src_on_path(repo)
    
    # Verify setup for Spyder debugging
    import os
    print(f"🔧 Working Directory: {os.getcwd()}")
    print(f"🔧 Repo Root: {repo}")
    print(f"🔧 PYTHONPATH: {sys.path[:3]}")
    print()

    cfg_path = repo / "configs" / "inside_bar_debug_us.yaml"
    cfg = load_config(cfg_path)
    session_spec = build_session_spec(cfg)

    run = cfg["run"]
    symbol = run["symbol"]
    date_from = run["date_from"]
    date_to = run["date_to"]
    bar_freq = run.get("bar_freq", "M5")
    data_source = run.get("data_source_backtest", "EODHD")

    debug_cfg = cfg.get("debug", {})
    trace_session = bool(debug_cfg.get("trace_session_decisions", True))
    trace_orders = bool(debug_cfg.get("trace_order_rejections", True))

    print("=== DEBUG RUN CONFIG ===")
    print("repo:", repo)
    print("symbol:", symbol)
    print("range:", date_from, "->", date_to)
    print("bar_freq:", bar_freq, "data_source:", data_source)
    print("session_spec:", session_spec)
    print("trace_session:", trace_session, "trace_orders:", trace_orders)
    print("========================\n")

    # ==========================================================================
    # RUNNER INTEGRATION for axiom_bt.full_backtest_runner
    # ==========================================================================
    # Unser Runner: axiom_bt.full_backtest_runner.run_backtest_full
    # 
    # Er erwartet:
    # - run_id, symbol, timeframe, requested_end, lookback_days
    # - strategy_key = "inside_bar"
    # - strategy_params (dict mit session_timezone, session_windows)
    # - debug_trace = True
    # ==========================================================================
    
    from axiom_bt.full_backtest_runner import run_backtest_full
    from datetime import datetime
    import pandas as pd
    
    # Calculate lookback_days from date range
    start_dt = pd.Timestamp(date_from).tz_localize(session_spec.market_tz)
    end_dt = pd.Timestamp(date_to).tz_localize(session_spec.market_tz)
    lookback_days = (end_dt - start_dt).days
    
    # Build strategy_params with SESSION SPEC (SSOT)
    # CRITICAL: Wir überschreiben die hardcoded Berlin-Defaults!
    
    # Build session_windows from config (supports multiple windows)
    s = cfg["session"]
    if "windows" in s and s["windows"]:
        # Multiple windows mode (z.B. 10:00-11:00, 14:00-15:00)
        session_windows = [
            f"{w['start']}-{w['end']}" for w in s["windows"]
        ]
    else:
        # Single RTH mode (fallback)
        session_windows = [
            f"{session_spec.rth_start.strftime('%H:%M')}-{session_spec.rth_end.strftime('%H:%M')}"
        ]
    
    # ==========================================================================
    # STRATEGY PARAMETERS (WITH VALIDITY OVERRIDE)
    # ==========================================================================
    # CRITICAL: Set BOTH session_filter AND session_windows to avoid key mismatch
    # (orders_builder.py reads "session_filter", but other code may use "session_windows")
    #
    # 3 TEST VARIANTS AVAILABLE - ACTIVATE ONE AT A TIME:
    # ==========================================================================
    
    strategy_params = {
        # =================================================================
        # SESSION PARAMETERS (ROBUST - sets both keys to avoid divergence)
        # =================================================================
        "session_timezone": session_spec.market_tz,  # "America/New_York"
        "session_filter": session_windows,           # PRIMARY key for orders_builder
        "session_windows": session_windows,          # SECONDARY key for compatibility
        
        # =================================================================
        # TIMEFRAME CONFIGURATION
        # =================================================================
        "timeframe": bar_freq,  # "M5" → timeframe_minutes = 5
        
        # =================================================================
        # INSIDEBAR STRATEGY PARAMETERS
        # =================================================================
        "atr_period": 14,
        "atr_multiplier": 2.0,
        "take_profit_atr_multiplier": 3.0,
        "entry_offset_atr_multiplier": 0.1,
        "execution_mode": "full_backtest",
        "version": "1.00",
    }
    
    # ==========================================================================
    # VALIDITY POLICY OVERRIDE - CHOOSE ONE VARIANT (comment out others)
    # ==========================================================================
    
    # # ═══ VARIANTE A: ONE_BAR POLICY ═══
    # # Expected: valid_to - valid_from = exactly 5 minutes (M5)
    # strategy_params.update({
    #     "order_validity_policy": "one_bar",
    #     "valid_from_policy": "signal_ts",     # or "next_bar"
    #     # Compatibility mirrors
    #     "expire_policy": "one_bar",
    #     # NOTE: order_validity_minutes/validity_minutes IGNORED with one_bar!
    # })
    
    # ═══ VARIANTE B: FIXED_MINUTES POLICY (ACTIVE) ═══
    # Expected: valid_to - valid_from <= 30 minutes (clamped to session_end)
    strategy_params.update({
        "order_validity_policy": "fixed_minutes",
        "validity_minutes": 60,               # PRIMARY key (used by orders_builder)
        "valid_from_policy": "signal_ts",
        # Compatibility mirrors
        "order_validity_minutes": 60,         # SECONDARY key (for other code paths)
        "expire_policy": "fixed_minutes",
    })
    
    # # ═══ VARIANTE C: SESSION_END POLICY ═══
    # # Expected: valid_to = session window end (variable duration)
    # strategy_params.update({
    #     "order_validity_policy": "session_end",
    #     "valid_from_policy": "signal_ts",
    #     # Compatibility mirrors
    #     "expire_policy": "session_end",
    #     # NOTE: validity_minutes/timeframe_minutes IGNORED with session_end!
    # })

    
    run_id = f"spyder_debug_{datetime.now().strftime('%y%m%d_%H%M%S')}_{symbol.lower()}"
    
    print(f"\n🔍 Starting backtest with SessionSpec:")
    print(f"   Timezone: {session_spec.market_tz}")
    print(f"   Windows: {session_windows}")
    print(f"   Debug trace: {trace_session}")
    print()
    
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # ⚠️  BREAKPOINT HIER SETZEN für Step-by-Step Debugging:
    # 
    # 1. In strategies/inside_bar/config.py:
    #    - SessionFilter.is_in_session() Zeile ~95
    # 
    # 2. In strategies/inside_bar/core.py:
    #    - scan_for_patterns() wo Signale entstehen
    #    - Zeile mit "session_tz = getattr(self.config, 'session_timezone'..."
    # 
    # 3. In trade/orders_builder.py:
    #    - build_orders_for_backtest()
    #    - Wo "not in session window" Exception geworfen wird
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    
    result = run_backtest_full(
        run_id=run_id,
        symbol=symbol,
        timeframe=bar_freq,
        requested_end=date_to,
        lookback_days=lookback_days,
        strategy_key="inside_bar",
        strategy_params=strategy_params,  # ← Session-Spec drin!
        artifacts_root=Path("artifacts/backtests"),
        market_tz=session_spec.market_tz,  # ← Auch hier NY!
        initial_cash=10000.0,
        costs={"fees_bps": 0.0, "slippage_bps": 5.0},
        debug_trace=True,  # ← Debug artifacts aktiviert
    )

    print("\n=== RUN RESULT ===")
    print(f"Status: {result.status}")
    print(f"Run ID: {result.run_id}")
    print(f"Details: {result.details}")
    
    if result.status.value == "SUCCESS":
        print(f"\n✅ SUCCESS!")
        print(f"Artifacts: artifacts/backtests/{result.run_id}/")
        print(f"\n📊 Check:")
        print(f"  - debug/inside_bar_trace.jsonl (per-candle decisions)")
        print(f"  - debug/orders_debug.jsonl (signal→order mapping)")
        print(f"  - run_steps.jsonl (execution timeline)")
    else:
        print(f"\n❌ FAILED: {result.status}")
        if hasattr(result, 'reason'):
            print(f"Reason: {result.reason}")
    
    return result


if __name__ == "__main__":
    main()
