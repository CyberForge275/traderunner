# InsideBar Doc vs Code Alignment Report

**Scope:** `src/strategies/inside_bar/**` + pipeline integration for intent validity.  
**Goal:** Map documented rules to implementation with line references, and highlight deviations/risks.

## 1) Documentation Sources (Discovery)
- `src/strategies/inside_bar/docs/INSIDE_BAR_SSOT.md`
- `src/strategies/inside_bar/docs/INSIDE_BAR_STRATEGY.md`
- `src/strategies/inside_bar/docs/INSIDEBAR_STRATEGY_SPEC_V1_IMPLEMENTATION.md`
- `src/strategies/inside_bar/docs/INSIDE_BAR_LIVE_TRADING.md`
- `src/strategies/inside_bar/docs/README.md`

## 2) Rule Extraction (Doc Statements)

Key documented rules (condensed):
- **Timeframe M5**; **timezone Europe/Berlin**; session windows param via `session_windows`.  
  (INSIDE_BAR_SSOT.md, INSIDE_BAR_STRATEGY.md, SPEC_V1)
- **Inside Bar (inclusive)**: `IB.high <= Mother.high` and `IB.low >= Mother.low`.  
  (SSOT, STRATEGY, SPEC_V1)
- **Mother Bar is previous candle** and must be in the **same session** as IB.  
  (SSOT, SPEC_V1)
- **Breakout confirmation**: trigger on close beyond entry level.  
  (SSOT, STRATEGY)
- **Entry level** default `mother_bar`:  
  LONG = mother_high, SHORT = mother_low.  
  (SSOT, STRATEGY, SPEC_V1)
- **SL/TP**:  
  SL = opposite mother side; SL cap by ticks; TP = entry ± risk * RRR.  
  (SSOT, STRATEGY, SPEC_V1)
- **Max 1 trade per session**; netting: one position per symbol.  
  (SSOT, STRATEGY)
- **Order validity** default `session_end`, `valid_from_policy` typically signal_ts (docs), or next_bar (SSOT note).  
  (STRATEGY, SSOT, SPEC_V1)
- **OCO** cancellation after fill.  
  (STRATEGY, SSOT)
- **Trailing stop** optional.  
  (SSOT, STRATEGY, SPEC_V1)

## 3) Doc → Code Mapping Table

| Doc Statement | Code Location (file:lines) | Implementation Summary | Match | Notes/Risks |
|---|---|---|---|---|
| Timeframe M5, TZ Europe/Berlin, session windows | `src/strategies/inside_bar/config.py:L189–L200` | Default config: M5 implied, session_timezone=Europe/Berlin, session_windows defaults | PARTIAL | Timeframe is enforced via pipeline SSOT, not in core; config defaults may be overridden |
| Inside Bar inclusive | `src/strategies/inside_bar/core.py:L216–L227` | inclusive: high<=prev_high and low>=prev_low | YES | — |
| Mother Bar = previous candle (same session) | `core.py:L415–L426` | Reject if prev session != current session | YES | — |
| Breakout confirmation on close | `core.py:L509–L604` | trigger if current close > entry_long (BUY) or < entry_short (SELL) | YES | Confirmed uses `close` |
| Entry level mother_bar default | `core.py:L475–L481`, `config.py:L203–L205` | entry_long=mother_high, entry_short=mother_low if entry_level_mode=mother_bar | YES | — |
| SL/TP calculation + SL cap | `core.py:L528–L551` (BUY), `core.py:L620–L643` (SELL) | SL on opposite mother side, cap risk by ticks, TP = entry ± risk * RRR | YES | — |
| Max 1 trade per session | `core.py:L306–L489` | signals_per_session + max_trades_per_session | YES | — |
| Netting: one position per symbol | `core.py:L310–L508`, `L576–L591`, `L669–L680` | netting_open_until blocks new signals until window ends | YES | Conservative window-based netting |
| Session gate + trigger must be in session | `core.py:L359–L392`, `L510–L527`, `L604–L619` | bars outside session rejected; trigger must be within session | YES | — |
| Order validity default session_end | `config.py:L207–L230`, `signals.py:L118–L130` | intent exit_ts set to session window end | YES | Pipeline enforces session_end validity |
| valid_from_policy default signal_ts (docs) | `signals.py:L112–L143` | effective policy forced to **next_bar** for `insidebar_intraday` | **NO** | Doc mismatch: code forces next_bar |
| OCO cancellation | **Not found in core/pipeline** | No OCO enforcement in inside_bar core or pipeline fill/execution | NO | Doc mentions OCO but code lacks implementation |
| Trailing stop | **Not found in core** | No trailing stop logic present in core | NO | Config has trailing params, but no logic |
| Diagnostics/debug artifacts always on | `artifacts.py:L24–L57` | Writes events_intent, fills, trades, equity, metrics | PARTIAL | No diagnostics.json/run_steps.jsonl in pipeline artifacts |

## 4) Top 5 Deviations / Risks (Evidence‑based)

1) **valid_from_policy mismatch**  
   - **Doc:** default `signal_ts` (INSIDE_BAR_STRATEGY.md §9).  
   - **Code:** forces `next_bar` for `insidebar_intraday` (signals.py:L112–L115).  
   - **Risk:** behavior drift vs doc; but intentional to avoid lookahead.

2) **OCO enforcement missing**  
   - **Doc:** OCO cancellation described (SSOT/STRATEGY).  
   - **Code:** No OCO logic in core or pipeline (no references).  
   - **Risk:** divergence if OCO expected in replay/backtest.

3) **Trailing stop not implemented**  
   - **Doc:** trailing rules defined (SSOT/STRATEGY/SPEC_V1).  
   - **Code:** core has no trailing implementation (no `trailing_*` in core).  
   - **Risk:** doc describes behavior that doesn’t exist.

4) **Diagnostics artifacts in docs but not in pipeline**  
   - **Doc:** diagnostics.json, run_steps.jsonl, debug traces (SSOT/STRATEGY).  
   - **Code:** pipeline writes only events_intent/fills/trades/equity/metrics (artifacts.py).  
   - **Risk:** audit expectations not met.

5) **Timezone/Session SSOT mismatch risk**  
   - **Doc:** session timezone Europe/Berlin.  
   - **Pipeline SSOT:** market timezone America/New_York (AGENTS.md).  
   - **Code:** core defaults Berlin, pipeline uses session_timezone from config.  
   - **Risk:** depends on YAML; mismatch can shift signals if not aligned.

## 5) Direct Answers to Required Questions

- **Where are stop_price / take_profit_price computed?**  
  `src/strategies/inside_bar/core.py`:  
  BUY SL/TP at L528–L551, SELL SL/TP at L620–L643.

- **Which rule sets valid_to=session_end?**  
  `src/axiom_bt/pipeline/signals.py:L118–L130` using `session_window_end_for_ts(...)`.

- **Which candle triggers entry?**  
  `core.py:L509–L604`: breakout on **current bar close**; signal timestamp = current bar.  
  `signals.py` enforces `valid_from_policy=next_bar` → no same‑bar fill.

- **Is there lookahead?**  
  No direct lookahead in core (no `.shift(-1)`); signals use current bar close.  
  Pipeline enforces `valid_from_policy=next_bar` to prevent same‑bar fill.

- **Session times/TZ consistency?**  
  Core uses `session_timezone` from config (default Berlin).  
  Pipeline expects `session_timezone` in strategy params (config/YAML).  
  If YAML uses NY but docs say Berlin, mismatch risk exists (see Top 5 #5).
