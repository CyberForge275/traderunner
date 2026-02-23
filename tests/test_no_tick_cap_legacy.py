from pathlib import Path


def test_no_tick_cap_legacy_string_in_src():
    src_root = Path(__file__).resolve().parents[1] / "src"
    hits = []
    for path in src_root.rglob("*.py"):
        text = path.read_text()
        if "stop_distance_cap_ticks" in text:
            hits.append(str(path))
    assert hits == [], f"legacy stop_distance_cap_ticks references found: {hits}"


def test_inside_bar_session_logic_has_no_tick_cap_formula():
    files = [
        Path("src/strategies/inside_bar/session_logic.py"),
        Path("src/strategies/confirmed_breakout/session_logic.py"),
    ]
    for path in files:
        text = path.read_text()
        assert "tick_size" not in text
        assert "cap_ticks" not in text
        assert "stop_distance_cap_ticks" not in text
