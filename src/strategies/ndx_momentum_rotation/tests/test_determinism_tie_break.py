from __future__ import annotations

import pandas as pd

from strategies.ndx_momentum_rotation.ranking import apply_deterministic_tie_break


def test_tie_break_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["MSFT", "AAPL", "NVDA"],
            "score": [1.0, 1.0, 2.0],
        }
    )
    out = apply_deterministic_tie_break(frame)
    assert out["symbol"].tolist() == ["NVDA", "AAPL", "MSFT"]
