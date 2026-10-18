"""
2.2.0-2 — `==` and `!=` in comparisons.

A comparison may test the reported value for equality with its limit:
`precondition: "approvals" == 2`, `precondition: "insurance cover" !=
MinimumCover`, and the same in a standing duty's keeps. Equality is of the
values (exact Decimal), not of the text: "2.0" == 2 holds, "10.00%" != 10%
fails. Not established exactly as for the ordering operators. `=>` stays
a syntax error.

Layer 1 (grammar) and Layer 3 (runtime) tests per tests/README.md's strategy.
"""
import contextlib
import io
from datetime import datetime, timedelta, timezone

import pytest

from el_engine import DeadlineClock, precondition_text
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """
enterprise specification EqualityProbe

policy MinimumCover : amount {{ initial_value: 20000000 AUD }}
policy MaximumShare : percentage {{ initial_value: 10% }}

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
{extra}
"""


def _parse(pre, extra="", validate=False):
    return _quiet(parse_string, _SPEC.format(pre=pre, extra=extra), validate=validate)


def _act(pre, facts):
    result = _parse(pre)
    assert result.ok, result.errors
    return _quiet(_quiet(Runtime.build_from_spec, result.model).advance, "assess", "Assessor", facts)


# ── Grammar ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("op", ["==", "!="])
def test_parses_and_validates_cleanly(op):
    result = _parse(f'"approvals" {op} 2', validate=True)
    assert result.ok and result.warnings == [], (result.errors, result.warnings)
    cmp = next(e for e in result.model.elements if type(e).__name__ == "Community") \
        .roles[0].actions[0].preconditions[0]
    assert (cmp.fact, cmp.op, cmp.literal) == ("approvals", op, 2)


@pytest.mark.parametrize("pre", ['"x" => 5', '"x" = 5', '"x" =< 5', '"x" === 5', '"x" !== 5'])
def test_typos_stay_refused(pre):
    assert not _parse(pre).ok


def test_comparison_type_text_unchanged():
    """The 2.1.0 comparison-type message is the same with an equality operator."""
    errors = _parse('"response time" == 60 day', validate=True).errors
    assert errors == [
        "[comparison-type] Action 'assess': precondition \"response time\" == 60 day: limit "
        "60 day has currency code 'day', not three upper-case letters A-Z (ISO 4217 form); "
        "a duration cannot be compared. (clause to be confirmed)"]


# ── Judging ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pre, reported, holds", [
    ('"approvals" == 2', "2", True),
    ('"approvals" == 2', "2.0", True),                         # values, not text
    ('"approvals" == 2', "3", False),
    ('"approvals" != 2', "3", True),
    ('"approvals" != 2', "2.00", False),
    ('"share" == 10%', "10.00%", True),
    ('"share" != MaximumShare', "10.00%", False),
    ('"cover" == MinimumCover', "20000000.00 AUD", True),
    ('"cover" != 20000000 AUD', "25000000 AUD", True),
])
def test_holds_or_fails(pre, reported, holds):
    fact = pre.split('"')[1]
    record = _act(pre, {fact: reported})
    if holds:
        assert record.outcome == "ok"
        assert record.effects[0].startswith(f"precondition satisfied: '{fact}' {reported} ")
    else:
        assert record.outcome == "blocked"
        assert record.reason.startswith(f"precondition not satisfied: '{fact}' {reported} ")


def test_failing_reason_format():
    assert _act('"approvals" == 2', {"approvals": "3"}).reason == \
        "precondition not satisfied: 'approvals' 3 == 2"
    assert _act('"cover" != MinimumCover', {"cover": "20000000 AUD"}).reason == \
        "precondition not satisfied: 'cover' 20000000 AUD != 20000000 AUD (MinimumCover)"


@pytest.mark.parametrize("op", ["==", "!="])
@pytest.mark.parametrize("facts, reason", [
    ({}, "'cover' not reported"),
    ({"cover": 20000000}, "'cover' reported a value of type int, not text; "
                          "send text, e.g. \"25000000.00 AUD\""),
    ({"cover": "20000000"}, "'cover' reported 20000000: not an amount value"),
    ({"cover": "20000000 NZD"}, "'cover' reported 20000000 NZD: currency NZD, not AUD; "
                                "amounts are compared only within one currency"),
])
def test_not_established(op, facts, reason):
    record = _act(f'"cover" {op} MinimumCover', facts)
    assert record.outcome == "blocked"
    assert record.reason == f"precondition not established: {reason}"


def test_precondition_text():
    model = _parse('"cover" != MinimumCover').model
    cmp = next(e for e in model.elements if type(e).__name__ == "Community") \
        .roles[0].actions[0].preconditions[0]
    assert precondition_text(cmp) == '"cover" != MinimumCover'


# ── Standing duties ──────────────────────────────────────────────────────

@pytest.mark.parametrize("reported, verdict", [("10.0%", "kept"), ("12%", "breached")])
def test_keeps_with_equality(reported, verdict):
    duty = 'party Supplier { holds duty }\nburden duty { standing keeps: "share" == MaximumShare state: active }'
    result = _parse('"approvals" == 2', extra=duty)
    assert result.ok, result.errors
    rt = _quiet(Runtime.build_from_spec, result.model,
                clock=DeadlineClock(utc_offset=timezone(timedelta(hours=10))))
    record = rt.check_live_violations(as_at=datetime.fromisoformat("2027-01-01T09:00+10:00"),
                                      facts={"share": reported})
    assert record.effects == (
        f"{verdict} 'duty' held by 'Supplier': 'share' {reported} == 10% (MaximumShare) "
        f"at as_at 2027-01-01T09:00:00+10:00",)
