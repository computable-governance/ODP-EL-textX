"""
Layer 2 — AM-90: multi-parent authority join, warnings side.

Two new advisory validator rules, both read through the AM-89 channel
(ParseResult.warnings — never affects .ok):

  [W-16c] multi-parent notice — an agent/party that is the delegate of
          Delegations from >=2 DISTINCT delegators. Multi-parent is
          legitimate (§7.10.1: "the parties (collectively) become
          principal"); this only names the structure, it never refuses to
          load a spec and never composes the parents' authorities itself
          — that composition is application-defined.
  [W-16d] same-token conflict — one token (transfers_burden, or a
          transfers_token_group member) transferred by >=2 distinct
          Delegations to the SAME delegate (double-source), or by the
          SAME delegator to >=2 DIFFERENT delegates (fork). Sequential
          chains (P->A, then A->B carrying the same token onward) do not
          trigger this.

Both are built entirely from el_reasoner.parents_of() (W-16c) and
el_reasoner.delegation_graph() (both) — no separate re-derivation of a
Delegation's burden/token_group fields anywhere in el_validator.py, so the
warning text and the public parents_of() query can never diverge.

Per §6.4.1/§7.8.7 a token still resolves to exactly one holder — its own
delegation chain stays linear (AM-88 series). Multi-parent is a property
of the AGENT (§7.10.1), which is what these two rules describe.

Out of scope (documented, not fixed here): structural principal_of
affiliations with no Delegation of their own, and to_role Authorizations
(no single resolved agent to attribute them to) — neither counts toward
either rule.
"""
import itertools

from el_parser import parse, parse_string
from el_reasoner import parents_of
from el_validator import validate_spec


# ── Repro-1-shaped multi-parent probe (reused across several tests) ────────

_REPRO1_PARTS = {
    "finDel": 'delegation finDel { from: FinanceParty to: SettlementAgent '
              'obligation: "Settle payments" transfers_burden: settleBurdenA }',
    "legDel": 'delegation legDel { from: LegalParty to: SettlementAgent '
              'obligation: "Settle payments" transfers_burden: settleBurdenB }',
    "authFin": 'authorization authFin { authority: FinanceParty to_agent: SettlementAgent '
               "grants_permit: facilitatePermit }",
}

_REPRO1_EXPECTED_W16C = (
    "[W-16c] Agent 'SettlementAgent' has 2 parents: "
    "FinanceParty (finDel -> settleBurdenA), LegalParty (legDel -> settleBurdenB). "
    "Principals are collectively responsible (§7.10.1). "
    "If these parents' authorities overlap, how they combine is application-defined; "
    "the toolchain does not compose them. "
    "Permits granted to 'SettlementAgent' (authority sources, not necessarily principals): "
    "authFin (FinanceParty: facilitatePermit). "
    "See el_reasoner.parents_of(model, 'SettlementAgent')."
)


def _repro1_spec(parts_order):
    body = "\n".join(_REPRO1_PARTS[k] for k in parts_order)
    return f"""
enterprise specification Repro1Probe
party FinanceParty {{ principal_of SettlementAgent }}
party LegalParty {{ principal_of SettlementAgent }}
agent SettlementAgent

permit facilitatePermit {{ state: active }}
burden settleBurdenA {{ state: active }}
burden settleBurdenB {{ state: active }}

commitment cA {{ by: FinanceParty obligation: "Settle payments" creates_burden: settleBurdenA }}
commitment cB {{ by: LegalParty obligation: "Settle payments" creates_burden: settleBurdenB }}

{body}
"""


def test_repro1_produces_exactly_one_w16c_with_both_parents_and_permit_line():
    result = parse_string(_repro1_spec(["finDel", "legDel", "authFin"]), validate=True)
    assert result.ok is True
    w16c = [w for w in result.warnings if w.startswith("[W-16c]")]
    assert len(w16c) == 1
    assert w16c[0] == _REPRO1_EXPECTED_W16C


def test_repro1_order_invariant_across_all_permutations():
    """Delegations AND the Authorization, in every declaration order —
    identical warning string every time (deterministic sort inside both
    parents_of() and the message builder, not declaration order). Only one
    Authorization here, so this alone doesn't exercise sort order across
    multiple Authorizations — see
    test_order_invariant_across_all_permutations_with_two_authorizations
    below for that."""
    seen = set()
    for order in itertools.permutations(_REPRO1_PARTS.keys()):
        result = parse_string(_repro1_spec(order), validate=True)
        w16c = [w for w in result.warnings if w.startswith("[W-16c]")]
        assert len(w16c) == 1, order
        seen.add(w16c[0])
    assert seen == {_REPRO1_EXPECTED_W16C}


