"""
Layer 4 — hybrid-mode Rule T4/T10 (Delegation Revoke/Reinstate), AM-81
(2026-09-14) and AM-84 (2026-09-14).

docs/CONCEPTS_INDEX.md's 2026-09-12 T4 investigation finding identified
the documented T4 ("flip the delegate's ActorStatus to INACTIVE globally")
as the wrong shape: it would incorrectly affect every other obligation the
delegate separately holds. AM-81 implements T4 scoped per delegation
instance instead (`World.delegation_states`, mirroring how T7/T8 scope
Permit/Embargo per instance), and threads a resolved `_effective_holder()`
through T1's discharge check/label and `strict_burden_blocks()` so a
revoked delegation's burden is judged/attributed against its delegator,
not its (now-former) delegate. AM-84 closes the one-way gap AM-81
deliberately left open: T10 flips a `"revoked"` delegation back to
`"active"` in the same `delegation_states` map, restoring
`_effective_holder()`'s fall-through to the original delegate — same
scope, same guard, same instantaneous shape as T4.

Scoped narrowly, matching T7/T8's own scope exactly: single
`transfers_burden` Delegations only, `.revocable` enforced as a real
precondition, hybrid mode only (`build_kripke_from_runtime()` —
`build_kripke_model()` is untouched).

Two fixtures:
  - referral_scenario.el (via el_api._build_referral_runtime()) for the
    real-world edge-reachability tests, using specialistToAIDelegation
    (the scenario's only `transfers_burden` Delegation) as specified.
    Its burden, aiExaminationBurden, happens to be gated behind
    patientRecordAccessPermitByAuthorization (T6/Examine territory, not
    T1/Discharge) — so post-revocation its `examine:` edge disappears
    entirely (SpecialistClinician, the new effective holder, doesn't hold
    the AI-specific permit), rather than being relabeled. That is itself
    a real, correct AM-81 consequence and is tested directly below.
  - a minimal inline probe spec (parse_string(), same throwaway pattern as
    tests/test_discharge_burden.py) with an *ungated* delegated burden, to
    exercise T1's effective-holder discharge-label rewiring directly —
    the one behavior no burden in referral_scenario.el's own
    transfers_burden Delegation can demonstrate, since its only such
    Delegation's burden is permit-gated.
"""
from el_api import _build_referral_runtime
from el_engine import discharge_burden
from el_kripke import build_kripke_from_runtime
from el_parser import parse_string
from el_runtime import Runtime


# ── referral_scenario.el — real-world edge reachability ─────────────────────

def test_t4_absent_from_w0_while_strict_burden_outstanding():
    """Mirrors test_t7_t8_absent_from_w0_while_strict_burden_outstanding
    exactly: referralInitiationBurden (discharge_mode: strict) is PENDING
    and GPClinician ACTIVE by construction in a freshly-built runtime, so
    no revoke_delegation: edge may appear from w0 for any Delegation."""
    rt = _build_referral_runtime()
    km = build_kripke_from_runtime(rt, horizon=10)
    w0 = km.initial
    assert w0.get_obligation("referralInitiationBurden").name == "PENDING"

    direct_from_w0 = {km.labels[(w0, w)] for w in km.edges.get(w0, set())}
    assert not any(lbl.startswith("revoke_delegation:") for lbl in direct_from_w0)


def test_t4_revoke_delegation_edge_present_once_strict_burden_clears():
    """Once referralInitiationBurden is discharged (no strict burden left
    outstanding), T4 must offer a revoke_delegation: edge from w0 for
    specialistToAIDelegation, and the reached world must show the
    delegation flagged 'revoked'."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, record = discharge_burden(state, spec, "referralInitiationBurden")
    assert record.outcome == "ok"
    rt = Runtime(state, spec)

    km = build_kripke_from_runtime(rt, horizon=10)
    w0 = km.initial
    direct_from_w0 = {km.labels[(w0, w)] for w in km.edges.get(w0, set())}
    assert "revoke_delegation:specialistToAIDelegation" in direct_from_w0

    w_revoked = next(
        w for w in km.edges[w0]
        if km.labels[(w0, w)] == "revoke_delegation:specialistToAIDelegation"
    )
    assert w_revoked.get_delegation("specialistToAIDelegation") == "revoked"
    # No re-revoke edge from an already-revoked world (T4's own branch is
    # guarded by the == "active" check) — T10's reinstate edge from here
    # is tested separately below.
    out_from_revoked = {km.labels[(w_revoked, w)] for w in km.edges.get(w_revoked, set())}
    assert not any("specialistToAIDelegation" in lbl and lbl.startswith("revoke_delegation")
                   for lbl in out_from_revoked)


def test_t4_examine_edge_for_gated_burden_disappears_after_revocation():
    """AM-81 consequence, verified directly: aiExaminationBurden's
    for_action (conductAIExamination) requires patientRecordAccessPermit
    ByAuthorization, which SpecialistAIAgent holds. Post-revocation, the
    effective holder is SpecialistClinician, who does NOT hold that
    permit — so T6's permit-ownership check (now keyed on the effective
    holder, same as T1's) fails and the examine: edge is no longer
    offered at all. Present pre-revocation, absent in the revoked world —
    a real reachability change, not a relabeling."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, _ = discharge_burden(state, spec, "referralInitiationBurden")
    rt = Runtime(state, spec)

    km = build_kripke_from_runtime(rt, horizon=10)
    w0 = km.initial
    pre_edges = {km.labels[(w0, w)] for w in km.edges.get(w0, set())}
    assert "examine:aiExaminationBurden → conductAIExamination" in pre_edges

    w_revoked = next(
        w for w in km.edges[w0]
        if km.labels[(w0, w)] == "revoke_delegation:specialistToAIDelegation"
    )
    post_edges = {km.labels[(w_revoked, w)] for w in km.edges.get(w_revoked, set())}
    assert "examine:aiExaminationBurden → conductAIExamination" not in post_edges


