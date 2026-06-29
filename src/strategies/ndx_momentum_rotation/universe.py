"""Universe consumer helpers for NDX100 constituents.

This module intentionally does not own constituent logic.
It consumes an externally supplied member set and validates which symbols are
actually usable on a given date against the daily bars source.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from axiom_bt.daily import DailyStore
from axiom_bt.pipeline.marketdata_stream_client import (
    MarketdataStreamClient,
    UniverseMembersRequest,
)


@dataclass(frozen=True)
class UniverseSnapshot:
    members: list[str]
    source: str
    pit_available: bool


class UniverseProviderNotImplementedError(NotImplementedError):
    """Raised when PIT universe lookup is not implemented in skeleton."""




def resolve_valid_symbols_for_date(
    *,
    as_of_date: str,
    members: list[str],
    daily_bars_path: Path,
    tz: str = "America/New_York",
) -> list[str]:
    """Resolve symbols that are both in the member set and present on the date."""

    if not members:
        return []

    store = DailyStore(default_tz=tz)
    df = store.load_universe(universe_path=daily_bars_path, tz=tz)
    as_of_ts = pd.Timestamp(as_of_date)
    if as_of_ts.tzinfo is None:
        as_of_ts = as_of_ts.tz_localize(tz)
    else:
        as_of_ts = as_of_ts.tz_convert(tz)

    day_rows = df[df["timestamp"] == as_of_ts].copy()
    if day_rows.empty:
        return []

    available = set(day_rows["symbol"].astype(str).str.upper().tolist())
    wanted = {symbol.strip().upper() for symbol in members if str(symbol).strip()}
    return sorted(available & wanted)


def load_universe_snapshot(
    *,
    as_of_date: str,
    survivorship_mode: str,
    daily_bars_path: Path | None = None,
    tz: str = "America/New_York",
    universe: str = "NDX",
    base_url: str | None = None,
) -> UniverseSnapshot:
    """Load NDX100 members for the date from external universe source.

    PIT membership remains explicitly unsupported until a real PIT source exists.
    """

    if survivorship_mode == "pit_members":
        raise UniverseProviderNotImplementedError(
            "PIT universe provider is not implemented for ndx_momentum_rotation skeleton"
        )

    if daily_bars_path is None:
        raise ValueError(
            "daily_bars_path is required for survivorship_mode='current_members'"
        )

    client = MarketdataStreamClient(base_url=base_url, enabled=True)
    body = client.fetch_universe_members(
        UniverseMembersRequest(
            universe=universe,
            as_of_date=pd.Timestamp(as_of_date).date(),
            survivorship_mode=survivorship_mode,
        )
    )
    members_df = pd.DataFrame(body.get("data", []))
    members = []
    if "symbol" in members_df.columns:
        members = (
            members_df["symbol"].astype(str).str.strip().str.upper().replace("", pd.NA).dropna().tolist()
        )

    valid_members = resolve_valid_symbols_for_date(
        as_of_date=as_of_date,
        members=members,
        daily_bars_path=daily_bars_path,
        tz=tz,
    )
    return UniverseSnapshot(
        members=valid_members,
        source=f"marketdata_stream:{str(universe).strip().upper()}",
        pit_available=False,
    )
