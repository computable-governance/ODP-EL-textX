"""
Layer 2 — V-NEW-10: transfers_burden / transfers_token_group mutual
exclusivity on DelegationDecl.

Documented in docs/el_grammar_amendments.md ("V-NEW-10 — Mutual exclusion
of transfers_burden and transfers_token_group in DelegationDecl"),
registered in el_validator.py's _validate_delegations() as part of AM-51
(2026-08-22) — completing the latent token_group-membership gap in
el_kripke._delegation_chain_for_token() (see
tests/test_delegation_chain_token_group_match.py) and redirecting
referral_scenario.el's gpToSpecialistDelegation off the dual-declaration
that would otherwise trip this rule.

Minimal inline specs via parse_string(), same throwaway-fixture pattern as
test_v17_burden_embargo_conflict.py.
"""
from el_parser import parse, parse_string


_V_NEW_10_DUAL_DECLARATION = """
enterprise specification VNew10DualDeclarationProbe

party Alice {
    holds burdenOne
}

party Bob {
}

burden burdenOne {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden burdenTwo {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

token_group aliceBurdenGroup {
    member: burdenOne
    member: burdenTwo
}

commitment aliceCommitment {
    by: Alice
    obligation: "Do the group of things"
    creates_burden: burdenOne
}

delegation aliceToBob {
    from: Alice
    to: Bob
    obligation: "Do the group of things"
    transfers_burden: burdenOne
    transfers_token_group: aliceBurdenGroup
}
"""


def test_v_new_10_fires_on_dual_declaration():
    """A Delegation declaring both transfers_burden and
    transfers_token_group simultaneously must be flagged — the two fields
    are mutually exclusive per the documented rule."""
    result = parse_string(_V_NEW_10_DUAL_DECLARATION, validate=True)
    assert not result.ok
    assert any('V-NEW-10' in e for e in result.errors)


def test_v_new_10_does_not_fire_on_referral_scenario():
    """referral_scenario.el's gpToSpecialistDelegation previously declared
    both fields; redirected (AM-51) to transfers_token_group only. Must not
    trip V-NEW-10 now."""
    result = parse("scenarios/referral/referral_scenario.el", validate=True)
    assert result.ok, result.errors
    assert not any('V-NEW-10' in e for e in result.errors)
