"""
Layer 2 — AM-95: declared-parent union across all channels —
`el_reasoner.all_declared_parents_of()` and `[W-16g]`.

AM-90's `[W-16c]` counts only genuine Delegation-based parents; AM-91's
`[W-16e]` counts only standing principal_of parents. Each channel's own
`>=2` threshold is evaluated independently, so an agent with exactly one
parent in each of two or three channels (Delegation, standing
principal_of, delegated_from) triggered neither — invisible to both,
and to the AM-93 `delegated_from`-as-list amendment, which explicitly
logged this as a deliberately untouched gap.

`delegated_from` is itself a self-sufficient static declaration (§6.6.8
NOTE 3) — it needs no backing Delegation to be a genuine declared
parent, so `all_declared_parents_of()` counts it on its own terms, never
requiring a matching Delegation for visibility.

AM-95 closes the gap:
  - `el_reasoner.all_declared_parents_of(model, agent_name)` — new
    public query, sorted, the union of `parents_of()`'s Delegation-based
    parents, `standing_parents_of()`'s standing parents, and every
    `delegated_from` entry's delegator — deduplicated by name across
    channels (a party declared via more than one channel counts once).
  - `el_validator._validate_all_channel_multi_parent_notice()` —
    `[W-16g]`, built from the same three primitives (no twin logic),
    advisory (AM-89 channel, never affects `.ok`).

Non-redundancy: `[W-16g]` fires only when the union is not already
exactly what `[W-16c]` or `[W-16e]` alone would name — if one channel's
own warning already explains the whole set, a third warning naming the
same set would be redundant. `[W-16c]`, `[W-16d]`, and `[W-16e]` are
unchanged — same triggers, same wording, same tests.
"""
import itertools

from el_parser import parse, parse_string
from el_reasoner import all_declared_parents_of


# ── Shared probe builder — one Delegation-channel parent (DelegParent),
# one standing-channel parent (StandingParent), one delegated_from-only
# parent (DFParent), each independently toggleable. ─────────────────────

def _probe(include_delegation, include_standing, include_delegated_from):
    lines = ["enterprise specification ChannelProbe", ""]
    if include_standing:
        lines.append("party StandingParent {\n    principal_of Agent\n}")
    else:
        lines.append("party StandingParent {}")
    if include_delegated_from:
        lines.append("party DFParent {}")
        agent_body = "party Agent {\n    delegated_from DFParent\n}"
    else:
        agent_body = "party Agent {}"
    if include_delegation:
        lines.append("party DelegParent {}")
    lines.append(agent_body)
    lines.append("")
    if include_delegation:
        lines.append(
            'burden probeBurden {\n    state: active\n    discharge_mode: eventual\n'
            '    description: "probe"\n}\n'
        )
        lines.append(
            "commitment probeCommitment {\n"
            "    by: DelegParent\n"
            '    obligation: "probe obligation"\n'
            "    creates_burden: probeBurden\n"
            "}\n"
        )
        lines.append(
            "delegation delegParentDelegation {\n"
            "    from: DelegParent\n"
            "    to: Agent\n"
            '    obligation: "probe obligation"\n'
            "    transfers_burden: probeBurden\n"
            "}\n"
        )
    return "\n".join(lines)


def _w16g(result):
    return [w for w in result.warnings if w.startswith("[W-16g]")]


# ── ThreeChannelProbe: all three channels, one parent each ────────────────

