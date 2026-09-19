"""
Layer 2 — AM-92: V-08 (sub-delegation check) becomes token-aware and
order-independent (`toolchain/el_validator.py`).

Problem: V-08 used `_find_parent_delegation()`, which returned the FIRST
Delegation in declaration order whose delegate matched the sub-delegating
agent — ignoring which token was actually being passed on, and ignoring
every other incoming Delegation. With >=2 distinct incoming Delegations to
one agent, the verdict depended on which was declared first. Live repro:
FinanceParty/LegalParty each commit a burden into SettlementAgent (one
permits sub-delegation, one doesn't); SettlementAgent sub-delegates only
FinanceParty's burden onward. Pre-fix, swapping the declaration order of
the two incoming Delegations flipped the verdict from "ok" to a false
positive blaming the WRONG (LegalParty's) delegation.

Fix — token-aware (S1), order-independent by construction (S3): for each
token a sub-delegating Delegation `d` transfers, look up the incoming,
genuine (non-structural) Delegations to `d`'s delegator that structurally
name that same token (read off `el_reasoner.delegation_graph()`'s already-
extracted fields — no re-derivation). If one forbids sub-delegation, that
is the genuine V-08 violation, naming that specific token and that
specific parent. Conservative fallback (S2) when a token is unmatched by
any incoming Delegation, or `d` has neither `transfers_burden` nor
`transfers_token_group` at all: every incoming Delegation must permit
sub-delegation — byte-identical, for a single-parent agent, to the pre-
AM-92 verdict AND message (confirmed empirically against the entire
tracked corpus: zero diffs).

Deliberate scope boundary: an incoming Delegation with NEITHER transfer
field set can never S1-match a specific token (it has no structural token
to match against) — it only ever participates in the S2 fallback. So if
some OTHER incoming Delegation structurally matches and permits a token,
a neither-field incoming Delegation to the same agent does not block that
token even though it itself forbids sub-delegation in general. This is a
conservative-on-single-parent design choice, not an oversight — S2 is
only reached when NO incoming Delegation makes any structural claim on
the token at all.

One error per (d, forbidding parent Delegation), deduplicated: if one
parent forbids several of d's tokens, all of them are named, sorted and
comma-joined, in a single error.

`_find_parent_delegation()` is deleted — its only caller was V-08 itself,
and no test referenced it directly.
"""
import itertools

from el_parser import parse, parse_string
from el_validator import validate_spec


# ── The repro, in all 6 declaration-order permutations, both token choices ─

_REPRO_PARTS = {
    "finDel": 'delegation finDel { from: FinanceParty to: SettlementAgent '
              'obligation: "Settle payments" transfers_burden: settleBurdenA '
              "sub_delegation_allowed: true }",
    "legDel": 'delegation legDel { from: LegalParty to: SettlementAgent '
              'obligation: "Settle payments" transfers_burden: settleBurdenB }',
}


def _repro_spec(order, sub_token):
    parts = dict(_REPRO_PARTS)
    parts["subDel"] = (
        f'delegation subDel {{ from: SettlementAgent to: SubAgent '
        f'obligation: "Settle payments" transfers_burden: {sub_token} }}'
    )
    body = "\n".join(parts[k] for k in order)
    return f"""
enterprise specification V08Probe
party FinanceParty {{ principal_of SettlementAgent }}
party LegalParty {{ principal_of SettlementAgent }}
agent SettlementAgent {{ principal_of SubAgent }}
agent SubAgent
burden settleBurdenA {{ state: active }}
burden settleBurdenB {{ state: active }}
commitment cA {{ by: FinanceParty obligation: "Settle payments" creates_burden: settleBurdenA }}
commitment cB {{ by: LegalParty obligation: "Settle payments" creates_burden: settleBurdenB }}
{body}
"""


_ALL_ORDERS = list(itertools.permutations(["finDel", "legDel", "subDel"]))

_EXPECTED_FORBIDDEN_MSG = (
    "[V-08] Delegation 'subDel': agent 'SettlementAgent' attempts to "
    "sub-delegate 'settleBurdenB' but parent delegation 'legDel' has "
    "sub_delegation_allowed=false. (§7.10.1)"
)


