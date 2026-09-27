"""
AM-115 — violation declaration in both terms-of-engagement scenarios.

The replay: the gateway refuses a request and does not record the refusal.
refusalRecordBurden (strict, "5 minutes") freezes the community. Nobody
but the watchdog, filling declarerRole and holding
violationDeclarationPermit, may declare it violated, and not before its
deadline. The declaration ends the freeze; unrecordedRefusalResponse then
revokes the agent's two Authorizations (explicit revokes list) and gives
gatewayInvestigationBurden to the security manager filling
gatewayFailureInvestigatorRole. Reinstatement stays a manual
reinstate_authorization().

Also: both scenarios validate with no warnings ([W-19], [W-20], [W-22]
cleared); the verifier keeps AF for refusalRecordBurden, and the
declaration-created investigation burden never activates in the static
model (the declaration is outside it) but is live in the hybrid model
built after the response fires.
"""
import contextlib
import io

import pytest

import el_api
from el_kripke import ObligationState, build_kripke_from_runtime, build_kripke_model
from el_parser import parse


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


# builder, path, org, gateway, contact, watchdog, manager, agent, operator,
# agent's permitted action, the agent's Authorizations and their permits
_SCENARIOS = {
    "external_agent_access": (
        el_api._build_external_agent_access_runtime, el_api._EXTERNAL_AGENT_ACCESS_SCENARIO,
        "ProviderOrg", "ProviderAPIGateway", "ProviderSecurityContact",
        "ProviderViolationWatchdog", "ProviderSecurityManager",
        "VendorReferralAgent", "VendorOrg", "submitServiceRequest",
        ["AgentAccessAuthorization", "PatientLookupAuthorization"],
        ["serviceRequestSubmitPermit", "patientLookupPermit"],
    ),
    "public_data_portal": (
        el_api._build_public_data_portal_runtime, el_api._PUBLIC_DATA_PORTAL_SCENARIO,
        "DataAgency", "AgencyGateway", "AgencySecurityContact",
        "AgencyViolationWatchdog", "AgencySecurityManager",
        "ExternalAIAgent", "AgentOperator", "readPublishedDataset",
        ["DatasetReadAuthorization", "AggregateQueryAuthorization"],
        ["publishedDatasetReadPermit", "aggregateQueryPermit"],
    ),
}
B = "refusalRecordBurden"


def _states(rt, token):
    return sorted((t.holder, t.state) for t in rt.current_state().tokens if t.token_name == token)