def test_three_channel_probe_fires_once_naming_all_three_sources():
    result = parse_string(_probe(True, True, True), validate=True)
    assert result.ok, result.errors
    assert not any(w.startswith("[W-16c]") for w in result.warnings)
    assert not any(w.startswith("[W-16e]") for w in result.warnings)
    w16g = _w16g(result)
    assert len(w16g) == 1
    assert w16g[0] == (
        "[W-16g] Agent 'Agent' has 3 declared parents across all channels: "
        "DFParent (delegated_from), DelegParent (delegParentDelegation), "
        "StandingParent (standing principal_of). Principals are collectively "
        "responsible (§7.10.1); delegated_from is itself a self-sufficient static "
        "declaration (§6.6.8 NOTE 3) and is counted here even with no backing "
        "Delegation. How these authorities combine is application-defined; the "
        "toolchain does not compose them. See "
        "el_reasoner.all_declared_parents_of(model, 'Agent')."
    )
    assert all_declared_parents_of(result.model, "Agent") == [
        "DFParent", "DelegParent", "StandingParent"
    ]


# ── Each 2-of-3 pairing fires ──────────────────────────────────────────────

def test_pair_delegation_and_standing_fires():
    result = parse_string(_probe(True, True, False), validate=True)
    assert result.ok, result.errors
    assert len(_w16g(result)) == 1


def test_pair_delegation_and_delegated_from_fires():
    result = parse_string(_probe(True, False, True), validate=True)
    assert result.ok, result.errors
    assert len(_w16g(result)) == 1


def test_pair_standing_and_delegated_from_fires():
    result = parse_string(_probe(False, True, True), validate=True)
    assert result.ok, result.errors
    assert len(_w16g(result)) == 1


# ── Single channels: silent (below both individual and union thresholds) ──

def test_delegation_only_produces_no_w16g():
    result = parse_string(_probe(True, False, False), validate=True)
    assert result.ok, result.errors
    assert _w16g(result) == []


def test_standing_only_produces_no_w16g():
    result = parse_string(_probe(False, True, False), validate=True)
    assert result.ok, result.errors
    assert _w16g(result) == []


def test_delegated_from_only_produces_no_w16g():
    result = parse_string(_probe(False, False, True), validate=True)
    assert result.ok, result.errors
    assert _w16g(result) == []


# ── Non-redundancy: a channel already at >=2 on its own ───────────────────

_ALREADY_AT_2_VIA_W16C = """
enterprise specification AlreadyAt2ViaW16c

party DelegParentX {}
party DelegParentY {}
party Agent {}

burden probeBurden {
    state: active
    discharge_mode: eventual
    description: "probe"
}

commitment cX {
    by: DelegParentX
    obligation: "obX"
    creates_burden: probeBurden
}

delegation dX {
    from: DelegParentX
    to: Agent
    obligation: "obX"
    transfers_burden: probeBurden
}

delegation dY {
    from: DelegParentY
    to: Agent
    obligation: "obX"
}
"""


def test_channel_already_at_2_via_w16c_alone_suppresses_w16g():
    """Two genuine Delegations, no other channel contributes a name
    beyond that set: the union equals W-16c's own set exactly, so a
    redundant [W-16g] naming the same two parents is suppressed."""
    result = parse_string(_ALREADY_AT_2_VIA_W16C, validate=True)
    assert result.ok, result.errors
    assert len(_w16g(result)) == 0
    assert any(w.startswith("[W-16c]") for w in result.warnings)


_ALREADY_AT_2_VIA_W16E = """
enterprise specification AlreadyAt2ViaW16e

party StandingX { principal_of Agent }
party StandingY { principal_of Agent }
agent Agent
"""


def test_channel_already_at_2_via_w16e_alone_suppresses_w16g():
    """Symmetric case: two standing principal_of parents, no other
    channel contributes a name beyond that set."""
    result = parse_string(_ALREADY_AT_2_VIA_W16E, validate=True)
    assert result.ok, result.errors
    assert len(_w16g(result)) == 0
    assert any(w.startswith("[W-16e]") for w in result.warnings)


# ── Non-redundancy: a channel at >=2, plus one distinct extra parent ──────

