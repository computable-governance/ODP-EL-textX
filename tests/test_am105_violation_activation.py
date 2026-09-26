"""
AM-105 — a burden a ViolationResponse creates waits on the violation.

Both builders: the created burden starts WAITING (KripkeModel.
violation_activation) and the T2 edge that violates the burden it waits on
makes it PENDING, deadline counted from there; its verdict is the bounded
response property. A violated world is enqueued only when its T2 edge
activated such a burden; every other violated world stays terminal.

Pins escalationNoticeBurden's corrected verdict in both referral scenarios
and both builders: "not triggered within horizon" (referralResponseBurden's
40-step deadline is beyond horizon 10), where the static model used to
report AF true.
"""
import contextlib
import io

import pytest

from el_api import _SCENARIO_BUILDERS
from el_engine import _transition, enroll, grant_token, initial_state, token_from_spec
from el_kripke import (
    NOT_TRIGGERED_WITHIN_HORIZON,
    RESPONSE_OPERATOR,
    ObligationState,
    build_kripke_from_runtime,
    build_kripke_model,
)
from el_parser import parse, parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _w0_state(km, oid):
    return dict(km.initial.obligation_states).get(oid)


def _assert_not_triggered(km, oid):
    verdict = km.check_obligation(oid)
    assert verdict.modal_operator == RESPONSE_OPERATOR
    assert verdict.satisfied is False
    assert verdict.status == NOT_TRIGGERED_WITHIN_HORIZON
    assert km.check_permission(oid).satisfied is False


_REFERRAL = {
    "referral": "scenarios/referral/referral_scenario.el",
    "gp_referral": "scenarios/gp_referral/gp_referral_scenario.el",
}


@pytest.mark.parametrize("name", sorted(_REFERRAL))
def test_escalation_notice_static_verdict(name):
    km = _quiet(build_kripke_model, _quiet(parse, _REFERRAL[name], validate=False).model, horizon=10)
    assert km.violation_activation == {"escalationNoticeBurden": ("referralResponseBurden",)}
    assert _w0_state(km, "escalationNoticeBurden") == ObligationState.WAITING
    _assert_not_triggered(km, "escalationNoticeBurden")


@pytest.mark.parametrize("name", sorted(_REFERRAL))
def test_escalation_notice_hybrid_verdict_matches_static(name):
    """Hybrid parity: not yet granted, so seeded WAITING on the live
    referralResponseBurden, with the same verdict as the static model."""
    km = _quiet(build_kripke_from_runtime, _quiet(_SCENARIO_BUILDERS[name]), horizon=10)
    assert _w0_state(km, "escalationNoticeBurden") == ObligationState.WAITING
    _assert_not_triggered(km, "escalationNoticeBurden")


def test_hybrid_does_not_index_a_granted_created_burden():
    """Once the response has fired, the created burden is an ordinary live
    token: not seeded, not in violation_activation."""
    rt = _quiet(_SCENARIO_BUILDERS["referral"])
    rt._state = grant_token(rt._state, token_from_spec(
        rt._spec, "escalationNoticeBurden", "SpecialistPractice", rt.current_state().tick))
    km = _quiet(build_kripke_from_runtime, rt, horizon=10)
    assert km.violation_activation == {}
    assert _w0_state(km, "escalationNoticeBurden") == ObligationState.PENDING


_PROBE = """
enterprise specification ViolationActivationProbe

party Clinic
party Practice
party GP

burden answerBurden { for_action: "answer" state: active deadline: "1 hour" discharge_mode: eventual }
burden noticeBurden { for_action: "notify" state: active deadline: "1 hour" discharge_mode: strict }

commitment ClinicAnswers { by: Clinic obligation: "answer" creates_burden: answerBurden }

violation_response lateAnswer {
    on_violation_of: answerBurden
    obligates: Practice
    response_kind: escalate
    creates_burden: noticeBurden
    escalate_to: GP
}
"""


# The same, plus an unrelated obligation whose violation activates nothing.
_PROBE_OTHER = _PROBE + """
burden otherBurden { for_action: "other" state: active deadline: "1 hour" discharge_mode: eventual }
commitment ClinicOther { by: Clinic obligation: "other" creates_burden: otherBurden }
"""


def _probe(src=_PROBE):
    result = _quiet(parse_string, src, validate=False)
    assert result.ok, result.errors
    return result.model


def _violation_edges(km, oid):
    return [(w, s) for (w, s), label in km.labels.items() if label.startswith(f"violate:{oid}")]


def test_static_t2_activates_and_continues():
    """The violation of answerBurden activates noticeBurden on the same
    edge (activation step = that step) and the violated world continues
    below the horizon; noticeBurden is then discharged on every path."""
    km = _quiet(build_kripke_model, _probe(), horizon=10)
    assert km.violation_activation == {"noticeBurden": ("answerBurden",)}
    assert _w0_state(km, "noticeBurden") == ObligationState.WAITING

    edges = _violation_edges(km, "answerBurden")
    assert edges
    for _, s in edges:
        assert dict(s.obligation_states)["noticeBurden"] == ObligationState.PENDING
        assert dict(s.activation_steps)["noticeBurden"] == s.step
        if s.step < km.horizon:
            assert km.successors(s)

    verdict = km.check_obligation("noticeBurden")
    assert verdict.modal_operator == RESPONSE_OPERATOR
    assert verdict.satisfied is True
    assert km.check_permission("noticeBurden").satisfied is True


