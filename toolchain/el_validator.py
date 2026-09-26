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
        delegation has sub_delegation_allowed=True. Token-aware,
        order-independent (AM-92).                                §7.10.1
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
  V-15  DelegationDecl's referenced token (transfers_burden /
        transfers_token_group) must have a resolvable origin — a
        Commitment naming it, or a Role 'holds' naming it (AM-55,
        structural-first). Falls back to free-text obligation
        matching only for a delegation with no structural
        reference at all (chain continuity check).                §7.10.1
  V-NEW-10  transfers_burden and transfers_token_group on a
        DelegationDecl are mutually exclusive — a delegation
        transfers a single burden or a token group, not both.   §6.6.6, §7.10.1
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
  W-16c  An agent/party that is the delegate of Delegations from
        >=2 distinct delegators — multi-parent notice, warn (not
        error): principals are collectively responsible, but the
        toolchain does not compose overlapping authorities.      AM-90, §7.10.1
  W-16d  One token (transfers_burden, or a transfers_token_group
        member) transferred by >=2 distinct Delegations to the
        same delegate, or by the same delegator to >=2 different
        delegates — same-token conflict, warn (not error).       AM-90, §6.4.1
  W-16e  An agent with >=2 DISTINCT standing principal_of parents
        (one-sided structural affiliations, not paired with
        delegated_from) — separate from W-16c, which only counts
        genuine Delegation-based parents. Warn (not error).      AM-91, §7.10.1
  W-16f  An Action requires >=1 permit of a set co-granted to one
        target (to_agent or to_role) in one non-empty domain_scope
        by >=2 distinct authorities, but an authority of the set has
        none of its permits required — that authority is never
        consulted. Advisory, never an error; role Action bodies
        only (ConditionalAction is not read by anything).  AM-94, §6.6.4, §6.4.6
  W-16g  An agent with >=2 DISTINCT declared parents across the
        UNION of all three channels (Delegation, standing
        principal_of, delegated_from), where neither W-16c nor
        W-16e alone already names that exact union — closes the
        blind spot where each channel has only 1 parent on its own.
        Advisory, never an error.                          AM-95, §7.10.1
  W-16h  An Action's requires_permit names a permit that no
        Authorization, holds clause (object or role), or action
        effect create grants anywhere in the specification — the
        requirement can never be satisfied. Advisory, never an
        error; role Action bodies only (ConditionalAction is not
        read by anything).                         AM-96, §6.4.6, §7.10.1
  W-18  An Embargo named by >=1 Action via inhibited_by_embargo
        has a for_action outside that set — blocking follows the
        naming Actions, so the for_action is ignored. Advisory,
        never an error; role Action bodies only.        AM-102, §6.4.4, §6.4.6
  W-19  A discharge_mode: strict Burden has no deadline with an
        elapsed-time magnitude (a number with a unit, e.g. "15
        minutes") — none at all, or prose only. Advisory.  AM-103, §6.4.3, §7.8.7
  W-20  A discharge_mode: strict Burden that no ViolationResponse
        names in on_violation_of. Advisory; not needed if the
        enforcement point discharges it atomically.        AM-103, §6.3.8, §7.8.6
  W-21  A terminate ViolationResponse whose violator chain holds
        no revocable Authorization (with an on_revocation
        embargo) granted by its obligates — it would fire and
        revoke nothing. Advisory.                 AM-104, §6.3.8, §7.8.6, §6.6.4
  W-22  An escalate ViolationResponse with no creates_burden —
        fires as a ledger entry only; nobody becomes obligated.
        Advisory.                                AM-104, §6.3.8, §7.8.6 NOTE 2
  W-23  An escalate ViolationResponse whose escalate_to is
        missing or not a party. The dormant V-NEW-16, as a
        warning. Advisory.                            AM-104, §6.3.8, §7.4
  W-24  An eventual Burden whose deadline has no elapsed-time
        magnitude and that is in no opted-in satisfaction group
        (on_objective_achieved) with another member — never
        violated at runtime or in the verifier. Advisory.
                                                  AM-108, §6.4.3, §7.8.7
  V-17  An ACTIVE Burden's for_action must not match an ACTIVE
        Embargo's for_action — direct normative conflict
        (obligated to do the one thing that is prohibited).
        Single-domain-scoped: see docs/CONCEPTS_INDEX.md,
        "Permit/Embargo missing domain scope".               §6.4.3, §6.4.4
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

from typing import Any, Dict, List, Optional, Set, Tuple


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
    errors.extend(_validate_delegations(delegations, commitments, all_objects, model))

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
    errors.extend(_validate_obligation_chain(commitments, delegations, model))

    # V-NEW-19 — CommunityObject.abstracts must resolve (AM-26)
    errors.extend(_validate_community_objects(model, all_communities))

    # V-NEW-21 — Domain controlling/controlled filler, either syntax (AM-40)
    errors.extend(_validate_domain_controlling_controlled(model))

    # V-16a — TokenGroup member provenance check (§6.4.2)
    errors.extend(_validate_token_group_provenance(model))

    # V-16b — singleton SatisfactionCondition warning (AM-29)
    errors.extend(_validate_satisfaction_singleton(model))

    # W-16c — multi-parent notice (AM-90, §7.10.1)
    errors.extend(_validate_multi_parent_notice(model))

    # W-16d — same-token conflict (AM-90, §6.4.1)
    errors.extend(_validate_same_token_conflict(model))

    # W-16e — standing principal_of multi-parent notice (AM-91, §7.10.1)
    errors.extend(_validate_standing_multi_parent_notice(model))

    # W-16f — action leaves a co-granting authority unconsulted (AM-94, §6.6.4, §6.4.6)
    errors.extend(_validate_unconsulted_permit_authority(model))

    # W-16g — declared-parent union across all channels (AM-95, §7.10.1)
    errors.extend(_validate_all_channel_multi_parent_notice(model))

    # W-16h — ungrantable permit requirement (AM-96, §6.4.6, §7.10.1)
    errors.extend(_validate_ungrantable_permit_requirement(model))

    # W-18 — embargo for_action outside its naming Actions (AM-102, §6.4.4, §6.4.6)
    errors.extend(_validate_embargo_for_action_consistency(model))

    # W-19 — strict burden without a measurable deadline (AM-103, §6.4.3, §7.8.7)
    errors.extend(_validate_strict_burden_deadline(model))

    # W-20 — strict burden no ViolationResponse names (AM-103, §6.3.8, §7.8.6)
    errors.extend(_validate_strict_burden_violation_response(model))

    # W-21 — terminate response with nothing to revoke (AM-104, §6.3.8, §7.8.6, §6.6.4)
    errors.extend(_validate_terminate_response_target(model))

    # W-22 — escalate response that obligates nobody (AM-104, §6.3.8, §7.8.6 NOTE 2)
    errors.extend(_validate_escalate_response_burden(model))

    # W-23 — escalate_to must be a party; the dormant V-NEW-16 (AM-104, §6.3.8, §7.4)
    errors.extend(_validate_escalate_to_party(model))

    # W-24 — eventual burden that can never be violated (AM-108, §6.4.3, §7.8.7)
    errors.extend(_validate_unviolatable_eventual_burden(model))

    # V-17 — Burden/Embargo for_action conflict (§6.4.3, §6.4.4)
    errors.extend(_validate_burden_embargo_conflict(model))

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
    model: Any,
) -> List[str]:
    """V-07/V-08/V-NEW-10 over every Delegation.

    AM-92: V-08 is now token-aware and order-independent — see
    _validate_sub_delegation() below for the algorithm and rationale.
    """
    errors: List[str] = []

    from el_reasoner import delegation_graph
    graph = delegation_graph(model)
    links_by_name: Dict[str, Any] = {
        link.delegation_name: link
        for links in graph.values()
        for link in links
        if not link.structural
    }
    incoming_by_agent: Dict[str, List[Any]] = {}
    for links in graph.values():
        for link in links:
            if link.structural:
                continue
            incoming_by_agent.setdefault(link.to_obj, []).append(link)

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

        # V-08: sub-delegation check (AM-92)
        if delegator_obj and delegator_obj.kind == "agent":
            errors.extend(_validate_sub_delegation(
                d, dname, delegator_obj.name, incoming_by_agent, links_by_name
            ))

        # V-NEW-10: transfers_burden and transfers_token_group are mutually
        # exclusive — a delegation either transfers a single burden or a
        # token group, not both. (§6.6.6, §7.10.1)
        if getattr(d, "burden", None) and getattr(d, "token_group", None):
            errors.append(
                f"[V-NEW-10] Delegation '{dname}' declares both "
                f"'transfers_burden' and 'transfers_token_group' "
                f"— these are mutually exclusive."
            )

    return errors