_W16C_PLUS_EXTRA = """
enterprise specification W16cPlusExtra

party DelegParentX {}
party DelegParentY {}
party StandingParentC {
    principal_of Agent
}
party Agent {}

burden probeBurden {
    state: active
    discharge_mode: eventual
    description: "probe"
}

commitment cX {
    by: DelegParentX
    obligation: "obX"
    creates_burden: probeBurden
}

delegation dX {
    from: DelegParentX
    to: Agent
    obligation: "obX"
    transfers_burden: probeBurden
}

delegation dY {
    from: DelegParentY
    to: Agent
    obligation: "obX"
}
"""


def test_w16c_at_2_plus_distinct_extra_parent_fires_w16g_too():
    """W-16c fires for {DelegParentX, DelegParentY}; a third, distinct
    standing parent makes the union a strict superset of W-16c's own
    set — new information neither W-16c nor W-16e stated, so [W-16g]
    fires alongside [W-16c]."""
    result = parse_string(_W16C_PLUS_EXTRA, validate=True)
    assert result.ok, result.errors
    assert any(w.startswith("[W-16c]") for w in result.warnings)
    assert not any(w.startswith("[W-16e]") for w in result.warnings)
    w16g = _w16g(result)
    assert len(w16g) == 1
    assert "DelegParentX" in w16g[0] and "DelegParentY" in w16g[0] and "StandingParentC" in w16g[0]
    assert "has 3 declared parents" in w16g[0]


# ── R1d: a party declared via two channels to the same agent renders as
# ONE entry naming both channels, never duplicated. Assert the exact
# string — not just the underlying set. ────────────────────────────────

_R1D_OVERLAP = """
enterprise specification R1dOverlap

party SameParty {}
party StandingParentC {
    principal_of Agent
}
party Agent {
    delegated_from SameParty
}

burden probeBurden {
    state: active
    discharge_mode: eventual
    description: "probe"
}

commitment cX {
    by: SameParty
    obligation: "obX"
    creates_burden: probeBurden
}

delegation sameDelegation {
    from: SameParty
    to: Agent
    obligation: "obX"
    transfers_burden: probeBurden
}
"""


def test_party_declared_via_two_channels_renders_as_one_entry_with_both_tags():
    result = parse_string(_R1D_OVERLAP, validate=True)
    assert result.ok, result.errors
    assert not any(w.startswith("[W-16c]") for w in result.warnings)
    assert not any(w.startswith("[W-16e]") for w in result.warnings)
    w16g = _w16g(result)
    assert len(w16g) == 1
    # Exact string: SameParty appears ONCE, tagged with both channels it
    # came from — never as two separate list entries for the same name.
    assert w16g[0] == (
        "[W-16g] Agent 'Agent' has 2 declared parents across all channels: "
        "SameParty (sameDelegation, delegated_from), StandingParentC "
        "(standing principal_of). Principals are collectively responsible "
        "(§7.10.1); delegated_from is itself a self-sufficient static "
        "declaration (§6.6.8 NOTE 3) and is counted here even with no backing "
        "Delegation. How these authorities combine is application-defined; the "
        "toolchain does not compose them. See "
        "el_reasoner.all_declared_parents_of(model, 'Agent')."
    )
    assert w16g[0].count("SameParty") == 1
    assert all_declared_parents_of(result.model, "Agent") == ["SameParty", "StandingParentC"]


# ── Order-invariance across declaration-order permutations ────────────────

_ORDER_PARTS = {
    "deleg_party": "party DelegParentX {}",
    "standing_party": "party StandingParentC {\n    principal_of Agent\n}",
    "df_party": "party DFParentY {}",
}


def _order_probe(order):
    body = "\n".join(_ORDER_PARTS[k] for k in order)
    return f"""
enterprise specification OrderProbe
{body}
agent Agent {{
    delegated_from DFParentY
}}

burden probeBurden {{
    state: active
    discharge_mode: eventual
    description: "probe"
}}

commitment cX {{
    by: DelegParentX
    obligation: "obX"
    creates_burden: probeBurden
}}

delegation dX {{
    from: DelegParentX
    to: Agent
    obligation: "obX"
    transfers_burden: probeBurden
}}
"""


