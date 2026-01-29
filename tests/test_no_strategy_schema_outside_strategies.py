import pathlib
import re


def test_no_strategy_schema_outside_strategies():
    root = pathlib.Path("src/axiom_bt")
    patterns = [r"ib__", r"inside_bar", r"mother_", r"SIGNAL_COLUMNS", r"INDICATOR_COLUMNS"]
    offenders = []
    for path in root.rglob("*.py"):
        # allow legacy runner/adapters and tests; guard pipeline/contracts only
        if "strategies" in path.parts:
            continue
        if "strategy_adapters" in str(path) or "trade_templates" in str(path):
            continue
        if "contracts" in path.parts or "pipeline" in path.parts:
            text = path.read_text(errors="ignore")
            for pat in patterns:
                if re.search(pat, text):
                    if "signal_schema.py" in str(path):
                        continue
                    offenders.append(str(path))
                    break
    assert not offenders, f"Found strategy schema tokens outside strategies/: {offenders}"
