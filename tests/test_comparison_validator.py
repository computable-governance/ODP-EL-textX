"""
2.1.0-13 — comparison and envelope validation (errors).

  comparison-type      the limit is a number, percentage or amount literal
                       (amount code in the ISO 4217 form), or a Policy of
                       type integer, decimal, number, percentage or amount;
  fact-key-clash       one fact key read two ways (plain and comparison, or
                       comparisons of different kinds or currencies);
  comparison-in-step   a comparison in a Step precondition, which no engine
                       path enforces;
  envelope-currency    an amount initial_value with envelope amounts in
                       another currency;
  envelope-membership  the initial_value inside every envelope rule.

Every message ends "(clause to be confirmed)".

Layer 2 (validator) tests per tests/README.md's strategy.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_parser import parse, parse_string


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_RULES = ("comparison-type", "fact-key-clash", "comparison-in-step",
          "envelope-currency", "envelope-membership")
_CITATION = "(clause to be confirmed)"

_POLICIES = """
policy MinimumCover : amount { initial_value: 20000000 AUD }
policy MaximumShare : percentage { initial_value: 10% }
policy MinimumStaff : integer { initial_value: 5 }
policy Ratio : decimal { initial_value: 0.75 }
policy Count : number { initial_value: 3 }
policy Label : string { initial_value: "x" }
policy Flag : boolean { initial_value: true }
policy Window : duration { initial_value: 60 days }
policy Cutoff : date { initial_value: 2026-11-30 }
policy Tier : TierOptions { initial_value: gold }
policy LowerCover : amount { initial_value: 5 aud }
"""


def _errors(body):
    result = _quiet(parse_string, "enterprise specification V\n" + _POLICIES + body)
    assert result.model is not None, result.errors
    return [e for e in result.errors if e.startswith(tuple(f"[{r}]" for r in _RULES))]


def _actions(*actions):
    """actions: (name, [preconditions]) pairs."""
    body = "\n".join(
        f"        action {name} {{ actor: r "
        + " ".join(f"precondition: {p}" for p in pres) + " }"
        for name, pres in actions)
    return f"""
