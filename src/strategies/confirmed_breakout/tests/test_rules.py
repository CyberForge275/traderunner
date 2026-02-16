import pandas as pd

from strategies.inside_bar import rules


def _make_df(mb, ib):
    data = [mb, ib]
    df = pd.DataFrame(data, columns=["open", "high", "low", "close"])
    df["atr"] = 1.0
    return df


def test_mode1_mb_body_ib_hl_inclusive():
    mb = [10.0, 13.0, 9.0, 12.0]  # body 10-12
    ib = [11.0, 11.5, 10.5, 11.2]
    df = _make_df(mb, ib)
    mask = rules.eval_vectorized(df, rules.MODE_MB_BODY_IB_HL, strict=False)
    assert bool(mask.iloc[1]) is True


def test_mode1_mb_body_ib_hl_reject_outside_body():
    mb = [10.0, 13.0, 9.0, 12.0]  # body 10-12
    ib = [11.0, 12.5, 9.9, 11.2]  # low below body
    df = _make_df(mb, ib)
    mask = rules.eval_vectorized(df, rules.MODE_MB_BODY_IB_HL, strict=False)
    assert bool(mask.iloc[1]) is False


def test_mode2_mb_body_ib_body_allows_wicks_outside():
    mb = [10.0, 13.0, 9.0, 12.0]  # body 10-12
    ib = [11.0, 13.5, 9.5, 11.5]  # body inside, wicks outside
    df = _make_df(mb, ib)
    mask = rules.eval_vectorized(df, rules.MODE_MB_BODY_IB_BODY, strict=False)
    assert bool(mask.iloc[1]) is True


def test_mode3_mb_range_ib_hl_allows_body_outside():
    mb = [10.0, 14.0, 8.0, 12.0]  # range 8-14
    ib = [13.0, 13.5, 12.5, 12.8]  # outside body, inside range
    df = _make_df(mb, ib)
    mask = rules.eval_vectorized(df, rules.MODE_MB_RANGE_IB_HL, strict=False)
    assert bool(mask.iloc[1]) is True


def test_mode4_mb_high_ib_high_and_close_in_mb_range():
    mb = [10.0, 14.0, 8.0, 12.0]  # range 8-14
    ib = [11.0, 13.5, 7.5, 13.9]  # ib_high inside, ib_close inside, ib_low outside allowed
    df = _make_df(mb, ib)
    mask = rules.eval_vectorized(df, rules.MODE_MB_HIGH_IB_HIGH_AND_CLOSE_IN_MB_RANGE, strict=False)
    assert bool(mask.iloc[1]) is True


def test_mode4_rejects_ib_high_above_mb_high():
    mb = [10.0, 14.0, 8.0, 12.0]  # range 8-14
    ib = [11.0, 14.5, 9.0, 13.0]  # ib_high above mb_high
    df = _make_df(mb, ib)
    mask = rules.eval_vectorized(df, rules.MODE_MB_HIGH_IB_HIGH_AND_CLOSE_IN_MB_RANGE, strict=False)
    assert bool(mask.iloc[1]) is False


def test_mode4_rejects_ib_close_outside_mb_range():
    mb = [10.0, 14.0, 8.0, 12.0]  # range 8-14
    ib = [11.0, 13.5, 9.0, 7.5]  # ib_close below mb_low
    df = _make_df(mb, ib)
    mask = rules.eval_vectorized(df, rules.MODE_MB_HIGH_IB_HIGH_AND_CLOSE_IN_MB_RANGE, strict=False)
    assert bool(mask.iloc[1]) is False

def test_strict_vs_inclusive_boundary():
    mb = [10.0, 13.0, 9.0, 12.0]  # body 10-12
    ib = [10.5, 12.0, 10.0, 11.0]  # touches body bounds
    df = _make_df(mb, ib)
    inclusive = rules.eval_vectorized(df, rules.MODE_MB_BODY_IB_HL, strict=False)
    strict = rules.eval_vectorized(df, rules.MODE_MB_BODY_IB_HL, strict=True)
    assert bool(inclusive.iloc[1]) is True
    assert bool(strict.iloc[1]) is False


def test_scalar_vectorized_parity():
    mb = [10.0, 13.0, 9.0, 12.0]
    ib = [11.0, 11.5, 10.5, 11.2]
    df = _make_df(mb, ib)
    mask = rules.eval_vectorized(df, rules.MODE_MB_BODY_IB_HL, strict=False)
    scalar = rules.eval_scalar(
        mb_open=mb[0],
        mb_high=mb[1],
        mb_low=mb[2],
        mb_close=mb[3],
        ib_open=ib[0],
        ib_high=ib[1],
        ib_low=ib[2],
        ib_close=ib[3],
        mode=rules.MODE_MB_BODY_IB_HL,
        strict=False,
    )
    assert mask.iloc[1] == scalar
