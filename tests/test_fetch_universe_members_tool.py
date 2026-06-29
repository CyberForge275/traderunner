from __future__ import annotations

from tools.fetch_universe_members import (
    UniverseMembersRangeRequest,
    UniverseMembersRequest,
    dataframe_from_response,
)


def test_universe_members_request_to_json_normalizes_values() -> None:
    req = UniverseMembersRequest(
        universe=" ndx ",
        as_of_date="2026-03-25",
        survivorship_mode="CURRENT_MEMBERS",
    )

    assert req.to_json() == {
        "universe": "NDX",
        "as_of_date": "2026-03-25",
        "survivorship_mode": "current_members",
    }


def test_universe_members_range_request_to_json_normalizes_values() -> None:
    req = UniverseMembersRangeRequest(
        universe=" sp500 ",
        valid_from="2025-01-01",
        valid_to="2026-03-25",
        survivorship_mode="CURRENT_MEMBERS",
    )

    assert req.to_json() == {
        "universe": "SP500",
        "valid_from": "2025-01-01",
        "valid_to": "2026-03-25",
        "survivorship_mode": "current_members",
    }


def test_dataframe_from_response_sorts_symbols_deterministically() -> None:
    body = {
        "status": "ok",
        "data": [
            {"symbol": "msft", "valid_from": "2026-03-25", "valid_to": "2026-03-25", "source": "current_members"},
            {"symbol": "AAPL", "valid_from": "2026-03-25", "valid_to": "2026-03-25", "source": "current_members"},
        ],
    }

    df = dataframe_from_response(body)

    assert df["symbol"].tolist() == ["AAPL", "MSFT"]
