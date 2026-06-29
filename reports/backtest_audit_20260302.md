# Backtest Audit 2026-03-02 (hb_cmpind_rerun_300_40d)

## Executive Summary
- Runs analyzed: **22** (successful + required artifacts present).
- Aggregate net PnL: **-8356.03**.
- Mean profit factor across runs: **0.830**.
- Positive net runs: **8/22**.
- Edge status: **weak/fragile** if performance is concentrated by symbol/time bucket.
- Top symbol concentration share: **22.44%** of total net.
- Top 10% trades concentration share: **34.61%**.
- Main risk flags: coverage incompleteness, symbol concentration, regime dependence.
- Slippage/fees are included if present in `trades.csv` cost columns.
- Determinism note: all joins sorted by timestamp/template_id, no random sampling used.

## A) Run Inventory
| run_id                             | status   | symbol   | timeframe   |   lookback_days | requested_end   | missing_artifacts   |
|:-----------------------------------|:---------|:---------|:------------|----------------:|:----------------|:--------------------|
| 260302_161004_HOOD_HB_cmpind_rerun | success  | HOOD     | M5          |             300 | 2026-02-27      |                     |
| 260302_161006_COIN_HB_cmpind_rerun | success  | COIN     | M5          |             300 | 2026-02-27      |                     |
| 260302_161008_PYPL_HB_cmpind_rerun | success  | PYPL     | M5          |             300 | 2026-02-27      |                     |
| 260302_161009_AAOI_HB_cmpind_rerun | success  | AAOI     | M5          |              40 | 2026-03-01      |                     |
| 260302_161010_ADI_HB_cmpind_rerun  | success  | ADI      | M5          |              40 | 2026-03-01      |                     |
| 260302_161011_AMAT_HB_cmpind_rerun | success  | AMAT     | M5          |              40 | 2026-03-01      |                     |
| 260302_161011_AMD_HB_cmpind_rerun  | success  | AMD      | M5          |              40 | 2026-03-01      |                     |
| 260302_161011_ASML_HB_cmpind_rerun | success  | ASML     | M5          |              40 | 2026-03-01      |                     |
| 260302_161011_AXTI_HB_cmpind_rerun | success  | AXTI     | M5          |              40 | 2026-03-01      |                     |
| 260302_161013_BKR_HB_cmpind_rerun  | success  | BKR      | M5          |              40 | 2026-03-01      |                     |
| 260302_161014_IBRX_HB_cmpind_rerun | success  | IBRX     | M5          |              40 | 2026-03-01      |                     |
| 260302_161014_SOFI_HB_cmpind_rerun | success  | SOFI     | M5          |             300 | 2026-02-27      |                     |
| 260302_161015_INTC_HB_cmpind_rerun | success  | INTC     | M5          |              40 | 2026-03-01      |                     |
| 260302_161015_LITE_HB_cmpind_rerun | success  | LITE     | M5          |              40 | 2026-03-01      |                     |
| 260302_161016_MNST_HB_cmpind_rerun | success  | MNST     | M5          |              40 | 2026-03-01      |                     |
| 260302_161016_MU_HB_cmpind_rerun   | success  | MU       | M5          |              40 | 2026-03-01      |                     |
| 260302_161016_STX_HB_cmpind_rerun  | success  | STX      | M5          |              40 | 2026-03-01      |                     |
| 260302_161017_AAOI_HB_cmpind_rerun | success  | AAOI     | M5          |             300 | 2026-02-27      |                     |
| 260302_161017_WBD_HB_cmpind_rerun  | success  | WBD      | M5          |              40 | 2026-03-01      |                     |
| 260302_161017_WDC_HB_cmpind_rerun  | success  | WDC      | M5          |              40 | 2026-03-01      |                     |
| 260302_161031_IBRX_HB_cmpind_rerun | success  | IBRX     | M5          |             300 | 2026-02-27      |                     |
| 260302_161039_LITE_HB_cmpind_rerun | success  | LITE     | M5          |             300 | 2026-02-27      |                     |

