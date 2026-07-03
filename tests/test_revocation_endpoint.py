"""
Layer 4 — integration test for the revocation endpoint.

POST /authorizations/{authorization_name}/revoke (el_api.py) exposes the
AM-31 engine primitive Runtime.revoke_authorization through the REST API.

This test locks in the AM-31b design intent: revoking patientDataAuthorization
must supersede ONLY the AI agent's authorization-based permit
(patientRecordAccessPermitByAuthorization) and activate its embargo, while
leaving the specialist clinician's independent role-based permit
(patientRecordAccessPermitByRole) untouched. The two permits were
deliberately split (AM-31b) so patient consent withdrawal targets the AI
delegate's access without collaterally revoking the human clinician's
standing role access — a regression here would be clinically wrong, not
just a test failure.

Each test re-imports the API module fresh (the _runtime singleton is rebuilt
at import), so each starts from pristine initial GP-referral state.
"""
import importlib

import pytest
from fastapi import HTTPException


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


def test_revocation_supersedes_only_authorization_permit(api):
    before = _permit_states(api._runtime)
    # Sanity: both permits active before revocation
    assert before[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"
    assert before[("patientRecordAccessPermitByRole", "SpecialistClinician")] == "active"

    resp = api.revoke_authorization_endpoint("patientDataAuthorization")
    assert resp.outcome == "ok"
    assert resp.authority == "PatientParty"

    after = _permit_states(api._runtime)
    # AI agent's authorization-based permit is superseded
    assert after[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "superseded"
    # Clinician's role-based permit is UNTOUCHED — the core AM-31b guarantee
    assert after[("patientRecordAccessPermitByRole", "SpecialistClinician")] == "active"


def test_revocation_activates_embargo(api):
    api.revoke_authorization_endpoint("patientDataAuthorization")
    embargo = [
        t for t in api._runtime.current_state().tokens
        if t.token_name == "patientRecordAccessEmbargo"
    ]
    assert embargo, "embargo should exist after revocation"
    assert embargo[0].state == "active"


def test_revoke_unknown_authorization_returns_404(api):
    with pytest.raises(HTTPException) as exc:
        api.revoke_authorization_endpoint("nonexistentAuthorization")
    assert exc.value.status_code == 404