party H
community C {{
    objective: "o"
    H fills r
    role r {{
{body}
    }}
}}
"""


def _rules(errors):
    return [e[1:e.index("]")] for e in errors]


# ── comparison-type ──────────────────────────────────────────────────────

@pytest.mark.parametrize("limit", [
    "20000000 AUD", "10%", "4.25%", "5", "2.5",
    "MinimumCover", "MaximumShare", "MinimumStaff", "Ratio", "Count",
])
def test_comparable_limits(limit):
    assert _errors(_actions(("a", [f'"x" >= {limit}']))) == []


@pytest.mark.parametrize("limit, policy_type", [
    ("Label", "string"), ("Flag", "boolean"), ("Tier", "TierOptions"),
])   # 2.2.0-6: Window (duration) and Cutoff (date) are comparable
def test_policy_of_another_type_refused(limit, policy_type):
    assert _errors(_actions(("a", [f'"x" >= {limit}']))) == [
        f"[comparison-type] Action 'a': precondition \"x\" >= {limit}: limit {limit} is a "
        f"policy of type '{policy_type}'; a comparison takes a policy of type integer, "
        f"decimal, number, percentage, amount, date, instant or duration. {_CITATION}"]


@pytest.mark.parametrize("limit", ["Window", "Cutoff"])
def test_time_policy_limits_comparable(limit):
    # 2.2.0-6: refused in 2.1.0
    assert _errors(_actions(("a", [f'"x" >= {limit}']))) == []


def test_sixty_sec_refused():
    # 2.2.0-4: "60 day" is a duration; "60 sec" is still an amount.
    assert _errors(_actions(("a", ['"x" <= 60 sec']))) == [
        "[comparison-type] Action 'a': precondition \"x\" <= 60 sec: limit 60 sec has "
        "currency code 'sec', not three upper-case letters A-Z (ISO 4217 form); a "
        f"duration's unit is minute, hour, day, week, month or year. {_CITATION}"]


@pytest.mark.parametrize("limit", ["5 aud", "5 Aud", "LowerCover"])
def test_lower_case_code_refused(limit):
    assert _rules(_errors(_actions(("a", [f'"x" >= {limit}'])))) == ["comparison-type"]


# ── fact-key-clash ───────────────────────────────────────────────────────

def test_plain_and_comparison_clash():
    assert _errors(_actions(("a", ['"cover" >= 5 AUD']), ("b", ['"cover"']))) == [
        "[fact-key-clash] Fact 'cover' is read in more than one way (a plain fact in "
        "Action 'b'; an amount in AUD in Action 'a'); one reported value cannot satisfy "
        f"both. Use a different fact key for each reading. {_CITATION}"]


@pytest.mark.parametrize("first, second", [
    ('"k" >= 5 AUD', '"k" <= 10%'),
    ('"k" >= 5 AUD', '"k" >= 5 NZD'),
    ('"k" >= 5', '"k" <= 10%'),
    ('"k" >= MinimumCover', '"k" >= 5'),
])
def test_comparisons_of_different_kinds_clash(first, second):
    assert _rules(_errors(_actions(("a", [first]), ("b", [second])))) == ["fact-key-clash"]


@pytest.mark.parametrize("first, second", [
    ('"k" >= 5 AUD', '"k" <= 50000000 AUD'),
    ('"k" >= 5', '"k" <= 7.5'),
    ('"k" >= MinimumCover', '"k" <= 30000000 AUD'),
    ('"k" >= 5', '"other"'),
])
def test_same_reading_no_clash(first, second):
    assert _errors(_actions(("a", [first]), ("b", [second]))) == []


def test_plain_preconditions_alone_never_clash():
    assert _errors(_actions(("a", ['"ready"']), ("b", ['"ready"']))) == []


# ── comparison-in-step ───────────────────────────────────────────────────

def _process(*preconditions):
    pre = " ".join(f"precondition: {p}" for p in preconditions)
    return f"""
