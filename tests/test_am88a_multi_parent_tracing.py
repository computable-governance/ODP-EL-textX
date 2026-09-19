"""
Layer 3 — AM-88a: `_build_obligation_descriptors()`'s `walk_chain()`
(`toolchain/el_engine.py`) becomes structural-first and per-token, closing
two single-lineage flaws that only bite when two delegation lineages
converge on one agent:

1. `walk_chain()` used to follow edges by free-text obligation matching and
   take `outgoing[0]` — it never consulted which token a `Delegation`
   actually transfers. Two lineages carrying the *same* obligation text to
   the *same* delegate (e.g. "Settle payments" from both Finance and Legal
   into one settlement agent, each transferring a *different* burden) could
   have one lineage's walk silently continue along the other's onward
   Delegation, producing a holder/chain that belongs to the wrong burden.

2. `sub_delegation_allowed`/`revocable` were re-derived after the walk by
   scanning the whole model for "the last Delegation whose delegate equals
   the resolved holder" — order-dependent, and wrong whenever two
   Delegations share a delegate: both tokens ended up with whichever
   Delegation happened to be declared last, regardless of which one
   actually transferred which token.

Fix: `walk_chain()` now takes `token_name` and matches each outgoing
`Delegation` structurally — `transfers_burden` unconditionally, or
`transfers_token_group` membership guarded by the AM-52 rule (trusted
unconditionally when the token has no Commitment of its own, otherwise only
when the Commitment's own obligation text is relevant to this Delegation's
— see `_commitment_root_for_token()`'s docstring for the concrete
gp_referral_scenario.el case that guard exists to reject). Free-text
matching remains only for a Delegation with neither field (AM-54
ground-truth: none exist in any current scenario, but the grammar permits
it). `sub_delegation_allowed`/`revocable` are now taken from the specific
Delegation that produced the final hop of *this token's own* walk, recorded
during the walk itself rather than re-derived afterward by delegate name.

Regression: every pre-existing descriptor's fields are pinned against an
empirical snapshot taken from the pre-fix code
(tests/fixtures/am88a_obligation_descriptors_snapshot.json, generated via
`dataclasses.asdict()` over every scenario file, git commit f2f5a66) —
confirming this is a pure bug fix with zero behavioural change to any
existing scenario, same convention as
tests/test_am86_obligation_descriptor_roots.py.
"""
import dataclasses
import glob
import itertools
import json

import pytest

from el_engine import _build_obligation_descriptors
from el_kripke import _delegation_chain_for_token
from el_parser import parse, parse_string


_SNAPSHOT_PATH = "tests/fixtures/am88a_obligation_descriptors_snapshot.json"


# ── Byte-identical regression over the full corpus ─────────────────────────

def test_descriptors_byte_identical_to_pre_fix_snapshot():
    """Every parseable scenario file's full descriptor set, compared field-
    by-field against the pre-AM-88a snapshot. Confirms the structural-first
    rewrite changes nothing for any existing scenario — none of them
    exercise the multi-parent-convergence case this amendment targets (see
    docs/CONCEPTS_INDEX.md's AM-88 ground-truth scan)."""
    with open(_SNAPSHOT_PATH) as fh:
        snapshot = json.load(fh)

    checked = 0
    for f in sorted(glob.glob("scenarios/**/*.el", recursive=True)):
        result = parse(f, validate=False)
        if result.model is None:
            continue  # scenarios/ecommerce/ecommerce_scenario.el: pre-existing syntax error
        assert f in snapshot, f"no snapshot entry for {f}"
        descriptors = _build_obligation_descriptors(result.model)
        actual = {name: dataclasses.asdict(d) for name, d in descriptors.items()}
        assert actual == snapshot[f], f"descriptor mismatch in {f}"
        checked += len(actual)

    assert checked == 37


# ── Repro 1 — two lineages carrying identical obligation text converge ─────

