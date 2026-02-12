import importlib
import importlib.abc
import sys


class _BlockTraceFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "axiom_bt.utils.trace":
            raise ModuleNotFoundError("blocked for test")
        return None


def test_run_backtest_callback_import_without_trace(monkeypatch):
    blocker = _BlockTraceFinder()
    monkeypatch.setattr(sys, "meta_path", [blocker] + list(sys.meta_path))
    sys.modules.pop("axiom_bt.utils.trace", None)
    sys.modules.pop("trading_dashboard.callbacks.run_backtest_callback", None)

    mod = importlib.import_module("trading_dashboard.callbacks.run_backtest_callback")
    assert callable(mod.trace_ui)