## B) KPI Board
### Per Run
| run_id                             | symbol   |   trades |     net_pnl |   profit_factor |   winrate |   expectancy_usd |   expectancy_r |   avg_hold_min |     max_dd |     sharpe |
|:-----------------------------------|:---------|---------:|------------:|----------------:|----------:|-----------------:|---------------:|---------------:|-----------:|-----------:|
| 260302_161017_AAOI_HB_cmpind_rerun | AAOI     |      174 |  2620.09    |        1.31036  |  0.528736 |        15.058    |       13.0873  |        18.477  | -0.0678479 |   1.86973  |
| 260302_161009_AAOI_HB_cmpind_rerun | AAOI     |       26 |  1722.2     |        2.43263  |  0.538462 |        66.2386   |        6.56848 |        19.8077 | -0.0360164 |   4.97413  |
| 260302_161015_LITE_HB_cmpind_rerun | LITE     |       19 |   910.851   |        1.86911  |  0.684211 |        47.9395   |        3.13254 |        25.5263 | -0.0519073 |   3.84395  |
| 260302_161004_HOOD_HB_cmpind_rerun | HOOD     |      150 |   864.901   |        1.20328  |  0.506667 |         5.76601  |       -5.24312 |        20.2333 | -0.0687966 |   1.07113  |
| 260302_161006_COIN_HB_cmpind_rerun | COIN     |      169 |   478.939   |        1.11076  |  0.526627 |         2.83396  |       -1.58536 |        18.1361 | -0.0588728 |   0.599571 |
| 260302_161014_IBRX_HB_cmpind_rerun | IBRX     |       22 |   346.564   |        1.32347  |  0.545455 |        15.7529   |     -186.616   |        23.8636 | -0.0380995 |   2.96657  |
| 260302_161011_AMAT_HB_cmpind_rerun | AMAT     |       22 |   123.559   |        1.33556  |  0.545455 |         5.61632  |       -3.21928 |        18.8636 | -0.0170641 |   2.54063  |
| 260302_161011_AMD_HB_cmpind_rerun  | AMD      |       21 |    20.6619  |        1.0321   |  0.333333 |         0.983898 |      -13.3318  |        22.8571 | -0.0391269 |  -2.70033  |
| 260302_161011_ASML_HB_cmpind_rerun | ASML     |       18 |    -2.29425 |        0.991837 |  0.444444 |        -0.127458 |       -1.5427  |        14.4444 | -0.012304  |   0.462859 |
| 260302_161016_MNST_HB_cmpind_rerun | MNST     |       19 |   -86.6572  |        0.641088 |  0.368421 |        -4.5609   |      -55.851   |        18.6842 | -0.0216944 |  -5.04364  |
| 260302_161017_WBD_HB_cmpind_rerun  | WBD      |       19 |  -216.801   |        0.283229 |  0.263158 |       -11.4106   |     -244.101   |        31.0526 | -0.0233226 | -10.7763   |
| 260302_161011_AXTI_HB_cmpind_rerun | AXTI     |       20 |  -380.561   |        0.761783 |  0.25     |       -19.0281   |     -194.495   |        16.75   | -0.0664827 |  -1.38862  |
| 260302_161010_ADI_HB_cmpind_rerun  | ADI      |       21 |  -478.884   |        0.252126 |  0.333333 |       -22.804    |      -14.3437  |        16.1905 | -0.0583344 |  -8.0349   |
| 260302_161013_BKR_HB_cmpind_rerun  | BKR      |       21 |  -561.452   |        0.164304 |  0.190476 |       -26.7358   |     -115.347   |        14.2857 | -0.0542894 | -10.5968   |
| 260302_161015_INTC_HB_cmpind_rerun | INTC     |       20 |  -634.079   |        0.411859 |  0.2      |       -31.7039   |     -113.39    |        15      | -0.0714099 |  -5.48762  |
| 260302_161039_LITE_HB_cmpind_rerun | LITE     |      146 |  -714.275   |        0.872083 |  0.472603 |        -4.8923   |      -14.2316  |        23.3219 | -0.2193    |  -0.577725 |
| 260302_161016_MU_HB_cmpind_rerun   | MU       |       21 |  -714.792   |        0.335113 |  0.380952 |       -34.0377   |       -6.55397 |        18.0952 | -0.0803201 |  -5.42102  |
| 260302_161017_WDC_HB_cmpind_rerun  | WDC      |       16 |  -791.458   |        0.290022 |  0.3125   |       -49.4661   |      -15.4363  |        27.1875 | -0.0635261 |  -5.30683  |
| 260302_161016_STX_HB_cmpind_rerun  | STX      |       19 | -1041.33    |        0.25395  |  0.315789 |       -54.8069   |       -8.94679 |        12.1053 | -0.114401  |  -8.46608  |
| 260302_161008_PYPL_HB_cmpind_rerun | PYPL     |      173 | -1974.46    |        0.400597 |  0.381503 |       -11.4131   |      -56.0101  |        20.2601 | -0.212296  |  -5.88335  |
| 260302_161014_SOFI_HB_cmpind_rerun | SOFI     |      176 | -2920.77    |        0.465771 |  0.363636 |       -16.5953   |     -145.421   |        18.9489 | -0.292753  |  -4.87053  |
| 260302_161031_IBRX_HB_cmpind_rerun | IBRX     |      198 | -4925.99    |        0.518461 |  0.313131 |       -24.8788   |    -1226.02    |        19.7222 | -0.567669  |  -3.95038  |