def test_static_other_violations_stay_terminal():
    """A violation that activates nothing stays terminal, even with a
    response-created burden PENDING: that path is a dead end, so the
    bounded response fails there (violation ends the path, pre-AM-105
    semantics kept). EF still holds."""
    km = _quiet(build_kripke_model, _probe(_PROBE_OTHER), horizon=10)
    other_edges = _violation_edges(km, "otherBurden")
    assert other_edges
    assert all(not km.successors(s) for _, s in other_edges)

    verdict = km.check_obligation("noticeBurden")
    assert verdict.satisfied is False
    assert verdict.status is None
    final_world, final_label = verdict.counterexample_path[-1]
    assert dict(final_world.obligation_states)["otherBurden"] == ObligationState.VIOLATED
    assert dict(final_world.obligation_states)["noticeBurden"] == ObligationState.PENDING
    assert "dead-end" in final_label
    assert km.check_permission("noticeBurden").satisfied is True


def _probe_runtime(answer_state=None):
    spec = _probe()
    state = initial_state()
    for actor in ("Clinic", "Practice", "GP"):
        state = enroll(state, actor)
    answer = token_from_spec(spec, "answerBurden", "Clinic", 0)
    if answer_state:
        answer = _transition(answer, answer_state)
    state = grant_token(state, answer)
    return Runtime(state, spec)


def test_hybrid_t2_activates_like_static():
    km = _quiet(build_kripke_from_runtime, _probe_runtime(), horizon=10)
    assert km.violation_activation == {"noticeBurden": ("answerBurden",)}
    assert _w0_state(km, "noticeBurden") == ObligationState.WAITING
    for _, s in _violation_edges(km, "answerBurden"):
        assert dict(s.obligation_states)["noticeBurden"] == ObligationState.PENDING
        if s.step < km.initial.step + km.horizon:
            assert km.successors(s)
    verdict = km.check_obligation("noticeBurden")
    assert verdict.modal_operator == RESPONSE_OPERATOR
    assert verdict.satisfied is True


def test_hybrid_seeds_pending_when_already_violated():
    """Violated but the response not yet fired: the created burden is
    PENDING at w0, activated at the runtime's tick."""
    km = _quiet(build_kripke_from_runtime, _probe_runtime("violated"), horizon=10)
    assert _w0_state(km, "noticeBurden") == ObligationState.PENDING
    assert dict(km.initial.activation_steps)["noticeBurden"] == km.initial.step
    assert km.check_obligation("noticeBurden").satisfied is True


_LINK_PROBE = """
enterprise specification ViolationActivationLinkProbe

party Clinic
party Practice

burden sourceA { for_action: "a" state: active deadline: "1 hour" discharge_mode: eventual }
burden sourceB { for_action: "b" state: active deadline: "1 hour" discharge_mode: eventual }
burden sharedBurden { for_action: "shared" state: active deadline: "1 hour" discharge_mode: eventual }
burden triggeredBurden {
    for_action: "triggered"
    state: pending
    deadline: "1 hour"
    triggered_by: someEvent
    discharge_mode: eventual
}
burden committedBurden { for_action: "committed" state: active deadline: "1 hour" discharge_mode: eventual }

commitment CA { by: Clinic obligation: "a" creates_burden: sourceA }
commitment CB { by: Clinic obligation: "b" creates_burden: sourceB }
commitment CC { by: Practice obligation: "committed" creates_burden: committedBurden }

community C {
    objective: "probe"
    event someEvent
    role r {
        action emitSome { emits: someEvent }
    }
}

violation_response rA1 { on_violation_of: sourceA obligates: Practice response_kind: escalate creates_burden: sharedBurden }
violation_response rB1 { on_violation_of: sourceB obligates: Practice response_kind: escalate creates_burden: sharedBurden }
violation_response rA2 { on_violation_of: sourceA obligates: Practice response_kind: remediate creates_burden: triggeredBurden }
violation_response rA3 { on_violation_of: sourceA obligates: Practice response_kind: remediate creates_burden: committedBurden }
"""


def test_index_links_only_response_only_untriggered_burdens():
    """Several creating responses list every violated burden; a created
    burden with its own triggered_by, or with another root (here a
    Commitment), is not linked."""
    result = _quiet(parse_string, _LINK_PROBE, validate=False)
    assert result.ok, result.errors
    km = _quiet(build_kripke_model, result.model, horizon=4)
    assert km.violation_activation == {"sharedBurden": ("sourceA", "sourceB")}
    assert _w0_state(km, "committedBurden") == ObligationState.PENDING
