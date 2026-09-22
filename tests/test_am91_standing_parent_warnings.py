"""
Layer 2/4 — AM-91: standing `principal_of` multi-parent — `[W-16e]`
warning and a deterministic fallback in `el_kripke.py`.

AM-90's `[W-16c]` counts only genuine `Delegation`-based parents;
structural `principal_of` affiliations are documented out of scope there.
That left a gap: an agent with >=2 STANDING `principal_of` parents (a
one-sided structural affiliation, not paired with `delegated_from` — see
`el_reasoner._is_standing_affiliation()`), where a token among them has no
`Commitment` of its own, was BOTH order-dependent
(`el_kripke._delegation_chain_for_token()`'s final extension fell back to
first-declared) AND unwarned (docs/CONCEPTS_INDEX.md's AM-88 residual).

AM-91 closes both:
  - `el_reasoner.standing_parents_of(model, agent_name)` — new public
    query, sorted, built entirely on `delegation_graph()`'s structural
    links (`link.structural=True`) — no separate principal_of scan.
  - `el_validator._validate_standing_multi_parent_notice()` — `[W-16e]`,
    built from that exact query (no twin logic), advisory (AM-89 channel,
    never affects `.ok`).
  - `el_kripke._delegation_chain_for_token()`'s final chain-extension
    loop: when an agent has >1 `principal_of` parent and no
    Commitment-anchored choice exists, the fallback is now
    `sorted(candidates)[0]` instead of first-declared — deterministic,
    and exactly what `[W-16e]`'s "the first alphabetically" claim
    describes (see the parity test below, which is what stops the message
    and the fallback from silently diverging).

`[W-16e]` and `[W-16c]` are independent: an agent can trigger either,
both, or neither, depending on which kind of parent edge it has.
"""
import itertools

from el_parser import parse, parse_string
from el_reasoner import standing_parents_of
from el_kripke import _delegation_chain_for_token
from el_validator import validate_spec


# ── [W-16e] positive, order-invariance, and the message/behaviour parity ──

_NO_COMMIT_PARTS = {
    "p1": "party P1 { principal_of AgentA }",
    "p2": "party P2 { principal_of AgentA }",
    "p3": "party P3 { principal_of AgentA }",
}

_NO_COMMIT_EXPECTED_W16E = (
    "[W-16e] Agent 'AgentA' has 3 standing principal_of parents: P1, P2, P3. "
    "For a token with no Commitment of its own, chain-based views name one of "
    "them (the first alphabetically); the choice is stable but arbitrary. "
    "Which parent's authority applies is application-defined. "
    "See el_reasoner.standing_parents_of(model, 'AgentA')."
)


def _no_commitment_spec(parts_order):
    body = "\n".join(_NO_COMMIT_PARTS[k] for k in parts_order)
    return f"""
enterprise specification NoCommitmentThreeParentProbe
{body}
agent AgentA
agent AgentB

burden burdenNoCommit {{
    state: active
}}

token_group grpNC {{
    member: burdenNoCommit
}}

community DummyCommunity {{
    objective: "Ground burdenNoCommit via role holds, not a Commitment (V-15)"
    role HolderRole {{
        holds burdenNoCommit
    }}
}}

delegation grpDel {{
    from: AgentA
    to: AgentB
    obligation: "Handle onward"
    transfers_token_group: grpNC
}}
"""


def test_w16e_fires_with_expected_message():
    result = parse_string(_no_commitment_spec(["p1", "p2", "p3"]), validate=True)
    assert result.ok is True
    w16e = [w for w in result.warnings if w.startswith("[W-16e]")]
    assert len(w16e) == 1
    assert w16e[0] == _NO_COMMIT_EXPECTED_W16E


def test_w16e_order_invariant_across_all_permutations():
    seen = set()
    for order in itertools.permutations(_NO_COMMIT_PARTS.keys()):
        result = parse_string(_no_commitment_spec(order), validate=True)
        w16e = [w for w in result.warnings if w.startswith("[W-16e]")]
        assert len(w16e) == 1, order
        seen.add(w16e[0])
    assert seen == {_NO_COMMIT_EXPECTED_W16E}


