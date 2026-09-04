"""
Layer 4 — integration test for the reinstate endpoint.

POST /authorizations/{authorization_name}/reinstate (el_api.py) exposes the
R30 Option B engine primitive Runtime.reinstate_authorization through the
REST API. Direct-call counterpart to POST /fhir/consent-events with
status="active" (see tests/test_fhir_event_handler.py for that path) — same
engine call, no FHIR envelope, and mirrors POST /authorizations/{name}/revoke
in reverse (see tests/test_revocation_endpoint.py, whose structure this file
follows).

ReinstateAuthorizationResponse deliberately has no action_taken discriminator
(unlike ConsentEventResponse): the URL itself fixes the semantic, outcome is
always "ok", and every field is always populated. The already-active vs.
genuinely-reinstated distinction is carried entirely by effects being empty
vs. non-empty — asserted explicitly below.

Each test re-imports the API module fresh (the _runtime singleton is rebuilt
at import), so each starts from pristine initial default-scenario state.
"""
import importlib

import pytest
from fastapi import HTTPException

from el_engine import initial_state
from el_parser import parse_string
from el_runtime import Runtime


@pytest.fixture
def api():
    """Fresh el_api module (rebuilds the _runtime singleton from initial state)."""
    import el_api
    importlib.reload(el_api)
    return el_api


def _permit_states(runtime):
    return {
        (t.token_name, t.holder): t.state
        for t in runtime.current_state().tokens
        if "patientRecordAccess" in t.token_name
    }


def test_reinstate_after_revoke_activates_permit_and_lifts_embargo(api):
    # Pinned to the referral scenario, same as test_referral_revocation.py.
    api.switch_scenario("referral")
    api._runtime.discharge_burden("referralInitiationBurden")

    api.revoke_authorization_endpoint("patientDataAuthorization")
    revoked = _permit_states(api._runtime)
    assert revoked[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "superseded"

    resp = api.reinstate_authorization_endpoint("patientDataAuthorization")
    assert resp.outcome == "ok"
    assert resp.authority == "Patient"
    assert resp.effects  # non-empty: a real transition happened
    assert any("activated permit" in e for e in resp.effects)
    assert any("lifted embargo" in e for e in resp.effects)

    after = _permit_states(api._runtime)
    assert after[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"
    # Clinician's independent role-based permit was never touched by either call
    assert after[("patientRecordAccessPermitByRole", "SpecialistClinician")] == "active"

    embargo = [
        t for t in api._runtime.current_state().tokens
        if t.token_name == "patientRecordAccessEmbargo"
    ]
    assert embargo, "embargo token should still exist after reinstate (lifted, not removed)"
    assert embargo[0].state == "lifted"


def test_reinstate_when_already_active_is_idempotent_with_empty_effects(api):
    api.switch_scenario("referral")
    api._runtime.discharge_burden("referralInitiationBurden")

    # Permit is active from initial scenario construction — no revoke first.
    before = _permit_states(api._runtime)
    assert before[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"

    resp = api.reinstate_authorization_endpoint("patientDataAuthorization")
    assert resp.outcome == "ok"
    assert resp.effects == []  # nothing to change — the empty-vs-non-empty signal

    after = _permit_states(api._runtime)
    assert after[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"


def test_reinstate_unknown_authorization_returns_404(api):
    with pytest.raises(HTTPException) as exc:
        api.reinstate_authorization_endpoint("nonexistentAuthorization")
    assert exc.value.status_code == 404


def test_reinstate_authorization_without_embargo_returns_400(api):
    """An Authorization with no on_revocation embargo is declared but not
    meaningfully reinstatable — same defensive check as revoke's 400 case
    (toolchain/el_api.py's revoke_authorization_endpoint has this same
    check but no test of its own; this covers the shared engine-level
    KeyError path for the new endpoint). Throwaway fixture, mirroring
    tests/test_permit_embargo_governance_resolution.py's pattern: the
    KeyError raises before reinstate_authorization() ever touches
    WorldState.tokens, so no actors/tokens need to be enrolled/granted."""
    src = (
        'enterprise specification Probe\n\n'
        'party Authority\n'
        'agent Agent1\n\n'
        'permit TestPermit {\n'
        '    state: active\n'
        '}\n\n'
        'authorization TestAuth {\n'
        '    authority: Authority\n'
        '    to_agent: Agent1\n'
        '    grants_permit: TestPermit\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    api._runtime = Runtime(initial_state(), result.model)

    with pytest.raises(HTTPException) as exc:
        api.reinstate_authorization_endpoint("TestAuth")
    assert exc.value.status_code == 400
