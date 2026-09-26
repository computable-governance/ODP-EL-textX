"""
Layer 4 — AM-86: `_build_obligation_descriptors()` (`toolchain/el_engine.py`)
gains two new accountability roots, ViolationResponse.creates_burden and
Authorization.auth_burden (grammar keyword `creates_burden_on_authority`).
Previously the function only ever iterated `Commitment`, leaving any burden
created exclusively through either of those two constructs structurally
absent from `km.obligation_descriptors` — invisible not just to AF/EF
checks but to `recommend_action()`/Bellman planning too, since both only
ever score obligations already present in that dict.

Real case: `escalationNoticeBurden` in `scenarios/referral/referral_scenario.el`
is created only via `violation_response referralNoResponseViolation`'s
`creates_burden` field — no Commitment anywhere in the file creates it (see
docs/CONCEPTS_INDEX.md's now-resolved "escalationNoticeBurden has no
ObligationDescriptor" finding). AM-56 already closed the equivalent Layer-2
gap in `el_reasoner.ultimate_accountability()`; this closes the matching
Layer-4 gap `el_kripke.py`'s hybrid-mode docstring explicitly flagged as
"unaffected and remains open."

Proactive case: `Authorization.auth_burden` has the identical shape
(optional field creating a burden on a non-Commitment root) but zero live
usage anywhere in the corpus as of this amendment — closed before anything
depends on it, same shape as AM-82/T9. Exercised here via a small inline
probe (`parse_string()`), same throwaway convention as
`tests/test_transfer_effect_from_role_resolution.py` (AM-85).

Regression: every pre-existing Commitment-backed descriptor's fields are
pinned to values captured from an empirical before/after diff against the
pre-AM-86 code at git HEAD (`dde0e6c`), run via `dataclasses.asdict()`
equality over the full descriptor dict for both `referral_scenario.el` and
`consent_scenario.el` — confirming this is a pure additive change to the
existing Commitment path, not a behavior change to it.
"""
import dataclasses

import pytest

from el_api import _SCENARIO_BUILDERS
from el_engine import _build_obligation_descriptors, grant_token, token_from_spec
from el_kripke import (
    NOT_TRIGGERED_WITHIN_HORIZON,
    RESPONSE_OPERATOR,
    ObligationState,
    build_kripke_from_runtime,
    build_kripke_model,
)
from el_parser import parse, parse_string


_REFERRAL_PATH = "scenarios/referral/referral_scenario.el"
_CONSENT_PATH = "scenarios/consent/consent_scenario.el"


def _referral_model():
    result = parse(_REFERRAL_PATH, validate=False)
    assert result.ok, result.errors
    return result.model


# ── escalationNoticeBurden — pre-exec mode (build_kripke_model) ────────────

def test_escalation_notice_burden_gets_descriptor_in_pre_exec_mode():
    """Direct consequence named by the original finding: the descriptor now
    exists in km.obligation_descriptors, sourced from ViolationResponse, not
    a Commitment (none exists for this burden anywhere in the file)."""
    km = build_kripke_model(_referral_model(), horizon=10)
    assert "escalationNoticeBurden" in km.obligation_descriptors

    desc = km.obligation_descriptors["escalationNoticeBurden"]
    # No Delegation originates at SpecialistPractice in this scenario, so
    # walk_chain() degenerates to the single-element case — confirmed by
    # direct inspection of the file's delegation blocks (gpToSpecialistDelegation:
    # GPClinician -> SpecialistClinician; specialistToAIDelegation:
    # SpecialistClinician -> SpecialistAIAgent — neither originates at
    # SpecialistPractice), not assumed.
    assert desc.holder == "SpecialistPractice"
    assert desc.chain == ["SpecialistPractice"]
    assert desc.for_action == "notify_gp_of_non_response"
    assert desc.discharge_mode == "strict"


