from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan import scan_marketdata
from strategies.perlentaucher_daily_scan import scan_runner


def _build_symbol_frame(
    symbol: str,
    dates: pd.DatetimeIndex,
    *,
    base_close: float,
    last_closes: list[float],
    base_volume: float,
    last_volumes: list[float],
) -> pd.DataFrame:
    closes = [base_close] * (len(dates) - len(last_closes)) + list(last_closes)
    volumes = [base_volume] * (len(dates) - len(last_volumes)) + list(last_volumes)
    lows = [c - 0.5 for c in closes]
    opens = [c - 0.1 for c in closes]
    highs = [c + 0.2 for c in closes]
    return pd.DataFrame(
        {
            "symbol": symbol,
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def test_resolve_request_window_extends_for_match_reference_history() -> None:
    valid_from, valid_to = scan_runner.resolve_request_window(
        valid_from="2026-06-11",
        valid_to="2026-06-17",
        mode="match",
        sweet_spot_pairs=[("AXTI", "2025-08-20")],
    )

    assert valid_from == "2025-02-25"
    assert valid_to == "2026-06-17"


def test_run_perlentaucher_scan_returns_final_matches_for_requested_timeframe(monkeypatch) -> None:
    dates = pd.date_range("2025-10-01", periods=140, freq="B", tz="UTC")
    shared_last_closes = [6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5]
    shared_last_volumes = [650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0]

    axti = _build_symbol_frame(
        "AXTI",
        dates,
        base_close=20.0,
        last_closes=[value + 15.0 for value in shared_last_closes],
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )
    passed = _build_symbol_frame(
        "PASS",
        dates,
        base_close=5.0,
        last_closes=shared_last_closes,
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )

    raw_df = pd.concat([axti, passed], ignore_index=True)
    as_of_date = str(dates[-1].date())
    monkeypatch.setattr(
        scan_runner,
        "fetch_daily_stock_data",
        lambda **_: (raw_df, {"merged_rows": len(raw_df), "status": "ok"}),
    )
    monkeypatch.setattr(
        scan_runner,
        "load_active_sweet_spot_config",
        lambda: {"reference_set": "default", "sweet_spot_pairs": [["AXTI", as_of_date]]},
    )

    out = scan_runner.run_perlentaucher_scan(
        scan_runner.PerlentaucherScanRequest(
            valid_from=as_of_date,
            valid_to=as_of_date,
            base_url="http://127.0.0.1:8090",
            mode="match",
            non_empty_only=False,
        )
    )

    assert list(out.summary_df["symbols_csv"]) == ["PASS"]
    assert out.detail_df.empty
    assert out.meta["status"] == "ok"


def test_run_perlentaucher_scan_filters_empty_days_when_requested(monkeypatch) -> None:
    summary_df = pd.DataFrame(
        {
            "as_of_date": ["2026-06-11", "2026-06-12"],
            "symbol_count": [0, 1],
            "symbols": [[], ["PASS"]],
            "symbols_csv": ["", "PASS"],
            "closest_miss_count": [1, 0],
            "closest_miss_symbols": [["MISS"], []],
            "closest_miss_symbols_csv": ["MISS", ""],
            "closest_miss_scores_csv": ["1.0", ""],
        }
    )
    detail_df = pd.DataFrame(
        {
            "as_of_date": ["2026-06-11", "2026-06-12"],
            "symbol": ["MISS", "PASS"],
        }
    )
    monkeypatch.setattr(
        scan_runner,
        "fetch_daily_stock_data",
        lambda **_: (pd.DataFrame(), {"status": "ok"}),
    )
    monkeypatch.setattr(
        scan_runner,
        "build_scan_outputs",
        lambda **_: scan_runner.PerlentaucherScanOutputs(
            summary_df=summary_df,
            detail_df=detail_df,
            reference_frame_df=pd.DataFrame(),
        ),
    )

    out = scan_runner.run_perlentaucher_scan(
        scan_runner.PerlentaucherScanRequest(
            valid_from="2026-06-11",
            valid_to="2026-06-12",
            base_url="http://127.0.0.1:8090",
            mode="match",
            non_empty_only=True,
        )
    )

    assert list(out.summary_df["as_of_date"]) == ["2026-06-12"]
    assert list(out.detail_df["as_of_date"]) == ["2026-06-12"]


def test_run_perlentaucher_scan_fetches_one_extra_day_for_first_trigger_entry_levels(monkeypatch) -> None:
    captured: dict[str, object] = {}
    summary_df = pd.DataFrame(
        {
            "as_of_date": ["2026-06-17"],
            "symbol_count": [1],
            "symbols": [["PASS"]],
            "symbols_csv": ["PASS"],
            "entry_dates_csv": ["2026-06-18"],
            "entry_prices_csv": ["4.10"],
        }
    )
    detail_df = pd.DataFrame(
        {
            "as_of_date": ["2026-06-17"],
            "symbol": ["PASS"],
            "entry_date": ["2026-06-18"],
            "entry_open": [4.10],
        }
    )

    def _stub_fetch_daily_stock_data(**kwargs):
        captured["valid_to"] = kwargs["valid_to"]
        return pd.DataFrame(), {"status": "ok"}

    monkeypatch.setattr(scan_runner, "fetch_daily_stock_data", _stub_fetch_daily_stock_data)
    monkeypatch.setattr(
        scan_runner,
        "build_scan_outputs",
        lambda **_: scan_runner.PerlentaucherScanOutputs(
            summary_df=summary_df,
            detail_df=detail_df,
            reference_frame_df=pd.DataFrame(),
        ),
    )

    out = scan_runner.run_perlentaucher_scan(
        scan_runner.PerlentaucherScanRequest(
            valid_from="2026-06-17",
            valid_to="2026-06-17",
            base_url="http://127.0.0.1:8090",
            mode="first_trigger",
            non_empty_only=False,
        )
    )

    assert captured["valid_to"] == "2026-06-18"
    assert out.summary_df.iloc[0]["entry_dates_csv"] == "2026-06-18"


def test_fetch_daily_stock_data_refreshes_stale_v2_export_via_mysql_fallback(
    monkeypatch,
    tmp_path,
) -> None:
    stale_path = tmp_path / "stale.parquet"
    fresh_path = tmp_path / "fresh.parquet"
    stale_path.write_text("")
    fresh_path.write_text("")

    stale_df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2025-02-25", "2026-06-11", "2026-06-12"], utc=True),
            "open": [3.8, 4.0, 4.1],
            "high": [4.0, 4.2, 4.3],
            "low": [3.7, 3.9, 4.0],
            "close": [3.9, 4.1, 4.2],
            "volume": [95_000.0, 100_000.0, 110_000.0],
        }
    )
    fresh_df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2025-02-25", "2026-06-15", "2026-06-16", "2026-06-17"], utc=True),
            "open": [3.8, 4.3, 4.4, 4.5],
            "high": [4.0, 4.4, 4.5, 4.6],
            "low": [3.7, 4.2, 4.3, 4.4],
            "close": [3.9, 4.35, 4.45, 4.55],
            "volume": [95_000.0, 120_000.0, 130_000.0, 140_000.0],
        }
    )

    calls: list[str] = []

    class _Response:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return dict(self._payload)

    def _fake_post(url: str, json: dict, timeout: int) -> _Response:
        del json, timeout
        calls.append(url)
        if url.endswith("/daily/v2/export_merged"):
            return _Response({"status": "ok", "cache_hit": True, "merged_parquet_path": str(stale_path)})
        if url.endswith("/daily/mysql/export_merged"):
            return _Response({"status": "ok", "cache_hit": False, "merged_parquet_path": str(fresh_path)})
        raise AssertionError(f"unexpected url: {url}")

    def _fake_read_parquet(path: str | object, *args, **kwargs) -> pd.DataFrame:
        del args, kwargs
        if str(path) == str(stale_path):
            return stale_df.copy()
        if str(path) == str(fresh_path):
            return fresh_df.copy()
        raise AssertionError(f"unexpected parquet path: {path}")

    monkeypatch.setattr(scan_marketdata.requests, "post", _fake_post)
    monkeypatch.setattr(scan_marketdata.pd, "read_parquet", _fake_read_parquet)
    monkeypatch.setattr(scan_marketdata, "_market_today", lambda session_timezone: pd.Timestamp("2026-06-18").date())

    raw_df, meta = scan_runner.fetch_daily_stock_data(
        base_url="http://127.0.0.1:8090",
        valid_from="2026-06-12",
        valid_to="2026-06-18",
        mode="match",
        sweet_spot_pairs=[("AXTI", "2025-08-20")],
    )

    assert calls == [
        "http://127.0.0.1:8090/daily/v2/export_merged",
        "http://127.0.0.1:8090/daily/mysql/export_merged",
    ]
    assert str(raw_df["date"].max().date()) == "2026-06-17"
    assert meta["coverage_refresh_triggered"] is True
    assert meta["source_endpoint"] == scan_marketdata.REFRESH_MERGED_ENDPOINT
    assert meta["coverage_target_to"] == "2026-06-17"


