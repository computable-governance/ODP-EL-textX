"""
2.5.0-1 — the sweep writes `expired`.

check_live_violations() moves an active or pending permit whose time is up to
`expired`. A duration is judged by _permit_elapsed() from the permit's clock; a
date is judged against as_at under a clock, at the sweep only. An expiry is not a
violation: the outcome stays ok unless a burden was violated, and no response
fires. The tick advances once if any permit expired, and not otherwise. The cause
is `deadline`. not_judged_date_burdens() and POST /check-violations also list a
date-form permit that cannot be judged, for every reason a burden is listed for.

The table cells, by state, are in tests/test_permit_transition_table.py.

Fixture: Operator holds the tokens it is given from GRANT_TICK. Tokens are granted
at tick 3, so a clock that starts at grant cannot be mistaken for one that starts
at tick 0. Layer 3 tests per tests/README.md's strategy.
"""
import contextlib
import io
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import el_api
from el_engine import (
    DeadlineClock,
    enroll,
    grant_token,
    initial_state,
    not_judged_date_burdens,
    token_from_spec,
)
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_PROBE = """
enterprise specification PermitSweepProbe

party Issuer
party Operator

community ProbeCommunity
    description: "Single role whose acts are gated by permits with time limits"
    {
        objective: "Exercise the sweep"
            satisfaction: any_discharged(siblingGroup)

        role operatorRole
            description: "Performs the acts"
            {
                action useTimed {
                    actor: operatorRole
                    requires_permit timedPermit
                }

                action useDated {
                    actor: operatorRole
                    requires_permit datedPermit
                }

                action dischargeSibling {
                    actor: operatorRole
                }

                action lateAct {
                    actor: operatorRole
                }

                action frozenAct {
                    actor: operatorRole
                }
            }
    }

permit timedPermit {
    for_action: "useTimed"
    state: active
    deadline: "5 minutes"
}

permit longerPermit {
    for_action: "useTimed"
    state: active
    deadline: "10 minutes"
}

permit datedPermit {
    for_action: "useDated"
    state: active
    deadline: "by 2026-05-20"
}

permit laterDatedPermit {
    for_action: "useDated"
    state: active
    deadline: "by 2026-08-20"
}

permit thirdDatedPermit {
    for_action: "useDated"
    state: active
    deadline: "by 2026-09-20"
}

permit strictPermit {
    for_action: "useTimed"
    state: active
    deadline: "5 minutes"
    discharge_mode: strict
}

permit wordsPermit {
    for_action: "useTimed"
    state: active
    deadline: "thirty days"
}

permit episodePermit {
    for_action: "useTimed"
    state: active
    deadline: "referral episode"
}

burden siblingBurden {
    for_action: "dischargeSibling"
    state: active
    discharge_mode: eventual
}

burden lateBurden {
    for_action: "lateAct"
    state: active
    deadline: "5 minutes"
    discharge_mode: eventual
}

burden frozenBurden {
    for_action: "frozenAct"
    state: active
    deadline: "5 minutes"
    discharge_mode: strict
}

token_group siblingGroup {
    member: siblingBurden
    member: timedPermit
}

commitment siblingBurdenCommitment {
    by: Issuer
    obligation: "Backs the group member siblingBurden"
    creates_burden: siblingBurden
}

commitment timedPermitCommitment {
    by: Issuer
    obligation: "Backs the group member timedPermit"
    creates_burden: timedPermit
}

violation_response OnExpiry {
    on_violation_of: timedPermit
    obligates: Issuer
    response_kind: remediate
}
"""

GRANT_TICK = 3
PAST_THE_LIMIT = 20
OFFSET = timezone(timedelta(hours=10))
CLOCK = DeadlineClock(utc_offset=OFFSET)
PAST_THE_DATES = datetime(2026, 12, 1, 0, 0, tzinfo=OFFSET)

ELAPSED_LINE = ("expired permit 'timedPermit' held by 'Operator' "
                "(elapsed 17 >= deadline 5 steps)")
NOT_HELD = "required permit '{}' not held by actor"


def _spec():
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    return result


