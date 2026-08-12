"""
Layer 4 — hybrid-mode Rule T5 (Exercise) and its Embargo guard.

Design finalized in chat 2026-08-12/13 (Stage 2 of hybrid-mode T5,
building on Stage 1's structure/state unification, commit 6ae1581).
Landed in four reviewed diffs against el_kripke.py:
  Diff 1 — split _build_embargo_holder_index() into pure
           _extract_embargo_holder() + a thin spec-static-state wrapper.
  Diff 2 — hybrid-mode Permit/Embargo descriptor sourcing in
           build_kripke_from_runtime() (live tok.holder/tok.state, with
           spec-structural for_action fallback to tok.for_action).
  Diff 3 — the T5 edge-generation rule and Embargo guard themselves,
           ported into build_kripke_from_runtime()'s BFS loop.
  Diff 4 — this file.

The first three cases mirror tests/test_t5_exercise_embargo_guard.py's
three-case structure exactly (same minimal spec strings), but exercised
through the hybrid pipeline (Runtime -> build_kripke_from_runtime())
instead of build_kripke_model() directly — proving the hybrid port
produces the same verdicts as pre-exec, not just that it doesn't crash.

The first three cases rely on Runtime.build_from_spec()'s own `holds`
auto-grant. That auto-grant previously read a stale attribute name
(getattr(el, "tokens", ...) instead of "holds_tokens") and silently
granted nothing — discovered while first writing these tests, logged in
CONCEPTS_INDEX.md, and fixed in el_runtime.py as its own follow-on change
once confirmed safe (no scenario builder reaches that code path; see the
finding for the verification). These tests no longer need the manual
grant_token()/token_from_spec() workaround that el_kripke.py's own
_run_hybrid_smoke_test() still uses for its own, separate purposes.

The fourth test exercises revoke_authorization() end-to-end against the
real referral scenario and checks the Kripke-level effect directly on
edge labels, closing the exact gap identified in the 2026-08-11
CONCEPTS_INDEX.md finding (AM-34's 6 tests assert against runtime/ledger
state only; none ever built a Kripke model or checked an AF/EF verdict
after revocation). It does NOT assert on the action-level EF query,
because the referral scenario's real content has two independent Permits
(patientRecordAccessPermitByRole, patientRecordAccessPermitByAuthorization)
governing the same for_action — revoking the Authorization behind one of
them correctly leaves the action reachable via the other, so EF stays
True by design. Instead it asserts on the specific
"exercise:patientRecordAccessPermitByAuthorization -> ..." edge label,
which does disappear. See the 2026-08-13 CONCEPTS_INDEX.md finding
("T5's edge labels silently collide when two Permits share a
for_action") for why a bare label-presence check on a shared for_action
would itself be fragile in general — not an issue here since only one
of the two permits is ever superseded by this specific revocation.
"""
from el_api import _SCENARIO_BUILDERS
from el_engine import revoke_authorization
from el_kripke import build_kripke_from_runtime
from el_parser import parse_string
from el_runtime import Runtime


_T5_FIRE = """
enterprise specification T5FireProbe

party Operator {
    holds accessPermit
}

permit accessPermit {
    for_action: "performAccess"
    state: active
}
"""


def test_hybrid_t5_fires_and_action_reaches_occurred_via_ef():
    """Core edge-generation path through the hybrid pipeline: one ACTIVE
    Permit, holder resolvable via live tok.holder, explicit for_action, no
    competing Embargo at all. EF(occurred:performAccess) must hold from
    w0 — same assertion as pre-exec's test_t5_fires_and_action_reaches_
    occurred_via_ef, proving the hybrid port reproduces it."""
    result = parse_string(_T5_FIRE, validate=True)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)

    km = build_kripke_from_runtime(rt, horizon=5)
    assert km.EF(km.initial, "occurred:performAccess") is True


