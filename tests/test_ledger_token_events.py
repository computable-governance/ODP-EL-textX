"""
Layer 3 — token events in the ledger.

Each TransitionRecord lists the changes its act made to token instances
(token_events): an instance granted, an instance removed (its holder
changed), or an instance's state changed. A Runtime also has a build
record, outside the ledger, with one 'granted' event per token it started
from (by 'model', cause 'initial'); Runtime.history() returns it before the
ledger.

Pinned here:
  - the build record (one event per initial token, in its initial state;
    the ledger stays empty);
  - completeness: folding every event of history() reproduces the current
    tokens, for the referral and both terms-of-engagement runtimes driven
    through a fixed sequence of acts;
  - no side effects: with event production switched off, every record's
    other fields and every state are the same;
  - blocked records and no-op sweeps carry no events.
"""
import contextlib
import io
from collections import Counter
from dataclasses import replace

import pytest

import el_api
import el_engine
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_PROBE = """
enterprise specification LedgerTokenEventsProbe

party Operator

community ProbeCommunity
    description: "One role, one emitting action"
    {
        objective: "Exercise token events"

        event workStarted
            description: "Fired when startWork runs"

        role operatorRole
            description: "Performs the actions"
            {
                action startWork {
                    description: "Emits workStarted"
                    actor: operatorRole
                    emits: workStarted
                }
            }
    }

burden activeBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden waitingBurden {
    state: pending
    deadline: "1 hour"
    triggered_by: workStarted
    discharge_mode: eventual
}
"""


def _probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    for name in ("activeBurden", "waitingBurden"):
        state = grant_token(state, token_from_spec(spec, name, "Operator", 0))
    return Runtime(state, spec)


def _key(t):
    return (t.token_name, t.kind, t.holder, t.granted_at_tick)


def _fold(history):
    """The instances (key, state) that history()'s events describe."""
    live = Counter()
    for record in history:
        for e in record.token_events:
            key = (e.token_name, e.token_kind, e.holder, e.granted_at_tick)
            if e.from_state is not None:
                assert live[(key, e.from_state)] > 0, e
                live[(key, e.from_state)] -= 1
            if e.to_state is not None:
                live[(key, e.to_state)] += 1
    return +live


def _current(rt):
    return Counter((_key(t), t.state) for t in rt.current_state().tokens)


# ── Build record ──────────────────────────────────────────────────────────────

def test_build_record_lists_initial_grants():
    rt = _probe_runtime()
    build = rt.build_record
    assert (build.actor_name, build.action_name, build.outcome, build.tick) == (
        "model", "build", "ok", 0)
    assert (build.discharged, build.effects, build.violations) == ((), (), ())
    assert [(e.event, e.token_name, e.holder, e.from_state, e.to_state, e.tick, e.by,
             e.cause, e.cause_ref) for e in build.token_events] == [
        ("granted", "activeBurden", "Operator", None, "active", 0, "model", "initial", None),
        ("granted", "waitingBurden", "Operator", None, "pending", 0, "model", "initial", None),
    ]
    assert rt._ledger == []
    assert rt.history() == (build,)


def test_build_from_spec_has_a_build_record():
    rt = _quiet(el_api._build_public_data_portal_runtime)
    assert len(rt.build_record.token_events) == len(rt.current_state().tokens)
    assert all(e.event == "granted" and e.by == "model" for e in rt.build_record.token_events)


def test_history_is_build_record_then_ledger():
    rt = _probe_runtime()
    record = rt.advance("startWork", "Operator")
    assert rt.history() == (rt.build_record, record)
    assert [(e.event, e.token_name, e.from_state, e.to_state, e.by, e.cause, e.cause_ref)
            for e in record.token_events] == [
        ("active", "waitingBurden", "pending", "active", "Operator", "action", "startWork"),
    ]


# ── Completeness ──────────────────────────────────────────────────────────────

_REFERRAL_FACTS = {
    "initiateReferral": {"Patient must have an active episode of care and clinical "
                         "indication for referral": True},
    "provideHandover": {"Referral must be active and acknowledged by specialist": True},
    "scheduleAssessment": {"Referral must be acknowledged and patient availability "
                           "confirmed": True},
    "conductAIExamination": {"Referral must be active for AI examination to proceed": True,
                             "AI agent must hold patientRecordAccessPermitByAuthorization": True},
}


