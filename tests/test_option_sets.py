"""
2.2.0-10 to 2.2.0-12 — options sets.

`options ApprovalStates [pending, approved, rejected]` declares a named set
of options. A Policy whose type is the set's name takes one of its options
(the validator checks its initial_value and envelope values); a type that
names no options set stays unchecked and silent, as in 2.1.0. A comparison
against a Policy of an options type uses == and != only.

Layer 1 (grammar), Layer 2 (validator) and Layer 3 (runtime) tests per
tests/README.md's strategy.
"""
import contextlib
import io

import pytest

from el_domain import OptionSet
from el_parser import parse_string


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _parse(text, validate=False):
    return _quiet(parse_string, text, validate=validate)


_HEAD = "enterprise specification OptionsProbe\n"


# ── Grammar (2.2.0-10) ───────────────────────────────────────────────────

def test_options_set_parses():
    result = _parse(_HEAD + "options ApprovalStates [pending, approved, rejected]\n")
    assert result.model is not None, result.errors
    (oset,) = result.model.elements
    assert isinstance(oset, OptionSet)
    assert oset.name == "ApprovalStates"
    assert oset.options == ["pending", "approved", "rejected"]
    assert oset.parent is result.model


def test_policy_of_an_options_type_parses():
    result = _parse(_HEAD + "options ApprovalStates [pending, approved, rejected]\n"
                    "policy GateState : ApprovalStates {\n"
                    "    initial_value: pending\n"
                    "    envelope { one of [pending, approved] }\n"
                    "}\n")
    assert result.model is not None, result.errors
    policy = result.model.elements[1]
    assert policy.policy_type == "ApprovalStates"
    assert policy.initial_value == "pending"


@pytest.mark.parametrize("name", ["integerCodes", "dateWindows", "Tiers"])
def test_options_set_may_begin_with_a_type_keyword(name):
    result = _parse(_HEAD + f"options {name} [a]\npolicy P : {name} {{ initial_value: a }}\n")
    assert result.model is not None, result.errors
    assert result.model.elements[1].policy_type == name


@pytest.mark.parametrize("text", [
    "options X []",          # at least one option
    "options X [a,]",        # no trailing comma
    "options X [a b]",       # options are comma-separated
    "options X [\"a\"]",     # options are names, not strings
    "options X [1, 2]",      # nor numbers
    "options [a]",           # a name is required
])
def test_refused(text):
    assert _parse(_HEAD + text + "\n").model is None


def test_option_names_are_not_cross_references():
    # An option may share a name with any other element; nothing resolves it.
    result = _parse(_HEAD + "party pending\noptions ApprovalStates [pending, approved]\n")
    assert result.model is not None, result.errors
    assert result.model.elements[1].options == ["pending", "approved"]


def test_runtime_and_verifier_build_with_an_options_set():
    from el_engine import initial_state
    from el_kripke import build_kripke_model
    result = _parse(_HEAD + "options ApprovalStates [pending, approved]\n"
                    "policy GateState : ApprovalStates { initial_value: approved }\n")
    assert result.model is not None, result.errors
    assert initial_state(result.model).policy_values == (("GateState", "approved"),)
    model = _quiet(build_kripke_model, result.model, horizon=3)
    assert len(model.worlds) == 1


# ── Validator (2.2.0-11) ─────────────────────────────────────────────────

def _messages(text, tag):
    result = _parse(_HEAD + text, validate=True)
    assert result.model is not None, result.errors
    return [m for m in result.errors + result.warnings if m.startswith(f"[{tag}]")]


_STATES = "options ApprovalStates [pending, approved, rejected]\n"


@pytest.mark.parametrize("policy", [
    "policy P : ApprovalStates { initial_value: approved }",
    'policy P : ApprovalStates { initial_value: "approved" }',   # a string reads as text
    "policy P : ApprovalStates { initial_value: pending envelope { one of [pending, approved] } }",
    "normative_policy P { source: \"s\" kind: regulation type: ApprovalStates initial_value: rejected }",
])
def test_option_values_accepted(policy):
    result = _parse(_HEAD + _STATES + policy + "\n", validate=True)
    assert result.model is not None, result.errors
    assert result.errors == []


def test_initial_value_not_an_option():
    assert _messages(_STATES + "policy P : ApprovalStates { initial_value: maybe }\n",
                     "policy-value-type") == [
        "[policy-value-type] Policy 'P': initial_value \"maybe\" is not one of the options "
        "of 'ApprovalStates' [pending, approved, rejected]. (clause to be confirmed)"]


