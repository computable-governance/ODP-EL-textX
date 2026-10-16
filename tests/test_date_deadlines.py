"""
2.1.0-7 — the clock and date deadlines.

A burden deadline that is a date alone ("by 2026-11-30") or a date and time
with a UTC offset ("2026-11-30T17:00+10:00"), in the 2.1.0 notation of Date
and Instant policy values, is judged against a caller-supplied wall-clock
time `as_at`, never against the tick. It needs a DeadlineClock (one fixed
UTC offset). A date alone is due at 00:00 on the next day in the clock's
offset; an instant at that moment. Without a clock or an as_at the burden
is "not judged", never reported as met, and never violated by episode
conclusion. `as_at` may not go backwards within one runtime.

Strict date burdens are out of scope (they keep the 2.0.0 behaviour), and
the verifier does not model date deadlines: an eventual date burden is
never reported compelled (docs/ENGINE_VERIFIER_PARITY.md, rows R6, R7).

Layer 3 (runtime) and Layer 4 (verifier) tests per tests/README.md.
"""
import contextlib
import io
from datetime import datetime, timedelta, timezone

import pytest

from el_engine import (
    DeadlineClock, check_live_violations, not_judged_date_burdens,
)
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


AEST = timezone(timedelta(hours=10))
CLOCK = DeadlineClock(utc_offset=AEST)


def _at(text):
    return datetime.fromisoformat(text)


def _spec(*burdens, extra=""):
    """A party holding each burden; burdens are (name, deadline, attrs)."""
    holds = "\n".join(f"    holds {name}" for name, _, _ in burdens)
    decls = "\n".join(
        f'burden {name} {{ for_action: "do_{name}" state: {attrs.get("state", "active")} '
        f'deadline: "{deadline}" '
        + (f'triggered_by: {attrs["triggered_by"]} ' if "triggered_by" in attrs else "")
        + f'discharge_mode: {attrs.get("mode", "eventual")} }}'
        for name, deadline, attrs in burdens
    )
    src = (f"enterprise specification DateProbe\n\nparty Holder {{\n{holds}\n}}\n\n"
           f"{decls}\n\ncommunity C {{\n    objective: \"probe\"\n    event started\n}}\n{extra}")
    result = _quiet(parse_string, src, validate=False)
    assert result.ok, result.errors
    return result.model


def _runtime(*burdens, clock=CLOCK):
    return _quiet(Runtime.build_from_spec, _spec(*burdens), clock=clock)


def _state(rt, name):
    return next(t.state for t in rt.current_state().tokens if t.token_name == name)


_BY_DATE = ("byDate", "by 2026-11-30", {})


# ── The clock ────────────────────────────────────────────────────────────

def test_clock_is_keyword_only():
    with pytest.raises(TypeError):
        DeadlineClock(AEST)


def test_clock_needs_a_timezone_offset():
    with pytest.raises(ValueError):
        DeadlineClock(utc_offset="+10:00")


def test_clock_epoch_optional_whole_minute_naive_read_in_offset():
    assert DeadlineClock(utc_offset=AEST).epoch is None
    clock = DeadlineClock(utc_offset=AEST, epoch=datetime(2026, 11, 1, 9, 0))
    assert clock.epoch == datetime(2026, 11, 1, 9, 0, tzinfo=AEST)
    with pytest.raises(ValueError):
        DeadlineClock(utc_offset=AEST, epoch=datetime(2026, 11, 1, 9, 0, 30))


# ── Not judged ───────────────────────────────────────────────────────────

def test_not_judged_without_a_clock():
    rt = _runtime(_BY_DATE, clock=None)
    record = rt.check_live_violations(as_at=_at("2027-01-01T00:00+10:00"))
    assert record.outcome == "ok" and record.violations == ()
    assert record.effects == ("not judged 'byDate' held by 'Holder': date deadline, no clock",)
    assert rt.current_state().tick == 0
    assert _state(rt, "byDate") == "active"


def test_not_judged_without_as_at_whatever_the_tick():
    rt = _runtime(_BY_DATE)
    assert _quiet(rt.advance_clock, 10 ** 6).outcome == "ok"
    record = rt.check_live_violations()
    assert record.violations == ()
    assert record.effects == ("not judged 'byDate' held by 'Holder': date deadline, no as_at",)


