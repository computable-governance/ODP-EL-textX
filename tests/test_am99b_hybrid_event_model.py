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
    Step 3.5), and T1 runs the P6a cascade on a discharge event;
  - an event also activates pending Permits/Embargoes per world, as the
    engine's Step 7c does, and the T5/T6 embargo guards read that
    per-world state.
  - noCircumventionEmbargo: the verifier does not model retryByOtherRoute
    (no permit, no burden), so it verifies the embargo's state, not the
    blocking itself. Both halves of the claim are tested here: the
    embargo is active in every world reachable after a refusal, and the
    engine blocks retryByOtherRoute while allowing submit and read.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_api import _SCENARIO_BUILDERS
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_kripke import ObligationState, build_kripke_from_runtime, build_kripke_model
from el_parser import parse, parse_string
from el_runtime import Runtime


_REPO = Path(__file__).resolve().parent.parent
_TOE = _REPO / "scenarios" / "terms_of_engagement" / "external_agent_access_scenario.el"

# Holders follow the scenario's Commitment/Delegation chains and on_join
# transfers; build_from_spec() enrols none of these (no `holds` in bodies).
_TOE_ACTORS = ["ProviderOrg", "ProviderSecurityContact", "ProviderAPIGateway",
               "VendorOrg", "VendorReferralAgent"]
_TOE_GRANTS = [
    ("refusalRecordBurden", "ProviderAPIGateway"),
    ("refusalReviewBurden", "ProviderSecurityContact"),
    ("incidentNotificationBurden", "VendorOrg"),
    ("serviceRequestSubmitPermit", "VendorReferralAgent"),
    ("patientLookupPermit", "VendorReferralAgent"),
    ("outsideScopeEmbargo", "VendorReferralAgent"),
    ("noCircumventionEmbargo", "VendorReferralAgent"),
]


@pytest.fixture(scope="module")
def toe_spec():
    result = parse(_TOE, validate=False)
    assert result.ok, result.errors
    return result.model


def _toe_runtime(spec) -> Runtime:
    state = initial_state()
    for actor in _TOE_ACTORS:
        state = enroll(state, actor)
    for token, holder in _TOE_GRANTS:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    return Runtime(state, spec)


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
    km = _quiet(build_kripke_from_runtime, rt, horizon=30)
    deadline = km.obligation_descriptors["refusalReviewBurden"].deadline_steps
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
    static = _quiet(build_kripke_model, toe_spec, horizon=10)
    hybrid = _quiet(build_kripke_from_runtime, _after_refusal(toe_spec), horizon=10)
    for oid in ("refusalRecordBurden", "refusalReviewBurden", "incidentNotificationBurden"):
        h, s_ = hybrid.check_response(oid), static.check_obligation(oid)
        assert (h.satisfied, h.status) == (s_.satisfied, s_.status), oid
    assert hybrid.check_response("refusalRecordBurden").satisfied is True


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
    assert "discharge:refusalRecordBurden by ProviderAPIGateway" in labels


def test_t1_p6a_discharge_activates_dependent(toe_spec):
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
    for actor in ("Operator", "Requester"):
        state = enroll(state, actor)
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
