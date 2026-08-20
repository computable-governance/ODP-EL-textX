"""
Layer 3 — el_engine.check_live_violations().

Closes the live-detection gap logged in docs/CONCEPTS_INDEX.md ("Live
violation triggering — detection mechanism exists and is tested; wiring to
on_violation_of effects is the actual gap", corrected same day 2026-08-20):
before this function, the only deadline→VIOLATED logic anywhere in the
codebase lived inside el_kripke.py's BFS world-expansion, walking the
verifier's own hypothetical `step` counter with no connection to a live
WorldState.tick. check_live_violations() is tick-based (the finding's first
open design question) and an explicit call, not something advance() invokes
automatically (the finding's second open design question).

Also the first test to exercise TransitionRecord.outcome == 'violation' —
documented as a valid value since TransitionRecord's own docstring was
written, but never produced by any code path until now (same finding).

Minimal inline spec via parse_string(), same throwaway-probe pattern as
tests/test_t6_examine_embargo_guard.py / test_v17_burden_embargo_conflict.py.
"deadline: "1 hour"" parses to 5 steps via _parse_deadline_steps — chosen
for a small, exact elapsed-vs-deadline boundary to assert on. Both burdens
are wired through a real Commitment (`by: Holder`), matching Tier 1 of the
two-tier deadline lookup — the same Commitment-derived path
referralResponseBurden/assessmentSchedulingBurden use in the real
scenarios (see docs/CONCEPTS_INDEX.md's double-grant/pre-seed finding for
why that path matters, not just the bare-string fallback).
"""
from el_engine import check_live_violations
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification CheckLiveViolationsProbe

party Holder {
    holds eventualBurden
    holds strictBurden
}

burden eventualBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden strictBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: strict
}

commitment eventualCommitment {
    by: Holder
    obligation: "Discharge the eventual burden"
    creates_burden: eventualBurden
}

commitment strictCommitment {
    by: Holder
    obligation: "Discharge the strict burden"
    creates_burden: strictBurden
}
"""


def _build_probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


def _token(state, name):
    return next(t for t in state.tokens if t.token_name == name)


def test_eventual_burden_stays_active_before_deadline_elapsed():
    rt = _build_probe_runtime()
    state = rt.current_state()
    assert _token(state, "eventualBurden").granted_at_tick == 0

    # deadline_steps == 5 ("1 hour"); elapsed == 4 < 5 — not yet violated.
    almost_due = state.with_tick(4)
    new_state, record = check_live_violations(almost_due, rt._spec)

    assert record.outcome == "ok"
    assert record.violations == ()
    assert _token(new_state, "eventualBurden").state == "active"
    # No-op poll must not consume a tick — see el_engine.check_live_violations()'s
    # docstring: this is a deliberate exception to the "every mutation advances
    # tick unconditionally" convention, specifically to keep repeated polling safe.
    assert new_state.tick == 4


def test_eventual_burden_transitions_to_violated_once_elapsed_reaches_deadline():
    rt = _build_probe_runtime()
    state = rt.current_state()

    # elapsed == 5 == deadline_steps — boundary is inclusive ("elapsed >= deadline").
    exactly_due = state.with_tick(5)
    new_state, record = check_live_violations(exactly_due, rt._spec)

    assert record.outcome == "violation"
    assert record.violations == ("eventualBurden",)
    assert "eventualBurden" in record.effects[0]
    assert _token(new_state, "eventualBurden").state == "violated"
    # Non-mutating on the input WorldState (frozen dataclass, copy-on-write).
    assert _token(state, "eventualBurden").state == "active"
    assert new_state.tick == 6  # a real transition happened — tick DOES advance


def test_strict_burden_never_touched_regardless_of_elapsed_time():
    rt = _build_probe_runtime()
    state = rt.current_state()

    # Wildly past any plausible deadline — must still be skipped entirely.
    way_past_due = state.with_tick(1000)
    new_state, record = check_live_violations(way_past_due, rt._spec)

    assert "strictBurden" not in record.violations
    assert _token(new_state, "strictBurden").state == "active"
    # The eventual sibling, by contrast, does get caught at the same tick —
    # confirms strictBurden's exclusion is discharge_mode-specific, not an
    # accident of the fixture never reaching the deadline check at all.
    assert "eventualBurden" in record.violations


def test_tick_advances_when_a_violation_is_found():
    rt = _build_probe_runtime()
    state = rt.current_state().with_tick(5)
    new_state, _record = check_live_violations(state, rt._spec)
    assert new_state.tick == 6


def test_tick_does_not_advance_on_no_op():
    """The no-op-still-advances precedent (reinstate_authorization()) is
    deliberately NOT followed here — see el_engine.check_live_violations()'s
    docstring. A poll that finds nothing must be free to repeat without
    consuming ticks other live Burdens' deadlines are measured against."""
    rt = _build_probe_runtime()
    state = rt.current_state().with_tick(4)  # elapsed 4 < deadline_steps 5
    new_state, record = check_live_violations(state, rt._spec)
    assert record.outcome == "ok"
    assert new_state.tick == 4


def test_runtime_wrapper_appends_to_ledger():
    rt = _build_probe_runtime()
    rt._state = rt._state.with_tick(5)

    record = rt.check_live_violations()

    assert record.outcome == "violation"
    assert record in rt._ledger
    assert _token(rt.current_state(), "eventualBurden").state == "violated"