def test_escalation_notice_burden_reachable_via_af_ef_and_bellman():
    """Before AM-86 this obligation had no entry in obligation_descriptors
    at all, so w0 never carried an obligation_states entry for it: the
    "discharged:escalationNoticeBurden" proposition was never true in any
    world, making both AF and EF trivially/silently False rather than
    erroring — the "invisible to AF/EF checks... can never appear in an
    optimal path recommendation at all" consequence the original finding
    named. Post-fix it is in the model and participates in Bellman planning
    (visible in a successor world's obligation_states).

    AM-105 corrected the verdict this test used to pin. It asserted AF true
    (compelled): the static builder placed the burden in w0 as an ordinary
    PENDING strict obligation, so it was discharged at once although it
    exists only after referralResponseBurden is violated. It now starts
    WAITING and is activated by that violation's T2 edge, so its verdict is
    the bounded response property. referralResponseBurden's deadline is 40
    steps and the horizon 10, so the violation, and with it the escalation,
    is out of reach: "not triggered within horizon", not compelled, and EF
    false. The hybrid model gives the same verdict (AM-105 part 2)."""
    km = build_kripke_model(_referral_model(), horizon=10)

    verdict = km.check_obligation("escalationNoticeBurden")
    assert verdict.modal_operator == RESPONSE_OPERATOR
    assert verdict.satisfied is False
    assert verdict.status == NOT_TRIGGERED_WITHIN_HORIZON
    assert km.check_permission("escalationNoticeBurden").satisfied is False
    assert dict(km.initial.obligation_states)["escalationNoticeBurden"] == ObligationState.WAITING

    recs = km.recommend_action(km.initial)
    assert recs, "expected at least one recommended action from w0"
    obligation_ids = {oid for oid, _ in recs[0].successor_world.obligation_states}
    assert "escalationNoticeBurden" in obligation_ids


# ── escalationNoticeBurden — hybrid mode (build_kripke_from_runtime) ───────

def test_escalation_notice_burden_descriptor_in_hybrid_mode():
    """Confirms the fix reaches build_kripke_from_runtime() too, not just
    build_kripke_model() — both share the same _build_obligation_descriptors()
    import (el_kripke.py:94). escalationNoticeBurden is never granted at
    referral-runtime builder time (same live-granting gap
    tests/test_referral_event_triggers.py documents for this token), so a
    live TokenInstance is granted directly here — same shortcut
    tests/test_gp_escalation_notification_chain.py uses for the identical
    burden shape, bypassing the separate (still-open, unrelated) live
    violation-triggering gap.

    for_action is the concrete field this hybrid-mode fix changes: pre-AM-86,
    with no spec_descriptors entry, build_kripke_from_runtime()'s fallback
    branch (el_kripke.py, spec_desc is None) hardcodes for_action=None
    unconditionally — verified empirically against git HEAD's pre-AM-86
    el_engine.py on this exact live-token setup. Post-AM-86, spec_descriptors
    now has a real entry and for_action resolves correctly."""
    rt = _SCENARIO_BUILDERS["referral"]()
    state = rt.current_state()
    state = grant_token(
        state,
        token_from_spec(rt._spec, "escalationNoticeBurden", "SpecialistPractice", state.tick),
    )
    rt._state = state

    km = build_kripke_from_runtime(rt, horizon=10)
    assert "escalationNoticeBurden" in km.obligation_descriptors

    desc = km.obligation_descriptors["escalationNoticeBurden"]
    assert desc.holder == "SpecialistPractice"
    assert desc.for_action == "notify_gp_of_non_response"
    assert desc.discharge_mode == "strict"
    # AM-108 (pinned as current behaviour): AF is false. Counterexample:
    # the other episode members discharge at step 0, T2b violates
    # aiExaminationBurden ("episode concluded"), and that violated world is
    # terminal with the strict escalation still PENDING — a dead end. The
    # engine allows the sequence; the dead end is the terminal-violated-
    # world rule, and with violated worlds non-terminal AF holds. Expected
    # to flip back to True with AM-109. Before AM-108, aiExaminationBurden
    # was only violated by T2's default 5 steps, which the strict freeze
    # never let elapse.
    verdict = km.check_obligation("escalationNoticeBurden")
    assert verdict.satisfied is False and verdict.status is None
    labels = [label for _, label in verdict.counterexample_path]
    assert "violate:aiExaminationBurden (episode concluded)" in labels
    assert labels[-1].startswith("✗ dead-end")