def _validate_sub_delegation(
    d: Any,
    dname: str,
    agent_name: str,
    incoming_by_agent: Dict[str, List[Any]],
    links_by_name: Dict[str, Any],
) -> List[str]:
    """V-08 (AM-92): d's delegator (agent_name) is an agent, so d is a
    sub-delegation — it requires that every incoming, genuine (non-
    structural) Delegation to agent_name which actually transfers one of
    d's own tokens permits sub-delegation.

    Token-aware (S1): for each token T that d structurally transfers
    (transfers_burden, or its transfers_token_group's members — read off
    delegation_graph()'s already-extracted DelegationLink fields, not
    re-derived here), find the incoming Delegation(s) to agent_name that
    structurally name T. If any such Delegation has
    sub_delegation_allowed=false, that is a genuine V-08 violation for T.

    Order-independent by construction (S3): "the incoming Delegations to
    agent_name" is looked up from a pre-built structural index, not by
    scanning for "the first" one — there is no first here, only the set
    of genuine parents.

    Conservative fallback (S2): if T is not named by ANY incoming
    Delegation, or d itself has neither transfers_burden nor
    transfers_token_group set at all, this falls back to the pre-AM-92
    check: every incoming Delegation to agent_name must permit
    sub-delegation, regardless of what it transfers. For a single-parent
    agent this is IDENTICAL to the pre-AM-92 verdict AND to the pre-AM-92
    message text (no token named) — confirmed empirically against every
    tracked scenario (zero diffs) as part of AM-92's recon.

    Deliberate scope boundary, not an oversight: an incoming Delegation
    with NEITHER transfers_burden nor transfers_token_group set can never
    S1-match a token (it has no structural token to match against) — it
    only ever participates in the S2 fallback. So if some OTHER incoming
    Delegation structurally matches and permits T, a neither-field
    incoming Delegation to the same agent does not block T even though it
    itself forbids sub-delegation in general — S1's per-token match is
    authoritative once it succeeds; S2 only applies when no incoming
    Delegation makes any structural claim on T at all.

    One error per (d, forbidding parent Delegation) — deduplicated: if one
    parent forbids several of d's tokens, they are all named, sorted and
    comma-joined, in a single error, not one error per token."""
    incoming = incoming_by_agent.get(agent_name, [])
    link_d = links_by_name.get(dname)
    tokens_d: Set[str] = set()
    if link_d:
        if link_d.burden_name:
            tokens_d.add(link_d.burden_name)
        tokens_d |= set(link_d.token_group_members)

    forbidding_tokens: Dict[str, Set[str]] = {}

    def _mark(parent_name: str, token: Optional[str]) -> None:
        forbidding_tokens.setdefault(parent_name, set())
        if token is not None:
            forbidding_tokens[parent_name].add(token)

    if tokens_d:
        for token in sorted(tokens_d):
            matching = [
                inc for inc in incoming
                if inc.burden_name == token or token in inc.token_group_members
            ]
            if matching:
                for inc in matching:
                    if not inc.sub_delegation_allowed:
                        _mark(inc.delegation_name, token)
            else:
                # S2: this specific token is unmatched by any incoming Delegation
                for inc in incoming:
                    if not inc.sub_delegation_allowed:
                        _mark(inc.delegation_name, None)
    else:
        # S2: d has neither transfers_burden nor transfers_token_group
        for inc in incoming:
            if not inc.sub_delegation_allowed:
                _mark(inc.delegation_name, None)

    errors: List[str] = []
    for parent_name in sorted(forbidding_tokens):
        toks = forbidding_tokens[parent_name]
        if toks:
            token_list = ", ".join(f"'{t}'" for t in sorted(toks))
            errors.append(
                f"[V-08] Delegation '{dname}': agent '{agent_name}' "
                f"attempts to sub-delegate {token_list} but parent delegation "
                f"'{parent_name}' has sub_delegation_allowed=false. (§7.10.1)"
            )
        else:
            errors.append(
                f"[V-08] Delegation '{dname}': agent '{agent_name}' "
                f"attempts to sub-delegate but parent delegation "
                f"'{parent_name}' has sub_delegation_allowed=false. (§7.10.1)"
            )
    return errors


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


