# Impulse 600-Session First Trigger Export

## Source
- Dataset: `/var/lib/trading/marketdata/mysql_daily/exports/stock_all_2024-01-01_2026-05-15.parquet`
- Available sessions: `600`
- Session range: `2024-01-01` to `2026-05-07`

## Definitions
- First trigger: `precondition_passed and prewindow_path_passed and breakout_passed and breakout_bar_passed`
- Final trigger: `trigger_passed == True`

## Cold-Phase Filter
- Price band: `2.0` to `9.0`
- Mean volume band: `100000.0` to `1500000.0`
- Median volume band: `80000.0` to `1200000.0`
- Pre-window: `30` bars
- Confirm offset: `1` bar

## Trigger Thresholds
- min_price_lr_trimmed: `-0.1`
- min_vol_lr_trimmed: `-100000.0`
- min_price_ratio_prev_to_breakout: `1.172897`
- min_volume_ratio_prev_to_breakout: `19.617994`
- min_price_ratio_prev_to_confirm: `1.158879`
- min_volume_ratio_prev_to_confirm: `3.01405`
- require_breakout_green: `False`
- min_confirm_close_vs_breakout_close: `0.9`
- min_confirm_close_position_in_range: `0.5`
- min_pre_max_drawdown: `-0.6`
- max_pre_gap_down_count: `8`

## Counts
- First-trigger candidates: `156`
- Final-trigger candidates: `65`

## Invalid / Excluded Symbols
- `ITI`
  - status: `invalid_excluded`
  - reason: `source_data_identity_or_stitching_issue`
  - removed rows: `2`
  - removed breakout sessions: `2024-08-08, 2024-11-04`
  - note: Removed from research export after detecting an invalid post-2024-11-01 price regime inconsistent with Iteris acquisition at $7.20 cash/share.
- `TERN`
  - status: `invalid_excluded`
  - reason: `source_data_tail_regime_issue`
  - removed rows: `1`
  - removed breakout sessions: `2025-11-02`
  - note: Removed after local May 2026 tail collapsed to sub-$1 prices inconsistent with Yahoo Finance for Terns Pharmaceuticals.
- `RGTIW`
  - status: `invalid_excluded`
  - reason: `non_common_stock_warrant`
  - removed rows: `1`
  - removed breakout sessions: `2025-07-15`
  - note: Removed because RGTIW is a warrant, not common stock, and should not be part of the common-stock baseline basket.

## Saved Files
- CSV: `src/strategies/perlentaucher_daily_scan/docs/research/impulse_600_session_first_trigger_candidates_relaxed_baseline.csv`
- Meta JSON: `src/strategies/perlentaucher_daily_scan/docs/research/impulse_600_session_first_trigger_candidates_relaxed_baseline.meta.json`

## Notes
- `is_anchor_reference_symbol` marks the current anchor names: `AXTI, IONQ, MRAM, SOUN`
- `INOD` and `VTYX` remain in the basket, but any analysis must ignore zero-volume bars.
- This export is valid until the cold-phase filter or trigger thresholds change.
