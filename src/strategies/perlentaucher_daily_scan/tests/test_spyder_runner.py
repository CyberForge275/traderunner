from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.tools.run_sweet_spot_match_spyder import select_symbol_rows


def test_select_symbol_rows_filters_case_insensitively() -> None:
    df = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "AAPL"],
            "candidate_rank": [1.0, None, 2.0],
        }
    )

    out = select_symbol_rows(df, "aapl")

    assert list(out["symbol"]) == ["AAPL", "AAPL"]
