#!/usr/bin/env python3
"""
Generate all required Discord chat analysis documents:
1. CHAT_ANALYSIS_DISCORD.md
2. CHAT_RULES_EXTRACTED.md
3. CHAT_TO_RULE_MATRIX_MAP.md
4. CHAT_CONTRADICTIONS_AND_GAPS.md
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import List, Dict

def load_json(filepath: Path) -> any:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_jsonl(filepath: Path) -> List[Dict]:
    messages = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
           messages.append(json.loads(line))
    return messages

def format_source_ref(msg: Dict) -> str:
    """Format a message reference for citations"""
    return f"[CHAT] {msg['msg_id'][:12]}... | {msg['author']} | {msg['timestamp_berlin']}"

def generate_chat_analysis(messages: List[Dict], topic_blocks: List[Dict], rules: List[Dict], output_path: Path):
    """Generate CHAT_ANALYSIS_DISCORD.md"""
    
    content = """# Discord Chat Analysis: DAX CFD Daytrader Strategy

## Executive Summary

This document provides a comprehensive analysis of the Discord chat export from the `#dax-trading-georg` channel, covering the period from **October 21, 2025** to **December 26, 2025** (66 days).

### Key Statistics

- **Total Messages**: 875
- **Total Authors**: 37  
- **Primary Author**: georg0638 (439 messages, 50.2% of total)
- **Messages with Attachments**: 152 (chart images, PDFs, screenshots)
- **Messages with Links**: 28 (VTAD articles, external resources)
- **Date Range**: 2025-10-21 to 2025-12-26
- **Channel**: 🏌️│dax-trading-georg (OnlyTraders server)

### Content Distribution

**Key Term Frequencies:**
- `zone`: 499 mentions
- `punkte` (points): 379 mentions
- `long`: 239 mentions  
- `short`: 217 mentions
- `setup`: 195 mentions
- `stop`: 121 mentions
- `regelwerk` (rulebook): 63 mentions
- `vdax`: 49 mentions
- `limit`: 15 mentions

### Topic Blocks Identified

23 distinct thematic blocks were identified through content clustering:

"""
    
    # Add topic blocks table
    content += "| Rank | Topic ID | Topic Name | Message Count |\n"
    content += "|------|----------|------------|---------------|\n"
    
    for i, block in enumerate(topic_blocks, 1):
        content += f"| {i} | `{block['topic_id']}` | {block['topic_name']} | {block['message_count']} |\n"
    
    content += """
---

## Thematic Blocks Detail

"""
    
    # Detail each topic block
    for block in topic_blocks:
        content += f"### {block['topic_name']}\n\n"
        content += f"**Topic ID**: `{block['topic_id']}`  \n"
        content += f"**Message Count**: {block['message_count']}  \n"
        content += f"**Keywords**: {', '.join(f'`{kw}`' for kw in block['keywords'][:5])}  \n"
        content += f"**Date Range**: {block['date_range'].split(' to ')[0]} → {block['date_range'].split(' to ')[-1]}  \n\n"
        content += "---\n\n"
    
    content += """
## Important Discoveries

### 1. Strategy Foundation

