# InsideBar SSOT Inventory (Step 1 – Read‑only)

Goal: map where `config.py` / `InsideBarConfig` is used and where defaults currently originate, before any refactor.

---

## 1) config.py usage map

**Strategy core & adapter path**

- `src/strategies/inside_bar/core.py`  
  - Imports `InsideBarConfig` + `SessionFilter`.  
  - Class init expects an `InsideBarConfig` instance.  
  - Line refs: `core.py` uses `InsideBarConfig` in constructor and docs.  
  - Evidence: `core.py` import + class signature.

- `src/strategies/inside_bar/__init__.py`  
  - `_core_config_from_params()` constructs `InsideBarConfig` from `params`.  
  - Line refs: **18–51**.  
  - This is the *runtime* mapping for the pipeline `run_pipeline → build_signal_frame → plugin`.

**Config helpers**

- `src/strategies/inside_bar/config.py`  
  - Defines `InsideBarConfig` dataclass (defaults + validation).  
  - `load_config() / load_default_config()` are YAML helpers.  
  - Line refs: **200–335** (defaults + validation), **337+** (loaders).

**UI & SSOT managers**

- `trading_dashboard/config_store/strategy_config_store.py`  
  - Uses `InsideBarConfigManager` (SSOT YAML manager).  
  - Source: `src/strategies/config/managers/inside_bar_manager.py`.

**Tests (explicit config.py usage)**

- `src/strategies/inside_bar/tests/test_core.py`  
  - Instantiates `InsideBarConfig` directly for unit tests.
- `tests/test_inside_bar_config_loading.py`  
  - Calls `load_default_config()` and `get_default_config_path()`.
- `tests/test_session_filter_timezone.py`, `tests/test_netting_overlapping.py`, `tests/test_mvp_trigger_validity_netting.py`  
  - Instantiate `InsideBarConfig` directly.

---

## 2) Default sources map (where defaults are currently introduced)

### A) YAML SSOT (desired single source)

- `src/strategies/inside_bar/insidebar_intraday.yaml`  
  - Defines *core* and *tunable* defaults per version.  
  - Line refs (v1.0.1 example): **25–47**.  
  - Key fields: `valid_from_policy`, `session_filter`, `atr_period`, `min_mother_bar_size`, etc.

### B) Runtime mapping defaults (silent fallback)

- `src/strategies/inside_bar/__init__.py::_core_config_from_params`  
  - Uses `params.get(key, DEFAULT)` for every core field.  
  - Line refs: **20–49**.  
  - This means: *if a param is missing*, code injects a default silently.

### C) Dataclass defaults

- `src/strategies/inside_bar/config.py::InsideBarConfig`  
  - Declares defaults for all parameters (e.g., `valid_from_policy="signal_ts"`).  
  - Line refs: **200–335**.  
  - These defaults are applied when `InsideBarConfig(**params)` is called and a field is missing.

### D) UI / CLI / Spyder overrides

- `src/axiom_bt/pipeline/cli.py`  
  - Overrides allowed via CLI flags (valid_from_policy, order_validity_policy, etc.)
- `src/axiom_bt/pipeline/run_pipeline_spyder.py`  
  - Hardcoded overrides for requested_end, validity policy, etc.
- `trading_dashboard/services/new_pipeline_adapter.py`  
  - Constructs `strategy_params` from UI values and passes to pipeline.

---

## 3) Observed silent‑override paths (risk to SSOT)

1) **Runtime Fallbacks in `_core_config_from_params`**  
   - Missing params are silently filled from code defaults.
2) **Dataclass Defaults in `InsideBarConfig`**  
   - Missing params silently filled again.
3) **UI/CLI Overrides are not always audited**  
   - No enforced “core vs tunable” override policy at the boundary.

---

## 4) Step‑1 Acceptance Check (target later)

> There must be **no silent path** where missing params are auto‑filled by `config.py` defaults.  
> Either the YAML provides them, or the run fails loudly.

---

## 5) Evidence snippets (line refs)

- `_core_config_from_params` defaults: `src/strategies/inside_bar/__init__.py#L18-L51`  
- `InsideBarConfig` defaults: `src/strategies/inside_bar/config.py#L200-L335`  
- SSOT YAML defaults: `src/strategies/inside_bar/insidebar_intraday.yaml#L1-L67`