### Aggregate
{
  "trades": 1490,
  "symbols": 19,
  "net_pnl": -8356.033476887656,
  "winrate": 0.4261744966442953,
  "expectancy_usd": -5.608076158985004,
  "expectancy_r": -200.1873839425853,
  "profit_factor": 0.8461914574137486,
  "avg_hold_min": 19.738255033557046,
  "mfe_median": 0.1550000000000007,
  "mae_median": 0.25
}

## C) Distributions
### R-Multiple Quantiles
|      |   r_multiple |
|-----:|-------------:|
| 0.1  |    -747.192  |
| 0.25 |    -193.461  |
| 0.5  |     -25.3505 |
| 0.75 |      66.931  |
| 0.9  |     291.882  |

### Hold Time Quantiles (minutes)
|      |   hold_min |
|-----:|-----------:|
| 0.1  |          0 |
| 0.25 |          5 |
| 0.5  |         15 |
| 0.75 |         30 |
| 0.9  |         50 |

## D) Attribution / Edge Localisation
### Symbol
| symbol   |   trades |   winrate |    net_pnl |   expectancy |      avg_r |       pf |
|:---------|---------:|----------:|-----------:|-------------:|-----------:|---------:|
| AAOI     |      200 |  0.53     | 4342.3     |    21.7115   |   12.2398  | 1.45025  |
| HOOD     |      150 |  0.506667 |  864.901   |     5.76601  |   -5.24312 | 1.20328  |
| COIN     |      169 |  0.526627 |  478.939   |     2.83396  |   -1.58536 | 1.11076  |
| LITE     |      165 |  0.49697  |  196.576   |     1.19137  |  -12.2321  | 1.02964  |
| AMAT     |       22 |  0.545455 |  123.559   |     5.61632  |   -3.21928 | 1.33556  |
| AMD      |       21 |  0.333333 |   20.6619  |     0.983898 |  -13.3318  | 1.0321   |
| ASML     |       18 |  0.444444 |   -2.29425 |    -0.127458 |   -1.5427  | 0.991837 |
| MNST     |       19 |  0.368421 |  -86.6572  |    -4.5609   |  -55.851   | 0.641088 |
| WBD      |       19 |  0.263158 | -216.801   |   -11.4106   | -244.101   | 0.283229 |
| AXTI     |       20 |  0.25     | -380.561   |   -19.0281   | -194.495   | 0.761783 |
| ADI      |       21 |  0.333333 | -478.884   |   -22.804    |  -14.3437  | 0.252126 |
| BKR      |       21 |  0.190476 | -561.452   |   -26.7358   | -115.347   | 0.164304 |
| INTC     |       20 |  0.2      | -634.079   |   -31.7039   | -113.39    | 0.411859 |
| MU       |       21 |  0.380952 | -714.792   |   -34.0377   |   -6.55397 | 0.335113 |
| WDC      |       16 |  0.3125   | -791.458   |   -49.4661   |  -15.4363  | 0.290022 |

### Weekday
| weekday   |   trades |   winrate |   net_pnl |   expectancy |    avg_r |       pf |
|:----------|---------:|----------:|----------:|-------------:|---------:|---------:|
| Wednesday |      309 |  0.436893 |  -460.132 |     -1.4891  | -145.679 | 0.958821 |
| Monday    |      272 |  0.444853 |  -618.34  |     -2.27331 | -248.293 | 0.934174 |
| Friday    |      292 |  0.410959 | -1869.63  |     -6.40284 | -196.138 | 0.829501 |
| Tuesday   |      306 |  0.437908 | -2680.2   |     -8.75882 | -185.503 | 0.758261 |
| Thursday  |      311 |  0.401929 | -2727.73  |     -8.77085 | -230.522 | 0.767008 |

### Session Bucket
| session_bucket   |   trades |   winrate |     net_pnl |   expectancy |     avg_r |       pf |
|:-----------------|---------:|----------:|------------:|-------------:|----------:|---------:|
| 11:00-14:00      |       21 |  0.333333 |     8.20836 |     0.390874 |  190.936  | 1.0288   |
| other            |       12 |  0.333333 |   -55.1055  |    -4.59213  |   20.8336 | 0.655299 |
| 09:30-11:00      |      701 |  0.46077  |  -821.478   |    -1.17187  | -166.341  | 0.975306 |
| 14:00-15:30      |      756 |  0.398148 | -7487.66    |    -9.90431  | -245.945  | 0.63681  |

