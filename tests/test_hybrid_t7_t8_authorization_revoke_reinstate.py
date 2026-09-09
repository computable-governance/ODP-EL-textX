"""
Layer 4 — hybrid-mode Rules T7 (Authorization Revoke) and T8
(Authorization Reinstate), DN_014/AM-79 (2026-09-09).

docs/design_notes/DN_014_kripke_permit_embargo_per_world_state.md.
Root problem T7/T8 close: `World` tracked obligation/actor/occurred-action
state per-world, but Permit/Embargo state was a single static snapshot
computed once before BFS even started (filtered active-only) and then
treated as a fixed global constant for the entire graph -- so once a
permit was revoked, every world in the model saw it as permanently gone,
with no way back, no matter what the live system actually allowed.

T7/T8 add genuine per-world Permit/Embargo state (`World.permit_states`/
`embargo_states`) and two new hybrid-mode-only edges mirroring
`revoke_authorization()`/`reinstate_authorization()` (el_engine.py):
  T7 — supersede an active permit, activate its on_revocation embargo.
  T8 — (re-)activate a superseded (or never-granted) permit, lift the
       embargo if it was active.
Both gated by the identical strict-burden condition T3 already uses
(`strict_burden_blocks()`) -- AM-78 left revoke/reinstate's own live
guard unconditional, since neither ever discharges anything, so they
stay correctly blocked whenever a strict burden is outstanding and
actionable, exactly like tick.

This file tests the T7/T8 mechanism directly, against the real referral
scenario (scenarios/referral/referral_scenario.el, via
el_api._build_referral_runtime()) -- the same scenario
test_referral_kripke_t6_permit_gate.py uses, which also carries the
DN_014 §1 live-finding regression test (EF true again after revoke, via
reinstate) and the T6-still-gates-directly guard test.
"""
from el_api import _build_referral_runtime
from el_engine import discharge_burden, revoke_authorization
from el_kripke import build_kripke_from_runtime
from el_runtime import Runtime


def test_t7_t8_absent_from_w0_while_strict_burden_outstanding():
    """Guard, DN_014 §6/§7: mirrors revoke_authorization()'s/
    reinstate_authorization()'s own live block (AM-78) -- while
    referralInitiationBurden (discharge_mode: strict) is still PENDING and
    its holder ACTIVE, neither a revoke: nor a reinstate: edge may appear
    from w0 at all, for any Authorization in the spec. Uses the freshly-
    built runtime, before any discharge -- referralInitiationBurden is
    PENDING and GPClinician is ACTIVE by construction."""
    rt = _build_referral_runtime()
    km = build_kripke_from_runtime(rt, horizon=10)
    w0 = km.initial
    assert w0.get_obligation("referralInitiationBurden").name == "PENDING"

    direct_from_w0 = {km.labels[(w0, w)] for w in km.edges.get(w0, set())}
    assert not any(lbl.startswith("revoke:") for lbl in direct_from_w0)
    assert not any(lbl.startswith("reinstate:") for lbl in direct_from_w0)


def test_t7_revoke_edge_present_once_strict_burden_clears():
    """Once referralInitiationBurden is discharged (no strict burden left
    outstanding), T7 must offer a revoke: edge from w0 for
    patientDataAuthorization, whose permit (patientRecordAccessPermitBy
    Authorization) is active in this freshly-built runtime."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, record = discharge_burden(state, spec, "referralInitiationBurden")
    assert record.outcome == "ok"
    rt = Runtime(state, spec)

    km = build_kripke_from_runtime(rt, horizon=10)
    w0 = km.initial
    direct_from_w0 = {km.labels[(w0, w)] for w in km.edges.get(w0, set())}
    assert "revoke:patientDataAuthorization" in direct_from_w0

    w_revoked = next(
        w for w in km.edges[w0]
        if km.labels[(w0, w)] == "revoke:patientDataAuthorization"
    )
    assert w_revoked.get_permit("patientRecordAccessPermitByAuthorization") == "superseded"
    assert w_revoked.get_embargo("patientRecordAccessEmbargo") == "active"


def test_t8_reinstate_edge_present_and_lifts_embargo():
    """Starting from a genuinely-revoked live state (permit superseded,
    embargo active in state.tokens, per revoke_authorization()), T8 must
    offer a reinstate: edge from w0 that puts the permit back to active
    and the embargo to 'lifted' -- distinct from 'active'/'superseded',
    matching reinstate_authorization()'s own state machine exactly
    (el_engine.py: 'lifted' means the embargo's own restriction was
    rescinded, not that a permit superseded it)."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, _ = discharge_burden(state, spec, "referralInitiationBurden")
    state, record = revoke_authorization(state, spec, "patientDataAuthorization")
    assert record.outcome == "ok"
    rt = Runtime(state, spec)

    km = build_kripke_from_runtime(rt, horizon=10)
    w0 = km.initial
    assert w0.get_permit("patientRecordAccessPermitByAuthorization") == "superseded"
    assert w0.get_embargo("patientRecordAccessEmbargo") == "active"

    direct_from_w0 = {km.labels[(w0, w)] for w in km.edges.get(w0, set())}
    assert "reinstate:patientDataAuthorization" in direct_from_w0
    # Already revoked, so no second revoke: edge from the same world.
    assert "revoke:patientDataAuthorization" not in direct_from_w0

    w_reinstated = next(
        w for w in km.edges[w0]
        if km.labels[(w0, w)] == "reinstate:patientDataAuthorization"
    )
    assert w_reinstated.get_permit("patientRecordAccessPermitByAuthorization") == "active"
    assert w_reinstated.get_embargo("patientRecordAccessEmbargo") == "lifted"
