"""
2.1.0-6 — the deadline convention, and a date shape has no duration
magnitude.

Convention: a burden deadline is one duration counted from activation —
the first firing of its `triggered_by` event, an `activate` effect, or
else the grant — measured on the tick, one step per minute. "N days after
event E" is a burden with `state: pending`, `triggered_by: E` and
`deadline: "N days"`. Most tests here pin behaviour that already held.

The change: a deadline containing a calendar date (YYYY-MM-DD) is never
read as a duration. Before 2.1.0-6, "by 2026-11-30 end of day" paired the
30 in the date with the word "day" and was enforced as 30 days after
activation, in the engine and in both Kripke builders, with no warning.
It is no longer enforced as 30 days; engine and verifier change together
because the verifier takes the engine's predicate
(docs/ENGINE_VERIFIER_PARITY.md, row R5).

Layer 3 (runtime) and Layer 4 (verifier) tests per tests/README.md.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_engine import (
    _has_deadline_magnitude, _parse_deadline_steps, enroll, grant_token,
    initial_state, token_from_spec,
)
from el_kripke import _build_enforceable_deadlines
from el_parser import parse, parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_DAY = 1440   # steps: one step is one minute

_PROBE = """
enterprise specification ConventionProbe

party Holder

community C {
    objective: "probe"
    event started
    Holder fills holderRole
    role holderRole {
        action openFollowUp { actor: holderRole effect activate followUpBurden }
    }
}

burden afterEvent {
    for_action: "respond"
    state: pending
    deadline: "21 days"
    triggered_by: started
    discharge_mode: eventual
}

burden followUpBurden {
    state: pending
    deadline: "2 days"
    discharge_mode: eventual
}

burden fromGrant {
    state: active
    deadline: "1 day"
    discharge_mode: eventual
}

burden dateEndOfDay {
    state: active
    deadline: "by 2026-11-30 end of day"
    discharge_mode: eventual
}
"""


def _runtime(*tokens):
    spec = _quiet(parse_string, _PROBE, validate=False).model
    state = enroll(initial_state(spec), "Holder", role_name="holderRole")
    for name in tokens:
        state = grant_token(state, token_from_spec(spec, name, "Holder", 0))
    return Runtime(state, spec)


def _token(rt, name):
    return next(t for t in rt.current_state().tokens if t.token_name == name)


def _clock_to(rt, tick):
    if tick > rt.current_state().tick:
        assert _quiet(rt.advance_clock, tick - rt.current_state().tick).outcome == "ok"
    assert rt.current_state().tick == tick


def _violated_at(rt, name, tick):
    _clock_to(rt, tick)
    _quiet(rt.check_live_violations)
    return _token(rt, name).state == "violated"


# ── The convention (already held; pinned) ───────────────────────────────

def test_duration_after_event_counts_from_the_firing():
    rt = _runtime("afterEvent")
    _clock_to(rt, 100)
    _quiet(rt.fire_event, "started")
    fired = _token(rt, "afterEvent").activated_at_tick
    assert fired == 100
    assert not _violated_at(rt, "afterEvent", fired + 21 * _DAY - 1)
    assert _violated_at(rt, "afterEvent", fired + 21 * _DAY)


def test_repeated_event_does_not_re_anchor():
    rt = _runtime("afterEvent")
    _quiet(rt.fire_event, "started")
    first = _token(rt, "afterEvent").activated_at_tick
    _clock_to(rt, 500)
    _quiet(rt.fire_event, "started")
    assert _token(rt, "afterEvent").activated_at_tick == first


def test_activate_effect_anchors_the_deadline():
    rt = _runtime("followUpBurden")
    _clock_to(rt, 50)
    assert _quiet(rt.advance, "openFollowUp", "Holder").outcome == "ok"
    anchored = _token(rt, "followUpBurden").activated_at_tick
    assert anchored == 50
    assert not _violated_at(rt, "followUpBurden", anchored + 2 * _DAY - 1)
    assert _violated_at(rt, "followUpBurden", anchored + 2 * _DAY)


def test_without_a_trigger_the_deadline_counts_from_the_grant():
    rt = _runtime("fromGrant")
    assert not _violated_at(rt, "fromGrant", _DAY - 1)
    assert _violated_at(rt, "fromGrant", _DAY)


@pytest.mark.parametrize("deadline, steps", [
    ("30 days", 30 * _DAY), ("48 hours", 2880), ("5 working days", 7 * _DAY),
    ("2 weeks", 14 * _DAY), ("1 year", 365 * _DAY), ("15 minutes", 15),
])
def test_durations_keep_their_magnitude_and_steps(deadline, steps):
    assert _has_deadline_magnitude(deadline)
    assert _parse_deadline_steps(deadline) == steps


# ── The change: a date shape has no duration magnitude ──────────────────

_DATE_SHAPES = [
    "by 2026-11-30",
    "2026-11-30",
    "by 2026-11-30 end of day",            # was 30 days
    "2026-11-30 (30 days)",                # was 30 days
    "within 5 days of 2026-11-30",         # was 5 days
    "2026-11-30T17:00+10:00",
    "before 2026-12-01 at 17:00",
]


@pytest.mark.parametrize("deadline", _DATE_SHAPES)
def test_date_shape_has_no_magnitude(deadline):
    assert not _has_deadline_magnitude(deadline)


@pytest.mark.parametrize("deadline", ["ref 20261130 within 2 days", "case 12345, 3 days"])
def test_digit_runs_that_are_not_dates_are_unchanged(deadline):
    assert _has_deadline_magnitude(deadline)


def test_date_shapes_are_not_enforceable_in_the_verifier():
    src = "enterprise specification Dates\n" + "\n".join(
        f'burden b{i} {{ state: active deadline: "{d}" discharge_mode: eventual }}'
        for i, d in enumerate(_DATE_SHAPES)
    ) + '\nburden duration { state: active deadline: "30 days" discharge_mode: eventual }\n'
    model = _quiet(parse_string, src, validate=False).model
    assert _build_enforceable_deadlines(model) == frozenset({"duration"})


def test_end_of_day_date_is_no_longer_enforced_as_30_days():
    # Before 2.1.0-6 this burden was violated at tick 43200 (30 days).
    rt = _runtime("dateEndOfDay")
    assert not _violated_at(rt, "dateEndOfDay", 30 * _DAY)
    assert not _violated_at(rt, "dateEndOfDay", 400 * _DAY)


def test_no_shipped_scenario_burden_deadline_has_a_date_shape():
    # So the change cannot alter any shipped scenario's enforceable deadlines.
    from el_engine import _DATE_SHAPE_RE
    root = Path(__file__).resolve().parent.parent / "scenarios"
    for path in sorted(root.rglob("*.el")):
        result = _quiet(parse, path, validate=False)
        if result.model is None:
            continue
        for el in result.model.elements:
            if type(el).__name__ == "DeonticToken" and el.kind == "burden":
                assert not _DATE_SHAPE_RE.search(el.deadline or ""), (path.name, el.name)
