from __future__ import annotations

import builtins

import pandas as pd

from strategies.perlentaucher_daily_scan import debug_hooks
from strategies.perlentaucher_daily_scan import prefilter
from strategies.perlentaucher_daily_scan import scan_runner
from strategies.perlentaucher_daily_scan.tools import perlantaucher_scan


EXPECTED_DEBUG_STAGES = {
    "request_window",
    "fetch_request",
    "fetch_data",
    "coverage",
    "normalize",
    "prefilter",
    "candidate_select",
    "sweet_spot_config",
    "sweet_spot_cache",
    "slope",
    "candidate_feature_filter",
    "reference",
    "match",
    "summary",
    "cli_state",
}


def test_debug_stage_registry_lists_all_spyder_breakpoints() -> None:
    assert EXPECTED_DEBUG_STAGES.issubset(debug_hooks.SUPPORTED_DEBUG_STAGES)


def test_debug_stage_enabled_respects_stage_symbol_and_date_filters(monkeypatch) -> None:
    monkeypatch.setenv("PT_DEBUG_STAGES", "prefilter,slope,coverage")
    monkeypatch.setenv("PT_DEBUG_SYMBOL", "AXTI")
    monkeypatch.setenv("PT_DEBUG_DATE", "2026-06-17")

    assert debug_hooks.debug_stage_enabled("prefilter", symbol="AXTI", as_of_date="2026-06-17")
    assert not debug_hooks.debug_stage_enabled("prefilter", symbol="ABCL", as_of_date="2026-06-17")
    assert not debug_hooks.debug_stage_enabled("prefilter", symbol="AXTI", as_of_date="2026-06-18")
    assert not debug_hooks.debug_stage_enabled("match", symbol="AXTI", as_of_date="2026-06-17")
    assert debug_hooks.debug_stage_enabled("coverage", as_of_date="2026-06-17")


def test_resolve_request_window_triggers_programmatic_breakpoint(monkeypatch) -> None:
    hits: list[str] = []

    monkeypatch.setenv("PT_DEBUG_STAGES", "request_window")
    monkeypatch.setattr(builtins, "breakpoint", lambda: hits.append("request_window"))

    valid_from, valid_to = scan_runner.resolve_request_window(
        valid_from="2026-06-11",
        valid_to="2026-06-17",
        mode="match",
        sweet_spot_pairs=[("AXTI", "2025-08-20")],
    )

    assert valid_from == "2025-02-25"
    assert valid_to == "2026-06-17"
    assert hits == ["request_window"]


def test_prefilter_stage_triggers_programmatic_breakpoint_for_matching_symbol(monkeypatch) -> None:
    hits: list[str] = []
    dates = pd.date_range("2026-01-01", periods=70, freq="B", tz="America/New_York")
    raw = pd.DataFrame(
        {
            "symbol": ["PASS"] * len(dates),
            "timestamp": dates.tz_convert("UTC"),
            "low": [4.5] * (len(dates) - 7) + [5.5, 5.7, 6.0, 6.5, 7.0, 8.0, 9.0],
            "close": [5.0] * (len(dates) - 7) + [6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5],
            "volume": [200_000.0] * (len(dates) - 7) + [650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0],
        }
    )

    monkeypatch.setenv("PT_DEBUG_STAGES", "prefilter")
    monkeypatch.setenv("PT_DEBUG_SYMBOL", "PASS")
    monkeypatch.setenv("PT_DEBUG_DATE", "2026-04-08")
    monkeypatch.setattr(builtins, "breakpoint", lambda: hits.append("prefilter"))

    metrics = prefilter.build_volume_prefilter_metrics(raw, as_of_date="2026-04-08")

    assert metrics.iloc[0]["symbol"] == "PASS"
    assert hits == ["prefilter"]


def test_cli_state_stage_triggers_programmatic_breakpoint(monkeypatch, capsys) -> None:
    hits: list[str] = []
    summary_df = pd.DataFrame({"as_of_date": ["2026-04-08"], "symbols_csv": [""], "symbol_count": [0]})

    run_artifacts = scan_runner.PerlentaucherScanArtifacts(
        summary_df=summary_df,
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

    monkeypatch.setattr(perlantaucher_scan, "SPYDER_DEBUG_ENABLED", True)
    monkeypatch.setattr(perlantaucher_scan, "SPYDER_DEBUG_STAGES", "cli_state")
    monkeypatch.setattr(builtins, "breakpoint", lambda: hits.append("cli_state"))
    monkeypatch.setattr(perlantaucher_scan, "run_perlentaucher_scan", lambda _request: run_artifacts)

    exit_code = perlantaucher_scan.main(["vf:2026-04-08", "vt:2026-04-08", "mode:prefilter"])
    _out = capsys.readouterr().out

    assert exit_code == 0
    assert hits == ["cli_state"]
