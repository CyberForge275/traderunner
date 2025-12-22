from __future__ import annotations

from pathlib import Path

import matplotlib

# Use headless backend to avoid Tk/thread crashes in Dash/background threads
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .metrics import drawdown_series


def save_equity_png(equity: pd.DataFrame, path: Path) -> Path:
    if equity is None or equity.empty:
        return path
    x = pd.to_datetime(equity["ts"], utc=True)
    y = equity["equity"].astype(float)

    figure = plt.figure(figsize=(9, 4))
    axis = figure.add_subplot(111)
    axis.plot(x, y, linewidth=1.5)
    axis.set_title("Equity Curve")
    axis.set_xlabel("Time")
    axis.set_ylabel("Equity")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return path


def save_drawdown_png(equity: pd.DataFrame, path: Path) -> Path:
    if equity is None or equity.empty:
        return path
    _, dd_pct = drawdown_series(equity)
    figure = plt.figure(figsize=(9, 3))
    axis = figure.add_subplot(111)
    axis.plot(dd_pct.index, dd_pct.values, linewidth=1.2)
    axis.set_title("Drawdown (pct)")
    axis.set_xlabel("Time")
    axis.set_ylabel("DD %")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return path
