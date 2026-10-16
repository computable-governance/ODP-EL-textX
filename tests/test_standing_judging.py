"""
2.1.0-18 — judging standing duties.

At check_live_violations(as_at=..., facts=...), each active standing duty
is judged:

1. its term end by date or instant (ends_at), only with a clock and an
   as_at: at or after the end it is met (discharged, "term ended …; no
   breach recorded") and its keeps is not judged;
2. otherwise its keeps comparison against the facts reported with the
   check, only with an as_at: true "kept …", false "breached …"
   (violated), not established "not judged …". Never "kept" without a
   value that holds.

Its ended_by event, when it fires (an emitting action or fire_event()),
also ends the term. A met or breached duty is final. Facts are not stored.

Layer 3 (runtime) tests per tests/README.md's strategy.
"""
import contextlib
import dataclasses
import io
from datetime import datetime, timedelta, timezone

import pytest

from el_engine import DeadlineClock
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


AEST = timezone(timedelta(hours=10))
CLOCK = DeadlineClock(utc_offset=AEST)


def _at(text):
    return datetime.fromisoformat(text)


def _runtime(duty_fields, clock=CLOCK, extra_tokens="", holds="duty"):
    src = f"""enterprise specification JudgingProbe
policy MinimumCover : amount {{ initial_value: 20000000 AUD }}
policy ContractEnd : instant {{ initial_value: 2027-06-30T17:00+10:00 }}
policy ContractEndDate : date {{ initial_value: 2027-06-30 }}
party Supplier {{ {" ".join("holds " + h for h in holds.split())} }}
community C {{
    objective: "o"
    event contractSigned
    event contractTerminated
    Supplier fills r
    role r {{
        action terminate {{ actor: r emits: contractTerminated }}
        action sign {{ actor: r emits: contractSigned }}
    }}
}}
burden duty {{ standing keeps: "insurance cover" >= MinimumCover {duty_fields} }}
{extra_tokens}
"""
    result = _quiet(parse_string, src, validate=False)
    assert result.ok, result.errors
    return _quiet(Runtime.build_from_spec, result.model, clock=clock)


def _state(rt, name="duty"):
    return next(t.state for t in rt.current_state().tokens if t.token_name == name)


GOOD = {"insurance cover": "25000000.00 AUD"}
BAD = {"insurance cover": "15000000 AUD"}


# ── keeps: kept, breached, not judged ────────────────────────────────────

def test_kept():
    rt = _runtime("state: active")
    record = rt.check_live_violations(as_at=_at("2027-01-01T09:00+10:00"), facts=GOOD)
    assert record.outcome == "ok" and record.violations == () and record.discharged == ()
    assert record.effects == (
        "kept 'duty' held by 'Supplier': 'insurance cover' 25000000.00 AUD >= 20000000 AUD "
        "(MinimumCover) at as_at 2027-01-01T09:00:00+10:00",)
    assert _state(rt) == "active" and rt.current_state().tick == 0


def test_breached():
    rt = _runtime("state: active")
    record = rt.check_live_violations(as_at=_at("2027-01-01T09:00+10:00"), facts=BAD)
    assert record.outcome == "violation" and record.violations == ("duty",)
    assert record.effects == (
        "breached 'duty' held by 'Supplier': 'insurance cover' 15000000 AUD >= 20000000 AUD "
        "(MinimumCover) at as_at 2027-01-01T09:00:00+10:00",)
    assert _state(rt) == "violated" and rt.current_state().tick == 1


@pytest.mark.parametrize("facts, reason", [
    ({}, "'insurance cover' not reported"),
    ({"insurance cover": "unknown"}, "'insurance cover' not reported"),
    ({"insurance cover": 25000000}, "'insurance cover' reported a value of type int, not text; "
                                    "send text, e.g. \"25000000.00 AUD\""),
    ({"insurance cover": "25000000"}, "'insurance cover' reported 25000000: not an amount value"),
    ({"insurance cover": "25000000 NZD"}, "'insurance cover' reported 25000000 NZD: currency "
                                          "NZD, not AUD; amounts are compared only within one currency"),
])
def test_not_established_is_never_kept(facts, reason):
    rt = _runtime("state: active")
    record = rt.check_live_violations(as_at=_at("2027-01-01T09:00+10:00"), facts=facts)
    assert record.effects == (f"not judged 'duty' held by 'Supplier': {reason}",)
    assert record.violations == () and _state(rt) == "active"
    assert not any(e.startswith("kept") for e in record.effects)


