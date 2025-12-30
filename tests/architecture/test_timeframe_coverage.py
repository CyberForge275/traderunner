# tests/architecture/test_timeframe_coverage.py

from pathlib import Path
import importlib
import re


def _get_timeframe_button_ids_from_layout() -> set[str]:
    """Extract all timeframe button IDs (tf-*) from the Charts layout."""
    layout_path = Path("trading_dashboard/layouts/charts.py")
    text = layout_path.read_text(encoding="utf-8")

    # Matches id="tf-m1" or id='tf-m1' (specifically tf-*, not just any 't*')
    ids = set(re.findall(r'id=["\']((tf-[^"\']+))["\']', text))
    # findall with groups returns tuples, extract the first group
    return {match[0] for match in ids if match[0].startswith('tf-')}


def _get_timeframe_ids_from_mapping() -> set[str]:
    """
    Get the set of timeframe button IDs from the callback mapping.

    Supports either TIMEFRAME_MAP or timeframe_map in
    trading_dashboard.callbacks.chart_callbacks.
    """
    try:
        cb = importlib.import_module(
            "trading_dashboard.callbacks.chart_callbacks"
        )
    except ImportError as e:
        raise AssertionError(
            "Cannot import trading_dashboard.callbacks.chart_callbacks"
        ) from e

    mapping = None
    if hasattr(cb, "TIMEFRAME_MAP"):
        mapping = getattr(cb, "TIMEFRAME_MAP")
    elif hasattr(cb, "timeframe_map"):
        mapping = getattr(cb, "timeframe_map")

    if mapping is None:
        raise AssertionError(
            "chart_callbacks must define TIMEFRAME_MAP or timeframe_map "
            "for timeframe button mapping."
        )

    if not isinstance(mapping, dict):
        raise AssertionError(
            "Timeframe mapping must be a dict of button_id -> timeframe_code."
        )

    return set(mapping.keys())


def test_all_timeframe_buttons_have_mapping():
    """Every tf-* button in the Charts layout must be covered by the mapping."""
    button_ids = _get_timeframe_button_ids_from_layout()
    mapping_ids = _get_timeframe_ids_from_mapping()

    missing = sorted(button_ids - mapping_ids)
    assert not missing, (
        "Timeframe buttons without mapping in chart_callbacks: "
        f"{missing}"
    )
