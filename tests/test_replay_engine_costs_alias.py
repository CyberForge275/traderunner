from axiom_bt.engines.replay_engine import Costs


def test_costs_accepts_legacy_fees_bps_keyword():
    costs = Costs(fees_bps=2.5, slippage_bps=1.0)
    assert costs.commission_bps == 2.5
    assert costs.fees_bps == 2.5
    assert costs.slippage_bps == 1.0


def test_costs_accepts_canonical_commission_bps_keyword():
    costs = Costs(commission_bps=3.0, slippage_bps=0.5)
    assert costs.commission_bps == 3.0
    assert costs.fees_bps == 3.0
    assert costs.slippage_bps == 0.5


def test_costs_prefers_commission_when_both_are_set():
    costs = Costs(fees_bps=1.0, commission_bps=4.0, slippage_bps=0.0)
    assert costs.commission_bps == 4.0
    assert costs.fees_bps == 4.0