def _refused(name):
    make, _, org, gw, *_ = _SCENARIOS[name]
    rt = _quiet(make)
    assert rt.advance("refuseRequest", gw).outcome == "ok"
    return rt


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_scenarios_validate_without_warnings(name):
    result = _quiet(parse, _SCENARIOS[name][1])
    assert result.ok, result.errors
    assert result.warnings == []


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_freeze_holds_until_an_authorised_declaration(name):
    _, _, org, gw, contact, dog, mgr, agent, operator, act, _, _ = _SCENARIOS[name]
    rt = _refused(name)
    assert _states(rt, B) == [(gw, "active")]
    assert rt.advance(act, agent).outcome == "blocked"
    assert rt.advance_clock(60).outcome == "blocked"
    rt.check_live_violations()
    assert _states(rt, B) == [(gw, "active")]

    for who in (agent, contact, gw, org, mgr, operator):
        rec = rt.declare_violation(B, who, at_tick=100)
        assert rec.outcome == "blocked"
        assert rec.reason.startswith(f"actor '{who}' does not fill role 'declarerRole'")
    assert rt.declare_violation(B, "Nobody", at_tick=100).reason == "actor 'Nobody' is not enrolled"
    rec = rt.declare_violation(B, dog, at_tick=4)
    assert rec.outcome == "blocked"
    assert rec.reason == f"'{B}' is not overdue: 4 of 5 steps elapsed at step 4"
    assert _states(rt, B) == [(gw, "active")]
    assert rt.advance(act, agent).outcome == "blocked"   # still frozen

    rec = rt.declare_violation(B, dog, at_tick=5)
    assert rec.outcome == "violation"
    assert (rec.actor_name, rec.action_name) == (dog, "declareRefusalRecordViolation")
    assert _states(rt, B) == [(gw, "violated")]
    assert rt.advance_clock(60).outcome == "ok"          # freeze lifted
    assert rt.advance("retryByOtherRoute", agent).outcome == "blocked"   # embargo stands


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_response_suspends_access_and_obliges_investigation(name):
    _, _, org, gw, contact, dog, mgr, agent, _, act, auths, permits = _SCENARIOS[name]
    rt = _refused(name)
    rt.declare_violation(B, dog, at_tick=5)
    assert rt.advance(act, agent).outcome == "ok"        # access intact until the response

    rec = rt.fire_violation_responses()
    assert rec.fired_responses == ("unrecordedRefusalResponse",)
    assert rec.effects[:2] == (
        f"fired 'unrecordedRefusalResponse': granted 'gatewayInvestigationBurden' to '{mgr}'",
        f"fired 'unrecordedRefusalResponse' (remediate) on violation of '{B}' by '{gw}'",
    )
    for auth in auths:
        assert f"revoked '{auth}' (to '{agent}')" in rec.effects
    assert _states(rt, "gatewayInvestigationBurden") == [(mgr, "active")]
    for permit in permits:
        assert _states(rt, permit) == [(agent, "superseded")]
    assert _states(rt, "outsideScopeEmbargo") == [(agent, "active")]
    assert rt.advance(act, agent).outcome == "blocked"
    assert rt.fire_violation_responses().fired_responses == ()

    # Investigation, then manual reinstatement (no automatic reinstatement).
    assert rt.advance("investigateGatewayFailure", mgr).outcome == "ok"
    assert _states(rt, "gatewayInvestigationBurden") == [(mgr, "discharged")]
    assert rt.advance(act, agent).outcome == "blocked"
    for auth in auths:
        rt.reinstate_authorization(auth)
    assert rt.advance(act, agent).outcome == "ok"


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_late_record_still_starts_the_review(name):
    _, _, org, gw, contact, dog, *_ = _SCENARIOS[name]
    rt = _refused(name)
    rt.declare_violation(B, dog, at_tick=5)
    rec = rt.advance("recordRefusal", gw)
    assert rec.outcome == "ok" and rec.discharged == ()
    assert _states(rt, B) == [(gw, "violated")]
    assert _states(rt, "refusalReviewBurden") == [(contact, "active")]


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_timely_record_leaves_nothing_to_declare(name):
    _, _, org, gw, contact, dog, *_ = _SCENARIOS[name]
    rt = _refused(name)
    assert rt.advance("recordRefusal", gw).outcome == "ok"
    rec = rt.declare_violation(B, dog, at_tick=100)
    assert rec.outcome == "blocked" and "no active instance (discharged)" in rec.reason


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_watchdog_has_no_available_action(name, monkeypatch):
    dog = _SCENARIOS[name][5]
    monkeypatch.setattr(el_api, "_runtime", _quiet(_SCENARIOS[name][0]))
    assert el_api.get_available_actions(dog).available_actions == []


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_verifier_keeps_af_and_leaves_the_declaration_out(name):
    make, path = _SCENARIOS[name][:2]
    spec = _quiet(parse, path, validate=False).model
    km = _quiet(build_kripke_model, spec, horizon=10, deadline_scale=480)
    assert km.check_obligation(B).satisfied
    assert all(w.obligation_dict().get("gatewayInvestigationBurden") == ObligationState.WAITING
               for w in km.worlds)
    assert not any(label.startswith("exercise:violationDeclarationPermit")
                   for label in km.labels.values())


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_hybrid_after_the_response_has_the_investigation_live(name):
    _, _, org, gw, contact, dog, mgr, *_ = _SCENARIOS[name]
    rt = _refused(name)
    rt.declare_violation(B, dog, at_tick=5)
    rt.fire_violation_responses()
    km = _quiet(build_kripke_from_runtime, rt, horizon=10, deadline_scale=480)
    obligs = km.initial.obligation_dict()
    assert obligs[B] == ObligationState.VIOLATED
    assert obligs["gatewayInvestigationBurden"] == ObligationState.PENDING
    assert km.obligation_descriptors["gatewayInvestigationBurden"].holder == mgr
