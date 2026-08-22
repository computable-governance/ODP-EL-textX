"""
el_reasoner.py
==============
Accountability reasoning for DSL-EL models.

Primary query (as agreed):
    "Which party is ultimately accountable for obligation O
     through a delegation chain?"

The algorithm builds a directed graph:
    delegator ──delegation──► delegate

and walks backwards from the current obligation holder to find
the root party node (a party is accountable for all its agents,
transitively — §7.10.1).

Secondary queries provided:
    can_perform(actor_name, action_name) — §6.4.6 deontic check
    policy_conflicts(spec)               — §7.9.1 cross-community check
    delegation_graph(spec)               — raw graph for visualisation

Usage
-----
    from el_parser import parse
    from el_reasoner import (
        ultimate_accountability,
        can_perform,
        policy_conflicts,
        delegation_graph,
    )

    result = parse("my_spec.el")
    spec   = result.model

    chains = ultimate_accountability(spec, "Process all customer payments")
    for chain in chains:
        print(chain.render())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class DelegationLink:
    """A single hop in a delegation chain."""
    delegation_name: str
    from_obj: str          # delegator name
    to_obj: str            # delegate name
    obligation: str
    sub_delegation_allowed: bool
    revocable: bool
    duration: Optional[str]
    conditions: Optional[str]
    creates_reporting_burden: bool
    structural: bool = False   # AM-50: principal_of-derived, not a genuine Delegation
    # AM-54: structural transfer signals, mirroring el_kripke.py's
    # _delegation_chain_for_token() (AM-51/52) — a link "has a structural
    # reference" when either is set. Deliberately duplicated, not shared,
    # per the established Layer 2/4 no-cross-import convention.
    burden_name: Optional[str] = None
    token_group_members: FrozenSet[str] = field(default_factory=frozenset)

    @property
    def has_structural_ref(self) -> bool:
        return self.burden_name is not None or bool(self.token_group_members)


@dataclass
class AccountabilityChain:
    """
    The complete chain from the ultimately accountable party
    down to the current holder of an obligation.

    §7.10.1: "A principal is responsible for the acts of an object
              acting as its agent."
    """
    obligation: str
    root_party: str                          # ultimately accountable
    root_commitment: Optional[str]           # Commitment name, if any
    chain: List[DelegationLink]              # ordered from root → current holder
    current_holder: str                      # who currently holds the obligation

    def render(self) -> str:
        """Human-readable chain description."""
        lines = [
            f"Obligation : '{self.obligation}'",
            f"Root party : {self.root_party}  ← ULTIMATELY ACCOUNTABLE",
        ]
        if self.root_commitment:
            lines.append(f"Origin     : commitment '{self.root_commitment}'")
        if self.chain:
            lines.append("Chain      :")
            for i, link in enumerate(self.chain):
                prefix = "  " * (i + 1)
                lines.append(
                    f"{prefix}[{link.delegation_name}] "
                    f"{link.from_obj} ──► {link.to_obj}"
                    + (f"  (duration: {link.duration})" if link.duration else "")
                    + (f"  [sub-delegation allowed]" if link.sub_delegation_allowed else "")
                    + (f"  [reporting burden created]" if link.creates_reporting_burden else "")
                )
        lines.append(f"Holder now : {self.current_holder}")
        return "\n".join(lines)


@dataclass
class StaticRoleAnchor:
    """
    AM-53: the static spec's honest limit for an obligation with no
    Commitment and no matching Delegation — NOT a resolved accountable
    party, and structurally distinct from AccountabilityChain so a caller
    cannot mistake one for the other without an explicit isinstance()
    check (there is no shared "is this final" boolean field to forget).

    This is deliberately NOT a claim about who the standard says holds
    the token. §6.4.3 is explicit that deontic tokens are held by active
    enterprise objects filling roles, never by roles or communities
    directly (see docs/CONCEPTS_INDEX.md, "WorldState scope" finding,
    2026-08-20) — role-filling for an ordinary Community role is a
    runtime-only fact, established via enroll() in the Python builder,
    not expressible anywhere in the static .el spec (confirmed empirically
    against grammar/v2/el_grammar.tx and el_api.py's scenario builders,
    AM-53). ultimate_accountability() operates on the static spec alone
    and has no access to that runtime fact.

    This result reports the nearest static anchor — the Role that
    declares 'holds' on the token, and its owning Community — as far as
    the static spec alone can honestly go. "Who actually holds it" is a
    runtime question this function cannot answer; ask the live Runtime/
    WorldState instead.

    AM-54: chain/current_holder are optional extensions for the case
    where a role-conferred token IS further delegated onward (e.g. A's
    role-conferred burden delegated A→B→C) — the root (A) still isn't a
    resolved party, but the onward delegation hops and current holder are
    real, structurally-confirmed facts the static spec does know, and
    dropping them would silently lose information the walk already found.
    Both default empty for the plain no-further-delegation case (e.g.
    ereferral_model.el's 4 burdens), so this extension is additive and
    does not change AM-53's original cases.
    """
    obligation: str
    token_name: str
    role_name: str
    community_name: str
    chain: List["DelegationLink"] = field(default_factory=list)
    current_holder: Optional[str] = None

    def describe(self) -> str:
        """Human-readable description — deliberately NOT named render(),
        so it can't be called interchangeably with AccountabilityChain's
        render() by a caller iterating a mixed list without branching on
        type first."""
        lines = [
            f"Obligation : '{self.obligation}'",
            f"Token      : {self.token_name}",
            f"Static spec has no Commitment or Delegation naming an",
            f"accountable party for this obligation. Nearest static",
            f"anchor: role '{self.role_name}' in community",
            f"'{self.community_name}' declares 'holds {self.token_name}'.",
            f"This is NOT a resolved accountable party — §6.4.3: tokens",
            f"are held by active enterprise objects filling roles, never",
            f"by roles or communities directly. The actual holder is a",
            f"runtime fact (who fills '{self.role_name}', established via",
            f"enroll()) that this static reasoner has no access to.",
        ]
        if self.chain:
            lines.append("Further delegated onward (still not a resolved root):")
            for i, link in enumerate(self.chain, 1):
                prefix = "  " * i
                lines.append(f"{prefix}[{link.delegation_name}] {link.from_obj} ──► {link.to_obj}")
            lines.append(f"Current holder (structurally confirmed): {self.current_holder}")
        return "\n".join(lines)


@dataclass
class CanPerformResult:
    """Result of a deontic capability check."""
    actor: str
    action: str
    permitted: bool
    blocking_embargos: List[str] = field(default_factory=list)
    missing_permits: List[str] = field(default_factory=list)
    explanation: str = ""

    def render(self) -> str:
        verdict = "✓ CAN" if self.permitted else "✗ CANNOT"
        lines = [
            f"{verdict} perform '{self.action}'  (actor: '{self.actor}')",
            f"  {self.explanation}",
        ]
        if self.blocking_embargos:
            lines.append(f"  Blocking embargos : {self.blocking_embargos}")
        if self.missing_permits:
            lines.append(f"  Missing permits   : {self.missing_permits}")
        return "\n".join(lines)


@dataclass
class PolicyConflict:
    """A detected policy conflict between two communities."""
    community_a: str
    community_b: str
    obligation: str     # the conflicting rule text
    description: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cls(obj) -> str:
    return type(obj).__name__


def _collect(model, cls_name: str) -> List[Any]:
    return [e for e in model.elements if _cls(e) == cls_name]


def _name(obj) -> Optional[str]:
    return getattr(obj, "name", None)


def _obj_name(ref) -> Optional[str]:
    """textX cross-references resolve to the target object."""
    if ref is None:
        return None
    return getattr(ref, "name", None)


# ── Graph builder ─────────────────────────────────────────────────────────────

def _is_standing_affiliation(principal_name: str, agent: Any) -> bool:
    """A principal_of entry is a standing (structural) affiliation edge —
    not already represented by a genuine Delegation — when the agent's own
    delegated_from is absent, or points to a different principal than this
    one.

    Grounded in §7.10.1 alone ("by each such delegation, that active
    enterprise object becomes an agent of the parties delegating, and the
    parties (collectively) become principal of that object") — once a
    principal-agent relationship is established, by whatever mechanism,
    the principal is accountable for the agent's acts. The paired-vs-
    one-sided split itself is NOT something the standard's text draws;
    it is this scenario's own documented modelling convention — see
    referral_scenario.el's header comment (lines 41-84): one-sided
    principal_of is "organisational affiliation only... deliberately NOT
    full subordinate agency", while paired principal_of+delegated_from is
    "a GENUINE, if temporary, delegated principal-agent relationship".
    §6.6.8 NOTE 3 was considered and rejected as a citation for this
    specific discriminator — it licenses the delegated_from construct
    itself ("a specification may state that, in its initial state, an
    active enterprise object is an agent of a party", grammar/v2/
    el_grammar.tx:112-114) but says nothing about pairing being required
    for genuineness. See docs/CONCEPTS_INDEX.md's 2026-08-19/08-21
    delegation-chain findings and the AM-50 entry for the full rationale.

    A paired relationship is always already covered by an explicit
    Delegation with its own obligation-scoped text, so it is deliberately
    NOT added again here as an unconditionally-matching edge — doing so
    would let an unrelated obligation ride along a hop that was never
    actually delegated for it (e.g. clinicalHandoverBurden riding through
    GPClinician → SpecialistClinician, which is real only for
    referralResponseBurden)."""
    delegated_from = getattr(agent, "delegated_from", None)
    return delegated_from is None or _obj_name(delegated_from) != principal_name


def delegation_graph(model) -> Dict[str, List[DelegationLink]]:
    """
    Build adjacency list: delegator_name → [DelegationLink, ...]

    Suitable for graph traversal and for export to visualisation tools.

    AM-50: also includes one-sided principal_of edges (structural=True) —
    a standing organisational affiliation with no reciprocal
    delegated_from, per §7.10.1 ("the parties (collectively) become
    principal of that object"). These edges match any obligation (see
    _walk_chain's structural check) — unlike genuine Delegation edges,
    scoped to their own obligation text. Paired principal_of +
    delegated_from relationships are NOT duplicated here; see
    _is_standing_affiliation().

    AM-54: each link also carries its structural transfer signal
    (burden_name / token_group_members, mirroring el_kripke.py's AM-51/52
    _delegation_chain_for_token()) so _walk_chain() can match structurally
    first and treat free-text obligation matching as a fallback only for
    links with no structural reference at all (confirmed by ground-truth
    scan: every Delegation in every current scenario file has one — see
    AM-54's amendment entry).
    """
    graph: Dict[str, List[DelegationLink]] = {}

    for d in _collect(model, "Delegation"):
        from_name = _obj_name(d.delegator)
        to_name   = _obj_name(d.delegate)
        if not from_name or not to_name:
            continue

        group = getattr(d, "token_group", None)
        token_group_members = frozenset(
            n for n in (_obj_name(t) for t in getattr(group, "tokens", [])) if n
        ) if group is not None else frozenset()

        link = DelegationLink(
            delegation_name=d.name,
            from_obj=from_name,
            to_obj=to_name,
            obligation=d.obligation,
            sub_delegation_allowed=getattr(d, "sub_delegation_allowed", False),
            revocable=getattr(d, "revocable", False),
            duration=getattr(d, "duration", None),
            conditions=getattr(d, "conditions", None),
            burden_name=_obj_name(getattr(d, "burden", None)),
            token_group_members=token_group_members,
            creates_reporting_burden=getattr(d, "creates_reporting_burden", False),
        )
        graph.setdefault(from_name, []).append(link)

    for principal in _collect(model, "EnterpriseObject"):
        principal_name = _obj_name(principal)
        if not principal_name:
            continue
        for agent in getattr(principal, "principal_of", []):
            agent_name = _obj_name(agent)
            if not agent_name or not _is_standing_affiliation(principal_name, agent):
                continue
            link = DelegationLink(
                delegation_name=f"principal_of:{principal_name}->{agent_name}",
                from_obj=principal_name,
                to_obj=agent_name,
                obligation="",
                sub_delegation_allowed=False,
                revocable=False,
                duration=None,
                conditions=None,
                creates_reporting_burden=False,
                structural=True,
            )
            graph.setdefault(principal_name, []).append(link)

    return graph


# ── Last-resort fallback: static role anchor ───────────────────────────────────

def _find_role_anchors_for_obligation(model, obligation: str) -> List[StaticRoleAnchor]:
    """AM-53: last-resort path when neither a Commitment nor a Delegation
    names the obligation at all. Checks whether the query matches a bare
    Burden (by exact token name, or by substring against its own
    description) that some Role.holds_tokens declares — and if so,
    reports that Role and its owning Community as the nearest static
    anchor. See StaticRoleAnchor's docstring for why this is not a claim
    about who holds the token.

    Scope note: searches Community.roles and Federation.roles (both
    populated post-parse — AM-26/AM-25). Domain's role mechanism
    (controlling_role/controlled_role, AM-40) is a structurally different,
    singular-field shape, not a List[Role] — not covered here; no live
    scenario needs it for this path today."""
    query = obligation.lower()
    matching_tokens = [
        t for t in _collect(model, "DeonticToken")
        if getattr(t, "kind", None) == "burden"
        and (
            query == t.name.lower()
            or (t.description and query in t.description.lower())
        )
    ]
    if not matching_tokens:
        return []
    matching_names = {t.name for t in matching_tokens}

    anchors: List[StaticRoleAnchor] = []
    seen: Set[Tuple[str, str]] = set()
    for community in _collect(model, "Community") + _collect(model, "Federation"):
        community_name = _name(community)
        if not community_name:
            continue
        for role in getattr(community, "roles", []):
            role_name = _name(role)
            if not role_name:
                continue
            for tok in getattr(role, "holds_tokens", []):
                tok_name = _obj_name(tok)
                if tok_name in matching_names and (community_name, role_name) not in seen:
                    seen.add((community_name, role_name))
                    anchors.append(StaticRoleAnchor(
                        obligation=obligation,
                        token_name=tok_name,
                        role_name=role_name,
                        community_name=community_name,
                    ))
    return anchors


# ── Primary query: ultimate_accountability ────────────────────────────────────

def ultimate_accountability(
    model,
    obligation: str,
) -> List[Union[AccountabilityChain, StaticRoleAnchor]]:
    """
    Find which party is ultimately accountable for a named obligation.

    Algorithm
    ---------
    1. Find all CommitmentDecls whose obligation text matches.
    2. For each, identify the committing party.
    3. Build delegation sub-graph for this obligation.
    4. Walk the chain from the commitment party downward to find
       the current holder (the leaf node — no outgoing delegations
       for this obligation).
    5. Return one AccountabilityChain per root found.
    6. AM-53: if NEITHER a Commitment nor a Delegation names this
       obligation at all, fall back to _find_role_anchors_for_obligation()
       — a Burden can be conferred purely by 'holds' inside a Role body
       with no Commitment anywhere (§B.2.4's own worked example; confirmed
       live in this repo — ereferral_model.el has zero Commitment/
       Delegation blocks at all). This fallback returns StaticRoleAnchor
       results, NOT AccountabilityChain — see that class's docstring for
       why the distinction matters and must not be collapsed.
    7. AM-54: a Delegation-only root (step 4 territory, no Commitment at
       all) is itself checked for grounding before being wrapped in an
       AccountabilityChain — a role-conferred root (no Commitment, but
       held via Role.holds) is reported as a StaticRoleAnchor instead,
       with the onward delegation chain/current_holder preserved on it
       (confirmed by construction: MultiHopRoleConferredProbe,
       docs/CONCEPTS_INDEX.md, 2026-08-22). A root that is neither
       Commitment- nor role-grounded (confirmed to have zero live or
       constructed examples — see AM-54's amendment entry) keeps the
       pre-AM-54 AccountabilityChain/root_commitment=None behaviour
       unchanged; this is a deliberate, documented simplification, not an
       oversight.

    §7.10.1: "A principal is responsible for the acts of an object
              acting as its agent."
    §6.6.2 NOTE 1: "In the case of an action of commitment by an agent,
                    the principal responsible for the agent becomes obligated."

    Parameters
    ----------
    model      : parsed EnterpriseSpec
    obligation : the obligation string to search for (exact or substring match)

    Returns
    -------
    List of AccountabilityChain and/or StaticRoleAnchor. Never a mix of
    both in one call — the Commitment/Delegation path and the role-anchor
    fallback are mutually exclusive (the fallback only runs when the
    primary path found nothing at all). An empty list means genuinely not
    found: no Commitment, no Delegation, and no Role declares 'holds' on
    anything matching this obligation.
    """
    chains: List[Union[AccountabilityChain, StaticRoleAnchor]] = []
    graph = delegation_graph(model)

    # Index commitments by obligation text
    all_commitments = _collect(model, "Commitment")
    matching_commitments = [
        c for c in all_commitments
        if obligation.lower() in c.obligation.lower()
    ]

    # Also match delegations whose obligation text matches —
    # some obligations enter via delegation without an explicit top-level commitment.
    all_delegations = _collect(model, "Delegation")
    matching_delegations = [
        d for d in all_delegations
        if obligation.lower() in d.obligation.lower()
    ]

    if not matching_commitments and not matching_delegations:
        return _find_role_anchors_for_obligation(model, obligation)

    # Collect root parties: from commitments
    processed_roots: Set[str] = set()

    for c in matching_commitments:
        root_name = _obj_name(c.actor)
        if not root_name or root_name in processed_roots:
            continue
        processed_roots.add(root_name)

        # AM-54: track the Commitment's own token structurally so the
        # walk trusts a hop's .burden/.token_group over its free text.
        token_name = _obj_name(getattr(c, "burden", None))

        # Walk the delegation chain forward from root_name
        chain_links = _walk_chain(
            graph,
            start=root_name,
            obligation=obligation,
            token_name=token_name,
        )

        current_holder = chain_links[-1].to_obj if chain_links else root_name

        chains.append(AccountabilityChain(
            obligation=c.obligation,
            root_party=root_name,
            root_commitment=c.name,
            chain=chain_links,
            current_holder=current_holder,
        ))

    # Handle obligations that appear only in delegations (no matching commitment)
    # — walk backwards to find the root delegator
    if not matching_commitments:
        roots = _find_roots_from_delegations(matching_delegations, all_delegations)
        for root_name, (root_obligation, token_name) in roots.items():
            if root_name in processed_roots:
                continue
            processed_roots.add(root_name)

            chain_links = _walk_chain(
                graph, start=root_name, obligation=obligation, token_name=token_name,
            )
            current_holder = chain_links[-1].to_obj if chain_links else root_name

            # AM-54: is this root actually grounded? No Commitment (we're
            # in the no-matching_commitments branch already), so check
            # role-holds grounding via the same fallback AM-53 uses — a
            # root name is not, by itself, evidence of a resolved party.
            anchors = (
                _find_role_anchors_for_obligation(model, token_name)
                if token_name else []
            )
            if anchors:
                for anchor in anchors:
                    chains.append(StaticRoleAnchor(
                        obligation=root_obligation,
                        token_name=anchor.token_name,
                        role_name=anchor.role_name,
                        community_name=anchor.community_name,
                        chain=chain_links,
                        current_holder=current_holder,
                    ))
                continue

            # Neither Commitment- nor role-grounded (confirmed: zero live
            # or constructed examples today — see AM-54's amendment
            # entry). Deliberately unchanged pre-AM-54 behaviour.
            chains.append(AccountabilityChain(
                obligation=root_obligation,
                root_party=root_name,
                root_commitment=None,
                chain=chain_links,
                current_holder=current_holder,
            ))

    return chains


def _walk_chain(
    graph: Dict[str, List[DelegationLink]],
    start: str,
    obligation: str,
    token_name: Optional[str] = None,
    visited: Optional[Set[str]] = None,
) -> List[DelegationLink]:
    """
    Depth-first walk of the delegation graph from 'start', collecting
    matching outgoing links. Returns the path to the deepest leaf.

    AM-54: matching is structural-first when token_name is known — a link
    that declares a structural transfer signal (burden_name /
    token_group_members) is matched (or rejected) by that signal alone,
    regardless of its own obligation text; free-text obligation matching
    is used only as a fallback for a link with NO structural reference at
    all (ground-truth confirmed: none exist in any current scenario file,
    but the grammar permits it). This closes a real fragility: obligation
    text drifting across hops (e.g. re-worded at a later delegation) no
    longer silently truncates the walk, since a structurally-confirmed
    hop is trusted even when its own wording doesn't echo the original
    query text (see docs/CONCEPTS_INDEX.md's TextDriftProbe finding,
    2026-08-22). Structural (AM-50 principal_of) links always match,
    same as before.
    """
    if visited is None:
        visited = set()
    if start in visited:
        return []   # cycle guard
    visited.add(start)

    def _matches(link: DelegationLink) -> bool:
        if link.structural:
            return True
        if link.has_structural_ref:
            if token_name is None:
                return False
            return link.burden_name == token_name or token_name in link.token_group_members
        return obligation.lower() in link.obligation.lower()

    outgoing = [link for link in graph.get(start, []) if _matches(link)]

    if not outgoing:
        return []

    # Follow the first matching outgoing link (obligations form a tree
    # per §7.10.1; cycles are structurally invalid and caught by V-08)
    link = outgoing[0]
    rest = _walk_chain(graph, link.to_obj, obligation, token_name, visited)
    return [link] + rest


def _find_roots_from_delegations(
    matching: List[Any],
    all_delegations: List[Any],
) -> Dict[str, Tuple[str, Optional[str]]]:
    """
    Given a set of matching delegations, find those whose 'from'
    object does not appear as 'to' in any other delegation
    (i.e., the root of the chain). This root-finding step is already
    purely graph-topological (a set difference over the whole model),
    not text-based — it correctly finds the true origin regardless of
    how many hops separate it, no recursion needed.

    Returns {root_name: (obligation_text, token_name)}. AM-54:
    token_name is the matched delegation's own structural transfer
    reference (Delegation.burden, if set) — None if the delegation only
    declares transfers_token_group (ambiguous which specific member to
    track for the onward walk) or neither field at all. The caller uses
    token_name to drive _walk_chain()'s structural-first matching and to
    check the root's own grounding via _find_role_anchors_for_obligation()
    before deciding whether this root is a resolved party or a
    role-conferred one (AM-54 — see ultimate_accountability()).
    """
    all_delegates: Set[str] = {
        _obj_name(d.delegate) for d in all_delegations
        if _obj_name(d.delegate)
    }
    roots: Dict[str, Tuple[str, Optional[str]]] = {}
    for d in matching:
        from_name = _obj_name(d.delegator)
        if from_name and from_name not in all_delegates:
            roots[from_name] = (d.obligation, _obj_name(getattr(d, "burden", None)))
    return roots


# ── Secondary query: can_perform ─────────────────────────────────────────────

def can_perform(model, actor_name: str, action_name: str) -> CanPerformResult:
    """
    Check whether actor_name can perform action_name given its
    current deontic token holdings.

    Implements §6.4.6 conditional action semantics:
      - Actor must hold required permits.
      - Actor must NOT hold active embargos for the action.
      - Burdens do not block but favouring increases urgency.

    Limitations
    -----------
    This is a static check against declared token holdings in ObjectDecl
    bodies and role assignments. Runtime token state changes (via speech
    acts) are not modelled here — this is structural, not operational.
    """
    # Collect all tokens held by actor at spec level.
    # P2 (process_enterprise_object) dissolves ObjectBody: holds_tokens is
    # promoted to a flat list of DeonticToken objects on the EnterpriseObject itself.
    all_objects = {_name(e): e for e in _collect(model, "EnterpriseObject")}
    actor_obj = all_objects.get(actor_name)

    held_token_names: Set[str] = set()
    if actor_obj:
        for tok in getattr(actor_obj, "holds_tokens", []):
            if _name(tok):
                held_token_names.add(_name(tok))

    # Find the action across all communities.
    # P3 (process_role) dissolves role.items into role.actions; iterate directly.
    action = None
    for community in _collect(model, "Community"):
        for role in getattr(community, "roles", []):
            for item in getattr(role, "actions", []):
                if item.name == action_name:
                    action = item

    if action is None:
        return CanPerformResult(
            actor=actor_name,
            action=action_name,
            permitted=False,
            explanation=f"Action '{action_name}' not found in any community.",
        )

    # Check deontic requirements
    blocking_embargos: List[str] = []
    missing_permits: List[str] = []

    for req in getattr(action, "deontic_requirements", []):
        tok = getattr(req, "token", None)
        tok_name = _name(tok)
        req_kind = req.kind

        # Only check requirements without a specific role filter,
        # or where role filter matches actor's roles (simplified)
        if req_kind == "requires_permit":
            if tok_name and tok_name not in held_token_names:
                missing_permits.append(tok_name)
        elif req_kind == "inhibited_by_embargo":
            if tok_name and tok_name in held_token_names:
                blocking_embargos.append(tok_name)

    permitted = len(blocking_embargos) == 0 and len(missing_permits) == 0

    if permitted:
        explanation = "All deontic requirements satisfied."
    else:
        parts = []
        if missing_permits:
            parts.append(f"missing permits: {missing_permits}")
        if blocking_embargos:
            parts.append(f"blocked by embargos: {blocking_embargos}")
        explanation = "; ".join(parts)

    return CanPerformResult(
        actor=actor_name,
        action=action_name,
        permitted=permitted,
        blocking_embargos=blocking_embargos,
        missing_permits=missing_permits,
        explanation=explanation,
    )


# ── Secondary query: policy_conflicts ────────────────────────────────────────

def policy_conflicts(model) -> List[PolicyConflict]:
    """
    Detect potential policy conflicts when communities interact.

    §7.3.2: "When composing communities, there will be a set of policies
             common to those communities. These policies shall be consistent."
    §7.9.1: "Where an enterprise object is subject to policies of more than
             one community, the enterprise specification shall ensure that
             policy conflicts do not exist."

    Heuristic: two policies conflict if they have the same obligation target
    but one states 'obligation' and another states 'prohibition' for that target.
    """
    conflicts: List[PolicyConflict] = []
    communities = _collect(model, "Community")

    # Collect policy rules per community
    PolicyEntry = Tuple[str, str, str]  # (community, kind, target)
    all_policy_entries: List[PolicyEntry] = []

    for community in communities:
        for pref in getattr(community, "policy_refs", []):
            pol = getattr(pref, "policy", None)
            if pol is None:
                continue
            for rule in getattr(pol, "rules", []):
                all_policy_entries.append((community.name, rule.kind, rule.target))

    # Check for obligation ↔ prohibition conflicts on the same target
    by_target: Dict[str, List[Tuple[str, str]]] = {}
    for cname, kind, target in all_policy_entries:
        by_target.setdefault(target, []).append((cname, kind))

    for target, entries in by_target.items():
        kinds_present = {k for _, k in entries}
        if "obligation" in kinds_present and "prohibition" in kinds_present:
            communities_involved = [c for c, _ in entries]
            if len(set(communities_involved)) > 1:
                conflicts.append(PolicyConflict(
                    community_a=communities_involved[0],
                    community_b=communities_involved[1],
                    obligation=target,
                    description=(
                        f"Conflicting obligation and prohibition on '{target}' "
                        f"across communities {communities_involved}."
                    ),
                ))

    return conflicts


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from el_parser import parse

    if len(sys.argv) < 3:
        print("Usage: python el_reasoner.py <spec.el> <obligation>")
        print("       python el_reasoner.py <spec.el> --policy-conflicts")
        sys.exit(1)

    result = parse(sys.argv[1])
    if not result.ok:
        for e in result.errors:
            print(e)
        sys.exit(1)

    spec = result.model

    if sys.argv[2] == "--policy-conflicts":
        conflicts = policy_conflicts(spec)
        if not conflicts:
            print("No policy conflicts detected.")
        else:
            for c in conflicts:
                print(f"CONFLICT: {c.description}")
        sys.exit(0)

    obligation = " ".join(sys.argv[2:])
    results = ultimate_accountability(spec, obligation)

    if not results:
        print(f"No accountability chain found for obligation: '{obligation}'")
    else:
        print(f"Found {len(results)} result(s):\n")
        for i, result in enumerate(results, 1):
            print(f"── Result {i} ──")
            # AM-53: each result is either an AccountabilityChain (resolved
            # party) or a StaticRoleAnchor (static spec's honest limit, not
            # a resolved party) — branch explicitly, never duck-type.
            if isinstance(result, StaticRoleAnchor):
                print(result.describe())
            else:
                print(result.render())
            print()