_T5_EMBARGO_SAME_HOLDER = """
enterprise specification T5EmbargoSameHolderProbe

party Operator {
    holds accessPermit
    holds blockingEmbargo
}

permit accessPermit {
    for_action: "performAccess"
    state: active
}

embargo blockingEmbargo {
    state: active
}

community ProbeCommunity {
    objective: "probe embargo guard suppression"
    role operatorRole {
        action performAccess {
            inhibited_by_embargo blockingEmbargo
        }
    }
}
"""


def test_hybrid_t5_suppressed_by_active_embargo_held_by_same_actor():
    """Same Permit as the fire test, plus an Embargo: state active, held by
    the SAME actor as the Permit, linked to the Action via the real
    Action-scoped inhibited_by_embargo requirement. The exercise edge must
    be suppressed entirely — performAccess never appears in
    occurred_actions in any reachable world. Mirrors pre-exec's
    test_t5_suppressed_by_active_embargo_held_by_same_actor."""
    result = parse_string(_T5_EMBARGO_SAME_HOLDER, validate=True)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)

    km = build_kripke_from_runtime(rt, horizon=5)
    assert km.EF(km.initial, "occurred:performAccess") is False


_T5_EMBARGO_DIFFERENT_HOLDER = """
enterprise specification T5EmbargoDifferentHolderProbe

party Operator {
    holds accessPermit
}

party OtherActor {
    holds blockingEmbargo
}

permit accessPermit {
    for_action: "performAccess"
    state: active
}

embargo blockingEmbargo {
    state: active
}

community ProbeCommunity {
    objective: "probe embargo guard actor-scoping"
    role operatorRole {
        action performAccess {
            inhibited_by_embargo blockingEmbargo
        }
    }
}
"""


def test_hybrid_t5_not_suppressed_when_embargo_held_by_different_actor():
    """Same Embargo/linkage as the suppression test, but blockingEmbargo is
    held by OtherActor, not by Operator (the Permit's holder). The guard
    must NOT suppress the edge — confirms it is genuinely actor-scoped in
    the hybrid path too, not accidentally blocking on Embargo existence
    anywhere in the model. Mirrors pre-exec's test_t5_not_suppressed_
    when_embargo_held_by_different_actor."""
    result = parse_string(_T5_EMBARGO_DIFFERENT_HOLDER, validate=True)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)

    km = build_kripke_from_runtime(rt, horizon=5)
    assert km.EF(km.initial, "occurred:performAccess") is True


def test_hybrid_t5_revoke_authorization_removes_its_exercise_edge():
    """End-to-end against the real referral scenario: revoke
    patientDataAuthorization via revoke_authorization() (R31), then rebuild
    the hybrid Kripke model and confirm the Kripke-level effect directly —
    closing the gap noted in the 2026-08-11 CONCEPTS_INDEX.md finding that
    AM-34's tests never check a Kripke verdict after revocation.

    Asserts on the specific exercise: label rather than action-level EF,
    because the referral scenario has a second, independent Permit
    (patientRecordAccessPermitByRole, held by SpecialistClinician) governing
    the same for_action — revoking the AI agent's authorization-based
    access correctly leaves the action reachable via the clinician's
    role-based access, so EF(occurred:access_patient_clinical_records)
    stays True by design, not by bug. See the 2026-08-13 CONCEPTS_INDEX.md
    finding for the general label-collision property this sidesteps.
    """
    rt = _SCENARIO_BUILDERS["referral"]()

    km_before = build_kripke_from_runtime(rt, horizon=10)
    before_labels = set(km_before.labels.values())
    assert "exercise:patientRecordAccessPermitByAuthorization → access_patient_clinical_records" in before_labels

    new_state, record = revoke_authorization(rt.current_state(), rt._spec, "patientDataAuthorization")
    rt._state = new_state
    rt._ledger.append(record)

    km_after = build_kripke_from_runtime(rt, horizon=10)
    after_labels = set(km_after.labels.values())
    assert "exercise:patientRecordAccessPermitByAuthorization → access_patient_clinical_records" not in after_labels

    # The independently-granted role-based permit is unaffected by this
    # specific revocation and correctly remains reachable.
    assert "exercise:patientRecordAccessPermitByRole → access_patient_clinical_records" in after_labels
