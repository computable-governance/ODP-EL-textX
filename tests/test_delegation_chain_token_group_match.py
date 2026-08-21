"""
Extends el_kripke._delegation_chain_for_token() to match a Delegation via
token_group membership, not just a direct burden reference.

Prior to this fix, the function only matched Delegation.burden — a
Delegation declaring transfers_token_group only (no transfers_burden) was
structurally invisible to it, for any of its group's member tokens.
Confirmed latent (not yet exposed by any committed scenario): every current
transfers_token_group declaration (referral_scenario.el and
gp_referral_scenario.el's gpToSpecialistDelegation) is paired with a
transfers_burden that already provided a direct match, so the gap was never
actually exercised. Fixing it here, in isolation, ahead of
referral_scenario.el's gpToSpecialistDelegation dropping its redundant
transfers_burden (V-NEW-10 — see docs/el_grammar_amendments.md).
"""
from el_kripke import _delegation_chain_for_token
from el_parser import parse_string

_TOKEN_GROUP_ONLY_PROBE = """
enterprise specification TokenGroupOnlyProbe

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
    transfers_token_group: aliceBurdenGroup
}
"""


def test_token_group_only_delegation_extends_chain_for_group_member():
    """No transfers_burden at all on aliceToBob -- the only transfer signal
    is group membership. Must still extend Alice -> Bob for burdenOne
    (a member of aliceBurdenGroup), mirroring what a direct transfers_burden
    match would have done."""
    result = parse_string(_TOKEN_GROUP_ONLY_PROBE, validate=True)
    assert result.ok, result.errors
    model = result.model

    chain = _delegation_chain_for_token(model, "burdenOne", "Bob")
    assert chain == ["Alice", "Bob"]


def test_token_group_only_delegation_extends_chain_for_second_group_member():
    """burdenTwo is also a member of aliceBurdenGroup, with no Commitment
    and no direct transfers_burden anywhere -- confirms the match is on
    group membership generally, not just the token a Commitment happens to
    reference."""
    result = parse_string(_TOKEN_GROUP_ONLY_PROBE, validate=True)
    assert result.ok, result.errors
    model = result.model

    chain = _delegation_chain_for_token(model, "burdenTwo", "Bob")
    assert chain == ["Alice", "Bob"]


def test_token_group_match_does_not_extend_chain_for_non_member_token():
    """A token that is neither transferred by burden nor a member of the
    delegation's token_group must not be pulled into the chain."""
    result = parse_string(_TOKEN_GROUP_ONLY_PROBE, validate=True)
    assert result.ok, result.errors
    model = result.model

    chain = _delegation_chain_for_token(model, "unrelatedBurden", "Bob")
    assert chain == ["Bob"]
