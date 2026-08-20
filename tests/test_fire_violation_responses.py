"""
Layer 3 — el_engine.fire_violation_responses().

Wires the last piece of the violation feature: check_live_violations()
(landed earlier this session) detects a Burden past its deadline and
transitions it to 'violated'; this function fires the matching
ViolationResponse, if any, exactly once. Deliberately a separate function
from check_live_violations(), not folded into it — a considered reversal
of an earlier "automatic, same call" recommendation, so detection stays a
pure, poll-safe operation with no response-firing side effects (see
docs/CONCEPTS_INDEX.md).

Idempotency is the core correctness property under test here: a response
must fire exactly once per violation and never again, even after its
created burden is legitimately discharged — 'violated' never reverts, so
checking only 'active' (not 'active OR discharged') would silently re-fire
and grant a duplicate the moment the created burden is discharged.

Minimal inline probe via parse_string(), same throwaway-fixture pattern as
tests/test_check_live_violations.py. sourceBurden is constructed directly
in state 'violated' (via _transition) rather than driven through
check_live_violations() — keeps this test independent of that function's
own deadline-elapsed mechanics, which are already covered elsewhere.
"""
from el_engine import _transition, fire_violation_responses, grant_token, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification FireViolationResponsesProbe

party SourceHolder
party Responder
party EscalationTarget

burden sourceBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden escalationBurden {
    for_action: "respondToEscalation"
    state: active
    deadline: "1 hour"
    discharge_mode: strict
}

violation_response probeViolationResponse {
    on_violation_of: sourceBurden
    obligates: Responder
    response_kind: escalate
    creates_burden: escalationBurden
    escalate_to: EscalationTarget
}
"""


def _build_probe_runtime_with_violation():
    """Parses the probe and returns a Runtime whose sourceBurden is already
    'violated' (held by SourceHolder, granted at tick 0) — the precondition
    fire_violation_responses() actually operates on, built directly rather
    than via check_live_violations()."""
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    rt = Runtime.build_from_spec(spec)

    violated_tok = _transition(
        token_from_spec(spec, "sourceBurden", "SourceHolder", rt.current_state().tick),
        "violated",
    )
    rt._state = grant_token(rt._state, violated_tok)
    return rt


def _token(state, name, holder=None):
    return next(
        t for t in state.tokens
        if t.token_name == name and (holder is None or t.holder == holder)
    )


def test_fires_once_on_violated_burden():
    rt = _build_probe_runtime_with_violation()
    tick = rt.current_state().tick

    new_state, record = fire_violation_responses(rt.current_state(), rt._spec)

    assert record.fired_responses == ("probeViolationResponse",)
    assert record.outcome == "ok"
    assert "granted 'escalationBurden' to 'Responder'" in record.effects[0]
    assert "escalated 'probeViolationResponse' to 'EscalationTarget'" in record.effects[1]

    granted = _token(new_state, "escalationBurden", "Responder")
    assert granted.state == "active"
    assert granted.granted_at_tick == tick
    assert new_state.tick == tick + 1  # a response fired — tick advances


def test_does_not_refire_when_escalation_burden_active():
    rt = _build_probe_runtime_with_violation()

    state1, record1 = fire_violation_responses(rt.current_state(), rt._spec)
    assert record1.fired_responses == ("probeViolationResponse",)

    state2, record2 = fire_violation_responses(state1, rt._spec)

    assert record2.fired_responses == ()
    assert state2.tick == state1.tick  # no-op — tick does not advance
    assert len([t for t in state2.tokens if t.token_name == "escalationBurden"]) == 1


def test_does_not_refire_after_escalation_burden_discharged():
    rt = _build_probe_runtime_with_violation()

    state1, record1 = fire_violation_responses(rt.current_state(), rt._spec)
    assert record1.fired_responses == ("probeViolationResponse",)

    # Simulate notify_gp_of_non_response discharging escalationBurden.
    discharged_tokens = [
        _transition(t, "discharged") if t.token_name == "escalationBurden" else t
        for t in state1.tokens
    ]
    state1_discharged = state1.with_tokens(discharged_tokens)

    state2, record2 = fire_violation_responses(state1_discharged, rt._spec)

    assert record2.fired_responses == ()
    assert state2.tick == state1_discharged.tick  # no-op
    assert len([t for t in state2.tokens if t.token_name == "escalationBurden"]) == 1
    assert _token(state2, "escalationBurden", "Responder").state == "discharged"


def test_no_op_when_no_violation_present():
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    rt = Runtime.build_from_spec(result.model)  # sourceBurden not granted at all

    new_state, record = fire_violation_responses(rt.current_state(), rt._spec)

    assert record.fired_responses == ()
    assert record.outcome == "ok"
    assert new_state.tick == rt.current_state().tick
    assert not any(t.token_name == "escalationBurden" for t in new_state.tokens)


def test_runtime_wrapper_appends_to_ledger():
    rt = _build_probe_runtime_with_violation()

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("probeViolationResponse",)
    assert record in rt._ledger
    assert _token(rt.current_state(), "escalationBurden", "Responder").state == "active"