def test_parity_chain_fallback_names_standing_parents_of_first_entry():
    """The message vs. behaviour parity test: for every declaration order,
    _delegation_chain_for_token()'s extension for the Commitment-less
    token must equal sorted(standing_parents_of(model, agent))[0] — the
    exact claim [W-16e]'s "the first alphabetically" wording makes. This
    is what stops the message and the fallback from silently diverging if
    either is ever changed independently."""
    for order in itertools.permutations(_NO_COMMIT_PARTS.keys()):
        result = parse_string(_no_commitment_spec(order), validate=False)
        parents = standing_parents_of(result.model, "AgentA")
        assert parents == ["P1", "P2", "P3"], order  # sorted, order-independent

        chain = _delegation_chain_for_token(result.model, "burdenNoCommit", "AgentB")
        assert chain == [sorted(parents)[0], "AgentA", "AgentB"], order
        assert chain[0] == "P1"


# ── Negatives ────────────────────────────────────────────────────────────

def test_single_standing_parent_produces_no_w16e():
    spec_text = """
enterprise specification SingleStandingParentProbe
party P1 { principal_of AgentA }
agent AgentA
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok is True
    assert not any(w.startswith("[W-16e]") for w in result.warnings)


def test_paired_principal_of_delegated_from_does_not_count_as_standing():
    """A paired principal_of + delegated_from relationship is already
    covered by a real Delegation (el_reasoner._is_standing_affiliation) —
    it must never be counted as a second 'standing' parent alongside a
    genuine one-sided affiliation."""
    spec_text = """
enterprise specification PairedProbe
party P1 { principal_of AgentA }
party P2 { principal_of AgentA }
agent AgentA {
    delegated_from P2
}
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok is True
    parents = standing_parents_of(result.model, "AgentA")
    assert parents == ["P1"]
    assert not any(w.startswith("[W-16e]") for w in result.warnings)


def test_delegation_only_multi_parent_triggers_w16c_only_not_w16e():
    """Two genuine Delegation-based parents, and neither party declares
    principal_of at all — isolates W-16c from W-16e cleanly (no
    principal_of edges exist here for W-16e to find)."""
    spec_text = """
enterprise specification DelegationOnlyProbe
party FinanceParty
party LegalParty
agent SettlementAgent

burden settleBurdenA { state: active }
burden settleBurdenB { state: active }

commitment cA { by: FinanceParty obligation: "Settle payments" creates_burden: settleBurdenA }
commitment cB { by: LegalParty obligation: "Settle payments" creates_burden: settleBurdenB }

delegation finDel { from: FinanceParty to: SettlementAgent obligation: "Settle payments" transfers_burden: settleBurdenA }
delegation legDel { from: LegalParty to: SettlementAgent obligation: "Settle payments" transfers_burden: settleBurdenB }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok is True
    assert any(w.startswith("[W-16c]") for w in result.warnings)
    assert not any(w.startswith("[W-16e]") for w in result.warnings)


def test_agent_with_both_kinds_of_multi_parent_gets_both_warnings():
    """An agent that is both the delegate of >=2 distinct Delegations AND
    has >=2 standing principal_of parents (a disjoint set of principals,
    not the same ones) triggers both [W-16c] and [W-16e] independently."""
    spec_text = """
enterprise specification BothKindsProbe
party StandingP1 { principal_of SettlementAgent }
party StandingP2 { principal_of SettlementAgent }
party FinanceParty
party LegalParty
agent SettlementAgent

burden settleBurdenA { state: active }
burden settleBurdenB { state: active }

commitment cA { by: FinanceParty obligation: "Settle payments" creates_burden: settleBurdenA }
commitment cB { by: LegalParty obligation: "Settle payments" creates_burden: settleBurdenB }

delegation finDel { from: FinanceParty to: SettlementAgent obligation: "Settle payments" transfers_burden: settleBurdenA }
delegation legDel { from: LegalParty to: SettlementAgent obligation: "Settle payments" transfers_burden: settleBurdenB }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok is True
    w16c = [w for w in result.warnings if w.startswith("[W-16c]")]
    w16e = [w for w in result.warnings if w.startswith("[W-16e]")]
    assert len(w16c) == 1
    assert len(w16e) == 1
    assert w16e[0] == (
        "[W-16e] Agent 'SettlementAgent' has 2 standing principal_of parents: "
        "StandingP1, StandingP2. For a token with no Commitment of its own, "
        "chain-based views name one of them (the first alphabetically); the choice "
        "is stable but arbitrary. Which parent's authority applies is "
        "application-defined. See el_reasoner.standing_parents_of(model, 'SettlementAgent')."
    )


