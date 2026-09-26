"""
AM-104 — violation responses that act: response_kind read by the engine.

fire_violation_responses() now fires every ViolationResponse, with or
without creates_burden, once per violated token instance (marker:
WorldState.responded). escalate/remediate/penalise add a ledger line
(and grant creates_burden if set); terminate also revokes the violator
chain's Authorizations whose authority is the response's obligates, via
_apply_revocation(), which skips revoke_authorization()'s strict guard.

Covers: DN_019 step 2.10b (terminate) and the missed-review case
(escalate) in both terms-of-engagement scenarios; terminate during a
strict freeze; the authority-mismatch no-op; re-firing on a re-granted
instance. The creates_burden path is covered by
tests/test_fire_violation_responses.py, unchanged.
"""
import contextlib
import io

import pytest

from el_engine import (
    _parse_deadline_steps,
    _transition,
    fire_violation_responses,
    grant_token,
    token_from_spec,
)
from el_parser import parse, parse_string
from el_runtime import Runtime

import test_am99b_hybrid_event_model as toe_tests
import test_public_data_portal_scenario as pdp_tests


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


# (runtime factory, agent, operator, contact, gateway, agent's read action,
#  Authorizations to the agent, their permits)
_SCENARIOS = {
    "public_data_portal": (
        lambda: pdp_tests._runtime(_quiet(parse, pdp_tests._SCENARIO).model),
        "ExternalAIAgent", "AgentOperator", "AgencySecurityContact", "AgencyGateway",
        "readPublishedDataset",
        ["DatasetReadAuthorization", "AggregateQueryAuthorization"],
        ["publishedDatasetReadPermit", "aggregateQueryPermit"],
    ),
    "external_agent_access": (
        lambda: toe_tests._toe_runtime(_quiet(parse, toe_tests._TOE, validate=False).model),
        "VendorReferralAgent", "VendorOrg", "ProviderSecurityContact", "ProviderAPIGateway",
        "readPatientDemographics",
        ["AgentAccessAuthorization", "PatientLookupAuthorization"],
        ["serviceRequestSubmitPermit", "patientLookupPermit"],
    ),
}


def _states(rt, holder):
    return {t.token_name: t.state for t in rt.current_state().tokens if t.holder == holder}


def _violate(rt, deadline):
    rt.advance_clock(_parse_deadline_steps(deadline))
    return rt.check_live_violations()


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_late_notification_terminates_agent_access(name):
    """DN_019 step 2.10b: the operator stays silent past 72 hours; the
    terminate response revokes both of its agent's Authorizations."""
    make, agent, operator, contact, gateway, read, auths, permits = _SCENARIOS[name]
    rt = make()
    for action, actor in [("refuseRequest", gateway), ("recordRefusal", gateway),
                          ("reviewRefusal", contact), ("detectIncident", operator)]:
        assert rt.advance(action, actor).outcome == "ok"
    assert _violate(rt, "72 hours").violations == ("incidentNotificationBurden",)
    assert rt.advance(read, agent).outcome == "ok"

    tick = rt.current_state().tick
    record = rt.fire_violation_responses()

    assert record.fired_responses == ("lateNotificationResponse",)
    assert record.effects[0] == (
        f"fired 'lateNotificationResponse' (terminate) on violation of "
        f"'incidentNotificationBurden' by '{operator}'"
    )
    for auth in auths:
        assert f"revoked '{auth}' (to '{agent}')" in record.effects
    assert rt.current_state().tick == tick + 1
    held = _states(rt, agent)
    assert all(held[p] == "superseded" for p in permits)
    assert held["outsideScopeEmbargo"] == "active"

    blocked = rt.advance(read, agent)
    assert blocked.outcome == "blocked"
    assert "not held" in blocked.reason

    again = rt.fire_violation_responses()
    assert again.fired_responses == ()
    assert again.effects == ()
    assert rt.current_state().tick == tick + 1
    assert rt.current_state().responded == frozenset({
        ("lateNotificationResponse", "incidentNotificationBurden", operator, 0),
    })


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_missed_review_escalates_without_creates_burden(name):
    """escalate with no creates_burden fires as a ledger entry only: no
    token changes, and the agent keeps its access."""
    make, agent, operator, contact, gateway, read, auths, permits = _SCENARIOS[name]
    rt = make()
    rt.advance("refuseRequest", gateway)
    rt.advance("recordRefusal", gateway)
    assert _violate(rt, "1 day").violations == ("refusalReviewBurden",)
    tokens_before = rt.current_state().tokens

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("missedReviewResponse",)
    assert record.effects == (
        f"fired 'missedReviewResponse' (escalate) on violation of "
        f"'refusalReviewBurden' by '{contact}'",
        f"escalated 'missedReviewResponse' to '{contact}'",
    )
    assert rt.current_state().tokens == tokens_before
    assert rt.advance(read, agent).outcome == "ok"
    assert rt.fire_violation_responses().fired_responses == ()