def test_repro_passing_on_permitted_token_never_errors_any_order():
    for order in _ALL_ORDERS:
        result = parse_string(_repro_spec(order, "settleBurdenA"), validate=True)
        v08 = [e for e in result.errors if e.startswith("[V-08]")]
        assert v08 == [], order


def test_repro_passing_on_forbidden_token_errors_identically_every_order():
    seen = set()
    for order in _ALL_ORDERS:
        result = parse_string(_repro_spec(order, "settleBurdenB"), validate=True)
        v08 = [e for e in result.errors if e.startswith("[V-08]")]
        assert v08 == [_EXPECTED_FORBIDDEN_MSG], order
        seen.add(tuple(v08))
    assert seen == {(_EXPECTED_FORBIDDEN_MSG,)}


# ── Single-parent cases — verdict (and, for S1 matches, message) unchanged ─

def test_single_parent_forbidden_sub_delegation_still_errors():
    spec_text = """
enterprise specification SingleParentForbiddenProbe
party RootParty
agent AgentA
agent AgentB

burden sharedToken { state: active }

commitment c1 { by: RootParty obligation: "Handle it" creates_burden: sharedToken }

delegation d1 { from: RootParty to: AgentA obligation: "Handle it" transfers_burden: sharedToken }
delegation subDel { from: AgentA to: AgentB obligation: "Handle it onward" transfers_burden: sharedToken }
"""
    result = parse_string(spec_text, validate=True)
    v08 = [e for e in result.errors if e.startswith("[V-08]")]
    assert v08 == [
        "[V-08] Delegation 'subDel': agent 'AgentA' attempts to sub-delegate "
        "'sharedToken' but parent delegation 'd1' has sub_delegation_allowed=false. (§7.10.1)"
    ]


def test_single_parent_permitted_sub_delegation_is_ok():
    spec_text = """
enterprise specification SingleParentPermittedProbe
party RootParty
agent AgentA
agent AgentB

burden sharedToken { state: active }

commitment c1 { by: RootParty obligation: "Handle it" creates_burden: sharedToken }

delegation d1 { from: RootParty to: AgentA obligation: "Handle it" transfers_burden: sharedToken sub_delegation_allowed: true }
delegation subDel { from: AgentA to: AgentB obligation: "Handle it onward" transfers_burden: sharedToken }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok, result.errors
    assert not any(e.startswith("[V-08]") for e in result.errors)


def test_no_incoming_delegation_at_all_is_ok():
    """Tweak 4(a): an agent that sub-delegates but has NO incoming
    Delegation of its own — unchanged verdict, no error (there is nothing
    to forbid it)."""
    spec_text = """
enterprise specification NoIncomingProbe
party RootParty
agent AgentA
agent AgentB

burden sharedToken { state: active }

commitment c1 { by: RootParty obligation: "Handle it" creates_burden: sharedToken }

delegation subDel { from: AgentA to: AgentB obligation: "Handle it onward" transfers_burden: sharedToken }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok, result.errors
    assert not any(e.startswith("[V-08]") for e in result.errors)


# ── Group transfer ──────────────────────────────────────────────────────

def test_group_transfer_permitted_incoming_is_ok():
    spec_text = """
enterprise specification GroupPermitProbe
party RootParty
agent AgentA
agent AgentB

burden burdenX { state: active }

token_group grp {
    member: burdenX
}

commitment c1 { by: RootParty obligation: "Handle it" creates_burden: burdenX }

delegation inDel {
    from: RootParty
    to: AgentA
    obligation: "Handle onward"
    transfers_token_group: grp
    sub_delegation_allowed: true
}

delegation subDel {
    from: AgentA
    to: AgentB
    obligation: "Handle further"
    transfers_token_group: grp
}
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok, result.errors
    assert not any(e.startswith("[V-08]") for e in result.errors)


# ── S2 fallback: neither transfer field, one of two parents forbidding ────

_NEITHER_FIELD_PARTS = {
    "d1": 'delegation d1 { from: P1 to: AgentA obligation: "Handle it" sub_delegation_allowed: true }',
    "d2": 'delegation d2 { from: P2 to: AgentA obligation: "Handle it too" }',
    "subDel": 'delegation subDel { from: AgentA to: AgentB obligation: "Handle it onward" }',
}

_EXPECTED_NEITHER_FIELD_MSG = (
    "[V-08] Delegation 'subDel': agent 'AgentA' attempts to sub-delegate but "
    "parent delegation 'd2' has sub_delegation_allowed=false. (§7.10.1)"
)


def _neither_field_spec(order):
    body = "\n".join(_NEITHER_FIELD_PARTS[k] for k in order)
    return f"""