@pytest.mark.parametrize("deadline, reason", [
    ("2026-11-30 within 1 day", "a date with other numbers is not measured"),
    ("between 2026-11-01 and 2026-11-30", "a date with other numbers is not measured"),
    ("2026-11-30 17:00", "a date with other numbers is not measured"),
    ("2026-11-30T17:00", "date not in the 2.1.0 notation"),          # no offset
    ("2026-11-30t17:00+10:00", "date not in the 2.1.0 notation"),    # lower-case t
    ("2026-11-30T17:00z", "date not in the 2.1.0 notation"),         # lower-case z
    ("2026-11-30T17:00+1000", "date not in the 2.1.0 notation"),
    ("2026-11-30T17:00:00.5Z", "date not in the 2.1.0 notation"),
    ("by 2026-02-30", "invalid date"),
    ("2026-11-30T24:00Z", "invalid date"),
    ("2026-11-30T17:00:30Z", "invalid date"),                        # seconds only :00
    ("2026-11-30T17:00-00:00", "invalid date"),
    ("by 9999-12-31", "invalid date"),              # its end is past datetime.max
    ("9999-12-31T23:59-01:00", "invalid date"),
])
def test_not_measured_or_invalid(deadline, reason):
    rt = _runtime(("b", deadline, {}))
    record = rt.check_live_violations(as_at=_at("2030-01-01T00:00Z"))
    assert record.violations == ()
    assert record.effects == (f"not judged 'b' held by 'Holder': {reason}",)


def test_not_judged_list_matches_the_effects():
    rt = _runtime(_BY_DATE, ("noOffset", "2026-11-30T17:00", {}), ("dur", "30 days", {}))
    state, spec = rt.current_state(), rt._spec
    expected = [("byDate", "Holder", "date deadline, no as_at"),
                ("noOffset", "Holder", "date not in the 2.1.0 notation")]
    assert not_judged_date_burdens(state, spec, CLOCK) == expected
    record = rt.check_live_violations()
    assert record.effects == tuple(f"not judged '{t}' held by '{h}': {r}" for t, h, r in expected)


def test_sweep_and_not_judged_list_select_the_same_burdens():
    # One selection function serves both: active, eventual burdens only.
    rt = _runtime(
        ("activeDate", "by 2026-11-30", {}),
        ("pendingDate", "by 2026-11-30", {"state": "pending", "triggered_by": "started"}),
        ("strictDate", "by 2026-11-30", {"mode": "strict"}),
        ("duration", "30 days", {}),
        ("compound", "2026-11-30 within 1 day", {}),
    )
    for as_at in (None, _at("2026-11-01T00:00+10:00")):
        listed = not_judged_date_burdens(rt.current_state(), rt._spec, CLOCK, as_at)
        record = check_live_violations(rt.current_state(), rt._spec, CLOCK, as_at)[1]
        lines = tuple(f"not judged '{t}' held by '{h}': {r}" for t, h, r in listed)
        assert record.effects == lines
        names = [t for t, _, _ in listed]
        assert "pendingDate" not in names and "strictDate" not in names
        assert "duration" not in names
    assert [t for t, _, _ in not_judged_date_burdens(rt.current_state(), rt._spec, CLOCK)] \
        == ["activeDate", "compound"]


# ── Judged against as_at ─────────────────────────────────────────────────

def test_date_alone_is_due_at_the_end_of_the_day():
    rt = _runtime(_BY_DATE)
    record = rt.check_live_violations(as_at=_at("2026-11-30T23:59+10:00"))
    assert record.violations == () and record.effects == ()
    assert rt.current_state().tick == 0

    record = rt.check_live_violations(as_at=_at("2026-12-01T00:00+10:00"))
    assert record.violations == ("byDate",)
    assert record.effects == (
        "violated 'byDate' held by 'Holder' (due 2026-12-01T00:00:00+10:00; "
        "as_at 2026-12-01T00:00:00+10:00; activated at tick 0)",)
    assert rt.current_state().tick == 1
    assert _state(rt, "byDate") == "violated"


def test_instant_uses_its_own_offset_and_as_at_may_be_in_another():
    rt = _runtime(("opens", "2026-11-30T17:00+10:00", {}))
    assert rt.check_live_violations(as_at=_at("2026-11-30T06:59Z")).violations == ()
    assert rt.check_live_violations(as_at=_at("2026-11-30T07:00Z")).violations == ("opens",)


def test_the_tick_never_judges_a_date():
    rt = _runtime(_BY_DATE)
    assert _quiet(rt.advance_clock, 10 ** 6).outcome == "ok"
    assert rt.check_live_violations(as_at=_at("2026-11-30T12:00+10:00")).violations == ()


def test_event_triggered_date_burden_keeps_its_due_date():
    rt = _runtime(("afterStart", "by 2026-11-30", {"state": "pending", "triggered_by": "started"}))
    # Pending: not judged at all (no line), even after the date.
    assert rt.check_live_violations(as_at=_at("2026-11-01T00:00+10:00")).effects == ()
    _quiet(rt.advance_clock, 7)
    _quiet(rt.fire_event, "started")
    assert rt.check_live_violations(as_at=_at("2026-11-30T23:00+10:00")).violations == ()
    record = rt.check_live_violations(as_at=_at("2026-12-01T00:00+10:00"))
    assert record.violations == ("afterStart",)
    assert record.effects[0].endswith("activated at tick 7)")


