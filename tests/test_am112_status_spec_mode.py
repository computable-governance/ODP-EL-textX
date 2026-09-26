"""
AM-112 — the terms-of-engagement scenarios as API scenarios, and the
status endpoint's mode parameter.

GET /obligations/{token}/status takes mode=spec (static model of the active
scenario's .el file) or mode=hybrid (default, anchored to the runtime), as
GET /kripke/witness does, and reports the mode. For the public data portal
at its configured k = 480, spec mode gives the static terms-of-engagement
reading: recording holds; review and notification fail with a deadline
violation. Hybrid mode's counterexample is still the revoke/reinstate cycle
(see the hybrid-cycle finding in docs/CONCEPTS_INDEX.md).
"""
import contextlib
import io

import pytest
from fastapi import HTTPException

import el_api


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


@pytest.fixture
def pin(monkeypatch):
    """Point the API's shared runtime and active scenario at `name`."""
    def _pin(name):
        rt = _quiet(el_api._SCENARIO_BUILDERS[name])
        monkeypatch.setattr(el_api, "_runtime", rt)
        monkeypatch.setattr(el_api, "_active_scenario", name)
        return rt
    return _pin


@pytest.mark.parametrize("name", ["public_data_portal", "external_agent_access"])
def test_registered(name):
    assert el_api._COMMUNITY_FOR_SCENARIO[name] == "ExternalAgentAccess"
    assert el_api._SCENARIO_DEADLINE_SCALE[name] == 480


def test_portal_spec_mode_gives_static_reading(pin):
    pin("public_data_portal")
    record = _quiet(el_api.get_obligation_status, "refusalRecordBurden", mode="spec")
    assert (record.mode, record.deadline_scale) == ("spec", 480)
    assert record.compelled is True
    for token in ("refusalReviewBurden", "incidentNotificationBurden"):
        resp = _quiet(el_api.get_obligation_status, token, mode="spec")
        assert resp.compelled is False
        assert resp.detectable is True
        assert resp.status is None
        labels = [s.label for s in resp.counterexample_path]
        assert labels[-2].startswith(f"violate:{token} (deadline=")
        assert "at k=480" in labels[-2]


def test_spec_mode_ignores_runtime_state(pin):
    """Hybrid, refusalReviewBurden is discharged and no longer pending;
    spec mode still checks the model from the spec's initial state."""
    rt = pin("public_data_portal")
    for action, actor in [("refuseRequest", "AgencyGateway"),
                          ("recordRefusal", "AgencyGateway"),
                          ("reviewRefusal", "AgencySecurityContact")]:
        assert rt.advance(action, actor).outcome == "ok"
    hybrid = _quiet(el_api.get_obligation_status, "refusalReviewBurden")
    assert hybrid.mode == "hybrid"
    assert hybrid.status == "not triggered within horizon"
    spec = _quiet(el_api.get_obligation_status, "refusalReviewBurden", mode="spec")
    assert spec.status is None
    assert spec.counterexample_path


def test_hybrid_counterexample_is_still_the_cycle(pin):
    pin("public_data_portal")
    resp = _quiet(el_api.get_obligation_status, "incidentNotificationBurden")
    assert resp.mode == "hybrid"
    assert resp.counterexample_path[-1].label.startswith("↺ cycle")


@pytest.mark.parametrize("token, mode, code", [
    ("refusalRecordBurden", "bogus", 400),
    ("publishedDatasetReadPermit", "spec", 400),
    ("noSuchToken", "spec", 404),
])
def test_spec_mode_errors(pin, token, mode, code):
    pin("public_data_portal")
    with pytest.raises(HTTPException) as exc:
        _quiet(el_api.get_obligation_status, token, mode=mode)
    assert exc.value.status_code == code
