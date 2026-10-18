"""
2.1.0-11 — comparison grammar.

A precondition may compare a value the caller reports on the act with a
limit: `precondition: "insurance cover" >= 20000000 AUD`, or with a policy
at its value: `precondition: "insurance cover" >= MinimumCover`. Operators
>= <= > < (2.2.0-2: also == !=); operands a number, percentage or amount
literal, or a Policy.
The DSL compares; it does not compute. Plain preconditions parse as
before. (In 2.1.0-11 alone the engine refused every comparison as "not
established"; 2.1.0-12 judges them.)

Layer 1 (grammar/parse) tests per tests/README.md's strategy.
"""
import contextlib
import io
import re
from decimal import Decimal
from pathlib import Path

import pytest

from el_domain import Amount, Comparison, Percentage
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _src(preconditions, in_step=False):
    pre = "\n".join(f"            precondition: {p}" for p in preconditions)
    action = (f"        action assess {{\n            actor: r\n"
              f"{'' if in_step else pre}\n        }}")
    process = (f'    process P {{ initiates: "start" terminates: "end"\n'
               f"        step s1 {{ actor: r\n{pre}\n        }} }}" if in_step else "")
    return f"""
enterprise specification ComparisonProbe

policy MinimumCover : amount {{ initial_value: 20000000 AUD }}
policy MaximumShare : percentage {{ initial_value: 10% }}

party Assessor

community C {{
    objective: "probe"
    Assessor fills r
    role r {{
{action}
    }}
{process}
}}
"""


def _parse(*preconditions):
    return _quiet(parse_string, _src(preconditions), validate=False)


def _preconditions(*preconditions):
    result = _parse(*preconditions)
    assert result.ok, result.errors
    community = next(e for e in result.model.elements if type(e).__name__ == "Community")
    return community.roles[0].actions[0].preconditions


# ── Each operator and operand ────────────────────────────────────────────

@pytest.mark.parametrize("op", [">=", "<=", ">", "<"])
def test_each_operator(op):
    (cmp,) = _preconditions(f'"insurance cover" {op} 20000000 AUD')
    assert isinstance(cmp, Comparison)
    assert (cmp.fact, cmp.op) == ("insurance cover", op)


@pytest.mark.parametrize("operand, cls, value", [
    ("20000000 AUD", Amount, 20000000),
    ("20000000.00 AUD", Amount, Decimal("20000000.00")),
    ("10%", Percentage, 10),
    ("4.25%", Percentage, Decimal("4.25")),
    ("5", int, 5),
    ("2.5", Decimal, Decimal("2.5")),
])
def test_each_literal(operand, cls, value):
    (cmp,) = _preconditions(f'"x" >= {operand}')
    assert isinstance(cmp.literal, cls)
    assert getattr(cmp.literal, "value", cmp.literal) == value
    assert cmp.policy is None


def test_amount_literal_keeps_its_code():
    (cmp,) = _preconditions('"insurance cover" >= 20000000 AUD')
    assert cmp.literal.code == "AUD"


@pytest.mark.parametrize("policy", ["MinimumCover", "MaximumShare"])
def test_policy_operand(policy):
    (cmp,) = _preconditions(f'"x" <= {policy}')
    assert cmp.literal is None
    assert cmp.policy.name == policy


def test_two_character_operator_is_not_read_as_one():
    (cmp,) = _preconditions('"x" >= 5')
    assert cmp.op == ">=" and cmp.literal == 5


# ── Plain preconditions unchanged, order kept ────────────────────────────

def test_plain_precondition_is_still_a_string():
    assert _preconditions('"cover confirmed"') == ["cover confirmed"]


def test_mixed_preconditions_keep_declared_order():
    pre = _preconditions('"registered"', '"insurance cover" >= MinimumCover', '"vetted"')
    assert pre[0] == "registered" and pre[2] == "vetted"
    assert isinstance(pre[1], Comparison)


def test_step_precondition_may_compare():
    result = _quiet(parse_string, _src(['"share" <= 10%'], in_step=True), validate=False)
    assert result.ok, result.errors
    community = next(e for e in result.model.elements if type(e).__name__ == "Community")
    (cmp,) = community.processes[0].steps[0].preconditions
    assert isinstance(cmp, Comparison) and isinstance(cmp.literal, Percentage)


# ── Refused forms ────────────────────────────────────────────────────────

