from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Monthly boundary logic is not implemented in skeleton")
def test_calendar_monthly_boundaries_todo() -> None:
    assert False