def test_t10_reinstate_delegation_edge_present_and_flips_state_back_to_active():
    """AM-84: from a world where specialistToAIDelegation is 'revoked',
    a reinstate_delegation: edge must be reachable, and the world it
    leads to must show the delegation flagged 'active' again."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, _ = discharge_burden(state, spec, "referralInitiationBurden")
    rt = Runtime(state, spec)

    km = build_kripke_from_runtime(rt, horizon=10)
    w0 = km.initial
    w_revoked = next(
        w for w in km.edges[w0]
        if km.labels[(w0, w)] == "revoke_delegation:specialistToAIDelegation"
    )

    out_from_revoked = {km.labels[(w_revoked, w)] for w in km.edges.get(w_revoked, set())}
    assert "reinstate_delegation:specialistToAIDelegation" in out_from_revoked

    w_reinstated = next(
        w for w in km.edges[w_revoked]
        if km.labels[(w_revoked, w)] == "reinstate_delegation:specialistToAIDelegation"
    )
    assert w_reinstated.get_delegation("specialistToAIDelegation") == "active"


def test_t10_examine_edge_reappears_after_reinstatement():
    """Mirror image of test_t4_examine_edge_for_gated_burden_disappears_
    after_revocation: once specialistToAIDelegation is reinstated, the
    effective holder reverts to SpecialistAIAgent, who does hold
    patientRecordAccessPermitByAuthorization — so the examine: edge that
    disappeared under T4 must reappear under T10. This is the case where
    the AI genuinely does get its access back and the obligation stops
    being stranded."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    state, _ = discharge_burden(state, spec, "referralInitiationBurden")
    rt = Runtime(state, spec)

    km = build_kripke_from_runtime(rt, horizon=10)
    w0 = km.initial
    w_revoked = next(
        w for w in km.edges[w0]
        if km.labels[(w0, w)] == "revoke_delegation:specialistToAIDelegation"
    )
    revoked_edges = {km.labels[(w_revoked, w)] for w in km.edges.get(w_revoked, set())}
    assert "examine:aiExaminationBurden → conductAIExamination" not in revoked_edges

    w_reinstated = next(
        w for w in km.edges[w_revoked]
        if km.labels[(w_revoked, w)] == "reinstate_delegation:specialistToAIDelegation"
    )
    reinstated_edges = {km.labels[(w_reinstated, w)] for w in km.edges.get(w_reinstated, set())}
    assert "examine:aiExaminationBurden → conductAIExamination" in reinstated_edges


# ── Minimal probe spec — T1 effective-holder discharge-label rewiring ───────
# referral_scenario.el's only transfers_burden Delegation happens to be
# permit-gated (T6 territory), so it cannot demonstrate T1's own
# discharge:<oid> by <holder> label directly. This probe isolates that
# behavior with an ungated delegated burden.

_PROBE = """
enterprise specification T4KripkeProbe

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
    obligation: "probe obligation"
    creates_burden: probeBurden
}

delegation probeDelegation {
    from: Delegator
    to: Delegate
    obligation: "probe obligation"
    transfers_burden: probeBurden
    revocable: true
}
"""


def _build_probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


def test_t4_rewires_t1_discharge_label_to_delegator():
    rt = _build_probe_runtime()
    km = build_kripke_from_runtime(rt, horizon=5)
    w0 = km.initial

    w0_edges = {km.labels[(w0, w)] for w in km.edges.get(w0, set())}
    assert "discharge:probeBurden by Delegate" in w0_edges
    assert "revoke_delegation:probeDelegation" in w0_edges

    w_revoked = next(
        w for w in km.edges[w0]
        if km.labels[(w0, w)] == "revoke_delegation:probeDelegation"
    )
    assert w_revoked.get_delegation("probeDelegation") == "revoked"

    revoked_edges = {km.labels[(w_revoked, w)] for w in km.edges.get(w_revoked, set())}
    assert "discharge:probeBurden by Delegator" in revoked_edges
    assert "discharge:probeBurden by Delegate" not in revoked_edges
