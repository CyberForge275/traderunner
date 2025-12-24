# Strategy Factory: Labs & Lifecycle

This document defines how strategies move through the
**Automatic Trading Factory** and what "immutable strategy" means
from an engineering perspective.

It is the reference for:

- Explore Lab
- Backtest Lab
- Pre-Papertrading Lab
- Papertrading Lab
- Real Money Trading Room

and for how Strategy versions must be handled in code and tooling
(e.g. Antigravity).


## 1. Labs Overview

We distinguish five stages:

1. **Explore Lab**
   - Purpose: First-time exploration and translation of ideas into Python.
   - Typical sources: Pine scripts, community code, RealTest scripts, ad-hoc prototypes.
   - Strategy state: **Draft** (experimental, mutable).
   - Guarantees: None. The goal is to find out whether the idea can be
     expressed as a viable Python strategy at all.

2. **Backtest Lab**
   - Purpose: Turn a draft into a **proper strategy implementation** with
     full backtesting.
   - Requirements:
     - Clean Python module with clear entry points.
     - Stable parameter model (StrategyConfig).
     - Backtests across meaningful universes and time ranges.
   - Output:
     - A **Strategy Version** that has passed minimum backtest quality gates
       (performance, stability, robustness).

3. **Pre-Papertrading Lab**
   - Purpose: Run the exact Strategy Version from Backtest Lab on
     live-like data (replay, websockets) and generate real-time paper signals.
   - Characteristics:
     - Same Strategy Version as in Backtest Lab.
     - No code or parameter changes allowed for that version.
     - Focus on integration:
       - data → signals → order intents → APIs.
   - Duration: e.g. 1–2 weeks per version.

4. **Papertrading Lab**
   - Purpose: Run the same Strategy Version on a real broker
     (e.g. Interactive Brokers Paper/Demo account).
   - Characteristics:
     - Same Strategy Version and config as in Backtest & Pre-Papertrade.
     - Real order routing, but no real money.
     - Focus on:
       - execution quality,
       - slippage / fills,
       - operational robustness.

5. **Real Money Trading Room**
   - Purpose: Run the Strategy Version with real money.
   - Characteristics:
     - Strategy Version is fully frozen and traceable.
     - Any change requires a **new version** and a new full lifecycle run
       through the Labs.


## 2. Strategy Version Model (Atomicity)

A strategy is identified by a **stable key**, e.g.:

- `insidebar_intraday`
- `insidebar_intraday_v2`
- `rudometkin_moc_mode`

A **Strategy Version** is:

> (strategy_key, impl_version, config_profile, config_profile_version)

Example:

- `strategy_key`: `insidebar_intraday`
- `impl_version`: `3`
- `config_profile`: `default`
- `config_profile_version`: `2`

We refer to this as:

- `insidebar_intraday@v3` (`profile=default:v2`)

### 2.1 Immutability Line

The **immutability line** is at the **end of Backtest Lab**:

> Once a `(strategy_key, impl_version, config_profile, config_profile_version)`
> has been promoted **out of Backtest Lab**, it MUST be treated as immutable.

**Immutable** means:

- No changes to strategy code that affect behavior.
- No changes to the config profile contents.
- No silent bugfixes "in place":
  - If code behavior needs to change → bump `impl_version` (e.g. from v3 to v4).
  - If config needs to change → bump `config_profile_version`.

Any modification after promotion must be done by:

1. Creating a **new Strategy Version** (new `impl_version` and/or profile version).
2. Running the new version again through the Labs (Backtest → Pre-Papertrade → Paper → Real).


## 3. Allowed changes per Lab

### 3.1 Explore Lab

- Code: fully mutable
- Config: mutable
- Strategy ID:
  - either temporary (e.g. `insidebar_explore_2025_001`),
  - or a draft under a specific namespace.

Allowed:

- Renames, restructurings, API changes.
- Throwing away failed experiments.

Not allowed:

- Use of Explore-only versions in Pre-Papertrade, Paper, or Real.


### 3.2 Backtest Lab

During active Backtest development:

- Code: can still be refactored and adjusted.
- Config: can still be tuned.

At the moment a version is **approved**:

- A new `impl_version` is set (e.g. `3`).
- The config profile is frozen (with a `config_profile_version`).
- A Strategy Version record is created in the database.

From this point on:

> This Strategy Version is **immutable** and may enter the subsequent Labs.

### 3.3 Pre-Papertrading, Papertrading, Real Money

For these Labs:

- Only **immutable Strategy Versions** may be used.
- Using a strategy in these Labs implies:
  - There exists a Backtest run referencing the same Strategy Version.
  - Code and config exactly match the Backtest state.

Changing code/config of a Strategy Version that has runs in these Labs is **forbidden**.
Instead, create a new version and restart the lifecycle.


## 4. Invariants that must hold in code

These invariants must be enforced by code, tests and AI tools:

1. **Versioned usage only in higher Labs**

   - Pre-Papertrade, Papertrading and Real Money code paths may only accept
     Strategy Versions that are:
       - registered in the Strategy Catalog / Registry,
       - marked as `stage >= BACKTEST_LAB_APPROVED`.

   - Passing a "draft" or unapproved strategy into these Labs MUST raise
     a clear error.

2. **No in-place modification of promoted Strategy Versions**

   - Once a Strategy Version has `stage >= BACKTEST_LAB_APPROVED`:
     - its metadata is frozen,
     - its config profile is frozen,
     - any functional change requires a new `impl_version` or
       `config_profile_version`.

3. **Consistent Strategy Version across Labs**

   - For any real-money or paper run:
     - there must exist:
       - at least one Backtest run with the same `strategy_version_id`,
       - at least one Pre-Papertrade run with the same `strategy_version_id`
         (if configured that way).
   - The system must be able to answer:
     > "Show me all runs (Backtest → Pre-Papertrade → Paper → Real)
       for Strategy Version X."

4. **No „anonymous“ strategies in higher Labs**

   - Strategy selection in Pre-Papertrade, Paper, and Real must always be done
     via an explicit Strategy Version ID (key + impl_version + profile).


## 5. Implementation Guidelines

### 5.1 Strategy Catalog & Metadata

- There is a central **Strategy Catalog** (Python module), which defines:
  - `StrategyMetadata` per strategy key.
  - Known `impl_version` values.
  - Supported Labs (capabilities, e.g. `supports_pre_papertrade`).

- `STRATEGY_REGISTRY` (e.g. in `apps/streamlit/state.py`) is the **only**
  source of truth for available strategies in the UI.

- All UIs (Backtest, Pre-Papertrade, etc.) obtain their strategy options
  from this registry, not from separate hard-coded lists.


### 5.2 Strategy Version & Runs in the database

- There is a `strategy_version` table with:
  - `strategy_version_id`
  - `strategy_key`
  - `impl_version`
  - `config_profile`
  - `config_profile_version`
  - `commit_hash` (optional, for traceability)
  - `stage` (one of: explore, backtest_approved, pre_papertrade_done, paper_done, live)

- There is a `strategy_run` table with:
  - `run_id`
  - `strategy_version_id`
  - `lab_stage` (backtest, pre_papertrade, paper, live)
  - timestamps, metrics, etc.

All Labs (Backtest, Pre-Papertrade, Paper, Real) operate on a
`strategy_version_id`, not just a bare strategy name.


### 5.3 Enforcement in code

- Pre-Papertrade service / adapter:
  - Accepts only Strategy Versions with `stage >= backtest_approved`.
  - Fails fast with a clear error if an unapproved version is selected.

- Papertrading and Real Money workers:
  - Accept only Strategy Versions with the required stage
    (e.g. `pre_papertrade_done` for Paper, `paper_done` for Live).

- Tests:
  - Architecture tests to ensure:
    - higher Labs never reference non-versioned strategies directly.
  - Unit/integration tests to ensure:
    - trying to use a draft version in Pre-Papertrade or Paper raises an error.


## 6. Requirements for AI tools (e.g. Antigravity)

When an AI proposes or modifies strategy code:

1. It MUST read:
   - ENGINEERING_MANIFEST.md
   - AI_CONTRIBUTION_GUIDE.md
   - this document (FACTORY_LABS_AND_STRATEGY_LIFECYCLE.md)

2. If the code it touches belongs to a Strategy Version that is already
   `stage >= backtest_approved`:
   - It MUST NOT change behavior in place.
   - It MUST:
     - either refuse the change and suggest creating a new version,
     - or explicitly create a new `impl_version` and strategy entry,
       following the documented lifecycle.

3. It MUST NOT bypass lifecycle rules, e.g.:
   - by "quickly patching" a promoted strategy without version bump,
   - by adding new strategy IDs in UIs that are not in the Catalog.

4. Any change that affects behavior of a promoted strategy MUST:
   - bump `impl_version` or profile version,
   - add/update tests,
   - and be treated as a new Strategy Version that must go through the Labs again.
