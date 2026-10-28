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
  - blocked records and no-op sweeps carry no events;
  - the cause of each kind of change: the create effect, discharge (by
    action, destroy effect, discharged_by event, fire_event(),
    discharge_burden()), any_discharged supersession, transfer and
    delegation reassignment, violation (deadline, date, episode
    conclusion, standing breach, declaration), term end, a response's
    grant and revocations, revocation and reinstatement.
"""
import contextlib
import io
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import el_api
import el_engine
from el_engine import DeadlineClock, enroll, grant_token, initial_state, token_from_spec
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
        ("active", "waitingBurden", "pending", "active", "Operator", "event", "workStarted"),
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


# ── Causes, per site ──────────────────────────────────────────────────────────

def _events(record):
    return [(e.event, e.token_name, e.holder, e.from_state, e.to_state, e.by, e.cause,
             e.cause_ref) for e in record.token_events]


_ACTS = """
enterprise specification LedgerCausesProbe

party Lead
party WorkerA
party WorkerB

community ProbeCommunity
    description: "A lead and two workers"
    {
        objective: "Either worker's task"
            satisfaction: any_discharged(taskGroup)

        event jobDone
            description: "Emitted by the lead"
        event externalDone
            description: "Fired by fire_event() only"

        role leadRole
            description: "The lead"
            {
                action assignJob {
                    description: "Creates jobBurden for each worker"
                    actor: leadRole
                    effect create jobBurden to workerRole
                }
                action closeFile {
                    description: "Discharges fileBurden by a destroy effect"
                    actor: leadRole
                    effect destroy fileBurden
                }
                action finishReport {
                    description: "Discharges reportBurden by for_action"
                    actor: leadRole
                }
                action announceJobDone {
                    description: "Emits jobDone"
                    actor: leadRole
                    emits: jobDone
                }
                action handOver {
                    description: "Transfers handBurden to the workers"
                    actor: leadRole
                    effect transfer handBurden to workerRole
                }
            }

        role workerRole
            description: "A worker"
            {
                action doTaskA {
                    description: "Discharges taskA"
                    actor: workerRole
                }
                action doTaskB {
                    description: "Discharges taskB"
                    actor: workerRole
                }
            }
    }

burden jobBurden {
    state: active
    discharged_by: jobDone
    discharge_mode: eventual
}

burden fileBurden {
    state: active
    discharge_mode: eventual
}

burden reportBurden {
    for_action: "finishReport"
    state: active
    discharge_mode: eventual
}

burden externalBurden {
    state: active
    discharged_by: externalDone
    discharge_mode: eventual
}

burden callBurden {
    state: active
    discharge_mode: eventual
}

burden handBurden {
    state: active
    discharge_mode: eventual
}

burden taskA {
    for_action: "doTaskA"
    state: active
    discharge_mode: eventual
}

burden taskB {
    for_action: "doTaskB"
    state: active
    discharge_mode: eventual
}

