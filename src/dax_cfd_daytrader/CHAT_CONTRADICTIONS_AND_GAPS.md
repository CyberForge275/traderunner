# Contradictions & Gaps: Discord Chat Analysis

This document lists all identified contradictions between sources and critical gaps requiring clarification.

## Priority Classification

- **CRITICAL**: Blocks implementation entirely
- **HIGH**: Significant impact on strategy behavior
- **MEDIUM**: Affects specific edge cases or optimizations  
- **LOW**: Minor clarifications, nice-to-have

---

## Section 1: Contradictions

### [WIDERSPRUCH-001] NONE IDENTIFIED

**Status**: No direct contradictions between Chat and PDF/Charts found.

**Reason**: The chat primarily provides clarifications and examples complementing the PDF. No instances where chat explicitly contradicts the published regelwerk.

**Action**: NONE required.

---

## Section 2: Gap - Critical Blockers (Max 10)

### [GAP-001] Setup 1-5 Definitions

**Priority**: ⚠️ **CRITICAL**  
**Impact**: Cannot implement strategy without knowing setup conditions

**Question**: What are the exact entry conditions for Setup 1, Setup 2, Setup 3, Setup 4, and Setup 5?

**Chat References**:
- "Setup 4 Long & 2 Long wurden bewusst ausgelassen"
- "Setup 3 long 30 Tp erreicht"
- Multiple mentions of specific setups without defining them

**Options**:
- Option A: Setups are time-based (e.g., Setup 1 = 08:00-10:00, Setup 2 = 10:00-13:00, etc.)
- Option B: Setups are price-level based (e.g., Setup 1 = first zone, Setup 2 = second zone)
- Option C: Setups are pattern-based (e.g., Setup 1 = trend continuation, Setup 2 = reversal)
- Option D: Setups are defined in PDF/VTAD articles (need to extract)

**Source Needed**: FDAX-Regelwerk-August-2025.pdf

---

### [GAP-002] Zone Reference Point Selection Logic

**Priority**: ⚠️ **CRITICAL**  
**Impact**: Wrong reference → wrong zones → wrong entries/exits

**Question**: When calculating zones, when do you use:
- 22:00 close (previous day) as reference?
- 08:00 open (current day) as reference?

**Chat Evidence**:
- Long zones calculated "75 Punkte unter dem Schlusskurs (22 h)"
- Long zones calculated "75 Punkte unter dem Eröffnungskurs"
- Short zones calculated from "Eröffnung"
- Short zones calculated from "Schluss 22h"

**Observed Pattern**:
- After Up-Gap: Long zones use 22:00 close, Short zones use 08:00 open
- After Down-Gap: Long zones use 08:00 open, Short zones use 22:00 close
- But this is inferred, not explicitly stated

**Options**:
- Option A: Always use 08:00 open for Short zones, 22:00 close for Long zones
- Option B: Use whichever is further in the direction (Long = lower, Short = higher)
- Option C: Gap-dependent logic (if gap up, Long from close, Short from open, vice versa)
- Option D: Different rule from PDF

**Source Needed**: FDAX-Regelwerk or clarification from Georg

---

### [GAP-003] VDAX Zone Adjustment Thresholds

**Priority**: ⚠️ **HIGH**  
**Impact**: Incorrect zone sizing in volatile markets

**Question**: At what VDAX-NEW levels do zone sizes change, and by how much?

**Chat Evidence**:
- "Der VDAX-NEW notiert bei 17" → standard zones (75/50/35)
- "Der VDAX-NEW notiert bei 18" → zones mentioned but no change indicated
- "Sie ist darauf ausgelegt, sich dynamisch an verschiedene... Volatilitäten (VDAX-NEW) anzupassen"

**Missing**:
- VDAX threshold levels (e.g., <15, 15-20, 20-25, 25-30, >30)
- Corresponding zone adjustments (e.g., multiply by 1.0, 1.2, 1.5, 2.0)
- Which zones change (first, second, SL, all?)

**Options**:
- Option A: Linear scaling (e.g., zones = base_zones * (VDAX / 15))
- Option B: Step function (e.g., VDAX <16 = 1x, 16-20 = 1.2x, 20-25 = 1.5x, >25 = 2x)
- Option C: Only first zone adjusts, SL stays constant
- Option D: Defined in PDF with lookup table

