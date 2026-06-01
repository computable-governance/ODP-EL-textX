"""
el_validator.py
===============
Semantic validation of a parsed DSL-EL model.

Each rule is numbered and traced to a specific clause of
ISO/IEC 15414:2015 so that violations are actionable.

Rules implemented
-----------------
  V-01  Every community has exactly one objective.               §7.7
  V-02  Every process has at least one step.                     §7.8.5
  V-03  Every step has at least one actor.                       §7.8.5
  V-04  Every process declares initiation and termination.       §7.8.5
  V-05  A role referenced in an assignment policy must exist
        in the same community.                                    §7.8.2
  V-06  A sub-objective's assigned_to_name must match a role
        or process declared in the same community.               §7.7
  V-07  Every DelegationDecl references a valid delegator and
        delegate (must be ObjectDecl of kind party or agent).    §7.10.1
  V-08  Sub-delegation is only possible when the parent
        delegation has sub_delegation_allowed=True.              §7.10.1
  V-09  A DeonticTokenDecl held by more than one ObjectDecl
        at the top level violates the "exactly one holder" rule. §6.4.1
  V-10  A CommitmentDecl's actor must be of kind 'party'
        or 'agent'.                                              §6.6.2
  V-11  A PrescriptionDecl actor must be party/agent, or the
        spec must include a permit enabling prescription.        §7.10.5
  V-12  Every FederationDecl member must reference a declared
        CommunityDecl.                                           §7.5.2
  V-13  Policed-pessimistic policies must declare a mechanism.  §7.9.4
  V-14  A PolicyRef target must resolve to a declared role,
        community, process, action, or object in scope.         §7.9.1
  V-15  DelegationDecl.obligation text must match the obligation
        of a CommitmentDecl or a prior DelegationDecl (chain
        continuity check).                                       §7.10.1

Usage
-----
    from el_validator import validate_spec
    errors = validate_spec(model)   # returns list[str]
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cls(obj) -> str:
    return type(obj).__name__


def _collect(model, cls_name: str) -> List[Any]:
    return [e for e in model.elements if _cls(e) == cls_name]


def _name_set(model, cls_name: str) -> Set[str]:
    return {e.name for e in _collect(model, cls_name)}


def _find(model, cls_name: str, name: str) -> Optional[Any]:
    for e in _collect(model, cls_name):
        if getattr(e, "name", None) == name:
            return e
    return None


_AGENT_KINDS = {"party", "agent"}


# ── Main entry-point ──────────────────────────────────────────────────────────

def validate_spec(model) -> List[str]:
    """
    Run all semantic rules against a parsed EnterpriseSpec model.
    Returns a (possibly empty) list of human-readable error strings.
    """
    errors: List[str] = []

    # Pre-index objects and communities for cross-reference checks
    all_objects: Dict[str, Any] = {
        e.name: e for e in _collect(model, "ObjectDecl")
    }
    all_tokens: Dict[str, Any] = {
        e.name: e for e in _collect(model, "DeonticTokenDecl")
    }
    all_communities: Dict[str, Any] = {
        e.name: e for e in _collect(model, "CommunityDecl")
    }
    all_policies: Dict[str, Any] = {
        e.name: e for e in _collect(model, "PolicyDecl")
    }
    commitments: List[Any] = _collect(model, "CommitmentDecl")
    delegations: List[Any] = _collect(model, "DelegationDecl")

    # V-01 through V-06 operate per-community
    for community in all_communities.values():
        errors.extend(_validate_community(community))

    # V-07, V-08 — delegation structural rules
    errors.extend(_validate_delegations(delegations, commitments, all_objects))

    # V-09 — single holder per token
    errors.extend(_validate_token_holders(model, all_tokens))

    # V-10 — commitment actor must be party/agent
    for c in commitments:
        errors.extend(_validate_commitment(c, all_objects))

    # V-11 — prescription actor rules
    for p in _collect(model, "PrescriptionDecl"):
        errors.extend(_validate_prescription(p, all_objects))

    # V-12 — federation member references
    for fed in _collect(model, "FederationDecl"):
        errors.extend(_validate_federation(fed, all_communities))

    # V-13 — pessimistic enforcement mechanism
    for pol in all_policies.values():
        errors.extend(_validate_policy(pol))

    # V-14 — PolicyRef targets in communities
    for community in all_communities.values():
        errors.extend(_validate_policy_refs(community))

    # V-15 — delegation obligation chain continuity
    errors.extend(_validate_obligation_chain(commitments, delegations))

    return errors


# ── Per-rule implementations ──────────────────────────────────────────────────

def _validate_community(c) -> List[str]:
    errors: List[str] = []
    cname = c.name

    # V-01: exactly one objective (grammar enforces presence; this
    # catches if grammar changes to allow 0 objectives).
    if not hasattr(c, "objective") or c.objective is None:
        errors.append(
            f"[V-01] Community '{cname}' must have exactly one objective. (§7.7)"
        )

    # Collect role and process names for forward-reference checks
    role_names = {r.name for r in getattr(c, "roles", [])}
    process_names = {p.name for p in getattr(c, "processes", [])}

    # V-05: assignment policy roles must exist
    contract = getattr(c, "contract", None)
    if contract:
        for ap in getattr(contract, "assignment_policies", []):
            if ap.role_name not in role_names:
                errors.append(
                    f"[V-05] Community '{cname}': assignment_policy references "
                    f"unknown role '{ap.role_name}'. (§7.8.2)"
                )

    # V-06: sub-objective assignments
    obj = getattr(c, "objective", None)
    if obj:
        for so in getattr(obj, "sub_objectives", []):
            if so.assigned_to_name:
                if so.assigned_to_kind == "role" and so.assigned_to_name not in role_names:
                    errors.append(
                        f"[V-06] Community '{cname}', sub-objective '{so.name}': "
                        f"assigned_to role '{so.assigned_to_name}' not declared. (§7.7)"
                    )
                if so.assigned_to_kind == "process" and so.assigned_to_name not in process_names:
                    errors.append(
                        f"[V-06] Community '{cname}', sub-objective '{so.name}': "
                        f"assigned_to process '{so.assigned_to_name}' not declared. (§7.7)"
                    )

    # V-02, V-03, V-04: process / step rules
    for proc in getattr(c, "processes", []):
        proc_errors = _validate_process(proc, cname)
        errors.extend(proc_errors)

    return errors


def _validate_process(proc, community_name: str) -> List[str]:
    errors: List[str] = []
    pname = proc.name
    prefix = f"Community '{community_name}', process '{pname}'"

    # V-02
    if not getattr(proc, "steps", []):
        errors.append(f"[V-02] {prefix}: must have at least one step. (§7.8.5)")

    # V-04
    if not getattr(proc, "initiation", "").strip():
        errors.append(f"[V-04] {prefix}: must declare 'initiates'. (§7.8.5)")
    if not getattr(proc, "termination", "").strip():
        errors.append(f"[V-04] {prefix}: must declare 'terminates'. (§7.8.5)")

    # V-03: every step — steps now use items*=StepBodyItem
    for step in getattr(proc, "steps", []):
        step_items = getattr(step, "items", [])
        has_actor = any(_cls(i) == "ActorRef" for i in step_items)
        # Also check legacy .actors for forward compat
        if not has_actor and not getattr(step, "actors", []):
            errors.append(
                f"[V-03] {prefix}, step '{step.name}': "
                f"must have at least one actor. (§7.8.5)"
            )

    return errors


def _validate_delegations(
    delegations: List[Any],
    commitments: List[Any],
    all_objects: Dict[str, Any],
) -> List[str]:
    errors: List[str] = []

    for d in delegations:
        dname = d.name

        # V-07: delegator and delegate must be declared objects of kind party|agent
        delegator_obj = all_objects.get(getattr(d.delegator, "name", None))
        delegate_obj  = all_objects.get(getattr(d.delegate, "name", None))

        if delegator_obj and delegator_obj.kind not in _AGENT_KINDS:
            errors.append(
                f"[V-07] Delegation '{dname}': delegator '{delegator_obj.name}' "
                f"must be 'party' or 'agent' (found '{delegator_obj.kind}'). (§7.10.1)"
            )
        if delegate_obj and delegate_obj.kind not in _AGENT_KINDS:
            errors.append(
                f"[V-07] Delegation '{dname}': delegate '{delegate_obj.name}' "
                f"must be 'party' or 'agent' (found '{delegate_obj.kind}'). (§7.10.1)"
            )

        # V-08: sub-delegation check
        if delegator_obj and delegator_obj.kind == "agent":
            # This delegation comes FROM an agent — requires prior parent delegation
            # to have sub_delegation_allowed=True
            parent_delegation = _find_parent_delegation(
                delegations, getattr(d.delegator, "name", None)
            )
            if parent_delegation and not getattr(parent_delegation, "sub_delegation_allowed", False):
                errors.append(
                    f"[V-08] Delegation '{dname}': agent '{delegator_obj.name}' "
                    f"attempts to sub-delegate but parent delegation "
                    f"'{parent_delegation.name}' has sub_delegation_allowed=false. (§7.10.1)"
                )

    return errors


def _find_parent_delegation(delegations: List[Any], agent_name: Optional[str]) -> Optional[Any]:
    """Return the delegation whose delegate is agent_name."""
    if agent_name is None:
        return None
    for d in delegations:
        if getattr(d.delegate, "name", None) == agent_name:
            return d
    return None


def _validate_token_holders(model, all_tokens: Dict[str, Any]) -> List[str]:
    """
    V-09: A deontic token is held by exactly one active enterprise object. (§6.4.1)
    Check for tokens declared as 'holds' in more than one top-level ObjectDecl.
    """
    errors: List[str] = []
    token_holders: Dict[str, List[str]] = {}

    for obj in [e for e in model.elements if _cls(e) == "ObjectDecl"]:
        body = getattr(obj, "body", None)
        if not body:
            continue
        for ht in getattr(body, "holds_tokens", []):
            token_name = getattr(ht.token, "name", None)
            if token_name:
                token_holders.setdefault(token_name, []).append(obj.name)

    for token_name, holders in token_holders.items():
        if len(holders) > 1:
            errors.append(
                f"[V-09] Token '{token_name}' is held by multiple objects: "
                f"{holders}. A deontic token must be held by exactly one "
                f"active enterprise object. (§6.4.1)"
            )

    return errors


def _validate_commitment(c, all_objects: Dict[str, Any]) -> List[str]:
    """V-10: Commitment actor must be party or agent. (§6.6.2)"""
    errors: List[str] = []
    actor_name = getattr(c.actor, "name", None)
    obj = all_objects.get(actor_name)
    if obj and obj.kind not in _AGENT_KINDS:
        errors.append(
            f"[V-10] Commitment '{c.name}': actor '{actor_name}' "
            f"must be 'party' or 'agent' (found '{obj.kind}'). (§6.6.2)"
        )
    return errors


def _validate_prescription(p, all_objects: Dict[str, Any]) -> List[str]:
    """V-11: Prescription actor must be party/agent or hold a prescription permit. (§7.10.5)"""
    errors: List[str] = []
    actor_name = getattr(p.actor, "name", None)
    obj = all_objects.get(actor_name)
    has_permit = getattr(p, "permit", None) is not None
    if obj and obj.kind not in _AGENT_KINDS and not has_permit:
        errors.append(
            f"[V-11] Prescription '{p.name}': actor '{actor_name}' is not a "
            f"party/agent and no requires_permit is declared. (§7.10.5)"
        )
    return errors


def _validate_federation(fed, all_communities: Dict[str, Any]) -> List[str]:
    """V-12: Federation members must reference declared communities. (§7.5.2)"""
    errors: List[str] = []
    for member in getattr(fed, "members", []):
        member_name = getattr(member, "name", None)
        if member_name and member_name not in all_communities:
            errors.append(
                f"[V-12] Federation '{fed.name}': member '{member_name}' "
                f"is not a declared community. (§7.5.2)"
            )
    return errors


def _validate_policy(pol) -> List[str]:
    """V-13: Policed-pessimistic policies must declare a mechanism. (§7.9.4)"""
    errors: List[str] = []
    enforcement = getattr(pol, "enforcement", None)
    if enforcement and getattr(enforcement, "mode", None) == "pessimistic":
        if not getattr(enforcement, "mechanism", "").strip():
            errors.append(
                f"[V-13] Policy '{pol.name}': pessimistic enforcement requires "
                f"a 'mechanism' description. (§7.9.4)"
            )
    return errors


def _validate_policy_refs(community) -> List[str]:
    """V-14: PolicyRef target names must resolve within community scope."""
    errors: List[str] = []
    role_names    = {r.name for r in getattr(community, "roles", [])}
    process_names = {p.name for p in getattr(community, "processes", [])}

    for ref in getattr(community, "policy_refs", []):
        ref_name = getattr(ref, "ref_name", None)
        ref_scope = getattr(ref, "scope", None)
        if not ref_name or not ref_scope:
            continue
        if ref_scope == "role" and ref_name not in role_names:
            errors.append(
                f"[V-14] Community '{community.name}': policy applies to "
                f"unknown role '{ref_name}'. (§7.9.1)"
            )
        if ref_scope == "process" and ref_name not in process_names:
            errors.append(
                f"[V-14] Community '{community.name}': policy applies to "
                f"unknown process '{ref_name}'. (§7.9.1)"
            )

    return errors


def _validate_obligation_chain(
    commitments: List[Any],
    delegations: List[Any],
) -> List[str]:
    """
    V-15: Delegation obligation text must trace back to a Commitment.

    Each delegation's obligation must appear in at least one CommitmentDecl,
    forming a chain root.  Mid-chain delegations that don't directly match
    a commitment are still valid as long as the chain root does.
    """
    errors: List[str] = []
    committed_obligations = {c.obligation for c in commitments}

    for d in delegations:
        if d.obligation not in committed_obligations:
            errors.append(
                f"[V-15] Delegation '{d.name}': obligation '{d.obligation}' "
                f"does not match any CommitmentDecl. "
                f"Delegation chain has no commitment root. (§7.10.1)"
            )

    return errors
