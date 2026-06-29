"""CLI to list Perlentaucher prefilter candidates for a date range.

Runs directly from Spyder without requiring external PYTHONPATH setup.
If no date arguments are provided, the scan defaults to the last 5 business
days ending on today's market date in America/New_York.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from strategies.perlentaucher_daily_scan.scan_runner import (
    DEFAULT_BASE_URL,
    PerlentaucherScanRequest,
    run_perlentaucher_scan,
)
from strategies.perlentaucher_daily_scan.cli_output import render_scan_cli_output
from strategies.perlentaucher_daily_scan.debug_hooks import debug_stage_enabled


DEFAULT_SESSION_TIMEZONE = "America/New_York"
DEFAULT_BUSINESS_DAYS = 5

# Spyder debug section:
# - set SPYDER_DEBUG_ENABLED = True
# - adjust SPYDER_DEBUG_ARGS / STAGES / SYMBOL / DATE
# - then run the file in Spyder without passing extra CLI args
SPYDER_DEBUG_ENABLED = True
SPYDER_DEBUG_RESET_ENV = True
SPYDER_DEBUG_ARGS: list[str] = ["vf:2026-06-24", "vt:2026-06-26", "mode:match"]
SPYDER_DEBUG_STAGES = "request_window,fetch_request,fetch_data,coverage,prefilter,slope,reference,match,summary,cli_state"
SPYDER_DEBUG_SYMBOL = "AXTI"
SPYDER_DEBUG_DATE = "2026-06-26"


@dataclass
class ScanCliDebugState:
    args: PerlentaucherScanRequest | None = None
    meta: dict | None = None
    raw_df: pd.DataFrame | None = None
    scan_df: pd.DataFrame | None = None
    match_detail_df: pd.DataFrame | None = None
    match_reference_df: pd.DataFrame | None = None


DEBUG_STATE = ScanCliDebugState()
LAST_ARGS: PerlentaucherScanRequest | None = None
LAST_META: dict | None = None
LAST_RAW_DF: pd.DataFrame | None = None
LAST_SCAN_DF: pd.DataFrame | None = None
LAST_MATCH_DETAIL_DF: pd.DataFrame | None = None
LAST_MATCH_REFERENCE_DF: pd.DataFrame | None = None


def _store_debug_state(
    *,
    args: PerlentaucherScanRequest,
    meta: dict,
    raw_df: pd.DataFrame,
    scan_df: pd.DataFrame,
    match_detail_df: pd.DataFrame | None,
    match_reference_df: pd.DataFrame | None,
) -> None:
    DEBUG_STATE.args = args
    DEBUG_STATE.meta = dict(meta)
    DEBUG_STATE.raw_df = raw_df
    DEBUG_STATE.scan_df = scan_df.copy().reset_index(drop=True)
    DEBUG_STATE.match_detail_df = None if match_detail_df is None else match_detail_df.copy().reset_index(drop=True)
    DEBUG_STATE.match_reference_df = (
        None if match_reference_df is None else match_reference_df.copy().reset_index(drop=True)
    )

    module_state = globals()
    module_state["LAST_ARGS"] = DEBUG_STATE.args
    module_state["LAST_META"] = DEBUG_STATE.meta
    module_state["LAST_RAW_DF"] = DEBUG_STATE.raw_df
    module_state["LAST_SCAN_DF"] = DEBUG_STATE.scan_df
    module_state["LAST_MATCH_DETAIL_DF"] = DEBUG_STATE.match_detail_df
    module_state["LAST_MATCH_REFERENCE_DF"] = DEBUG_STATE.match_reference_df


def _rewrite_prefixed_args(argv: list[str]) -> list[str]:
    rewritten: list[str] = []
    for token in argv:
        if token.startswith("vf:"):
            rewritten.extend(["--valid-from", token[3:]])
        elif token.startswith("vt:"):
            rewritten.extend(["--valid-to", token[3:]])
        elif token.startswith("base:"):
            rewritten.extend(["--base-url", token[5:]])
        elif token.startswith("mode:"):
            rewritten.extend(["--mode", token[5:]])
        else:
            rewritten.append(token)
    return rewritten


def _validated_iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{field} must be YYYY-MM-DD") from exc


def _set_or_clear_env(name: str, value: str) -> None:
    text = str(value).strip()
    if text:
        os.environ[name] = text
    else:
        os.environ.pop(name, None)


def apply_spyder_debug_profile() -> None:
    if not SPYDER_DEBUG_ENABLED:
        if SPYDER_DEBUG_RESET_ENV:
            _set_or_clear_env("PT_DEBUG_STAGES", "")
            _set_or_clear_env("PT_DEBUG_SYMBOL", "")
            _set_or_clear_env("PT_DEBUG_DATE", "")
        return
    _set_or_clear_env("PT_DEBUG_STAGES", SPYDER_DEBUG_STAGES)
    _set_or_clear_env("PT_DEBUG_SYMBOL", SPYDER_DEBUG_SYMBOL)
    _set_or_clear_env("PT_DEBUG_DATE", SPYDER_DEBUG_DATE)


def resolve_cli_argv(argv: list[str] | None = None) -> list[str]:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args:
        return raw_args
    if SPYDER_DEBUG_ENABLED and SPYDER_DEBUG_ARGS:
        return list(SPYDER_DEBUG_ARGS)
    return raw_args


def default_business_date_range() -> tuple[str, str]:
    today_market = pd.Timestamp.now(tz=DEFAULT_SESSION_TIMEZONE).date()
    business_days = pd.bdate_range(end=pd.Timestamp(today_market), periods=DEFAULT_BUSINESS_DAYS)
    return business_days[0].date().isoformat(), business_days[-1].date().isoformat()


def parse_scan_args(argv: list[str] | None = None) -> PerlentaucherScanRequest:
    parser = argparse.ArgumentParser(
        description="List Perlentaucher candidate symbols per trading day.",
    )
    parser.add_argument("--valid-from", dest="valid_from")
    parser.add_argument("--valid-to", dest="valid_to")
    parser.add_argument("--base-url", dest="base_url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--mode",
        choices=("prefilter", "match", "first_trigger", "final_trigger", "first_trigger_backtest"),
        default="match",
        help=(
            "prefilter prints stage-1 candidates, match prints SweetSpot matches, "
            "first_trigger/final_trigger print the impulse research trigger sets, "
            "first_trigger_backtest adds the deterministic 15k research portfolio summary."
        ),
    )
    parser.add_argument(
        "--non-empty-only",
        action="store_true",
        help="Only print days with at least one candidate symbol.",
    )

    raw_args = resolve_cli_argv(argv)
    parsed = parser.parse_args(_rewrite_prefixed_args(raw_args))

    if not parsed.valid_from and not parsed.valid_to:
        valid_from, valid_to = default_business_date_range()
    elif parsed.valid_from and parsed.valid_to:
        valid_from = _validated_iso_date(str(parsed.valid_from), field="valid_from")
        valid_to = _validated_iso_date(str(parsed.valid_to), field="valid_to")
    else:
        parser.error("either provide both valid-from and valid-to or neither")

    if valid_from > valid_to:
        parser.error("valid-from must be <= valid-to")

    return PerlentaucherScanRequest(
        valid_from=valid_from,
        valid_to=valid_to,
        base_url=str(parsed.base_url).strip() or DEFAULT_BASE_URL,
        mode=str(parsed.mode),
        non_empty_only=bool(parsed.non_empty_only),
    )


def emit_scan_csv(scan_df: pd.DataFrame, detail_df: pd.DataFrame | None = None) -> None:
    print(render_scan_cli_output(scan_df, detail_df if detail_df is not None else pd.DataFrame()), end="")


def emit_backtest_summary(meta: dict) -> None:
    summary = meta.get("backtest_summary")
    if not isinstance(summary, dict) or not summary:
        return
    out = pd.DataFrame(
        {
            "metric": list(summary.keys()),
            "value": list(summary.values()),
        }
    )
    print()
    print(out.to_csv(index=False), end="")


def main(argv: list[str] | None = None) -> int:
    apply_spyder_debug_profile()
    args = parse_scan_args(argv)
    run_artifacts = run_perlentaucher_scan(args)
    scan_df = run_artifacts.summary_df
    match_detail_df = run_artifacts.detail_df
    match_reference_df = run_artifacts.reference_frame_df
    raw_df = run_artifacts.raw_df
    meta = run_artifacts.meta

    _store_debug_state(
        args=args,
        meta=meta,
        raw_df=raw_df,
        scan_df=scan_df,
        match_detail_df=match_detail_df,
        match_reference_df=match_reference_df,
    )
    if debug_stage_enabled("cli_state", as_of_date=args.valid_to):
        breakpoint()

    emit_scan_csv(scan_df, match_detail_df)
    emit_backtest_summary(meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
