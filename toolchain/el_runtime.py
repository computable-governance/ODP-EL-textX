"""
el_runtime.py
=============
Stateful facade over el_engine.py with an append-only ledger (Layer 3).

Standard reference: ISO/IEC 15414:2015 §6.6, §7.8, §7.10
"""

from __future__ import annotations

from typing import List, Optional

from el_engine import (
    WorldState,
    TokenInstance,
    TransitionRecord,
    advance as _engine_advance,
    enroll,
    grant_token,
    initial_state,
    token_from_spec,
)

# ── Federation helpers ────────────────────────────────────────────────────────

def _collect_domain_actors(domain) -> list:
    """Return [(actor_name, domain_name)] for all objects in a Domain.

    Reads controlling_objects and controlled_objects populated by P8.
    """
    result = []
    for obj in getattr(domain, "controlling_objects", []):
        result.append((obj.name, domain.name))
    for obj in getattr(domain, "controlled_objects", []):
        result.append((obj.name, domain.name))
    return result


def _build_delegation_chain(spec, token_name: str) -> list:
    """Trace the Commitment → Delegation* accountability chain for token_name.

    Returns a list of (step_kind, actor_name) tuples in chain order:
      ('commitment', actor_name)
      ('delegation', delegator_name → delegate_name)
    """
    chain = []

    # Find the Commitment that creates the token
    root_actor = None
    for el in spec.elements:
        if type(el).__name__ == "Commitment":
            burden = getattr(el, "burden", None)
            if burden and getattr(burden, "name", None) == token_name:
                root_actor = getattr(el, "actor", None)
                actor_name = root_actor.name if root_actor else "?"
                chain.append(("commitment", actor_name))
                break

    # Walk the Delegation chain (order: each step's from = previous delegate)
    visited = set()
    changed = True
    while changed:
        changed = False
        for el in spec.elements:
            if type(el).__name__ == "Delegation" and el.name not in visited:
                burden = getattr(el, "burden", None)
                if burden and getattr(burden, "name", None) == token_name:
                    delegator = getattr(el, "delegator", None)
                    delegate  = getattr(el, "delegate", None)
                    d_from = delegator.name if delegator else "?"
                    d_to   = delegate.name  if delegate  else "?"
                    chain.append(("delegation", f"{d_from} → {d_to}"))
                    visited.add(el.name)
                    changed = True
    return chain


class Runtime:
    """Stateful governance runtime: WorldState + EnterpriseSpec + append-only ledger."""

    def __init__(self, state: WorldState, spec) -> None:
        self._state = state
        self._spec = spec
        self._ledger: List[TransitionRecord] = []

    @classmethod
    def build_from_spec(cls, spec) -> "Runtime":
        """
        Factory: enroll all EnterpriseObject actors from spec; grant their
        declared tokens instantiated as TokenInstance objects.
        """
        state = initial_state()

        for el in spec.elements:
            if type(el).__name__ != "EnterpriseObject":
                continue

            role = getattr(el, "role", None)
            role_name = role.name if (role and hasattr(role, "name")) else None
            state = enroll(state, el.name, role_name)

            for tok_ref in getattr(el, "tokens", []) or []:
                tok_name = tok_ref.name if hasattr(tok_ref, "name") else str(tok_ref)
                try:
                    state = grant_token(state, token_from_spec(spec, tok_name, el.name))
                except KeyError:
                    pass

        # Known gap: tokens assigned via top-level CommitmentDecl and
        # DelegationDecl are not enrolled here.  Callers must grant those
        # tokens manually with grant_token() / el_engine.token_from_spec()
        # after calling build_from_spec().  Resolving the CommitmentDecl /
        # DelegationDecl chains automatically is a future refinement.
        return cls(state, spec)

    @classmethod
    def build_from_federation(cls, spec) -> "Runtime":
        """
        Factory (AM-25): enroll all actors from every Domain member of every
        Federation in spec, tagged with their domain name. Then traverse
        CommitmentDecl → DelegationDecl chains to auto-grant the burden token
        to the terminal delegate in each chain.

        This resolves the Step 6 known gap noted in build_from_spec(): tokens
        assigned via CommitmentDecl/DelegationDecl were not enrolled automatically.

        Steps:
          1. Find all Federation elements in spec.
          2. For each Federation member that is a Domain, collect its
             controlling and controlled EnterpriseObjects.
          3. Enroll each object with community_tag = domain.name.
          4. For each Commitment, find the terminal delegate in its
             Delegation chain and grant the committed burden token to them.
        """
        state = initial_state()

        # Step 1–3: enroll actors from domain members
        for el in spec.elements:
            if type(el).__name__ != "Federation":
                continue
            for member_ref in getattr(el, "members", []):
                # AM-26: members is List[MemberRef]; dereference to the community
                member = getattr(member_ref, "community", member_ref)
                if type(member).__name__ != "Domain":
                    continue
                for actor_name, domain_name in _collect_domain_actors(member):
                    # Avoid duplicate enrolment if actor appears in multiple domains
                    already = any(a.actor_name == actor_name for a in state.actors)
                    if not already:
                        state = enroll(state, actor_name, community_tag=domain_name)

        # Step 4: auto-grant terminal burden via Commitment → Delegation chain
        for el in spec.elements:
            if type(el).__name__ != "Commitment":
                continue
            burden_ref = getattr(el, "burden", None)
            if not burden_ref:
                continue
            token_name = getattr(burden_ref, "name", None)
            if not token_name:
                continue

            # Find the terminal delegate for this token using set arithmetic:
            # terminal = {delegates} − {delegators}  (a delegate who never delegates further)
            delegators: set = set()
            delegate_objs: dict = {}   # name → EnterpriseObject
            for d in spec.elements:
                if type(d).__name__ != "Delegation":
                    continue
                d_burden = getattr(d, "burden", None)
                if not d_burden or getattr(d_burden, "name", None) != token_name:
                    continue
                from_obj = getattr(d, "delegator", None)
                to_obj   = getattr(d, "delegate",  None)
                if from_obj:
                    delegators.add(from_obj.name)
                if to_obj:
                    delegate_objs[to_obj.name] = to_obj

            terminals = set(delegate_objs) - delegators
            terminal = delegate_objs.get(next(iter(terminals))) if terminals else None
            found_any_delegation = bool(delegate_objs)

            # If no delegation exists, grant directly to the committing actor
            if not found_any_delegation:
                actor_ref = getattr(el, "actor", None)
                if actor_ref:
                    terminal = actor_ref

            if terminal is None:
                continue

            # Grant the token to the terminal actor if they are enrolled
            enrolled_names = {a.actor_name for a in state.actors}
            if terminal.name in enrolled_names:
                try:
                    state = grant_token(state, token_from_spec(spec, token_name, terminal.name))
                except KeyError:
                    pass

        return cls(state, spec)

    def advance(self, action_name: str, actor_name: str,
                facts: Optional[dict] = None) -> TransitionRecord:
        """Execute one governed action step and append the record to the ledger."""
        new_state, record = _engine_advance(
            self._state, action_name, self._spec, actor_name, facts
        )
        self._state = new_state
        self._ledger.append(record)
        return record

    def accountability_chain(self, token_name: str) -> List[TransitionRecord]:
        """Return all ledger entries that mention the named token, in order."""
        return [
            r for r in self._ledger
            if token_name in r.discharged
            or any(token_name in e for e in r.effects)
            or any(token_name in v for v in r.violations)
        ]

    def current_state(self) -> WorldState:
        """Return the current immutable WorldState."""
        return self._state