def test_date_passed_before_activation_is_violated_at_the_next_check():
    rt = _runtime(("late", "by 2026-11-30", {"state": "pending", "triggered_by": "started"}))
    assert rt.check_live_violations(as_at=_at("2026-12-05T00:00+10:00")).violations == ()
    _quiet(rt.fire_event, "started")
    assert rt.check_live_violations(as_at=_at("2026-12-05T00:00+10:00")).violations == ("late",)


def test_strict_date_burden_is_untouched():
    rt = _runtime(("strictDate", "by 2026-11-30", {"mode": "strict"}))
    record = rt.check_live_violations(as_at=_at("2027-01-01T00:00+10:00"))
    assert record.violations == () and record.effects == ()
    assert _state(rt, "strictDate") == "active"


def test_duration_burden_unchanged():
    rt = _runtime(("dur", "1 hour", {}), _BY_DATE)
    _quiet(rt.advance_clock, 60)
    record = rt.check_live_violations(as_at=_at("2026-11-01T00:00+10:00"))
    assert record.violations == ("dur",)
    assert _state(rt, "byDate") == "active"


def test_date_burden_never_violated_by_episode_conclusion():
    extra = """
commitment C1 { by: Holder obligation: "main" creates_burden: mainBurden }
commitment C2 { by: Holder obligation: "tail" creates_burden: byDate }
token_group episodeGroup {
    member: mainBurden
    member: byDate
}
community EpisodeCommunity {
    objective: "probe"
        satisfaction: all_discharged(episodeGroup)
    lifecycle {
        terminating {
            on_objective_achieved: true
        }
    }
}
"""
    spec = _spec(("mainBurden", "1 week", {}), _BY_DATE, extra=extra)
    for clock, as_at in [(None, None), (CLOCK, None), (CLOCK, _at("2026-11-01T00:00+10:00"))]:
        rt = _quiet(Runtime.build_from_spec, spec, clock=clock)
        rt.discharge_burden("mainBurden")
        assert rt.check_live_violations(as_at=as_at).violations == ()
        assert _state(rt, "byDate") == "active"


# ── as_at checks ─────────────────────────────────────────────────────────

def test_naive_as_at_refused():
    rt = _runtime(_BY_DATE)
    with pytest.raises(ValueError):
        rt.check_live_violations(as_at=datetime(2026, 12, 1))
    assert rt._ledger == []
    with pytest.raises(ValueError):
        check_live_violations(rt.current_state(), rt._spec, CLOCK, datetime(2026, 12, 1))


def test_as_at_may_not_go_backwards():
    rt = _runtime(_BY_DATE)
    first = _at("2026-11-20T00:00+10:00")
    rt.check_live_violations(as_at=first)
    assert rt.last_as_at == first          # recorded although nothing was violated
    entries = len(rt._ledger)
    with pytest.raises(ValueError):
        rt.check_live_violations(as_at=_at("2026-11-19T23:59+10:00"))
    assert len(rt._ledger) == entries      # nothing ledgered
    rt.check_live_violations(as_at=_at("2026-11-19T14:00Z"))   # the same moment
    assert rt.check_live_violations().violations == ()          # no as_at: allowed
    assert rt.last_as_at == first


def test_builders_take_the_clock():
    spec = _spec(_BY_DATE)
    assert _quiet(Runtime.build_from_spec, spec, clock=CLOCK).clock is CLOCK
    assert _quiet(Runtime.build_from_federation, spec, clock=CLOCK).clock is CLOCK
    assert _quiet(Runtime.build_from_spec, spec).clock is None


# ── Verifier: an eventual date burden is never reported compelled ────────

@pytest.mark.parametrize("deadline", ["by 2026-11-30", "2026-11-30T17:00+10:00"])
def test_eventual_date_burden_never_compelled(deadline):
    extra = 'commitment C1 { by: Holder obligation: "d" creates_burden: dated }\n'
    spec = _spec(("dated", deadline, {}), extra=extra)
    static = _quiet(build_kripke_model, spec, horizon=10)
    rt = _quiet(Runtime.build_from_spec, spec, clock=CLOCK)
    rt.check_live_violations(as_at=_at("2026-11-01T00:00+10:00"))
    hybrid = _quiet(build_kripke_from_runtime, rt, horizon=10)
    for km in (static, hybrid):
        assert km.check_obligation("dated").satisfied is False
