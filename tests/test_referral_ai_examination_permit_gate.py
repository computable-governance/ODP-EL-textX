"""
Layer 3 — regression test for the conductAIExamination precondition-
enforcement gap (docs/CONCEPTS_INDEX.md, "conductAIExamination has no
enforced link to data-access authorization", fixed 2026-08-18).

Before the fix, conductAIExamination's only gate was a free-text
`precondition` string checked against a caller-supplied facts dict —
never derived from patientRecordAccessPermitByAuthorization's actual
live state, so revoking the permit did not block the action. The fix
added `requires_permit patientRecordAccessPermitByAuthorization for
aiExaminationRole` to the action's declaration in
scenarios/referral/referral_scenario.el, activating advance()'s
existing Step 6 check (_actor_holds_permit).

Encodes the three-case manual verification run in chat 2026-08-18
against real, throwaway _build_referral_runtime() instances (each test
below builds its own fresh runtime — no shared/mutated state between
tests):
  1. permit ACTIVE -> advance() succeeds, aiExaminationBurden discharges.
  2. permit revoked (revoke_authorization) -> advance() blocked, citing
     the missing permit; aiExaminationBurden remains undischarged.
  3. permit reinstated (reinstate_authorization) -> advance() succeeds
     again.

The free-text precondition field is left in the scenario as
documentation only (unchanged by the fix) -- FACTS below satisfies it
on every call so Step 6, not Step 4, is what's actually being
exercised.
"""
from el_api import _build_referral_runtime
from el_engine import advance, reinstate_authorization, revoke_authorization

ACTOR = "SpecialistAIAgent"
ACTION = "conductAIExamination"
PERMIT = "patientRecordAccessPermitByAuthorization"
AUTHORIZATION = "patientDataAuthorization"
BURDEN = "aiExaminationBurden"

# Satisfies conductAIExamination's free-text precondition field (Step 4)
# on every call, so a blocked outcome can only be attributed to Step 6.
FACTS = {"AI agent must hold patientRecordAccessPermitByAuthorization": True}


def _token(state, name, holder=ACTOR):
    for t in state.tokens:
        if t.token_name == name and t.holder == holder:
            return t
    return None


def test_conductAIExamination_succeeds_when_permit_active():
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec

    assert _token(state, PERMIT).state == "active"

    new_state, record = advance(state, ACTION, spec, ACTOR, facts=FACTS)

    assert record.outcome == "ok"
    assert record.discharged == (BURDEN,)
    assert _token(new_state, BURDEN).state == "discharged"


def test_conductAIExamination_blocked_after_permit_revoked():
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec

    revoked_state, rev_record = revoke_authorization(state, spec, AUTHORIZATION)
    assert rev_record.outcome == "ok"
    assert _token(revoked_state, PERMIT).state == "superseded"

    blocked_state, record = advance(revoked_state, ACTION, spec, ACTOR, facts=FACTS)

    assert record.outcome == "blocked"
    assert record.reason == f"required permit '{PERMIT}' not held by actor"
    assert record.discharged == ()
    assert _token(blocked_state, BURDEN).state == "active"  # not discharged
    assert blocked_state is revoked_state  # blocked advance() leaves state unchanged


def test_conductAIExamination_succeeds_again_after_reinstatement():
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec

    revoked_state, _ = revoke_authorization(state, spec, AUTHORIZATION)
    blocked_state, blocked_record = advance(revoked_state, ACTION, spec, ACTOR, facts=FACTS)
    assert blocked_record.outcome == "blocked"

    reinstated_state, reinst_record = reinstate_authorization(blocked_state, spec, AUTHORIZATION)
    assert reinst_record.outcome == "ok"
    assert _token(reinstated_state, PERMIT).state == "active"

    final_state, record = advance(reinstated_state, ACTION, spec, ACTOR, facts=FACTS)

    assert record.outcome == "ok"
    assert record.discharged == (BURDEN,)
    assert _token(final_state, BURDEN).state == "discharged"