def _runtime(*names, tick=GRANT_TICK, clock=CLOCK, seeds=None) -> Runtime:
    """Operator holds each named token from GRANT_TICK. seeds maps a token name
    to fields to replace on its instance. tick is where the runtime starts, for
    a strict burden, which refuses advance_clock()."""
    spec = _spec().model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = state.with_tick(GRANT_TICK)
    for name in names:
        token = token_from_spec(spec, name, "Operator", GRANT_TICK)
        token = replace(token, **(seeds or {}).get(name, {}))
        state = grant_token(state, token)
    return Runtime(state.with_tick(tick), spec, clock=clock)


def _state_of(rt, name):
    return next(t.state for t in rt.current_state().tokens if t.token_name == name)


def _clock_to(rt, tick):
    ticks = tick - rt.current_state().tick
    if ticks:
        assert rt.advance_clock(ticks).outcome == "ok"
    assert rt.current_state().tick == tick


def _expired_runtime(*names):
    """timedPermit (and any other named token) past its limit, not yet swept."""
    rt = _runtime("timedPermit", *names)
    _clock_to(rt, PAST_THE_LIMIT)
    return rt


# ── D12: the tick, the outcome and the lists ─────────────────────────────────

def test_nothing_expired_leaves_the_tick_unchanged():
    rt = _runtime("timedPermit", "datedPermit")
    _clock_to(rt, GRANT_TICK + 4)

    record = rt.check_live_violations(as_at=datetime(2026, 5, 1, tzinfo=OFFSET))

    assert record.outcome == "ok"
    assert record.effects == () and record.token_events == ()
    assert rt.current_state().tick == GRANT_TICK + 4


def test_one_expired_advances_the_tick_and_stays_ok():
    rt = _expired_runtime()

    record = rt.check_live_violations()

    assert record.outcome == "ok"
    assert record.violations == () and record.discharged == ()
    assert record.effects == (ELAPSED_LINE,)
    assert record.tick == PAST_THE_LIMIT
    assert rt.current_state().tick == PAST_THE_LIMIT + 1


def test_several_expired_advance_the_tick_once():
    rt = _expired_runtime("longerPermit", "datedPermit")

    record = rt.check_live_violations(as_at=PAST_THE_DATES)

    assert {_state_of(rt, n) for n in ("timedPermit", "longerPermit", "datedPermit")} \
        == {"expired"}
    assert len(record.effects) == 3
    assert rt.current_state().tick == PAST_THE_LIMIT + 1


def test_burden_and_permit_in_one_sweep_advance_the_tick_once():
    rt = _expired_runtime("lateBurden")

    record = rt.check_live_violations()

    assert record.outcome == "violation"
    assert record.violations == ("lateBurden",)
    assert _state_of(rt, "lateBurden") == "violated"
    assert _state_of(rt, "timedPermit") == "expired"
    assert rt.current_state().tick == PAST_THE_LIMIT + 1


def test_second_sweep_changes_nothing():
    rt = _expired_runtime()
    rt.check_live_violations()

    record = rt.check_live_violations()

    assert record.effects == () and record.token_events == ()
    assert _state_of(rt, "timedPermit") == "expired"
    assert rt.current_state().tick == PAST_THE_LIMIT + 1


# ── D2: the state and the cause ──────────────────────────────────────────────

def test_expiry_event_and_cause_for_both_forms():
    rt = _expired_runtime("datedPermit")

    record = rt.check_live_violations(as_at=PAST_THE_DATES)

    assert [e.token_name for e in record.token_events] == ["timedPermit", "datedPermit"]
    for event in record.token_events:
        assert event.event == "expired"
        assert event.token_kind == "permit"
        assert (event.from_state, event.to_state) == ("active", "expired")
        assert (event.cause, event.cause_ref) == ("deadline", None)
        assert event.by == "system"


def test_expiry_fires_no_response():
    rt = _expired_runtime()
    rt.check_live_violations()

    record = rt.fire_violation_responses()

    assert record.fired_responses == ()


# ── T5 with D12: discharge_mode and a strict freeze ──────────────────────────

def test_strict_permit_expires():
    rt = _runtime("strictPermit")
    _clock_to(rt, PAST_THE_LIMIT)

    rt.check_live_violations()

    assert _state_of(rt, "strictPermit") == "expired"