def _drive_referral(rt):
    rt.advance("initiateReferral", "GPClinician", facts=_REFERRAL_FACTS["initiateReferral"])
    rt.revoke_authorization("patientDataAuthorization")
    rt.advance("conductAIExamination", "SpecialistAIAgent",
               facts=_REFERRAL_FACTS["conductAIExamination"])          # refused
    rt.reinstate_authorization("patientDataAuthorization")
    rt.advance("acknowledgeReferral", "SpecialistClinician")
    rt.advance("provideHandover", "GPClinician", facts=_REFERRAL_FACTS["provideHandover"])
    rt.advance("scheduleAssessment", "SpecialistClinician",
               facts=_REFERRAL_FACTS["scheduleAssessment"])
    rt.advance("conductAIExamination", "SpecialistAIAgent",
               facts=_REFERRAL_FACTS["conductAIExamination"])
    rt.check_live_violations()
    rt.advance_clock(30000)
    rt.check_live_violations()
    rt.fire_violation_responses()


_TOE = {
    "external_agent_access": (
        el_api._build_external_agent_access_runtime, "ProviderAPIGateway",
        "ProviderViolationWatchdog", "ProviderSecurityManager", "VendorReferralAgent",
        "submitServiceRequest", ["AgentAccessAuthorization", "PatientLookupAuthorization"]),
    "public_data_portal": (
        el_api._build_public_data_portal_runtime, "AgencyGateway",
        "AgencyViolationWatchdog", "AgencySecurityManager", "ExternalAIAgent",
        "readPublishedDataset", ["DatasetReadAuthorization", "AggregateQueryAuthorization"]),
}


def _drive_terms_of_engagement(name):
    def drive(rt):
        _, gw, dog, mgr, agent, act, auths = _TOE[name]
        rt.advance("refuseRequest", gw)
        rt.advance(act, agent)                                  # refused: frozen
        rt.declare_violation("refusalRecordBurden", dog, at_tick=4)   # refused: early
        rt.declare_violation("refusalRecordBurden", dog, at_tick=5)
        rt.fire_violation_responses()
        rt.fire_violation_responses()                           # no-op
        rt.advance(act, agent)                                  # refused: revoked
        rt.advance("investigateGatewayFailure", mgr)
        for auth in auths:
            rt.reinstate_authorization(auth)
        rt.advance(act, agent)
        rt.advance("recordRefusal", gw)
    return drive


_RUNS = {
    "referral": (el_api._build_referral_runtime, _drive_referral),
    **{name: (spec[0], _drive_terms_of_engagement(name)) for name, spec in _TOE.items()},
}


@pytest.mark.parametrize("name", sorted(_RUNS))
def test_events_reproduce_the_current_tokens(name):
    make, drive = _RUNS[name]
    rt = _quiet(make)
    _quiet(drive, rt)
    assert any(r.token_events for r in rt._ledger)
    assert _fold(rt.history()) == +_current(rt)
    for record in rt._ledger:
        assert all(e.tick == record.tick and e.by == record.actor_name
                   for e in record.token_events)


@pytest.mark.parametrize("name", sorted(_RUNS))
def test_events_change_nothing_else(name, monkeypatch):
    make, drive = _RUNS[name]
    with_events = _quiet(make)
    _quiet(drive, with_events)

    monkeypatch.setattr(el_engine, "_token_events", lambda *args, **kwargs: ())
    without = _quiet(make)
    _quiet(drive, without)

    assert [replace(r, token_events=()) for r in with_events._ledger] == without._ledger
    assert with_events.current_state() == without.current_state()


# ── No events where nothing changed ───────────────────────────────────────────

def test_blocked_records_and_no_op_sweeps_carry_no_events():
    rt = _probe_runtime()
    assert rt.advance("startWork", "Nobody").token_events == ()        # not enrolled
    assert rt.advance("noSuchAction", "Operator").token_events == ()   # nothing changes
    sweep = rt.check_live_violations()
    assert (sweep.outcome, sweep.token_events) == ("ok", ())
    assert rt.fire_violation_responses().token_events == ()
    assert rt.advance_clock(5).token_events == ()
