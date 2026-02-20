from trading_dashboard.callbacks.ssot_config_viewer_callback import _normalize_new_version_input


def test_draft_same_version_allows_inplace_save():
    new_version_value, err = _normalize_new_version_input(
        is_finalized=False,
        current_version="1.0.1",
        new_version="1.0.1",
    )
    assert err is None
    assert new_version_value == ""


def test_finalized_requires_new_version():
    new_version_value, err = _normalize_new_version_input(
        is_finalized=True,
        current_version="1.0.1",
        new_version="",
    )
    assert new_version_value == ""
    assert err == "❌ Finalized versions require new version number"


def test_finalized_same_version_rejected():
    new_version_value, err = _normalize_new_version_input(
        is_finalized=True,
        current_version="1.0.1",
        new_version="1.0.1",
    )
    assert new_version_value == ""
    assert err == "❌ New version must differ from current (1.0.1)"


def test_draft_new_version_kept():
    new_version_value, err = _normalize_new_version_input(
        is_finalized=False,
        current_version="1.0.1",
        new_version="1.0.2",
    )
    assert err is None
    assert new_version_value == "1.0.2"
