from trading_dashboard.callbacks import ssot_config_viewer_callback as cb


def simulate_case(original, value):
    loaded_defaults = {
        "core": {},
        "tunable": {"max_position_loss_pct_equity": original},
    }
    edited_values = [value]
    edited_ids = [{"section": "tunable", "key": "max_position_loss_pct_equity"}]
    try:
        core_overrides, tunable_overrides = cb._compute_overrides(
            loaded_defaults, edited_values, edited_ids
        )
        return {
            "value_repr": repr(value),
            "value_type": type(value).__name__,
            "core_overrides": core_overrides,
            "tunable_overrides": tunable_overrides,
        }
    except Exception as e:
        return {
            "value_repr": repr(value),
            "value_type": type(value).__name__,
            "exception": f"{type(e).__name__}: {e}",
        }


cases = [
    (0.01, "0,03"),
    (0.01, "0.03"),
    (0.01, ""),
    (0.01, None),
    (0.01, " 0,03 "),
    (0.01, ["0,03"]),
]

for original, value in cases:
    result = simulate_case(original, value)
    print(f"original={original!r} value={result['value_repr']} type={result['value_type']}")
    if "exception" in result:
        print(f"  EXC: {result['exception']}")
    else:
        print(f"  core_overrides={result['core_overrides']}")
        print(f"  tunable_overrides={result['tunable_overrides']}")