def _validate_multi_parent_notice(model) -> List[str]:
    """W-16c (AM-90): an agent/party that is the delegate of Delegations
    from >=2 DISTINCT delegators — multi-parent is legitimate per
    §7.10.1 ("the parties (collectively) become principal"), so this is
    advisory, never an error; a token's own chain still resolves to
    exactly one holder (§6.4.1/§7.8.7), this only names the agent's
    surrounding authority structure.

    Built entirely from el_reasoner.parents_of() — the message and that
    public read-only query share the same data by construction, so they
    cannot diverge. N counts DISTINCT parents, not delegations; a parent
    with multiple delegations to this agent lists each one, grouped under
    that parent.

    Documented out of scope (see parents_of()'s own docstring): a
    structural principal_of affiliation with no Delegation of its own,
    and a to_role Authorization (no single resolved agent to attribute it
    to)."""
    from el_reasoner import delegation_graph, parents_of

    graph = delegation_graph(model)
    delegate_names = sorted(
        {link.to_obj for links in graph.values() for link in links if not link.structural}
    )

    warnings: List[str] = []
    for agent_name in delegate_names:
        records, auths = parents_of(model, agent_name)
        distinct_parents = sorted({r.parent for r in records})
        if len(distinct_parents) < 2:
            continue

        parent_groups = []
        for parent in distinct_parents:
            pairs = [f"{r.delegation_name} -> {', '.join(r.tokens)}" for r in records if r.parent == parent]
            parent_groups.append(f"{parent} ({'; '.join(pairs)})")

        msg = (
            f"[W-16c] Agent '{agent_name}' has {len(distinct_parents)} parents: "
            f"{', '.join(parent_groups)}. "
            f"Principals are collectively responsible (§7.10.1). "
            f"If these parents' authorities overlap, how they combine is "
            f"application-defined; the toolchain does not compose them."
        )
        if auths:
            auth_parts = [f"{a.authorization_name} ({a.authority}: {a.permit})" for a in auths]
            msg += (
                f" Permits granted to '{agent_name}' (authority sources, not "
                f"necessarily principals): {', '.join(auth_parts)}."
            )
        msg += f" See el_reasoner.parents_of(model, '{agent_name}')."
        warnings.append(msg)

    return warnings


