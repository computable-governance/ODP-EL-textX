"""
AM-54: structural-first matching in _walk_chain()/_find_roots_from_delegations()
(el_reasoner.py), plus root-grounding checks before wrapping a
delegation-only root in AccountabilityChain.

Closes two open findings logged 2026-08-22 (docs/CONCEPTS_INDEX.md,
immediately following the AM-52 Problem-2 entry), both surfaced during
ground-truth re-verification the same day AM-53 landed:

1. _find_roots_from_delegations() could present a role-conferred root
   (no Commitment, held only via a Role's 'holds') as a fully resolved
   AccountabilityChain, with only root_commitment=None as the (easy to
   miss) signal it wasn't real -- AM-53's StaticRoleAnchor fallback never
   covered this code path. Confirmed by construction
   (MultiHopRoleConferredProbe): a role-conferred burden delegated
   A -> B -> C came back as AccountabilityChain(root_party='A', ...)
   instead of a StaticRoleAnchor.

2. _walk_chain()'s recursive obligation-text matching used the ORIGINAL
   query string unchanged at every hop, so a later hop whose own
   obligation text drifted from the original wording silently truncated
   the walk -- independent of the Commitment-vs-role-conferred question
   entirely. Confirmed by construction (TextDriftProbe): a genuinely
   Commitment-backed, 2-hop delegation chain P -> Q -> R reported
   current_holder='Q', silently missing R.

Ground-truth check performed before designing the fix: every Delegation
in every current scenario file already declares transfers_burden or
transfers_token_group (zero exceptions) -- text-only Delegations are
grammar-legal but do not exist live today. The fix makes structural
matching (Delegation.burden / .token_group, mirroring el_kripke.py's
AM-51/52 _delegation_chain_for_token()) authoritative over free-text
obligation matching, with text used ONLY as a fallback for a link that
declares no structural reference at all -- and that fallback stays
inspectable per-hop via DelegationLink.has_structural_ref, not silently
identical to a structural match.

A separate ground-truth check (does the residual "neither Commitment nor
role-holds grounded" root correspond to direct EnterpriseObject.holds?)
found: no. Direct holds is used in the corpus (gp_referral_scenario.el's
GPClinician) but always redundantly alongside an existing Commitment,
never as sole grounding for anything, and the actual residual case (root
neither Commitment- nor role-grounded) has zero live or constructed
examples at all -- so that case is deliberately left at its pre-AM-54
AccountabilityChain/root_commitment=None behaviour, not a new gap this
fix needs to close.
"""
from el_parser import parse_string
from el_reasoner import AccountabilityChain, StaticRoleAnchor, ultimate_accountability


_MULTI_HOP_ROLE_CONFERRED_PROBE = """
enterprise specification MultiHopRoleConferredProbe

party A
party B
party C

community SomeCommunity {
    objective: "Get the thing done"

    role roleA
    {
        holds burdenX
    }

    role roleB
    {
    }

    role roleC
    {
    }
}

burden burdenX {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
    description: "The thing that must be done"
}

delegation aToB {
    from: A
    to: B
    obligation: "Do the thing"
    transfers_burden: burdenX
}

delegation bToC {
    from: B
    to: C
    obligation: "Do the thing"
    transfers_burden: burdenX
}
"""


def test_role_conferred_delegation_root_returns_static_role_anchor_not_chain():
    """A's burden is role-conferred (no Commitment). It's delegated
    A -> B -> C, both hops sharing identical obligation text. The result
    must be a StaticRoleAnchor (root grounded via Role.holds, not a
    resolved party), not a bare AccountabilityChain.

    validate=False: V-15 (el_validator.py) requires every Delegation's
    obligation to trace back to a CommitmentDecl -- it has the same
    conceptual blind spot as pre-AM-54 _walk_chain() for role-conferred
    roots, in a different layer, out of scope here. Parsing (not
    validating) is what this test needs."""
    result = parse_string(_MULTI_HOP_ROLE_CONFERRED_PROBE, validate=False)
    assert result.ok, result.errors
    model = result.model

    results = ultimate_accountability(model, "Do the thing")
    assert len(results) == 1
    anchor = results[0]
    assert isinstance(anchor, StaticRoleAnchor)
    assert not isinstance(anchor, AccountabilityChain)
    assert anchor.role_name == "roleA"
    assert anchor.community_name == "SomeCommunity"


def test_role_conferred_delegation_root_preserves_onward_chain_and_holder():
    """The onward delegation hops and current holder are real,
    structurally-confirmed facts -- must not be silently dropped just
    because the root itself isn't a resolved party."""
    result = parse_string(_MULTI_HOP_ROLE_CONFERRED_PROBE, validate=False)
    assert result.ok, result.errors
    model = result.model

    anchor = ultimate_accountability(model, "Do the thing")[0]
    assert [(l.from_obj, l.to_obj) for l in anchor.chain] == [("A", "B"), ("B", "C")]
    assert anchor.current_holder == "C"
    assert "Further delegated onward" in anchor.describe()
    assert "C" in anchor.describe()


_TEXT_DRIFT_PROBE = """
enterprise specification TextDriftProbe

party P
party Q
party R

burden burdenY {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
    description: "The report burden"
}

commitment pCommitment {
    by: P
    obligation: "Deliver the report"
    creates_burden: burdenY
}

delegation pToQ {
    from: P
    to: Q
    obligation: "Deliver the report"
    transfers_burden: burdenY
}

delegation qToR {
    from: Q
    to: R
    obligation: "Q hands off report duties to R entirely"
    transfers_burden: burdenY
}
"""


def test_structural_match_survives_obligation_text_drift_across_hops():
    """qToR's obligation text shares no substring with the original query
    -- pre-AM-54, the walk silently stopped at Q. Structural matching
    (transfers_burden: burdenY on both hops) must reach R regardless.

    validate=False: this fixture's whole point is drifted obligation text
    on qToR, which V-15 (el_validator.py) rejects for the same reason
    _walk_chain() used to fail -- a separate, text-matching-based
    validator rule with its own analogous gap, out of scope here."""
    result = parse_string(_TEXT_DRIFT_PROBE, validate=False)
    assert result.ok, result.errors
    model = result.model

    results = ultimate_accountability(model, "Deliver the report")
    assert len(results) == 1
    chain = results[0]
    assert isinstance(chain, AccountabilityChain)
    assert chain.root_party == "P"
    assert chain.current_holder == "R"
    assert [(l.from_obj, l.to_obj) for l in chain.chain] == [("P", "Q"), ("Q", "R")]


_NO_STRUCTURAL_REF_PROBE = """
enterprise specification NoStructuralRefProbe

party X
party Y

burden burdenZ {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

commitment xCommitment {
    by: X
    obligation: "Handle the matter"
    creates_burden: burdenZ
}

delegation xToY {
    from: X
    to: Y
    obligation: "Handle the matter"
}
"""


def test_text_fallback_still_works_when_delegation_has_no_structural_reference():
    """No scenario file today has a Delegation lacking both
    transfers_burden and transfers_token_group, but the grammar permits
    it -- the text-match fallback must still resolve this case, and must
    be inspectable as lower-confidence per-hop (DelegationLink.has_structural_ref),
    not silently identical to a structural match."""
    result = parse_string(_NO_STRUCTURAL_REF_PROBE, validate=True)
    assert result.ok, result.errors
    model = result.model

    results = ultimate_accountability(model, "Handle the matter")
    assert len(results) == 1
    chain = results[0]
    assert chain.root_party == "X"
    assert chain.current_holder == "Y"
    assert len(chain.chain) == 1
    assert chain.chain[0].has_structural_ref is False
