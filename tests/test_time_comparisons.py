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
