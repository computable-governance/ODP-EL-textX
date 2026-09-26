"""
AM-109 — violated worlds are no longer terminal.

Before AM-109 a world reached by T2/T2b was a dead end unless (AM-105) its
edge activated a response-created burden. A dead end makes AF fail, so any
other obligation still PENDING there was reported as failing — the
terminal rule under-reporting (CONCEPTS_INDEX, 7695d1f). The engine
continues after a violation, so now every violated world is expanded below
the horizon like any other; the violated obligation stays VIOLATED.

Directions: AF can only move from "fails" (to holds, "not resolved", or
still fails); EF and "eventually violated" only from false to true. A
bounded response can move from true to false: an obligation that becomes
PENDING only after another obligation's violation has pending worlds the
terminal rule used to cut off — pinned here with a probe.
"""
import contextlib
import io

from el_api import _SCENARIO_BUILDERS
from el_engine import grant_token, token_from_spec
from el_kripke import (
    NOT_RESOLVED_WITHIN_HORIZON,
    RESPONSE_OPERATOR,
    ObligationState,
    build_kripke_from_runtime,
    build_kripke_model,
)
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _violated_worlds(km, oid):
    return [w for w in km.worlds if w.get_obligation(oid) == ObligationState.VIOLATED]


# ── the rule ──────────────────────────────────────────────────────────────

_TWO_BURDENS = """
enterprise specification TwoBurdensProbe

party Holder {
    holds shortBurden
    holds longBurden
}

burden shortBurden { for_action: "doShort" state: active deadline: "1 hour" discharge_mode: eventual }
burden longBurden { for_action: "doLong" state: active deadline: "1 week" discharge_mode: eventual }
commitment CS { by: Holder obligation: "short" creates_burden: shortBurden }
commitment CL { by: Holder obligation: "long" creates_burden: longBurden }
"""


def test_violated_world_continues_and_stays_violated():
    """In both builders: a world below the horizon where shortBurden is
    violated and longBurden still PENDING has successors — longBurden can
    still be discharged there — and shortBurden is VIOLATED in every world
    reachable from it. (A violated world with nothing left PENDING simply
    has no move left, as any such world does.)"""
    model = _quiet(parse_string, _TWO_BURDENS, validate=False).model
    for km in (_quiet(build_kripke_model, model, horizon=10),
               _quiet(build_kripke_from_runtime, _quiet(Runtime.build_from_spec, model), horizon=10)):
        below = [w for w in _violated_worlds(km, "shortBurden")
                 if w.step < km.initial.step + km.horizon
                 and w.get_obligation("longBurden") == ObligationState.PENDING]
        assert below and all(km.successors(w) for w in below)
        for w in below:
            assert all(r.get_obligation("shortBurden") == ObligationState.VIOLATED
                       for r in km.reachable(w))
        assert any(r.get_obligation("longBurden") == ObligationState.DISCHARGED
                   for w in below for r in km.reachable(w))


# ── bounded response: true → false ────────────────────────────────────────

# qBurden (strict, deadline 0 steps) freezes time and T11 while PENDING; it
# is discharged or violated at step 0. Its discharge fires qDone, which
# activates unlockPermit; oBurden (strict, triggered by start) needs that
# permit. Discharged branch: oBurden is triggered and discharged at once.
# Violated branch: before AM-109 a dead end, so oBurden was never PENDING
# there; now oBurden is triggered there but can never be discharged (the
# permit never activates) and the strict freeze allows no tick: a genuine
# dead end below the horizon.
_TRUE_TO_FALSE = """
enterprise specification TrueToFalseProbe

party Holder {
    holds qBurden
    holds oBurden
    holds unlockPermit
}

burden qBurden { for_action: "doQ" state: active deadline: "0 minutes" discharged_by: qDone discharge_mode: strict }
permit unlockPermit { for_action: "doO" state: pending triggered_by: qDone }
burden oBurden { for_action: "doO" state: pending deadline: "1 hour" triggered_by: start discharge_mode: strict }

commitment CQ { by: Holder obligation: "q" creates_burden: qBurden }
commitment CO { by: Holder obligation: "o" creates_burden: oBurden }

community ProbeCommunity {
    objective: "probe a bounded response moving true to false"
    event qDone
    event start
    role r {
        action doQ { emits: qDone }
        action kickoff { emits: start }
        action doO { requires_permit unlockPermit }
    }
}
"""


def test_bounded_response_true_to_false_when_triggered_after_a_violation():
    """Hybrid builder (the static builder tracks no permit state, so an
    event-triggered permit never activates there — CONCEPTS_INDEX,
    "Static builder does not model event-triggered permits"). Before
    AM-109: oBurden's bounded response held (it was PENDING only on the
    discharged branch). Now it fails on the violated branch."""
    model = _quiet(parse_string, _TRUE_TO_FALSE, validate=False).model
    km = _quiet(build_kripke_from_runtime, _quiet(Runtime.build_from_spec, model), horizon=10)
    verdict = km.check_obligation("oBurden")
    assert verdict.modal_operator == RESPONSE_OPERATOR
    assert verdict.satisfied is False and verdict.status is None
    labels = [label for _, label in verdict.counterexample_path]
    assert labels[-3:] == ["violate:qBurden", "fire:start via kickoff",
                           "✗ dead-end — obligation not discharged"]
    last_world = verdict.counterexample_path[-1][0]
    assert last_world.step < km.initial.step + km.horizon


# ── the cases that motivated AM-109 ───────────────────────────────────────

def test_granted_escalation_back_to_af_true():
    """AM-108's flip reverts: with escalationNoticeBurden granted directly in
    the referral runtime, T2b can still violate aiExaminationBurden, but
    that world now continues and the strict escalation is discharged."""
    rt = _quiet(_SCENARIO_BUILDERS["referral"])
    rt._state = grant_token(rt._state, token_from_spec(
        rt._spec, "escalationNoticeBurden", "SpecialistPractice", rt.current_state().tick))
    km = _quiet(build_kripke_from_runtime, rt, horizon=10)
    assert "violate:aiExaminationBurden (episode concluded)" in set(km.labels.values())
    verdict = km.check_obligation("escalationNoticeBurden")
    assert verdict.satisfied is True and verdict.status is None


def test_ereferral_acknowledgement_not_resolved():
    """Its counterexample ended at another obligation's violation, then a
    dead end; now no path fails within the horizon."""
    km = _quiet(build_kripke_from_runtime, _quiet(_SCENARIO_BUILDERS["ereferral"]), horizon=10)
    verdict = km.check_obligation("acknowledgementBurden")
    assert verdict.satisfied is False
    assert verdict.status == NOT_RESOLVED_WITHIN_HORIZON
