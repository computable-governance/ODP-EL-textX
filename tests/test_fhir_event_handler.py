"""
Layer 1 -> Layer 3 integration test for FHIR Consent event ingestion.

POST /fhir/consent-events (el_api.py) wraps
fhir_event_handler.handle_consent_event(), which for Consent.status
'inactive' (R31) calls the same Runtime.revoke_authorization() engine
path already exercised by POST /authorizations/{name}/revoke (see
tests/test_referral_revocation.py) — this test locks in that the FHIR
entry point produces the same AM-31/AM-31b guarantees, plus stamps
Consent.id as fhir_provenance. Consent.status 'active' (R30,
2026-08-13) calls Runtime.reinstate_authorization() — this file covers
every shape that call can take: idempotent (permit already active),
fresh grant (permit never previously granted), reinstate after a prior
revoke (permit superseded, embargo active), and blocked (the permit has
expired, or a strict freeze applies) — plus that reinstate
stamps fhir_provenance under the permit token name, mirroring how revoke
stamps it under the embargo token name.

Follows the fixture pattern of tests/test_referral_revocation.py: fresh
el_api import per test, explicitly switched to the "referral" scenario.
"""
import importlib
from dataclasses import replace

import pytest
from fastapi import HTTPException

from el_engine import grant_token, token_from_spec


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
    api._runtime.discharge_burden("referralInitiationBurden")

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


