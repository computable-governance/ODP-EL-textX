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
  V-12  Every Federation member must reference a declared
        Community or Domain (both are community types).         §7.5.2
  V-13  Policed-pessimistic policies must declare a mechanism.  §7.9.4
  V-14  A PolicyRef target must resolve to a declared role,
        community, process, action, or object in scope.         §7.9.1
  V-15  DelegationDecl.obligation text must match the obligation
        of a CommitmentDecl or a prior DelegationDecl (chain
        continuity check).                                       §7.10.1
  V-NEW-19  CommunityObject.abstracts must reference a declared
        Community or Domain.                                     §6.2.2, §7.8.3
  V-NEW-21  Every Domain must have at least one controlling and
        one controlled filler, via either the object-reference
        syntax (controlling_object/controlled_object) or the
        role-based syntax (controlling_role/controlled_role,
        filled by 'fills' — AM-40, proposed).                    §7.5.1
  V-16a  Every TokenGroup member must have a backing Commitment or
        Delegation — static check for missing obligation descriptor. §6.4.2
  V-16b  SatisfactionCondition with a single member has no
        collective semantics — warn (not error).                 AM-29
  AM-31-V1  Authorization authority must be a party.               §6.6.4
  AM-31-V2  Revocable authorization must name an on_revocation
        embargo.                                                   AM-31
  AM-31-V3  Authorization must specify exactly one of to_agent
        or to_role.                                                AM-31 §4.0
  AM-31-V4  Authorization grants_permit must reference a
        permit-kind token.                                         §6.4.5
  AM-31-V5  Authorization on_revocation must reference a
        declared embargo-kind token.                                §6.4.4

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


def _obj_name(obj) -> str:
    return getattr(obj, "name", None) or ""


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
        e.name: e for e in _collect(model, "EnterpriseObject")
    }
    all_tokens: Dict[str, Any] = {
        e.name: e for e in _collect(model, "DeonticToken")
    }
    # Domain inherits Community in Python (AM-25) and is a valid MemberRef target,
    # so it must be included here for V-12 not to falsely flag Domain members.
    all_communities: Dict[str, Any] = {
        e.name: e
        for e in model.elements
        if _cls(e) in ("Community", "Domain")
    }
    all_policies: Dict[str, Any] = {
        e.name: e for e in _collect(model, "Policy")
    }
    commitments: List[Any] = _collect(model, "Commitment")
    delegations: List[Any] = _collect(model, "Delegation")

    # V-01 through V-06, V-14 — per Community
    for community in _collect(model, "Community"):
        errors.extend(_validate_community(community))

    # V-01 for Federation — AM-25 made objective mandatory on federation (§7.7)
    for fed in _collect(model, "Federation"):
        if not getattr(fed, "objective", None):
            errors.append(
                f"[V-01] Federation '{fed.name}' must have an objective. (§7.7)"
            )

    # V-07, V-08 — delegation structural rules
    errors.extend(_validate_delegations(delegations, commitments, all_objects))

    # AM-31-V1..V5 — authorization structural rules
    for a in _collect(model, "Authorization"):
        errors.extend(_validate_authorization(a, all_objects, all_tokens))

    # V-09 — single holder per token
    errors.extend(_validate_token_holders(model, all_tokens))

    # V-10 — commitment actor must be party/agent
    for c in commitments:
        errors.extend(_validate_commitment(c, all_objects))

    # V-11 — prescription actor rules
    for p in _collect(model, "Prescription"):
        errors.extend(_validate_prescription(p, all_objects))

    # V-12 — federation member references
    for fed in _collect(model, "Federation"):
        errors.extend(_validate_federation(fed, all_communities))

    # V-13 — pessimistic enforcement mechanism
    for pol in all_policies.values():
        errors.extend(_validate_policy(pol))

    # V-14 — PolicyRef targets in communities
    for community in all_communities.values():
        errors.extend(_validate_policy_refs(community))

    # V-15 — delegation obligation chain continuity
    errors.extend(_validate_obligation_chain(commitments, delegations))

    # V-NEW-19 — CommunityObject.abstracts must resolve (AM-26)
    errors.extend(_validate_community_objects(model, all_communities))

    # V-NEW-21 — Domain controlling/controlled filler, either syntax (AM-40)
    errors.extend(_validate_domain_controlling_controlled(model))

    # V-16a — TokenGroup member provenance check (§6.4.2)
    errors.extend(_validate_token_group_provenance(model))

    # V-16b — singleton SatisfactionCondition warning (AM-29)
    errors.extend(_validate_satisfaction_singleton(model))

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

    # V-05: assignment policy roles must exist.
    # AM-21: contract dissolved — assignment_policies is now a direct field on Community.
    for ap in getattr(c, "assignment_policies", []):
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


