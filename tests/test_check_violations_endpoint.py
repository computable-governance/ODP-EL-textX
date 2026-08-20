"""
Layer 4 — integration test for the violation-check endpoint.

POST /check-violations (el_api.py) exposes Runtime.check_live_violations()
through the REST API, following the same shape as
POST /authorizations/{authorization_name}/revoke and .../reinstate: a
state-mutating engine call, then a fresh build_kripke_from_runtime() query
for the updated world/objective score/reachability.

Uses the same throwaway-probe-spec pattern as
tests/test_check_live_violations.py, swapped onto api._runtime the same way
tests/test_revocation_endpoint.py pins api._runtime to a specific scenario
before asserting — here a self-contained probe rather than gp_referral/
referral, so the elapsed-vs-deadline boundary is exact and doesn't depend
on the real scenarios' pre-seed/holder-resolution quirks (see
docs/CONCEPTS_INDEX.md's double-grant/pre-seed finding).

Each test re-imports the API module fresh (the _runtime singleton is
rebuilt at import), so each starts from pristine state before being pointed
at the probe spec.
"""
import importlib

import pytest

from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification CheckViolationsEndpointProbe

party Holder {
    holds eventualBurden
    holds strictBurden
}

burden eventualBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden strictBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: strict
}

commitment eventualCommitment {
    by: Holder
    obligation: "Discharge the eventual burden"
    creates_burden: eventualBurden
}

commitment strictCommitment {
    by: Holder
    obligation: "Discharge the strict burden"
    creates_burden: strictBurden
}
"""


@pytest.fixture
def api():
    """Fresh el_api module, _runtime swapped onto the probe spec above."""
    import el_api
    importlib.reload(el_api)
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    el_api._runtime = Runtime.build_from_spec(result.model)
    return el_api


def _token(runtime, name):
    return next(t for t in runtime.current_state().tokens if t.token_name == name)


def test_check_violations_reports_nothing_before_deadline(api):
    api._runtime._state = api._runtime._state.with_tick(4)  # elapsed 4 < deadline_steps 5

    resp = api.check_violations_endpoint()

    assert resp.outcome == "ok"
    assert resp.violations == []
    assert _token(api._runtime, "eventualBurden").state == "active"
    # No-op poll must not consume a tick (see el_engine.check_live_violations()).
    assert api._runtime.current_state().tick == 4


def test_check_violations_transitions_eventual_burden_past_deadline(api):
    api._runtime._state = api._runtime._state.with_tick(5)  # elapsed 5 >= deadline_steps 5

    resp = api.check_violations_endpoint()

    assert resp.outcome == "violation"
    assert resp.violations == ["eventualBurden"]
    assert resp.effects and "eventualBurden" in resp.effects[0]
    assert resp.tick == 5
    assert _token(api._runtime, "eventualBurden").state == "violated"
    assert api._runtime.current_state().tick == 6  # a real transition — tick advances


def test_check_violations_never_reports_strict_burden(api):
    api._runtime._state = api._runtime._state.with_tick(1000)  # wildly past any deadline

    resp = api.check_violations_endpoint()

    assert "strictBurden" not in resp.violations
    assert _token(api._runtime, "strictBurden").state == "active"


def test_check_violations_report_shape_matches_revoke_endpoint(api):
    """Same fields as RevokeAuthorizationResponse/ReinstateAuthorizationResponse
    (minus the authorization-specific ones) — updated_world/objective score/
    reachability re-queried the same way, per the endpoint's own docstring."""
    api._runtime._state = api._runtime._state.with_tick(5)

    resp = api.check_violations_endpoint()

    assert isinstance(resp.updated_world, dict)
    assert "step" in resp.updated_world
    assert "obligations" in resp.updated_world
    assert "actors" in resp.updated_world
    assert isinstance(resp.new_objective_score, float)
    assert isinstance(resp.objective_reachable, bool)
