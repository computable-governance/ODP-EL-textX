"""
Layer 3 — el_engine.advance_clock().

AM-48: the "simulate N days pass" primitive the referral demo needs. Every
tick-advancing endpoint before this one advances by at most 1 per call
(execute-action, revoke/reinstate, check-violations, fire-violation-responses
— see docs/CONCEPTS_INDEX.md), so reaching a deadline several ticks out
required either N real actions or N fake no-op calls (e.g. re-reinstating an
already-active authorization) padding the ledger with events that never
really happened. advance_clock() is the honest alternative: pure time
passage, no action semantics, no token mutation of any kind — the only
change it ever makes to WorldState is the tick itself.

Minimal inline probe via parse_string(), same throwaway-fixture pattern as
tests/test_check_live_violations.py / tests/test_fire_violation_responses.py.
One burden is enough here — advance_clock() doesn't inspect tokens at all,
so the fixture only needs to prove nothing about them changes.
"""
from el_engine import advance_clock
from el_parser import parse_string
from el_runtime import Runtime

import pytest


_PROBE = """
enterprise specification AdvanceClockProbe

party Holder {
    holds eventualBurden
}

burden eventualBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

commitment eventualCommitment {
    by: Holder
    obligation: "Discharge the eventual burden"
    creates_burden: eventualBurden
}
"""


def _build_probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


def test_advances_tick_by_exactly_n():
    rt = _build_probe_runtime()
    state = rt.current_state()
    assert state.tick == 0

    new_state, record = advance_clock(state, 8)

    assert new_state.tick == 8
    assert record.tick == 0          # record.tick is the pre-transition tick, same convention as every other engine function
    assert record.outcome == "ok"
    assert record.effects == ("clock advanced 8 tick(s): 0 → 8",)


def test_advances_from_a_nonzero_starting_tick():
    rt = _build_probe_runtime()
    state = rt.current_state().with_tick(3)

    new_state, record = advance_clock(state, 5)

    assert new_state.tick == 8
    assert record.tick == 3
    assert record.effects == ("clock advanced 5 tick(s): 3 → 8",)


def test_touches_no_tokens():
    rt = _build_probe_runtime()
    state = rt.current_state()

    new_state, _record = advance_clock(state, 8)

    assert new_state.tokens == state.tokens
    for before, after in zip(state.tokens, new_state.tokens):
        assert before.state == after.state
        assert before.granted_at_tick == after.granted_at_tick


def test_produces_no_discharge_or_violation():
    rt = _build_probe_runtime()
    state = rt.current_state()

    _new_state, record = advance_clock(state, 8)

    assert record.discharged == ()
    assert record.violations == ()
    assert record.fired_responses == ()


def test_rejects_zero_ticks():
    rt = _build_probe_runtime()
    state = rt.current_state()

    with pytest.raises(ValueError):
        advance_clock(state, 0)


def test_rejects_negative_ticks():
    rt = _build_probe_runtime()
    state = rt.current_state()

    with pytest.raises(ValueError):
        advance_clock(state, -1)


def test_rejecting_invalid_ticks_does_not_mutate_state():
    rt = _build_probe_runtime()
    state = rt.current_state()

    with pytest.raises(ValueError):
        advance_clock(state, 0)

    assert rt.current_state().tick == 0
    assert rt.current_state().tokens == state.tokens


def test_runtime_wrapper_appends_to_ledger():
    rt = _build_probe_runtime()

    record = rt.advance_clock(8)

    assert record.action_name == "advance_clock"
    assert record in rt._ledger
    assert rt.current_state().tick == 8


def test_runtime_wrapper_touches_no_tokens():
    rt = _build_probe_runtime()
    tokens_before = rt.current_state().tokens

    rt.advance_clock(8)

    assert rt.current_state().tokens == tokens_before
