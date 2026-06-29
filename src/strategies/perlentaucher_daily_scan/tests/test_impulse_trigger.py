from __future__ import annotations

from strategies.perlentaucher_daily_scan.impulse_trigger import (
    evaluate_impulse_trigger,
)


def test_evaluate_impulse_trigger_passes_when_all_thresholds_met() -> None:
    features = {
        "price_lr_trimmed": 0.01,
        "vol_lr_trimmed": 1000.0,
        "price_ratio_prev_to_breakout": 1.18,
        "volume_ratio_prev_to_breakout": 8.0,
        "price_ratio_prev_to_confirm": 1.12,
        "volume_ratio_prev_to_confirm": 2.0,
        "breakout_green": True,
        "confirm_close_vs_breakout_close": 1.01,
        "confirm_close_position_in_range": 0.60,
        "pre_max_drawdown": -0.20,
        "pre_gap_down_count": 1,
    }

    out = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=0.0,
        min_vol_lr_trimmed=0.0,
        min_price_ratio_prev_to_breakout=1.10,
        min_volume_ratio_prev_to_breakout=3.0,
        min_price_ratio_prev_to_confirm=1.05,
        min_volume_ratio_prev_to_confirm=1.2,
        require_breakout_green=True,
        min_confirm_close_vs_breakout_close=0.98,
        min_pre_max_drawdown=-0.35,
        max_pre_gap_down_count=4,
    )

    assert out["trigger_passed"] is True
    assert out["precondition_passed"] is True
    assert out["breakout_passed"] is True
    assert out["confirmation_passed"] is True
    assert out["trigger_reason"] == "IMPULSE_CONFIRMED"


def test_evaluate_impulse_trigger_fails_when_breakout_ratios_too_small() -> None:
    features = {
        "price_lr_trimmed": 0.01,
        "vol_lr_trimmed": 1000.0,
        "price_ratio_prev_to_breakout": 1.02,
        "volume_ratio_prev_to_breakout": 1.1,
        "price_ratio_prev_to_confirm": 1.02,
        "volume_ratio_prev_to_confirm": 1.0,
        "breakout_green": True,
        "confirm_close_vs_breakout_close": 1.01,
        "confirm_close_position_in_range": 0.60,
        "pre_max_drawdown": -0.20,
        "pre_gap_down_count": 1,
    }

    out = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=0.0,
        min_vol_lr_trimmed=0.0,
        min_price_ratio_prev_to_breakout=1.10,
        min_volume_ratio_prev_to_breakout=3.0,
        min_price_ratio_prev_to_confirm=1.05,
        min_volume_ratio_prev_to_confirm=1.2,
        require_breakout_green=True,
        min_confirm_close_vs_breakout_close=0.98,
        min_pre_max_drawdown=-0.35,
        max_pre_gap_down_count=4,
    )

    assert out["trigger_passed"] is False
    assert out["precondition_passed"] is True
    assert out["breakout_passed"] is False
    assert out["confirmation_passed"] is False
    assert out["trigger_reason"] == "BREAKOUT_THRESHOLD_FAILED"


def test_evaluate_impulse_trigger_fails_when_confirmation_missing() -> None:
    features = {
        "price_lr_trimmed": 0.01,
        "vol_lr_trimmed": 1000.0,
        "price_ratio_prev_to_breakout": 1.18,
        "volume_ratio_prev_to_breakout": 8.0,
        "price_ratio_prev_to_confirm": float("nan"),
        "volume_ratio_prev_to_confirm": float("nan"),
        "breakout_green": True,
        "confirm_close_vs_breakout_close": float("nan"),
        "confirm_close_position_in_range": float("nan"),
        "pre_max_drawdown": -0.20,
        "pre_gap_down_count": 1,
    }

    out = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=0.0,
        min_vol_lr_trimmed=0.0,
        min_price_ratio_prev_to_breakout=1.10,
        min_volume_ratio_prev_to_breakout=3.0,
        min_price_ratio_prev_to_confirm=1.05,
        min_volume_ratio_prev_to_confirm=1.2,
        require_breakout_green=True,
        min_confirm_close_vs_breakout_close=0.98,
        min_pre_max_drawdown=-0.35,
        max_pre_gap_down_count=4,
    )

    assert out["trigger_passed"] is False
    assert out["breakout_passed"] is True
    assert out["confirmation_passed"] is False
    assert out["trigger_reason"] == "CONFIRMATION_DATA_MISSING"


def test_evaluate_impulse_trigger_fails_when_precondition_is_negative() -> None:
    features = {
        "price_lr_trimmed": -0.02,
        "vol_lr_trimmed": -5.0,
        "price_ratio_prev_to_breakout": 1.18,
        "volume_ratio_prev_to_breakout": 8.0,
        "price_ratio_prev_to_confirm": 1.12,
        "volume_ratio_prev_to_confirm": 2.0,
        "breakout_green": True,
        "confirm_close_vs_breakout_close": 1.01,
        "confirm_close_position_in_range": 0.60,
        "pre_max_drawdown": -0.20,
        "pre_gap_down_count": 1,
    }

    out = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=0.0,
        min_vol_lr_trimmed=0.0,
        min_price_ratio_prev_to_breakout=1.10,
        min_volume_ratio_prev_to_breakout=3.0,
        min_price_ratio_prev_to_confirm=1.05,
        min_volume_ratio_prev_to_confirm=1.2,
        require_breakout_green=True,
        min_confirm_close_vs_breakout_close=0.98,
        min_pre_max_drawdown=-0.35,
        max_pre_gap_down_count=4,
    )

    assert out["trigger_passed"] is False
    assert out["precondition_passed"] is False
    assert out["breakout_passed"] is True
    assert out["confirmation_passed"] is True
    assert out["trigger_reason"] == "PRECONDITION_FAILED"


