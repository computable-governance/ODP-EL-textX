"""
2.1.0-12 — judging comparison preconditions.

The caller reports a value on the act, as text in the 2.1.0 notation
(facts: {"insurance cover": "25000000.00 AUD"}). The engine reads it
strictly in the kind of the limit (number, percentage or amount; 2.2.0-5
also date, instant or duration, tests/test_time_comparisons.py) and
compares; it does not compute. Amounts are compared only within one
currency, never converted.

- holds: the precondition passes, and the act's effects gain
  "precondition satisfied: <comparison>" (plain preconditions add none);
- fails: the act is refused, "precondition not satisfied: ...";
- not established (not reported, not text, wrong kind, another currency):
  the act is refused, "precondition not established: ...".
A false precondition is reported before one not established, each in
declared order. advance() and declare_violation() share the check.

Layer 3 (runtime) tests per tests/README.md's strategy.
"""
import contextlib
import io
from decimal import Decimal

import pytest

import el_api
from el_api import ExecuteActionRequest
from el_engine import read_reported_value
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """
enterprise specification CoverProbe

policy MinimumCover : amount {{ initial_value: 20000000 AUD }}
policy MaximumShare : percentage {{ initial_value: 10% }}
policy MinimumStaff : integer {{ initial_value: 5 }}
policy Label : string {{ initial_value: "x" }}

party Assessor

community CoverCommunity {{
    objective: "probe"
    Assessor fills r
    role r {{
        action assess {{
            actor: r
{preconditions}
        }}
    }}
}}
"""


def _runtime(*preconditions):
    pre = "\n".join(f"            precondition: {p}" for p in preconditions)
    result = _quiet(parse_string, _SPEC.format(preconditions=pre), validate=False)
    assert result.ok, result.errors
    return _quiet(Runtime.build_from_spec, result.model)


def _act(preconditions, facts):
    if isinstance(preconditions, str):
        preconditions = (preconditions,)
    return _quiet(_runtime(*preconditions).advance, "assess", "Assessor", facts)


# ── Holds and fails, per kind ────────────────────────────────────────────

@pytest.mark.parametrize("pre, reported, holds", [
    ('"cover" >= 20000000 AUD', "25000000.00 AUD", True),
    ('"cover" >= 20000000 AUD', "19999999.99 AUD", False),
    ('"cover" >= MinimumCover', "20000000 AUD", True),          # equal limit
    ('"cover" > MinimumCover', "20000000 AUD", False),
    ('"share" <= 10%', "8.5%", True),
    ('"share" <= MaximumShare', "10.01%", False),
    ('"share" < 10%', "10%", False),
    ('"staff" >= MinimumStaff', "5", True),
    ('"staff" >= 5', "4.99", False),
    ('"staff" >= 5', "5.50", True),                             # integer limit, decimal reading
    ('"ratio" <= 0.75', "0.750", True),
    ('"delta" >= -1', "-0.5", True),
])
def test_holds_or_fails(pre, reported, holds):
    fact = pre.split('"')[1]
    record = _act(pre, {fact: reported})
    if holds:
        assert record.outcome == "ok"
    else:
        assert record.outcome == "blocked"
        assert record.reason.startswith(f"precondition not satisfied: '{fact}' {reported} ")


def test_failing_reason_names_value_operator_and_limit():
    record = _act('"insurance cover" >= MinimumCover', {"insurance cover": "15000000 AUD"})
    assert record.reason == ("precondition not satisfied: 'insurance cover' 15000000 AUD "
                             ">= 20000000 AUD (MinimumCover)")
    record = _act('"insurance cover" >= 20000000 AUD', {"insurance cover": "15000000 AUD"})
    assert record.reason == ("precondition not satisfied: 'insurance cover' 15000000 AUD "
                             ">= 20000000 AUD")


# ── The ledger line for a passed comparison ──────────────────────────────

