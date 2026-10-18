"""
2.2.0-4 to 2.2.0-6 — date, instant and duration limits in comparisons.

A comparison's limit may be a date (2027-06-30), an instant
(2027-06-30T17:00+10:00) or a duration (24 hours) literal, or a Policy of
type date, instant or duration at its declared value. The reported text is
read strictly in the limit's kind: a date as YYYY-MM-DD, an instant in the
2.1.0 notation with a UTC offset, a duration as a whole number, one space
and a unit. Dates compare by calendar day, instants by moment (17:00+10:00
equals 07:00Z), durations in minutes (a 30-day month, a 365-day year). A
date is never compared with an instant. No arithmetic.

Layer 1 (grammar), Layer 2 (validator) and Layer 3 (runtime) tests per
tests/README.md's strategy.
"""
import contextlib
import io

import pytest

from el_domain import Amount, CompareDuration, Date, Instant
from el_parser import parse_string


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """enterprise specification TimeProbe
policy Cutoff : date {{ initial_value: 2027-06-30 }}
policy Closes : instant {{ initial_value: 2027-06-30T17:00+10:00 }}
policy NoticePeriod : duration {{ initial_value: 24 hours }}
party Assessor
community C {{
    objective: "probe"
    Assessor fills r
    role r {{
        action assess {{
            actor: r
            precondition: {pre}
        }}
    }}
}}
"""


def _parse(pre, validate=False):
    return _quiet(parse_string, _SPEC.format(pre=pre), validate=validate)


def _limit(pre):
    result = _parse(pre)
    assert result.model is not None, result.errors
    community = next(e for e in result.model.elements if type(e).__name__ == "Community")
    return community.roles[0].actions[0].preconditions[0].literal


# ── Grammar (2.2.0-4) ────────────────────────────────────────────────────

@pytest.mark.parametrize("limit, cls, value", [
    ("2027-06-30", Date, "2027-06-30"),
    ("2027-06-30T17:00+10:00", Instant, "2027-06-30T17:00+10:00"),
    ("2027-06-30T07:00Z", Instant, "2027-06-30T07:00Z"),
    ("24 hours", CompareDuration, 24),
    ("60 day", CompareDuration, 60),                  # a duration, no longer an amount
    ("0 minutes", CompareDuration, 0),
    ("60 sec", Amount, 60),                           # sec is no duration unit
])
def test_literal_order(limit, cls, value):
    literal = _limit(f'"x" >= {limit}')
    assert type(literal) is cls and literal.value == value


def test_duration_count_is_an_int():
    literal = _limit('"x" <= 24 hours')
    assert isinstance(literal.value, int) and literal.unit == "hours"


@pytest.mark.parametrize("limit", ["+60 days", "-60 days", "60.5 days", "1e3 days"])
def test_signed_or_fractional_duration_refused(limit):
    assert _parse(f'"x" <= {limit}').model is None


def test_policy_duration_keeps_its_sign():
    """Policy values are unchanged: textX INT still accepts +5 days."""
    src = _SPEC.format(pre='"x"').replace("initial_value: 24 hours", "initial_value: +5 days")
    result = _quiet(parse_string, src, validate=False)
    assert result.model is not None, result.errors


# ── Judging (2.2.0-5) ────────────────────────────────────────────────────

from el_engine import read_reported_value  # noqa: E402
from el_runtime import Runtime  # noqa: E402


def _act(pre, reported):
    result = _parse(pre)
    assert result.model is not None, result.errors
    fact = pre.split('"')[1]
    return _quiet(_quiet(Runtime.build_from_spec, result.model).advance,
                  "assess", "Assessor", {fact: reported})