def _validate_same_token_conflict(model) -> List[str]:
    """W-16d (AM-90): one token transferred by >=2 distinct Delegations to
    the SAME delegate (double-source), or by the SAME delegator to >=2
    DIFFERENT delegates (fork). Advisory, never an error — which transfer
    actually governs is application-defined.

    Sequential chains (P -> A, then A -> B carrying the same token onward)
    do NOT trigger this: each Delegation's own transferred-token set is
    scoped to that one hop, so grouping by (token, delegate) or
    (token, delegator) never conflates a chain with a conflict. A single
    Delegation declaring both transfers_burden and transfers_token_group
    naming the same token (a V-NEW-10 violation — gp_referral_scenario.el
    has this) does not self-flag: tokens are deduped per Delegation via
    the same set-union parents_of() uses, before grouping.

    Built on el_reasoner.delegation_graph()'s already-extracted
    burden_name/token_group_members fields — no separate getattr(d,
    "burden"/"token_group") expansion here, same shared-data principle as
    parents_of() (§6.4.1/§7.8.7, §7.10.1)."""
    from el_reasoner import delegation_graph

    graph = delegation_graph(model)

    token_transfers: Dict[str, List[Tuple[str, str, str]]] = {}
    for links in graph.values():
        for link in links:
            if link.structural:
                continue
            tokens = ({link.burden_name} if link.burden_name else set()) | set(link.token_group_members)
            for tok in tokens:
                token_transfers.setdefault(tok, []).append(
                    (link.from_obj, link.to_obj, link.delegation_name)
                )

    warnings: List[str] = []
    for token_name in sorted(token_transfers):
        by_delegate: Dict[str, Set[str]] = {}
        by_delegator: Dict[str, Set[str]] = {}
        for delegator, delegate, dname in token_transfers[token_name]:
            by_delegate.setdefault(delegate, set()).add(dname)
            by_delegator.setdefault(delegator, set()).add(delegate)

        for delegate in sorted(by_delegate):
            dnames = by_delegate[delegate]
            if len(dnames) >= 2:
                warnings.append(
                    f"[W-16d] Token '{token_name}' is transferred to '{delegate}' "
                    f"by {len(dnames)} distinct delegations: {', '.join(sorted(dnames))}. "
                    f"Which transfer takes effect is application-defined; the "
                    f"toolchain does not resolve it."
                )

        for delegator in sorted(by_delegator):
            delegates = by_delegator[delegator]
            if len(delegates) >= 2:
                warnings.append(
                    f"[W-16d] Token '{token_name}' is transferred by '{delegator}' "
                    f"to {len(delegates)} distinct delegates: {', '.join(sorted(delegates))}. "
                    f"Which transfer takes effect is application-defined; the "
                    f"toolchain does not resolve it."
                )

    return warnings


def _validate_standing_multi_parent_notice(model) -> List[str]:
    """W-16e (AM-91): an agent with >=2 DISTINCT standing principal_of
    parents — a one-sided structural affiliation with no Delegation of its
    own (el_reasoner.delegation_graph()'s link.structural=True), NOT a
    paired principal_of+delegated_from relationship (already covered by a
    real Delegation, per el_reasoner._is_standing_affiliation()). Advisory,
    never an error — §7.10.1 makes multi-parent legitimate.

    Distinct from W-16c, which counts only genuine Delegation-based
    parents: an agent can trigger W-16c, W-16e, both, or neither,
    independently, depending on which kind of parent edge it has.

    Built entirely from el_reasoner.standing_parents_of() — the message
    and that public read-only query share the same data by construction,
    so they cannot diverge. This is also why the message's "the first
    alphabetically" claim about chain-based views is safe to make: it is
    exactly what el_kripke.py's _delegation_chain_for_token() now falls
    back to (AM-91) when no Commitment anchors the choice."""
    from el_reasoner import delegation_graph, standing_parents_of

    graph = delegation_graph(model)
    agent_names = sorted(
        {link.to_obj for links in graph.values() for link in links if link.structural}
    )

    warnings: List[str] = []
    for agent_name in agent_names:
        parents = standing_parents_of(model, agent_name)
        if len(parents) < 2:
            continue
        warnings.append(
            f"[W-16e] Agent '{agent_name}' has {len(parents)} standing principal_of "
            f"parents: {', '.join(parents)}. For a token with no Commitment of its own, "
            f"chain-based views name one of them (the first alphabetically); the choice "
            f"is stable but arbitrary. Which parent's authority applies is "
            f"application-defined. See el_reasoner.standing_parents_of(model, '{agent_name}')."
        )
    return warnings


def _validate_all_channel_multi_parent_notice(model) -> List[str]:
    """W-16g (AM-95): an agent with >=2 DISTINCT declared parents across
    the UNION of all three channels — genuine Delegation (parents_of()),
    standing principal_of (standing_parents_of()), and delegated_from
    (el_reasoner._delegated_from_parents()) — where that union is not
    already exactly what W-16c or W-16e alone would name. Advisory,
    never an error — §7.10.1 makes multi-parent legitimate; §6.6.8
    NOTE 3 makes delegated_from a self-sufficient declaration needing no
    backing Delegation, so it is counted here on its own terms, never
    requiring a matching Delegation to be visible.

    Built entirely from el_reasoner.all_declared_parents_of()'s three
    underlying primitives — the message and that public read-only query
    share the same data by construction, so they cannot diverge.

    Non-redundancy rule: fires iff len(union) >= 2 AND union != the
    Delegation-only parent set (what W-16c would name) AND union != the
    standing-only parent set (what W-16e would name). If either channel
    alone already explains the whole union, that channel's own warning
    already says it — a third warning naming the exact same set would be
    redundant. When W-16c or W-16e fires for a strict subset of the
    union (a third, distinct parent from another channel), W-16g fires
    alongside it — that extra parent is new information neither of them
    stated.

    A parent declared via more than one channel to the same agent (e.g.
    a real Delegation paired with a matching delegated_from entry from
    the same party — referral_scenario.el's and consent_scenario.el's
    own idiom for a genuine delegated principal-agent relationship, per
    el_reasoner._is_standing_affiliation()'s docstring) renders as ONE
    entry naming every channel it came from, never duplicated.

    [W-16c], [W-16d], and [W-16e] are unchanged by this rule — same
    triggers, same wording, same tests."""
    from el_reasoner import (
        _collect,
        _delegated_from_parents,
        _obj_name,
        parents_of,
        standing_parents_of,
    )

    agent_names = sorted(
        {n for o in _collect(model, "EnterpriseObject") if (n := _obj_name(o))}
    )

    warnings: List[str] = []
    for agent_name in agent_names:
        records, _ = parents_of(model, agent_name)
        delegation_parents = {r.parent for r in records}
        standing = set(standing_parents_of(model, agent_name))
        delegated_from_parents = _delegated_from_parents(model, agent_name)
        union = delegation_parents | standing | delegated_from_parents

        if len(union) < 2 or union == delegation_parents or union == standing:
            continue

        delegation_names_by_parent: Dict[str, List[str]] = {}
        for r in records:
            delegation_names_by_parent.setdefault(r.parent, []).append(r.delegation_name)

        parts = []
        for parent in sorted(union):
            tags: List[str] = []
            if parent in delegation_parents:
                tags.extend(sorted(delegation_names_by_parent.get(parent, [])))
            if parent in standing:
                tags.append("standing principal_of")
            if parent in delegated_from_parents:
                tags.append("delegated_from")
            parts.append(f"{parent} ({', '.join(tags)})")

        warnings.append(
            f"[W-16g] Agent '{agent_name}' has {len(union)} declared parents across "
            f"all channels: {', '.join(parts)}. Principals are collectively "
            f"responsible (§7.10.1); delegated_from is itself a self-sufficient "
            f"static declaration (§6.6.8 NOTE 3) and is counted here even with no "
            f"backing Delegation. How these authorities combine is "
            f"application-defined; the toolchain does not compose them. "
            f"See el_reasoner.all_declared_parents_of(model, '{agent_name}')."
        )
    return warnings


