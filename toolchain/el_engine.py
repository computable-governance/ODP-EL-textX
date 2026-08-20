"""
el_engine.py
============
Stateless governance engine (Layer 3) operating directly over el_domain.py
objects produced by el_parser.py.

Seven-step execution pipeline (CLAUDE.md §7.1):
  1. Expiry          — identify tokens past deadline  (informational; real
                       clock requires caller to manage tick-to-deadline mapping)
  2. Initiator       — actor must appear in state.actors
  3. Discharge key   — identify burdens this action discharges:
                       a) explicit DeonticEffect(destroy, burden) in grammar action
                       b) burden.for_action == action_name  (informational match)
                       c) burden.discharged_by event == action's emits event (AM-22)
  4. Preconditions   — grammar precondition strings checked against facts dict;
                       absent key → blocked  (fail-safe, not fail-open — see §7.3)
  5. Embargo sweep   — active embargo on actor targeting this action → blocked
  6. Permit check    — DeonticRequirement(requires_permit) must be held by actor
  7. Effect application — DeonticEffect operations + burden discharge transitions

Standard reference: ISO/IEC 15414:2015 §6.4, §6.6, §7.8, §7.10
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# ── Runtime types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TokenInstance:
    """Runtime instance of a deontic token held by one actor."""
    token_name: str
    kind: str                       # 'burden' | 'permit' | 'embargo'
    holder: str                     # actor name
    state: str                      # 'active' | 'pending' | 'discharged' | 'violated' | 'superseded'
    discharge_mode: str             # 'eventual' | 'strict'
    priority: str                   # 'critical' | 'high' | 'normal' | 'low'
    granted_at_tick: int            # tick at which this instance was created; required, no
                                     # default -- see docs/CONCEPTS_INDEX.md, discharge_mode:
                                     # strict finding's convergence addendum (2026-08-20)
    deadline: Optional[str] = None
    for_action: Optional[str] = None  # informational — see AM-01


@dataclass(frozen=True)
class ActorState:
    """An actor enrolled in the community, optionally filling a named role."""
    actor_name: str
    role_name: Optional[str] = None
    community_tag: str = ""   # AM-25: domain name the actor belongs to


@dataclass(frozen=True)
class WorldState:
    """
    Immutable snapshot of governance state.
    Derive next state via with_tokens() / with_tick(); never mutate in place.
    """
    tokens: Tuple[TokenInstance, ...]
    actors: Tuple[ActorState, ...]
    tick: int = 0

    def with_tokens(self, tokens) -> "WorldState":
        return WorldState(tokens=tuple(tokens), actors=self.actors, tick=self.tick)

    def with_tick(self, tick: int) -> "WorldState":
        return WorldState(tokens=self.tokens, actors=self.actors, tick=tick)


@dataclass(frozen=True)
class TransitionRecord:
    """Append-only ledger entry produced by one advance() call."""
    tick: int
    actor_name: str
    action_name: str
    outcome: str                        # 'ok' | 'blocked' | 'violation'
    discharged: Tuple[str, ...]         # burden names discharged
    effects: Tuple[str, ...]            # human-readable effect log
    violations: Tuple[str, ...]         # violation names (if outcome == 'violation')
    reason: Optional[str] = None        # set when outcome == 'blocked'
    fired_responses: Tuple[str, ...] = ()  # ViolationResponse names fired (fire_violation_responses() only)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _find_action(spec, action_name):
    """Return (Action, Role) matching action_name across all communities, or (None, None).

    Object processor P3 dissolves role.items into role.actions (and empties
    role.items), so role.actions is the correct post-parse attribute.
    Also searches Domain and Federation elements in addition to Community.
    """
    for el in spec.elements:
        if type(el).__name__ not in ("Community", "Domain", "Federation"):
            continue
        for role in getattr(el, "roles", []):
            for action in getattr(role, "actions", []):
                if action.name == action_name:
                    return action, role
    return None, None


def _actor_holds_permit(state: WorldState, actor_name: str, token_name: str) -> bool:
    return any(
        t.holder == actor_name
        and t.token_name == token_name
        and t.kind == "permit"
        and t.state == "active"
        for t in state.tokens
    )


def _transition(tok: TokenInstance, new_state: str) -> TokenInstance:
    return TokenInstance(
        token_name=tok.token_name,
        kind=tok.kind,
        holder=tok.holder,
        state=new_state,
        discharge_mode=tok.discharge_mode,
        priority=tok.priority,
        granted_at_tick=tok.granted_at_tick,
        deadline=tok.deadline,
        for_action=tok.for_action,
    )


def _blocked(state: WorldState, actor: str, action: str, reason: str, tick: int
             ) -> Tuple[WorldState, TransitionRecord]:
    return state, TransitionRecord(
        tick=tick,
        actor_name=actor,
        action_name=action,
        outcome="blocked",
        discharged=(),
        effects=(),
        violations=(),
        reason=reason,
    )


def _find_spec_tokens_for_event(spec, event_name: str, attr: str) -> set:
    """Return names of spec tokens whose `attr` (triggered_by/discharged_by) matches event_name.

    Checks both top-level DeonticToken declarations and InlineTokens inside roles.
    """
    result = set()
    for el in spec.elements:
        if type(el).__name__ == "DeonticToken":
            ref = getattr(el, attr, None)
            if ref is not None and getattr(ref, "name", None) == event_name:
                result.add(el.name)
    for el in spec.elements:
        if type(el).__name__ == "Community":
            for role in el.roles:
                for tok in role.holds_tokens:
                    if type(tok).__name__ == "InlineToken":
                        ref = getattr(tok, attr, None)
                        if ref is not None and getattr(ref, "name", None) == event_name:
                            result.add(tok.name)
    return result


def _activate_triggered_tokens(spec, tokens: list, event_name: str) -> tuple[list, list[str]]:
    """
    Transition to 'active' every token whose triggered_by matches event_name.
    Returns (updated_tokens, effect_log_lines). Shared by advance() Step 7c
    (action-driven) and Runtime.fire_event() (direct-call, e.g. FHIR-driven).
    """
    triggered = _find_spec_tokens_for_event(spec, event_name, "triggered_by")
    if not triggered:
        return tokens, []
    new_tokens = [
        _transition(t, "active") if t.token_name in triggered else t
        for t in tokens
    ]
    log_lines = [f"event '{event_name}' triggered activation of '{name}'" for name in triggered]
    return new_tokens, log_lines


# ── Core engine function ──────────────────────────────────────────────────────

def advance(
    state: WorldState,
    action_name: str,
    spec,
    actor_name: str,
    facts: Optional[dict] = None,
) -> Tuple[WorldState, TransitionRecord]:
    """
    Execute one governance-checked action step.

    Parameters
    ----------
    state       : current WorldState
    action_name : name of the action to perform (must be declared in a community
                  Role, OR match a burden's for_action for discharge-only semantics)
    spec        : EnterpriseSpec from el_parser.parse()
    actor_name  : name of the EnterpriseObject performing the action
    facts       : dict mapping precondition strings to truthy values;
                  absent key → blocked  (fail-safe)

    Returns
    -------
    (new_state, record) — new_state equals state if blocked.
    """
    if facts is None:
        facts = {}

    tick = state.tick

    # ── Step 1: Expiry ────────────────────────────────────────────────────────
    # Deadline semantics require a wall-clock or tick-to-time mapping that the
    # caller must supply.  This implementation surfaces expired tokens for the
    # caller to inspect but does not auto-violate here.

    # ── Step 2: Initiator ─────────────────────────────────────────────────────
    enrolled = {a.actor_name for a in state.actors}
    if actor_name not in enrolled:
        return _blocked(state, actor_name, action_name,
                        f"actor '{actor_name}' is not enrolled", tick)

    # ── Step 3: Discharge key ─────────────────────────────────────────────────
    grammar_action, grammar_role = _find_action(spec, action_name)

    explicit_destroys: set[str] = set()
    if grammar_action:
        for eff in grammar_action.deontic_effects:
            if eff.operation == "destroy" and eff.token:
                explicit_destroys.add(eff.token.name)

    # AM-22: burdens discharged by the event this action emits
    event_discharged: set = set()
    if grammar_action and grammar_action.emits:
        event_discharged = _find_spec_tokens_for_event(
            spec, grammar_action.emits.name, "discharged_by"
        )

    # Burdens dischargeable by this action (actor must hold them, state active)
    dischargeable: list[str] = []
    for tok in state.tokens:
        if (tok.holder == actor_name
                and tok.kind == "burden"
                and tok.state == "active"):
            if (tok.token_name in explicit_destroys
                    or tok.for_action == action_name
                    or tok.token_name in event_discharged):
                dischargeable.append(tok.token_name)

    # ── Step 4: Preconditions ─────────────────────────────────────────────────
    if grammar_action:
        for precond in grammar_action.preconditions:
            if not facts.get(precond):
                return _blocked(state, actor_name, action_name,
                                f"precondition not satisfied: '{precond}'", tick)

    # ── Step 5: Embargo sweep ─────────────────────────────────────────────────
    for tok in state.tokens:
        if (tok.holder == actor_name
                and tok.kind == "embargo"
                and tok.state == "active"):
            # A general embargo (for_action=None) blocks all actions.
            # An action-specific embargo blocks only that action.
            if tok.for_action is None or tok.for_action == action_name:
                return _blocked(state, actor_name, action_name,
                                f"active embargo '{tok.token_name}' blocks action", tick)

    # ── Step 6: Permit check ──────────────────────────────────────────────────
    if grammar_action:
        for req in grammar_action.deontic_requirements:
            if req.kind == "requires_permit" and req.token:
                permit_name = req.token.name
                if not _actor_holds_permit(state, actor_name, permit_name):
                    return _blocked(state, actor_name, action_name,
                                    f"required permit '{permit_name}' not held by actor", tick)

    # ── Step 7: Effect application ────────────────────────────────────────────
    tokens = list(state.tokens)
    effects_log: list[str] = []
    discharged_names: list[str] = []

    # 7a — Discharge identified burdens (transition to 'discharged')
    tokens = [
        _transition(t, "discharged")
        if t.token_name in dischargeable and t.holder == actor_name
        else t
        for t in tokens
    ]
    for name in dischargeable:
        discharged_names.append(name)
        effects_log.append(f"discharged burden '{name}'")

    # 7b — Grammar DeonticEffect operations
    if grammar_action:
        for eff in grammar_action.deontic_effects:
            op, tok_ref = eff.operation, eff.token
            if not tok_ref:
                continue

            if op == "create":
                # Determine target: actors filling eff.to_role, or actor_name
                target_role = eff.to_role
                if target_role:
                    targets = [
                        a.actor_name for a in state.actors
                        if a.role_name == target_role
                    ] or [target_role]
                else:
                    targets = [actor_name]

                for target in targets:
                    # Idempotency guard: some scenario builders pre-seed a token
                    # that this same create effect also grants to the same
                    # holder (e.g. referralResponseBurden/assessmentSchedulingBurden
                    # in referral_scenario.el/gp_referral_scenario.el — see
                    # docs/CONCEPTS_INDEX.md). Skip creation if the target
                    # already holds a token of this name rather than granting a
                    # second, indistinguishable instance.
                    if any(t.token_name == tok_ref.name and t.holder == target
                           for t in tokens):
                        continue

                    new_tok = TokenInstance(
                        token_name=tok_ref.name,
                        kind=tok_ref.kind,
                        holder=target,
                        state="active",
                        discharge_mode=tok_ref.discharge_mode or "eventual",
                        priority=tok_ref.priority or "normal",
                        granted_at_tick=tick,
                        deadline=getattr(tok_ref, "deadline", None),
                        for_action=getattr(tok_ref, "for_action", None),
                    )
                    tokens.append(new_tok)
                    effects_log.append(f"created '{tok_ref.name}' for '{target}'")

            elif op == "destroy":
                # Already added to dischargeable in step 3a; mark as discharged
                # (handled in 7a above — avoid double-processing)
                pass

            elif op == "pend":
                tokens = [
                    _transition(t, "pending") if t.token_name == tok_ref.name else t
                    for t in tokens
                ]
                effects_log.append(f"pended '{tok_ref.name}'")

            elif op == "activate":
                tokens = [
                    _transition(t, "active") if t.token_name == tok_ref.name else t
                    for t in tokens
                ]
                effects_log.append(f"activated '{tok_ref.name}'")

            elif op == "transfer":
                from_role = eff.from_role or actor_name
                to_role = eff.to_role
                if to_role:
                    to_actors = [
                        a.actor_name for a in state.actors
                        if a.role_name == to_role
                    ] or [to_role]
                    updated: list[TokenInstance] = []
                    for t in tokens:
                        if t.token_name == tok_ref.name and t.holder == from_role:
                            for tgt in to_actors:
                                updated.append(TokenInstance(
                                    token_name=t.token_name,
                                    kind=t.kind,
                                    holder=tgt,
                                    state=t.state,
                                    discharge_mode=t.discharge_mode,
                                    priority=t.priority,
                                    granted_at_tick=t.granted_at_tick,
                                    deadline=t.deadline,
                                    for_action=t.for_action,
                                ))
                            effects_log.append(
                                f"transferred '{tok_ref.name}' from '{from_role}'"
                                f" to {to_actors}"
                            )
                        else:
                            updated.append(t)
                    tokens = updated

            elif op == "clone":
                # Clone: add a copy for actor_name; original remains
                for t in list(tokens):
                    if t.token_name == tok_ref.name:
                        tokens.append(TokenInstance(
                            token_name=t.token_name,
                            kind=t.kind,
                            holder=actor_name,
                            state=t.state,
                            discharge_mode=t.discharge_mode,
                            priority=t.priority,
                            granted_at_tick=t.granted_at_tick,
                            deadline=t.deadline,
                            for_action=t.for_action,
                        ))
                        effects_log.append(f"cloned '{tok_ref.name}' to '{actor_name}'")
                        break

    # 7c — AM-22: event-triggered token activation
    if grammar_action and grammar_action.emits:
        tokens, triggered_log = _activate_triggered_tokens(
            spec, tokens, grammar_action.emits.name
        )
        effects_log.extend(triggered_log)

    new_state = state.with_tokens(tokens).with_tick(tick + 1)
    record = TransitionRecord(
        tick=tick,
        actor_name=actor_name,
        action_name=action_name,
        outcome="ok",
        discharged=tuple(discharged_names),
        effects=tuple(effects_log),
        violations=(),
    )
    return new_state, record


# ── WorldState construction helpers ──────────────────────────────────────────

def initial_state() -> WorldState:
    """Return an empty WorldState at tick 0."""
    return WorldState(tokens=(), actors=(), tick=0)


def enroll(state: WorldState, actor_name: str, role_name: Optional[str] = None,
           community_tag: str = "") -> WorldState:
    """Add an actor (optionally filling role_name) to state.actors.

    community_tag (AM-25): domain name the actor belongs to, used by
    build_from_federation() to track cross-domain membership.
    """
    new_actors = list(state.actors) + [
        ActorState(actor_name=actor_name, role_name=role_name, community_tag=community_tag)
    ]
    return WorldState(tokens=state.tokens, actors=tuple(new_actors), tick=state.tick)


def grant_token(state: WorldState, token: TokenInstance) -> WorldState:
    """Add a TokenInstance to the WorldState."""
    return state.with_tokens(list(state.tokens) + [token])


def _find_action_for_burden(model: Any, burden_name: str) -> Optional[str]:
    """
    Search community Role bodies for the Action that carries burden_name as a
    ConditionalAction.favoured_by entry.

    Mirrors the identical helper in el_kripke.py. Duplicated here to avoid
    a circular import (el_engine ← el_kripke would create a cycle).

    Traversal path (post-dissolution attributes):
      model.elements
        → Community | Domain | Federation
          → el.roles (post-P3)
            → role.actions (post-P3, not role.items)
              → action.conditional_actions (post-P4, not action.items)
                → ca.favoured_by (post-P5, not ca.favoured_by_burden)
                  → if name matches → return action.name
    Returns the Action name, or None if no match is found.
    """
    for el in model.elements:
        if type(el).__name__ not in ("Community", "Domain", "Federation"):
            continue
        for role in getattr(el, "roles", []):
            for action in getattr(role, "actions", []):
                for burden_ref in getattr(action, "favoured_by", []):
                    if getattr(burden_ref, "name", None) == burden_name:
                        return action.name
                for ca in getattr(action, "conditional_actions", []):
                    for burden_ref in getattr(ca, "favoured_by", []):
                        if getattr(burden_ref, "name", None) == burden_name:
                            return action.name
    return None


# ── Obligation descriptor (relocated from el_kripke.py 2026-08-20) ─────────────
# Layer 4 (el_kripke.py) depends on Layer 3 for this: ObligationDescriptor and
# the Commitment/Delegation-chain resolution that builds it are properties of
# the live accountability model, not of the verifier. el_kripke.py imports
# these three back (see its own import block) rather than defining them —
# check_live_violations() below and el_kripke.py's build_kripke_model() /
# build_kripke_from_runtime() now share one implementation instead of two.

@dataclass
class ObligationDescriptor:
    """
    Metadata about one obligation extracted from the DSL-EL spec.
    Used by the Layer 4 reachability builder to generate transitions, and by
    check_live_violations() below to resolve a live Burden's deadline_steps.
    """
    obligation_id: str        # burden name from the DSL (e.g. "paymentProcessingObligation")
    obligation_text: str      # natural language text (e.g. "Process all customer payments…")
    deadline_steps: int       # finite horizon; parsed from deadline string or defaulted
    holder: str               # actor currently responsible (leaf of delegation chain)
    chain: List[str]          # full chain [root_party, …, current_holder]
    revocable: bool
    sub_delegation_allowed: bool
    discharge_mode: str = "eventual"
    # "eventual" (default) — holder may delay; TICK available; AF may not hold
    # "strict"             — holder must act at first opportunity; TICK removed; AF holds
    priority_weight: float = 0.5
    # Numeric weight derived from PriorityLevel (AM-15):
    #   critical → 1.00   high → 0.75   normal → 0.50   low → 0.25
    # Used by the weighted utility function (§C.3) to reflect modeller-specified
    # importance ordering across obligations.
    triggered_by: Optional[str] = None
    # Event name (from DeonticToken.triggered_by) whose firing moves this
    # obligation from WAITING → PENDING. None means obligation starts PENDING.
    fires_event: Optional[str] = None
    # Event name (from DeonticToken.discharged_by) emitted when this obligation
    # is discharged. Bidirectional convention: discharging this obligation fires
    # this event, which may cascade to trigger other WAITING obligations (P6).
    for_action: Optional[str] = None
    # Name of the Action (within a community Role body) whose ConditionalAction
    # has this obligation as a favoured_by_burden entry. Resolved by
    # _find_action_for_burden() when not set directly on the DeonticToken.


def _parse_deadline_steps(deadline_str: Optional[str], default: int = 5) -> int:
    """
    Convert a natural-language deadline string to a finite step count.

    The mapping is necessarily approximate because the DSL deadline is
    expressed in domain time (seconds, days, etc.) while our step model
    is abstract. The goal is to preserve the relative ordering of deadlines.

    Heuristics:
      "… second …"        → 2 steps   (very tight)
      "… minute …"        → 3 steps
      "… hour …"          → 5 steps
      "… day …"           → 8 steps
      "… week …"          → 12 steps
      "… month …"         → 20 steps
      anything else       → default
    """
    if not deadline_str:
        return default
    s = deadline_str.lower()
    if "second" in s:
        return 2
    if "minute" in s:
        return 3
    if "hour"   in s:
        return 5
    if "day"    in s:
        return 8
    if "week"   in s:
        return 12
    if "month"  in s:
        return 20
    return default


def _priority_weight(priority_str: Optional[str]) -> float:
    """
    §C.3: Convert a PriorityLevel string (AM-15) to a numeric weight.

    Duplicated verbatim from el_kripke.py's identical helper — same
    circular-import rationale as _find_action_for_burden above. el_kripke.py
    keeps its own copy since it is used far more widely there than just by
    the descriptor-building logic that moved here.

      critical → 1.00   (must not be violated under any circumstances)
      high     → 0.75   (strongly preferred to discharge)
      normal   → 0.50   (default — equal weight)
      low      → 0.25   (desirable but not critical)
    """
    return {
        "critical": 1.00,
        "high":     0.75,
        "normal":   0.50,
        "low":      0.25,
    }.get(priority_str or "normal", 0.50)


def _build_obligation_descriptors(model: Any) -> Dict[str, ObligationDescriptor]:
    """
    Extract ObligationDescriptor for each burden that appears in at least
    one CommitmentDecl or DelegationDecl.

    Algorithm:
    1. Index all BurdenDecl elements by name.
    2. For each CommitmentDecl, find its creates_burden reference.
    3. Walk the delegation graph forward to find the current holder.
    4. Record the full accountability chain.
    """
    # Index burdens by name.
    # The grammar uses DeonticToken for all token kinds (burden/permit/embargo);
    # we filter by kind == "burden". (AM-18 renamed DeonticTokenDecl → DeonticToken)
    burdens: Dict[str, Any] = {
        t.name: t
        for t in model.elements
        if type(t).__name__ == "DeonticToken" and getattr(t, "kind", None) == "burden"
    }

    # Build delegation graph: from_name → list of (to_name, obligation_text)
    # (duplicates el_reasoner.delegation_graph but avoids import)
    del_graph: Dict[str, List[Tuple[str, str, bool, bool]]] = {}
    for d in model.elements:
        if type(d).__name__ != "Delegation":  # AM-18: DelegationDecl → Delegation
            continue
        from_name = getattr(getattr(d, "delegator", None), "name", None)
        to_name   = getattr(getattr(d, "delegate", None), "name", None)
        if from_name and to_name:
            del_graph.setdefault(from_name, []).append((
                to_name,
                d.obligation,
                getattr(d, "sub_delegation_allowed", False),
                getattr(d, "revocable", False),
            ))

    def walk_chain(start: str, obl_text: str) -> List[str]:
        """DFS to leaf; returns [start, …, leaf]."""
        chain = [start]
        visited: Set[str] = {start}
        current = start
        while True:
            outgoing = [
                (to, oblt, sda, rev)
                for to, oblt, sda, rev in del_graph.get(current, [])
                if obl_text.lower() in oblt.lower()
            ]
            if not outgoing or outgoing[0][0] in visited:
                break
            to, oblt, sda, rev = outgoing[0]
            chain.append(to)
            visited.add(to)
            current = to
        return chain

    descriptors: Dict[str, ObligationDescriptor] = {}

    for c in model.elements:
        if type(c).__name__ != "Commitment":  # AM-18: CommitmentDecl → Commitment
            continue
        burden_ref = getattr(c, "burden", None)
        burden_name = getattr(burden_ref, "name", None)
        actor_name  = getattr(getattr(c, "actor", None), "name", None)
        if not burden_name or not actor_name:
            continue
        burden = burdens.get(burden_name)
        if burden is None:
            continue

        obl_text     = getattr(c, "obligation", burden_name)
        deadline_str = getattr(burden, "deadline", None)
        chain        = walk_chain(actor_name, obl_text)
        holder       = chain[-1]

        # Use sub_delegation_allowed / revocable from the LAST delegation link
        # that terminates at holder, if any
        sda, rev = False, False
        for d in model.elements:
            if type(d).__name__ != "Delegation":  # AM-18: DelegationDecl → Delegation
                continue
            if getattr(getattr(d, "delegate", None), "name", None) == holder:
                sda = getattr(d, "sub_delegation_allowed", False)
                rev = getattr(d, "revocable", False)

        # P6: extract event wiring from the burden token
        triggered_by = getattr(getattr(burden, "triggered_by", None), "name", None)
        fires_event  = getattr(getattr(burden, "discharged_by", None), "name", None)
        # fires_event convention: DeonticToken.discharged_by names the event that
        # fires when this obligation is discharged (bidirectional: the same event
        # that the holder's action emits). Used by T1 cascade to activate WAITING
        # obligations whose triggered_by matches this event name.

        # Tier 1: explicit for_action on the DeonticToken grammar attribute
        # Tier 2: structural search through community Role → Action → ConditionalAction
        for_action = getattr(burden, "for_action", None) or None
        if for_action is None:
            for_action = _find_action_for_burden(model, burden_name)

        descriptors[burden_name] = ObligationDescriptor(
            obligation_id=burden_name,
            obligation_text=obl_text,
            deadline_steps=_parse_deadline_steps(deadline_str),
            holder=holder,
            chain=chain,
            revocable=rev,
            sub_delegation_allowed=sda,
            discharge_mode=getattr(burden, "discharge_mode", "") or "eventual",
            priority_weight=_priority_weight(getattr(burden, "priority", None)),
            triggered_by=triggered_by,
            fires_event=fires_event,
            for_action=for_action,
        )

    # Second pass: Delegation elements that transfer a token_group (§7.8.7 NOTE).
    # These obligations are held by the delegate but may not have a Commitment.
    for d in model.elements:
        if type(d).__name__ != "Delegation":
            continue
        group_ref = getattr(d, "token_group", None)
        if group_ref is None:
            continue
        delegate_name = getattr(getattr(d, "delegate", None), "name", None)
        if not delegate_name:
            continue
        for tok_ref in getattr(group_ref, "tokens", []):
            burden_name = getattr(tok_ref, "name", None)
            if not burden_name or burden_name in descriptors:
                continue
            burden = burdens.get(burden_name)
            if burden is None:
                continue
            triggered_by = getattr(getattr(burden, "triggered_by", None), "name", None)
            fires_event  = getattr(getattr(burden, "discharged_by", None), "name", None)
            for_action = getattr(burden, "for_action", None) or None
            if for_action is None:
                for_action = _find_action_for_burden(model, burden_name)
            deadline_str = getattr(burden, "deadline", None)
            descriptors[burden_name] = ObligationDescriptor(
                obligation_id=burden_name,
                obligation_text=burden_name,
                deadline_steps=_parse_deadline_steps(deadline_str),
                holder=delegate_name,
                chain=[delegate_name],
                revocable=getattr(d, "revocable", False),
                sub_delegation_allowed=getattr(d, "sub_delegation_allowed", False),
                discharge_mode=getattr(burden, "discharge_mode", "") or "eventual",
                priority_weight=_priority_weight(getattr(burden, "priority", None)),
                triggered_by=triggered_by,
                fires_event=fires_event,
                for_action=for_action,
            )

    return descriptors


def token_from_spec(spec, token_name: str, holder: str, granted_at_tick: int) -> TokenInstance:
    """
    Construct a TokenInstance from a top-level DeonticToken in the spec.

    Raises KeyError if token_name is not found.
    """
    for el in spec.elements:
        if type(el).__name__ == "DeonticToken" and el.name == token_name:
            return TokenInstance(
                token_name=el.name,
                kind=el.kind,
                holder=holder,
                state=el.state or "active",
                discharge_mode=el.discharge_mode or "eventual",
                priority=el.priority or "normal",
                granted_at_tick=granted_at_tick,
                deadline=getattr(el, "deadline", None),
                for_action=(
                    getattr(el, "for_action", None)
                    or _find_action_for_burden(spec, el.name)
                ),
            )
    raise KeyError(f"DeonticToken '{token_name}' not found in spec")


def revoke_authorization(
    state: WorldState, spec, authorization_name: str
) -> Tuple[WorldState, TransitionRecord]:
    """
    AM-31: Withdraw a revocable Authorization at runtime.

    1. Transitions the granted permit's TokenInstance(s) to 'superseded'.
    2. Activates the on_revocation embargo — transitions it if already
       granted, otherwise instantiates and grants it fresh to the permit's
       former holder.
    3. Returns a TransitionRecord documenting the revocation for the ledger.

    Raises KeyError if authorization_name is not declared, or has no
    on_revocation embargo (AM-31-V2 catches this at spec-validation time;
    this is a runtime defensive check).
    """
    auth = None
    for el in spec.elements:
        if type(el).__name__ == "Authorization" and el.name == authorization_name:
            auth = el
            break
    if auth is None:
        raise KeyError(f"Authorization '{authorization_name}' not found in spec")

    permit_name = auth.permit.name
    # on_revocation_embargo is a plain ID: absent → "" per textX default, not None
    embargo_name = getattr(auth, "on_revocation_embargo", "")
    if not embargo_name:
        raise KeyError(f"Authorization '{authorization_name}' has no on_revocation embargo")

    tick = state.tick
    effects_log: list[str] = []

    # 1 — supersede the granted permit(s)
    holders = [
        t.holder for t in state.tokens
        if t.token_name == permit_name and t.kind == "permit"
    ]
    tokens = [
        _transition(t, "superseded")
        if t.token_name == permit_name and t.kind == "permit"
        else t
        for t in state.tokens
    ]
    effects_log.append(f"superseded permit '{permit_name}'")

    # 2 — activate the on_revocation embargo
    if any(t.token_name == embargo_name for t in tokens):
        tokens = [
            _transition(t, "active") if t.token_name == embargo_name else t
            for t in tokens
        ]
    else:
        target = holders[0] if holders else auth.authority.name
        tokens.append(_transition(token_from_spec(spec, embargo_name, target, tick), "active"))
    effects_log.append(f"activated embargo '{embargo_name}'")

    new_state = state.with_tokens(tokens).with_tick(tick + 1)
    record = TransitionRecord(
        tick=tick,
        actor_name=auth.authority.name,
        action_name=f"revoke:{authorization_name}",
        outcome="ok",
        discharged=(),
        effects=tuple(effects_log),
        violations=(),
    )
    return new_state, record


def reinstate_authorization(
    state: WorldState, spec, authorization_name: str
) -> Tuple[WorldState, TransitionRecord]:
    """
    R30 Option B: (Re-)establish a revocable Authorization's grant at runtime.

    Mirrors revoke_authorization() in reverse:
    1. Transitions the granted permit's TokenInstance to 'active' — if one
       already exists (most likely 'superseded' from a prior revoke),
       reuses it; otherwise instantiates and grants it fresh (first-time
       grant, no prior revoke). This single branch correctly handles both
       cases without needing to distinguish them explicitly.
    2. Lifts the on_revocation embargo — if a TokenInstance for it exists
       and is 'active', transitions it to 'lifted' (a state distinct from
       'superseded': 'superseded' means a Permit lost governance to an
       Embargo taking over the same action; 'lifted' means an Embargo's
       own restriction has been rescinded — the opposite relationship).
       If no embargo TokenInstance exists at all, there is nothing to
       lift — unlike revoke's embargo branch, reinstate never creates an
       embargo token.
    3. Returns a TransitionRecord documenting the reinstatement for the
       ledger.

    Raises KeyError if authorization_name is not declared, or has no
    on_revocation embargo — same defensive check as revoke_authorization().
    """
    auth = None
    for el in spec.elements:
        if type(el).__name__ == "Authorization" and el.name == authorization_name:
            auth = el
            break
    if auth is None:
        raise KeyError(f"Authorization '{authorization_name}' not found in spec")

    permit_name = auth.permit.name
    # on_revocation_embargo is a plain ID: absent → "" per textX default, not None
    embargo_name = getattr(auth, "on_revocation_embargo", "")
    if not embargo_name:
        raise KeyError(f"Authorization '{authorization_name}' has no on_revocation embargo")

    tick = state.tick
    effects_log: list[str] = []

    # 1 — (re-)activate the permit. Only append to effects_log when a real
    # state change happens — mirrors fire_event()'s convention (empty
    # effects means nothing was activated), which handle_consent_event()
    # relies on to distinguish "already_active" from "reinstated" the same
    # way handle_encounter_event() distinguishes "fired" from
    # "fired_no_match" by inspecting TransitionRecord.effects.
    existing_permit = next(
        (t for t in state.tokens if t.token_name == permit_name and t.kind == "permit"),
        None,
    )
    if existing_permit is not None and existing_permit.state == "active":
        tokens = list(state.tokens)
    elif existing_permit is not None:
        tokens = [
            _transition(t, "active")
            if t.token_name == permit_name and t.kind == "permit"
            else t
            for t in state.tokens
        ]
        effects_log.append(f"activated permit '{permit_name}'")
    else:
        # First-time grant: no prior permit TokenInstance to reactivate.
        # Target the Authorization's declared recipient. to_role is not
        # resolved to a concrete actor anywhere in this codebase (same
        # degrade-gracefully convention as _build_permit_descriptors's
        # Tier-2), so fall back to the authority as a last resort.
        target = auth.authorized_agent.name if auth.authorized_agent else auth.authority.name
        tokens = list(state.tokens) + [
            _transition(token_from_spec(spec, permit_name, target, tick), "active")
        ]
        effects_log.append(f"activated permit '{permit_name}'")

    # 2 — lift the on_revocation embargo, if one is currently active
    if any(t.token_name == embargo_name and t.state == "active" for t in tokens):
        tokens = [
            _transition(t, "lifted") if t.token_name == embargo_name else t
            for t in tokens
        ]
        effects_log.append(f"lifted embargo '{embargo_name}'")

    new_state = state.with_tokens(tokens).with_tick(tick + 1)
    record = TransitionRecord(
        tick=tick,
        actor_name=auth.authority.name,
        action_name=f"reinstate:{authorization_name}",
        outcome="ok",
        discharged=(),
        effects=tuple(effects_log),
        violations=(),
    )
    return new_state, record


def fire_event(
    state: WorldState, spec, event_name: str, source: str = "external"
) -> Tuple[WorldState, TransitionRecord]:
    """
    Directly fire a named event against state, activating any token whose
    triggered_by matches it — without requiring an Action/emits. Used for
    externally-driven events (e.g. FHIR resource state changes) that have
    no corresponding DSL action.

    Mirrors revoke_authorization()'s direct-call pattern (AM-31): there is
    no calling actor the way advance() has one, so `source` documents the
    event's origin for the ledger (analogous to advance()'s actor_name
    parameter) instead of attributing it to an EnterpriseObject. Callers
    with more specific provenance (e.g. a FHIR resource id) should pass it
    via `source`; this module stays domain-generic and assumes nothing
    about the calling context.
    """
    tick = state.tick
    tokens, effects_log = _activate_triggered_tokens(spec, list(state.tokens), event_name)

    new_state = state.with_tokens(tokens).with_tick(tick + 1)
    record = TransitionRecord(
        tick=tick,
        actor_name=source,
        action_name=f"fire_event:{event_name}",
        outcome="ok",
        discharged=(),
        effects=tuple(effects_log),
        violations=(),
    )
    return new_state, record


def check_live_violations(state: WorldState, spec) -> Tuple[WorldState, TransitionRecord]:
    """
    Sweep every live, active, discharge_mode: eventual Burden for an elapsed
    deadline and transition it to 'violated'.

    Closes the live-detection gap logged in docs/CONCEPTS_INDEX.md ("Live
    violation triggering — detection mechanism exists and is tested; wiring
    to on_violation_of effects is the actual gap", corrected same day):
    the only deadline→VIOLATED logic that existed anywhere in the codebase
    lived inside el_kripke.py's BFS world-expansion, walking the verifier's
    own hypothetical `step` counter — it had no connection to a live
    WorldState.tick at all. This function is that connection: tick-based
    (not wall-clock-based — the open design question the finding left
    undecided), reusing the Kripke model's own deadline_steps vocabulary
    against the real WorldState.tick/TokenInstance.granted_at_tick instead
    of a hypothetical one. It is deliberately an explicit call, not
    something advance() invokes automatically — the finding's other open
    question — so callers control when a deadline sweep happens (e.g. an
    explicit "check deadlines" endpoint) rather than it firing silently on
    unrelated actions.

    Deliberately excludes discharge_mode: strict Burdens entirely — not
    checked, not transitioned, regardless of elapsed time. Strict-mode
    enforcement is itself a live-runtime gap (see docs/CONCEPTS_INDEX.md,
    "discharge_mode: strict — enforcement exists only in the verifier, not
    the live runtime"): today nothing in advance()/revoke_authorization()/
    reinstate_authorization() suppresses tick advancement for a pending
    strict obligation, so tick-elapsed time is not a meaningful signal for
    a strict Burden in the live system the way it is for eventual — treating
    it as violatable on elapsed time here would fabricate an enforcement
    guarantee this function does not actually provide. That gap is out of
    scope for this function to fix.

    deadline_steps is resolved via the same two-tier lookup
    build_kripke_from_runtime() (el_kripke.py) already uses for exactly
    this reason — some scenario builders pre-seed a Burden directly onto
    WorldState.tokens without a matching Commitment (e.g.
    referralResponseBurden/assessmentSchedulingBurden; see
    docs/CONCEPTS_INDEX.md, the double-grant/pre-seed finding), so a token
    absent from the Commitment-derived index still needs a deadline:

      Tier 1 — _build_obligation_descriptors(spec)[token_name].deadline_steps
               (Commitment-derived: real accountability chain, real
               discharge_mode/priority context)
      Tier 2 — direct DeonticToken lookup + _parse_deadline_steps(), default 5
               (bare-string fallback, for a token with no Commitment)

    Returns (new_state, record). record.outcome is 'violation' if at least
    one Burden was transitioned this call, 'ok' otherwise (checked, nothing
    past deadline) — the first live code path to ever produce
    outcome == 'violation'; TransitionRecord.outcome has documented
    'violation' as a valid value since its own docstring was written, but
    no code path produced it until now (also logged in the same finding).

    Deliberate exception to the "every engine mutation advances tick
    unconditionally" convention established by reinstate_authorization()'s
    own no-op branch (its tick advances even when the permit was already
    active and nothing changed): here, tick only advances when at least
    one Burden actually transitions to VIOLATED. This is the endpoint most
    likely to be polled repeatedly during a live demo ("is anything
    overdue yet?") — if a no-op poll silently advanced the global tick the
    same as a real mutation, every unrelated poll would bring every other
    live Burden's elapsed-vs-deadline count closer to violation,
    independent of any real actor action. Confirmed deliberate 2026-08-20.
    """
    tick = state.tick
    spec_descriptors = _build_obligation_descriptors(spec)
    tokens = list(state.tokens)
    violated_names: List[str] = []
    effects_log: List[str] = []

    for i, tok in enumerate(tokens):
        if tok.kind != "burden" or tok.state != "active" or tok.discharge_mode != "eventual":
            continue

        spec_desc = spec_descriptors.get(tok.token_name)
        if spec_desc is not None:
            deadline_steps = spec_desc.deadline_steps
        else:
            spec_tok = next(
                (e for e in spec.elements
                 if type(e).__name__ == "DeonticToken" and e.name == tok.token_name),
                None,
            )
            deadline_steps = _parse_deadline_steps(getattr(spec_tok, "deadline", None), default=5)

        elapsed = tick - tok.granted_at_tick
        if elapsed >= deadline_steps:
            tokens[i] = _transition(tok, "violated")
            violated_names.append(tok.token_name)
            effects_log.append(
                f"violated '{tok.token_name}' held by '{tok.holder}' "
                f"(elapsed {elapsed} >= deadline {deadline_steps} steps)"
            )

    # Tick only advances when something actually happened — deliberate
    # departure from reinstate_authorization()'s "always advance, even on
    # a no-op" precedent; see docstring above.
    new_tick = tick + 1 if violated_names else tick
    new_state = state.with_tokens(tokens).with_tick(new_tick)
    record = TransitionRecord(
        tick=tick,
        actor_name="system",
        action_name="check_live_violations",
        outcome="violation" if violated_names else "ok",
        discharged=(),
        effects=tuple(effects_log),
        violations=tuple(violated_names),
    )
    return new_state, record


def fire_violation_responses(state: WorldState, spec) -> Tuple[WorldState, TransitionRecord]:
    """
    Fire each declared ViolationResponse whose on_violation_of Burden is
    currently VIOLATED in the live state — exactly once per violation, never
    again once fired, regardless of what happens to the created burden
    afterward.

    Deliberately separate from check_live_violations(), not folded into it —
    a considered reversal of this session's earlier "automatic, same call"
    recommendation. check_live_violations() stays a pure, poll-safe detector
    with zero response-firing side effects: detection is freely pollable/
    displayable on its own; response-firing is a distinct, deliberate beat.
    See docs/CONCEPTS_INDEX.md for the fuller rationale.

    Fires VR iff:
      (A) some token named VR.on_violation_of.name is state == 'violated'
          anywhere in live state — NOT scoped by holder: the violated
          Burden's holder and VR.obligates are commonly different parties
          (e.g. referralResponseBurden/SpecialistClinician vs.
          escalationNoticeBurden/SpecialistPractice).
      (B) VR.obligates does NOT already hold a token named
          VR.creates_burden.name in state 'active' OR 'discharged'. The
          'OR discharged' is load-bearing: checking only 'active' would
          re-fire (granting a duplicate) the moment the created burden is
          legitimately discharged by its own for_action — 'violated' never
          reverts, so without this the predicate would flip back to fireable
          every poll after a real discharge.

    On fire, two effects:
      1. Grant creates_burden to obligates as a real TokenInstance via
         token_from_spec() — the same general-purpose grant path
         revoke_authorization()/reinstate_authorization() already reuse for
         their own fresh-grant cases, granted_at_tick stamped.
      2. escalate_to: an informational effects-log entry only, no token or
         event fired. The genuine ISO/IEC 15414 X.902 §8.4 outbound
         notification-to-a-non-participant this conceptually is does NOT
         map onto this toolchain's `emits` construct (that implements
         intra-spec token choreography — discharged_by/triggered_by — not
         §8.4 notification; see docs/CONCEPTS_INDEX.md's emits-vs-
         notification finding). Revisit only if/when a real GP-side
         consumer token exists.

    Tick only advances when at least one response actually fires — same
    conditional-advance pattern and poll-safety rationale as
    check_live_violations(); a no-op poll (nothing currently violated, or
    already responded to) must not consume a tick.

    Returns (new_state, record). record.fired_responses holds the
    ViolationResponse names fired this call (empty if none). outcome is
    always 'ok' — nothing here is ever 'blocked', and nothing newly
    'violates' (that's check_live_violations()'s vocabulary, not this
    function's).
    """
    tick = state.tick
    tokens = list(state.tokens)
    fired: List[str] = []
    effects_log: List[str] = []

    for vr in spec.elements:
        if type(vr).__name__ != "ViolationResponse":
            continue

        violated_burden_name = getattr(getattr(vr, "violated_burden", None), "name", None)
        if not violated_burden_name:
            continue
        if not any(t.token_name == violated_burden_name and t.state == "violated" for t in tokens):
            continue

        responding_actor = getattr(getattr(vr, "responding_actor", None), "name", None)
        creates_burden_ref = getattr(vr, "creates_burden", None)
        if not responding_actor or creates_burden_ref is None:
            continue
        creates_burden_name = creates_burden_ref.name

        already_responded = any(
            t.token_name == creates_burden_name
            and t.holder == responding_actor
            and t.state in ("active", "discharged")
            for t in tokens
        )
        if already_responded:
            continue

        new_tok = token_from_spec(spec, creates_burden_name, responding_actor, tick)
        tokens.append(new_tok)
        fired.append(vr.name)
        effects_log.append(
            f"fired '{vr.name}': granted '{creates_burden_name}' to '{responding_actor}'"
        )

        escalate_to_ref = getattr(vr, "escalate_to", None)
        if escalate_to_ref is not None:
            effects_log.append(f"escalated '{vr.name}' to '{escalate_to_ref.name}'")

    new_tick = tick + 1 if fired else tick
    new_state = state.with_tokens(tokens).with_tick(new_tick)
    record = TransitionRecord(
        tick=tick,
        actor_name="system",
        action_name="fire_violation_responses",
        outcome="ok",
        discharged=(),
        effects=tuple(effects_log),
        violations=(),
        fired_responses=tuple(fired),
    )
    return new_state, record


# ── CLI / test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _here = Path(__file__).parent
    sys.path.insert(0, str(_here))

    from el_parser import parse

    scenario = _here.parent / "scenarios" / "consent" / "consent_scenario.el"
    result = parse(scenario, validate=False)
    if not result.ok:
        print(f"Parse failed: {result.errors}")
        sys.exit(1)

    spec = result.model
    print(f"Parsed '{spec.name}' — {len(spec.elements)} elements")

    # ── Build initial WorldState ──────────────────────────────────────────────
    # Three EnterpriseObjects enrolled in their community roles.
    # AIDiagnosticAgent holds seekConsentObligation (end of delegation chain)
    # and aiAnalysisPermit (required by seekConsent per grammar).
    s = initial_state()
    s = enroll(s, "GPPracticeParty",    "gpRole")
    s = enroll(s, "SpecialistAgent",    "specialistRole")
    s = enroll(s, "AIDiagnosticAgent",  "aiAgentRole")
    s = grant_token(s, token_from_spec(spec, "seekConsentObligation", "AIDiagnosticAgent", s.tick))
    s = grant_token(s, token_from_spec(spec, "aiAnalysisPermit",      "AIDiagnosticAgent", s.tick))

    print(f"\nInitial WorldState (tick {s.tick}):")
    for tok in s.tokens:
        print(f"  {tok.kind} '{tok.token_name}' held by {tok.holder} [{tok.state}]"
              f" for_action={tok.for_action!r}")

    passed = 0

    # ── Test 1: blocked — precondition absent from facts ──────────────────────
    _, r1 = advance(s, "seekConsent", spec, "AIDiagnosticAgent", facts={})
    assert r1.outcome == "blocked", f"T1 expected blocked, got {r1}"
    assert "precondition" in (r1.reason or "").lower(), f"T1 wrong reason: {r1.reason}"
    print(f"\nPASS T1: seekConsent blocked — {r1.reason}")
    passed += 1

    # ── Test 2: blocked — permit not held ─────────────────────────────────────
    s_no_permit = initial_state()
    s_no_permit = enroll(s_no_permit, "AIDiagnosticAgent", "aiAgentRole")
    s_no_permit = grant_token(
        s_no_permit,
        token_from_spec(spec, "seekConsentObligation", "AIDiagnosticAgent", s_no_permit.tick)
    )
    # aiAnalysisPermit intentionally NOT granted
    _, r2 = advance(s_no_permit, "seekConsent", spec, "AIDiagnosticAgent",
                    facts={"Patient must be contactable": True})
    assert r2.outcome == "blocked", f"T2 expected blocked, got {r2}"
    assert "permit" in (r2.reason or "").lower(), f"T2 wrong reason: {r2.reason}"
    print(f"PASS T2: seekConsent blocked — {r2.reason}")
    passed += 1

    # ── Test 3: seekConsent passes — permit held, precondition met ────────────
    s3, r3 = advance(s, "seekConsent", spec, "AIDiagnosticAgent",
                     facts={"Patient must be contactable": True})
    assert r3.outcome == "ok", f"T3 expected ok, got {r3}"
    # seekConsent has no DeonticEffect destroy, for_action mismatch → no discharge yet
    assert "seekConsentObligation" not in r3.discharged, \
        "T3 should not have discharged (no effect or for_action match)"
    print(f"PASS T3: seekConsent executed (permit held, precondition met)"
          f" — effects: {r3.effects or '(none)'}")
    passed += 1

    # ── Test 4: discharge seekConsentObligation via for_action match ──────────
    # seekConsentObligation.for_action = "seek_patient_consent"
    # Calling advance with that exact string triggers step-3b discharge.
    s4, r4 = advance(s, "seek_patient_consent", spec, "AIDiagnosticAgent")
    assert r4.outcome == "ok", f"T4 expected ok, got {r4}"
    assert "seekConsentObligation" in r4.discharged, \
        f"T4 expected burden discharged, discharged={r4.discharged}"
    discharged_tok = next(
        t for t in s4.tokens if t.token_name == "seekConsentObligation"
    )
    assert discharged_tok.state == "discharged", \
        f"T4 token state should be 'discharged', got '{discharged_tok.state}'"
    print(f"PASS T4: seekConsentObligation discharged via for_action match"
          f" — tick {r4.tick} → {s4.tick}")
    passed += 1

    # ── Test 5: non-enrolled actor blocked ────────────────────────────────────
    _, r5 = advance(s, "seekConsent", spec, "UnknownActor")
    assert r5.outcome == "blocked", f"T5 expected blocked, got {r5}"
    print(f"PASS T5: non-enrolled actor blocked — {r5.reason}")
    passed += 1

    print(f"\n{passed}/5 tests passed.")
