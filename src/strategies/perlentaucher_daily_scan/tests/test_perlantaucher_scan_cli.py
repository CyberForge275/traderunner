from __future__ import annotations

import builtins
import inspect
import os

import pandas as pd

from strategies.perlentaucher_daily_scan import scan_runner
from strategies.perlentaucher_daily_scan.tools import perlantaucher_scan


def _build_symbol_frame(
    symbol: str,
    dates: pd.DatetimeIndex,
    *,
    base_close: float,
    last_closes: list[float],
    base_volume: float,
    last_volumes: list[float],
) -> pd.DataFrame:
    closes = [base_close] * (len(dates) - len(last_closes)) + list(last_closes)
    volumes = [base_volume] * (len(dates) - len(last_volumes)) + list(last_volumes)
    lows = [c - 0.5 for c in closes]
    opens = [c - 0.1 for c in closes]
    highs = [c + 0.2 for c in closes]
    return pd.DataFrame(
        {
            "symbol": symbol,
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def test_parse_scan_args_accepts_requested_vf_vt_syntax() -> None:
    args = perlantaucher_scan.parse_scan_args(["vf:2026-06-08", "vt:2026-06-16"])

    assert args.valid_from == "2026-06-08"
    assert args.valid_to == "2026-06-16"
    assert args.base_url == perlantaucher_scan.DEFAULT_BASE_URL
    assert args.mode == "match"


def test_parse_scan_args_accepts_prefilter_mode() -> None:
    args = perlantaucher_scan.parse_scan_args(["vf:2026-06-08", "vt:2026-06-16", "mode:prefilter"])

    assert args.mode == "prefilter"


def test_parse_scan_args_accepts_impulse_modes() -> None:
    first_args = perlantaucher_scan.parse_scan_args(["vf:2026-06-08", "vt:2026-06-16", "mode:first_trigger"])
    final_args = perlantaucher_scan.parse_scan_args(["vf:2026-06-08", "vt:2026-06-16", "mode:final_trigger"])

    assert first_args.mode == "first_trigger"
    assert final_args.mode == "final_trigger"


def test_parse_scan_args_accepts_first_trigger_backtest_mode() -> None:
    args = perlantaucher_scan.parse_scan_args(
        ["vf:2026-06-08", "vt:2026-06-16", "mode:first_trigger_backtest"]
    )

    assert args.mode == "first_trigger_backtest"


def test_parse_scan_args_defaults_to_last_five_business_days(monkeypatch) -> None:
    monkeypatch.setattr(
        perlantaucher_scan,
        "default_business_date_range",
        lambda: ("2026-06-10", "2026-06-16"),
    )

    args = perlantaucher_scan.parse_scan_args([])

    assert args.valid_from == "2026-06-10"
    assert args.valid_to == "2026-06-16"


def test_parse_scan_args_uses_spyder_debug_args_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(perlantaucher_scan, "SPYDER_DEBUG_ENABLED", True)
    monkeypatch.setattr(
        perlantaucher_scan,
        "SPYDER_DEBUG_ARGS",
        ["vf:2026-06-12", "vt:2026-06-16", "mode:match"],
    )
    monkeypatch.setattr(perlantaucher_scan.sys, "argv", ["perlantaucher_scan.py"])

    args = perlantaucher_scan.parse_scan_args()

    assert args.valid_from == "2026-06-12"
    assert args.valid_to == "2026-06-16"
    assert args.mode == "match"


def test_main_applies_spyder_debug_environment_before_runner(monkeypatch, capsys) -> None:
    monkeypatch.setattr(perlantaucher_scan, "SPYDER_DEBUG_ENABLED", True)
    monkeypatch.setattr(perlantaucher_scan, "SPYDER_DEBUG_STAGES", "cli_state,summary")
    monkeypatch.setattr(perlantaucher_scan, "SPYDER_DEBUG_SYMBOL", "AXTI")
    monkeypatch.setattr(perlantaucher_scan, "SPYDER_DEBUG_DATE", "2026-04-08")
    monkeypatch.delenv("PT_DEBUG_STAGES", raising=False)
    monkeypatch.delenv("PT_DEBUG_SYMBOL", raising=False)
    monkeypatch.delenv("PT_DEBUG_DATE", raising=False)
    monkeypatch.setattr(builtins, "breakpoint", lambda: None)

    captured: dict[str, str | None] = {}
    run_artifacts = scan_runner.PerlentaucherScanArtifacts(
        summary_df=pd.DataFrame({"as_of_date": ["2026-04-08"], "symbols_csv": [""], "symbol_count": [0]}),
        detail_df=pd.DataFrame(),
        reference_frame_df=pd.DataFrame(),
        raw_df=pd.DataFrame(),
        meta={"status": "ok"},
        request=scan_runner.PerlentaucherScanRequest(
            valid_from="2026-04-08",
            valid_to="2026-04-08",
            base_url=perlantaucher_scan.DEFAULT_BASE_URL,
            mode="prefilter",
            non_empty_only=False,
        ),
        sweet_spot_pairs=[],
    )

    def _stub_run(request):
        del request
        captured["PT_DEBUG_STAGES"] = os.environ.get("PT_DEBUG_STAGES")
        captured["PT_DEBUG_SYMBOL"] = os.environ.get("PT_DEBUG_SYMBOL")
        captured["PT_DEBUG_DATE"] = os.environ.get("PT_DEBUG_DATE")
        return run_artifacts

    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", _stub_run)

    exit_code = perlantaucher_scan.main(["vf:2026-04-08", "vt:2026-04-08", "mode:prefilter"])
    _out = capsys.readouterr().out

    assert exit_code == 0
    assert captured == {
        "PT_DEBUG_STAGES": "cli_state,summary",
        "PT_DEBUG_SYMBOL": "AXTI",
        "PT_DEBUG_DATE": "2026-04-08",
    }


def test_main_clears_spyder_debug_environment_when_profile_disabled(monkeypatch, capsys) -> None:
    monkeypatch.setattr(perlantaucher_scan, "SPYDER_DEBUG_ENABLED", False)
    monkeypatch.setattr(perlantaucher_scan, "SPYDER_DEBUG_RESET_ENV", True)
    monkeypatch.setenv("PT_DEBUG_STAGES", "cli_state")
    monkeypatch.setenv("PT_DEBUG_SYMBOL", "AXTI")
    monkeypatch.setenv("PT_DEBUG_DATE", "2026-04-08")

    captured: dict[str, str | None] = {}
    run_artifacts = scan_runner.PerlentaucherScanArtifacts(
        summary_df=pd.DataFrame({"as_of_date": ["2026-04-08"], "symbols_csv": [""], "symbol_count": [0]}),
        detail_df=pd.DataFrame(),
        reference_frame_df=pd.DataFrame(),
        raw_df=pd.DataFrame(),
        meta={"status": "ok"},
        request=scan_runner.PerlentaucherScanRequest(
            valid_from="2026-04-08",
            valid_to="2026-04-08",
            base_url=perlantaucher_scan.DEFAULT_BASE_URL,
            mode="prefilter",
            non_empty_only=False,
        ),
        sweet_spot_pairs=[],
    )

    def _stub_run(request):
        del request
        captured["PT_DEBUG_STAGES"] = os.environ.get("PT_DEBUG_STAGES")
        captured["PT_DEBUG_SYMBOL"] = os.environ.get("PT_DEBUG_SYMBOL")
        captured["PT_DEBUG_DATE"] = os.environ.get("PT_DEBUG_DATE")
        return run_artifacts

    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", _stub_run)

    exit_code = perlantaucher_scan.main(["vf:2026-04-08", "vt:2026-04-08", "mode:prefilter"])
    _out = capsys.readouterr().out

    assert exit_code == 0
    assert captured == {
        "PT_DEBUG_STAGES": None,
        "PT_DEBUG_SYMBOL": None,
        "PT_DEBUG_DATE": None,
    }


def test_main_delegates_to_runner_and_prints_summary_csv(monkeypatch, capsys) -> None:
    summary_df = pd.DataFrame(
        {
            "as_of_date": ["2026-04-08"],
            "symbol_count": [1],
            "symbols": [["PASS"]],
            "symbols_csv": ["PASS"],
            "closest_miss_count": [0],
            "closest_miss_symbols": [[]],
            "closest_miss_symbols_csv": [""],
            "closest_miss_scores_csv": [""],
        }
    )
    run_artifacts = scan_runner.PerlentaucherScanArtifacts(
        summary_df=summary_df,
        detail_df=pd.DataFrame(),
        reference_frame_df=pd.DataFrame(),
        raw_df=pd.DataFrame({"symbol": ["PASS"]}),
        meta={"status": "ok"},
        request=scan_runner.PerlentaucherScanRequest(
            valid_from="2026-04-07",
            valid_to="2026-04-08",
            base_url=perlantaucher_scan.DEFAULT_BASE_URL,
            mode="match",
            non_empty_only=False,
        ),
        sweet_spot_pairs=[("AXTI", "2025-08-20")],
    )
    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", lambda request: run_artifacts)

    exit_code = perlantaucher_scan.main(["vf:2026-04-07", "vt:2026-04-08"])
    out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert out[0] == "[signal_found]"
    assert out[1] == "as_of_date,symbol"
    assert out[2] == "2026-04-08,PASS"
    assert out[4] == "[closest_miss]"
    assert out[5] == (
        "as_of_date,miss_rank,symbol,match_score,closest_reference_symbol,closest_reference_as_of_date"
    )


def test_main_without_args_uses_default_business_range(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        perlantaucher_scan,
        "default_business_date_range",
        lambda: ("2026-04-07", "2026-04-08"),
    )
    captured: dict[str, object] = {}
    def _stub_run(request):
        captured["request"] = request
        return scan_runner.PerlentaucherScanArtifacts(
            summary_df=pd.DataFrame(
                {
                    "as_of_date": ["2026-04-08"],
                    "symbol_count": [0],
                    "symbols": [[]],
                    "symbols_csv": [""],
                    "closest_miss_count": [0],
                    "closest_miss_symbols": [[]],
                    "closest_miss_symbols_csv": [""],
                    "closest_miss_scores_csv": [""],
                }
            ),
            detail_df=pd.DataFrame(),
            reference_frame_df=pd.DataFrame(),
            raw_df=pd.DataFrame(),
            meta={"status": "ok"},
            request=request,
            sweet_spot_pairs=[("AXTI", "2025-08-20")],
        )
    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", _stub_run)

    exit_code = perlantaucher_scan.main([])
    _out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert captured["request"].valid_from == "2026-04-07"
    assert captured["request"].valid_to == "2026-04-08"


def test_main_prints_csv_match_rows(monkeypatch, capsys) -> None:
    dates = pd.date_range("2025-10-01", periods=140, freq="B", tz="UTC")
    shared_last_closes = [6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5]
    shared_last_volumes = [650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0]

    axti = _build_symbol_frame(
        "AXTI",
        dates,
        base_close=20.0,
        last_closes=[value + 15.0 for value in shared_last_closes],
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )
    passed = _build_symbol_frame(
        "PASS",
        dates,
        base_close=5.0,
        last_closes=shared_last_closes,
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )

    as_of_date = str(dates[-1].date())
    run_artifacts = scan_runner.PerlentaucherScanArtifacts(
        summary_df=pd.DataFrame(
            {
                "as_of_date": [as_of_date],
                "symbol_count": [1],
                "symbols": [["PASS"]],
                "symbols_csv": ["PASS"],
                "closest_miss_count": [0],
                "closest_miss_symbols": [[]],
                "closest_miss_symbols_csv": [""],
                "closest_miss_scores_csv": [""],
            }
        ),
        detail_df=pd.DataFrame(),
        reference_frame_df=pd.DataFrame({"symbol": ["AXTI"], "as_of_date": [as_of_date]}),
        raw_df=pd.concat([axti, passed], ignore_index=True),
        meta={"merged_rows": len(axti) + len(passed)},
        request=scan_runner.PerlentaucherScanRequest(
            valid_from=as_of_date,
            valid_to=as_of_date,
            base_url=perlantaucher_scan.DEFAULT_BASE_URL,
            mode="match",
            non_empty_only=False,
        ),
        sweet_spot_pairs=[("AXTI", as_of_date)],
    )
    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", lambda request: run_artifacts)

    exit_code = perlantaucher_scan.main([f"vf:{as_of_date}", f"vt:{as_of_date}", "mode:match"])
    out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert out[0] == "[signal_found]"
    assert out[1] == "as_of_date,symbol"
    assert out[2] == f"{as_of_date},PASS"
    assert out[4] == "[closest_miss]"
    assert perlantaucher_scan.LAST_MATCH_DETAIL_DF is not None
    assert perlantaucher_scan.LAST_MATCH_DETAIL_DF.empty
    assert perlantaucher_scan.LAST_MATCH_REFERENCE_DF is not None


def test_main_populates_debug_state_container_without_global_statement(monkeypatch, capsys) -> None:
    summary_df = pd.DataFrame(
        {
            "as_of_date": ["2026-04-08"],
            "symbol_count": [1],
            "symbols": [["PASS"]],
            "symbols_csv": ["PASS"],
            "closest_miss_count": [0],
            "closest_miss_symbols": [[]],
            "closest_miss_symbols_csv": [""],
            "closest_miss_scores_csv": [""],
        }
    )
    detail_df = pd.DataFrame({"symbol": ["PASS"]})
    reference_df = pd.DataFrame({"symbol": ["AXTI"]})
    request = scan_runner.PerlentaucherScanRequest(
        valid_from="2026-04-07",
        valid_to="2026-04-08",
        base_url=perlantaucher_scan.DEFAULT_BASE_URL,
        mode="match",
        non_empty_only=False,
    )
    run_artifacts = scan_runner.PerlentaucherScanArtifacts(
        summary_df=summary_df,
        detail_df=detail_df,
        reference_frame_df=reference_df,
        raw_df=pd.DataFrame({"symbol": ["PASS"]}),
        meta={"status": "ok"},
        request=request,
        sweet_spot_pairs=[("AXTI", "2025-08-20")],
    )
    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", lambda _request: run_artifacts)

    exit_code = perlantaucher_scan.main(["vf:2026-04-07", "vt:2026-04-08"])
    _out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert perlantaucher_scan.DEBUG_STATE.args == request
    assert perlantaucher_scan.DEBUG_STATE.meta == {"status": "ok"}
    assert perlantaucher_scan.DEBUG_STATE.scan_df.equals(summary_df.reset_index(drop=True))
    assert perlantaucher_scan.DEBUG_STATE.match_detail_df.equals(detail_df.reset_index(drop=True))
    assert perlantaucher_scan.DEBUG_STATE.match_reference_df.equals(reference_df.reset_index(drop=True))
    assert "global LAST_ARGS" not in inspect.getsource(perlantaucher_scan.main)


def test_main_prints_entry_level_columns_when_present(monkeypatch, capsys) -> None:
    summary_df = pd.DataFrame(
        {
            "as_of_date": ["2026-04-08"],
            "symbol_count": [2],
            "symbols": [["ALFA", "BETA"]],
            "symbols_csv": ["ALFA,BETA"],
            "entry_dates_csv": ["2026-04-09,2026-04-09"],
            "entry_prices_csv": ["4.10,7.25"],
        }
    )
    run_artifacts = scan_runner.PerlentaucherScanArtifacts(
        summary_df=summary_df,
        detail_df=pd.DataFrame(),
        reference_frame_df=pd.DataFrame(),
        raw_df=pd.DataFrame({"symbol": ["ALFA", "BETA"]}),
        meta={"status": "ok"},
        request=scan_runner.PerlentaucherScanRequest(
            valid_from="2026-04-08",
            valid_to="2026-04-08",
            base_url=perlantaucher_scan.DEFAULT_BASE_URL,
            mode="first_trigger",
            non_empty_only=False,
        ),
        sweet_spot_pairs=[],
    )
    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", lambda request: run_artifacts)

    exit_code = perlantaucher_scan.main(["vf:2026-04-08", "vt:2026-04-08", "mode:first_trigger"])
    out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert out[0] == "[signal_found]"
    assert out[1] == "as_of_date,symbol,entry_date,entry_price"
    assert out[2] == "2026-04-08,ALFA,2026-04-09,4.10"
    assert out[3] == "2026-04-08,BETA,2026-04-09,7.25"


def test_main_prints_clean_found_and_near_match_sections(monkeypatch, capsys) -> None:
    summary_df = pd.DataFrame(
        {
            "as_of_date": ["2026-04-08"],
            "symbol_count": [1],
            "symbols": [["PASS"]],
            "symbols_csv": ["PASS"],
            "closest_miss_count": [2],
            "closest_miss_symbols": [["MISSA", "MISSB"]],
            "closest_miss_symbols_csv": ["MISSA,MISSB"],
            "closest_miss_scores_csv": ["1.250000,2.500000"],
        }
    )
    detail_df = pd.DataFrame(
        {
            "as_of_date": ["2026-04-08", "2026-04-08"],
            "miss_rank": [1, 2],
            "symbol": ["MISSA", "MISSB"],
            "match_score": [1.25, 2.5],
            "closest_reference_symbol": ["AXTI", "AXTI"],
            "closest_reference_as_of_date": ["2025-08-20", "2025-08-20"],
        }
    )
    run_artifacts = scan_runner.PerlentaucherScanArtifacts(
        summary_df=summary_df,
        detail_df=detail_df,
        reference_frame_df=pd.DataFrame(),
        raw_df=pd.DataFrame({"symbol": ["PASS", "MISSA", "MISSB"]}),
        meta={"status": "ok"},
        request=scan_runner.PerlentaucherScanRequest(
            valid_from="2026-04-08",
            valid_to="2026-04-08",
            base_url=perlantaucher_scan.DEFAULT_BASE_URL,
            mode="match",
            non_empty_only=False,
        ),
        sweet_spot_pairs=[("AXTI", "2025-08-20")],
    )
    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", lambda request: run_artifacts)

    exit_code = perlantaucher_scan.main(["vf:2026-04-08", "vt:2026-04-08", "mode:match"])
    out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert out[0] == "[signal_found]"
    assert out[1] == "as_of_date,symbol"
    assert out[2] == "2026-04-08,PASS"
    assert out[4] == "[closest_miss]"
    assert out[5] == (
        "as_of_date,miss_rank,symbol,match_score,closest_reference_symbol,closest_reference_as_of_date"
    )
    assert out[6] == "2026-04-08,1,MISSA,1.250000,AXTI,2025-08-20"
    assert out[7] == "2026-04-08,2,MISSB,2.500000,AXTI,2025-08-20"


def test_main_prints_backtest_summary_csv_when_present(monkeypatch, capsys) -> None:
    summary_df = pd.DataFrame(
        {
            "as_of_date": ["2026-04-08"],
            "symbol_count": [1],
            "symbols": [["ALFA"]],
            "symbols_csv": ["ALFA"],
            "entry_dates_csv": ["2026-04-09"],
            "entry_prices_csv": ["4.10"],
        }
    )
    run_artifacts = scan_runner.PerlentaucherScanArtifacts(
        summary_df=summary_df,
        detail_df=pd.DataFrame(),
        reference_frame_df=pd.DataFrame(),
        raw_df=pd.DataFrame({"symbol": ["ALFA"]}),
        meta={
            "status": "ok",
            "backtest_summary": {
                "initial_capital": 15000.0,
                "end_equity": 16000.0,
                "profit": 1000.0,
            },
        },
        request=scan_runner.PerlentaucherScanRequest(
            valid_from="2026-04-08",
            valid_to="2026-04-08",
            base_url=perlantaucher_scan.DEFAULT_BASE_URL,
            mode="first_trigger_backtest",
            non_empty_only=False,
        ),
        sweet_spot_pairs=[],
    )
    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", lambda request: run_artifacts)

    exit_code = perlantaucher_scan.main(
        ["vf:2026-04-08", "vt:2026-04-08", "mode:first_trigger_backtest"]
    )
    out = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert "metric,value" in out
    assert "initial_capital,15000.0" in out
    assert "end_equity,16000.0" in out
