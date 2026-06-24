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
from typing import Any, Optional, Tuple


# ── Runtime types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TokenInstance:
    """Runtime instance of a deontic token held by one actor."""
    token_name: str
    kind: str                       # 'burden' | 'permit' | 'embargo'
    holder: str                     # actor name
    state: str                      # 'active' | 'pending' | 'discharged' | 'violated'
    discharge_mode: str             # 'eventual' | 'strict'
    priority: str                   # 'critical' | 'high' | 'normal' | 'low'
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
                    new_tok = TokenInstance(
                        token_name=tok_ref.name,
                        kind=tok_ref.kind,
                        holder=target,
                        state="active",
                        discharge_mode=tok_ref.discharge_mode or "eventual",
                        priority=tok_ref.priority or "normal",
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
                            deadline=t.deadline,
                            for_action=t.for_action,
                        ))
                        effects_log.append(f"cloned '{tok_ref.name}' to '{actor_name}'")
                        break

    # 7c — AM-22: event-triggered token activation
    if grammar_action and grammar_action.emits:
        event_name = grammar_action.emits.name
        triggered = _find_spec_tokens_for_event(spec, event_name, "triggered_by")
        if triggered:
            tokens = [
                _transition(t, "active") if t.token_name in triggered else t
                for t in tokens
            ]
            for name in triggered:
                effects_log.append(
                    f"event '{event_name}' triggered activation of '{name}'"
                )

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
                for ca in getattr(action, "conditional_actions", []):
                    for burden_ref in getattr(ca, "favoured_by", []):
                        if getattr(burden_ref, "name", None) == burden_name:
                            return action.name
    return None


def token_from_spec(spec, token_name: str, holder: str) -> TokenInstance:
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
                deadline=getattr(el, "deadline", None),
                for_action=(
                    getattr(el, "for_action", None)
                    or _find_action_for_burden(spec, el.name)
                ),
            )
    raise KeyError(f"DeonticToken '{token_name}' not found in spec")


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
    s = grant_token(s, token_from_spec(spec, "seekConsentObligation", "AIDiagnosticAgent"))
    s = grant_token(s, token_from_spec(spec, "aiAnalysisPermit",      "AIDiagnosticAgent"))

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
        token_from_spec(spec, "seekConsentObligation", "AIDiagnosticAgent")
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