# ── Authorization.auth_burden — proactive, zero live usage ─────────────────

_AUTH_BURDEN_PROBE = """
enterprise specification AuthBurdenProbe

party Authority
party Agent

permit accessPermit {
    state: active
}

burden facilitationBurden {
    state: active
    discharge_mode: eventual
    description: "AM-86 probe: burden created via Authorization.creates_burden_on_authority"
}

authorization probeAuthorization {
    authority: Authority
    to_agent: Agent
    grants_permit: accessPermit
    creates_burden_on_authority: facilitationBurden
}
"""


def test_authorization_creates_burden_on_authority_gets_descriptor():
    """No live scenario declares this field (grep confirms zero usage in
    scenarios/ as of AM-86); this is the proactive-closure test — same
    shape as AM-82/T9's advance-of-need pattern. actor_name resolves from
    .authority (the grammar's own comment: "the authority grants a permit
    AND undertakes a burden to facilitate"), not .to_agent/.authorized_role
    (the party being authorized, not the one taking on the burden).
    Grammar keyword is 'creates_burden_on_authority'; the parsed attribute
    is auth_burden (grammar/v2/el_grammar.tx:1018, el_domain.py:1183) — the
    same keyword/attribute-name split as ViolationResponse's
    on_violation_of -> violated_burden."""
    result = parse_string(_AUTH_BURDEN_PROBE, validate=True)
    assert result.ok, result.errors

    descriptors = _build_obligation_descriptors(result.model)
    assert "facilitationBurden" in descriptors

    desc = descriptors["facilitationBurden"]
    assert desc.holder == "Authority"
    assert desc.chain == ["Authority"]
    # No .description on the Authorization block itself -> falls back to
    # burden_name, same fallback convention as the ViolationResponse root.
    assert desc.obligation_text == "facilitationBurden"


def test_authorization_without_creates_burden_on_authority_yields_no_descriptor():
    """Sanity/negative case: an Authorization with no auth_burden set must
    not produce a descriptor (mirrors how ViolationResponse.creates_burden
    is already skipped when absent)."""
    probe = _AUTH_BURDEN_PROBE.replace(
        "    creates_burden_on_authority: facilitationBurden\n", ""
    )
    result = parse_string(probe, validate=True)
    assert result.ok, result.errors

    descriptors = _build_obligation_descriptors(result.model)
    assert "facilitationBurden" not in descriptors


# ── Regression: existing Commitment-backed descriptors unchanged ──────────