# ── Federation demo (AM-25) ───────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _here = Path(__file__).parent
    sys.path.insert(0, str(_here))

    from el_parser import parse

    scenario = _here.parent / "scenarios" / "consent" / "federation_consent_scenario.el"
    result = parse(scenario, validate=False)
    if not result.ok:
        print(f"Parse failed:")
        for e in result.errors:
            print(f"  {e}")
        sys.exit(1)

    spec = result.model
    print(f"Parsed '{spec.name}' — {len(spec.elements)} elements")

    # ── build_from_federation ─────────────────────────────────────────────────
    runtime = Runtime.build_from_federation(spec)
    state = runtime.current_state()

    print(f"\nEnrolled actors ({len(state.actors)}):")
    for a in state.actors:
        tag = f"  [{a.community_tag}]" if a.community_tag else ""
        print(f"  {a.actor_name}{tag}")

    print(f"\nGranted tokens ({len(state.tokens)}):")
    for t in state.tokens:
        print(f"  {t.kind} '{t.token_name}' → {t.holder}"
              f"  [{t.state}] discharge_mode={t.discharge_mode} priority={t.priority}")

    # ── Static accountability chain from spec ─────────────────────────────────
    print(f"\nStatic accountability chain for 'seekConsentObligation':")
    for step_kind, detail in _build_delegation_chain(spec, "seekConsentObligation"):
        if step_kind == "commitment":
            print(f"  commitment  by {detail}")
        else:
            print(f"  delegation  {detail}")

    # ── Runtime discharge ─────────────────────────────────────────────────────
    print(f"\nDischarging seekConsentObligation via seek_patient_consent ...")
    r = runtime.advance("seek_patient_consent", "AISpecialistAgent")
    print(f"  outcome   : {r.outcome}")
    print(f"  discharged: {r.discharged}")
    print(f"  effects   : {r.effects or '(none)'}")
    if r.reason:
        print(f"  reason    : {r.reason}")

    print(f"\nRuntime ledger accountability chain for 'seekConsentObligation':")
    chain = runtime.accountability_chain("seekConsentObligation")
    for entry in chain:
        print(f"  tick={entry.tick}  actor={entry.actor_name}"
              f"  action={entry.action_name}  outcome={entry.outcome}"
              f"  discharged={entry.discharged}")
    if not chain:
        print("  (none — token not yet referenced in ledger)")
