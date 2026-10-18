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