**Source Needed**: FDAX-Regelwerk

---

### [GAP-004] Maximum Trades Per Day

**Priority**: ⚠️ **HIGH**  
**Impact**: Risk management, prevents overtrading

**Question**: Is there a maximum number of trades allowed per day? If yes, what is it?

**Chat Evidence**:
- MAX_TRADES topic: only 3 messages, none specify a number
- No explicit "max 3 trades" or similar statements found

**Missing**:
- Hard limit (e.g., 5 trades/day)
- Soft limit after which to reduce size
- Separate limits for winning vs losing trades?

**Options**:
- Option A: No hard limit (trade all setups that trigger)
- Option B: Max 5 trades per day
- Option C: Stop after 3 consecutive losses
- Option D: Defined in PDF

**Source Needed**: FDAX-Regelwerk or risk management section

---

### [GAP-005] Maximum Daily Loss Limit

**Priority**: ⚠️ **HIGH**  
**Impact**: Capital preservation, prevents blow-up

**Question**: Is there a max daily loss limit? If yes, how is it calculated?

**Chat Evidence**:
- MAX_LOSS topic: 0 messages
- No "max -100 points" or "stop at -2% equity" statements

**Missing**:
- Loss limit in points
- Loss limit as % of account
- Action when limit hit (stop trading, reduce size, wait for next day)

**Options**:
- Option A: No daily limit (manage per-trade SL only)
- Option B: Stop after -150 points cumulative  
- Option C: Stop after -2% account equity
- Option D: Defined in PDF

**Source Needed**: FDAX-Regelwerk, risk management section

---

### [GAP-006] Position Sizing Formula

**Priority**: ⚠️ **HIGH**  
**Impact**: Incorrectsizing → incorrect risk per trade

**Question**: How is position size calculated from account equity?

**Chat Evidence**:
- POSITION_SIZING topic: 10 messages
- Discussion of 1€, 5€, 25€ per point for CFDs
- "doppelte Kontrakthöhe" at second zone
- No formula like "risk 1% of equity per trade"

**Missing**:
- Fixed fractional formula (e.g., Position Size = Account * RiskPct / StopLossPts)
- Fixed size (e.g., always 1 contract)
- Kelly criterion or similar
- Scaling as account grows

**Options**:
- Option A: Fixed size (e.g., 1 CFD contract @ 1€/point)
- Option B: Risk 1% of account per trade
- Option C: Use ATR-based sizing
- Option D: Defined in PDF

**Source Needed**: FDAX-Regelwerk, money management section

---

### [GAP-007] 13:00-14:45Pause Period

**Priority**: 🟡 **MEDIUM**  
**Impact**: May affect afternoon setups

**Question**: Is 13:00-14:45 a mandatory no-trade period? Should positions be closed at 13:00?

**Chat Evidence**:
- PAUSE_FLATTEN topic: only 2 messages
- Mentioned in one message but not repeated
- No examples of "flattening at 13:00"

**Missing**:
- Is this a hard rule?
- Does it apply to all setups?
- Can you hold existing positions through the pause?
- Or only avoid NEW entries?

**Options**:
- Option A: Hard rule - close all positions at 13:00, no new entries until 14:45
- Option B: Soft rule - avoid new entries, but hold existing
- Option C: Not a rule, just an observation of low volume period
- Option D: Defined in PDF

**Source Needed**: FDAX-Regelwerk, session rules

---

### [GAP-008] Gap Size Threshold for No-Trade

**Priority**: 🟡 **MEDIUM**  
**Impact**: Prevents trading in abnormal conditions

**Question**: At what gap size (in points or %) should trading be avoided?

**Chat Evidence**:
- "kleines Up-Gap von 24 Punkten" → trading continues
- "kleines Down-Gap" (size not specified)
- GAP_HANDLING topic: 63 messages, but no threshold specified

**Missing**:
- "Small" gap definition (e.g., < 50 points)
- "Large" gap definition (e.g., > 100 points)
- Action on large gap (skip day, widen zones, reduce size)

**Options**:
- Option A: No gap threshold (trade all gaps)
- Option B: Skip day if gap > 100 points
- Option C: Skip day if gap > ±1%
- Option D: Widen zones proportionally to gap size

**Source Needed**: FDAX-Regelwerk, gap handling section

---

### [GAP-009] Trailing Stop Logic