def _two_parent_probe(delegation_order):
    """delegation_order: a permutation of ('finDel', 'legDel', 'subDel')."""
    delegations = {
        "finDel": 'delegation finDel { from: FinanceParty to: SettlementAgent '
                  'obligation: "Settle payments" transfers_burden: settleBurdenA '
                  "sub_delegation_allowed: true }",
        "legDel": 'delegation legDel { from: LegalParty to: SettlementAgent '
                  'obligation: "Settle payments" transfers_burden: settleBurdenB }',
        "subDel": 'delegation subDel { from: SettlementAgent to: SubAgent '
                  'obligation: "Settle payments" transfers_burden: settleBurdenA }',
    }
    ordered = "\n".join(delegations[name] for name in delegation_order)
    return f"""
enterprise specification TwoParentProbe
party FinanceParty {{ principal_of SettlementAgent }}
party LegalParty {{ principal_of SettlementAgent }}
agent SettlementAgent {{ principal_of SubAgent }}
agent SubAgent

burden settleBurdenA {{ state: active }}
burden settleBurdenB {{ state: active }}

commitment cA {{ by: FinanceParty obligation: "Settle payments" creates_burden: settleBurdenA }}
commitment cB {{ by: LegalParty obligation: "Settle payments" creates_burden: settleBurdenB }}

{ordered}
"""


@pytest.mark.parametrize(
    "delegation_order",
    list(itertools.permutations(["finDel", "legDel", "subDel"])),
)
def test_repro1_converging_lineages_resolve_per_token(delegation_order):
    """Pre-fix, settleBurdenB's chain incorrectly continued onto subDel (which
    only transfers settleBurdenA), giving holder SubAgent for a token subDel
    never touched. Fixed: each burden's chain follows only the Delegations
    that structurally name it, regardless of declaration order."""
    result = parse_string(_two_parent_probe(delegation_order), validate=False)
    assert result.ok, result.errors
    descriptors = _build_obligation_descriptors(result.model)

    assert descriptors["settleBurdenA"].chain == ["FinanceParty", "SettlementAgent", "SubAgent"]
    assert descriptors["settleBurdenA"].holder == "SubAgent"

    assert descriptors["settleBurdenB"].chain == ["LegalParty", "SettlementAgent"]
    assert descriptors["settleBurdenB"].holder == "SettlementAgent"


@pytest.mark.parametrize(
    "delegation_order",
    list(itertools.permutations(["finDel", "legDel", "subDel"])),
)
def test_repro1_parity_with_kripke_delegation_chain_for_token(delegation_order):
    """Engine and Kripke chains must agree here because the criterion from
    docs/CONCEPTS_INDEX.md's AM-88 recon (item f) holds: each token's root
    actor (FinanceParty / LegalParty) has no unpaired principal_of PARENT of
    its own (both are top-level parties, never the target of anyone else's
    principal_of) — so Kripke's extra backward-through-principal_of step
    never fires here, and the two chains are directly comparable. Verified
    by running both, not assumed."""
    result = parse_string(_two_parent_probe(delegation_order), validate=False)
    assert result.ok, result.errors

    engine_descriptors = _build_obligation_descriptors(result.model)
    for token_name in ("settleBurdenA", "settleBurdenB"):
        engine_chain = engine_descriptors[token_name].chain
        kripke_chain = _delegation_chain_for_token(
            result.model, token_name, engine_descriptors[token_name].holder
        )
        assert engine_chain == kripke_chain, token_name


# ── Repro 2 — sub_delegation_allowed/revocable must not leak across tokens ─

def _two_parent_probe_sda(delegation_order):
    delegations = {
        "finDel": 'delegation finDel { from: FinanceParty to: SettlementAgent '
                  'obligation: "Settle payments" transfers_burden: settleBurdenA '
                  "sub_delegation_allowed: true revocable: true }",
        "legDel": 'delegation legDel { from: LegalParty to: SettlementAgent '
                  'obligation: "Settle payments" transfers_burden: settleBurdenB }',
    }
    ordered = "\n".join(delegations[name] for name in delegation_order)
    return f"""
enterprise specification TwoParentProbe2
party FinanceParty {{ principal_of SettlementAgent }}
party LegalParty {{ principal_of SettlementAgent }}
agent SettlementAgent

burden settleBurdenA {{ state: active }}
burden settleBurdenB {{ state: active }}

commitment cA {{ by: FinanceParty obligation: "Settle payments" creates_burden: settleBurdenA }}
commitment cB {{ by: LegalParty obligation: "Settle payments" creates_burden: settleBurdenB }}

{ordered}
"""


