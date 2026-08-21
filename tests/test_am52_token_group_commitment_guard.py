"""
AM-52: guard el_kripke._delegation_chain_for_token()'s token_group-membership
match (AM-51) against a token's own, independently-declared Commitment root.

Surfaced during a ground-truth re-verification of the 2026-08-19 "Delegation
holder/chain resolution" finding's Problem 2, the same day AM-51 landed:
AM-51's token_group match is keyed purely on group co-membership, with no
awareness of a token's own Commitment at all. That's fine when every group
member is genuinely covered by the same delegation (referralResponseBurden
in referral_scenario.el, the case AM-51 was built for) but wrong when a
member has an independent Commitment root the delegation has nothing to do
with (assessmentSchedulingBurden in both referral_scenario.el and
gp_referral_scenario.el; referralInitiationBurden/clinicalHandoverBurden in
gp_referral_scenario.el, whose Commitment.actor happens to equal the
delegation's own delegator, so a reachability-only guard would have missed
them -- their Commitment.obligation text is what actually disqualifies the
match).

The guard requires BOTH reachability (the Delegation's delegator equals, or
is a one-sided-principal_of descendant of, the Commitment's actor) and text
relevance (the Commitment's own obligation text is consistent with the
Delegation's obligation text, mirroring el_reasoner.py's _walk_chain()
matching) before trusting a token_group-derived match. A token with no
Commitment at all is unaffected -- see
tests/test_delegation_chain_token_group_match.py, still passing unchanged.
"""
from el_kripke import _delegation_chain_for_token
from el_parser import parse, parse_string


def _referral_model():
    result = parse("scenarios/referral/referral_scenario.el", validate=False)
    assert result.ok, result.errors
    return result.model


def _gp_referral_model():
    result = parse("scenarios/gp_referral/gp_referral_scenario.el", validate=False)
    assert result.ok, result.errors
    return result.model


def test_referral_scenario_assessment_scheduling_burden_resolves_to_own_commitment_root():
    """The conflict AM-51 introduced: assessmentSchedulingBurden is a member
    of specialistBurdenGroup (transferred by gpToSpecialistDelegation,
    GPClinician -> SpecialistClinician), but its own Commitment is by
    SpecialistPractice -- structurally unreachable from GPClinician. Must
    now resolve via its own Commitment root, matching ultimate_accountability()
    and the live runtime holder, not the incorrect GPClinician-rooted path."""
    model = _referral_model()
    chain = _delegation_chain_for_token(model, "assessmentSchedulingBurden", "SpecialistClinician")
    assert chain == ["SpecialistPractice", "SpecialistClinician"]


def test_referral_scenario_referral_response_burden_still_resolves_via_token_group_no_regression():
    """The case AM-51 was built for: referralResponseBurden's own Commitment
    (by GPPractice) IS reachable from gpToSpecialistDelegation's delegator
    (GPClinician) via the GPPractice -> GPClinician structural edge, and the
    obligation text is identical -- must still resolve exactly as AM-51 left
    it, unaffected by the new guard."""
    model = _referral_model()
    chain = _delegation_chain_for_token(model, "referralResponseBurden", "SpecialistClinician")
    assert chain == ["GPPractice", "GPClinician", "SpecialistClinician"]


def test_gp_referral_scenario_assessment_scheduling_burden_resolves_to_own_commitment_root():
    """Same conflict shape as referral_scenario.el's case, via
    referralBurdenGroup instead of specialistBurdenGroup: assessmentSchedulingBurden's
    Commitment is by SpecialistParty, unreachable from gpToSpecialistDelegation's
    delegator (GPPracticeParty, no principal_of path to SpecialistParty at all)."""
    model = _gp_referral_model()
    chain = _delegation_chain_for_token(model, "assessmentSchedulingBurden", "SpecialistClinician")
    assert chain == ["SpecialistParty", "SpecialistClinician"]


def test_gp_referral_scenario_referral_initiation_burden_excluded_by_text_not_reachability():
    """referralInitiationBurden's Commitment.actor (GPPracticeParty) equals
    gpToSpecialistDelegation's own delegator (GPPracticeParty) -- a bare
    reachability check would have wrongly passed this. It's the obligation
    text ("Initiate specialist referral...") that correctly disqualifies the
    match against gpToSpecialistDelegation's own text ("Respond to the
    specialist referral..."). True outcome, not forced: the token was never
    actually delegated in this scenario (held directly by GPClinician), and
    GPPracticeParty -> GPClinician is a PAIRED principal_of+delegated_from
    relationship -- deliberately excluded from AM-50's structural edges --
    so the chain does not extend past the queried holder at all."""
    model = _gp_referral_model()
    chain = _delegation_chain_for_token(model, "referralInitiationBurden", "GPClinician")
    assert chain == ["GPClinician"]


def test_gp_referral_scenario_clinical_handover_burden_excluded_by_text_not_reachability():
    """Same shape as the initiation-burden case above -- Commitment.actor
    equals the delegator, text is what disqualifies it."""
    model = _gp_referral_model()
    chain = _delegation_chain_for_token(model, "clinicalHandoverBurden", "GPClinician")
    assert chain == ["GPClinician"]


def test_gp_referral_scenario_referral_response_burden_still_resolves_no_regression():
    """gp_referral_scenario.el's referralResponseBurden has BOTH a direct
    transfers_burden match (unconditional, unaffected by this guard) and
    group membership -- must still resolve exactly as before."""
    model = _gp_referral_model()
    chain = _delegation_chain_for_token(model, "referralResponseBurden", "SpecialistClinician")
    assert chain == ["GPPracticeParty", "SpecialistClinician"]


_REACHABLE_BUT_TEXT_IRRELEVANT_PROBE = """
enterprise specification ReachableButTextIrrelevantProbe

party Alice {
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

commitment burdenOneCommitment {
    by: Alice
    obligation: "Do the first thing"
    creates_burden: burdenOne
}

commitment burdenTwoCommitment {
    by: Alice
    obligation: "Do a completely unrelated second thing"
    creates_burden: burdenTwo
}

delegation aliceToBob {
    from: Alice
    to: Bob
    obligation: "Do the first thing"
    transfers_token_group: aliceBurdenGroup
}
"""


def test_text_relevance_alone_excludes_reachable_but_irrelevant_match():
    """Both burdenOne and burdenTwo are committed by Alice, the same actor
    as aliceToBob's delegator -- reachability alone (actor == delegator)
    would wrongly pass both. burdenOne's obligation text matches the
    delegation's own text and must still extend Alice -> Bob. burdenTwo's
    obligation text ("a completely unrelated second thing") does not, and
    must NOT extend -- confirming the text-relevance check independently
    catches what a reachability-only guard would have missed, mirroring
    gp_referral_scenario.el's real referralInitiationBurden/clinicalHandoverBurden
    cases above."""
    result = parse_string(_REACHABLE_BUT_TEXT_IRRELEVANT_PROBE, validate=True)
    assert result.ok, result.errors
    model = result.model

    assert _delegation_chain_for_token(model, "burdenOne", "Bob") == ["Alice", "Bob"]
    assert _delegation_chain_for_token(model, "burdenTwo", "Bob") == ["Bob"]