def test_fetch_daily_stock_data_raises_when_refresh_is_still_stale(
    monkeypatch,
    tmp_path,
) -> None:
    stale_path = tmp_path / "stale.parquet"
    still_stale_path = tmp_path / "still_stale.parquet"
    stale_path.write_text("")
    still_stale_path.write_text("")

    stale_df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2025-02-25", "2026-06-11", "2026-06-12"], utc=True),
            "open": [3.8, 4.0, 4.1],
            "high": [4.0, 4.2, 4.3],
            "low": [3.7, 3.9, 4.0],
            "close": [3.9, 4.1, 4.2],
            "volume": [95_000.0, 100_000.0, 110_000.0],
        }
    )
    still_stale_df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2025-02-25", "2026-06-15", "2026-06-16"], utc=True),
            "open": [3.8, 4.3, 4.4],
            "high": [4.0, 4.4, 4.5],
            "low": [3.7, 4.2, 4.3],
            "close": [3.9, 4.35, 4.45],
            "volume": [95_000.0, 120_000.0, 130_000.0],
        }
    )

    class _Response:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return dict(self._payload)

    def _fake_post(url: str, json: dict, timeout: int) -> _Response:
        del json, timeout
        if url.endswith("/daily/v2/export_merged"):
            return _Response({"status": "ok", "cache_hit": True, "merged_parquet_path": str(stale_path)})
        if url.endswith("/daily/mysql/export_merged"):
            return _Response({"status": "ok", "cache_hit": False, "merged_parquet_path": str(still_stale_path)})
        raise AssertionError(f"unexpected url: {url}")

    def _fake_read_parquet(path: str | object, *args, **kwargs) -> pd.DataFrame:
        del args, kwargs
        if str(path) == str(stale_path):
            return stale_df.copy()
        if str(path) == str(still_stale_path):
            return still_stale_df.copy()
        raise AssertionError(f"unexpected parquet path: {path}")

    monkeypatch.setattr(scan_marketdata.requests, "post", _fake_post)
    monkeypatch.setattr(scan_marketdata.pd, "read_parquet", _fake_read_parquet)
    monkeypatch.setattr(scan_marketdata, "_market_today", lambda session_timezone: pd.Timestamp("2026-06-18").date())

    try:
        scan_runner.fetch_daily_stock_data(
            base_url="http://127.0.0.1:8090",
            valid_from="2026-06-12",
            valid_to="2026-06-18",
            mode="match",
            sweet_spot_pairs=[("AXTI", "2025-08-20")],
        )
    except RuntimeError as exc:
        message = str(exc)
        assert "coverage" in message.lower()
        assert "2026-06-17" in message
        assert "2026-06-16" in message
    else:
        raise AssertionError("expected RuntimeError when refresh export remains stale")