@pytest.mark.parametrize("delegation_order", [("finDel", "legDel"), ("legDel", "finDel")])
def test_repro2_sub_delegation_allowed_and_revocable_are_order_independent(delegation_order):
    """Pre-fix, both tokens took on whichever Delegation into SettlementAgent
    was declared last, so both flipped identically when the two Delegations
    were reordered. Fixed: each token keeps its own Delegation's values
    regardless of declaration order."""
    result = parse_string(_two_parent_probe_sda(delegation_order), validate=False)
    assert result.ok, result.errors
    descriptors = _build_obligation_descriptors(result.model)

    assert descriptors["settleBurdenA"].sub_delegation_allowed is True
    assert descriptors["settleBurdenA"].revocable is True
    assert descriptors["settleBurdenB"].sub_delegation_allowed is False
    assert descriptors["settleBurdenB"].revocable is False


# ── Free-text fallback — a Delegation with neither structural field ────────

_FREE_TEXT_FALLBACK_PROBE = """
enterprise specification FreeTextFallbackProbe

party RootParty
agent LeafAgent

burden textOnlyBurden {
    state: active
}

commitment cRoot {
    by: RootParty
    obligation: "Handle the matter end to end"
    creates_burden: textOnlyBurden
}

delegation freeTextDel {
    from: RootParty
    to: LeafAgent
    obligation: "Handle the matter end to end, in full"
}
"""


def test_free_text_fallback_still_matches_when_delegation_has_no_structural_ref():
    """AM-54 confirmed no scenario in the corpus has a Delegation with
    neither transfers_burden nor transfers_token_group, but the grammar
    permits it (both fields are optional). Constructed here so the fallback
    branch of walk_chain()'s structural-first matching is actually
    exercised, not just theoretically reachable."""
    result = parse_string(_FREE_TEXT_FALLBACK_PROBE, validate=False)
    assert result.ok, result.errors
    descriptors = _build_obligation_descriptors(result.model)

    assert descriptors["textOnlyBurden"].chain == ["RootParty", "LeafAgent"]
    assert descriptors["textOnlyBurden"].holder == "LeafAgent"


# ── Unconditional token_group branch — no Commitment of its own ────────────

_AUTHORIZATION_GROUP_PROBE = """
enterprise specification AuthGroupProbe

party AuthorityParty
agent DelegateAgent

permit facilitatePermit {
    state: active
}

burden authBurden {
    state: active
}

token_group authGroup {
    member: authBurden
}

authorization authGrant {
    authority: AuthorityParty
    grants_permit: facilitatePermit
    creates_burden_on_authority: authBurden
}

delegation authDel {
    from: AuthorityParty
    to: DelegateAgent
    obligation: "Facilitate onward"
    transfers_token_group: authGroup
}
"""


def test_token_group_transfer_trusted_unconditionally_when_token_has_no_commitment():
    """authBurden is rooted at Authorization.auth_burden (AM-87), not a
    Commitment — _commitment_root_for_token() returns None for it, so the
    AM-52 text-relevance guard does not apply and the token_group transfer
    is trusted unconditionally, extending the chain onto DelegateAgent."""
    result = parse_string(_AUTHORIZATION_GROUP_PROBE, validate=False)
    assert result.ok, result.errors
    descriptors = _build_obligation_descriptors(result.model)

    assert descriptors["authBurden"].chain == ["AuthorityParty", "DelegateAgent"]
    assert descriptors["authBurden"].holder == "DelegateAgent"


# ── Both fields set on one Delegation (V-NEW-10 violation, mirroring the ──
# ── real gp_referral_scenario.el shape) — fallthrough to group required ───