def test_envelope_values_not_options():
    found = _messages(_STATES + "policy P : ApprovalStates { initial_value: pending\n"
                      "    envelope { one of [pending, other, 5] } }\n", "policy-value-type")
    assert found == [
        "[policy-value-type] Policy 'P': envelope 'one of' value \"other\" is not one of the "
        "options of 'ApprovalStates' [pending, approved, rejected]. (clause to be confirmed)",
        "[policy-value-type] Policy 'P': envelope 'one of' value 5 is not one of the "
        "options of 'ApprovalStates' [pending, approved, rejected]. (clause to be confirmed)"]


def test_range_ends_not_options():
    found = _messages(_STATES + "policy P : ApprovalStates { initial_value: pending\n"
                      "    envelope { range of [1 to 3] } }\n", "policy-value-type")
    assert [m.split(": ", 1)[1].split(" is ")[0] for m in found] == \
        ["envelope range low end 1", "envelope range high end 3"]


def test_boolean_value_is_not_an_option():
    # true parses as a boolean, not as a name, so an option named true is never matched
    assert len(_messages("options Flags [true, false]\n"
                         "policy P : Flags { initial_value: true }\n", "policy-value-type")) == 1


def test_undeclared_type_stays_silent():
    # As in 2.1.0: a type naming no options set is not checked.
    result = _parse(_HEAD + "policy Tier : TierOptions { initial_value: gold\n"
                    "    envelope { one of [bronze, silver, gold] } }\n", validate=True)
    assert result.errors == [] and result.warnings == []


def test_ok_typed_values_unchanged():
    from pathlib import Path
    from el_parser import parse
    path = Path(__file__).resolve().parent / "examples" / "typed_values" / "ok_typed_values.el"
    assert "options" not in path.read_text()
    result = _quiet(parse, str(path))
    assert result.errors == [] and result.warnings == []


def test_first_declared_set_is_read():
    text = ("options Tiers [gold]\noptions Tiers [silver]\n"
            "policy P : Tiers { initial_value: silver }\n")
    assert len(_messages(text, "policy-value-type")) == 1


def test_option_duplicate():
    assert _messages("options M [courier, post, courier, post, courier]\n",
                     "option-duplicate") == [
        "[option-duplicate] Options 'M': option 'courier' is listed more than once. "
        "(clause to be confirmed)",
        "[option-duplicate] Options 'M': option 'post' is listed more than once. "
        "(clause to be confirmed)"]


def test_option_set_name():
    assert _messages("options date [early, late]\n", "option-set-name") == [
        "[option-set-name] Options 'date': 'date' is a policy type keyword, so a policy "
        "of type date takes date values, never these options. Rename the options set. "
        "(clause to be confirmed)"]


@pytest.mark.parametrize("name", ["dateWindows", "Amounts", "integerCodes"])
def test_option_set_name_beginning_with_a_keyword_accepted(name):
    assert _messages(f"options {name} [a]\n", "option-set-name") == []


def test_keyword_type_policy_unaffected_by_a_keyword_named_set():
    # policy P : date is a date policy, whatever options set is named date
    result = _parse(_HEAD + "options date [early]\npolicy P : date { initial_value: 2026-11-30 }\n",
                    validate=True)
    assert [m.split("]")[0] for m in result.errors] == ["[option-set-name"]


# ── Comparisons (2.2.0-12) ───────────────────────────────────────────────

from el_engine import judge_comparison, read_reported_value  # noqa: E402
from el_runtime import Runtime  # noqa: E402

_CMP_SPEC = """enterprise specification OptionsCompare
options ApprovalStates [pending, approved, rejected]
policy Required : ApprovalStates {{ initial_value: approved }}
party Clerk
community C {{
    objective: "probe"
    Clerk fills clerk
    role clerk {{
        action release {{
            actor: clerk
            precondition: {pre}
        }}
    }}
}}
"""


def _cmp_parse(pre, validate=False):
    return _parse(_CMP_SPEC.format(pre=pre), validate=validate)


def _release(pre, facts):
    result = _cmp_parse(pre)
    assert result.model is not None, result.errors
    return _quiet(_quiet(Runtime.build_from_spec, result.model).advance, "release", "Clerk", facts)


@pytest.mark.parametrize("pre, reported, outcome, reason", [
    ('"approval" == Required', "approved", "ok", None),
    ('"approval" == Required', "pending",  "blocked",
     "precondition not satisfied: 'approval' pending == approved (Required)"),
    ('"approval" != Required', "pending",  "ok", None),
    ('"approval" != Required', "approved", "blocked",
     "precondition not satisfied: 'approval' approved != approved (Required)"),
    ('"approval" == Required', "maybe",    "blocked",
     "precondition not established: 'approval' reported maybe: not one of the options "
     "[pending, approved, rejected]"),
    ('"approval" == Required', "Approved", "blocked",          # names match exactly
     "precondition not established: 'approval' reported Approved: not one of the options "
     "[pending, approved, rejected]"),
])
def test_judged(pre, reported, outcome, reason):
    record = _release(pre, {"approval": reported})
    assert (record.outcome, record.reason) == (outcome, reason)


