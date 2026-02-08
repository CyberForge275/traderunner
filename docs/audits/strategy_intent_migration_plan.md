# Strategy-Owned Intent & Schema Migration Plan (Phases 0–5)

Status: **Plan only (no code changes)**

## Scope
- Move intent generation and schema ownership into Strategy.
- Pipeline becomes neutral (no strategy tokens).
- Ensure determinism and parity via intent-hash checks.

---

## Phase 0 — Inventory & Contracts (read-only)
**Goal:** Prove current contracts and where strategy tokens leak.

**Current call chain (run_pipeline):**
1) build OHLCV bars
2) build_signal_frame (strategy)
3) generate_intent (pipeline)
4) generate_fills
5) execute (trades)

**Artifact ownership (SSOT):**
- `events_intent.csv`: Strategy-owned, frozen stream
- `fills.csv` / `trades.csv`: pipeline/execution-owned

**Guardrail test (SSOT):**
- `tests/test_no_strategy_schema_outside_strategies.py` (regex scan)

**Deliverables:**
- “Current Flow vs Target Flow” summary
- Token-leak list (file → token group)

---

## Phase 1 — Strategy provides Intent Producer
**Goal:** Strategy owns all intent generation (no pipeline strategy logic).

**Interface:**
`StrategyIntentProducer.generate_intent(signals_frame, strategy_id, version, params) -> IntentArtifacts`

**Location (strategy-owned):**
- `src/strategies/<strategy_id>/intent_generation.py` (preferred)

**Rules:**
- All inside_bar/mother_/breakout_/strategy overrides move into Strategy.
- Pipeline only consumes `events_intent` + `signals_frame`.

**Deliverables:**
- “StrategyIntentProducer contract” doc
- Mapping: fields Strategy guarantees in `events_intent`

---

## Phase 2 — Schema SSOT (Strategy-owned)
**Goal:** Strategy defines schema/version and validates outputs.

**Per-strategy schema file:**
- `signal_schema.py` with:
  - schema_version
  - required_columns
  - optional_debug_columns
  - intent_columns

**Strategy validation (end of compute):**
- Required columns present
- Datatypes / tz correctness
- oco_group_id requirement by version

**Deliverables:**
- Schema definition per strategy
- Optional “Schema Drift Report” tooling

---

## Phase 3 — Pipeline neutral (signals.py removed or generic)
**Goal:** Pipeline has zero strategy tokens.

**Runner changes:**
- Replace pipeline `generate_intent(...)` with `strategy.generate_intent(...)`.

**Pipeline responsibilities only:**
- Accept `events_intent` DataFrame
- Hash / write artifacts
- Execute fills/trades

**Guardrail:**
- `rg 'inside_bar|mother_|breakout_|ib__' src/axiom_bt/pipeline` → 0 hits

---

## Phase 4 — Parity & Determinism (Golden vs Dev)
**Goal:** Migration cannot silently drift results.

**Freeze rule:**
- `events_intent.csv` is SSOT and immutable after creation.

**Parity checks:**
- **Intent Hash Parity** (CI)
- Intent → Fill → Trade delta chain

**Deliverables:**
- “Intent Hash Parity” check in CI
- “Top-20 Intent Delta” report

---

## Phase 5 — Cutover & Rollback
**Goal:** Safe rollout with quick rollback.

**Steps:**
1) Dual runs: legacy vs new (compare intent_hash, deltas, trades)
2) Feature flag: `USE_STRATEGY_INTENT=1`
3) Tag before switch: `insideBar_pre_intent_migration_v1`
4) Rollback: `git reset --hard insideBar_pre_intent_migration_v1`
5) Deprecation cleanup after stable period

**Deliverables:**
- Rollout checklist
- Rollback plan (tag + reset)

