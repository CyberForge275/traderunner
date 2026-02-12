import axiom_bt


def test_axiom_bt_import_origin_is_local_traderunner_src():
    origin = str(axiom_bt.__file__)
    assert "/traderunner/src/axiom_bt/" in origin
    assert "marketdata-monorepo" not in origin