token_group taskGroup {
    member: taskA
    member: taskB
}
"""


def _acts_runtime() -> Runtime:
    result = _quiet(parse_string, _ACTS, validate=False)
    assert result.ok, result.errors
    spec = result.model
    state = initial_state()
    state = enroll(state, "Lead", role_name="leadRole")
    state = enroll(state, "WorkerA", role_name="workerRole")
    state = enroll(state, "WorkerB", role_name="workerRole")
    for name, holder in (("fileBurden", "Lead"), ("reportBurden", "Lead"),
                         ("externalBurden", "Lead"), ("callBurden", "Lead"),
                         ("handBurden", "Lead"), ("taskA", "WorkerA"), ("taskB", "WorkerB")):
        state = grant_token(state, token_from_spec(spec, name, holder, 0))
    return Runtime(state, spec)


def test_create_effect_grants_to_each_role_filler():
    rt = _acts_runtime()
    assert _events(rt.advance("assignJob", "Lead")) == [
        ("granted", "jobBurden", "WorkerA", None, "active", "Lead", "action", "assignJob"),
        ("granted", "jobBurden", "WorkerB", None, "active", "Lead", "action", "assignJob"),
    ]


def test_discharge_causes():
    rt = _acts_runtime()
    assert _events(rt.advance("closeFile", "Lead")) == [
        ("discharged", "fileBurden", "Lead", "active", "discharged", "Lead", "action", "closeFile")]
    assert _events(rt.advance("finishReport", "Lead")) == [
        ("discharged", "reportBurden", "Lead", "active", "discharged", "Lead", "action",
         "finishReport")]
    # discharged_by: the lead's event discharges the workers' burdens
    rt.advance("assignJob", "Lead")
    assert _events(rt.advance("announceJobDone", "Lead")) == [
        ("discharged", "jobBurden", "WorkerA", "active", "discharged", "Lead", "event", "jobDone"),
        ("discharged", "jobBurden", "WorkerB", "active", "discharged", "Lead", "event", "jobDone"),
    ]
    assert _events(rt.fire_event("externalDone", source="feed")) == [
        ("discharged", "externalBurden", "Lead", "active", "discharged", "feed", "event",
         "externalDone")]
    assert _events(rt.discharge_burden("callBurden")) == [
        ("discharged", "callBurden", "Lead", "active", "discharged", "Lead", "discharge_call",
         None)]


def test_any_discharged_sibling_is_superseded():
    rt = _acts_runtime()
    assert _events(rt.advance("doTaskA", "WorkerA")) == [
        ("discharged", "taskA", "WorkerA", "active", "discharged", "WorkerA", "action", "doTaskA"),
        ("superseded", "taskB", "WorkerB", "active", "superseded", "WorkerA", "sibling", "taskA"),
    ]


def test_transfer_removes_and_grants():
    rt = _acts_runtime()
    assert _events(rt.advance("handOver", "Lead")) == [
        ("granted", "handBurden", "WorkerA", None, "active", "Lead", "action", "handOver"),
        ("granted", "handBurden", "WorkerB", None, "active", "Lead", "action", "handOver"),
        ("removed", "handBurden", "Lead", "active", None, "Lead", "action", "handOver"),
    ]


_DELEGATION = """
enterprise specification LedgerDelegationProbe

party Delegator {}

party Delegate {
    holds probeBurden
}

burden probeBurden {
    state: active
    discharge_mode: eventual
}

commitment probeCommitment {
    by: Delegator
    obligation: "o"
    creates_burden: probeBurden
}

delegation probeDelegation {
    from: Delegator
    to: Delegate
    obligation: "o"
    transfers_burden: probeBurden
    revocable: true
}
"""


def test_delegation_revocation_moves_the_instance():
    from el_engine import reinstate_delegation, revoke_delegation
    result = _quiet(parse_string, _DELEGATION, validate=False)
    assert result.ok, result.errors
    rt = _quiet(Runtime.build_from_spec, result.model)
    state, record = revoke_delegation(rt.current_state(), rt._spec, "probeDelegation")
    assert _events(record) == [
        ("granted", "probeBurden", "Delegator", None, "active", "Delegator",
         "delegation_revoked", "probeDelegation"),
        ("removed", "probeBurden", "Delegate", "active", None, "Delegator",
         "delegation_revoked", "probeDelegation"),
    ]
    _, record = reinstate_delegation(state, rt._spec, "probeDelegation")
    assert [(e.event, e.holder, e.cause) for e in record.token_events] == [
        ("granted", "Delegate", "delegation_reinstated"),
        ("removed", "Delegator", "delegation_reinstated"),
    ]


# ── Violations ────────────────────────────────────────────────────────────────

_AEST = timezone(timedelta(hours=10))

_DEADLINES = """
enterprise specification LedgerDeadlinesProbe
policy MinimumCover : amount { initial_value: 20000000 AUD }
party Holder { holds durationBurden holds dateBurden holds siblingBurden
               holds episodeBurden holds keptDuty holds datedDuty holds eventDuty }
community C {
    objective: "o"
        satisfaction: all_discharged(episodeGroup)
    event contractTerminated
    Holder fills r
    role r {
        action terminate { actor: r emits: contractTerminated }
        action finishSibling { actor: r }
    }
    lifecycle { terminating { on_objective_achieved: true } }
}
burden durationBurden { state: active deadline: "1 hour" discharge_mode: eventual }
burden dateBurden { state: active deadline: "by 2026-11-30" discharge_mode: eventual }
burden siblingBurden { for_action: "finishSibling" state: active discharge_mode: eventual }
burden episodeBurden { state: active deadline: "referral episode" discharge_mode: eventual }
burden keptDuty { standing keeps: "insurance cover" >= MinimumCover state: active }
burden datedDuty { standing keeps: "insurance cover" >= MinimumCover
                   ends_at: 2026-11-01 state: active }
