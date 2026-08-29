"""
Layer 3 — el_engine.discharge_burden().

A direct, non-action-based way to discharge a Burden token by name — no
Action, no actor-initiated step. Mirrors revoke_authorization()/
reinstate_authorization()'s established shape (thin Runtime wrapper over
an el_engine function taking (state, spec, name), returning (new_state,
TransitionRecord), KeyError on an undeclared target, _transition() for
the actual state change) — but without the Authorization-style permit/
authority indirection: a Burden's TokenInstance already carries .holder
directly.

Idempotency: mirrors reinstate_authorization()'s real signal (outcome
stays 'ok' throughout; empty `effects` is what distinguishes a no-op from
a real transition — not a distinct outcome value). Discharging an
already-'discharged' burden, or one with no live TokenInstance at all, is
a no-op: effects and discharged both stay empty. tick still advances by 1
regardless (this is a real external call, not check_live_violations'
repeatable poll).

Minimal inline spec via parse_string(), same throwaway-probe pattern as
tests/test_check_live_violations.py.
"""
from el_engine import _transition, discharge_burden
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification DischargeBurdenProbe

party Holder {
    holds targetBurden
    holds otherPermit
}

burden targetBurden {
    state: active
    discharge_mode: eventual
}

permit otherPermit {
    state: active
}
"""


def _build_probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


def _token(state, name):
    return next(t for t in state.tokens if t.token_name == name)


def test_active_burden_transitions_to_discharged():
    rt = _build_probe_runtime()
    state = rt.current_state()
    assert _token(state, "targetBurden").state == "active"

    new_state, record = discharge_burden(state, rt._spec, "targetBurden")

    assert record.outcome == "ok"
    assert record.discharged == ("targetBurden",)
    assert "targetBurden" in record.effects[0]
    assert record.actor_name == "Holder"
    assert record.action_name == "discharge:targetBurden"
    assert _token(new_state, "targetBurden").state == "discharged"
    # Non-mutating on the input WorldState (frozen dataclass, copy-on-write).
    assert _token(state, "targetBurden").state == "active"
    assert new_state.tick == state.tick + 1


def test_unknown_burden_name_raises_key_error():
    rt = _build_probe_runtime()
    state = rt.current_state()
    import pytest
    with pytest.raises(KeyError):
        discharge_burden(state, rt._spec, "nonexistentBurden")


def test_discharging_a_permit_name_raises_key_error():
    """discharge_burden() must reject a validly-declared token that isn't
    a burden — otherwise it would silently discharge a permit or embargo,
    which has no defined meaning."""
    rt = _build_probe_runtime()
    state = rt.current_state()
    import pytest
    with pytest.raises(KeyError):
        discharge_burden(state, rt._spec, "otherPermit")


def test_already_discharged_burden_is_an_idempotent_no_op():
    rt = _build_probe_runtime()
    state = _with_token_state(rt.current_state(), "targetBurden", "discharged")

    new_state, record = discharge_burden(state, rt._spec, "targetBurden")

    assert record.outcome == "ok"
    assert record.discharged == ()
    assert record.effects == ()
    assert _token(new_state, "targetBurden").state == "discharged"
    # tick still advances even on the idempotent no-op — matches revoke/
    # reinstate's unconditional-advance convention, not check_live_violations'
    # poll-safe exception.
    assert new_state.tick == state.tick + 1


def test_burden_with_no_live_instance_is_an_idempotent_no_op():
    """targetBurden is declared in spec but never granted to anyone in
    this state — nothing to discharge. A no-op, not a KeyError: the
    declared-token check already caught the real caller-error case (name
    not declared at all); a declared-but-ungranted burden is safer as a
    silent no-op for an external bridge than a hard failure."""
    rt = _build_probe_runtime()
    state = rt.current_state()
    ungranted_state = state.with_tokens([
        t for t in state.tokens if t.token_name != "targetBurden"
    ])

    new_state, record = discharge_burden(ungranted_state, rt._spec, "targetBurden")

    assert record.outcome == "ok"
    assert record.discharged == ()
    assert record.effects == ()
    assert record.actor_name == "system"
    assert new_state.tick == ungranted_state.tick + 1


def _with_token_state(state, token_name, new_state_str):
    tokens = [
        _transition(t, new_state_str) if t.token_name == token_name else t
        for t in state.tokens
    ]
    return state.with_tokens(tokens)


def test_runtime_wrapper_appends_to_ledger():
    rt = _build_probe_runtime()

    record = rt.discharge_burden("targetBurden")

    assert record.outcome == "ok"
    assert record in rt._ledger
    assert _token(rt.current_state(), "targetBurden").state == "discharged"


def test_runtime_wrapper_idempotent_call_still_appends_a_record():
    rt = _build_probe_runtime()
    rt.discharge_burden("targetBurden")

    record = rt.discharge_burden("targetBurden")

    assert record.outcome == "ok"
    assert record.effects == ()
    assert record in rt._ledger
    assert _token(rt.current_state(), "targetBurden").state == "discharged"