# Values pinned from an empirical before/after diff: git HEAD's (dde0e6c)
# _build_obligation_descriptors() vs. this amendment's refactored version,
# run over dataclasses.asdict() for every shared key, on both scenario
# files below. All were byte-identical; pinning them here as a persisted
# regression check, not just a one-off diff.
_EXPECTED_REFERRAL_COMMITMENT_DESCRIPTORS = {
    "referralInitiationBurden": {
        "obligation_id": "referralInitiationBurden",
        "obligation_text": "Initiate specialist referral and provide clinical handover for the patient",
        "deadline_steps": 240,
        "holder": "GPPractice",
        "chain": ["GPPractice"],
        "revocable": False,
        "sub_delegation_allowed": False,
        "discharge_mode": "strict",
        "priority_weight": 1.0,
        "triggered_by": "encounterConcluded",
        "fires_event": None,
        "for_action": "initiateReferral",
    },
    "referralResponseBurden": {
        "obligation_id": "referralResponseBurden",
        "obligation_text": "Respond to the specialist referral within the agreed timeframe and schedule assessment",
        "deadline_steps": 40,
        "holder": "GPPractice",
        "chain": ["GPPractice"],
        "revocable": False,
        "sub_delegation_allowed": False,
        "discharge_mode": "eventual",
        "priority_weight": 0.75,
        "triggered_by": None,
        "fires_event": None,
        "for_action": "acknowledgeReferral",
    },
    "clinicalHandoverBurden": {
        "obligation_id": "clinicalHandoverBurden",
        "obligation_text": "Provide complete clinical handover documentation to specialist",
        "deadline_steps": 5,
        "holder": "GPPractice",
        "chain": ["GPPractice"],
        "revocable": False,
        "sub_delegation_allowed": False,
        "discharge_mode": "eventual",
        "priority_weight": 0.5,
        "triggered_by": None,
        "fires_event": None,
        "for_action": "provideHandover",
    },
    "assessmentSchedulingBurden": {
        "obligation_id": "assessmentSchedulingBurden",
        "obligation_text": "Schedule specialist assessment appointment for the patient",
        "deadline_steps": 112,
        "holder": "SpecialistPractice",
        "chain": ["SpecialistPractice"],
        "revocable": False,
        "sub_delegation_allowed": False,
        "discharge_mode": "eventual",
        "priority_weight": 0.5,
        "triggered_by": None,
        "fires_event": None,
        "for_action": "scheduleAssessment",
    },
    "aiExaminationBurden": {
        "obligation_id": "aiExaminationBurden",
        "obligation_text": "Conduct AI diagnostic examination of the referred patient and report findings back to the accountable clinician",
        "deadline_steps": 5,
        "holder": "SpecialistAIAgent",
        "chain": ["SpecialistClinician", "SpecialistAIAgent"],
        "revocable": True,
        "sub_delegation_allowed": False,
        "discharge_mode": "eventual",
        "priority_weight": 0.5,
        "triggered_by": None,
        "fires_event": None,
        "for_action": "conductAIExamination",
    },
    "reviewNonResponseAndDetermineNextStepsBurden": {
        "obligation_id": "reviewNonResponseAndDetermineNextStepsBurden",
        "obligation_text": "Review referral non-response escalations and determine appropriate next steps",
        "deadline_steps": 240,
        "holder": "GPPractice",
        "chain": ["GPPractice"],
        "revocable": False,
        "sub_delegation_allowed": False,
        "discharge_mode": "eventual",
        "priority_weight": 0.75,
        "triggered_by": None,
        "fires_event": None,
        "for_action": "reviewNonResponseAndDetermineNextSteps",
    },
}

_EXPECTED_CONSENT_COMMITMENT_DESCRIPTORS = {
    "reportingObligation": {
        "obligation_id": "reportingObligation",
        "obligation_text": "Submit consent and analysis report after AI diagnostic session",
        "deadline_steps": 5,
        "holder": "GPPracticeParty",
        "chain": ["GPPracticeParty"],
        "revocable": False,
        "sub_delegation_allowed": False,
        "discharge_mode": "eventual",
        "priority_weight": 0.25,
        "triggered_by": None,
        "fires_event": None,
        "for_action": "submit_consent_report",
    },
    "seekConsentObligation": {
        "obligation_id": "seekConsentObligation",
        "obligation_text": "Seek informed patient consent before AI diagnostic analysis",
        "deadline_steps": 5,
        "holder": "AIDiagnosticAgent",
        "chain": ["GPPracticeParty", "SpecialistAgent", "AIDiagnosticAgent"],
        "revocable": True,
        "sub_delegation_allowed": False,
        "discharge_mode": "strict",
        "priority_weight": 1.0,
        "triggered_by": None,
        "fires_event": None,
        "for_action": "seek_patient_consent",
    },
}


@pytest.mark.parametrize(
    "path, expected",
    [
        (_REFERRAL_PATH, _EXPECTED_REFERRAL_COMMITMENT_DESCRIPTORS),
        (_CONSENT_PATH, _EXPECTED_CONSENT_COMMITMENT_DESCRIPTORS),
    ],
)
def test_existing_commitment_backed_descriptors_unchanged(path, expected):
    result = parse(path, validate=False)
    assert result.ok, result.errors
    descriptors = _build_obligation_descriptors(result.model)

    for burden_name, expected_fields in expected.items():
        assert burden_name in descriptors, f"{burden_name} missing from {path}"
        assert dataclasses.asdict(descriptors[burden_name]) == expected_fields