def test_w16g_order_invariant_across_all_permutations():
    seen = set()
    for order in itertools.permutations(_ORDER_PARTS.keys()):
        result = parse_string(_order_probe(order), validate=True)
        assert result.ok, (order, result.errors)
        w16g = _w16g(result)
        assert len(w16g) == 1, order
        seen.add(w16g[0])
        assert all_declared_parents_of(result.model, "Agent") == [
            "DFParentY", "DelegParentX", "StandingParentC"
        ], order
    assert len(seen) == 1


# ── all_declared_parents_of(): unknown agent, and parity with the message ─

def test_all_declared_parents_of_unknown_agent_returns_empty():
    result = parse_string(_probe(True, True, True), validate=False)
    assert all_declared_parents_of(result.model, "NoSuchAgent") == []


def test_all_declared_parents_of_matches_w16g_message_content():
    result = parse_string(_probe(True, True, True), validate=True)
    parents = all_declared_parents_of(result.model, "Agent")
    w16g = _w16g(result)[0]
    for p in parents:
        assert p in w16g
    assert f"has {len(parents)} declared parents" in w16g


def test_warnings_never_affect_ok():
    result = parse_string(_probe(True, True, True), validate=True)
    assert result.ok is True
    assert result.errors == []
    assert len(result.warnings) >= 1


# ── Named tracked scenarios ─────────────────────────────────────────────

def test_referral_scenario_produces_exactly_one_w16g_true_positive():
    """The one real, tracked-corpus hit found during AM-95 recon —
    matching the AM-91 precedent for federation_consent_scenario.el:
    referral_scenario.el's SpecialistClinician has two genuinely
    distinct declared parents (GPClinician — both a real Delegation
    'gpToSpecialistDelegation' AND a paired delegated_from entry, the
    file's own idiom for a genuine delegated principal-agent
    relationship — and SpecialistPractice, a standing principal_of
    parent). Neither W-16c nor W-16e alone names the full union (each
    channel has only 1 distinct parent on its own), so this was
    previously silent. This is a true positive, advisory, and the
    scenario file itself is not modified — pinning the exact string
    here, on the named tracked file, per the maintainer's instruction."""
    result = parse("scenarios/referral/referral_scenario.el", validate=True)
    assert result.ok, result.errors
    # AM-103: scoped to [W-16g], the code this test is about.
    assert [w for w in result.warnings if w.startswith("[W-16g]")] == [
        "[W-16g] Agent 'SpecialistClinician' has 2 declared parents across all "
        "channels: GPClinician (gpToSpecialistDelegation, delegated_from), "
        "SpecialistPractice (standing principal_of). Principals are collectively "
        "responsible (§7.10.1); delegated_from is itself a self-sufficient static "
        "declaration (§6.6.8 NOTE 3) and is counted here even with no backing "
        "Delegation. How these authorities combine is application-defined; the "
        "toolchain does not compose them. See "
        "el_reasoner.all_declared_parents_of(model, 'SpecialistClinician')."
    ]


def test_consent_scenario_produces_no_w16g():
    result = parse("scenarios/consent/consent_scenario.el", validate=True)
    assert result.ok, result.errors
    assert _w16g(result) == []


def test_federation_consent_scenario_gets_no_additional_w16g():
    """SpecialistParty's union (GPParty, SpecialistPracticeParty) equals
    its own standing set exactly — [W-16e] alone already names the
    whole set, so [W-16g] correctly stays silent (non-redundancy rule),
    verified against the real corpus file, not just a synthetic case."""
    result = parse("scenarios/consent/federation_consent_scenario.el", validate=True)
    assert result.ok, result.errors
    assert any(w.startswith("[W-16e]") for w in result.warnings)
    assert _w16g(result) == []