_TWO_AUTH_PARTS = {
    "finDel": 'delegation finDel { from: FinanceParty to: SettlementAgent '
              'obligation: "Settle payments" transfers_burden: settleBurdenA }',
    "legDel": 'delegation legDel { from: LegalParty to: SettlementAgent '
              'obligation: "Settle payments" transfers_burden: settleBurdenB }',
    "authFin": 'authorization authFin { authority: FinanceParty to_agent: SettlementAgent '
               "grants_permit: facilitatePermit }",
    "authThird": 'authorization authThird { authority: ThirdAuthority to_agent: SettlementAgent '
                 "grants_permit: facilitatePermit2 }",
}

_TWO_AUTH_EXPECTED_W16C = (
    "[W-16c] Agent 'SettlementAgent' has 2 parents: "
    "FinanceParty (finDel -> settleBurdenA), LegalParty (legDel -> settleBurdenB). "
    "Principals are collectively responsible (§7.10.1). "
    "If these parents' authorities overlap, how they combine is application-defined; "
    "the toolchain does not compose them. "
    "Permits granted to 'SettlementAgent' (authority sources, not necessarily principals): "
    "authFin (FinanceParty: facilitatePermit), authThird (ThirdAuthority: facilitatePermit2). "
    "See el_reasoner.parents_of(model, 'SettlementAgent')."
)


def _two_auth_spec(parts_order):
    body = "\n".join(_TWO_AUTH_PARTS[k] for k in parts_order)
    return f"""
enterprise specification TwoAuthOrderProbe
party FinanceParty {{ principal_of SettlementAgent }}
party LegalParty {{ principal_of SettlementAgent }}
party ThirdAuthority
agent SettlementAgent

permit facilitatePermit {{ state: active }}
permit facilitatePermit2 {{ state: active }}
burden settleBurdenA {{ state: active }}
burden settleBurdenB {{ state: active }}

commitment cA {{ by: FinanceParty obligation: "Settle payments" creates_burden: settleBurdenA }}
commitment cB {{ by: LegalParty obligation: "Settle payments" creates_burden: settleBurdenB }}

{body}
"""


def test_order_invariant_across_all_permutations_with_two_authorizations():
    """Two Delegations AND two Authorizations, all 24 permutations of
    declaration order — identical warning string every time. Unlike the
    single-Authorization test above, this actually exercises
    parents_of()'s CoGrantedAuthorization sort (by authorization_name),
    not just a trivially-order-invariant one-element list."""
    seen = set()
    for order in itertools.permutations(_TWO_AUTH_PARTS.keys()):
        result = parse_string(_two_auth_spec(order), validate=True)
        w16c = [w for w in result.warnings if w.startswith("[W-16c]")]
        assert len(w16c) == 1, order
        seen.add(w16c[0])
    assert seen == {_TWO_AUTH_EXPECTED_W16C}


# ── Negatives ────────────────────────────────────────────────────────────

def test_single_parent_chain_produces_no_multi_parent_warnings():
    spec_text = """
enterprise specification SingleParentChainProbe
party RootParty
agent AgentA
agent AgentB

burden sharedToken { state: active }

commitment c1 { by: RootParty obligation: "Handle it" creates_burden: sharedToken }

delegation d1 { from: RootParty to: AgentA obligation: "Handle it" transfers_burden: sharedToken sub_delegation_allowed: true }
delegation d2 { from: AgentA to: AgentB obligation: "Handle it onward" transfers_burden: sharedToken }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok, result.errors
    assert result.warnings == []


def test_one_delegator_two_delegations_to_one_delegate_no_w16c():
    """R1: two Delegations from ONE delegator to the same delegate must
    NOT trigger — the trigger is distinct PARENTS, not delegation count."""
    spec_text = """
enterprise specification OneDelegatorTwoDelegationsProbe
party RootParty
agent AgentA

burden tokenOne { state: active }
burden tokenTwo { state: active }

commitment c1 { by: RootParty obligation: "Handle one" creates_burden: tokenOne }
commitment c2 { by: RootParty obligation: "Handle two" creates_burden: tokenTwo }

delegation d1 { from: RootParty to: AgentA obligation: "Handle one" transfers_burden: tokenOne }
delegation d2 { from: RootParty to: AgentA obligation: "Handle two" transfers_burden: tokenTwo }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok is True
    assert not any(w.startswith("[W-16c]") for w in result.warnings)


