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
from typing import Any, Dict, List, Optional, Set, Tuple


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

def delegation_graph(model) -> Dict[str, List[DelegationLink]]:
    """
    Build adjacency list: delegator_name → [DelegationLink, ...]

    Suitable for graph traversal and for export to visualisation tools.
    """
    graph: Dict[str, List[DelegationLink]] = {}

    for d in _collect(model, "Delegation"):
        from_name = _obj_name(d.delegator)
        to_name   = _obj_name(d.delegate)
        if not from_name or not to_name:
            continue

        link = DelegationLink(
            delegation_name=d.name,
            from_obj=from_name,
            to_obj=to_name,
            obligation=d.obligation,
            sub_delegation_allowed=getattr(d, "sub_delegation_allowed", False),
            revocable=getattr(d, "revocable", False),
            duration=getattr(d, "duration", None),
            conditions=getattr(d, "conditions", None),
            creates_reporting_burden=getattr(d, "creates_reporting_burden", False),
        )
        graph.setdefault(from_name, []).append(link)

    return graph


# ── Primary query: ultimate_accountability ────────────────────────────────────

def ultimate_accountability(
    model,
    obligation: str,
) -> List[AccountabilityChain]:
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
    List of AccountabilityChain (may be multiple if the obligation
    is committed by / delegated through several independent chains).
    """
    chains: List[AccountabilityChain] = []
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
        return []

    # Collect root parties: from commitments
    processed_roots: Set[str] = set()

    for c in matching_commitments:
        root_name = _obj_name(c.actor)
        if not root_name or root_name in processed_roots:
            continue
        processed_roots.add(root_name)

        # Walk the delegation chain forward from root_name
        chain_links = _walk_chain(
            graph,
            start=root_name,
            obligation=obligation,
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
        for root_name, root_obligation in roots.items():
            if root_name in processed_roots:
                continue
            processed_roots.add(root_name)

            chain_links = _walk_chain(graph, start=root_name, obligation=obligation)
            current_holder = chain_links[-1].to_obj if chain_links else root_name

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
    visited: Optional[Set[str]] = None,
) -> List[DelegationLink]:
    """
    Depth-first walk of the delegation graph from 'start', collecting
    only links whose obligation matches.
    Returns the path to the deepest leaf.
    """
    if visited is None:
        visited = set()
    if start in visited:
        return []   # cycle guard
    visited.add(start)

    outgoing = [
        link for link in graph.get(start, [])
        if obligation.lower() in link.obligation.lower()
    ]

    if not outgoing:
        return []

    # Follow the first matching outgoing link (obligations form a tree
    # per §7.10.1; cycles are structurally invalid and caught by V-08)
    link = outgoing[0]
    rest = _walk_chain(graph, link.to_obj, obligation, visited)
    return [link] + rest


def _find_roots_from_delegations(
    matching: List[Any],
    all_delegations: List[Any],
) -> Dict[str, str]:
    """
    Given a set of matching delegations, find those whose 'from'
    object does not appear as 'to' in any other delegation
    (i.e., the root of the chain).
    Returns {root_name: obligation_text}.
    """
    all_delegates: Set[str] = {
        _obj_name(d.delegate) for d in all_delegations
        if _obj_name(d.delegate)
    }
    roots: Dict[str, str] = {}
    for d in matching:
        from_name = _obj_name(d.delegator)
        if from_name and from_name not in all_delegates:
            roots[from_name] = d.obligation
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
    chains = ultimate_accountability(spec, obligation)

    if not chains:
        print(f"No accountability chain found for obligation: '{obligation}'")
    else:
        print(f"Found {len(chains)} accountability chain(s):\n")
        for i, chain in enumerate(chains, 1):
            print(f"── Chain {i} ──")
            print(chain.render())
            print()