### Volatility Bucket (ADX proxy)
| adx_bucket   |   trades |   winrate |   net_pnl |   expectancy |      avg_r |       pf |
|:-------------|---------:|----------:|----------:|-------------:|-----------:|---------:|
| 25-30        |      259 |  0.459459 |  1747.73  |      6.748   |  -97.4495  | 1.18701  |
| nan          |       11 |  0.545455 |   344.274 |     31.2977  |    3.44597 | 2.10482  |
| >=30         |      461 |  0.446855 | -2601.6   |     -5.64338 | -226.804   | 0.865354 |
| 20-25        |      276 |  0.398551 | -3321.64  |    -12.0349  | -315.578   | 0.694566 |
| <20          |      483 |  0.401656 | -4524.8   |     -9.36812 | -168.574   | 0.687368 |

### Regime Bucket
| regime_bucket       |   trades |   winrate |   net_pnl |   expectancy |    avg_r |       pf |
|:--------------------|---------:|----------:|----------:|-------------:|---------:|---------:|
| trend               |      720 |  0.451389 |  -853.867 |     -1.18593 | -180.272 | 0.970215 |
| range_or_transition |      770 |  0.402597 | -7502.17  |     -9.74307 | -218.809 | 0.707632 |

## E) Robustness / Drift
### Rolling 1M (head)
| bucket   |   trades |   net_pnl |   winrate |   expectancy |       pf |
|:---------|---------:|----------:|----------:|-------------:|---------:|
| 2025-05  |      110 |   124.401 |  0.536364 |      1.13092 | 1.03403  |
| 2025-06  |      119 |  -705.73  |  0.445378 |     -5.9305  | 0.827187 |
| 2025-07  |      139 |  -844.045 |  0.395683 |     -6.07226 | 0.813876 |
| 2025-08  |      124 | -1482.14  |  0.370968 |    -11.9527  | 0.656548 |
| 2025-09  |      132 | -1500.3   |  0.439394 |    -11.3659  | 0.61708  |
| 2025-10  |      133 | -1586.23  |  0.398496 |    -11.9265  | 0.682239 |
| 2025-11  |       94 | -1424.85  |  0.43617  |    -15.158   | 0.675653 |
| 2025-12  |      120 |  -467.594 |  0.4      |     -3.89662 | 0.876998 |
| 2026-01  |      206 | -1694.87  |  0.38835  |     -8.22754 | 0.816693 |
| 2026-02  |      313 |  1225.32  |  0.453674 |      3.91477 | 1.1076   |

### Temporal Split 70/30
| split         |   trades |   net_pnl |   winrate |   expectancy |       pf |
|:--------------|---------:|----------:|----------:|-------------:|---------:|
| in_sample     |     1043 | -7871.19  |  0.427613 |     -7.54668 | 0.784647 |
| out_of_sample |      447 |  -484.841 |  0.422819 |     -1.08466 | 0.972727 |

### Concentration
{
  "top_10pct_trade_share": 0.3461024846473718,
  "top_symbol_share": 0.22437299171596434
}

## F) Sensitivity / Ablation
- Detected varying parameter keys across runs: lookback_days, requested_end, symbol
- Full join export: `sensitivity_run_vs_params.csv`.

## G) Forensic Sanity Checks
| check                            |   count |
|:---------------------------------|--------:|
| duplicate_template_id_within_run |       0 |
| template_id_reused_across_runs   |      66 |
| entry_after_exit                 |       0 |
| non_positive_prices              |       0 |
| signal_after_entry               |       0 |

## Output Artifacts
- Analysis directory: `artifacts/analysis/20260302_161619_hb_cmpind_rerun_300_40d`
- Core exports: `summary_runs.csv`, `attribution_*.csv`, `rolling_metrics_*.csv`, `sanity_checks.csv`.
- Plots: `equity_curves.png`, `drawdown_by_run.png`, `rolling_expectancy.png`, `attribution_symbol.png`.

## Run Inventory
_See section A above._

## Fix List / Data Issues
- No structural trade-ordering issues detected in analyzed runs.

## Experiment Specs (next 8)
- Hypothesis: Morning window has higher expectancy; change: keep `09:30-11:00` only; gate: +PF with >=150 trades.
- Hypothesis: Afternoon BUY harms edge; change: disable BUY in `14:00-15:30`; gate: net pnl and maxDD improvement.
- Hypothesis: Mother body sweet spot drives edge; change: tighten to `0.72-0.78`; gate: expectancy improvement.
- Hypothesis: ADX mid-high performs better; change: require `adx_14 >= 20`; gate: winrate and PF increase.
- Hypothesis: High ADX + high mother body is noisy; change: cap body at 0.80 when ADX>=30.
- Hypothesis: Stop-loss cluster near session end; change: reduce validity window in afternoon only.
- Hypothesis: Symbol concentration risk; change: cap per-symbol weight in batch selection.
- Hypothesis: Coverage quality bias; change: exclude symbols with recurrent incomplete-day warnings in prefilter.