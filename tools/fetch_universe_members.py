#!/usr/bin/env python3
"""Fetch universe membership snapshots from marketdata-stream.

This is a repo-level research/operator helper.
Use it from Spyder or CLI to inspect members for a date or range.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib import error, request

import pandas as pd
from IPython.display import display

DEFAULT_BASE_URL = os.getenv("MARKETDATA_STREAM_URL", "http://127.0.0.1:8090")
DEFAULT_SURVIVORSHIP_MODE = "current_members"
DEFAULT_UNIVERSE = "NDX"
DEFAULT_AS_OF_DATE = "2026-03-25"
DEFAULT_VALID_FROM = "2025-01-01"
DEFAULT_VALID_TO = "2026-03-25"

RESPONSE_JSON: dict[str, Any] | None = None
MEMBERS_DF: pd.DataFrame | None = None
MEMBERS: list[str] | None = None


@dataclass(frozen=True)
class UniverseMembersRequest:
    universe: str
    as_of_date: str
    survivorship_mode: str = DEFAULT_SURVIVORSHIP_MODE

    def to_json(self) -> dict[str, str]:
        return {
            "universe": self.universe.strip().upper(),
            "as_of_date": self.as_of_date,
            "survivorship_mode": self.survivorship_mode.strip().lower(),
        }


@dataclass(frozen=True)
class UniverseMembersRangeRequest:
    universe: str
    valid_from: str
    valid_to: str
    survivorship_mode: str = DEFAULT_SURVIVORSHIP_MODE

    def to_json(self) -> dict[str, str]:
        return {
            "universe": self.universe.strip().upper(),
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "survivorship_mode": self.survivorship_mode.strip().lower(),
        }


def _post_json(*, url: str, payload: dict[str, Any], timeout_sec: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"cannot reach {url}: {exc.reason}") from exc


def fetch_universe_members(
    *,
    base_url: str,
    payload: UniverseMembersRequest,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    return _post_json(
        url=f"{base_url.rstrip('/')}/universe/members",
        payload=payload.to_json(),
        timeout_sec=timeout_sec,
    )


def fetch_universe_members_range(
    *,
    base_url: str,
    payload: UniverseMembersRangeRequest,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    return _post_json(
        url=f"{base_url.rstrip('/')}/universe/members/range",
        payload=payload.to_json(),
        timeout_sec=timeout_sec,
    )


def dataframe_from_response(body: dict[str, Any]) -> pd.DataFrame:
    data = body.get("data", [])
    df = pd.DataFrame(data)
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper()
        df = df.sort_values([c for c in ["symbol", "valid_from", "valid_to"] if c in df.columns]).reset_index(drop=True)
    return df


def run_from_spyder(
    *,
    base_url: str = DEFAULT_BASE_URL,
    universe: str = DEFAULT_UNIVERSE,
    as_of_date: str = DEFAULT_AS_OF_DATE,
    survivorship_mode: str = DEFAULT_SURVIVORSHIP_MODE,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    global RESPONSE_JSON, MEMBERS_DF, MEMBERS
    payload = UniverseMembersRequest(
        universe=universe,
        as_of_date=as_of_date,
        survivorship_mode=survivorship_mode,
    )
    body = fetch_universe_members(base_url=base_url, payload=payload, timeout_sec=timeout_sec)
    df = dataframe_from_response(body)
    RESPONSE_JSON = body
    MEMBERS_DF = df
    MEMBERS = df["symbol"].tolist() if "symbol" in df.columns else []

    print(json.dumps(body, indent=2, sort_keys=True))
    print(f"\nrows={len(df)} symbols={len(MEMBERS)}")
    if not df.empty:
        print("\n--- MEMBERS (head 20) ---")
        print(df.head(20).to_string(index=False))
    display(df)
    return body


def run_range_from_spyder(
    *,
    base_url: str = DEFAULT_BASE_URL,
    universe: str = DEFAULT_UNIVERSE,
    valid_from: str = DEFAULT_VALID_FROM,
    valid_to: str = DEFAULT_VALID_TO,
    survivorship_mode: str = DEFAULT_SURVIVORSHIP_MODE,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    global RESPONSE_JSON, MEMBERS_DF, MEMBERS
    payload = UniverseMembersRangeRequest(
        universe=universe,
        valid_from=valid_from,
        valid_to=valid_to,
        survivorship_mode=survivorship_mode,
    )
    body = fetch_universe_members_range(base_url=base_url, payload=payload, timeout_sec=timeout_sec)
    df = dataframe_from_response(body)
    RESPONSE_JSON = body
    MEMBERS_DF = df
    MEMBERS = sorted(df["symbol"].astype(str).unique().tolist()) if "symbol" in df.columns else []

    print(json.dumps(body, indent=2, sort_keys=True))
    print(f"\nrows={len(df)} unique_symbols={len(MEMBERS)}")
    if not df.empty:
        print("\n--- MEMBERS RANGE (head 20) ---")
        print(df.head(20).to_string(index=False))
    display(df)
    return body


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch universe membership from marketdata-stream")
    sub = p.add_subparsers(dest="mode", required=False)

    p_single = sub.add_parser("single", help="Fetch members for a single date")
    p_single.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p_single.add_argument("--universe", default=DEFAULT_UNIVERSE)
    p_single.add_argument("--as-of-date", default=DEFAULT_AS_OF_DATE)
    p_single.add_argument("--survivorship-mode", default=DEFAULT_SURVIVORSHIP_MODE)
    p_single.add_argument("--timeout-sec", type=int, default=180)

    p_range = sub.add_parser("range", help="Fetch members for a date range")
    p_range.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p_range.add_argument("--universe", default=DEFAULT_UNIVERSE)
    p_range.add_argument("--valid-from", default=DEFAULT_VALID_FROM)
    p_range.add_argument("--valid-to", default=DEFAULT_VALID_TO)
    p_range.add_argument("--survivorship-mode", default=DEFAULT_SURVIVORSHIP_MODE)
    p_range.add_argument("--timeout-sec", type=int, default=180)

    return p.parse_args()


def main() -> int:
    args = _parse_args()
    mode = args.mode or "single"
    if mode == "range":
        run_range_from_spyder(
            base_url=args.base_url,
            universe=args.universe,
            valid_from=args.valid_from,
            valid_to=args.valid_to,
            survivorship_mode=args.survivorship_mode,
            timeout_sec=max(1, int(args.timeout_sec)),
        )
        return 0

    run_from_spyder(
        base_url=args.base_url,
        universe=args.universe,
        as_of_date=args.as_of_date,
        survivorship_mode=args.survivorship_mode,
        timeout_sec=max(1, int(args.timeout_sec)),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