party H
community C {{
    objective: "o"
    H fills r
    role r {{ action go {{ actor: r }} }}
    process P {{ initiates: "s" terminates: "e"
        step s1 {{ actor: r {pre}
            step s2 {{ actor: r precondition: "nested" >= 1 }} }}
    }}
}}
"""


def test_comparison_in_step_refused_nested_too():
    errors = _errors(_process('"cover" >= 5 AUD'))
    assert errors[0] == (
        "[comparison-in-step] Step 's1': precondition \"cover\" >= 5 AUD is never checked: "
        "Step preconditions are not enforced. Put the comparison on the Action. "
        f"{_CITATION}")
    assert any(e.startswith("[comparison-in-step] Step 's2'") for e in errors)


def test_plain_step_precondition_not_flagged():
    errors = [e for e in _errors(_process('"ready"')) if "'s1'" in e]
    assert errors == []


# ── envelope-currency ────────────────────────────────────────────────────

@pytest.mark.parametrize("envelope", [
    "one of [250 NZD, 300 AUD]", "range of [10 NZD to 500 NZD]",
])
def test_envelope_currency(envelope):
    errors = _errors(f"policy F : amount {{ initial_value: 250 AUD envelope {{ {envelope} }} }}")
    assert errors == [
        "[envelope-currency] Policy 'F': initial_value 250 AUD is in AUD, but its envelope "
        "holds amounts in NZD; amounts are compared only within one currency. "
        f"{_CITATION}"]


def test_same_currency_no_envelope_currency_error():
    assert _errors("policy F : amount { initial_value: 250 AUD "
                   "envelope { range of [10 AUD to 500 AUD] } }") == []


# ── envelope-membership ──────────────────────────────────────────────────

@pytest.mark.parametrize("policy", [
    "policy I : integer { initial_value: 5 envelope { one of [1, 5, 9] } }",
    "policy I : integer { initial_value: 5 envelope { one of [5.0] } }",          # by value
    "policy I : decimal { initial_value: 4.50 envelope { one of [4.5] } }",
    "policy I : integer { initial_value: 1 envelope { range of [1 to 10] } }",   # ends included
    "policy I : integer { initial_value: 10 envelope { range of [1 to 10] } }",
    "policy W : duration { initial_value: 2 weeks envelope { one of [14 days] } }",
    "policy W : duration { initial_value: 60 days envelope { range of [1 month to 1 year] } }",
    "policy D : date { initial_value: 2026-06-30 envelope { range of [2026-01-01 to 2026-06-30] } }",
    "policy T : instant { initial_value: 2026-11-30T17:00+10:00 "
    "envelope { one of [2026-11-30T07:00Z] } }",                                  # by moment
    "policy P : percentage { initial_value: 10% envelope { one of [5%, 10%] range of [0% to 15%] } }",
    "policy F : amount { initial_value: 250 AUD envelope { range of [10 AUD to 500 AUD] } }",
    "policy O : TierOptions { initial_value: gold envelope { one of [bronze, gold] } }",
    "policy N : integer { initial_value: 7..9 envelope { range of [1 to 10] } }",
])
def test_member(policy):
    assert _errors(policy) == []


@pytest.mark.parametrize("policy, text", [
    ("policy I : integer { initial_value: 5 envelope { one of [1, 2, 3] } }",
     "initial_value 5 is not one of its envelope 'one of' values [1, 2, 3]"),
    ("policy I : integer { initial_value: 11 envelope { range of [1 to 10] } }",
     "initial_value 11 is not within its envelope range [1 to 10]"),
    ("policy W : duration { initial_value: 2 days envelope { range of [1 week to 1 month] } }",
     "initial_value 2 days is not within its envelope range [1 week to 1 month]"),
    ("policy F : amount { initial_value: 600 AUD envelope { range of [10 AUD to 500 AUD] } }",
     "initial_value 600 AUD is not within its envelope range [10 AUD to 500 AUD]"),
    ("policy O : TierOptions { initial_value: gold envelope { one of [bronze, silver] } }",
     "initial_value \"gold\" is not one of its envelope 'one of' values [\"bronze\", \"silver\"]"),
    ("policy I : integer { initial_value: 5 envelope { one of [5 days] } }",
     "initial_value 5 is not one of its envelope 'one of' values [5 days]"),
])
def test_not_a_member(policy, text):
    name = policy.split()[1]
    assert f"[envelope-membership] Policy '{name}': {text}. {_CITATION}" in _errors(policy)


def test_every_rule_must_hold():
    errors = _errors("policy I : integer { initial_value: 5 "
                     "envelope { one of [5, 6] range of [6 to 10] } }")
    assert _rules(errors) == ["envelope-membership"]


@pytest.mark.parametrize("policy", [
    "policy R : integer { initial_value: 5 envelope { range of [10 to 1] } }",         # range-ends
    "policy R : integer { initial_value: 5 envelope { range of [1 to 10 days] } }",    # range-ends
    "policy D : date { initial_value: 2026-02-30 envelope { one of [2026-03-01] } }",  # calendar-date
    "policy F : amount { initial_value: 250 AUD envelope { range of [10 NZD to 50 NZD] } }",
])
def test_no_double_report(policy):
    assert "envelope-membership" not in _rules(_errors(policy))


# ── Shipped scenarios ────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("path", sorted(
    p for p in (_REPO / "scenarios").rglob("*.el") if p.name != "ecommerce_scenario.el"
), ids=lambda p: p.name)
def test_shipped_scenarios_pass(path):
    result = _quiet(parse, path)
    assert result.model is not None
    assert [e for e in result.errors if e.startswith(tuple(f"[{r}]" for r in _RULES))] == []
