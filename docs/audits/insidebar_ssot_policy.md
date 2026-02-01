# InsideBar SSOT Policy (Step 2 – YAML as Single Source of Truth)

**Goal:** Make YAML the only authoritative parameter source. No silent defaults from code, no hidden overrides.

---

## 1) SSOT Loader (Concept)

**Loader responsibilities:**

1. Read YAML for `strategy_id + version`.
2. Validate required keys.
3. Produce a single `effective_config` (core + tunable).
4. Record the `config_path` in `run_manifest.json`.

**Required keys (minimum):**
- `required_warmup_bars`
- `core` (dict)
- `tunable` (dict)

**Effective config format (example):**
```
effective_config = {
  "core": { ... },
  "tunable": { ... },
  "strategy_id": "...",
  "version": "...",
  "required_warmup_bars": 40,
}
```

---

## 2) Override Policy

### 2.1 Non‑overridable (Core / Rule Keys)

These keys MUST come from YAML; any override must raise an error.

**Core Keys (examples):**
- `valid_from_policy`
- `order_validity_policy`
- `breakout_confirmation`
- `inside_bar_mode`
- `session_filter`
- `session_timezone`
- `entry_level_mode`

**Rationale:** These affect signal timing and semantics. Silent overrides would invalidate SSOT.

---

### 2.2 Overridable (Tunable Keys)

Allowed to override *only if explicitly declared as tunable*.

**Tunable Keys (examples):**
- `atr_period`
- `risk_reward_ratio`
- `min_mother_bar_size`
- `max_deviation_atr`
- `max_pattern_age_candles`
- `max_position_loss_pct_equity`
- `fees_bps`, `slippage_bps` *(if surfaced at UI/CLI layer)*

**Rationale:** These tune risk/scale but do not redefine the pattern rules.

---

## 3) Override Audit (Manifest)

Every override must be recorded into the run manifest:

```
"config_overrides": [
  {
    "key": "atr_period",
    "yaml_value": 15,
    "override_value": 20,
    "source": "UI"
  }
]
```

If a **core key** override is attempted → **error**.

---

## 4) Effective Config Debug

Optional (but recommended):
- Add `dbg_effective_*` fields for visibility in `events_intent.csv`.
- Example:
  - `dbg_effective_valid_from_policy`
  - `dbg_effective_order_validity_policy`

---

## 5) Run Contract

**No run may proceed** unless:
- YAML is fully loaded.
- All required keys present.
- Overrides are validated and audited.

---

## 6) Examples

### ✅ Allowed override
```
override: atr_period = 20
result: accepted (tunable)
manifest: logged
```

### ❌ Forbidden override
```
override: valid_from_policy = next_bar
result: ERROR (core key)
```

---

## 7) Acceptance Criteria (Step 2)

- YAML is the only source of defaults.
- Overrides must be declared + auditable.
- No core‑key override allowed.
- Any deviation is visible in `run_manifest.json`.

