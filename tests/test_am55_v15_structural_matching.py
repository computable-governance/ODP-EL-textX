"""
AM-55: structural-first matching for V-15 (el_validator.py).

Extends AM-54's fix (el_reasoner.py's _walk_chain()/
_find_roots_from_delegations()) to the validator layer -- same
conceptual gap (free-text obligation matching with no structural
option), same fix shape, different layer. Surfaced while writing AM-54's
own test fixtures: V-15 rejected both MultiHopRoleConferredProbe (a
role-conferred delegation root with no Commitment at all) and
TextDriftProbe (a later hop's obligation text deliberately reworded),
requiring a validate=False workaround (logged as its own open finding,
docs/CONCEPTS_INDEX.md, 2026-08-22).

V-15 now checks a Delegation's structural reference
(transfers_burden/transfers_token_group) first: is at least one
referenced token's origin resolvable via a Commitment naming it, or a
Role 'holds' naming it (AM-53-style)? Free-text obligation matching
against CommitmentDecl.obligation applies only to a Delegation with no
structural reference at all (grammar-legal, ground-truth confirmed zero
live examples -- see AM-54's amendment entry).
"""
from el_parser import parse_string


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


def test_role_conferred_delegation_chain_validates_cleanly():
    """burdenX has no Commitment at all, but IS role-held (roleA) --
    both delegations transferring it must validate without a V-15 error,
    now that role-holds grounding is checked."""
    result = parse_string(_MULTI_HOP_ROLE_CONFERRED_PROBE, validate=True)
    assert result.ok, result.errors


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


def test_drifted_obligation_text_no_longer_blocks_validation():
    """qToR's obligation text shares no substring with pCommitment's or
    pToQ's -- pre-AM-55, this exact-match text check flagged it. Both
    hops reference burdenY, which IS Commitment-backed -- must validate
    cleanly regardless of qToR's own wording."""
    result = parse_string(_TEXT_DRIFT_PROBE, validate=True)
    assert result.ok, result.errors


_ORPHANED_TOKEN_PROBE = """
enterprise specification OrphanedTokenProbe

party X
party Y

burden burdenOrphan {
    state: active
    deadline: "1 hour"
}

delegation xToY {
    from: X
    to: Y
    obligation: "Do the orphan thing"
    transfers_burden: burdenOrphan
}
"""


def test_genuine_v15_violation_still_fires_structural_case():
    """burdenOrphan has no Commitment AND no Role holds it -- a real
    orphaned transfer, not a text-drift false positive. Must still be
    flagged."""
    result = parse_string(_ORPHANED_TOKEN_PROBE, validate=True)
    assert not result.ok
    assert any("V-15" in e for e in result.errors)
    assert any("burdenOrphan" in e for e in result.errors)


_TEXT_ONLY_NO_STRUCTURAL_REF_PROBE = """
enterprise specification TextOnlyNoStructuralRefProbe

party X
party Y

burden burdenZ {
    state: active
    deadline: "1 hour"
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


def test_text_only_fallback_still_works_for_delegation_with_no_structural_reference():
    """No scenario file today has a Delegation lacking both
    transfers_burden and transfers_token_group, but the grammar permits
    it -- the original free-text check must still apply and pass here."""
    result = parse_string(_TEXT_ONLY_NO_STRUCTURAL_REF_PROBE, validate=True)
    assert result.ok, result.errors


_TEXT_ONLY_MISMATCH_PROBE = """
enterprise specification TextOnlyMismatchProbe

party X
party Y

burden burdenZ {
    state: active
    deadline: "1 hour"
}

commitment xCommitment {
    by: X
    obligation: "Handle the matter"
    creates_burden: burdenZ
}

delegation xToY {
    from: X
    to: Y
    obligation: "Completely different wording"
}
"""


def test_text_only_fallback_still_fires_on_genuine_mismatch():
    """Same shape as above, but the delegation's obligation text doesn't
    match the Commitment's -- with no structural reference to fall back
    on, this must still be flagged exactly as pre-AM-55."""
    result = parse_string(_TEXT_ONLY_MISMATCH_PROBE, validate=True)
    assert not result.ok
    assert any("V-15" in e for e in result.errors)
