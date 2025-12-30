# Chat Rules to Rule Matrix Mapping

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
