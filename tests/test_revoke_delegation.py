"""
Layer 3 — el_engine.revoke_delegation() (AM-81).

Revokes a revocable, `transfers_burden` Delegation at runtime, reassigning
the burden's holder from the delegate back to the delegator. Mirrors
revoke_authorization()'s shape (state, spec, name) -> (new_state,
TransitionRecord), KeyError on an undeclared/non-revocable/token_group
target, _unaddressed_strict_burdens() guard, no-op convention for a burden
with no live 'pending' instance.

Scoped narrowly (AM-81): single `transfers_burden` Delegations only —
`transfers_token_group` is explicitly out of scope and raises. One-way
only: no reinstate-delegation counterpart exists.

Uses two fixtures:
  - referral_scenario.el (via el_api._build_referral_runtime()) for the
    real-world happy-path/blocked-case tests, using specialistToAIDelegation
    (the scenario's only `transfers_burden` Delegation) as the task specified.
  - a minimal inline probe spec (parse_string(), same throwaway pattern as
    tests/test_discharge_burden.py) for the non-revocable case, which has
    no counterpart anywhere in referral_scenario.el.
"""
import pytest

from el_api import _build_referral_runtime
from el_engine import discharge_burden, revoke_delegation
from el_parser import parse_string
from el_runtime import Runtime


def _token(state, name, holder=None):
    for t in state.tokens:
        if t.token_name == name and (holder is None or t.holder == holder):
            return t
    raise AssertionError(f"no TokenInstance named '{name}'" + (f" held by '{holder}'" if holder else ""))


# ── referral_scenario.el — real-world cases ────────────────────────────────

def test_revoke_delegation_reassigns_holder():
    """Happy path: aiExaminationBurden moves from SpecialistAIAgent back to
    SpecialistClinician (specialistToAIDelegation's delegator), active
    state preserved, a real effect logged."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, _ = discharge_burden(state, spec, "referralInitiationBurden")

    before = _token(state, "aiExaminationBurden")
    assert before.holder == "SpecialistAIAgent"
    assert before.state == "active"

    new_state, record = revoke_delegation(state, spec, "specialistToAIDelegation")
    assert record.outcome == "ok"
    assert record.effects == (
        "reassigned 'aiExaminationBurden' from 'SpecialistAIAgent' to 'SpecialistClinician'",
    )

    after = _token(new_state, "aiExaminationBurden")
    assert after.holder == "SpecialistClinician"
    assert after.state == "active"  # unchanged — only holder moves


def test_revoke_delegation_raises_on_unknown_delegation():
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    with pytest.raises(KeyError):
        revoke_delegation(state, spec, "noSuchDelegation")


def test_revoke_delegation_raises_on_token_group_delegation():
    """gpToSpecialistDelegation is revocable but transfers_token_group
    (specialistBurdenGroup), not a direct burden — out of scope for AM-81."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    with pytest.raises(KeyError):
        revoke_delegation(state, spec, "gpToSpecialistDelegation")


def test_revoke_delegation_blocked_while_strict_burden_outstanding():
    """referralInitiationBurden (discharge_mode: strict) is PENDING and
    GPClinician is ACTIVE by construction in a freshly-built runtime —
    revoke_delegation() must be blocked exactly like revoke_authorization()
    is, before any discharge clears it."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec

    blocked_state, record = revoke_delegation(state, spec, "specialistToAIDelegation")
    assert record.outcome == "blocked"
    assert "referralInitiationBurden" in record.reason
    assert blocked_state is state

    # Nothing moved — the target burden's holder is untouched.
    assert _token(state, "aiExaminationBurden").holder == "SpecialistAIAgent"


def test_revoke_delegation_is_a_no_op_once_the_burden_is_already_discharged():
    """Once aiExaminationBurden is discharged directly (no live 'pending'
    instance held by SpecialistAIAgent remains), revoke_delegation() is a
    no-op — outcome 'ok', empty effects, state unchanged — mirroring
    reinstate_authorization()'s 'already_active' convention."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, _ = discharge_burden(state, spec, "referralInitiationBurden")
    state, discharge_record = discharge_burden(state, spec, "aiExaminationBurden")
    assert discharge_record.outcome == "ok"
    assert _token(state, "aiExaminationBurden").state == "discharged"

    new_state, record = revoke_delegation(state, spec, "specialistToAIDelegation")
    assert record.outcome == "ok"
    assert record.effects == ()
    assert new_state is state


# ── Minimal probe spec — non-revocable case (no counterpart in the real scenario) ──

_PROBE = """
enterprise specification RevokeDelegationProbe

party Delegator {}

party Delegate {
    holds probeBurden
}

burden probeBurden {
    state: active
    discharge_mode: eventual
}

commitment probeCommitment {
    by: Delegator
    obligation: "test obligation, not revocable"
    creates_burden: probeBurden
}

delegation nonRevocableDelegation {
    from: Delegator
    to: Delegate
    obligation: "test obligation, not revocable"
    transfers_burden: probeBurden
}
"""


def _build_probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


def test_revoke_delegation_raises_on_non_revocable_delegation():
    rt = _build_probe_runtime()
    state, spec = rt.current_state(), rt._spec
    with pytest.raises(KeyError):
        revoke_delegation(state, spec, "nonRevocableDelegation")
