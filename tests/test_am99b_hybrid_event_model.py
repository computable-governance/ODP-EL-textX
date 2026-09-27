"""
AM-99b — hybrid mode (build_kripke_from_runtime()) mirrors the live
engine's event model for triggered obligations.

Part 1: w0 seeding and Rule T2.
  - an engine 'pending' burden with triggered_by maps to WAITING, not
    PENDING; one without triggered_by (masked while delegated) stays
    PENDING, as before;
  - every burden PENDING at w0 has its engine activation tick
    (activated_at_tick, else granted_at_tick) seeded into
    w0.activation_steps, and hybrid T2 counts its deadline from there.

Part 2: events inside the hybrid model.
  - Rule T11 fires action-emitted events (strict guard as the engine's
    Step 3.5); AM-113: an emitted discharged_by event discharges its
    burden on the same edge (before, T1 raised it by the P6a cascade);
  - an event also activates pending Permits/Embargoes per world, as the
    engine's Step 7c does, and the T5/T6 embargo guards read that
    per-world state.
  - noCircumventionEmbargo: the verifier does not model retryByOtherRoute
    (no permit, no burden), so it verifies the embargo's state, not the
    blocking itself. Both halves of the claim are tested here: the
    embargo is active in every world reachable after a refusal, and the
    engine blocks retryByOtherRoute while allowing submit and read.

Part 3: gated actions fire their events, in both builders.
  - T5: exercising a permit fires the event its action emits (gated
    actions fire here, not through T11 — engine Step 7c after Step 6);
  - T6: a gated discharge fires its action's emitted event.
  - AM-113: a gated action emitting a burden's discharged_by event
    discharges it (T5), and the burden's own gated for_action does not.

Part 4: the hybrid horizon is relative to the anchored world.
  - worlds are expanded up to step state.tick + horizon; before, a
    runtime at tick >= horizon expanded only w0;
  - KripkeModel.horizon stays relative, and check_response() counts its
    horizon step from initial.step.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_api import _SCENARIO_BUILDERS
from el_engine import _parse_deadline_steps, enroll, grant_token, initial_state, token_from_spec
from el_kripke import (
    NOT_RESOLVED_WITHIN_HORIZON,
    ObligationState,
    build_kripke_from_runtime,
    build_kripke_model,
)
from el_parser import parse, parse_string
from el_runtime import Runtime
from el_api import _build_external_agent_access_runtime as _toe_runtime


_REPO = Path(__file__).resolve().parent.parent
_TOE = _REPO / "scenarios" / "terms_of_engagement" / "external_agent_access_scenario.el"

@pytest.fixture(scope="module")
def toe_spec():
    result = parse(_TOE, validate=False)
    assert result.ok, result.errors
    return result.model


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _obligs(km):
    return dict(km.initial.obligation_states)


# ── w0 seeding ───────────────────────────────────────────────────────────────

def test_no_event_fired_matches_static_w0(toe_spec):
    static = _quiet(build_kripke_model, toe_spec, horizon=10)
    hybrid = _quiet(build_kripke_from_runtime, _toe_runtime(toe_spec), horizon=10)
    assert _obligs(hybrid) == _obligs(static)
    assert set(_obligs(hybrid).values()) == {ObligationState.WAITING}
    assert hybrid.initial.activation_steps == static.initial.activation_steps == frozenset()


def test_untriggered_pending_stays_pending():
    """ereferral's pending burdens have no triggered_by (masked while
    delegated): they keep the PENDING mapping, not WAITING."""
    km = _quiet(build_kripke_from_runtime, _SCENARIO_BUILDERS["ereferral"](), horizon=10)
    for oid in ("acknowledgementBurden", "examinationBurden", "aiExaminationBurden"):
        assert km.initial.get_obligation(oid) == ObligationState.PENDING


def test_activation_tick_seeded_from_engine(toe_spec):
    rt = _toe_runtime(toe_spec)
    rt.advance_clock(7)
    rt.advance("refuseRequest", "ProviderAPIGateway")   # tick 7: activates record
    rt.advance("recordRefusal", "ProviderAPIGateway")   # tick 8: activates review
    km = _quiet(build_kripke_from_runtime, rt, horizon=10)
    obligs = _obligs(km)
    assert obligs["refusalRecordBurden"] == ObligationState.DISCHARGED
    assert obligs["refusalReviewBurden"] == ObligationState.PENDING
    assert obligs["incidentNotificationBurden"] == ObligationState.WAITING
    assert dict(km.initial.activation_steps) == {"refusalReviewBurden": 8}


def test_activation_seed_falls_back_to_grant_tick():
    """Burdens active since grant carry granted_at_tick (0 in every builder)."""
    km = _quiet(build_kripke_from_runtime, _SCENARIO_BUILDERS["referral"](), horizon=10)
    seeds = dict(km.initial.activation_steps)
    pending = {o for o, s in km.initial.obligation_states if s == ObligationState.PENDING}
    assert set(seeds) == pending
    assert set(seeds.values()) == {0}


# ── Rule T2 counts from activation ───────────────────────────────────────────

def test_triggered_burden_violated_no_earlier_than_activation_plus_deadline(toe_spec):
    rt = _toe_runtime(toe_spec)
    rt.advance_clock(7)
    rt.advance("refuseRequest", "ProviderAPIGateway")
    rt.advance("recordRefusal", "ProviderAPIGateway")
    activated = next(t.activated_at_tick for t in rt.current_state().tokens
                     if t.token_name == "refusalReviewBurden")
    deadline = _parse_deadline_steps("1 day")  # AM-111: 1440 steps
    # horizon counts from the runtime's tick since AM-99b part 4: bring the
    # runtime to 4 ticks before activation (8) + deadline, so the deadline
    # falls inside the 10-step horizon.
    rt.advance_clock(activated + deadline - 4 - rt.current_state().tick)
    km = _quiet(build_kripke_from_runtime, rt, horizon=10)
    assert km.obligation_descriptors["refusalReviewBurden"].deadline_steps == deadline
    violation_steps = {
        w.step for (src, w), label in km.labels.items()
        if label == "violate:refusalReviewBurden"
    }
    assert violation_steps, "deadline must still be reachable within horizon"
    assert min(violation_steps) == activated + deadline


# ── Part 2: events inside the hybrid model ───────────────────────────────────

def _after_refusal(spec) -> Runtime:
    rt = _toe_runtime(spec)
    rec = rt.advance("refuseRequest", "ProviderAPIGateway")
    assert rec.outcome == "ok", rec.reason
    return rt


def test_after_refusal_w0_mirrors_engine(toe_spec):
    km = _quiet(build_kripke_from_runtime, _after_refusal(toe_spec), horizon=10)
    obligs = _obligs(km)
    assert obligs["refusalRecordBurden"] == ObligationState.PENDING
    assert obligs["refusalReviewBurden"] == ObligationState.WAITING
    assert obligs["incidentNotificationBurden"] == ObligationState.WAITING
    assert km.initial.embargo_dict()["noCircumventionEmbargo"] == "active"


def test_after_refusal_response_verdicts_match_static(toe_spec):
    # AM-111: the review's "1 day" is 1440 steps, beyond horizon 10, so the
    # record/review comparison runs at the scenario's configured k (480;
    # review 3 steps). At k = 1 static says "not resolved" for the review
    # and hybrid fails via the same cycle as the notification below.
    static_k = _quiet(build_kripke_model, toe_spec, horizon=10, deadline_scale=480)
    hybrid_k = _quiet(build_kripke_from_runtime, _after_refusal(toe_spec), horizon=10,
                      deadline_scale=480)
    for oid in ("refusalRecordBurden", "refusalReviewBurden"):
        h, s_ = hybrid_k.check_response(oid), static_k.check_obligation(oid)
        assert (h.satisfied, h.status) == (s_.satisfied, s_.status), oid
    assert hybrid_k.check_response("refusalRecordBurden").satisfied is True

    static = _quiet(build_kripke_model, toe_spec, horizon=10)
    hybrid = _quiet(build_kripke_from_runtime, _after_refusal(toe_spec), horizon=10)

    # AM-109: incidentNotificationBurden no longer matches, pinned here.
    # Static: "not resolved within horizon" — its only counterexample used
    # to end at another obligation's violation (the terminal rule), and its
    # own deadline (4320 steps since AM-111) is beyond the horizon. Hybrid: fails, via a
    # revoke/reinstate cycle on AgentAccessAuthorization (T7/T8, which only
    # the hybrid builder has) that defers the notification forever. Before
    # AM-109 both said "fails", for different reasons. notifyIncident needs
    # no permit, so the discharge stays enabled through the cycle: weak
    # fairness (accepted in AM-103) would exclude it — see CONCEPTS_INDEX,
    # "Institutional-act cycles as AF counterexamples".
    s_ = static.check_obligation("incidentNotificationBurden")
    assert (s_.satisfied, s_.status) == (False, NOT_RESOLVED_WITHIN_HORIZON)
    h = hybrid.check_response("incidentNotificationBurden")
    assert (h.satisfied, h.status) == (False, None)
    labels = [label for _, label in h.counterexample_path]
    assert labels[-1].startswith("↺ cycle")
    assert any(label.startswith("revoke:AgentAccessAuthorization") for label in labels)
    assert any(label.startswith("reinstate:AgentAccessAuthorization") for label in labels)


def test_no_circumvention_embargo_active_in_every_reachable_world(toe_spec):
    """Verifier half: once refused, no reachable world lifts the embargo."""
    km = _quiet(build_kripke_from_runtime, _after_refusal(toe_spec), horizon=10)
    reachable = km.reachable(km.initial)
    assert len(reachable) > 1
    assert all(w.embargo_dict().get("noCircumventionEmbargo") == "active"
               for w in reachable)


def test_engine_blocks_only_retry_after_refusal(toe_spec):
    """Engine half: retryByOtherRoute is blocked; the legitimate actions
    stay open (the refusal is recorded first, since the strict
    refusalRecordBurden blocks every no-progress action until then)."""
    rt = _after_refusal(toe_spec)
    assert rt.advance("recordRefusal", "ProviderAPIGateway").outcome == "ok"
    retry = rt.advance("retryByOtherRoute", "VendorReferralAgent")
    assert retry.outcome == "blocked"
    assert "noCircumventionEmbargo" in retry.reason
    assert rt.advance("submitServiceRequest", "VendorReferralAgent").outcome == "ok"
    assert rt.advance("readPatientDemographics", "VendorReferralAgent").outcome == "ok"


def test_t11_fires_refusal_from_fresh_runtime(toe_spec):
    km = _quiet(build_kripke_from_runtime, _toe_runtime(toe_spec), horizon=10)
    fired = [w for w in km.successors(km.initial)
             if km.labels[(km.initial, w)] == "fire:accessRefused via refuseRequest"]
    assert len(fired) == 1
    w = fired[0]
    assert w.get_obligation("refusalRecordBurden") == ObligationState.PENDING
    assert dict(w.activation_steps)["refusalRecordBurden"] == km.initial.step
    assert w.embargo_dict()["noCircumventionEmbargo"] == "active"
    assert w.has_occurred("refuseRequest")


def test_t11_suppressed_while_strict_burden_actionable(toe_spec):
    """refusalRecordBurden (strict) is PENDING with an ACTIVE holder at
    w0, so detectIncident may not fire yet — engine Step 3.5 parity."""
    km = _quiet(build_kripke_from_runtime, _after_refusal(toe_spec), horizon=10)
    labels = {km.labels[(km.initial, w)] for w in km.successors(km.initial)}
    assert not any(l.startswith("fire:") for l in labels)
    assert "discharge:refusalRecordBurden via recordRefusal (refusalRecorded)" in labels


def test_event_discharge_activates_dependent(toe_spec):
    """AM-113: recordRefusal emitting refusalRecorded discharges
    refusalRecordBurden and activates refusalReviewBurden on one edge
    (before, T1's P6a cascade raised the event on the discharge)."""
    km = _quiet(build_kripke_from_runtime, _after_refusal(toe_spec), horizon=10)
    (w,) = [w for w in km.successors(km.initial)
            if km.labels[(km.initial, w)].startswith("discharge:refusalRecordBurden")]
    assert w.get_obligation("refusalReviewBurden") == ObligationState.PENDING
    assert dict(w.activation_steps)["refusalReviewBurden"] == km.initial.step


_EMBARGO_PROBE = """
enterprise specification EventEmbargoProbe

party Operator
agent Requester

permit readPermit {
    for_action: "readData"
    state: active
}

embargo lockEmbargo {
    for_action: "readData"
    state: pending
    triggered_by: lockdown
}

community ProbeCommunity {
    objective: "probe an event-activated embargo"
    event lockdown

    role requesterRole {
        action readData {
            actor: requesterRole
            inhibited_by_embargo lockEmbargo
        }
    }
    role operatorRole {
        action declareLockdown {
            actor: operatorRole
            emits: lockdown
        }
    }
}
"""


def test_event_activated_embargo_blocks_exercise_per_world():
    """T5's guard reads the per-world embargo state: after T11 activates
    lockEmbargo, readData can no longer be exercised in that world."""
    result = parse_string(_EMBARGO_PROBE, validate=False)
    assert result.ok, result.errors
    spec = result.model
    state = initial_state()
    # AM-114: each actor fills the role whose actions it performs.
    for actor, role in (("Operator", "operatorRole"), ("Requester", "requesterRole")):
        state = enroll(state, actor, role_name=role)
    for token in ("readPermit", "lockEmbargo"):
        state = grant_token(state, token_from_spec(spec, token, "Requester", 0))
    km = _quiet(build_kripke_from_runtime, Runtime(state, spec), horizon=5)

    def labels_from(w):
        return {km.labels[(w, s)] for s in km.successors(w)}

    assert "exercise:readPermit → readData" in labels_from(km.initial)
    (locked,) = [w for w in km.successors(km.initial)
                 if km.labels[(km.initial, w)] == "fire:lockdown via declareLockdown"]
    assert locked.embargo_dict()["lockEmbargo"] == "active"
    assert not any(l.startswith("exercise:") for l in labels_from(locked))


# ── Part 3: gated actions fire their events (T5/T6), both builders ──────────

_GATED_EMITS_PROBE = """
enterprise specification GatedEmitsProbe

agent Worker {
    holds submitPermit
    holds examinePermit
    holds closePermit
}

permit submitPermit {
    for_action: "submitForm"
    state: active
}

permit examinePermit {
    for_action: "examineCase"
    state: active
}

permit closePermit {
    for_action: "closeCase"
    state: active
}

burden followUpBurden {
    for_action: "followUp"
    state: pending
    triggered_by: formSubmitted
    discharge_mode: eventual
}

burden examineBurden {
    for_action: "examineCase"
    state: active
    discharged_by: caseClosed
    discharge_mode: eventual
}

burden reportBurden {
    for_action: "writeReport"
    state: pending
    triggered_by: caseExamined
    discharge_mode: eventual
}

burden archiveBurden {
    for_action: "archiveCase"
    state: pending
    triggered_by: caseClosed
    discharge_mode: eventual
}

community ProbeCommunity {
    objective: "probe events emitted by gated actions"
    event formSubmitted
    event caseExamined
    event caseClosed

    role workerRole {
        action submitForm {
            actor: workerRole
            requires_permit submitPermit
            emits: formSubmitted
        }
        action examineCase {
            actor: workerRole
            requires_permit examinePermit
            emits: caseExamined
        }
        action closeCase {
            actor: workerRole
            requires_permit closePermit
            emits: caseClosed
        }
    }
}

commitment WorkerFollowsUp {
    by: Worker
    obligation: "follow up a submitted form"
    creates_burden: followUpBurden
}

commitment WorkerExamines {
    by: Worker
    obligation: "examine the case"
    creates_burden: examineBurden
}

commitment WorkerReports {
    by: Worker
    obligation: "report on an examined case"
    creates_burden: reportBurden
}

commitment WorkerArchives {
    by: Worker
    obligation: "archive a closed case"
    creates_burden: archiveBurden
}
"""

_GATED_GRANTS = ["submitPermit", "examinePermit", "closePermit", "followUpBurden",
                 "examineBurden", "reportBurden", "archiveBurden"]


@pytest.fixture(scope="module")
def gated_spec():
    result = parse_string(_GATED_EMITS_PROBE, validate=False)
    assert result.ok, result.errors
    return result.model


def _gated_models(spec):
    state = enroll(initial_state(), "Worker", role_name="workerRole")  # AM-114
    for token in _GATED_GRANTS:
        state = grant_token(state, token_from_spec(spec, token, "Worker", 0))
    return {
        "static": _quiet(build_kripke_model, spec, horizon=5),
        "hybrid": _quiet(build_kripke_from_runtime, Runtime(state, spec), horizon=5),
    }


def _successor(km, label):
    (w,) = [s for s in km.successors(km.initial) if km.labels[(km.initial, s)] == label]
    return w


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_gated_action_events_start_waiting(gated_spec, builder):
    km = _gated_models(gated_spec)[builder]
    for oid in ("followUpBurden", "reportBurden", "archiveBurden"):
        assert km.initial.get_obligation(oid) == ObligationState.WAITING, oid
    assert not any(l.startswith("fire:") for l in km.labels.values())


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_t5_exercise_fires_gated_action_event(gated_spec, builder):
    km = _gated_models(gated_spec)[builder]
    w = _successor(km, "exercise:submitPermit → submitForm")
    assert w.get_obligation("followUpBurden") == ObligationState.PENDING
    assert dict(w.activation_steps)["followUpBurden"] == km.initial.step
    assert w.has_occurred("submitForm")


# T6 needs a gated burden without discharged_by (AM-113: examineBurden
# above is discharged only by caseClosed); a separate fixture keeps the
# gated one small.
_T6_PROBE = """
enterprise specification GatedT6Probe

agent Worker {
    holds reviewPermit
}

permit reviewPermit {
    for_action: "reviewCase"
    state: active
}

burden reviewBurden {
    for_action: "reviewCase"
    state: active
    discharge_mode: eventual
}

burden filingBurden {
    for_action: "fileReview"
    state: pending
    triggered_by: caseReviewed
    discharge_mode: eventual
}

burden followUpBurden {
    for_action: "followUp"
    state: pending
    triggered_by: caseFiled
    discharge_mode: eventual
}

community ProbeCommunity {
    objective: "probe a gated discharge firing its action's event"
    event caseReviewed
    event caseFiled

    role workerRole {
        action reviewCase {
            actor: workerRole
            requires_permit reviewPermit
            emits: caseReviewed
        }
    }
}

commitment WorkerReviews {
    by: Worker
    obligation: "review the case"
    creates_burden: reviewBurden
}

commitment WorkerFiles {
    by: Worker
    obligation: "file a reviewed case"
    creates_burden: filingBurden
}

commitment WorkerFollowsUp {
    by: Worker
    obligation: "follow up a filed case"
    creates_burden: followUpBurden
}
"""


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_t6_examine_fires_emits(builder):
    spec = parse_string(_T6_PROBE, validate=False).model
    state = enroll(initial_state(), "Worker", role_name="workerRole")  # AM-114
    for token in ("reviewPermit", "reviewBurden", "filingBurden", "followUpBurden"):
        state = grant_token(state, token_from_spec(spec, token, "Worker", 0))
    km = (_quiet(build_kripke_model, spec, horizon=5) if builder == "static"
          else _quiet(build_kripke_from_runtime, Runtime(state, spec), horizon=5))
    w = _successor(km, "examine:reviewBurden → reviewCase")
    assert w.get_obligation("reviewBurden") == ObligationState.DISCHARGED
    assert w.get_obligation("filingBurden") == ObligationState.PENDING    # emits
    assert w.get_obligation("followUpBurden") == ObligationState.WAITING  # untouched


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_for_action_alone_does_not_discharge_event_bound_burden(gated_spec, builder):
    """AM-113: examineBurden declares discharged_by caseClosed, so its
    for_action examineCase no longer discharges it: no T6 edge, and
    exercising examineCase only fires caseExamined."""
    km = _gated_models(gated_spec)[builder]
    assert not any(l.startswith("examine:examineBurden") for l in km.labels.values())
    w = _successor(km, "exercise:examinePermit → examineCase")
    assert w.get_obligation("examineBurden") == ObligationState.PENDING
    assert w.get_obligation("reportBurden") == ObligationState.PENDING    # emits
    assert w.get_obligation("archiveBurden") == ObligationState.WAITING


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_gated_emitter_discharges_by_event(gated_spec, builder):
    """AM-113: closeCase (gated) emits caseClosed, examineBurden's
    discharged_by: exercising it discharges examineBurden and activates
    archiveBurden (triggered_by caseClosed) on the same edge."""
    km = _gated_models(gated_spec)[builder]
    w = _successor(km, "exercise:closePermit → closeCase")
    assert w.get_obligation("examineBurden") == ObligationState.DISCHARGED
    assert w.get_obligation("archiveBurden") == ObligationState.PENDING
    assert w.has_occurred("closeCase")


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_gated_event_burdens_reachable(gated_spec, builder):
    km = _gated_models(gated_spec)[builder]
    for oid in ("followUpBurden", "reportBurden", "archiveBurden", "examineBurden"):
        assert km.check_permission(oid).satisfied is True, oid


# ── Part 4: relative hybrid horizon ──────────────────────────────────────────

def _shape(km):
    """World count, edge count and the multiset of edge labels."""
    labels = sorted(km.labels.values())
    return len(km.worlds), sum(len(v) for v in km.edges.values()), labels


def test_horizon_is_relative_to_runtime_tick(toe_spec):
    """Only clock ticks separate the two runtimes and nothing is PENDING
    yet, so the models differ only by a step offset."""
    fresh = _toe_runtime(toe_spec)
    later = _toe_runtime(toe_spec)
    later.advance_clock(12)
    km0 = _quiet(build_kripke_from_runtime, fresh, horizon=10)
    km12 = _quiet(build_kripke_from_runtime, later, horizon=10)
    assert km12.initial.step == 12
    assert km12.horizon == km0.horizon == 10
    assert _shape(km12) == _shape(km0)
    assert max(w.step for w in km12.worlds) == 22


def test_response_verdicts_past_absolute_horizon_match_static(toe_spec):
    """A refusal at tick 12 (past the old absolute bound of 10) still
    gets real verdicts, not 'not resolved within horizon'."""
    rt = _toe_runtime(toe_spec)
    rt.advance_clock(12)
    assert rt.advance("refuseRequest", "ProviderAPIGateway").outcome == "ok"
    static = _quiet(build_kripke_model, toe_spec, horizon=10)
    hybrid = _quiet(build_kripke_from_runtime, rt, horizon=10)
    for oid in ("refusalRecordBurden", "refusalReviewBurden", "incidentNotificationBurden"):
        h, s_ = hybrid.check_response(oid), static.check_obligation(oid)
        assert h.status is None, oid
        assert h.satisfied == s_.satisfied, oid
