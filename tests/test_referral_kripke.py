"""
Layer 4 — Kripke AF/EF verification and structural checks for
referral_scenario.el (candidate reference scenario). Required for
promotion to Reference status per scenarios/README.md's promotion
criteria ("correctly applies every settled decision current in the
concept index") — closes the gap where AF/EF values, the (now split,
2026-07-22) PatientDataDomain's structure, and the two-hop delegation
chain were manually verified in a sandbox during design (2026-07-07) but
never asserted as a persisted test.
"""
from pathlib import Path

import pytest

from el_api import _SCENARIO_BUILDERS
from el_kripke import build_kripke_from_runtime
from el_parser import parse

_SCENARIO = Path(__file__).resolve().parent.parent / "scenarios" / "referral" / "referral_scenario.el"


@pytest.fixture
def runtime():
    return _SCENARIO_BUILDERS["referral"]()


def test_referral_initiation_is_compelled(runtime):
    """discharge_mode: strict -> AF holds."""
    km = build_kripke_from_runtime(runtime, horizon=10)
    verdict = km.check_obligation("referralInitiationBurden")
    assert verdict.satisfied is True


def test_referral_response_is_detectable_not_compelled(runtime):
    """discharge_mode: eventual -> AF fails, EF holds."""
    km = build_kripke_from_runtime(runtime, horizon=10)
    assert km.check_obligation("referralResponseBurden").satisfied is False
    assert km.check_permission("referralResponseBurden").satisfied is True


def test_ai_examination_is_detectable_not_compelled(runtime):
    """discharge_mode: eventual -> AF fails, EF holds. Same compelled vs
    detectable pattern as referralResponseBurden, now applied to the AI
    agent's own diagnostic work, not just the specialist's response."""
    km = build_kripke_from_runtime(runtime, horizon=10)
    assert km.check_obligation("aiExaminationBurden").satisfied is False
    assert km.check_permission("aiExaminationBurden").satisfied is True


def test_clinical_handover_is_detectable_not_compelled(runtime):
    """discharge_mode: eventual -> AF fails, EF holds."""
    km = build_kripke_from_runtime(runtime, horizon=10)
    assert km.check_obligation("clinicalHandoverBurden").satisfied is False
    assert km.check_permission("clinicalHandoverBurden").satisfied is True


def test_assessment_scheduling_is_detectable_not_compelled(runtime):
    """discharge_mode: eventual -> AF fails, EF holds. Completes AF/EF
    verification for all five members of referralBurdenGroup — the other
    three (referralInitiationBurden, referralResponseBurden,
    aiExaminationBurden) were verified in the tests above."""
    km = build_kripke_from_runtime(runtime, horizon=10)
    assert km.check_obligation("assessmentSchedulingBurden").satisfied is False
    assert km.check_permission("assessmentSchedulingBurden").satisfied is True


def test_patient_data_authorship_domain_structure():
    """PatientDataAuthorshipDomain (split from the original PatientDataDomain
    2026-07-22, design settled 2026-07-19, docs/CONCEPTS_INDEX.md 'Domain'
    entry): controller-processor relationship — GPPractice and
    SpecialistPractice as controlling authorities, each across their own
    clinicians plus the shared AI diagnostic agent."""
    result = parse(_SCENARIO, validate=True)
    assert result.ok
    domain = next(el for el in result.model.elements if el.name == "PatientDataAuthorshipDomain")
    assert {o.name for o in domain.controlling_objects} == {"GPPractice", "SpecialistPractice"}
    assert {o.name for o in domain.controlled_objects} == {
        "GPClinician", "SpecialistClinician", "SpecialistAIAgent",
    }
    assert [p.name for p in domain.normative_policies] == ["AuthorshipBasis"]


def test_patient_data_consent_domain_structure():
    """PatientDataConsentDomain (split from the original PatientDataDomain
    2026-07-22): consent-governed use — Patient as the controlling
    authority over the same three controlled objects, genuinely
    overlapping with PatientDataAuthorshipDomain rather than partitioning
    them."""
    result = parse(_SCENARIO, validate=True)
    assert result.ok
    domain = next(el for el in result.model.elements if el.name == "PatientDataConsentDomain")
    assert [o.name for o in domain.controlling_objects] == ["Patient"]
    assert {o.name for o in domain.controlled_objects} == {
        "GPClinician", "SpecialistClinician", "SpecialistAIAgent",
    }
    assert [p.name for p in domain.normative_policies] == ["ConsentRightsBasis"]


def test_referral_episode_community_normative_policy():
    """ReferralEpisodeCommunity cites ReferralEpisodeAccountability — the
    episodic-Community-level NormativePolicy example (AM-41's capability
    confirmed via a throwaway fixture in test_am41_community_normative_policy.py;
    this is the real scenario demonstration). Deliberately kind: guideline /
    enforcement: unpoliced, contrasting with the standing
    PatientDataAuthorshipDomain/PatientDataConsentDomain and federation-level
    citations, which cite binding legislation under
    enforcement: policed pessimistic (AM-42). mode must stay None — mode and
    unpoliced are mutually exclusive by grammar construction (AM-42)."""
    result = parse(_SCENARIO, validate=True)
    assert result.ok
    community = next(el for el in result.model.elements if el.name == "ReferralEpisodeCommunity")
    assert [p.name for p in community.normative_policies] == ["ReferralEpisodeAccountability"]
    policy = community.normative_policies[0]
    assert policy.kind == "guideline"
    assert policy.enforcement.unpoliced is True
    assert policy.enforcement.mode is None


def test_two_hop_delegation_chain():
    """Option B (2026-07-07): clinician-to-clinician, not
    practice-to-practice, with sub-delegation enabling the AI hop."""
    result = parse(_SCENARIO, validate=True)
    assert result.ok

    def find(name):
        return next(el for el in result.model.elements if el.name == name)

    hop1 = find("gpToSpecialistDelegation")
    hop2 = find("specialistToAIDelegation")
    assert hop1.delegator.name == "GPClinician"
    assert hop1.delegate.name == "SpecialistClinician"
    assert hop1.sub_delegation_allowed is True
    assert hop2.delegator.name == "SpecialistClinician"
    assert hop2.delegate.name == "SpecialistAIAgent"
