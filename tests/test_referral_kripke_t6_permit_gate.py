"""
Layer 4 — regression test for T6 (Examine): the Kripke-model counterpart
to the Layer 3 conductAIExamination fix (docs/CONCEPTS_INDEX.md,
"conductAIExamination has no enforced link to data-access
authorization"), generalized to all Burdens gated by a requires_permit
link (docs/CONCEPTS_INDEX.md, "T1 is blind to requires_permit — affects
three Burdens, not one").

Before T6: T1 discharged any Burden unconditionally, with zero
awareness of whether its discharge Action carried a requires_permit
clause -- EF(discharged:<gated burden>) was True regardless of the
required Permit's actual state. T6 (plus T1's new exclusion check)
makes EF correctly track the live state of the Permit(s) a gated
Burden's Action requires -- mirroring, at the Kripke/pre-execution
layer, what advance()'s existing Step 6 already enforces at the
engine/runtime layer (see tests/test_referral_ai_examination_permit_gate.py
for the equivalent Layer 3 coverage).

Tests against referral_scenario.el via build_kripke_from_runtime()
(hybrid mode -- the only mode T6 is verified correct in today; spec-only
mode has a separately logged gap for role-granted permits, see
docs/CONCEPTS_INDEX.md, "Permit granted via role-level `holds` is
invisible to spec-only `permit_descriptors`"). Two gated Burdens
covered, deliberately exercising both permit-granting mechanisms:
  - aiExaminationBurden / patientRecordAccessPermitByAuthorization
    (granted via Authorization -- resolvable in both modes)
  - referralResponseBurden / patientRecordAccessPermitByRole
    (granted via role `holds` + on_join transfer -- the mechanism
    invisible to spec-only mode's permit_descriptors, per the finding
    above; only reachable here because hybrid mode reads live-granted
    WorldState tokens directly)
Plus one ungated Burden (referralInitiationBurden) as a regression
guard confirming T1's new exclusion check doesn't overreach onto
Burdens with no requires_permit link.
"""
from el_api import _build_referral_runtime
from el_engine import revoke_authorization
from el_kripke import build_kripke_from_runtime
from el_runtime import Runtime


def test_ai_examination_burden_ef_true_when_permit_active():
    rt = _build_referral_runtime()
    km = build_kripke_from_runtime(rt, horizon=10)
    assert km.check_permission("aiExaminationBurden").satisfied is True


def test_ai_examination_burden_ef_false_when_permit_revoked():
    """Before T6, this would incorrectly stay True -- T1 discharged the
    burden unconditionally regardless of live permit state. With T6 (and
    T1's exclusion), revoking the permit removes the only path that
    could ever discharge aiExaminationBurden in this closed model."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    revoked_state, _ = revoke_authorization(state, spec, "patientDataAuthorization")
    revoked_rt = Runtime(revoked_state, spec)

    km = build_kripke_from_runtime(revoked_rt, horizon=10)
    assert km.check_permission("aiExaminationBurden").satisfied is False


def test_referral_response_burden_ef_true_when_permit_active():
    """Exercises the role-granted permit path (patientRecordAccessPermitByRole)
    -- distinct from aiExaminationBurden's Authorization-granted permit
    above, and the specific mechanism the spec-only-mode gap (logged
    separately) cannot resolve. Hybrid mode resolves it correctly."""
    rt = _build_referral_runtime()
    km = build_kripke_from_runtime(rt, horizon=10)
    assert km.check_permission("referralResponseBurden").satisfied is True


def test_referral_initiation_burden_unaffected_by_gating():
    """Regression guard: referralInitiationBurden has no requires_permit
    link, so T1's new exclusion check must not touch it -- AF must still
    hold (discharge_mode: strict), exactly as before T6 existed."""
    rt = _build_referral_runtime()
    km = build_kripke_from_runtime(rt, horizon=10)
    assert km.check_obligation("referralInitiationBurden").satisfied is True