def test_principal_of_only_multi_parent_structure_is_out_of_scope_for_w16c():
    """Adjustment 5(b): two principal_of parents with NO Delegations at
    all must NOT trigger W-16c — W-16c is documented as covering only
    genuine Delegation-based parents. This exact shape is what AM-91's
    [W-16e] covers instead (see tests/test_am91_standing_parent_warnings.py)
    — updated from AM-90's original "no warning at all" assertion now that
    AM-91 has landed; the scope boundary moved, it didn't disappear."""
    spec_text = """
enterprise specification PrincipalOfOnlyProbe
party P1 { principal_of AgentA }
party P2 { principal_of AgentA }
agent AgentA
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok is True
    assert not any(w.startswith("[W-16c]") for w in result.warnings)


def test_both_fields_delegation_does_not_self_flag_w16d():
    """A single Delegation declaring both transfers_burden and
    transfers_token_group naming the same token (V-NEW-10 violation,
    mirroring gp_referral_scenario.el) must not conflict with itself —
    tokens are deduped per Delegation before grouping."""
    spec_text = """
enterprise specification BothFieldsProbe
party RootParty
agent DelegateAgent

burden directBurden { state: active }
burden groupToken { state: active }

token_group mixedGroup {
    member: directBurden
    member: groupToken
}

commitment c1 { by: RootParty obligation: "Handle direct" creates_burden: directBurden }

delegation bothFieldsDel {
    from: RootParty
    to: DelegateAgent
    obligation: "Handle onward"
    transfers_burden: directBurden
    transfers_token_group: mixedGroup
}
"""
    result = parse_string(spec_text, validate=False)
    assert result.model is not None
    messages = validate_spec(result.model)
    assert not any(m.startswith("[W-16") for m in messages)


# ── W-16d positives ──────────────────────────────────────────────────────

def test_w16d_double_source_same_token_same_delegate():
    spec_text = """
enterprise specification DoubleSourceProbe
party P1
party P2
agent AgentA

burden sharedToken { state: active }

commitment c1 { by: P1 obligation: "Handle shared" creates_burden: sharedToken }

delegation d1 { from: P1 to: AgentA obligation: "Handle shared" transfers_burden: sharedToken }
delegation d2 { from: P2 to: AgentA obligation: "Handle shared too" transfers_burden: sharedToken }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok is True
    w16d = [w for w in result.warnings if w.startswith("[W-16d]")]
    assert len(w16d) == 1
    assert w16d[0] == (
        "[W-16d] Token 'sharedToken' is transferred to 'AgentA' by 2 distinct "
        "delegations: d1, d2. Which transfer takes effect is application-defined; "
        "the toolchain does not resolve it."
    )


def test_w16d_fork_same_token_two_delegates():
    spec_text = """
enterprise specification ForkProbe
party P1
agent AgentA
agent AgentB

burden sharedToken { state: active }

commitment c1 { by: P1 obligation: "Handle shared" creates_burden: sharedToken }

delegation d1 { from: P1 to: AgentA obligation: "Handle shared" transfers_burden: sharedToken }
delegation d2 { from: P1 to: AgentB obligation: "Handle shared" transfers_burden: sharedToken }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok is True
    w16d = [w for w in result.warnings if w.startswith("[W-16d]")]
    assert len(w16d) == 1
    assert w16d[0] == (
        "[W-16d] Token 'sharedToken' is transferred by 'P1' to 2 distinct "
        "delegates: AgentA, AgentB. Which transfer takes effect is "
        "application-defined; the toolchain does not resolve it."
    )
    # A single delegator does not itself create a multi-parent notice for
    # either delegate (each has exactly one parent, P1).
    assert not any(w.startswith("[W-16c]") for w in result.warnings)


# ── parents_of() parity and edge cases ──────────────────────────────────

def test_parents_of_unknown_agent_returns_empty_no_exception():
    result = parse_string(_repro1_spec(["finDel", "legDel", "authFin"]), validate=False)
    records, auths = parents_of(result.model, "NoSuchAgent")
    assert records == []
    assert auths == []


def test_parents_of_output_matches_w16c_message_content():
    result = parse_string(_repro1_spec(["finDel", "legDel", "authFin"]), validate=True)
    records, auths = parents_of(result.model, "SettlementAgent")

    assert [r.parent for r in records] == ["FinanceParty", "LegalParty"]
    assert [r.delegation_name for r in records] == ["finDel", "legDel"]
    assert [r.tokens for r in records] == [["settleBurdenA"], ["settleBurdenB"]]
    assert [a.authorization_name for a in auths] == ["authFin"]
    assert auths[0].authority == "FinanceParty"
    assert auths[0].permit == "facilitatePermit"

    w16c = [w for w in result.warnings if w.startswith("[W-16c]")][0]
    for r in records:
        assert r.parent in w16c
        assert r.delegation_name in w16c
        for tok in r.tokens:
            assert tok in w16c
    for a in auths:
        assert a.authorization_name in w16c
        assert a.authority in w16c
        assert a.permit in w16c


def test_third_authority_appears_only_in_authorization_clause_not_parents():
    """Adjustment 5(d): an Authorization from an authority who is NOT a
    delegator must appear in the authority-sources clause and never be
    counted among the parents (N stays 2, not 3)."""
    spec_text = """