_BOTH_FIELDS_PROBE = """
enterprise specification BothFieldsProbe

party RootParty
agent DelegateAgent

permit facilitatePermit {
    state: active
}

burden directBurden {
    state: active
}

burden groupOnlyBurden {
    state: active
}

token_group mixedGroup {
    member: directBurden
    member: groupOnlyBurden
}

commitment cDirect {
    by: RootParty
    obligation: "Handle the direct matter"
    creates_burden: directBurden
}

authorization authGroupOnly {
    authority: RootParty
    grants_permit: facilitatePermit
    creates_burden_on_authority: groupOnlyBurden
}

delegation bothFieldsDel {
    from: RootParty
    to: DelegateAgent
    obligation: "Handle onward"
    transfers_burden: directBurden
    transfers_token_group: mixedGroup
}
"""


def test_both_fields_delegation_falls_through_to_group_for_other_member():
    """bothFieldsDel declares both transfers_burden (directBurden) and
    transfers_token_group (mixedGroup, which also contains groupOnlyBurden)
    — a real V-NEW-10 violation, mirroring gp_referral_scenario.el's
    gpToSpecialistDelegation exactly. groupOnlyBurden has no Commitment of
    its own (rooted at Authorization.auth_burden instead), so once the
    walk correctly falls through to the group check after the burden field
    fails to match it, the guard trusts it unconditionally.

    Under the very first, pre-AM-88a text-only walk_chain(), obligation
    text alone decided every match ("Handle the direct matter" vs. "Handle
    onward" share no substring), so both tokens' chains stayed at
    ['RootParty'] — confirmed by running this exact probe against that
    code. Under the intermediate, since-corrected version reviewed and
    approved as part of AM-88a's own review round (checking burden_name is
    not None and stopping there regardless of match, never falling through
    to check group_tokens at all), directBurden already extended correctly
    (its own burden field matches directly) but groupOnlyBurden stayed
    truncated at ['RootParty'] — the specific gap this test pins. Fixed:
    both extend onto DelegateAgent, matching el_kripke.py's
    _delegation_chain_for_token() exactly."""
    result = parse_string(_BOTH_FIELDS_PROBE, validate=False)
    assert result.ok, result.errors
    descriptors = _build_obligation_descriptors(result.model)

    assert descriptors["directBurden"].chain == ["RootParty", "DelegateAgent"]
    assert descriptors["groupOnlyBurden"].chain == ["RootParty", "DelegateAgent"]

    result2 = parse_string(_BOTH_FIELDS_PROBE, validate=False)
    for token_name in ("directBurden", "groupOnlyBurden"):
        engine_chain = descriptors[token_name].chain
        kripke_chain = _delegation_chain_for_token(
            result2.model, token_name, descriptors[token_name].holder
        )
        assert engine_chain == kripke_chain, token_name


# ── gp_referral_scenario.el — the real AM-52 guard case, unchanged ─────────

def test_gp_referral_scenario_guard_case_unchanged():
    """referralInitiationBurden and clinicalHandoverBurden are Commitment-
    rooted at GPPracticeParty and have no Delegation of their own — they are
    only *group co-members* of referralBurdenGroup, which
    gpToSpecialistDelegation also transfers via transfers_token_group
    alongside transfers_burden: referralResponseBurden (a real, separate
    V-NEW-10 tension in this file, logged separately in
    docs/CONCEPTS_INDEX.md and out of scope here). Without the AM-52
    text-relevance guard, a naive unconditional token_group match makes
    both burdens pick up a spurious extra hop onto SpecialistClinician
    purely from incidental group co-membership — confirmed by prototyping
    the unguarded predicate against this exact file during AM-88 recon.
    With the guard, both chains stay exactly as they were before AM-88a."""
    result = parse("scenarios/gp_referral/gp_referral_scenario.el", validate=False)
    assert result.ok, result.errors
    descriptors = _build_obligation_descriptors(result.model)

    assert descriptors["referralInitiationBurden"].chain == ["GPPracticeParty"]
    assert descriptors["referralInitiationBurden"].holder == "GPPracticeParty"
    assert descriptors["clinicalHandoverBurden"].chain == ["GPPracticeParty"]
    assert descriptors["clinicalHandoverBurden"].holder == "GPPracticeParty"