enterprise specification NeitherFieldProbe
party P1
party P2
agent AgentA
agent AgentB
{body}
"""


def test_neither_field_s2_fallback_one_of_two_forbidding_both_orders():
    """Tweak 4(b) (S2 half): message is byte-identical to the pre-AM-92
    format — no token named — since d has neither transfers_burden nor
    transfers_token_group at all."""
    for order in itertools.permutations(_NEITHER_FIELD_PARTS.keys()):
        result = parse_string(_neither_field_spec(order), validate=True)
        v08 = [e for e in result.errors if e.startswith("[V-08]")]
        assert v08 == [_EXPECTED_NEITHER_FIELD_MSG], order


# ── Both-fields Delegation — tokens deduped, one error listing all ─────────

def test_both_fields_delegation_dedupes_into_one_error_listing_all_tokens():
    spec_text = """
enterprise specification BothFieldsProbe
party RootParty
agent AgentA
agent AgentB

burden directBurden { state: active }
burden groupBurden { state: active }

token_group mixedGroup {
    member: directBurden
    member: groupBurden
}

delegation inDel {
    from: RootParty
    to: AgentA
    obligation: "Handle onward"
    transfers_token_group: mixedGroup
}

delegation subDel {
    from: AgentA
    to: AgentB
    obligation: "Handle further"
    transfers_burden: directBurden
    transfers_token_group: mixedGroup
}
"""
    result = parse_string(spec_text, validate=True)
    v08 = [e for e in result.errors if e.startswith("[V-08]")]
    assert v08 == [
        "[V-08] Delegation 'subDel': agent 'AgentA' attempts to sub-delegate "
        "'directBurden', 'groupBurden' but parent delegation 'inDel' has "
        "sub_delegation_allowed=false. (§7.10.1)"
    ]


# ── Party delegator — no check at all ──────────────────────────────────────

def test_party_delegator_is_never_checked():
    spec_text = """
enterprise specification PartyDelegatorProbe
party P1
party P2

burden sharedToken { state: active }

commitment c1 { by: P1 obligation: "Handle it" creates_burden: sharedToken }

delegation d1 { from: P1 to: P2 obligation: "Handle it" transfers_burden: sharedToken }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok, result.errors
    assert not any(e.startswith("[V-08]") for e in result.errors)


# ── Deliberate scope boundary: a neither-field incoming Delegation never ──
# ── S1-matches, so it does not block a token another incoming Delegation ──
# ── structurally permits ───────────────────────────────────────────────────

def test_neither_field_incoming_delegation_does_not_block_a_matched_permitted_token():
    """A neither-field incoming Delegation (d2) forbids sub-delegation in
    general, but it makes no structural claim on settleToken at all — d1
    (which DOES structurally transfer settleToken and permits it) is the
    only S1 match, so subDel passing on settleToken is ok. d2 only matters
    if subDel passes on a token no incoming Delegation names (S2)."""
    spec_text = """
enterprise specification ScopeBoundaryProbe
party P1
party P2
agent AgentA
agent AgentB

burden settleToken { state: active }
burden otherToken { state: active }

commitment c1 { by: P1 obligation: "Handle it" creates_burden: settleToken }
commitment c2 { by: P2 obligation: "Handle it generally" creates_burden: otherToken }

delegation d1 { from: P1 to: AgentA obligation: "Handle it" transfers_burden: settleToken sub_delegation_allowed: true }
delegation d2 { from: P2 to: AgentA obligation: "Handle it generally" }
delegation subDel { from: AgentA to: AgentB obligation: "Handle it onward" transfers_burden: settleToken }
"""
    result = parse_string(spec_text, validate=True)
    assert result.ok, result.errors
    assert not any(e.startswith("[V-08]") for e in result.errors)


