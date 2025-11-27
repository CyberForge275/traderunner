from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def _load_log(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("run_log.json must contain a JSON object")
    return data


def summarize_run(log_path: str) -> None:
    """Print a human-readable summary of a run_log.json file.

    Shows total measured time and per-step duration breakdown.
    """

    path = Path(log_path)
    if not path.exists():
        raise SystemExit(f"Log file not found: {path}")

    data = _load_log(path)
    entries: List[Dict[str, Any]] = list(data.get("entries", []))

    total = 0.0
    by_title: Dict[str, float] = defaultdict(float)

    for entry in entries:
        dur = entry.get("duration")
        try:
            dur_val = float(dur) if dur is not None else 0.0
        except (TypeError, ValueError):
            dur_val = 0.0
        total += dur_val
        title = str(entry.get("title") or entry.get("kind") or "(unknown)")
        by_title[title] += dur_val

    run_name = data.get("run_name", path.parent.name)
    strategy = data.get("strategy", "<unknown>")
    timeframe = data.get("timeframe", "<unknown>")

    print(f"Run: {run_name}")
    print(f"Strategy: {strategy} | Timeframe: {timeframe}")
    print(f"Total measured step time: {total:.2f}s")
    print("\nPer-step durations:")
    for title, dur in sorted(by_title.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {dur:6.2f}s  {title}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect TradeRunner run_log.json")
    parser.add_argument("log_path", help="Path to run_log.json")
    args = parser.parse_args()

    summarize_run(args.log_path)


if __name__ == "__main__":  # pragma: no cover - thin CLI wrapper
    main()