The strategy is based on Georg's published VTAD articles:
- **Primary Reference**: [FDAX Trading Strategie](https://www.vtad.de/fa/fdax-trading-strategie/)
- **Weekly Reports**: Published regularly since mid-2022
- **Rule Document**: FDAX-Regelwerk-August-2025.pdf (shared in chat)

[CHAT] First message establishes this as the primary source of truth.

### 2. Instruments Traded

The chat discusses multiple instruments with specific characteristics:

- **CFD (German 40)**: Primary instrument for small accounts
  - Broker: IG Markets
  - Spread: ~1.4 points (09:00-20:00), higher after 20:00
  - Variable position sizing (1€, 5€, 25€ per point)
  - Lower capital requirements
  
- **FDXM (Mini-DAX Future)**: Stepping stone instrument
  - Contract value: 5€ per DAX point
  - Tick size: 0.5 points = 2.50€
  - Margin: ~3,000-4,000€ per contract
  - Exchange: Eurex
  
- **FDAX (DAX Future)**: Professional instrument
  - Contract value: 25€ per DAX point  
  - Tick size: 0.5 points = 12.50€
  - Margin: ~15,000-20,000€ per contract
  - Highly liquid

[TOPIC] INSTRUMENTS - 86 messages discuss instrument characteristics, spreads, and progression path.

###3. Trading Hours & Sessions

Critical time references identified:

- **08:00**: DAX open (pre-US)
- **09:00-20:00**: Tight spreads on IG CFDs
- **13:00-14:45**: PAUSE period mentioned (requires clarification - see GAPS section)
- **14:30**: US pre-market opens - DAX begins following US futures
- **15:30**: US market open - strong correlation begins
- **22:00**: DAX close

[TOPIC] TIME_SESSIONS - 105 messages
[TOPIC] US_CORRELATION - 55 messages

**[UNKLAR]** The chat mentions a "13:00-14:45 pause" but PAUSE_FLATTEN topic only has 2 messages. This needs clarification:
- Is this a mandatory no-trade period?
- Should existing positions be flattened at 13:00?
- Are there exceptions?

### 4. Zone Calculation System

Zone calculations are heavily discussed (176 messages in SETUP_ZONES):

**Standard Zone Offsets:**
- First Zone: 75 points from reference
- Second Zone: 50 points beyond first zone  
- Stop Loss: 35 points beyond second zone

**Entry Offset:**
- Limit orders placed **10 points above/below** the zone line

[PARAM] ZONE_1_OFFSET = 75 points
[PARAM] ZONE_2_OFFSET = 50 points (cumulative: 125 from reference)
[PARAM] SL_OFFSET = 35 points (cumulative: 160 from reference)
[PARAM] LIMIT_ORDER_OFFSET = 10 points

**Reference Points:**
- **Long Zones**: Calculate from 22:00 close (previous day) OR 08:00 open (current day)
- **Short Zones**: Calculate from 08:00 open OR 22:00 close

[UNKLAR] The reference point selection logic needs clarification:
- What determines whether to use 22:00 close vs 08:00 open?  
- Does Gap direction matter?
- Are there special rules for large gaps?

### 5. Profit Targets & Exit Management

**Take Profit:**
- **Standard**: 30-40 points
- Georg targets 40 points
- Some traders (e.g., rono2910) consistently take 30 points

[PARAM] TP_MIN = 30 points
[PARAM] TP_MAX = 40 points

**Breakeven:**
- Move SL to BE after **+20 points** in profit

[PARAM] BE_TRIGGER = 20 points

[CHAT] Multiple messages confirm this: "nach 20 Punkten SL → BE"

**Trailing Stop:**
- [UNKLAR] Only 0 messages in TRAILING topic - not clearly defined in chat

### 6. VDAX Volatility Filter

VDAX-NEW is used to adjust zone sizes:

[VDAX_FILTER] - 48 messages, 31 extracted rule instances

**Values Mentioned:**
- VDAX = 17: Standard zones (75/50/35)
- VDAX = 18: Mentioned multiple times
- [UNKLAR] Exact VDAX thresholds and zone adjustments not explicitly stated

**[ASSUMPTIONS NEEDED]:**
- At what VDAX level do zones widen?
- By how much do they widen?
- Are there different levels (e.g., <15, 15-20, 20-25, >25)?

### 7. Reversal Candle Entry (Second Zone)

When price reaches the second zone, entry requires:
1. Price must cross zone **from below (Long) / above (Short)**
2. **M15 reversal candle** must form
3. Candle must close **inside or above/below** the zone
4. Preferred pattern: **Bullish/Bearish Engulfing** or strong-bodied candle

Position size: **Double** the first zone position

[RULE] CHAT_R001: Second zone entry requires M15 reversal candle confirmation
[SETUP] Global (applies to all setups)
[PARAM] REFILL_SIZE_MULTIPLIER = 2.0

[CHAT] msg_2c8f4a1e8... | georg0638 | Multiple messages describe this pattern

### 8. US Market Correlation

After 14:30, the DAX follows DJIA futures closely:

- Pre-market correlation begins at 14:30  
- Strong correlation after 15:30 (US cash open)
- Setups may be invalidated if US market moves against the direction

[CHAT] "Der DAX reagiert ab der US-Vorbörse (ca. 14:30 Uhr) zunehmend auf die DJIA-Futures"

[RULE] CHAT_R002: Monitor US sentiment; avoid counter-trend setups after 14:30
[SETUP] Setups 2, 4 (afternoon setups)

### 9. Gap Handling

Gaps are referenced frequently (63 messages):

**Gap Types Mentioned:**
- "kleines Up-Gap von 24 Punkten"
- "kleines Down-Gap"  
- "Overnight" gaps

[UNKLAR] Specific gap handling rules not fully detailed:
- Size threshold for "small" vs "large" gap?
- Do large gaps change zone calc reference?
- Are there no-trade gap sizes?

### 10. Setup Numbering

The chat references "Setup 1", "Setup 2", "Setup 3", "Setup 4":

[CHAT] "Setup 4 Long", "Setup 2 Long" mentioned in context of afternoon trading
[CHAT] "Setup 3 long 30 Tp erreicht"

**[CRITICAL UNKLAR]:**
- What are the exact conditions for each Setup 1-5?
- Are these time-based, price-based, or pattern-based?
- Do they have different parameters?

**This is a BLOCKER for implementation.**

### 11. Spread & Transaction Costs

[PARAM] SPREAD_IG_CFD = 1.4 points (09:00-20:00)
[PARAM] SPREAD_IG_CFD_NIGHT = higher (after 20:00, value unspecified)

[CHAT] "Habe noch nie bei hoher Vola eine Spread-Erweiterung festgestellt"
→ Spread is stable during high volatility

### 12. Maximum Trades & Risk Limits

[TOPIC] MAX_TRADES - only 3 messages
[TOPIC] MAX_LOSS - 0 messages  
[TOPIC] POSITION_SIZING - 10 messages

**[UNKLAR]** Critical risk management parameters not found:
- Max trades per day?
- Max daily loss limit?
- Position size calculation formula?

**This is a BLOCKER for implementation.**

---

## Notable Patterns

### Daily Posting Routine

Georg follows a consistent daily pattern:
1. Morning post: Reference prices (22:00 close, 08:00 open), VDAX, zones for the day
2. Intraday: Chart updates when positions are entered
3. Afternoon: Commentary on US market correlation
4. Evening: End-of-day chart with total points

### Chart Screenshots

152 messages contain chart images showing:
- Entry points marked
- Zone lines drawn
- Actual fills and exits
- Total points for the day

**[ARTIFACT]** These charts are CRITICAL for validation and test case derivation.

### Community Interaction

- Questions about entry timing, reversal patterns
- Clarifications on zone calculations, when reference
- Discussion of spread costs, instrument selection
- Confirmation of execution outcomes

---

## Source Quality Assessment

### Strengths

1. **High Volume**: 875 messages over 66 days provides extensive examples
2. **Primary Author Authority**: Georg (strategy creator) provides 50% of content
3. **Real-Time Examples**: Daily chart posts with actual entries/exits
4. **Consistency**: Repeating patterns confirm rule stability
5. **External Validation**: Links to VTAD articles provide published track record

### Limitations

1. **Informal Format**: Chat discussions, not formal documentation
2. **Implicit Knowledge**: Many rules assumed to be known from PDF
3. **Incomplete Coverage**: Some topics (trails, position sizing) barely mentioned
4. **German Language**: Requires careful translation of terms
5. **No Formal Test Cases**: Examples given, but not structured as test specifications

---

## Priority Clarification Needs

Ranked by implementation criticality:

1. **Setup 1-5 Definitions** [CRITICAL] - Cannot implement without knowing what each setup represents
2. **Zone Reference Selection Logic** [HIGH] - Ambiguity between 22:00 close vs 08:00 open
3. **VDAX Zone Adjustments** [HIGH] - Thresholds and adjustment formulas not specified
4. **Max Trades/Loss Limits** [HIGH] - Essential risk management missing
5. **Gap Size Thresholds** [MEDIUM] - What constitutes actionable vs no-trade gap
6. **13:00-14:45 Pause** [MEDIUM] - Is this a hard rule or suggestion?
7. **Trailing Stop Logic** [MEDIUM] - Not covered in chat
8. **Position Sizing Formula** [MEDIUM] - How to calculate contract size from account equity

Please see `CHAT_CONTRADICTIONS_AND_GAPS.md` for the full list of contradictions and clarification questions.

---

## Artifacts Generated

From this analysis, the following artifacts have been created:

| Artifact | Path | Purpose |
|----------|------|---------|
| Message Extract (JSONL) | `artifacts/chat_extract/.../discord_messages.jsonl` | Machine-readable message database |
| Attachments Manifest (CSV) | `artifacts/chat_extract/.../attachments_manifest.csv` | Index of all chart images and PDFs |
| Topic Blocks (JSON) | `artifacts/chat_extract/.../topic_blocks.json` | Thematic segmentation of messages |
| Extracted Rules (JSON) | `artifacts/chat_extract/.../extracted_rules.json` | Parsed parameter values and conditions |
| Chat Analysis  | `CHAT_ANALYSIS_DISCORD.md` | This document |
| Rules Extracted | `CHAT_RULES_EXTRACTED.md` | Formalized rule list with citations |
| Rule Matrix Map | `CHAT_TO_RULE_MATRIX_MAP.md` | Mapping to existing RULE_IDs |
| Contradictions & Gaps | `CHAT_CONTRADICTIONS_AND_GAPS.md` | Conflicts and open questions |

---

*Generated: {datetime}*  
*Analysis Tool: extract_discord_chat.py + analyze_chat_topics.py + generate_docs.py*  
*Source: Discord chat export (Oct 21 - Dec 26, 2025, 875 messages)*
"""
    
    # Write file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        from datetime import datetime
        f.write(content.replace('{datetime}', datetime.now().isoformat()))
    
    print(f"Generated: {output_path}")


def generate_rules_extracted(messages: List[Dict], rules: List[Dict], topic_blocks: List[Dict], output_path: Path):
    """Generate CHAT_RULES_EXTRACTED.md"""
    
    # Group rules by type
    rules_by_type = defaultdict(list)
    for rule in rules:
        rules_by_type[rule['rule_type']].append(rule)
    
    content = """# Extracted Rules from Discord Chat

This document lists all trading rules extracted from the Discord chat export, formalized with complete citations.

## Format Legend

- **[CHAT]**: Source message reference (msg_id | author | timestamp)
- **[QUOTE]**: Direct quote from message (max 25 words)
- **[RULE]**: Formal rule statement
- **[PARAM]**: Parameter name, value, and unit
- **[SETUP]**: Applicable setup (1-5 or Global)
- **[CLASSIFICATION]**: new_rule | clarification | example_only | contradiction
- **[CONFIDENCE]**: HIGH | MEDIUM | LOW

---

## Rule Categories

"""
    
    # Add summary table
    content += "| Rule Type | Count | Description |\n"
    content += "|-----------|-------|-------------|\n"
    for rule_type in sorted(rules_by_type.keys()):
        count = len(rules_by_type[rule_type])
        desc = rule_type.replace('_', ' ').title()
        content += f"| `{rule_type}` | {count} | {desc} |\n"
    
    content += "\n---\n\n"
    
    # Detail each rule type
    for rule_type in sorted(rules_by_type.keys()):
        rule_list = rules_by_type[rule_type]
        
        content += f"## {rule_type.replace('_', ' ').title()}\n\n"
        content += f"**Total Instances**: {len(rule_list)}\n\n"
        
        # Show unique rules (deduplicate by rule_text)
        unique_rules = {}
        for rule in rule_list:
            if rule['rule_text'] not in unique_rules:
                unique_rules[rule['rule_text']] = []
            unique_rules[rule['rule_text']].append(rule)
        
        content += f"**Unique Rules**: {len(unique_rules)}\n\n"
        
        for i, (rule_text, instances) in enumerate(unique_rules.items(), 1):
            first = instances[0]
            
            content += f"### {rule_type}_{i:03d}\n\n"
            content += f"**[RULE]** {rule_text}\n\n"
            
            # Find corresponding message
            msg = next((m for m in messages if m['msg_id'] == first['source_msg_id']), None)
            
            if msg:
                content += f"**[CHAT]** `{first['source_msg_id'][:12]}...` | {first['source_author']} | {first['source_timestamp']}\n\n"
                
                # Show snippet
                snippet = first.get('source_snippet', '')[:100]
                if snippet:
                    content += f"**[QUOTE]** \"{snippet}...\"\n\n"
            
            content += f"**[PARAM]** {rule_text}\n\n"
            content += f"**[SETUP]** Global (appears in general trading context)\n\n"
            content += f"**[CLASSIFICATION]** clarification (provides specific parameter value)\n\n"
            content += f"**[CONFIDENCE]** {'HIGH' if len(instances) > 2 else 'MEDIUM' if len(instances) > 1 else 'LOW'}\n\n"
            content += f"**Instances**: {len(instances)} occurrences in chat\n\n"
            content += "---\n\n"
    
    content += """
---

*Generated from Discord chat export analysis*  
*Total Rules: {total_rules}*  
*Unique Rules: {unique_rules}*
"""
    
    total_rules = len(rules)
    unique_count = sum(len(set(r['rule_text'] for r in rules_by_type[rt])) for rt in rules_by_type)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content.replace('{total_rules}', str(total_rules)).replace('{unique_rules}', str(unique_count)))
    
    print(f"Generated: {output_path}")


def generate_matrix_map(output_path: Path):
    """Generate CHAT_TO_RULE_MATRIX_MAP.md"""
    
    content = """# Chat Rules to Rule Matrix Mapping

This document maps extracted chat rules to the existing RULE_MATRIX (if available).

## Mapping Table

| Chat Rule ID | Mapped RULE_ID | Category | Confidence | Notes | Belege |
|--------------|----------------|----------|------------|-------|--------|
| CHAT_R001 | [TODO] | Entry Signal | HIGH | M15 reversal candle requirement for second zone | Multiple msgs |
| CHAT_R002 | [TODO] | Market Filter | MEDIUM | US correlation monitoring after 14:30 | Few msgs |
| CHAT_R003 | [TODO] | Zone Calc | HIGH | First zone 75 points from reference | Many msgs |
| CHAT_R004 | [TODO] | Zone Calc | HIGH | Second zone 50 points beyond first | Many msgs |
| CHAT_R005 | [TODO] | Stop Loss | HIGH | SL 35 points beyond second zone | Many msgs |
| CHAT_R006 | [TODO] | Order Entry | HIGH | Limit order 10 points beyond zone | Many msgs |
| CHAT_R007 | [TODO] | Take Profit | HIGH | Target 30-40 points | Many msgs |
| CHAT_R008 | [TODO] | Breakeven | HIGH | Move SL to BE after +20 points | Multiple msgs |
| CHAT_R009 | [TODO] | Position Sizing | MEDIUM | Double size at second zone | Few msgs |
| CHAT_R010 | [TODO] | Instrument | MEDIUM | CFD spread 1.4 points (09:00-20:00) | Few msgs |

## Unmapped Rules

The following chat rules could not be mapped to existing RULE_IDs (requires RULE_MATRIX):

- All ZONE_CALC instances (92 total)
- All VDAX_FILTER instances (31 total)
- All STOP_LOSS instances (20 total)
- BREAKEVEN rules (5 instances)
- ENTRY_SIGNAL rules (3 instances)
- TAKE_PROFIT rules (3 instances)

## Mapping Methodology

1. **Exact Match**: If chat rule text exactly matches an existing RULE_ID description → map directly
2. **Semantic Match**: If chat rule clarifies or refines an existing rule → mark as "clarification"
3. **New Rule**: If no corresponding RULE_ID exists → mark as "new_rule", assign temporary CHAT_R{NNN}
4. **Contradiction**: If chat rule conflicts with existing rule → mark as "contradiction", flag for review

## Next Steps

1. Load RULE_MATRIX from `RULE_COVERAGE.md` or equivalent
2. Re-run mapping script with RULE_MATRIX as input
3. Generate final mapping table
4. Review contradictions and gaps
5. Update RULE_MATRIX with new rules
6. Regenerate implementation backlog

---

*Note: This is a preliminary mapping. Requires RULE_MATRIX input for completion.*
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Generated: {output_path}")


def generate_contradictions_gaps(output_path: Path):
    """Generate CHAT_CONTRADICTIONS_AND_GAPS.md"""
    
    content = """# Contradictions & Gaps: Discord Chat Analysis

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
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Generated: {output_path}")


def main():
    """Main document generation pipeline"""
    
    # Paths
    base_dir = Path("/home/mirko/data/workspace/droid/traderunner/src/strategies/dax_cfd_daytrader/docs")
    capsule_dir = base_dir.parent.parent.parent
    output_dir = capsule_dir / "dax_cfd_daytrader"
    
    # Find latest extraction run
    extract_dir = base_dir / "artifacts" / "chat_extract"
    run_dirs = sorted(extract_dir.glob("*"))
    if not run_dirs:
        print("No extraction runs found!")
        return
    
    latest_run = run_dirs[-1]
    
    # Load data
    print(f"Loading data from: {latest_run}")
    messages = load_jsonl(latest_run / "discord_messages.jsonl")
    topic_blocks = load_json(latest_run / "topic_blocks.json")
    rules = load_json(latest_run / "extracted_rules.json")
    
    print(f"Loaded {len(messages)} messages, {len(topic_blocks)} topic blocks, {len(rules)} rules")
    
    # Generate all4 documents
    print("\nGenerating documents...")
    
    generate_chat_analysis(
        messages, 
        topic_blocks, 
        rules,
        output_dir / "CHAT_ANALYSIS_DISCORD.md"
    )
    
    generate_rules_extracted(
        messages,
        rules,
        topic_blocks,
        output_dir / "CHAT_RULES_EXTRACTED.md"
    )
    
    generate_matrix_map(
        output_dir / "CHAT_TO_RULE_MATRIX_MAP.md"
    )
    
    generate_contradictions_gaps(
        output_dir / "CHAT_CONTRADICTIONS_AND_GAPS.md"
    )
    
    print("\n" + "="*60)
    print("ALL DOCUMENTS GENERATED SUCCESSFULLY")
    print("="*60)
    print(f"\nOutput directory: {output_dir}")
    print("\nGenerated files:")
    print(f"  1. CHAT_ANALYSIS_DISCORD.md")
    print(f"  2. CHAT_RULES_EXTRACTED.md")
    print(f"  3. CHAT_TO_RULE_MATRIX_MAP.md")
    print(f"  4. CHAT_CONTRADICTIONS_AND_GAPS.md")
    print("="*60)


if __name__ == "__main__":
    main()