def test_no_as_at_not_judged_even_with_a_false_report():
    rt = _runtime("state: active")
    record = rt.check_live_violations(facts=BAD)
    assert record.effects == ("not judged 'duty' held by 'Supplier': no as_at",)
    assert _state(rt) == "active"


def test_one_breach_and_a_later_good_report_does_not_undo_it():
    rt = _runtime("state: active")
    rt.check_live_violations(as_at=_at("2027-01-01T09:00+10:00"), facts=BAD)
    record = rt.check_live_violations(as_at=_at("2027-01-02T09:00+10:00"), facts=GOOD)
    assert _state(rt) == "violated"
    assert record.violations == () and record.effects == ()
    record = rt.check_live_violations(as_at=_at("2027-01-03T09:00+10:00"), facts=BAD)
    assert record.violations == ()          # no second breach


# ── Term end by date or instant ──────────────────────────────────────────

@pytest.mark.parametrize("as_at, met", [
    ("2027-06-30T16:59:59+10:00", False),   # one second before
    ("2027-06-30T17:00:00+10:00", True),    # at
    ("2027-06-30T17:00:01+10:00", True),    # after
    ("2027-06-30T06:59:59Z", False),        # the same instants in another offset
    ("2027-06-30T07:00:00Z", True),
])
def test_instant_end_boundary(as_at, met):
    rt = _runtime("ends_at: 2027-06-30T17:00+10:00 state: active")
    record = rt.check_live_violations(as_at=_at(as_at), facts=GOOD)
    assert (_state(rt) == "discharged") is met
    if met:
        assert record.discharged == ("duty",)
        assert record.effects == (
            f"term ended 'duty' held by 'Supplier' (ends_at 2027-06-30T17:00:00+10:00; "
            f"as_at {_at(as_at).isoformat()}); no breach recorded",)
        assert rt.current_state().tick == 1
    else:
        assert record.effects[0].startswith("kept 'duty'")


@pytest.mark.parametrize("as_at, met", [
    ("2027-06-30T23:59:59+10:00", False),   # the whole date counts
    ("2027-07-01T00:00:00+10:00", True),    # the end of that day, clock offset
    ("2027-06-30T13:59:59Z", False),
    ("2027-06-30T14:00:00Z", True),
])
def test_date_alone_ends_at_the_end_of_that_day(as_at, met):
    rt = _runtime("ends_at: 2027-06-30 state: active")
    rt.check_live_violations(as_at=_at(as_at), facts=GOOD)
    assert (_state(rt) == "discharged") is met


@pytest.mark.parametrize("policy, as_at", [
    ("ContractEnd", "2027-06-30T17:00+10:00"),
    ("ContractEndDate", "2027-07-01T00:00+10:00"),
])
def test_policy_end(policy, as_at):
    rt = _runtime(f"ends_at: {policy} state: active")
    rt.check_live_violations(as_at=_at(as_at), facts=GOOD)
    assert _state(rt) == "discharged"


def test_keeps_not_judged_at_or_after_the_end():
    rt = _runtime("ends_at: 2027-06-30 state: active")
    record = rt.check_live_violations(as_at=_at("2027-07-02T00:00+10:00"), facts=BAD)
    assert _state(rt) == "discharged" and record.violations == ()


def test_a_met_duty_is_never_breached():
    rt = _runtime("ends_at: 2027-06-30 state: active")
    rt.check_live_violations(as_at=_at("2027-07-01T00:00+10:00"), facts=GOOD)
    record = rt.check_live_violations(as_at=_at("2027-07-02T00:00+10:00"), facts=BAD)
    assert _state(rt) == "discharged" and record.violations == () and record.effects == ()


