"""
AM-53: static-role-anchor fallback in el_reasoner.ultimate_accountability().

Standard-conformance gap: ISO/IEC 15414's own library annex example
(§B.2.4) shows a Burden originating purely from filling a role -- "the
action of filling a borrower role is therefore a speech act, resulting in
a burden representing the obligation to obey the regulations" -- with no
Commitment speech act at all. ultimate_accountability() previously only
had two paths to a root (a matching Commitment, or a matching Delegation
whose obligation text names the burden) and silently returned [] for
everything else -- confirmed live, not theoretical: ereferral_model.el has
zero commitment/delegation blocks anywhere; all 4 of its burdens are
conferred purely via 'holds' inside a Role body.

The fix adds a third, last-resort path: when neither a Commitment nor a
Delegation names the obligation at all, check whether it matches a bare
Burden held by some Role, and if so report that Role + its owning
Community as the nearest static anchor -- returned as a StaticRoleAnchor,
a type structurally distinct from AccountabilityChain, specifically so a
caller cannot mistake a non-final, static-spec-only answer for a resolved
accountable party. This is NOT a claim about who the standard says holds
the token -- see StaticRoleAnchor's own docstring and
docs/CONCEPTS_INDEX.md's "WorldState scope" finding (2026-08-20, §6.4.3):
role-filling for an ordinary Community role is a runtime-only fact
(enroll()), not expressible in the static .el spec, and this function has
no access to it.

Deliberately NOT closed by this fix: escalationNoticeBurden
(referral_scenario.el / gp_referral_scenario.el) -- its origination is
ViolationResponse.obligates (an already-resolved EnterpriseObject
reference), a different, still-open gap (ultimate_accountability() never
reads ViolationResponse at all) that happens to produce the same []
symptom. Confirmed still returns [] below -- not silently treated as
fixed.
"""
from el_reasoner import AccountabilityChain, StaticRoleAnchor, ultimate_accountability
from el_parser import parse


def _ereferral_model():
    result = parse("scenarios/ereferral/ereferral_model.el", validate=False)
    assert result.ok, result.errors
    return result.model


def _referral_model():
    result = parse("scenarios/referral/referral_scenario.el", validate=False)
    assert result.ok, result.errors
    return result.model


def test_referral_burden_resolves_to_static_role_anchor():
    model = _ereferral_model()
    results = ultimate_accountability(model, "referralBurden")
    assert len(results) == 1
    anchor = results[0]
    assert isinstance(anchor, StaticRoleAnchor)
    assert not isinstance(anchor, AccountabilityChain)
    assert anchor.token_name == "referralBurden"
    assert anchor.role_name == "referringClinicianRole"
    assert anchor.community_name == "ReferralEpisodeCommunity"


def test_examination_burden_resolves_to_static_role_anchor():
    model = _ereferral_model()
    results = ultimate_accountability(model, "examinationBurden")
    assert len(results) == 1
    anchor = results[0]
    assert isinstance(anchor, StaticRoleAnchor)
    assert anchor.role_name == "referredToSpecialistRole"
    assert anchor.community_name == "ReferralEpisodeCommunity"


def test_ai_examination_burden_resolves_to_static_role_anchor():
    model = _ereferral_model()
    results = ultimate_accountability(model, "aiExaminationBurden")
    assert len(results) == 1
    anchor = results[0]
    assert isinstance(anchor, StaticRoleAnchor)
    assert anchor.role_name == "aiExaminationRole"
    assert anchor.community_name == "ReferralEpisodeCommunity"


def test_acknowledgement_burden_resolves_to_static_role_anchor():
    model = _ereferral_model()
    results = ultimate_accountability(model, "acknowledgementBurden")
    assert len(results) == 1
    anchor = results[0]
    assert isinstance(anchor, StaticRoleAnchor)
    assert anchor.role_name == "referredToSpecialistRole"
    assert anchor.community_name == "ReferralEpisodeCommunity"


def test_static_role_anchor_describe_states_it_is_not_a_resolved_party():
    model = _ereferral_model()
    anchor = ultimate_accountability(model, "referralBurden")[0]
    text = anchor.describe()
    assert "NOT a resolved accountable party" in text
    assert "referringClinicianRole" in text
    assert "ReferralEpisodeCommunity" in text


def test_escalation_notice_burden_not_fixed_by_this_path_still_empty():
    """escalationNoticeBurden's gap is a DIFFERENT, still-open root cause
    (ViolationResponse.obligates, not Role.holds) -- confirming this fix
    does not silently paper over it. Reported honestly as still returning
    [], not treated as closed."""
    model = _referral_model()
    assert ultimate_accountability(model, "escalationNoticeBurden") == []
    assert ultimate_accountability(model, "notify GP practice") == []


def test_genuinely_nonexistent_obligation_still_returns_not_found():
    """Distinguishing 'truly not found' from 'found, role-anchored': a
    query matching nothing at all -- no Commitment, no Delegation, no
    Role.holds -- must still return the empty list, the same signal as
    before this fix, not a StaticRoleAnchor with fabricated content."""
    model = _ereferral_model()
    assert ultimate_accountability(model, "this obligation does not exist anywhere") == []


def test_existing_commitment_rooted_case_unaffected_no_regression():
    """The Commitment/Delegation path must be completely untouched: same
    AccountabilityChain type, same root, same chain, for a case that
    already resolved before this fix."""
    model = _referral_model()
    results = ultimate_accountability(
        model,
        "Respond to the specialist referral within the agreed timeframe and schedule assessment",
    )
    assert len(results) == 1
    chain = results[0]
    assert isinstance(chain, AccountabilityChain)
    assert not isinstance(chain, StaticRoleAnchor)
    assert chain.root_party == "GPPractice"
    assert chain.current_holder == "SpecialistClinician"