def test_passed_comparison_adds_an_effects_line():
    rt = _runtime('"registered"', '"insurance cover" >= 20000000 AUD', '"share" <= 10%')
    record = _quiet(rt.advance, "assess", "Assessor",
                    {"registered": True, "insurance cover": "25000000.00 AUD", "share": "8.5%"})
    assert record.outcome == "ok"
    assert record.effects == (
        "precondition satisfied: 'insurance cover' 25000000.00 AUD >= 20000000 AUD",
        "precondition satisfied: 'share' 8.5% <= 10%",
    )
    assert rt._ledger[-1] is record


def test_plain_preconditions_add_no_line():
    record = _act('"registered"', {"registered": True})
    assert record.outcome == "ok" and record.effects == ()


def test_refused_act_carries_no_satisfied_line():
    record = _act(('"insurance cover" >= 20000000 AUD', '"registered"'),
                  {"insurance cover": "25000000 AUD"})
    assert record.outcome == "blocked" and record.effects == ()
    assert record.reason == "precondition not satisfied: 'registered'"


# ── Not established ──────────────────────────────────────────────────────

@pytest.mark.parametrize("facts, reason", [
    ({}, "'cover' not reported"),
    ({"cover": None}, "'cover' not reported"),
    ({"cover": "unknown"}, "'cover' not reported"),
    ({"cover": 25000000}, "'cover' reported a value of type int, not text; send text, e.g. \"25000000.00 AUD\""),
    ({"cover": 25000000.0}, "'cover' reported a value of type float, not text; send text, e.g. \"25000000.00 AUD\""),
    ({"cover": True}, "'cover' reported a value of type bool, not text; send text, e.g. \"25000000.00 AUD\""),
    ({"cover": "25000000"}, "'cover' reported 25000000: not an amount value"),
    ({"cover": "25000000 aud"}, "'cover' reported 25000000 aud: not an amount value"),
    ({"cover": "25000000AUD"}, "'cover' reported 25000000AUD: not an amount value"),
    ({"cover": "25,000,000 AUD"}, "'cover' reported 25,000,000 AUD: not an amount value"),
    ({"cover": "2.5e7 AUD"}, "'cover' reported 2.5e7 AUD: not an amount value"),
    ({"cover": "+25000000 AUD"}, "'cover' reported +25000000 AUD: not an amount value"),
    ({"cover": " 25000000 AUD"}, "'cover' reported  25000000 AUD: not an amount value"),
    ({"cover": "25000000 NZD"},
     "'cover' reported 25000000 NZD: currency NZD, not AUD; amounts are compared only "
     "within one currency"),
])
def test_amount_not_established(facts, reason):
    record = _act('"cover" >= 20000000 AUD', facts)
    assert record.outcome == "blocked"
    assert record.reason == f"precondition not established: {reason}"


@pytest.mark.parametrize("pre, reported, noun, example", [
    ('"share" <= 10%', "8.5", "a percentage", "8.5%"),
    ('"share" <= 10%', "8.5 %", "a percentage", "8.5%"),
    ('"staff" >= 5', "five", "a number", "25000000"),
    ('"staff" >= 5', "٥", "a number", "25000000"),           # Arabic-Indic five
])
def test_wrong_kind_not_established(pre, reported, noun, example):
    fact = pre.split('"')[1]
    record = _act(pre, {fact: reported})
    assert record.reason == (f"precondition not established: '{fact}' reported {reported}: "
                             f"not {noun} value")
    record = _act(pre, {fact: 8})
    assert record.reason.endswith(f"send text, e.g. \"{example}\"")


def test_long_text_is_bounded_in_the_reason():
    reported = "1" * 101
    record = _act('"staff" >= 5', {"staff": reported})
    assert record.reason == ("precondition not established: 'staff' reported "
                             + "1" * 40 + "…: not a number value")


def test_limit_with_no_comparable_value():
    record = _act('"x" >= Label', {"x": "5"})
    assert record.reason == "precondition not established: 'x': limit x (Label) has no comparable value"


# ── Order: false before not established, each in declared order ─────────

