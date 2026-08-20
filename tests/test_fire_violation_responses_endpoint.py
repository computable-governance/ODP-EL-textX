"""
Layer 4 — integration test for the violation-response-firing endpoint.

POST /fire-violation-responses (el_api.py) exposes
Runtime.fire_violation_responses() through the REST API, following the same
shape as POST /check-violations: a state-mutating engine call, then a fresh
build_kripke_from_runtime() query for the updated world/objective score/
reachability. Deliberately a separate endpoint from /check-violations, not
folded into it — see tests/test_fire_violation_responses.py's module
docstring and docs/CONCEPTS_INDEX.md for the rationale.

Uses the same throwaway-probe-spec pattern as
tests/test_fire_violation_responses.py, swapped onto api._runtime the same
way tests/test_check_violations_endpoint.py does.
"""
import importlib

import pytest

from el_engine import _transition, grant_token, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification FireViolationResponsesEndpointProbe

party SourceHolder
party Responder
party EscalationTarget

burden sourceBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden escalationBurden {
    for_action: "respondToEscalation"
    state: active
    deadline: "1 hour"
    discharge_mode: strict
}

violation_response probeViolationResponse {
    on_violation_of: sourceBurden
    obligates: Responder
    response_kind: escalate
    creates_burden: escalationBurden
    escalate_to: EscalationTarget
}
"""


@pytest.fixture
def api():
    """Fresh el_api module, _runtime swapped onto the probe spec above, with
    sourceBurden already 'violated'."""
    import el_api
    importlib.reload(el_api)
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    rt = Runtime.build_from_spec(spec)
    violated_tok = _transition(
        token_from_spec(spec, "sourceBurden", "SourceHolder", rt.current_state().tick),
        "violated",
    )
    rt._state = grant_token(rt._state, violated_tok)
    el_api._runtime = rt
    return el_api


def _token(runtime, name, holder=None):
    return next(
        t for t in runtime.current_state().tokens
        if t.token_name == name and (holder is None or t.holder == holder)
    )


def test_fire_violation_responses_fires_once(api):
    resp = api.fire_violation_responses_endpoint()

    assert resp.fired == ["probeViolationResponse"]
    assert any("granted 'escalationBurden' to 'Responder'" in e for e in resp.effects)
    assert any("escalated 'probeViolationResponse' to 'EscalationTarget'" in e for e in resp.effects)
    assert _token(api._runtime, "escalationBurden", "Responder").state == "active"


def test_fire_violation_responses_does_not_refire_when_active(api):
    api.fire_violation_responses_endpoint()
    resp2 = api.fire_violation_responses_endpoint()

    assert resp2.fired == []
    assert len([
        t for t in api._runtime.current_state().tokens
        if t.token_name == "escalationBurden"
    ]) == 1


def test_fire_violation_responses_does_not_refire_after_discharge(api):
    api.fire_violation_responses_endpoint()

    discharged_tokens = [
        _transition(t, "discharged") if t.token_name == "escalationBurden" else t
        for t in api._runtime.current_state().tokens
    ]
    api._runtime._state = api._runtime._state.with_tokens(discharged_tokens)

    resp2 = api.fire_violation_responses_endpoint()

    assert resp2.fired == []
    assert len([
        t for t in api._runtime.current_state().tokens
        if t.token_name == "escalationBurden"
    ]) == 1
    assert _token(api._runtime, "escalationBurden", "Responder").state == "discharged"


def test_fire_violation_responses_no_op_does_not_advance_tick(api):
    # Remove the violation precondition: reset sourceBurden's holder set is
    # already fixed by the fixture, so instead exercise the no-op path via a
    # fresh runtime with no violation granted at all.
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    api._runtime = Runtime.build_from_spec(result.model)
    tick_before = api._runtime.current_state().tick

    resp = api.fire_violation_responses_endpoint()

    assert resp.fired == []
    assert resp.tick == tick_before
    assert api._runtime.current_state().tick == tick_before