def test_terminate_revokes_during_strict_freeze():
    """A response is an institutional act: terminate revokes while a strict
    burden is actionable, where a direct revoke_authorization() is still
    refused and Step 3.5 still blocks the agent's ordinary actions."""
    rt = _SCENARIOS["public_data_portal"][0]()
    rt.advance("detectIncident", "AgentOperator")
    assert _violate(rt, "72 hours").violations == ("incidentNotificationBurden",)
    assert rt.advance("refuseRequest", "AgencyGateway").outcome == "ok"
    assert _states(rt, "AgencyGateway")["refusalRecordBurden"] == "active"

    direct = rt.revoke_authorization("DatasetReadAuthorization")
    assert direct.outcome == "blocked"
    assert "refusalRecordBurden" in direct.reason

    record = rt.fire_violation_responses()
    assert record.fired_responses == ("lateNotificationResponse",)
    assert "revoked 'DatasetReadAuthorization' (to 'ExternalAIAgent')" in record.effects
    assert _states(rt, "ExternalAIAgent")["publishedDatasetReadPermit"] == "superseded"

    frozen = rt.advance("readPublishedDataset", "ExternalAIAgent")
    assert frozen.outcome == "blocked"
    assert "strict burden 'refusalRecordBurden'" in frozen.reason

    assert rt.advance("recordRefusal", "AgencyGateway").outcome == "ok"
    after = rt.advance("readPublishedDataset", "ExternalAIAgent")
    assert after.outcome == "blocked"
    assert "not held" in after.reason


_PROBE = """
enterprise specification TerminateProbe

party Agency
party OtherAuthority
party Operator
{
    principal_of Bot
}
agent Bot
{
    delegated_from Operator
}

permit ownPermit { for_action: "readOwn" state: active }
permit foreignPermit { for_action: "readForeign" state: active }
embargo cutOffEmbargo { for_action: "readAnything" state: pending }

burden noticeBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

authorization OwnAuthorization {
    authority: Agency
    to_agent: Bot
    grants_permit: ownPermit
    revocable: true
    on_revocation: activate cutOffEmbargo
}

authorization ForeignAuthorization {
    authority: OtherAuthority
    to_agent: Bot
    grants_permit: foreignPermit
    revocable: true
    on_revocation: activate cutOffEmbargo
}

violation_response terminateResponse {
    on_violation_of: noticeBurden
    obligates: Agency
    response_kind: terminate
}
"""


def _probe_state():
    result = _quiet(parse_string, _PROBE, validate=False)
    assert result.ok, result.errors
    spec = result.model
    rt = Runtime.build_from_spec(spec)
    state = rt.current_state()
    for permit in ("ownPermit", "foreignPermit"):
        state = grant_token(state, token_from_spec(spec, permit, "Bot", 0))
    state = grant_token(state, _transition(
        token_from_spec(spec, "noticeBurden", "Operator", 0), "violated"))
    return state, spec


def _permit_state(state, name):
    return next(t.state for t in state.tokens if t.token_name == name)


def test_terminate_skips_authorization_of_another_authority():
    """obligates must be the Authorization's authority: a mismatch is a
    ledger note, not a revocation, and the response still counts as fired."""
    state, spec = _probe_state()

    new_state, record = fire_violation_responses(state, spec)

    assert record.fired_responses == ("terminateResponse",)
    assert "revoked 'OwnAuthorization' (to 'Bot')" in record.effects
    assert ("not revoked 'ForeignAuthorization': authority is 'OtherAuthority', "
            "not 'Agency'") in record.effects
    assert _permit_state(new_state, "ownPermit") == "superseded"
    assert _permit_state(new_state, "foreignPermit") == "active"


def test_refires_on_regranted_violated_instance():
    """The marker is per violated instance: a new instance (new
    granted_at_tick) of the violated burden fires the response again; the
    already-revoked Authorization is then logged, not revoked twice."""
    state, spec = _probe_state()
    state, first = fire_violation_responses(state, spec)
    assert first.fired_responses == ("terminateResponse",)
    assert fire_violation_responses(state, spec)[1].fired_responses == ()

    regranted = _transition(
        token_from_spec(spec, "noticeBurden", "Operator", state.tick), "violated")
    state = grant_token(state, regranted)

    state, second = fire_violation_responses(state, spec)
    assert second.fired_responses == ("terminateResponse",)
    assert "not revoked 'OwnAuthorization': permit 'ownPermit' is not active" in second.effects
    assert state.responded == frozenset({
        ("terminateResponse", "noticeBurden", "Operator", 0),
        ("terminateResponse", "noticeBurden", "Operator", regranted.granted_at_tick),
    })
    assert fire_violation_responses(state, spec)[1].fired_responses == ()