enterprise specification ThirdAuthorityProbe
party FinanceParty { principal_of SettlementAgent }
party LegalParty { principal_of SettlementAgent }
party ThirdAuthority
agent SettlementAgent

permit facilitatePermit { state: active }
burden settleBurdenA { state: active }
burden settleBurdenB { state: active }

commitment cA { by: FinanceParty obligation: "Settle payments" creates_burden: settleBurdenA }
commitment cB { by: LegalParty obligation: "Settle payments" creates_burden: settleBurdenB }

delegation finDel { from: FinanceParty to: SettlementAgent obligation: "Settle payments" transfers_burden: settleBurdenA }
delegation legDel { from: LegalParty to: SettlementAgent obligation: "Settle payments" transfers_burden: settleBurdenB }

authorization authThird { authority: ThirdAuthority to_agent: SettlementAgent grants_permit: facilitatePermit }
"""
    result = parse_string(spec_text, validate=True)
    records, auths = parents_of(result.model, "SettlementAgent")
    assert {r.parent for r in records} == {"FinanceParty", "LegalParty"}
    assert "ThirdAuthority" not in {r.parent for r in records}
    assert [a.authority for a in auths] == ["ThirdAuthority"]

    w16c = [w for w in result.warnings if w.startswith("[W-16c]")][0]
    assert "has 2 parents" in w16c
    assert "ThirdAuthority" not in w16c.split(".")[0]  # not in the "N parents:" clause
    assert "authThird (ThirdAuthority: facilitatePermit)" in w16c


def test_one_parent_two_delegations_plus_second_parent_groups_correctly():
    """Adjustment 5(c): P1 has two delegations to AgentA, P2 has one —
    N=2 (distinct parents), P1's group lists both its delegations."""
    spec_text = """
enterprise specification GroupedProbe
party P1
party P2
agent AgentA

burden t1 { state: active }
burden t3 { state: active }
burden t2 { state: active }

commitment c1 { by: P1 obligation: "Do t1" creates_burden: t1 }
commitment c3 { by: P1 obligation: "Do t3" creates_burden: t3 }
commitment c2 { by: P2 obligation: "Do t2" creates_burden: t2 }

delegation d1a { from: P1 to: AgentA obligation: "Do t1" transfers_burden: t1 }
delegation d1b { from: P1 to: AgentA obligation: "Do t3" transfers_burden: t3 }
delegation d2 { from: P2 to: AgentA obligation: "Do t2" transfers_burden: t2 }
"""
    result = parse_string(spec_text, validate=True)
    w16c = [w for w in result.warnings if w.startswith("[W-16c]")]
    assert len(w16c) == 1
    assert w16c[0] == (
        "[W-16c] Agent 'AgentA' has 2 parents: P1 (d1a -> t1; d1b -> t3), P2 (d2 -> t2). "
        "Principals are collectively responsible (§7.10.1). "
        "If these parents' authorities overlap, how they combine is application-defined; "
        "the toolchain does not compose them. "
        "See el_reasoner.parents_of(model, 'AgentA')."
    )


# ── Named tracked scenarios — no glob, nothing local-only ──────────────────

def test_tracked_reference_scenarios_have_no_multi_parent_warnings():
    for path in (
        "scenarios/referral/referral_scenario.el",
        "scenarios/consent/consent_scenario.el",
    ):
        result = parse(path, validate=True)
        assert result.ok, result.errors
        w16 = [w for w in result.warnings if w.startswith("[W-16c]") or w.startswith("[W-16d]")]
        assert w16 == [], f"{path} unexpectedly produced: {w16}"


def test_warnings_never_affect_ok():
    result = parse_string(_repro1_spec(["finDel", "legDel", "authFin"]), validate=True)
    assert result.ok is True
    assert result.errors == []
    assert len(result.warnings) >= 1
