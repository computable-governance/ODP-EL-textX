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

DN_014/AM-79 (2026-09-09): the revoked-permit case below used to assert
EF is False -- itself a bug (docs/design_notes/DN_014_kripke_permit_
embargo_per_world_state.md), because Permit/Embargo state lived outside
World entirely, so revocation looked like a permanent dead end no matter
what the live system actually allowed. Rules T7 (Authorization Revoke)
and T8 (Authorization Reinstate) make Permit/Embargo state a genuine
per-world fact, closing that gap: EF is correctly True again (reachable
via reinstate, then examine), and a separate guard test confirms T6
itself still refuses to discharge directly while the permit stays
revoked.
"""
from el_api import _build_referral_runtime
from el_engine import discharge_burden, revoke_authorization
from el_kripke import build_kripke_from_runtime, extract_witness_path
from el_runtime import Runtime


def test_ai_examination_burden_ef_true_when_permit_active():
    rt = _build_referral_runtime()
    km = build_kripke_from_runtime(rt, horizon=10)
    assert km.check_permission("aiExaminationBurden").satisfied is True


def test_ai_examination_burden_ef_true_after_revoke_via_reinstate():
    """Before T6, this would incorrectly stay True regardless of live
    permit state -- T1 discharged the burden unconditionally. T6 (and
    T1's exclusion) made EF correctly track the permit's state.

    DN_014/AM-79 (2026-09-09): this test used to assert EF is False once
    the permit is revoked -- that was itself a bug this project carried
    for several weeks, confirmed live-tested (docs/design_notes/DN_014_
    kripke_permit_embargo_per_world_state.md §1): the live system genuinely
    allows re-authorizing access and then examining -- a real, governance-
    meaningful 2-hop path (reinstate, then examine) -- but the Kripke model
    reported it UNREACHABLE, because Permit/Embargo state lived outside
    World entirely (a single static snapshot computed once before BFS,
    never varying per-world). Rules T7 (Authorization Revoke) and T8
    (Authorization Reinstate) close this: the model now knows revocation
    is not the end of the story. EF is correctly True again, via the
    reinstate -> examine path -- not because the revoke never took effect
    (T6's gate genuinely blocks direct discharge while the permit stays
    revoked, see the guard test below), but because reinstating and then
    examining is a real option in the live system, and now in the model
    too."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, _ = discharge_burden(state, spec, "referralInitiationBurden")
    revoked_state, _ = revoke_authorization(state, spec, "patientDataAuthorization")
    revoked_rt = Runtime(revoked_state, spec)

    km = build_kripke_from_runtime(revoked_rt, horizon=10)
    assert km.check_permission("aiExaminationBurden").satisfied is True

    # The witness path is the exact 2-hop shape DN_014 §1 names as the
    # live finding: reinstate the authorization, then examine.
    path = extract_witness_path(km, target_proposition="discharged:aiExaminationBurden")
    edge_labels = [step["edge_from_previous"] for step in path if step["edge_from_previous"]]
    assert edge_labels == [
        "reinstate:patientDataAuthorization",
        "examine:aiExaminationBurden → conductAIExamination",
    ]


def test_ai_examination_burden_t6_gate_still_blocks_direct_discharge_while_revoked():
    """Guard, distinct from the EF test above: T6 must still refuse to
    discharge aiExaminationBurden DIRECTLY from a world where the permit
    is genuinely revoked -- T7/T8 adding a path THROUGH reinstate must not
    be confused with T6's own gate going slack. Checked at the edge level
    (w0's direct successors), not via EF, precisely because EF alone
    cannot distinguish "blocked here, reachable via reinstate" from
    "T6 stopped gating" -- both look identical from an EF-only vantage."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, _ = discharge_burden(state, spec, "referralInitiationBurden")
    revoked_state, _ = revoke_authorization(state, spec, "patientDataAuthorization")
    revoked_rt = Runtime(revoked_state, spec)

    km = build_kripke_from_runtime(revoked_rt, horizon=10)
    w0 = km.initial
    direct_from_w0 = {km.labels[(w0, w)] for w in km.edges.get(w0, set())}
    assert "examine:aiExaminationBurden → conductAIExamination" not in direct_from_w0
    assert "reinstate:patientDataAuthorization" in direct_from_w0


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