@pytest.mark.parametrize("pre, reported, holds", [
    ('"expiry" >= 2027-06-30', "2027-06-30", True),
    ('"expiry" >= 2027-06-30', "2027-06-29", False),
    ('"expiry" == Cutoff', "2027-06-30", True),
    ('"notified at" <= 2027-06-30T17:00+10:00', "2027-06-30T07:00Z", True),     # same moment
    ('"notified at" <= 2027-06-30T17:00+10:00', "2027-06-30T17:01+10:00", False),
    ('"notified at" < Closes', "2027-06-30T06:59Z", True),
    ('"within" <= 24 hours', "1 day", True),
    ('"within" <= 24 hours', "1440 minutes", True),
    ('"within" <= 24 hours', "25 hours", False),
    ('"within" <= 24 hours', "1 month", False),                                # a 30-day month
    ('"within" == NoticePeriod', "1 day", True),
    ('"within" != 1 year', "365 days", False),                                 # a 365-day year
    ('"within" >= 0 minutes', "0 minutes", True),
])
def test_holds_or_fails(pre, reported, holds):
    record = _act(pre, reported)
    fact = pre.split('"')[1]
    if holds:
        assert record.outcome == "ok"
        assert record.effects[0].startswith(f"precondition satisfied: '{fact}' {reported} ")
    else:
        assert record.outcome == "blocked"
        assert record.reason.startswith(f"precondition not satisfied: '{fact}' {reported} ")


def test_reason_names_a_policy_limit():
    assert _act('"within" <= NoticePeriod', "25 hours").reason == \
        "precondition not satisfied: 'within' 25 hours <= 24 hours (NoticePeriod)"


@pytest.mark.parametrize("pre, reported, noun", [
    ('"expiry" >= 2027-06-30', "2027-06-30T10:00+10:00", "a date"),            # an instant
    ('"expiry" >= 2027-06-30', "30 June 2027", "a date"),
    ('"expiry" >= 2027-06-30', "2027-02-30", "a date"),
    ('"expiry" >= 2027-06-30', "2027-6-30", "a date"),
    ('"notified at" <= Closes', "2027-06-30", "an instant"),                   # a date
    ('"notified at" <= Closes', "2027-06-30T17:00", "an instant"),             # no offset
    ('"notified at" <= Closes', "2027-06-30T17:00+24:00", "an instant"),
    ('"within" <= 24 hours', "24h", "a duration"),
    ('"within" <= 24 hours', "-1 day", "a duration"),
    ('"within" <= 24 hours', "1.5 days", "a duration"),
    ('"within" <= 24 hours', "24", "a duration"),
])
def test_not_established(pre, reported, noun):
    record = _act(pre, reported)
    fact = pre.split('"')[1]
    assert record.outcome == "blocked"
    assert record.reason == (f"precondition not established: '{fact}' reported {reported}: "
                             f"not {noun} value")


def test_not_text_names_an_example():
    assert _act('"within" <= 24 hours', 24).reason == (
        "precondition not established: 'within' reported a value of type int, not text; "
        "send text, e.g. \"24 hours\"")


@pytest.mark.parametrize("text, kind, value", [
    ("2027-06-30", "date", "2027-06-30"),
    ("2027-06-30T17:00+10:00", "instant", "2027-06-30 07:00:00+00:00"),
    ("2 weeks", "duration", 20160),
    ("1 year", "duration", 525600),
])
def test_read_reported_value(text, kind, value):
    read, reason = read_reported_value(text, kind)
    assert reason is None and str(read) == str(value)


def test_keeps_with_a_date_limit():
    from datetime import datetime, timedelta, timezone
    from el_engine import DeadlineClock
    src = _SPEC.format(pre='"x"') + (
        'party Supplier { holds duty }\n'
        'burden duty { standing keeps: "certificate expiry" >= Cutoff state: active }\n')
    result = _quiet(parse_string, src, validate=False)
    assert result.model is not None, result.errors
    rt = _quiet(Runtime.build_from_spec, result.model,
                clock=DeadlineClock(utc_offset=timezone(timedelta(hours=10))))
    record = rt.check_live_violations(as_at=datetime.fromisoformat("2027-01-01T09:00+10:00"),
                                      facts={"certificate expiry": "2027-05-31"})
    assert record.effects == (
        "breached 'duty' held by 'Supplier': 'certificate expiry' 2027-05-31 >= 2027-06-30 "
        "(Cutoff) at as_at 2027-01-01T09:00:00+10:00",)
