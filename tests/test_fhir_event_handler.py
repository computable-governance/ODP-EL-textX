"""
Layer 1 -> Layer 3 integration test for FHIR Consent event ingestion.

POST /fhir/consent-events (el_api.py) wraps
fhir_event_handler.handle_consent_event(), which for Consent.status
'inactive' (R31) calls the same Runtime.revoke_authorization() engine
path already exercised by POST /authorizations/{name}/revoke (see
tests/test_referral_revocation.py) — this test locks in that the FHIR
entry point produces the same AM-31/AM-31b guarantees, plus stamps
Consent.id as fhir_provenance. Consent.status 'active' (R30) is
bootstrap-only per AM-34; this test locks in that it returns an
informative no-op rather than raising or silently doing nothing.

Follows the fixture pattern of tests/test_referral_revocation.py: fresh
el_api import per test, explicitly switched to the "referral" scenario.
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


def test_consent_inactive_triggers_revocation_with_provenance(api):
    before = _permit_states(api._runtime)
    assert before[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"
    assert before[("patientRecordAccessPermitByRole", "SpecialistClinician")] == "active"

    consent = {"resourceType": "Consent", "id": "consent-001", "status": "inactive"}
    resp = api.consent_event(consent)

    assert resp.action_taken == "revoked"
    assert resp.fhir_provenance == "consent-001"
    assert resp.outcome == "ok"
    assert resp.authority == "Patient"
    assert resp.authorization_name == "patientDataAuthorization"

    after = _permit_states(api._runtime)
    # AI agent's authorization-based permit is superseded
    assert after[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "superseded"
    # Clinician's role-based permit is UNTOUCHED — the core AM-31b guarantee,
    # confirmed to hold through the FHIR entry point too.
    assert after[("patientRecordAccessPermitByRole", "SpecialistClinician")] == "active"

    embargo = [
        t for t in api._runtime.current_state().tokens
        if t.token_name == "patientRecordAccessEmbargo"
    ]
    assert embargo, "embargo should exist after revocation"
    assert embargo[0].state == "active"


def test_consent_active_post_bootstrap_is_informative_no_op(api):
    consent = {"resourceType": "Consent", "id": "consent-002", "status": "active"}
    resp = api.consent_event(consent)

    assert resp.action_taken == "no_op"
    assert resp.fhir_provenance == "consent-002"
    assert "no-op" in resp.message
    assert "bootstrap" in resp.message.lower()
    # Revoke-only fields are unset on the no-op path
    assert resp.tick is None
    assert resp.outcome is None

    # No side effect: permit remains untouched
    after = _permit_states(api._runtime)
    assert after[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"


def test_consent_missing_id_returns_400(api):
    with pytest.raises(HTTPException) as exc:
        api.consent_event({"resourceType": "Consent", "status": "inactive"})
    assert exc.value.status_code == 400


def test_consent_missing_status_returns_400(api):
    with pytest.raises(HTTPException) as exc:
        api.consent_event({"resourceType": "Consent", "id": "consent-003"})
    assert exc.value.status_code == 400


def test_consent_unhandled_status_is_no_op(api):
    consent = {"resourceType": "Consent", "id": "consent-004", "status": "draft"}
    resp = api.consent_event(consent)
    assert resp.action_taken == "no_op"
    assert resp.fhir_provenance == "consent-004"


def test_consent_events_unknown_authorization_returns_404(api, monkeypatch):
    # Point the endpoint's known_auths check at a name not declared in the
    # spec, mirroring test_revocation_endpoint.py's unknown-authorization
    # 404 case. The check runs (and raises) before handle_consent_event is
    # ever called, so patching el_api's own module-level name is sufficient.
    monkeypatch.setattr(api, "PATIENT_DATA_AUTHORIZATION", "nonexistentAuthorization")

    with pytest.raises(HTTPException) as exc:
        api.consent_event({"resourceType": "Consent", "id": "consent-005", "status": "inactive"})
    assert exc.value.status_code == 404
