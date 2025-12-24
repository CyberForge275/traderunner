import importlib


def test_service_has_no_dash_dependency():
    import inspect

    module = importlib.import_module("trading_dashboard.services.trade_detail_service")
    source = inspect.getsource(module)
    assert "from dash" not in source
    assert "import dash" not in source


def test_repository_has_no_strategy_imports():
    module = importlib.import_module("trading_dashboard.repositories.trade_repository")
    text = getattr(module, "__doc__", "") or ""
    assert "strategy" not in text.lower()