def _validate_unconsulted_permit_authority(model) -> List[str]:
    """W-16f (AM-94): an Action requires >=1 permit of a set of permits
    co-granted to one target (to_agent or to_role, separate namespaces) in
    one non-empty domain_scope by >=2 distinct authorities, but at least
    one of those authorities has none of its permits (within the set)
    required by the Action — so that authority is never consulted, and the
    Action still runs if its authorization is revoked. Advisory, never an
    error: how the authorities combine is application-defined and the
    toolchain does not compose them.

    Built entirely from el_reasoner.permit_omissions() — the message and
    that public read-only query share the same data by construction (no
    twin logic). One warning per (action, set).

    Documented out of scope: permits obtained by role `holds`; an
    Authorization without a domain_scope (never joins a set — fail-open);
    ConditionalAction (its requires_permit is read by nothing, so advising
    "add the missing requires_permit" would change nothing — see the open
    finding in docs/CONCEPTS_INDEX.md); Step, Prescription and Declaration
    requirements; role-to-agent resolution (the warning is about the permit
    set, not about who performs the action)."""
    from el_reasoner import permit_omissions

    warnings: List[str] = []
    for om in permit_omissions(model):
        a, cs = om.action, om.permit_set
        unconsulted = "; ".join(
            f"authority '{o.authority}' ("
            + "; ".join(f"Authorization '{g.authorization_name}': permit '{g.permit}'" for g in o.grants)
            + ")"
            for o in om.omitted
        )
        warnings.append(
            f"[W-16f] Action '{a.name}' (role '{a.role}', community '{a.community}') "
            f"requires {', '.join(repr(p) for p in om.required)} from the permits co-granted "
            f"to {cs.target_kind} '{cs.target}' in domain_scope '{cs.domain_scope}' by "
            f"{len(cs.authorities)} distinct authorities ({', '.join(cs.authorities)}). "
            f"Not consulted: {unconsulted}. "
            f"If every listed authority must approve this action, add the missing "
            f"requires_permit; if any one suffices, this is intended. How these "
            f"authorities combine is application-defined; the toolchain does not "
            f"compose them."
        )
    return warnings