def test_consent_inactive_revocation_blocked_while_strict_burden_outstanding(api):
    """AM-76, documented directly: with referralInitiationBurden
    (discharge_mode: strict, held by GPClinician) still outstanding — the
    referral scenario's normal initial state, before any test-fixture
    discharge — a Consent.status=inactive event must NOT actually revoke
    patientDataAuthorization. Every other test in this file discharges
    the burden in setup to reach the FHIR-specific behavior each one
    actually targets; this is the one test that asserts the guard itself,
    on its own merits, rather than routing around it as a fixture hazard.

    The label is "blocked" (2.5.0-1; before it the handler reported "revoked"
    whether or not the revoke was refused). Ground truth is still resp.outcome,
    the ledger's reason string, and the unchanged token state.
    """
    before = _permit_states(api._runtime)
    assert before[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"

    consent = {"resourceType": "Consent", "id": "consent-blocked", "status": "inactive"}
    resp = api.consent_event(consent)

    assert resp.outcome == "blocked"
    assert resp.action_taken == "blocked"

    ledger_reason = api._runtime._ledger[-1].reason
    assert "referralInitiationBurden" in ledger_reason
    assert "GPClinician" in ledger_reason

    after = _permit_states(api._runtime)
    assert after == before  # nothing changed -- the revoke never actually happened

    embargo = [
        t for t in api._runtime.current_state().tokens
        if t.token_name == "patientRecordAccessEmbargo"
    ]
    assert not embargo, "no embargo should be created when revocation is blocked"


def test_consent_active_when_already_active_is_a_true_no_op(api):
    """Referral scenario grants patientRecordAccessPermitByAuthorization
    active at construction, with no prior revoke — reinstate_authorization()
    finds the permit already active and makes no state change at all
    (mirrors fired_no_match: a real engine call happens, but effects stays
    empty, so handle_consent_event() reports "already_active" rather than
    "reinstated"). No embargo exists yet either, so nothing else to lift.
    A real TransitionRecord still comes back (tick/authority/outcome are
    populated), it just documents that nothing changed."""
    api._runtime.discharge_burden("referralInitiationBurden")

    before = _permit_states(api._runtime)
    assert before[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"

    consent = {"resourceType": "Consent", "id": "consent-002", "status": "active"}
    resp = api.consent_event(consent)

    assert resp.action_taken == "already_active"
    assert resp.fhir_provenance == "consent-002"
    assert resp.outcome == "ok"
    assert resp.authority == "Patient"
    assert resp.authorization_name == "patientDataAuthorization"
    assert resp.effects == []

    after = _permit_states(api._runtime)
    assert after[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"
    assert after[("patientRecordAccessPermitByRole", "SpecialistClinician")] == "active"


def test_consent_active_grants_permit_when_never_previously_granted(api):
    """Simulates a first-time grant (permit never issued at all) by
    stripping the permit TokenInstance before the event — the referral
    scenario builder always grants it at construction, so this is the
    only way to exercise reinstate_authorization()'s fresh-grant branch
    against a real scenario without inventing a new one."""
    api._runtime.discharge_burden("referralInitiationBurden")

    tokens = tuple(
        t for t in api._runtime.current_state().tokens
        if t.token_name != "patientRecordAccessPermitByAuthorization"
    )
    api._runtime._state = api._runtime._state.with_tokens(tokens)
    before = _permit_states(api._runtime)
    assert ("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent") not in before

    consent = {"resourceType": "Consent", "id": "consent-fresh", "status": "active"}
    resp = api.consent_event(consent)

    assert resp.action_taken == "reinstated"
    assert resp.effects == ["activated permit 'patientRecordAccessPermitByAuthorization'"]

    after = _permit_states(api._runtime)
    assert after[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"


def test_consent_active_reinstates_after_revoke_and_lifts_embargo(api):
    """Full revoke-then-reinstate cycle through the FHIR entry point:
    permit superseded + embargo active (post-revoke), then reinstate
    transitions permit -> active and embargo -> lifted, distinct from the
    'superseded' state a Permit gets when an Embargo takes over."""
    api._runtime.discharge_burden("referralInitiationBurden")

    revoke_resp = api.consent_event(
        {"resourceType": "Consent", "id": "consent-revoke", "status": "inactive"}
    )
    assert revoke_resp.action_taken == "revoked"

    mid = _permit_states(api._runtime)
    assert mid[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "superseded"
    embargo_mid = [
        t for t in api._runtime.current_state().tokens
        if t.token_name == "patientRecordAccessEmbargo"
    ]
    assert embargo_mid and embargo_mid[0].state == "active"

    reinstate_resp = api.consent_event(
        {"resourceType": "Consent", "id": "consent-reinstate", "status": "active"}
    )
    assert reinstate_resp.action_taken == "reinstated"
    assert reinstate_resp.effects == [
        "activated permit 'patientRecordAccessPermitByAuthorization'",
        "lifted embargo 'patientRecordAccessEmbargo'",
    ]

    after = _permit_states(api._runtime)
    assert after[("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent")] == "active"
    # Clinician's role-based permit was never touched by either direction.
    assert after[("patientRecordAccessPermitByRole", "SpecialistClinician")] == "active"

    embargo_after = [
        t for t in api._runtime.current_state().tokens
        if t.token_name == "patientRecordAccessEmbargo"
    ]
    assert embargo_after and embargo_after[0].state == "lifted"


# ── 2.5.0-1: an expired permit, and a refused event ──────────────────────────

_AUTH_PERMIT = "patientRecordAccessPermitByAuthorization"
_EXPIRY_REASON = f"permit '{_AUTH_PERMIT}' has expired; only a new grant restores it"


def _seed_permit(api, permit_state):
    """Puts the Authorization's permit in a state only a run can produce."""
    runtime = api._runtime
    runtime._state = runtime._state.with_tokens(tuple(
        replace(t, state=permit_state) if t.token_name == _AUTH_PERMIT else t
        for t in runtime.current_state().tokens
    ))


def _seed_embargo(api, embargo_state):
    runtime = api._runtime
    embargo = token_from_spec(runtime._spec, "patientRecordAccessEmbargo",
                              "SpecialistAIAgent", runtime.current_state().tick)
    runtime._state = grant_token(runtime.current_state(), replace(embargo, state=embargo_state))


def _embargo_states(api):
    return [t.state for t in api._runtime.current_state().tokens
            if t.token_name == "patientRecordAccessEmbargo"]


def test_consent_event_on_an_expired_permit(api):
    """A fresh active Consent does not restore an expired permit: refused, not
    "already_active", and nothing moves."""
    api._runtime.discharge_burden("referralInitiationBurden")
    _seed_permit(api, "expired")
    _seed_embargo(api, "active")
    before = api._runtime.current_state()

    resp = api.consent_event(
        {"resourceType": "Consent", "id": "consent-expired", "status": "active"}
    )

    assert resp.action_taken == "blocked"
    assert resp.outcome == "blocked"
    assert resp.effects == []
    assert _EXPIRY_REASON in resp.message
    assert api._runtime.current_state() == before
    assert api._runtime._ledger[-1].reason == _EXPIRY_REASON
    assert _AUTH_PERMIT not in api._fhir_provenance_by_token


def test_consent_inactive_on_an_expired_permit(api):
    """Nothing to revoke: not a refusal and not "revoked". The state's tick does
    not move and no embargo follows."""
    api._runtime.discharge_burden("referralInitiationBurden")
    _seed_permit(api, "expired")
    before = api._runtime.current_state()
    note = f"revoke '{_AUTH_PERMIT}' had no effect: 'SpecialistAIAgent' holds it expired"

    resp = api.consent_event(
        {"resourceType": "Consent", "id": "consent-expired-off", "status": "inactive"}
    )

    assert resp.action_taken == "already_expired"
    assert resp.outcome == "ok"
    assert resp.effects == [note]
    assert "already expired" in resp.message
    assert note in resp.message
    assert api._runtime.current_state() == before
    assert _embargo_states(api) == []
    assert "patientRecordAccessEmbargo" not in api._fhir_provenance_by_token


@pytest.mark.parametrize("permit_state", ["superseded", "expired"])
def test_consent_active_under_a_strict_freeze_reports_blocked(api, permit_state):
    """The strict guard comes first, so an expired permit gets the strict
    refusal too. Either way the permit is not active, so "already_active"
    would be false."""
    _seed_permit(api, permit_state)
    before = api._runtime.current_state()

    resp = api.consent_event(
        {"resourceType": "Consent", "id": "consent-frozen", "status": "active"}
    )

    assert resp.action_taken == "blocked"
    assert resp.outcome == "blocked"
    assert resp.effects == []
    assert "referralInitiationBurden" in resp.message
    assert "before the authorization can be reinstated" in resp.message
    assert api._runtime.current_state() == before


def test_consent_inactive_under_a_strict_freeze_reports_blocked(api):
    """On an expired permit, too, the strict guard answers first: the strict
    refusal, not "already_expired" and no note line."""
    _seed_permit(api, "expired")
    before = api._runtime.current_state()

    resp = api.consent_event(
        {"resourceType": "Consent", "id": "consent-frozen-off", "status": "inactive"}
    )

    assert resp.action_taken == "blocked"
    assert resp.outcome == "blocked"
    assert resp.effects == []
    assert "referralInitiationBurden" in resp.message
    assert "before the authorization can be revoked" in resp.message
    assert api._runtime.current_state() == before


def test_consent_active_reinstate_stamps_provenance_under_permit_token(api):
    """Mirrors test_consent_inactive_triggers_revocation_with_provenance,
    but for the reverse direction: reinstate stamps fhir_provenance under
    the permit token name, not the embargo — the embargo is what gets
    stamped on revoke, so the two directions must key differently."""
    api._runtime.discharge_burden("referralInitiationBurden")
    api.consent_event({"resourceType": "Consent", "id": "consent-revoke-2", "status": "inactive"})
    assert api._fhir_provenance_by_token["patientRecordAccessEmbargo"] == "consent-revoke-2"

    api.consent_event({"resourceType": "Consent", "id": "consent-reinstate-2", "status": "active"})
    assert api._fhir_provenance_by_token["patientRecordAccessPermitByAuthorization"] == "consent-reinstate-2"
    # The embargo's earlier provenance is untouched by the reinstate stash.
    assert api._fhir_provenance_by_token["patientRecordAccessEmbargo"] == "consent-revoke-2"


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
