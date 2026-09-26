"""
AM-104 part 4 — GET /obligations/{token_name}/status names the property
behind `compelled`.

For a burden with triggered_by, check_obligation() returns the bounded
response verdict (AG(pending→AF), AM-99a), not AF from w0. The response
now carries modal_operator, status and horizon, so a client can tell the
two apart, and can tell "not triggered within horizon" from a real
counterexample.
"""
import contextlib
import importlib
import io

import pytest

from el_parser import parse

import test_public_data_portal_scenario as pdp_tests


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


@pytest.fixture
def api():
    import el_api
    importlib.reload(el_api)
    return el_api


def _portal(api):
    rt = pdp_tests._runtime(_quiet(parse, pdp_tests._SCENARIO).model)
    api._runtime = rt
    return rt


def test_untriggered_burden_reports_af(api):
    api._runtime = _quiet(api._SCENARIO_BUILDERS["referral"])
    resp = _quiet(api.get_obligation_status, "referralResponseBurden")
    assert resp.modal_operator == "AF"
    assert resp.status is None
    assert resp.horizon == api._KRIPKE_HORIZON == 10


def test_triggered_burden_reports_bounded_response(api):
    """incidentNotificationBurden is triggered_by operatorIncidentDetected:
    detectable, not compelled, with a real counterexample."""
    _portal(api)
    resp = _quiet(api.get_obligation_status, "incidentNotificationBurden")
    assert resp.modal_operator == "AG(pending→AF)"
    assert resp.compelled is False
    assert resp.detectable is True
    assert resp.status is None
    assert resp.counterexample_path


def test_discharged_triggered_burden_reports_status(api):
    """Once refusalReviewBurden is discharged it is PENDING in no world:
    compelled is False for lack of evidence, not for a counterexample."""
    rt = _portal(api)
    for action, actor in [("refuseRequest", "AgencyGateway"),
                          ("recordRefusal", "AgencyGateway"),
                          ("reviewRefusal", "AgencySecurityContact")]:
        assert rt.advance(action, actor).outcome == "ok"
    resp = _quiet(api.get_obligation_status, "refusalReviewBurden")
    assert resp.modal_operator == "AG(pending→AF)"
    assert resp.compelled is False
    assert resp.status == "not triggered within horizon"
    assert resp.counterexample_path is None