**Priority**: 🟡 **MEDIUM**  
**Impact**: Profit protection, may improve R:R

**Question**: Is there a trailing stop rule? If yes, what triggers it and how does it move?

**Chat Evidence**:
- TRAILING topic: 0 messages in topic blocks
- No "trail by 20 points" or similar

**Missing**:
- Activation trigger (e.g., after +30 points)
- Trail amount (e.g., keep SL 20 points below high)
- Trail interval (every tick, every 5 points, etc.)

**Options**:
- Option A: No trailing stop (only BE + TP)
- Option B: Trail after BE reached
- Option C: Trail after +30 points
- Option D: Defined in PDF but not mentioned in chat

**Source Needed**: FDAX-Regelwerk, exit rules

---

### [GAP-010] ±1% Price Movement Filter

**Priority**: 🟡 **MEDIUM**  
**Impact**: Avoids trading in extreme volatility

**Question**: Is there a ±1% intraday movement filter? If price moves ±1% from open, what action?

**Chat Evidence**:
- PRICE_MOVEMENT topic: 20 messages
- Mention of "±1%" but not clearly defined as a rule

**Missing**:
- Exact threshold (1.0%, or variable based on ATR?)
- Action when crossed (stop new trades, close existing, widen SL)
- Applies to all setups or only specific ones?

**Options**:
- Option A: No filter (trade all conditions)
- Option B: Stop new trades if intraday move > ±1%
- Option C: Widen zones if intraday move > ±1%
- Option D: Close all positions if intraday move > ±1%

**Source Needed**: FDAX-Regelwerk, volatility filters

---

## Section 3: Minor Clarifications (Not Blockers)

### [MINOR-001] Spread After 20:00

**Question**: What is the exact spread for IG German 40 CFDs after 20:00?

**Evidence**: "Ab 20h Spread etwas höher" - no specific value

**Impact**: LOW - only affects late evening trades

---

### [MINOR-002] News Events List

**Question**: Which specific news events trigger no-trade periods?

**Evidence**: NEWS_EVENTS topic has 11 messages but no exhaustive list

**Impact**: LOW - traders can use standard economic calendars

---

### [MINOR-003] Reversal Candle Patterns

**Question**: Which candlestick patterns qualify as "reversal candles" beyond engulfing?

**Evidence**: "Idealerweise... bullishes Engulfing-Muster oder eine starke Candlestick-Kerze mit überdurchschnittlich großem Kerzenkörper"

**Impact**: LOW - general pattern recognition suffices

---

## Section 4: Testing Implications

### Test Cases Derived from Gaps

Each gap above should generate at least one test case:

- **[TESTFALL-001]**: Setup 1 vs Setup 2 vs Setup 3 vs Setup 4 vs Setup 5 entry conditions
- **[TESTFALL-002]**: Zone calc with Up-Gap vs Down-Gap (reference point selection)
- **[TESTFALL-003]**: Zone sizing at VDAX 15 vs 20 vs 25 vs 30
- **[TESTFALL-004]**: Max trades limit (if exists): 3rd, 4th, 5th trade of day
- **[TESTFALL-005]**: Max loss limit (if exists): trade that would exceed limit
- **[TESTFALL-006]**: Position sizing: account $10k vs $100k vs $1M
- **[TESTFALL-007]**: Pause period: 13:00-14:45 entry attempt
- **[TESTFALL-008]**: Large gap: gap > threshold, verify no trades
- **[TESTFALL-009]**: Trailing stop: profit > trigger, verify SL moves
- **[TESTFALL-010]**: ±1% filter: intraday move crossing threshold

---

## Next Actions

1. **Obtain PDF Regelwerk**: FDAX-Regelwerk-August-2025.pdf (shared in chat, needs extraction)
2. **Extract Answers**: Re-analyze PDF for gaps [GAP-001] through [GAP-010]
3. **Cross-Reference**: Map chat rules to PDF rules
4. **Generate Test Suite**: Create test cases for each ambiguity
5. **Clarify Remaining**: If PDF doesn't answer, prepare questions for Georg/community
6. **Update Rule Matrix**: Integrate all rules into unified RULE_MATRIX

---

*Generated from Discord chat analysis*  
*Contradictions: 0*  
*Critical Gaps: 10*  
*High Priority Gaps: 6*  
*Medium Priority Gaps: 4*  
*Low Priority Items: 3*