def test_expiry_during_a_strict_freeze_moves_the_tick():
    # The sweep has no strict guard; advance_clock() does.
    rt = _runtime("timedPermit", "frozenBurden", tick=PAST_THE_LIMIT)
    assert rt.advance_clock(1).outcome == "blocked"

    record = rt.check_live_violations()

    assert record.outcome == "ok"
    assert _state_of(rt, "timedPermit") == "expired"
    assert _state_of(rt, "frozenBurden") == "active"
    assert rt.current_state().tick == PAST_THE_LIMIT + 1


# ── D4 and use after the sweep ───────────────────────────────────────────────

def test_date_form_stays_usable_until_the_sweep():
    rt = _runtime("datedPermit")
    assert rt.advance("useDated", "Operator").outcome == "ok"

    rt.check_live_violations(as_at=PAST_THE_DATES)
    record = rt.advance("useDated", "Operator")

    assert record.outcome == "blocked"
    assert record.reason == NOT_HELD.format("datedPermit")


def test_use_after_the_sweep_names_the_expired_instance():
    rt = _expired_runtime()
    rt.check_live_violations()

    record = rt.advance("useTimed", "Operator")

    assert record.outcome == "blocked"
    assert record.reason == NOT_HELD.format("timedPermit")
    assert record.blocked_by.state == "expired"
    assert _state_of(rt, "timedPermit") == "expired"


# ── Q8: no measurable magnitude ──────────────────────────────────────────────

def test_deadline_with_no_magnitude_never_expires_and_gets_no_warning():
    rt = _runtime("wordsPermit", "episodePermit", tick=10_000_000)

    record = rt.check_live_violations(as_at=PAST_THE_DATES)

    assert _state_of(rt, "wordsPermit") == "active"
    assert _state_of(rt, "episodePermit") == "active"
    assert record.effects == ()
    assert rt.current_state().tick == 10_000_000
    assert not_judged_date_burdens(rt.current_state(), rt._spec, CLOCK, PAST_THE_DATES) == []
    assert [w for w in _spec().warnings
            if "deadline" in w and ("wordsPermit" in w or "episodePermit" in w)] == []


# ── T10: the not-judged list and lines ───────────────────────────────────────

def _lines(listed):
    return tuple(f"not judged '{t}' held by '{h}': {r}" for t, h, r in listed)


def test_no_clock_is_listed_and_written_as_not_judged():
    # Active and pending are listed; a state the sweep leaves alone is not.
    rt = _runtime("datedPermit", "laterDatedPermit", "thirdDatedPermit", clock=None, seeds={
        "laterDatedPermit": {"state": "pending"},
        "thirdDatedPermit": {"state": "superseded"},
    })

    listed = not_judged_date_burdens(rt.current_state(), rt._spec, None, PAST_THE_DATES)
    record = rt.check_live_violations(as_at=PAST_THE_DATES)

    assert listed == [("datedPermit", "Operator", "date deadline, no clock"),
                      ("laterDatedPermit", "Operator", "date deadline, no clock")]
    assert record.effects == _lines(listed)
    assert _state_of(rt, "datedPermit") == "active"
    assert _state_of(rt, "laterDatedPermit") == "pending"
    assert rt.current_state().tick == GRANT_TICK


def test_no_as_at_is_listed_and_written_as_not_judged():
    rt = _runtime("datedPermit")

    listed = not_judged_date_burdens(rt.current_state(), rt._spec, CLOCK)
    record = rt.check_live_violations()

    assert listed == [("datedPermit", "Operator", "date deadline, no as_at")]
    assert record.effects == _lines(listed)
    assert _state_of(rt, "datedPermit") == "active"


def test_every_other_date_reason_is_listed_as_for_a_burden():
    rt = _runtime("datedPermit", "laterDatedPermit", "thirdDatedPermit", seeds={
        "datedPermit": {"deadline": "2026-02-30"},
        "laterDatedPermit": {"deadline": "2026-02-20 within 1 day"},
        "thirdDatedPermit": {"deadline": "2026-02-20T17:00"},
    })

    listed = not_judged_date_burdens(rt.current_state(), rt._spec, CLOCK, PAST_THE_DATES)
    record = rt.check_live_violations(as_at=PAST_THE_DATES)

    assert listed == [
        ("datedPermit", "Operator", "invalid date"),
        ("laterDatedPermit", "Operator", "a date with other numbers is not measured"),
        ("thirdDatedPermit", "Operator", "date not in the 2.1.0 notation"),
    ]
    assert record.effects == _lines(listed)
    assert {_state_of(rt, n) for n, _, _ in listed} == {"active"}
    assert rt.current_state().tick == GRANT_TICK


