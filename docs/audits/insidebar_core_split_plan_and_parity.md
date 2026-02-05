# InsideBar core.py split plan + parity

## Preconditions
- main == origin/main (clean) verified before branch
- Tag created: insideBar_pre_core_split_v1
- Branch: refactor/insidebar-core-split-v1

## Current core.py summary
- File: src/strategies/inside_bar/core.py
- LoC: 838
- Primary responsibilities:
  - RawSignal model
  - ATR calculation
  - InsideBar detection (vectorized)
  - Session state machine + signal generation
  - Orchestration (process_data)

## Target structure
- models.py: RawSignal + data models
- indicators.py: ATR calc (unchanged behavior)
- pattern_detection.py: detect_inside_bars (unchanged behavior)
- session_logic.py: session state machine + generate_signals (unchanged behavior)
- core.py: orchestrator only (process_data, wiring)

## Parity strategy
- Baseline test: PYTHONPATH=src:. pytest -q src/strategies/inside_bar/tests/test_core.py
- After each mechanical commit: same test command
- No behavior change: only moving code, no logic edits

## Rollback
- git checkout main
- git reset --hard insideBar_pre_core_split_v1

## Diff Summary per Commit

- Commit A: extract RawSignal to models.py; update imports (core/__init__/strategy/tests). Tests: pytest -q src/strategies/inside_bar/tests/test_core.py (pass).
- Commit B: extract ATR calc to indicators.py; core.calculate_atr delegates. Tests: pytest -q src/strategies/inside_bar/tests/test_core.py (pass).
- Commit C: extract inside bar detection to pattern_detection.py; core.detect_inside_bars delegates. Tests: pytest -q src/strategies/inside_bar/tests/test_core.py (pass).