# ── Multi-error determinism: set of error strings identical across orders ─

def test_multiple_v08_errors_set_identical_across_all_permutations():
    """Tweak 4(c): a spec producing SEVERAL V-08 errors — assert the SET of
    error strings is identical across every declaration-order permutation
    of all four delegations involved (two forbidding incoming, two
    sub-delegations, one per forbidden token)."""
    parts = {
        "d1": 'delegation d1 { from: P1 to: AgentA obligation: "Handle t1" transfers_burden: t1 }',
        "d2": 'delegation d2 { from: P2 to: AgentA obligation: "Handle t2" transfers_burden: t2 }',
        "sub1": 'delegation sub1 { from: AgentA to: AgentB obligation: "Handle t1 onward" transfers_burden: t1 }',
        "sub2": 'delegation sub2 { from: AgentA to: AgentC obligation: "Handle t2 onward" transfers_burden: t2 }',
    }
    expected = {
        "[V-08] Delegation 'sub1': agent 'AgentA' attempts to sub-delegate "
        "'t1' but parent delegation 'd1' has sub_delegation_allowed=false. (§7.10.1)",
        "[V-08] Delegation 'sub2': agent 'AgentA' attempts to sub-delegate "
        "'t2' but parent delegation 'd2' has sub_delegation_allowed=false. (§7.10.1)",
    }

    def spec(order):
        body = "\n".join(parts[k] for k in order)
        return f"""
enterprise specification MultiErrorProbe
party P1
party P2
agent AgentA
agent AgentB
agent AgentC

burden t1 {{ state: active }}
burden t2 {{ state: active }}

commitment c1 {{ by: P1 obligation: "Handle t1" creates_burden: t1 }}
commitment c2 {{ by: P2 obligation: "Handle t2" creates_burden: t2 }}

{body}
"""

    for order in itertools.permutations(parts.keys()):
        result = parse_string(spec(order), validate=True)
        v08 = {e for e in result.errors if e.startswith("[V-08]")}
        assert v08 == expected, order


# ── Other rules unaffected ──────────────────────────────────────────────

def test_other_warnings_and_rules_unaffected_by_a_v08_triggering_spec():
    """A spec that both triggers V-08 and has an unrelated multi-parent
    warning shape must still produce both independently — AM-92 only
    changes V-08's own logic."""
    spec_text = """
enterprise specification V08PlusW16cProbe
party FinanceParty
party LegalParty
agent SettlementAgent
agent SubAgent

burden settleBurdenA { state: active }
burden settleBurdenB { state: active }

commitment cA { by: FinanceParty obligation: "Settle payments" creates_burden: settleBurdenA }
commitment cB { by: LegalParty obligation: "Settle payments" creates_burden: settleBurdenB }

delegation finDel { from: FinanceParty to: SettlementAgent obligation: "Settle payments" transfers_burden: settleBurdenA sub_delegation_allowed: true }
delegation legDel { from: LegalParty to: SettlementAgent obligation: "Settle payments" transfers_burden: settleBurdenB }
delegation subDel { from: SettlementAgent to: SubAgent obligation: "Settle payments" transfers_burden: settleBurdenB }
"""
    result = parse_string(spec_text, validate=True)
    assert any(e.startswith("[V-08]") for e in result.errors)
    assert any(w.startswith("[W-16c]") for w in result.warnings)
    assert not any(w.startswith("[W-16d]") for w in result.warnings)
    assert not any(w.startswith("[W-16e]") for w in result.warnings)


def test_validate_spec_new_signature_still_returns_flat_list():
    result = parse_string(_repro_spec(("finDel", "legDel", "subDel"), "settleBurdenB"), validate=False)
    messages = validate_spec(result.model)
    assert isinstance(messages, list)
    assert any(m.startswith("[V-08]") for m in messages)


# ── Named tracked scenarios ──────────────────────────────────────────────

def test_named_referral_and_consent_scenarios_still_parse_ok():
    for path in (
        "scenarios/referral/referral_scenario.el",
        "scenarios/consent/consent_scenario.el",
    ):
        result = parse(path, validate=True)
        assert result.ok, result.errors
        assert not any(e.startswith("[V-08]") for e in result.errors)