def test_satisfied_line():
    record = _release('"approval" == Required', {"approval": "approved"})
    assert record.effects[0] == "precondition satisfied: 'approval' approved == approved (Required)"


@pytest.mark.parametrize("facts, reason", [
    ({}, "precondition not established: 'approval' not reported"),
    ({"approval": "unknown"}, "precondition not established: 'approval' not reported"),
    ({"approval": True}, "precondition not established: 'approval' reported a value of type "
                         "bool, not text; send text, e.g. \"approved\""),
])
def test_not_established(facts, reason):
    assert _release('"approval" == Required', facts).reason == reason


@pytest.mark.parametrize("op", [">=", "<=", ">", "<"])
def test_ordering_not_established(op):
    result = _cmp_parse(f'"approval" {op} Required')
    cmp = next(e for e in result.model.elements
               if type(e).__name__ == "Community").roles[0].actions[0].preconditions[0]
    judged = judge_comparison(cmp, {"approval": "approved"})
    assert judged == (None, "'approval': limit approved (Required) is an option; options are "
                            "compared with == and != only")


def test_policy_value_not_an_option_not_established():
    text = _CMP_SPEC.replace("initial_value: approved", "initial_value: maybe")
    result = _parse(text.format(pre='"approval" == Required'))
    record = _quiet(_quiet(Runtime.build_from_spec, result.model).advance,
                    "release", "Clerk", {"approval": "maybe"})
    assert record.reason == ("precondition not established: 'approval': limit maybe (Required) "
                             "has no comparable value")


def test_read_reported_value_option():
    options = ("pending", "approved")
    assert read_reported_value("approved", "option", options) == ("approved", None)
    assert read_reported_value(" approved", "option", options) == \
        (None, "not one of the options [pending, approved]")
    assert read_reported_value("x" * 101, "option", ("x" * 101,))[0] is None


def test_validator_accepts_equality():
    for op in ("==", "!="):
        result = _cmp_parse(f'"approval" {op} Required', validate=True)
        assert result.errors == [] and result.warnings == []


@pytest.mark.parametrize("op", [">=", "<=", ">", "<"])
def test_validator_refuses_ordering(op):
    result = _cmp_parse(f'"approval" {op} Required', validate=True)
    assert result.errors == [
        f"[comparison-type] Action 'release': precondition \"approval\" {op} Required: limit "
        f"Required is a policy of options type 'ApprovalStates'; options are compared with == "
        f"and != only. (clause to be confirmed)"]


def test_value_not_an_option_reported_once():
    text = _CMP_SPEC.replace("initial_value: approved", "initial_value: maybe")
    result = _parse(text.format(pre='"approval" == Required'), validate=True)
    assert [m.split("]")[0] for m in result.errors] == ["[policy-value-type"]


def test_undeclared_type_limit_message_unchanged():
    # A policy whose type names no options set is refused as in 2.2.0-6.
    text = _CMP_SPEC.replace("options ApprovalStates [pending, approved, rejected]\n", "")
    result = _parse(text.format(pre='"approval" == Required'), validate=True)
    assert result.errors == [
        "[comparison-type] Action 'release': precondition \"approval\" == Required: limit "
        "Required is a policy of type 'ApprovalStates'; a comparison takes a policy of type "
        "integer, decimal, number, percentage, amount, date, instant or duration. "
        "(clause to be confirmed)"]


def test_fact_key_clash_names_the_option_reading():
    text = _CMP_SPEC.format(pre='"approval" == Required').replace(
        "            precondition: \"approval\" == Required\n",
        "            precondition: \"approval\" == Required\n"
        "            precondition: \"approval\"\n")
    result = _parse(text, validate=True)
    assert result.errors == [
        "[fact-key-clash] Fact 'approval' is read in more than one way (a plain fact in Action "
        "'release'; an option of 'ApprovalStates' in Action 'release'); one reported value cannot "
        "satisfy both. Use a different fact key for each reading. (clause to be confirmed)"]


def test_keeps_with_an_option_limit():
    text = """enterprise specification OptionsKeeps
options Ratings [green, amber, red]
policy Target : Ratings { initial_value: green }
party Supplier { holds rated }
burden rated {
    standing
    keeps: "rating" == Target
    ends_at: 2027-06-30
    state: active
}
"""
    result = _parse(text, validate=True)
    assert result.model is not None, result.errors
    assert [m.split("]")[0] for m in result.errors] == []
    keeps = result.model.elements[-1].keeps
    assert judge_comparison(keeps, {"rating": "green"}).value is True
    assert judge_comparison(keeps, {"rating": "red"}).value is False
    assert judge_comparison(keeps, {"rating": "blue"}).value is None
