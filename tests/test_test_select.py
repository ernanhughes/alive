"""Selector correctness tests for ALIVE-TEST-INTEL-01.

These verify the conservative change-aware selection itself runs
correctly; they do not weaken any existing suite.
"""

from scripts import test_select


def _files(mode, changed):
    selected, reasons, meta = test_select.select(changed, mode, {c: "test" for c in changed})
    return selected, reasons, meta


def test_frontend_change_does_not_require_postgres_rebuild():
    selected, reasons, meta = _files("affected", ["dashboard/src/App.tsx"])
    assert (
        "tests/test_demo_live_01.py" in selected or "tests/test_browser_provenance.py" in selected
    )
    assert "tests/test_migrations.py" not in selected
    assert meta.get("docker_required") is not True
    assert all(reasons.values())


def test_migration_change_requires_db_tests_and_docker_flag():
    selected, _, meta = _files("affected", ["migrations/versions/0007_x.py"])
    assert "tests/test_migrations.py" in selected
    assert meta.get("docker_required") is True


def test_eval_change_requires_eval_tests():
    selected, _, _ = _files("affected", ["scripts/alive_eval01.py"])
    assert "tests/test_alive_eval01.py" in selected


def test_docker_change_requires_config_and_docker_tier():
    selected, _, meta = _files("affected", ["Dockerfile"])
    assert "tests/test_docker_config.py" in selected
    assert meta.get("docker_required") is True
    docker_selected, _, docker_meta = _files("docker", ["Dockerfile"])
    assert "tests/test_docker_config.py" in docker_selected
    assert docker_meta.get("docker_required") is True


def test_docs_only_is_minimal():
    selected, _, _ = _files("affected", ["docs/testing/notes.md"])
    assert set(selected) == {"tests/test_docker_config.py", "tests/test_transport.py"}


def test_unknown_impact_falls_back_to_full():
    selected, _, meta = _files("affected", ["some/new/unknown.xyz"])
    _, _, all_tests = test_select.build_indexes()
    assert len(selected) == len(all_tests)
    assert meta.get("fallback_full") is True


def test_core_change_falls_back_to_full_in_affected():
    selected, _, meta = _files("affected", ["alive/app.py"])
    _, _, all_tests = test_select.build_indexes()
    assert len(selected) == len(all_tests)
    assert meta.get("fallback_full") is True


def test_quick_is_bounded_smoke_for_broad_change():
    selected, _, meta = _files("quick", ["alive/app.py"])
    _, _, all_tests = test_select.build_indexes()
    assert len(selected) < len(all_tests)
    assert "tests/test_transport.py" in selected


def test_every_selection_has_reasons_and_no_duplicates():
    for mode, changed in [
        ("quick", ["alive/browser.py"]),
        ("affected", ["alive/browser.py"]),
        ("full", ["alive/browser.py"]),
        ("docker", ["Dockerfile"]),
    ]:
        selected, reasons, _ = _files(mode, changed)
        assert len(selected) == len(set(selected))
        assert all(reasons.get(t) for t in selected)


def test_full_mode_selects_everything():
    selected, _, _ = _files("full", ["alive/browser.py"])
    _, _, all_tests = test_select.build_indexes()
    assert selected == sorted(all_tests)