# ── standing_parents_of() parity with the message ──────────────────────────

def test_standing_parents_of_output_matches_w16e_message_content():
    result = parse_string(_no_commitment_spec(["p1", "p2", "p3"]), validate=True)
    parents = standing_parents_of(result.model, "AgentA")
    assert parents == ["P1", "P2", "P3"]

    w16e = [w for w in result.warnings if w.startswith("[W-16e]")][0]
    for p in parents:
        assert p in w16e
    assert f"has {len(parents)} standing principal_of parents" in w16e


def test_standing_parents_of_unknown_agent_returns_empty():
    result = parse_string(_no_commitment_spec(["p1", "p2", "p3"]), validate=False)
    assert standing_parents_of(result.model, "NoSuchAgent") == []


# ── Named tracked scenarios ──────────────────────────────────────────────

def test_named_referral_and_consent_scenarios_unchanged():
    """[W-16e] itself fires on neither file, unaffected by AM-95.

    AM-95: referral_scenario.el now carries exactly one [W-16g] — a
    genuine tracked-corpus true positive (SpecialistClinician:
    GPClinician + SpecialistPractice), not a regression; see AM-95's
    amendment entry.

    AM-96 found two genuine tracked-corpus [W-16h] true positives here
    (aiAnalysisPermit, required but never granted); AM-97 fixed the
    scenario content — see AM-97's amendment entry. consent_scenario.el
    is warning-free again."""
    result = parse("scenarios/referral/referral_scenario.el", validate=True)
    assert result.ok, result.errors
    assert not any(w.startswith("[W-16e]") for w in result.warnings)
    assert result.warnings == [
        "[W-16g] Agent 'SpecialistClinician' has 2 declared parents across all "
        "channels: GPClinician (gpToSpecialistDelegation, delegated_from), "
        "SpecialistPractice (standing principal_of). Principals are collectively "
        "responsible (§7.10.1); delegated_from is itself a self-sufficient static "
        "declaration (§6.6.8 NOTE 3) and is counted here even with no backing "
        "Delegation. How these authorities combine is application-defined; the "
        "toolchain does not compose them. See "
        "el_reasoner.all_declared_parents_of(model, 'SpecialistClinician')."
    ]

    result = parse("scenarios/consent/consent_scenario.el", validate=True)
    assert result.ok, result.errors
    assert result.warnings == [], f"unexpectedly produced: {result.warnings}"


def test_federation_consent_scenario_produces_exactly_one_w16e():
    """The one real, tracked-corpus hit found during AM-91 recon:
    federation_consent_scenario.el's SpecialistParty has two standing
    principal_of parents (GPParty, SpecialistPracticeParty). This is a
    true positive, advisory, and the scenario file itself is not
    modified — pinning the exact string here, on the named tracked file,
    per the maintainer's instruction."""
    result = parse("scenarios/consent/federation_consent_scenario.el", validate=True)
    assert result.ok, result.errors
    assert result.warnings == [
        "[W-16e] Agent 'SpecialistParty' has 2 standing principal_of parents: "
        "GPParty, SpecialistPracticeParty. For a token with no Commitment of its "
        "own, chain-based views name one of them (the first alphabetically); the "
        "choice is stable but arbitrary. Which parent's authority applies is "
        "application-defined. See el_reasoner.standing_parents_of(model, 'SpecialistParty')."
    ]


def test_warnings_never_affect_ok():
    result = parse_string(_no_commitment_spec(["p1", "p2", "p3"]), validate=True)
    assert result.ok is True
    assert result.errors == []
    assert len(result.warnings) >= 1


def test_validate_spec_itself_returns_the_same_w16e_message():
    """validate_spec()'s own contract is unaffected — same flat list,
    [W-16e] included, unsplit (the split into .errors/.warnings is
    parse()-only, AM-89)."""
    result = parse_string(_no_commitment_spec(["p1", "p2", "p3"]), validate=False)
    messages = validate_spec(result.model)
    assert any(m.startswith("[W-16e]") for m in messages)
