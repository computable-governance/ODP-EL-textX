"""
AM-99a (part 1) — static builder counts deadlines from activation.

Pre-existing issue, independent of T11: build_kripke_model()'s Rule T2
compared w.step against deadline_steps directly, i.e. counted every
obligation's deadline from step 0 — including obligations the P6a
cascade only activated (WAITING -> PENDING) at some later step. An
obligation activated at step >= its deadline got a violation edge in
the very world it became PENDING. (The investigation assumed the live
engine already counted from activation; it counted from grant. Fixed on
the engine side by AM-100, TokenInstance.activated_at_tick.)

Fix: World.activation_steps records the step P6a activated each
obligation; T2 counts from there (docs/el_grammar_amendments.md, AM-99a).

Fixture: firstBurden (long deadline, so it can be discharged late)
fires firstDone on discharge; secondBurden is triggered_by firstDone
and has a 5-step deadline ("1 hour"). AM-108: it had no deadline and
relied on the parser's default of 5, which T2 no longer enforces (no
elapsed-time magnitude); "1 hour" gives the same 5 steps.
"""
from el_kripke import ObligationState, build_kripke_model
from el_parser import parse_string


_SPEC = """
enterprise specification DeadlineFromActivationProbe

party Operator

burden firstBurden {
    for_action: "doFirst"
    state: pending
    deadline: "1 week"
    discharged_by: firstDone
    discharge_mode: eventual
}

burden secondBurden {
    for_action: "doSecond"
    state: pending
    deadline: "1 hour"
    triggered_by: firstDone
    discharge_mode: eventual
}

community ProbeCommunity {
    objective: "probe deadline counting from activation"
    event firstDone
}

commitment OperatorDoesFirst {
    by: Operator
    obligation: "do first"
    creates_burden: firstBurden
}

commitment OperatorDoesSecond {
    by: Operator
    obligation: "do second"
    creates_burden: secondBurden
}
"""

_SECOND = "secondBurden"


def _model():
    result = parse_string(_SPEC, validate=False)
    assert result.ok, result.errors
    return build_kripke_model(result.model, horizon=10)


def _violated_successor(km, w):
    return any(
        s.get_obligation(_SECOND) == ObligationState.VIOLATED
        for s in km.successors(w)
    )


def test_second_burden_deadline_is_default_five_steps():
    km = _model()
    assert km.obligation_descriptors[_SECOND].deadline_steps == 5


def test_late_activation_has_no_immediate_violation_edge():
    """secondBurden activated at step >= 5 must not be violatable in the
    same world it became PENDING — its 5 steps start at activation."""
    km = _model()
    late = [
        w for w in km.worlds
        if w.get_obligation(_SECOND) == ObligationState.PENDING
        and dict(w.activation_steps).get(_SECOND) == w.step
        and w.step >= 5
    ]
    assert late, "fixture should reach a late activation within the horizon"
    assert not any(_violated_successor(km, w) for w in late)


def test_violation_still_reachable_deadline_steps_after_activation():
    """The deadline still bites: activated at step k, a violation edge
    exists once step - k >= 5, and never before."""
    km = _model()
    pending = [
        w for w in km.worlds
        if w.get_obligation(_SECOND) == ObligationState.PENDING
        and _SECOND in dict(w.activation_steps)
    ]
    for w in pending:
        elapsed = w.step - dict(w.activation_steps)[_SECOND]
        assert _violated_successor(km, w) == (elapsed >= 5), w
    assert any(_violated_successor(km, w) for w in pending)


def test_obligation_pending_at_w0_is_not_recorded():
    """Obligations PENDING from w0 keep implicit activation step 0 — w0
    carries no activation_steps entries, so existing models are unchanged."""
    km = _model()
    assert km.initial.activation_steps == frozenset()