def test_fetch_daily_stock_data_raises_when_refresh_still_misses_history_floor(
    monkeypatch,
    tmp_path,
) -> None:
    stale_path = tmp_path / "stale.parquet"
    short_history_path = tmp_path / "short_history.parquet"
    stale_path.write_text("")
    short_history_path.write_text("")

    stale_df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "date": pd.to_datetime(["2025-03-10", "2026-06-12"], utc=True),
            "open": [4.0, 4.1],
            "high": [4.2, 4.3],
            "low": [3.9, 4.0],
            "close": [4.1, 4.2],
            "volume": [100_000.0, 110_000.0],
        }
    )
    short_history_df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2025-03-03", "2026-06-16", "2026-06-17"], utc=True),
            "open": [4.3, 4.4, 4.5],
            "high": [4.4, 4.5, 4.6],
            "low": [4.2, 4.3, 4.4],
            "close": [4.35, 4.45, 4.55],
            "volume": [120_000.0, 130_000.0, 140_000.0],
        }
    )

    class _Response:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return dict(self._payload)

    def _fake_post(url: str, json: dict, timeout: int) -> _Response:
        del json, timeout
        if url.endswith("/daily/v2/export_merged"):
            return _Response({"status": "ok", "cache_hit": True, "merged_parquet_path": str(stale_path)})
        if url.endswith("/daily/mysql/export_merged"):
            return _Response({"status": "ok", "cache_hit": False, "merged_parquet_path": str(short_history_path)})
        raise AssertionError(f"unexpected url: {url}")

    def _fake_read_parquet(path: str | object, *args, **kwargs) -> pd.DataFrame:
        del args, kwargs
        if str(path) == str(stale_path):
            return stale_df.copy()
        if str(path) == str(short_history_path):
            return short_history_df.copy()
        raise AssertionError(f"unexpected parquet path: {path}")

    monkeypatch.setattr(scan_marketdata.requests, "post", _fake_post)
    monkeypatch.setattr(scan_marketdata.pd, "read_parquet", _fake_read_parquet)
    monkeypatch.setattr(scan_marketdata, "_market_today", lambda session_timezone: pd.Timestamp("2026-06-18").date())

    try:
        scan_runner.fetch_daily_stock_data(
            base_url="http://127.0.0.1:8090",
            valid_from="2026-06-12",
            valid_to="2026-06-18",
            mode="match",
            sweet_spot_pairs=[("AXTI", "2025-08-20")],
        )
    except RuntimeError as exc:
        message = str(exc)
        assert "coverage" in message.lower()
        assert "2025-02-25" in message
        assert "2025-03-03" in message
    else:
        raise AssertionError("expected RuntimeError when refresh export misses requested history floor")
