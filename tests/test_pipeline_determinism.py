import shutil
import pandas as pd
from pathlib import Path
from axiom_bt.pipeline.cli import main as pipeline_main


def make_bars(tmpdir: Path) -> Path:
    ts = pd.date_range("2025-01-01", periods=5, freq="5min", tz="UTC")
    df = pd.DataFrame({
        "timestamp": ts,
        "open": [100,101,102,103,104],
        "high": [101,102,103,104,105],
        "low":  [99,100,101,102,103],
        "close":[100,102,101,104,103],
        "volume":[1000,1000,1000,1000,1000],
    })
    path = tmpdir / "bars.csv"
    df.to_csv(path, index=False)
    return path


def run_pipeline(tmpdir: Path, run_id: str, compound: bool) -> Path:
    bars = make_bars(tmpdir)
    out = tmpdir / run_id
    argv = [
        "--run-id", run_id,
        "--out-dir", str(out),
        "--bars-path", str(bars),
        "--strategy-id", "insidebar_intraday",
        "--strategy-version", "1.0.0",
        "--symbol", "TEST",
        "--timeframe", "M5",
        "--requested-end", "2025-01-05",
        "--lookback-days", "5",
        "--initial-cash", "10000",
    ]
    if compound:
        argv.append("--compound-enabled")
    pipeline_main(argv)
    return out


def test_gate_determinism(tmp_path):
    out1 = run_pipeline(tmp_path, "runA", compound=False)
    out2 = run_pipeline(tmp_path, "runB", compound=False)

    # hashes must match
    man1 = (out1 / "run_manifest.json").read_text()
    man2 = (out2 / "run_manifest.json").read_text()
    # Compare hashes (ignore run_id)
    def extract(hay, key):
        marker = f'"{key}": "'
        return hay.split(marker)[1][:64]
    assert extract(man1, "bars_hash") == extract(man2, "bars_hash")
    assert extract(man1, "intent_hash") == extract(man2, "intent_hash")
    assert extract(man1, "fills_hash") == extract(man2, "fills_hash")

    # trades identical
    t1 = (out1 / "trades.csv").read_text()
    t2 = (out2 / "trades.csv").read_text()
    assert t1 == t2


def test_gate_parity_same_fills(tmp_path):
    outL = run_pipeline(tmp_path, "runL", compound=False)
    outC = run_pipeline(tmp_path, "runC", compound=True)

    manL = (outL / "run_manifest.json").read_text()
    manC = (outC / "run_manifest.json").read_text()
    assert 'intent_hash' in manL and 'intent_hash' in manC
    assert 'fills_hash' in manL and 'fills_hash' in manC
    assert 'fills_hash' in manL and manL.split('"fills_hash": "')[1][:64] == manC.split('"fills_hash": "')[1][:64]

    fillsL = (outL / "fills.csv").read_text()
    fillsC = (outC / "fills.csv").read_text()
    assert fillsL == fillsC
