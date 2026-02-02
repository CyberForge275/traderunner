import sys
from pprint import pprint

# Ensure local src import
sys.path.insert(0, "src")

from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore


def main():
    strategy_id = "insidebar_intraday"
    version = "1.0.1"
    defaults = StrategyConfigStore.get_defaults(strategy_id, version)

    core = defaults.get("core", {})
    tunable = defaults.get("tunable", {})

    print("strategy:", defaults.get("strategy"))
    print("version:", defaults.get("version"))

    for section_name, section in ("core", core), ("tunable", tunable):
        if "max_position_loss_pct_equity" in section:
            val = section.get("max_position_loss_pct_equity")
            print(
                f"section={section_name} key=max_position_loss_pct_equity value={val!r} type={type(val).__name__}"
            )
        else:
            print(f"section={section_name} key=max_position_loss_pct_equity MISSING")


if __name__ == "__main__":
    main()
