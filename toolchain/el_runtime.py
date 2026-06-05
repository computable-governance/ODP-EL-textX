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


# ── Smoke test ────────────────────────────────────────────────────────────────

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
    runtime = Runtime.build_from_spec(spec)

    state = runtime.current_state()
    print(f"Built runtime from '{spec.name}'")
    print(f"  Actors: {[a.actor_name for a in state.actors]}")
    print(f"  Tokens: {[t.token_name for t in state.tokens]}")

    # Fallback A: build_from_spec found no actors at all (type name mismatch).
    if not state.actors:
        print("\n[fallback A] build_from_spec found no EnterpriseObjects;"
              " enrolling manually from consent scenario")
        for actor, role in [
            ("GPPracticeParty",   "gpRole"),
            ("SpecialistAgent",   "specialistRole"),
            ("AIDiagnosticAgent", "aiAgentRole"),
        ]:
            runtime._state = enroll(runtime._state, actor, role)

    # Fallback B: actors enrolled but no tokens — tokens are declared at top
    # level and assigned via CommitmentDecl/DelegationDecl rather than inline
    # on the ObjectDecl.  Grant the well-known consent tokens manually.
    if not runtime.current_state().tokens:
        print("\n[fallback B] No inline token declarations on EnterpriseObjects;"
              " granting consent tokens manually (CommitmentDecl chain)")
        runtime._state = grant_token(
            runtime._state,
            token_from_spec(spec, "seekConsentObligation", "AIDiagnosticAgent"),
        )
        runtime._state = grant_token(
            runtime._state,
            token_from_spec(spec, "aiAnalysisPermit", "AIDiagnosticAgent"),
        )

    # Advance seek_patient_consent — discharges seekConsentObligation via for_action
    r = runtime.advance("seek_patient_consent", "AIDiagnosticAgent")
    print(f"\nadvance('seek_patient_consent', 'AIDiagnosticAgent')")
    print(f"  outcome   : {r.outcome}")
    print(f"  discharged: {r.discharged}")
    print(f"  effects   : {r.effects or '(none)'}")
    if r.reason:
        print(f"  reason    : {r.reason}")

    print("\nLedger entries:")
    for i, entry in enumerate(runtime._ledger):
        print(f"  [{i}] tick={entry.tick}  actor={entry.actor_name}"
              f"  action={entry.action_name}  outcome={entry.outcome}"
              f"  discharged={entry.discharged}")

    print("\nAccountability chain for 'seekConsentObligation':")
    chain = runtime.accountability_chain("seekConsentObligation")
    for entry in chain:
        print(f"  tick={entry.tick}  actor={entry.actor_name}"
              f"  action={entry.action_name}  outcome={entry.outcome}"
              f"  discharged={entry.discharged}")
    if not chain:
        print("  (none — token not referenced in any ledger entry)")