@pytest.mark.parametrize("pre", [
    '"x" => 5', '"x" = 5', '"x" =< 5',                   # typos (== and != parse from 2.2.0-2)
    '"x" >= +60 days', '"x" >= -60 days',                 # 2.2.0-4: no signed duration
    '"x" >= 60.5 days',                                   # a whole number of a unit
    '"x" >= 20,000,000 AUD',                              # no digit grouping
    '"x" >= +5', '"x" >= 1e3', '"x" >= .5',               # 2.1.0 number forms
    '"x" >= "five"', '"x" >= true',                       # no string or boolean literal
    '5 >= "x"',                                           # the fact comes first
])
def test_refused(pre):
    assert not _parse(pre).ok


def test_unknown_policy_operand_refused():
    result = _parse('"x" >= NoSuchPolicy')
    assert not result.ok and "NoSuchPolicy" in result.errors[0]


def test_lower_case_unit_parses_as_an_amount_code():
    # "60 sec" reads as an amount with code 'sec' (sec is no duration
    # unit). It can never match a reported amount, whose code must be
    # three upper-case letters. 2.2.0-4: "60 day" is a duration.
    (cmp,) = _preconditions('"x" >= 60 sec')
    assert isinstance(cmp.literal, Amount) and cmp.literal.code == "sec"
    (cmp,) = _preconditions('"x" >= 60 day')
    assert type(cmp.literal).__name__ == "CompareDuration"
    assert (cmp.literal.value, cmp.literal.unit) == (60, "day")


# ── A comparison precondition reaches the engine (judged from 2.1.0-12) ─

def test_comparison_precondition_is_judged():
    # 2.1.0-11 refused every comparison as not established; 2.1.0-12 judges
    # it (tests/test_comparison_judging.py has the details).
    model = _parse('"insurance cover" >= 20000000 AUD').model
    rt = _quiet(Runtime.build_from_spec, model)
    record = _quiet(rt.advance, "assess", "Assessor", {})
    assert record.reason == "precondition not established: 'insurance cover' not reported"
    record = _quiet(rt.advance, "assess", "Assessor", {"insurance cover": "25000000 AUD"})
    assert record.outcome == "ok"


def test_plain_precondition_behaviour_unchanged():
    model = _parse('"registered"').model
    rt = _quiet(Runtime.build_from_spec, model)
    record = _quiet(rt.advance, "assess", "Assessor", {})
    assert record.outcome == "blocked"
    assert record.reason == "precondition not satisfied: 'registered'"
    assert _quiet(rt.advance, "assess", "Assessor", {"registered": True}).outcome == "ok"


# ── No three-letter keyword can follow a comparison operand ─────────────

_GRAMMAR = (Path(__file__).resolve().parent.parent / "grammar" / "v2" / "el_grammar.tx").read_text()


def _rule_body(name):
    m = re.search(rf'(?ms)^{name}\s*:(.*?);[ \t]*$', _GRAMMAR)
    assert m, name
    return m.group(1)


def _alternatives(body):
    alts, depth, start = [], 0, 0
    for i, ch in enumerate(body):
        depth += {'(': 1, ')': -1}.get(ch, 0)
        if ch == '|' and depth == 0:
            alts.append(body[start:i])
            start = i + 1
    return alts + [body[start:]]


def _first_keywords(name, seen=()):
    if name in ("ID", "STRING", "INT") or name in seen:
        return set()
    out = set()
    for alt in _alternatives(_rule_body(name)):
        tok = re.findall(r"'[^']*'|\w+\s*[+?*]?=\s*\w+|\w+", alt)[0]
        out |= ({tok.strip("'")} if tok.startswith("'")
                else _first_keywords(tok.split("=")[-1], seen + (name,)))
    return out


def test_no_three_letter_keyword_follows_a_comparison_operand():
    # A comparison ends a PreconditionDecl, which is an item of an Action
    # or Step body: what can follow is the first keyword of any body item,
    # or the body's closing brace.
    followers = {"}"}
    for body in ("ActionBodyItem", "StepBodyItem"):
        for alt in _alternatives(_rule_body(body)):
            followers |= _first_keywords(alt.strip())
    assert {"actor", "precondition", "requires_permit", "effect", "emits",
            "declares_violation_of", "step"} <= followers, followers
    three_letter = set(re.findall(r"'([A-Za-z]{3})'", _GRAMMAR))
    assert three_letter
    assert three_letter & followers == set()