# ── The history after an expiry ──────────────────────────────────────────────

def test_history_after_an_expiry():
    rt = _expired_runtime("datedPermit")
    rt.check_live_violations(as_at=PAST_THE_DATES)

    assert rt.token_states_at("timedPermit", "Operator", PAST_THE_LIMIT) == ("active",)
    assert rt.token_states_at("timedPermit", "Operator", PAST_THE_LIMIT + 1) == ("expired",)
    assert rt.in_force_at("timedPermit", "Operator", GRANT_TICK + 4) is True
    assert rt.in_force_at("timedPermit", "Operator", PAST_THE_LIMIT) is False
    assert rt.in_force_at("timedPermit", "Operator", PAST_THE_LIMIT + 1) is False
    # A date form is not judged at use, so it was in force until the sweep.
    assert rt.in_force_at("datedPermit", "Operator", PAST_THE_LIMIT) is True
    assert rt.in_force_at("datedPermit", "Operator", PAST_THE_LIMIT + 1) is False


# ── T4: an elapsed, unswept permit and a discharged sibling ──────────────────

def test_sibling_discharged_first_wins():
    rt = _expired_runtime("siblingBurden")

    discharged = rt.advance("dischargeSibling", "Operator")

    event = next(e for e in discharged.token_events if e.token_name == "timedPermit")
    assert (event.event, event.cause, event.cause_ref) \
        == ("superseded", "sibling", "siblingBurden")

    tick = rt.current_state().tick
    swept = rt.check_live_violations()
    assert _state_of(rt, "timedPermit") == "superseded"
    assert swept.token_events == ()
    assert rt.current_state().tick == tick


def test_sweep_first_wins():
    rt = _expired_runtime("siblingBurden")

    swept = rt.check_live_violations()

    event = next(e for e in swept.token_events if e.token_name == "timedPermit")
    assert (event.event, event.cause) == ("expired", "deadline")

    discharged = rt.advance("dischargeSibling", "Operator")
    assert discharged.discharged == ("siblingBurden",)
    assert _state_of(rt, "timedPermit") == "expired"
    assert not [e for e in discharged.token_events if e.token_name == "timedPermit"]


# ── The API ──────────────────────────────────────────────────────────────────

_API_SPEC = """
enterprise specification PermitSweepApiProbe

party Holder {
    holds timedP
    holds datedP
}

permit timedP { for_action: "use" state: active deadline: "5 minutes" }
permit datedP { for_action: "use" state: active deadline: "by 2026-05-20" }

community SweepCommunity {
    objective: "probe"
}
"""


@pytest.fixture
def api(monkeypatch):
    spec = _quiet(parse_string, _API_SPEC, validate=False).model

    def build():
        return _quiet(Runtime.build_from_spec, spec)

    monkeypatch.setitem(el_api._SCENARIO_BUILDERS, "sweep_probe", build)
    monkeypatch.setitem(el_api._SCENARIO_CLOCK, "sweep_probe", None)
    monkeypatch.setattr(el_api, "_active_scenario", "sweep_probe")
    monkeypatch.setattr(el_api, "_active_community", "SweepCommunity")
    monkeypatch.setattr(el_api, "_runtime", el_api._new_runtime("sweep_probe"))
    return el_api


def test_api_shows_an_expiry_under_effects_only(api):
    assert api._runtime.advance_clock(PAST_THE_LIMIT).outcome == "ok"

    resp = _quiet(api.check_violations_endpoint)

    assert resp.tick == PAST_THE_LIMIT
    assert resp.outcome == "ok" and resp.violations == []
    assert "expired permit 'timedP' held by 'Holder' (elapsed 20 >= deadline 5 steps)" \
        in resp.effects
    assert api._runtime.current_state().tick == PAST_THE_LIMIT + 1


def test_api_lists_a_clockless_date_form_permit_as_not_judged(api):
    resp = _quiet(api.check_violations_endpoint, "2027-01-01T00:00+10:00")

    assert [(e.token, e.holder, e.reason) for e in resp.not_judged] == [
        ("datedP", "Holder", "date deadline, no clock")]
    assert "not judged 'datedP' held by 'Holder': date deadline, no clock" in resp.effects
    assert resp.violations == []