def _validate_ungrantable_permit_requirement(model) -> List[str]:
    """W-16h (AM-96): an Action's requires_permit names a permit that
    el_reasoner.grantable_permit_names() does not contain — no
    Authorization grants it, no holds clause (EnterpriseObject or Role)
    names it, and no action effect creates it, anywhere in the
    specification. Advisory, never an error, but worded as a
    spec-authoring defect to fix (distinct from W-16c/e/f/g's
    "application-defined, the toolchain does not compose them" closing):
    unlike those, this is not a composition question between legitimate
    alternatives — the requirement is unsatisfiable from the start, a
    dead end, not a substitution risk. Runtime enforcement already blocks
    it correctly (el_engine step 6 / Runtime.advance()); this only adds
    the missing static diagnostic.

    Built entirely from el_reasoner.ungrantable_permit_requirements() —
    the message and that public read-only query share the same data by
    construction, so they cannot diverge.

    When the ungrantable permit is ALSO named in a Delegation transfer
    (el_reasoner.delegation_transferred_token_names()) — the case
    grantable_permit_names() deliberately excludes as evidence, since a
    Delegation transfers an existing token rather than creating one
    (§6.4.7 NOTE 1) — the message says so explicitly, so a spec author
    isn't left wondering why a permit that is "transferred somewhere"
    still triggers the rule.

    Documented out of scope, same as W-16f: ConditionalAction (its
    requires_permits is read by nothing — see the open finding in
    docs/CONCEPTS_INDEX.md); Step, Prescription and Declaration
    requirements."""
    from el_reasoner import delegation_transferred_token_names, ungrantable_permit_requirements

    transferred = delegation_transferred_token_names(model)

    warnings: List[str] = []
    for req in ungrantable_permit_requirements(model):
        a = req.action
        delegation_note = (
            ", though it is named in a Delegation transfer (which "
            "presupposes, not creates, the token)"
            if req.permit in transferred else ""
        )
        warnings.append(
            f"[W-16h] Action '{a.name}' (role '{a.role}', community '{a.community}') "
            f"requires permit '{req.permit}', but nothing in this specification "
            f"grants it — no Authorization names it, no holds clause (object or "
            f"role) names it, and no action effect creates it{delegation_note}. "
            f"The requirement can never be satisfied. Add a grant for "
            f"'{req.permit}', or remove the requirement if it is no longer needed. "
            f"See el_reasoner.ungrantable_permit_requirements(model)."
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
    model: Any,
) -> List[str]:
    """
    V-15: a Delegation's transfer must trace back to a resolvable origin.

    AM-55: structural-first, mirroring AM-54's el_reasoner.py fix (same
    conceptual gap in a different layer — free-text obligation matching
    alone is not standard-grounded; §6.4.7 NOTE 1 describes delegation as
    literal token transfer). A Delegation with a structural reference
    (transfers_burden / transfers_token_group) is checked by that alone:
    is at least one referenced token's origin resolvable via a Commitment
    naming it, or a Role's 'holds' naming it (AM-53-style role-conferred
    grounding)? "Delegation-continuation" (a mid-chain delegation passing
    along an already-grounded token) needs no separate case — grounding
    is checked per TOKEN NAME, not per delegation-chain-position, so any
    delegation moving an already-grounded token is automatically valid.
    Per-token-group-member auditing is V-16a's job, not this rule's — V-15
    only needs at least one referenced token grounded to confirm this
    Delegation isn't wholly obligation-orphaned.

    A Delegation with NO structural reference at all (grammar-legal, but
    ground-truth confirmed zero live examples across every scenario file —
    see AM-54's amendment entry) falls back to the original free-text
    check: its obligation text must exactly match some Commitment's.
    """
    errors: List[str] = []
    committed_token_names = {
        _obj_name(getattr(c, "burden", None)) for c in commitments
    } - {""}
    role_held_token_names = {
        _obj_name(tok)
        for community in _collect(model, "Community") + _collect(model, "Federation")
        for role in getattr(community, "roles", [])
        for tok in getattr(role, "holds_tokens", [])
    } - {""}
    grounded_token_names = committed_token_names | role_held_token_names
    committed_obligations = {c.obligation for c in commitments}

    for d in delegations:
        burden_name = _obj_name(getattr(d, "burden", None))
        group = getattr(d, "token_group", None)
        group_names = (
            {_obj_name(t) for t in getattr(group, "tokens", [])} - {""}
            if group is not None else set()
        )
        referenced = ({burden_name} if burden_name else set()) | group_names

        if referenced:
            if not (referenced & grounded_token_names):
                errors.append(
                    f"[V-15] Delegation '{d.name}': none of its referenced "
                    f"token(s) ({sorted(referenced)}) has a resolvable "
                    f"origin — no Commitment names it and no Role 'holds' "
                    f"it. (§7.10.1)"
                )
            continue

        if d.obligation not in committed_obligations:
            errors.append(
                f"[V-15] Delegation '{d.name}': obligation '{d.obligation}' "
                f"does not match any CommitmentDecl. "
                f"Delegation chain has no commitment root. (§7.10.1)"
            )

    return errors


def _validate_embargo_for_action_consistency(model) -> List[str]:
    """W-18 (AM-102): an Embargo that one or more role Actions name via
    `inhibited_by_embargo`, and whose for_action is outside that set.
    Under the shared blocking rule (el_engine._embargo_coverage()) the
    naming Actions decide what the embargo blocks, in the engine and the
    verifier alike, so the for_action is ignored — the reader of the
    spec would expect it to be blocked, and it is not. Advisory, never an
    error. Built from el_engine._embargo_naming_actions(), the map the
    blocking rule itself reads, so the two cannot diverge. Role Action
    bodies only (ConditionalAction is not read by anything)."""
    from el_engine import _embargo_naming_actions

    named = _embargo_naming_actions(model)
    warnings: List[str] = []
    for tok in _collect(model, "DeonticToken"):
        if getattr(tok, "kind", None) != "embargo":
            continue
        for_action = getattr(tok, "for_action", None)
        actions = named.get(tok.name)
        if not for_action or not actions or for_action in actions:
            continue
        warnings.append(
            f"[W-18] Embargo '{tok.name}' has for_action '{for_action}', but "
            f"the Actions that declare inhibited_by_embargo {tok.name} are "
            f"{sorted(actions)}. The embargo blocks those Actions only; "
            f"'{for_action}' is not blocked by it. Name '{for_action}' in its "
            f"for_action only if it is one of them, or add inhibited_by_embargo "
            f"{tok.name} to '{for_action}'. (§6.4.4, §6.4.6)"
        )
    return warnings


def _strict_burdens(model) -> List[Any]:
    """AM-103: every discharge_mode: strict Burden — top-level DeonticTokens
    and role-scoped InlineTokens (AM-24; P3 places them in role.holds_tokens)."""
    tokens = list(_collect(model, "DeonticToken"))
    for el in model.elements:
        if _cls(el) not in ("Community", "Domain", "Federation"):
            continue
        for role in getattr(el, "roles", []) or []:
            tokens.extend(t for t in getattr(role, "holds_tokens", []) or []
                          if _cls(t) == "InlineToken")
    return [t for t in tokens
            if getattr(t, "kind", None) == "burden"
            and getattr(t, "discharge_mode", None) == "strict"]