burden eventDuty { standing keeps: "insurance cover" >= MinimumCover
                   ended_by: contractTerminated state: active }
commitment siblingCommitment { by: Holder obligation: "o" creates_burden: siblingBurden }
commitment episodeCommitment { by: Holder obligation: "o" creates_burden: episodeBurden }
token_group episodeGroup {
    member: siblingBurden
    member: episodeBurden
}
"""


def test_violation_and_term_end_causes():
    result = _quiet(parse_string, _DEADLINES, validate=False)
    assert result.ok, result.errors
    rt = _quiet(Runtime.build_from_spec, result.model, clock=DeadlineClock(utc_offset=_AEST))

    assert _events(rt.advance("terminate", "Holder")) == [
        ("discharged", "eventDuty", "Holder", "active", "discharged", "Holder", "event",
         "contractTerminated")]
    rt.advance("finishSibling", "Holder")
    rt.advance_clock(60)
    record = rt.check_live_violations(as_at=datetime(2026, 12, 1, tzinfo=_AEST),
                                      facts={"insurance cover": "15000000 AUD"})
    assert {e.token_name: (e.event, e.by, e.cause) for e in record.token_events} == {
        "durationBurden": ("violated", "system", "deadline"),
        "dateBurden": ("violated", "system", "date_due"),
        "episodeBurden": ("violated", "system", "episode_concluded"),
        "keptDuty": ("violated", "system", "standing_breach"),
        "datedDuty": ("discharged", "system", "term_end"),
    }


@pytest.mark.parametrize("name", sorted(_TOE))
def test_declaration_response_and_reinstatement_causes(name):
    make, gw, dog, mgr, agent, act, auths = _TOE[name]
    rt = _quiet(make)
    rt.advance("refuseRequest", gw)

    record = rt.declare_violation("refusalRecordBurden", dog, at_tick=5)
    assert _events(record) == [
        ("violated", "refusalRecordBurden", gw, "active", "violated", dog, "declaration",
         "declareRefusalRecordViolation")]

    record = rt.fire_violation_responses()
    by_token = {e.token_name: (e.event, e.holder, e.by, e.cause, e.cause_ref)
                for e in record.token_events}
    permits = [t.token_name for t in rt.current_state().tokens
               if t.kind == "permit" and t.state == "superseded"]
    assert len(permits) == len(auths)
    assert by_token.pop("gatewayInvestigationBurden") == (
        "granted", mgr, "system", "response", "unrecordedRefusalResponse")
    assert sorted(by_token.values()) == sorted(
        ("superseded", agent, "system", "revocation", auth) for auth in auths)

    record = rt.reinstate_authorization(auths[0])
    assert {(e.event, e.token_kind, e.cause, e.cause_ref) for e in record.token_events} == {
        ("lifted", "embargo", "reinstatement", auths[0]),
        ("active", "permit", "reinstatement", auths[0]),
    }


def test_revocation_supersedes_the_permit_and_grants_the_embargo():
    rt = _quiet(el_api._build_referral_runtime)
    rt.advance("initiateReferral", "GPClinician", facts=_REFERRAL_FACTS["initiateReferral"])
    record = rt.revoke_authorization("patientDataAuthorization")
    assert [(e.event, e.token_kind, e.holder, e.by, e.cause, e.cause_ref)
            for e in record.token_events] == [
        ("superseded", "permit", "SpecialistAIAgent", record.actor_name, "revocation",
         "patientDataAuthorization"),
        ("granted", "embargo", "SpecialistAIAgent", record.actor_name, "revocation",
         "patientDataAuthorization"),
    ]


def test_claimed_sibling_lapses_the_other_pool_member():
    rt = _quiet(el_api._build_erequesting_claiming_runtime)
    record = rt.claim("providerAClaimBurden", "DiagnosticProviderA")
    assert _events(record) == [
        ("active", "providerAClaimBurden", "DiagnosticProviderA", "claimable", "active",
         "DiagnosticProviderA", "action", "claimReferralA"),
        ("lapsed", "providerBClaimBurden", "DiagnosticProviderB", "claimable", "lapsed",
         "DiagnosticProviderA", "sibling", "providerAClaimBurden"),
    ]
