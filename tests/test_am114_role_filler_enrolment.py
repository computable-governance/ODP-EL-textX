"""
AM-114 part 4 — runtimes enrol role fillers from the specification.

`obj fills role` statements (Community/Federation bodies) are enrolled
through join_role() by Runtime.build_from_spec(), build_from_federation()
and the API builders, so each role's on_join grants apply in their declared
state. The terms-of-engagement API runtimes no longer hand-list their role
fillers or the agent's on_join embargoes; they must start in the same state
as before, now with roles.
"""
import contextlib
import io
from pathlib import Path

import pytest

import el_api
from el_engine import enroll, grant_token, initial_state, role_fillers, token_from_spec
from el_parser import parse, parse_string
from el_runtime import Runtime


_REPO = Path(__file__).resolve().parent.parent
_TOE_DIR = _REPO / "scenarios" / "terms_of_engagement"


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _spec(path):
    result = _quiet(parse, path, validate=False)
    assert result.ok, result.errors
    return result.model


def _token_set(state):
    return sorted((t.token_name, t.kind, t.holder, t.state, t.discharge_mode, t.priority,
                   t.granted_at_tick, t.deadline, t.for_action, t.activated_at_tick)
                  for t in state.tokens)


# The pre-AM-114 construction: five actors without roles, every token hand-granted.
_LEGACY = {
    "public_data_portal": (
        _TOE_DIR / "public_data_portal_scenario.el",
        ["DataAgency", "AgencySecurityContact", "AgencyGateway", "AgentOperator", "ExternalAIAgent"],
        [("refusalRecordBurden", "AgencyGateway"),
         ("refusalReviewBurden", "AgencySecurityContact"),
         ("incidentNotificationBurden", "AgentOperator"),
         ("publishedDatasetReadPermit", "ExternalAIAgent"),
         ("aggregateQueryPermit", "ExternalAIAgent"),
         ("outsideScopeEmbargo", "ExternalAIAgent"),
         ("noCircumventionEmbargo", "ExternalAIAgent")],
        {"AgencySecurityContact": "incidentContactRole", "AgencyGateway": "accessGatewayRole",
         "AgentOperator": "accountablePrincipalRole", "ExternalAIAgent": "externalRequesterRole"},
    ),
    "external_agent_access": (
        _TOE_DIR / "external_agent_access_scenario.el",
        ["ProviderOrg", "ProviderSecurityContact", "ProviderAPIGateway", "VendorOrg", "VendorReferralAgent"],
        [("refusalRecordBurden", "ProviderAPIGateway"),
         ("refusalReviewBurden", "ProviderSecurityContact"),
         ("incidentNotificationBurden", "VendorOrg"),
         ("serviceRequestSubmitPermit", "VendorReferralAgent"),
         ("patientLookupPermit", "VendorReferralAgent"),
         ("outsideScopeEmbargo", "VendorReferralAgent"),
         ("noCircumventionEmbargo", "VendorReferralAgent")],
        {"ProviderSecurityContact": "incidentContactRole", "ProviderAPIGateway": "accessGatewayRole",
         "VendorOrg": "accountablePrincipalRole", "VendorReferralAgent": "externalRequesterRole"},
    ),
}


@pytest.mark.parametrize("name", sorted(_LEGACY))
def test_terms_of_engagement_runtime_starts_as_before_now_with_roles(name):
    path, actors, grants, roles = _LEGACY[name]
    spec = _spec(path)
    legacy = initial_state()
    for actor in actors:
        legacy = enroll(legacy, actor)
    for token, holder in grants:
        legacy = grant_token(legacy, token_from_spec(spec, token, holder, 0))

    state = el_api._SCENARIO_BUILDERS[name]().current_state()

    assert _token_set(state) == _token_set(legacy)
    assert state.tick == legacy.tick == 0
    assert {a.actor_name for a in state.actors} == set(actors)
    assert {a.actor_name: a.role_name for a in state.actors} == {
        actor: roles.get(actor) for actor in actors}


@pytest.mark.parametrize("name", sorted(_LEGACY))
def test_no_circumvention_embargo_stays_pending_until_access_refused(name):
    state = el_api._SCENARIO_BUILDERS[name]().current_state()
    embargo = {t.token_name: t for t in state.tokens if t.kind == "embargo"}
    assert embargo["outsideScopeEmbargo"].state == "active"
    assert embargo["noCircumventionEmbargo"].state == "pending"


_PROBE = """
enterprise specification FillerEnrolmentProbe
agent Worker
party Owner
agent Outsider

permit joinPermit {
    for_action: "work"
    state: active
}

embargo laterEmbargo {
    for_action: "work"
    state: pending
    triggered_by: stop
}

community C {
    objective: "probe"
    event stop
    on_join workerRole transfer joinPermit
    on_join workerRole transfer laterEmbargo
    Worker fills workerRole
    Owner fills ownerRole
    role workerRole { action work { actor: workerRole } }
    role ownerRole { action stopWork { actor: ownerRole emits: stop } }
}
"""


def test_build_from_spec_enrols_fillers_with_roles_and_on_join_grants():
    spec = _quiet(parse_string, _PROBE, validate=False).model
    state = _quiet(Runtime.build_from_spec, spec).current_state()

    assert sorted((a.actor_name, a.role_name) for a in state.actors) == [
        ("Outsider", None), ("Owner", "ownerRole"), ("Worker", "workerRole")]
    tokens = {(t.token_name, t.holder): t.state for t in state.tokens}
    assert tokens == {("joinPermit", "Worker"): "active",
                      ("laterEmbargo", "Worker"): "pending"}


def test_role_fillers_in_declaration_order():
    spec = _quiet(parse_string, _PROBE, validate=False).model
    assert role_fillers(spec) == [("Worker", "workerRole"), ("Owner", "ownerRole")]


def test_build_from_federation_enrols_fillers():
    spec = _quiet(parse_string, _PROBE, validate=False).model
    state = _quiet(Runtime.build_from_federation, spec).current_state()
    assert sorted((a.actor_name, a.role_name) for a in state.actors) == [
        ("Owner", "ownerRole"), ("Worker", "workerRole")]