def _validate_strict_burden_deadline(model) -> List[str]:
    """W-19 (AM-103): a strict Burden with no deadline that carries an
    elapsed-time magnitude. The live engine never violates a strict Burden
    on its clock (check_live_violations() excludes them); its violation is
    to come from an external, authorised violation declaration, which needs
    a deadline to judge against. "A deadline" means
    el_engine._has_deadline_magnitude() is true — the same test
    check_live_violations() uses for a genuine deadline. A prose deadline
    ("clinical session") or a bare number only yields
    _parse_deadline_steps()'s default of 5, which does not count.
    The token's own `deadline` is the only source: Commitment has no
    deadline field. Advisory, never an error."""
    from el_engine import _has_deadline_magnitude

    warnings: List[str] = []
    for tok in _strict_burdens(model):
        deadline = getattr(tok, "deadline", None) or None
        if _has_deadline_magnitude(deadline):
            continue
        if deadline is None:
            problem = "has no deadline"
        else:
            problem = (f"has deadline '{deadline}', which carries no elapsed-time "
                       f"magnitude (a number with a unit)")
        warnings.append(
            f"[W-19] Strict burden '{tok.name}' {problem}. Its violation can only "
            f"be declared against a deadline; the verifier falls back to 5 steps "
            f"and the engine cannot measure it. Add a deadline such as "
            f"\"15 minutes\". (§6.4.3, §7.8.7)"
        )
    return warnings


def _validate_strict_burden_violation_response(model) -> List[str]:
    """W-20 (AM-103): a strict Burden that no ViolationResponse names in
    on_violation_of. While it is actionable, the engine refuses every
    non-discharging action (Step 3.5); if its holder never acts, nothing
    responds. Fires on every such Burden, including ones whose
    enforcement point discharges them atomically (executing-compelled),
    which the validator cannot distinguish; the message names that
    exception. Advisory, never an error."""
    named = {
        getattr(getattr(vr, "violated_burden", None), "name", None)
        for vr in _collect(model, "ViolationResponse")
    }
    warnings: List[str] = []
    for tok in _strict_burdens(model):
        if tok.name in named:
            continue
        warnings.append(
            f"[W-20] Strict burden '{tok.name}' is named by no ViolationResponse "
            f"(on_violation_of). If its holder never discharges it, nothing "
            f"responds. Not needed if the enforcement point discharges the burden "
            f"atomically; otherwise add a violation_response. (§6.3.8, §7.8.6)"
        )
    return warnings


def _validate_terminate_response_target(model) -> List[str]:
    """W-21 (AM-104): a response_kind terminate ViolationResponse that
    would fire and revoke nothing. On fire, the engine revokes each
    Authorization whose to_agent is in the violator chain
    (el_engine._violator_chain() of the violated burden's holder), that is
    revocable with an on_revocation embargo, and whose authority is the
    response's obligates. Warns when no declared Authorization meets all
    of these. The holder is the one el_engine._build_obligation_descriptors()
    resolves (root construct, then the delegation walk); a burden with no
    descriptor has no static holder and is skipped. to_role Authorizations
    are not revoked by terminate, so they do not count. Advisory."""
    from el_engine import _build_obligation_descriptors, _violator_chain

    descriptors = _build_obligation_descriptors(model)
    authorizations = _collect(model, "Authorization")
    warnings: List[str] = []
    for vr in _collect(model, "ViolationResponse"):
        if getattr(vr, "response_kind", None) != "terminate":
            continue
        burden = _obj_name(getattr(vr, "violated_burden", None))
        desc = descriptors.get(burden)
        if desc is None:
            continue
        responder = _obj_name(getattr(vr, "responding_actor", None))
        chain = _violator_chain(model, desc.holder)
        revocable = [
            a for a in authorizations
            if _obj_name(getattr(a, "authorized_agent", None)) in chain
            and getattr(a, "revocable", False)
            and getattr(a, "on_revocation_embargo", "")
            and _obj_name(getattr(a, "authority", None)) == responder
        ]
        if revocable:
            continue
        warnings.append(
            f"[W-21] Terminate response '{vr.name}' has nothing to revoke: no "
            f"revocable Authorization with an on_revocation embargo, granted by "
            f"'{responder}', is held by '{desc.holder}' or its agents "
            f"({', '.join(sorted(chain))}). It would fire and do nothing. "
            f"(§6.3.8, §7.8.6, §6.6.4)"
        )
    return warnings


def _validate_escalate_response_burden(model) -> List[str]:
    """W-22 (AM-104): a response_kind escalate ViolationResponse with no
    creates_burden. It fires as a ledger entry only; nobody becomes
    obligated to act on the escalation, although §7.8.6 NOTE 2 makes the
    response rule an obligation on the object it applies to. Advisory."""
    warnings: List[str] = []
    for vr in _collect(model, "ViolationResponse"):
        if getattr(vr, "response_kind", None) != "escalate":
            continue
        if getattr(vr, "creates_burden", None) is not None:
            continue
        warnings.append(
            f"[W-22] Escalate response '{vr.name}' has no creates_burden: it "
            f"fires as a ledger entry only; nobody becomes obligated. "
            f"(§6.3.8, §7.8.6 NOTE 2)"
        )
    return warnings


