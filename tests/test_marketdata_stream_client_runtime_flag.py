from __future__ import annotations


def test_client_uses_runtime_flag_when_env_not_set(monkeypatch, tmp_path):
    from core.settings.runtime_config import reset_runtime_config_for_tests
    from axiom_bt.pipeline.marketdata_stream_client import MarketdataStreamClient

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        """
paths:
  marketdata_data_root: /var/lib/trading/marketdata
  trading_artifacts_root: /var/lib/trading/artifacts
services:
  marketdata_stream_url: http://127.0.0.1:8090
runtime:
  pipeline_auto_ensure_bars: true
""".strip()
    )

    reset_runtime_config_for_tests()
    monkeypatch.setenv("TRADING_CONFIG", str(cfg))
    monkeypatch.delenv("PIPELINE_AUTO_ENSURE_BARS", raising=False)
    monkeypatch.delenv("MARKETDATA_STREAM_URL", raising=False)

    client = MarketdataStreamClient()
    assert client.is_configured() is True
