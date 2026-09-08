"""
AM-78 — loosens AM-76's strict-burden guard in advance()/discharge_burden()
back toward el_kripke.py's actual Rule T3 scope: a discharge_mode: strict
Burden should only ever suppress the "let time pass, nothing happens"
tick-edge (T3), never a real T1 discharge edge for an unrelated obligation.
AM-76 over-tightened this by blocking any advance() call that didn't
address THIS specific strict burden — see docs DN_013 for the full design
note this test file encodes.

Uses referralInitiationBurden (discharge_mode: strict, held by GPClinician,
active from _build_referral_runtime()'s initial state, never discharged by
setup in these tests) as the outstanding strict burden throughout.
"""
from el_api import _build_referral_runtime
from el_engine import advance, discharge_burden

STRICT_BURDEN = "referralInitiationBurden"
STRICT_HOLDER = "GPClinician"


def _token(state, name, holder=None):
    for t in state.tokens:
        if t.token_name == name and (holder is None or t.holder == holder):
            return t
    return None


def test_advance_discharges_unrelated_burden_while_other_strict_burden_outstanding():
    """Previously (AM-76) blocked: conductAIExamination discharges
    aiExaminationBurden, unrelated to referralInitiationBurden, which is
    left untouched here (no setup discharge). AM-78 lets this through
    because the call makes real discharge progress."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec

    assert _token(state, STRICT_BURDEN, STRICT_HOLDER).state == "active"

    new_state, record = advance(
        state, "conductAIExamination", spec, "SpecialistAIAgent",
        facts={
            "Referral must be active for AI examination to proceed": True,
            "AI agent must hold patientRecordAccessPermitByAuthorization": True,
        },
    )

    assert record.outcome == "ok"
    assert record.discharged == ("aiExaminationBurden",)
    assert _token(new_state, "aiExaminationBurden").state == "discharged"
    # The unrelated strict burden is still outstanding — untouched by this call.
    assert _token(new_state, STRICT_BURDEN, STRICT_HOLDER).state == "active"


def test_advance_still_blocks_a_zero_progress_action():
    """access_patient_clinical_records discharges no burden at all
    (no favoured_by_burden) — this remains blocked by the strict guard,
    since the call makes zero discharge progress."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec

    blocked_state, record = advance(
        state, "access_patient_clinical_records", spec, "SpecialistAIAgent",
    )

    assert record.outcome == "blocked"
    assert STRICT_BURDEN in record.reason
    assert STRICT_HOLDER in record.reason
    assert blocked_state is state


def test_discharge_burden_succeeds_unconditionally_despite_other_strict_burden():
    """discharge_burden() always makes progress on the named burden by
    construction, so AM-78 removes AM-76's guard here entirely: this must
    succeed even though referralInitiationBurden (a *different* strict
    burden) is left outstanding."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec

    assert _token(state, STRICT_BURDEN, STRICT_HOLDER).state == "active"

    new_state, record = discharge_burden(state, spec, "aiExaminationBurden")

    assert record.outcome == "ok"
    assert record.discharged == ("aiExaminationBurden",)
    assert _token(new_state, "aiExaminationBurden").state == "discharged"
    assert _token(new_state, STRICT_BURDEN, STRICT_HOLDER).state == "active"