def test_false_reported_before_not_established():
    record = _act(('"a" >= 5', '"b" >= 5', '"c" >= 5'), {"b": "1", "c": "2"})
    assert record.reason == "precondition not satisfied: 'b' 1 >= 5"


def test_first_not_established_in_declared_order():
    record = _act(('"a" >= 5', '"b" >= 5'), {})
    assert record.reason == "precondition not established: 'a' not reported"


# ── Reading function ─────────────────────────────────────────────────────

@pytest.mark.parametrize("text, kind, value", [
    ("25000000.00 AUD", "amount", (Decimal("25000000.00"), "AUD")),
    ("8.5%", "percentage", Decimal("8.5")),
    ("-0.5", "number", Decimal("-0.5")),
    ("20000000.50", "number", Decimal("20000000.50")),
])
def test_read_reported_value(text, kind, value):
    assert read_reported_value(text, kind) == (value, None)


@pytest.mark.parametrize("text, kind", [
    ("1e3", "number"), (".5", "number"), ("5.", "number"), ("1,000", "number"),
    ("8.5", "percentage"), ("25000000 AU", "amount"), ("25000000  AUD", "amount"),
    ("1" * 101, "number"),
])
def test_read_reported_value_refused(text, kind):
    value, reason = read_reported_value(text, kind)
    assert value is None and reason.startswith("not ")


# ── declare_violation() shares the check ────────────────────────────────

_DECLARE = """
enterprise specification DeclareProbe
party Gate {{ holds recB }}
agent Dog {{ holds declP }}
burden recB {{ for_action: "rec" state: active deadline: "5 minutes" discharge_mode: strict }}
permit declP {{ for_action: "declRec" state: active }}
commitment GR {{ by: Gate obligation: "record" creates_burden: recB }}
community C {{
    objective: "o"
    Gate fills gw
    Dog fills dec
    role gw {{ action rec {{ actor: gw }} }}
    role dec {{
        action declRec {{
            actor: dec
            requires_permit declP
            declares_violation_of recB
            precondition: "evidence age" <= 30
        }}
    }}
}}
"""


def _declare(facts):
    result = _quiet(parse_string, _DECLARE.format(), validate=False)
    assert result.ok, result.errors
    rt = _quiet(Runtime.build_from_spec, result.model)
    return rt.declare_violation("recB", "Dog", 10, facts=facts)


def test_declaration_refused_by_a_comparison():
    record = _declare({"evidence age": "31"})
    assert record.outcome == "blocked"
    assert record.reason == "precondition not satisfied: 'evidence age' 31 <= 30"
    assert _declare({}).reason == "precondition not established: 'evidence age' not reported"


def test_declaration_carries_the_satisfied_line():
    record = _declare({"evidence age": "12"})
    assert record.outcome == "violation"
    assert record.effects[0] == "precondition satisfied: 'evidence age' 12 <= 30"
    assert record.effects[1].startswith("declared 'recB' held by 'Gate' violated")


# ── Through the API: facts as text ───────────────────────────────────────

@pytest.fixture
def api(monkeypatch):
    rt = _runtime('"insurance cover" >= MinimumCover')
    monkeypatch.setattr(el_api, "_runtime", rt)
    monkeypatch.setattr(el_api, "_active_community", "CoverCommunity")
    return el_api


def test_api_execute_action_with_text_fact(api):
    resp = _quiet(api.execute_action, "Assessor", ExecuteActionRequest(
        action_name="assess", facts={"insurance cover": "25000000.00 AUD"}))
    assert resp.outcome == "ok"
    assert resp.effects == [
        "precondition satisfied: 'insurance cover' 25000000.00 AUD >= 20000000 AUD (MinimumCover)"]


def test_api_execute_action_with_json_number_is_not_established(api):
    resp = _quiet(api.execute_action, "Assessor", ExecuteActionRequest(
        action_name="assess", facts={"insurance cover": 25000000}))
    assert resp.outcome == "blocked"
    assert resp.reason == ("precondition not established: 'insurance cover' reported a value of "
                           "type int, not text; send text, e.g. \"25000000.00 AUD\"")