def test_evaluate_impulse_trigger_rejects_red_breakout_bar() -> None:
    features = {
        "price_lr_trimmed": 0.02,
        "vol_lr_trimmed": 5000.0,
        "price_ratio_prev_to_breakout": 1.30,
        "volume_ratio_prev_to_breakout": 50.0,
        "price_ratio_prev_to_confirm": 1.25,
        "volume_ratio_prev_to_confirm": 5.0,
        "breakout_green": False,
        "confirm_close_vs_breakout_close": 1.02,
        "confirm_close_position_in_range": 0.60,
        "pre_max_drawdown": -0.25,
        "pre_gap_down_count": 2,
    }

    out = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=-0.02,
        min_vol_lr_trimmed=-20_000.0,
        min_price_ratio_prev_to_breakout=1.17,
        min_volume_ratio_prev_to_breakout=19.0,
        min_price_ratio_prev_to_confirm=1.15,
        min_volume_ratio_prev_to_confirm=3.0,
        require_breakout_green=True,
        min_confirm_close_vs_breakout_close=0.98,
        min_pre_max_drawdown=-0.35,
        max_pre_gap_down_count=4,
    )

    assert out["trigger_passed"] is False
    assert out["trigger_reason"] == "BREAKOUT_BAR_REJECTED"


def test_evaluate_impulse_trigger_rejects_weak_confirmation_close() -> None:
    features = {
        "price_lr_trimmed": 0.02,
        "vol_lr_trimmed": 5000.0,
        "price_ratio_prev_to_breakout": 1.30,
        "volume_ratio_prev_to_breakout": 50.0,
        "price_ratio_prev_to_confirm": 1.20,
        "volume_ratio_prev_to_confirm": 4.0,
        "breakout_green": True,
        "confirm_close_vs_breakout_close": 0.90,
        "confirm_close_position_in_range": 0.60,
        "pre_max_drawdown": -0.25,
        "pre_gap_down_count": 2,
    }

    out = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=-0.02,
        min_vol_lr_trimmed=-20_000.0,
        min_price_ratio_prev_to_breakout=1.17,
        min_volume_ratio_prev_to_breakout=19.0,
        min_price_ratio_prev_to_confirm=1.15,
        min_volume_ratio_prev_to_confirm=3.0,
        require_breakout_green=True,
        min_confirm_close_vs_breakout_close=0.98,
        min_pre_max_drawdown=-0.35,
        max_pre_gap_down_count=4,
    )

    assert out["trigger_passed"] is False
    assert out["trigger_reason"] == "CONFIRMATION_CLOSE_REJECTED"


def test_evaluate_impulse_trigger_rejects_confirmation_close_low_in_range() -> None:
    features = {
        "price_lr_trimmed": 0.02,
        "vol_lr_trimmed": 5000.0,
        "price_ratio_prev_to_breakout": 1.30,
        "volume_ratio_prev_to_breakout": 50.0,
        "price_ratio_prev_to_confirm": 1.20,
        "volume_ratio_prev_to_confirm": 4.0,
        "breakout_green": True,
        "confirm_close_vs_breakout_close": 1.00,
        "confirm_close_position_in_range": 0.20,
        "pre_max_drawdown": -0.25,
        "pre_gap_down_count": 2,
    }

    out = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=-0.02,
        min_vol_lr_trimmed=-20_000.0,
        min_price_ratio_prev_to_breakout=1.17,
        min_volume_ratio_prev_to_breakout=19.0,
        min_price_ratio_prev_to_confirm=1.15,
        min_volume_ratio_prev_to_confirm=3.0,
        require_breakout_green=True,
        min_confirm_close_vs_breakout_close=0.98,
        min_confirm_close_position_in_range=0.50,
        min_pre_max_drawdown=-0.35,
        max_pre_gap_down_count=4,
    )

    assert out["trigger_passed"] is False
    assert out["trigger_reason"] == "CONFIRMATION_RANGE_POSITION_REJECTED"


def test_evaluate_impulse_trigger_rejects_rough_pre_window_path() -> None:
    features = {
        "price_lr_trimmed": 0.02,
        "vol_lr_trimmed": 5000.0,
        "price_ratio_prev_to_breakout": 1.30,
        "volume_ratio_prev_to_breakout": 50.0,
        "price_ratio_prev_to_confirm": 1.20,
        "volume_ratio_prev_to_confirm": 4.0,
        "breakout_green": True,
        "confirm_close_vs_breakout_close": 1.00,
        "confirm_close_position_in_range": 0.60,
        "pre_max_drawdown": -0.55,
        "pre_gap_down_count": 5,
    }

    out = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=-0.02,
        min_vol_lr_trimmed=-20_000.0,
        min_price_ratio_prev_to_breakout=1.17,
        min_volume_ratio_prev_to_breakout=19.0,
        min_price_ratio_prev_to_confirm=1.15,
        min_volume_ratio_prev_to_confirm=3.0,
        require_breakout_green=True,
        min_confirm_close_vs_breakout_close=0.98,
        min_pre_max_drawdown=-0.35,
        max_pre_gap_down_count=4,
    )

    assert out["trigger_passed"] is False
    assert out["trigger_reason"] == "PREWINDOW_PATH_REJECTED"
