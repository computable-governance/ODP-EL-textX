"""
AM-42 — optional enforcement field on NormativePolicy (§7.9.4).

Grammar: NormativePolicy gained `('enforcement' ':' enforcement=NormativePolicyEnforcement)?`.
NormativePolicyEnforcement reuses the existing EnforcementMode rule
('optimistic' | 'pessimistic', already defined for Policy's own
Enforcement construct) by reference — `('policed' mode=EnforcementMode) |
(unpoliced?='unpoliced')` — deliberately omitting Enforcement's
'mechanism' sub-field, per NormativePolicy's lightweight design
(docs/CONCEPTS_INDEX.md, "NormativePolicy scope").

A prior attempt at this amendment introduced a second, differently-named
EnforcementMode rule with policed_pessimistic/policed_optimistic/unpoliced
literals; that collided with the existing rule name and broke parsing of
gp_referral_scenario.el's own (unrelated) `enforcement policed pessimistic`
usage. This file's fixtures exercise both the reused-vocabulary shape and
the mutual exclusivity of mode vs. unpoliced on one instance.

Minimal Layer 1 (grammar/parse) tests per tests/README.md's strategy —
throwaway fixtures, not a full scenario, except where the real referral
scenario is checked directly (AuthorshipBasis/ConsentRightsBasis).
"""
from pathlib import Path

from el_parser import parse, parse_string


_HEADER = 'enterprise specification EnforcementProbe\n\n'

_SCENARIO = Path(__file__).resolve().parent.parent / "scenarios" / "referral" / "referral_scenario.el"


def _find(model, cls_name, name=None):
    matches = [e for e in model.elements if type(e).__name__ == cls_name]
    if name is None:
        return matches
    return next(e for e in matches if e.name == name)


def test_enforcement_policed_pessimistic_resolves():
    src = _HEADER + (
        'normative_policy TestAct {\n'
        '    source: "Test Act 2026"\n'
        '    kind: legislation\n'
        '    enforcement: policed pessimistic\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    policy = _find(result.model, 'NormativePolicy', 'TestAct')
    assert policy.enforcement.mode == 'pessimistic'
    assert policy.enforcement.unpoliced is False


def test_enforcement_policed_optimistic_resolves():
    src = _HEADER + (
        'normative_policy TestAct {\n'
        '    source: "Test Act 2026"\n'
        '    kind: guideline\n'
        '    enforcement: policed optimistic\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    policy = _find(result.model, 'NormativePolicy', 'TestAct')
    assert policy.enforcement.mode == 'optimistic'
    assert policy.enforcement.unpoliced is False


def test_enforcement_unpoliced_resolves():
    src = _HEADER + (
        'normative_policy TestAct {\n'
        '    source: "Test Act 2026"\n'
        '    kind: guideline\n'
        '    enforcement: unpoliced\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    policy = _find(result.model, 'NormativePolicy', 'TestAct')
    assert policy.enforcement.mode is None
    assert policy.enforcement.unpoliced is True


def test_enforcement_absent_defaults_to_none():
    """enforcement is optional — a NormativePolicy without it must not
    error, and .enforcement itself (not a sub-field) must be None."""
    src = _HEADER + (
        'normative_policy TestAct {\n'
        '    source: "Test Act 2026"\n'
        '    kind: guideline\n'
        '}\n'
    )
    result = parse_string(src, validate=True)
    assert result.ok, result.errors

    policy = _find(result.model, 'NormativePolicy', 'TestAct')
    assert policy.enforcement is None


def test_enforcement_mode_and_unpoliced_are_mutually_exclusive():
    """Grammar-level guarantee (confirmed by direct syntax-error test, not
    just absence of a counterexample): the ordered-choice alternation in
    NormativePolicyEnforcement makes mode-set-and-unpoliced-True
    unreachable. Combining 'policed <mode>' with 'unpoliced' in one clause
    is a syntax error, not a value that silently sets both fields."""
    src = _HEADER + (
        'normative_policy TestAct {\n'
        '    source: "Test Act 2026"\n'
        '    kind: guideline\n'
        '    enforcement: policed pessimistic unpoliced\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert not result.ok
    assert any('SYNTAX' in e for e in result.errors)


def test_referral_scenario_authorship_and_consent_enforcement():
    """AuthorshipBasis and ConsentRightsBasis (added under AM-41, scenario
    migration 2026-07-22) both declare enforcement: policed pessimistic —
    privacy legislation isn't optional/voluntary."""
    result = parse(_SCENARIO, validate=True)
    assert result.ok, result.errors

    for name in ('AuthorshipBasis', 'ConsentRightsBasis'):
        policy = _find(result.model, 'NormativePolicy', name)
        assert policy.enforcement.mode == 'pessimistic'
        assert policy.enforcement.unpoliced is False