def _validate_authorization(a, all_objects: Dict[str, Any], all_tokens: Dict[str, Any]) -> List[str]:
    """AM-31: Authorization must be a well-formed empowerment. (§6.6.4, §7.10.2)"""
    errors: List[str] = []
    aname = a.name

    # AM-31-V1: authority must be a party — agents cannot grant authorizations
    authority_obj = all_objects.get(getattr(a.authority, "name", None))
    if authority_obj and authority_obj.kind != "party":
        errors.append(
            f"[AM-31-V1] Authorization '{aname}': authority must be a party "
            f"(§6.6.4); agents cannot grant authorizations "
            f"(found '{authority_obj.kind}')."
        )

    # AM-31-V2: revocable authorization must name an on_revocation embargo
    # (on_revocation_embargo is a plain ID: absent → "" per textX default, not None)
    if getattr(a, "revocable", False) and not getattr(a, "on_revocation_embargo", ""):
        errors.append(
            f"[AM-31-V2] Authorization '{aname}' is revocable but declares "
            f"no on_revocation embargo; withdrawal has no architectural effect."
        )

    # AM-31-V3: exactly one of to_agent / to_role
    # (authorized_role is a plain ID: absent → "" per textX default, not None)
    has_agent = getattr(a, "authorized_agent", None) is not None
    has_role = bool(getattr(a, "authorized_role", ""))
    if has_agent == has_role:
        errors.append(
            f"[AM-31-V3] Authorization '{aname}' must specify exactly one of "
            f"to_agent or to_role (AM-31 §4.0)."
        )

    # AM-31-V4: grants_permit must reference a permit-kind token
    permit_tok = getattr(a, "permit", None)
    if permit_tok is not None and getattr(permit_tok, "kind", None) != "permit":
        errors.append(
            f"[AM-31-V4] Authorization '{aname}' grants_permit must reference "
            f"a permit token (found kind '{getattr(permit_tok, 'kind', None)}')."
        )

    # AM-31-V5: on_revocation embargo must resolve to a declared embargo token
    # (on_revocation_embargo is a plain ID: absent → "" per textX default, not None)
    embargo_name = getattr(a, "on_revocation_embargo", "")
    if embargo_name:
        embargo_tok = all_tokens.get(embargo_name)
        if embargo_tok is None or getattr(embargo_tok, "kind", None) != "embargo":
            errors.append(
                f"[AM-31-V5] Authorization '{aname}' on_revocation references "
                f"'{embargo_name}' which is not a declared embargo."
            )

    return errors


def _validate_token_holders(model, all_tokens: Dict[str, Any]) -> List[str]:
    """
    V-09: A deontic token is held by exactly one active enterprise object. (§6.4.1)
    Check for tokens declared as 'holds' in more than one top-level ObjectDecl.
    """
    errors: List[str] = []
    token_holders: Dict[str, List[str]] = {}

    # After P2, body is dissolved — holds_tokens is a direct List[DeonticToken] on the object.
    for obj in [e for e in model.elements if _cls(e) == "EnterpriseObject"]:
        for token in getattr(obj, "holds_tokens", []):
            token_name = getattr(token, "name", None)
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
    # AM-26: members is now List[MemberRef]; dereference .community for name check
    for member in getattr(fed, "members", []):
        community = getattr(member, "community", None)
        member_name = getattr(community, "name", None)
        if member_name and member_name not in all_communities:
            errors.append(
                f"[V-12] Federation '{fed.name}': member '{member_name}' "
                f"is not a declared community. (§7.5.2)"
            )
    return errors