@pytest.mark.parametrize("clock, as_at, reason", [
    (None, "2027-01-01T09:00+10:00", "term end, no clock"),
    (CLOCK, None, "term end, no as_at"),
])
def test_end_not_judged_means_keeps_not_judged(clock, as_at, reason):
    rt = _runtime("ends_at: 2027-06-30 state: active", clock=clock)
    record = rt.check_live_violations(as_at=_at(as_at) if as_at else None, facts=BAD)
    assert record.effects == (f"not judged 'duty' held by 'Supplier': {reason}",)
    assert _state(rt) == "active"


def test_end_already_passed_at_activation_is_met_at_the_first_check():
    rt = _runtime("ends_at: 2026-01-01 state: pending triggered_by: contractSigned")
    _quiet(rt.advance, "sign", "Supplier", {})
    record = rt.check_live_violations(as_at=_at("2027-01-01T09:00+10:00"), facts=BAD)
    assert _state(rt) == "discharged" and record.violations == ()


# ── Term end by event; start by event ────────────────────────────────────

@pytest.mark.parametrize("how", ["action", "fire_event"])
def test_ended_by_event(how):
    rt = _runtime("ended_by: contractTerminated state: active")
    if how == "action":
        record = _quiet(rt.advance, "terminate", "Supplier", {})
    else:
        record = _quiet(rt.fire_event, "contractTerminated")
    assert _state(rt) == "discharged"
    assert "duty" in record.discharged
    assert ("term ended 'duty' held by 'Supplier' (event contractTerminated); no breach "
            "recorded") in record.effects


def test_ended_by_event_leaves_a_pending_duty():
    rt = _runtime("ended_by: contractTerminated state: pending triggered_by: contractSigned")
    _quiet(rt.fire_event, "contractTerminated")
    assert _state(rt) == "pending"


def test_a_breached_duty_is_not_met_by_its_event():
    rt = _runtime("ended_by: contractTerminated state: active")
    rt.check_live_violations(as_at=_at("2027-01-01T09:00+10:00"), facts=BAD)
    _quiet(rt.fire_event, "contractTerminated")
    assert _state(rt) == "violated"


def test_pending_duty_not_judged_until_its_term_starts():
    rt = _runtime("state: pending triggered_by: contractSigned")
    record = rt.check_live_violations(as_at=_at("2027-01-01T09:00+10:00"), facts=BAD)
    assert record.effects == () and _state(rt) == "pending"
    _quiet(rt.fire_event, "contractSigned")
    record = rt.check_live_violations(as_at=_at("2027-01-02T09:00+10:00"), facts=BAD)
    assert _state(rt) == "violated"


# ── Facts are not stored; as_at monotonic ────────────────────────────────

def test_facts_are_not_stored():
    rt = _runtime("state: active")
    rt.check_live_violations(as_at=_at("2027-01-01T09:00+10:00"), facts=GOOD)
    state = rt.current_state()
    assert "facts" not in {f.name for f in dataclasses.fields(state)}
    assert not any(GOOD["insurance cover"] == v for v in vars(rt).values() if isinstance(v, str))
    record = rt.check_live_violations(as_at=_at("2027-01-02T09:00+10:00"))
    assert record.effects == ("not judged 'duty' held by 'Supplier': 'insurance cover' not reported",)


def test_as_at_may_not_go_backwards():
    rt = _runtime("state: active")
    rt.check_live_violations(as_at=_at("2027-01-02T09:00+10:00"), facts=GOOD)
    with pytest.raises(ValueError):
        rt.check_live_violations(as_at=_at("2027-01-01T09:00+10:00"), facts=BAD)
    assert _state(rt) == "active"


# ── Other burdens unchanged ──────────────────────────────────────────────

def test_plain_and_date_burdens_unchanged_beside_a_standing_duty():
    extra = ('burden dur { state: active deadline: "1 hour" }\n'
             'burden byDate { state: active deadline: "by 2026-11-30" }')
    rt = _runtime("state: active", extra_tokens=extra, holds="duty dur byDate")
    _quiet(rt.advance_clock, 60)
    record = rt.check_live_violations(as_at=_at("2026-12-01T00:00+10:00"), facts=GOOD)
    assert set(record.violations) == {"dur", "byDate"}
    assert _state(rt) == "active"
    assert any(e.startswith("kept 'duty'") for e in record.effects)
