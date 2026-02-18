from trading_dashboard.services.new_pipeline_adapter import NewPipelineAdapter


def _base_params():
    return {
        "strategy_version": "1.0.1",
        "lookback_days": 30,
        "session_timezone": "America/New_York",
        "session_mode": "rth",
        "session_filter": ["09:30-11:00", "14:00-15:00"],
        "timeframe_minutes": 5,
        "lookback_candles": 50,
    }


def test_adapter_preflight_ensure_bars_flag_off_skips_http(monkeypatch, tmp_path):
    from core.settings.runtime_config import reset_runtime_config_for_tests

    calls = {"ensure": 0, "run": 0}

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        f"""
paths:
  marketdata_data_root: {tmp_path / "marketdata"}
  trading_artifacts_root: {tmp_path / "artifacts"}
services:
  marketdata_stream_url: http://127.0.0.1:8090
runtime:
  pipeline_auto_ensure_bars: false
""".strip()
    )
    reset_runtime_config_for_tests()
    monkeypatch.setenv("TRADING_CONFIG", str(cfg))
    monkeypatch.setenv("PIPELINE_AUTO_ENSURE_BARS", "0")
    monkeypatch.setenv("MARKETDATA_STREAM_URL", "http://127.0.0.1:8090")
    monkeypatch.setenv("MARKETDATA_DATA_ROOT", str(tmp_path / "marketdata"))

    def _fake_ensure(self, req):
        calls["ensure"] += 1
        return {"status": "ok", "gaps_before": [], "gaps_after": []}

    def _fake_run_pipeline(**kwargs):
        calls["run"] += 1
        raise RuntimeError("stop_after_run")

    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.MarketdataStreamClient.ensure_bars",
        _fake_ensure,
    )
    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.run_pipeline",
        _fake_run_pipeline,
    )

    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    result = adapter.execute_backtest(
        run_name="ensure_off",
        strategy="insidebar_intraday",
        symbols=["HOOD"],
        timeframe="M5",
        start_date="2026-01-12",
        end_date="2026-02-11",
        config_params=_base_params(),
    )

    assert calls["ensure"] == 0
    assert calls["run"] == 1
    assert result["status"] == "failed"
    assert "stop_after_run" in result.get("error", "")


def test_adapter_preflight_ensure_bars_flag_on_calls_http(monkeypatch, tmp_path):
    from core.settings.runtime_config import reset_runtime_config_for_tests

    calls = {"ensure": 0, "run": 0}

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        f"""
paths:
  marketdata_data_root: {tmp_path / "marketdata"}
  trading_artifacts_root: {tmp_path / "artifacts"}
services:
  marketdata_stream_url: http://127.0.0.1:8090
runtime:
  pipeline_auto_ensure_bars: true
""".strip()
    )
    reset_runtime_config_for_tests()
    monkeypatch.setenv("TRADING_CONFIG", str(cfg))
    monkeypatch.setenv("PIPELINE_AUTO_ENSURE_BARS", "1")
    monkeypatch.setenv("MARKETDATA_STREAM_URL", "http://127.0.0.1:8090")
    monkeypatch.setenv("MARKETDATA_DATA_ROOT", str(tmp_path / "marketdata"))

    def _fake_ensure(self, req):
        calls["ensure"] += 1
        return {"status": "ok", "gaps_before": [{"a": 1}], "gaps_after": []}

    def _fake_run_pipeline(**kwargs):
        calls["run"] += 1
        raise RuntimeError("stop_after_run")

    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.MarketdataStreamClient.ensure_bars",
        _fake_ensure,
    )
    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.run_pipeline",
        _fake_run_pipeline,
    )

    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    result = adapter.execute_backtest(
        run_name="ensure_on",
        strategy="insidebar_intraday",
        symbols=["HOOD"],
        timeframe="M5",
        start_date="2026-01-12",
        end_date="2026-02-11",
        config_params=_base_params(),
    )

    assert calls["ensure"] == 1
    assert calls["run"] == 1
    assert result["status"] == "failed"
    assert "stop_after_run" in result.get("error", "")


def test_adapter_fails_when_producer_reports_gaps_after(monkeypatch, tmp_path):
    from core.settings.runtime_config import reset_runtime_config_for_tests

    calls = {"ensure": 0, "run": 0}

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        f"""
paths:
  marketdata_data_root: {tmp_path / "marketdata"}
  trading_artifacts_root: {tmp_path / "artifacts"}
services:
  marketdata_stream_url: http://127.0.0.1:8090
runtime:
  pipeline_auto_ensure_bars: true
""".strip()
    )
    reset_runtime_config_for_tests()
    monkeypatch.setenv("TRADING_CONFIG", str(cfg))
    monkeypatch.setenv("PIPELINE_AUTO_ENSURE_BARS", "1")
    monkeypatch.setenv("MARKETDATA_STREAM_URL", "http://127.0.0.1:8090")
    monkeypatch.setenv("MARKETDATA_DATA_ROOT", str(tmp_path / "marketdata"))

    def _fake_ensure(self, req):
        calls["ensure"] += 1
        return {
            "status": "ok",
            "gaps_before": [],
            "gaps_after": [{"gap_start": "2026-02-14", "gap_end": "2026-02-17"}],
        }

    def _fake_run_pipeline(**kwargs):
        calls["run"] += 1
        raise RuntimeError("run_pipeline_must_not_be_called")

    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.MarketdataStreamClient.ensure_bars",
        _fake_ensure,
    )
    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.run_pipeline",
        _fake_run_pipeline,
    )

    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    result = adapter.execute_backtest(
        run_name="ensure_gaps_after",
        strategy="insidebar_intraday",
        symbols=["HOOD"],
        timeframe="M5",
        start_date="2026-01-12",
        end_date="2026-02-11",
        config_params=_base_params(),
    )

    assert calls["ensure"] == 1
    assert calls["run"] == 0
    assert result["status"] == "failed"
    assert "ensure_bars_failed" in result.get("error", "")
