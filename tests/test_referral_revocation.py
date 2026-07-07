"""
Layer 4 — integration test for the revocation endpoint, against the
unified referral_scenario.el (candidate reference scenario).

Mirrors tests/test_revocation_endpoint.py's gp_referral-scoped test, but
targets the "referral" scenario via switch_scenario() (the module-level
_runtime singleton defaults to gp_referral on import; must be switched
explicitly). Confirms the same AM-31b guarantee holds under the new
community/federation/episode structure: revoking patientDataAuthorization
supersedes ONLY SpecialistAIAgent's authorization-based permit, leaving
SpecialistClinician's independent role-based permit untouched — and
exercises switch_scenario("referral") itself, which the 2026-07-07
_COMMUNITY_FOR_SCENARIO fix (commit b576c6e) was needed for.

Each test re-imports the API module fresh (rebuilds gp_referral by
default), then explicitly switches to "referral" before asserting.
"""
import importlib

import pytest
from fastapi import HTTPException


@pytest.fixture
def api():
    """Fresh el_api module, switched to the referral scenario."""
    import el_api
    importlib.reload(el_api)
    el_api.switch_scenario("referral")
    return el_api


def _permit_states(runtime):
    return {
        (t.token_name, t.holder): t.state
        for t in runtime.current_state().tokens
        if "patientRecordAccess" in t.token_name
    }


def test_referral_revocation_supersedes_only_authorization_permit(api):
    before = _permit_states(api._runtime)
    assert before[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"
    assert before[("patientRecordAccessPermitByRole", "SpecialistClinician")] == "active"

    resp = api.revoke_authorization_endpoint("patientDataAuthorization")
    assert resp.outcome == "ok"
    assert resp.authority == "Patient"

    after = _permit_states(api._runtime)
    assert after[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "superseded"
    assert after[("patientRecordAccessPermitByRole", "SpecialistClinician")] == "active"


def test_referral_revocation_activates_embargo(api):
    api.revoke_authorization_endpoint("patientDataAuthorization")
    embargo = [
        t for t in api._runtime.current_state().tokens
        if t.token_name == "patientRecordAccessEmbargo"
    ]
    assert embargo, "embargo should exist after revocation"
    assert embargo[0].state == "active"


def test_referral_revoke_unknown_authorization_returns_404(api):
    with pytest.raises(HTTPException) as exc:
        api.revoke_authorization_endpoint("nonexistentAuthorization")
    assert exc.value.status_code == 404