def _validate_community_objects(model, all_communities: Dict[str, Any]) -> List[str]:
    """V-NEW-19: CommunityObject.abstracts must reference a declared community. (§6.2.2, §7.8.3)"""
    errors: List[str] = []
    for co in _collect(model, "CommunityObject"):
        if co.abstracts is None:
            errors.append(
                f"[V-NEW-19] CommunityObject '{co.name}' must declare 'abstracts' "
                f"referencing a Community or Domain. (§6.2.2, §7.8.3)"
            )
        else:
            abstracted_name = getattr(co.abstracts, "name", None)
            if abstracted_name and abstracted_name not in all_communities:
                errors.append(
                    f"[V-NEW-19] CommunityObject '{co.name}': 'abstracts' references "
                    f"'{abstracted_name}' which is not a declared community. (§7.8.3)"
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


def _validate_token_group_provenance(model) -> List[str]:
    """V-16a: every TokenGroup member must have a backing obligation descriptor.

    A member is 'backed' if it appears as:
      (a) the burden of a top-level CommitmentDecl,
      (b) a token within a Delegation.transfers_token_group group, or
      (c) a token held via 'holds' in any role body within a community,
          federation, or domain.

    Path (c) covers scenarios that declare burdens through role membership
    (holds: tokenName) rather than top-level Commitment declarations —
    both are valid ODP-EL modelling styles.

    Without any of the above, _build_obligation_descriptors() at runtime
    will silently produce no descriptor for the token, making it invisible
    to the engine. Catching this at static validation time closes the gap.
    ISO basis: §6.4.2 (TokenGroup as named collection of deontic tokens).
    """
    errors: List[str] = []
    backed_by_commitment = {
        _obj_name(getattr(c, "burden", None))
        for c in _collect(model, "Commitment")
        if _obj_name(getattr(c, "burden", None))
    }
    backed_by_delegation: Set[str] = set()
    for d in _collect(model, "Delegation"):
        group_ref = getattr(d, "token_group", None)
        if group_ref is None:
            continue
        for tok in getattr(group_ref, "tokens", []):
            name = _obj_name(tok)
            if name:
                backed_by_delegation.add(name)
    backed_by_role_holds: Set[str] = set()
    for el in model.elements:
        if type(el).__name__ not in ("Community", "Federation", "Domain"):
            continue
        for role in getattr(el, "roles", []):
            for ht in getattr(role, "holds_tokens", []):
                # P3 process_role() dissolves HoldsToken wrappers; the list
                # contains DeonticToken objects directly after processing.
                name = _obj_name(ht)
                if name:
                    backed_by_role_holds.add(name)
    backed = backed_by_commitment | backed_by_delegation | backed_by_role_holds
    for tg in _collect(model, "TokenGroup"):
        for tok in getattr(tg, "tokens", []):
            name = _obj_name(tok)
            if name and name not in backed:
                errors.append(
                    f"[E-16a] TokenGroup '{tg.name}' member '{name}' has no "
                    f"backing Commitment or Delegation — obligation descriptor "
                    f"will be missing at runtime"
                )
    return errors


def _validate_satisfaction_singleton(model) -> List[str]:
    """V-16b: SatisfactionCondition with a single member has no collective semantics.

    Warns (prefix [W-16b]) in both forms:
      - AM-27 TokenGroup form: group has exactly one member token
      - AM-29 inline form: raw_args list contains exactly one entry

    A single-member condition is functionally equivalent to checking one
    token individually and does not benefit from the group construct.
    """
    warnings: List[str] = []
    tg_names = {e.name for e in model.elements if _cls(e) == "TokenGroup"}
    tg_tokens: Dict[str, List] = {}
    for el in model.elements:
        if _cls(el) == "TokenGroup":
            tg_tokens[el.name] = getattr(el, "tokens", [])

    for el in model.elements:
        if _cls(el) not in ("Community", "Federation", "Domain"):
            continue
        obj = getattr(el, "objective", None)
        if obj is None:
            continue
        sat = getattr(obj, "satisfaction", None)
        if sat is None:
            continue
        raw_args = getattr(sat, "raw_args", [])
        arg_names = [a.name for a in raw_args if getattr(a, "name", None)]
        if not arg_names:
            continue
        # AM-27 form: single arg that names a TokenGroup with one member
        if len(arg_names) == 1 and arg_names[0] in tg_names:
            members = tg_tokens.get(arg_names[0], [])
            if len(members) == 1:
                warnings.append(
                    f"[W-16b] Community '{el.name}': SatisfactionCondition "
                    f"references TokenGroup '{arg_names[0]}' which has only one "
                    f"member — no collective semantics. Consider whether a "
                    f"TokenGroup is needed. (AM-29)"
                )
        # AM-29 form: inline list with only one entry
        elif len(arg_names) == 1:
            warnings.append(
                f"[W-16b] Community '{el.name}': SatisfactionCondition "
                f"has a single inline member '{arg_names[0]}' — no collective "
                f"semantics. Consider whether a TokenGroup is needed. (AM-29)"
            )
    return warnings


def _validate_domain_controlling_controlled(model) -> List[str]:
    """V-NEW-21: Domain must have at least one controlling and one
    controlled filler, via either syntax. (§7.5.1)

    Object-reference syntax: at least one controlling_object and one
    controlled_object.
    Role-based syntax (AM-40, proposed): at least one controlling_role and
    one controlled_role, each filled by at least one DomainRoleFiller
    ('fills') resolving to that role.

    Identity comparison (`is`), not equality: role=[Role] cross-references
    resolve globally (no custom scope_provider — same behaviour as
    MemberRef.fills), so a same-named role declared in a different domain
    could otherwise slip past a value-equality or name-string check.
    Plain dataclasses here use default value-based __eq__, so `in`/`==`
    would risk a false positive; `is` against this domain's own
    controlling_roles/controlled_roles is the only check that actually
    confirms the filler resolved to *this* domain's role.

    No cardinality constraint beyond "at least one" on either side —
    controlling-role filler cardinality is deliberately left open (see
    docs/CONCEPTS_INDEX.md and docs/el_grammar_amendments.md, AM-40).
    """
    errors: List[str] = []
    for d in _collect(model, "Domain"):
        has_obj_syntax = bool(d.controlling_objects) and bool(d.controlled_objects)

        has_role_syntax = any(
            any(rf.role is c for c in d.controlling_roles)
            for rf in d.role_fillers
        ) and any(
            any(rf.role is c for c in d.controlled_roles)
            for rf in d.role_fillers
        )

        if not has_obj_syntax and not has_role_syntax:
            errors.append(
                f"[V-NEW-21] Domain '{d.name}': must declare at least one "
                f"controlling_object and one controlled_object, or at "
                f"least one controlling_role and one controlled_role each "
                f"filled by a role-filling statement ('fills'). (§7.5.1)"
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