def _validate_escalate_to_party(model) -> List[str]:
    """W-23 (AM-104): the dormant V-NEW-16 from el_domain.ViolationResponse's
    docstring, as a warning — a response_kind escalate ViolationResponse
    must name a party in escalate_to. Missing escalate_to also warns.
    Advisory."""
    warnings: List[str] = []
    for vr in _collect(model, "ViolationResponse"):
        if getattr(vr, "response_kind", None) != "escalate":
            continue
        target = getattr(vr, "escalate_to", None)
        if target is None:
            problem = "names no escalate_to"
        elif getattr(target, "kind", None) != "party":
            problem = f"escalates to '{target.name}' ({getattr(target, 'kind', None)}), not a party"
        else:
            continue
        warnings.append(
            f"[W-23] Escalate response '{vr.name}' {problem}. Escalation goes "
            f"to a party. (V-NEW-16; §6.3.8, §7.4)"
        )
    return warnings


def _validate_unviolatable_eventual_burden(model) -> List[str]:
    """W-24 (AM-108): an eventual Burden (top-level or role-scoped) whose
    deadline has no elapsed-time magnitude (el_engine._has_deadline_magnitude():
    prose, a bare number, or none) and that has no episode-conclusion path:
    it is not in the satisfaction group of any Community/Federation/Domain
    that opts in with lifecycle { terminating { on_objective_achieved: true } },
    together with at least one other member. The engine then never violates
    it (check_live_violations(): no clock without a magnitude, no conclusion
    without such a group), and since AM-108 neither does the verifier (T2
    skips it, T2b needs the group). Strict burdens are [W-19]'s. Advisory."""
    from el_engine import (
        _build_satisfaction_conditions,
        _concludes_on_objective_achieved,
        _has_deadline_magnitude,
    )

    concludes = {
        el.name: _concludes_on_objective_achieved(el)
        for el in model.elements
        if _cls(el) in ("Community", "Federation", "Domain")
    }
    concludable: Set[str] = set()
    for el_name, (_op, members) in _build_satisfaction_conditions(model).items():
        if concludes.get(el_name) and len(members) > 1:
            concludable.update(members)

    tokens = list(_collect(model, "DeonticToken"))
    for el in model.elements:
        if _cls(el) not in ("Community", "Domain", "Federation"):
            continue
        for role in getattr(el, "roles", []) or []:
            tokens.extend(t for t in getattr(role, "holds_tokens", []) or []
                          if _cls(t) == "InlineToken")

    warnings: List[str] = []
    for tok in tokens:
        if getattr(tok, "kind", None) != "burden":
            continue
        if (getattr(tok, "discharge_mode", None) or "eventual") != "eventual":
            continue
        deadline = getattr(tok, "deadline", None) or None
        if _has_deadline_magnitude(deadline) or tok.name in concludable:
            continue
        shown = f"'{deadline}'" if deadline else "none"
        warnings.append(
            f"[W-24] Eventual burden '{tok.name}' has no enforceable deadline "
            f"({shown}) and no episode-conclusion path: it is never violated, "
            f"at runtime or in the verifier. Give it a deadline with a time "
            f"unit, or put it in a satisfaction group whose community opts in "
            f"with on_objective_achieved. (§6.4.3, §7.8.7)"
        )
    return warnings


def _validate_burden_embargo_conflict(model) -> List[str]:
    """
    V-17: An ACTIVE Burden's for_action must not match an ACTIVE Embargo's
    for_action — the spec would obligate an actor to perform the one
    action it is simultaneously prohibited from performing. (§6.4.3
    obligation, §6.4.4 prohibition)

    Specification-time check, not a Kripke/runtime one — consistent with
    the specification_time_assurance conflict-resolution strategy already
    used at the federation level (§7.9.1 NOTE 3), rather than letting the
    Kripke builder (el_kripke.py) silently mask or resolve the conflict at
    model-construction time.

    Direct for_action-to-for_action string comparison — the field both
    Burden and Embargo already carry — not DeonticToken.inhibited_by_embargo
    (confirmed dead/unused repo-wide during T5's build: no scenario sets it,
    no toolchain code reads it) and not the Action-scoped
    inhibited_by_embargo linkage T5's Embargo guard uses
    (el_kripke.py:_build_embargo_inhibition_index). This rule checks a
    different, simpler thing than that guard: not "is this specific Permit
    blocked by a linked Embargo" but "does a Burden's required action
    directly collide with an Embargo's prohibited action" — no
    Action-scoped traversal needed here.

    Single-domain-scoped, same caveat as T5's Embargo guard: cannot detect
    conflicts where the Burden and Embargo belong to different domains in a
    federation, since domain_scope does not exist on bare DeonticToken
    today — see "Permit/Embargo missing domain scope" in
    docs/CONCEPTS_INDEX.md.
    """
    errors: List[str] = []
    burdens = [
        t for t in _collect(model, "DeonticToken")
        if getattr(t, "kind", None) == "burden"
        and getattr(t, "state", None) == "active"
        and getattr(t, "for_action", None)
    ]
    embargoes = [
        t for t in _collect(model, "DeonticToken")
        if getattr(t, "kind", None) == "embargo"
        and getattr(t, "state", None) == "active"
        and getattr(t, "for_action", None)
    ]

    for burden in burdens:
        for embargo in embargoes:
            if burden.for_action == embargo.for_action:
                errors.append(
                    f"[V-17] Burden '{burden.name}' requires action "
                    f"'{burden.for_action}', which Embargo '{embargo.name}' "
                    f"actively prohibits — normative conflict. (§6.4.3, §6.4.4)"
                )

    return errors
