"""
Layer 4 — integration test for GET /tokens/{token_name}/governance.

This endpoint resolves the Community/Domain/Federation that governs a
token and surfaces that element's normative_policies (AM-28/AM-41)
citations, via el_kripke.find_normative_policies_for_token's two
resolution paths:

1. Burden path (primary) — role → action → favoured_by traversal.
2. Authorization path (fallback, permit/embargo tokens) — granted/revoked
   token → Authorization.domain_scope → matching model element. See
   docs/Board_NormativePolicy_Display_Investigation_2026-07-22.md
   (computable-governance-ui), "combined next-session scope" addendum,
   item 2, for the design trace.

Most tokens will still NOT resolve to a governing element or a citation
— that is a normal, expected outcome (empty list, 200 OK), not an error.

Follows test_revocation_endpoint.py's convention: fresh-reload the api
module per test, pin the scenario explicitly rather than relying on the
module's default.
"""
import importlib

import pytest
from fastapi import HTTPException


@pytest.fixture
def api():
    """Fresh el_api module (rebuilds the _runtime singleton from initial state)."""
    import el_api
    importlib.reload(el_api)
    return el_api


def test_burden_resolves_to_community_normative_policy(api):
    # clinicalHandoverBurden's favoured_by lives in ReferralEpisodeCommunity's
    # provideHandover action (referral_scenario.el ~line 596), which carries
    # a single citation: normative_policy: ReferralEpisodeAccountability.
    api._runtime = api._SCENARIO_BUILDERS["referral"]()

    resp = api.get_token_governance("clinicalHandoverBurden")

    assert resp.token_name == "clinicalHandoverBurden"
    assert resp.governing_element == "ReferralEpisodeCommunity"
    assert len(resp.normative_policies) == 1
    policy = resp.normative_policies[0]
    assert policy.name == "ReferralEpisodeAccountability"
    assert policy.kind == "guideline"
    assert "National Model for Clinical Governance" in policy.source
    # AM-43: url passed through from NormativePolicy to NormativePolicyInfo
    assert policy.url == "https://www.safetyandquality.gov.au/clinical-topics/clinical-governance/2026-national-model"


def test_resolved_policy_enforcement_surfaces_mode_and_unpoliced(api):
    # ReferralEpisodeAccountability declares `enforcement: unpoliced` (no
    # mode keyword) — mode should surface as None and unpoliced as True.
    # (AuthorshipBasis, the other `enforcement: policed pessimistic` policy
    # in this scenario, sits on PatientDataAuthorshipDomain, which no
    # Authorization's domain_scope names — still unreachable by either
    # resolution path. ConsentRightsBasis, on PatientDataConsentDomain, IS
    # now reachable via the Authorization path — see
    # test_permit_resolves_via_authorization_domain_scope below.)
    api._runtime = api._SCENARIO_BUILDERS["referral"]()

    resp = api.get_token_governance("assessmentSchedulingBurden")

    assert resp.governing_element == "ReferralEpisodeCommunity"
    policy = resp.normative_policies[0]
    assert policy.name == "ReferralEpisodeAccountability"
    assert policy.enforcement is not None
    assert policy.enforcement.mode is None
    assert policy.enforcement.unpoliced is True


def test_permit_resolves_via_authorization_domain_scope(api):
    # patientRecordAccessPermitByAuthorization is never referenced via
    # favoured_by, so the burden path can't reach it — but it IS the
    # grants_permit target of patientDataAuthorization, whose
    # domain_scope: "PatientDataConsentDomain" resolves it via the
    # Authorization fallback path.
    api._runtime = api._SCENARIO_BUILDERS["referral"]()

    resp = api.get_token_governance("patientRecordAccessPermitByAuthorization")

    assert resp.token_name == "patientRecordAccessPermitByAuthorization"
    assert resp.governing_element == "PatientDataConsentDomain"
    assert len(resp.normative_policies) == 1
    policy = resp.normative_policies[0]
    assert policy.name == "ConsentRightsBasis"
    assert policy.kind == "legislation"
    assert policy.url == "https://www.legislation.gov.au/C2004A03712/latest"


# Note: patientRecordAccessEmbargo (patientDataAuthorization's
# on_revocation_embargo target) is NOT tested at this API layer — it
# starts pending and isn't enrolled in _runtime.current_state().tokens
# until a revocation event materializes it, so this endpoint's
# pre-existence check 404s before governance resolution ever runs. Its
# resolution is covered directly against the parsed model instead, in
# tests/test_permit_embargo_governance_resolution.py's
# test_permit_and_embargo_resolve_via_real_authorization.


def test_permit_referenced_only_via_role_action_stays_unresolvable(api):
    # patientRecordAccessPermitByRole is referenced via requires_permit on
    # aiExaminationRole (referral_scenario.el ~line 632) but granted or
    # revoked by no Authorization at all — the Authorization fallback path
    # is scoped to Authorization.grants_permit/on_revocation_embargo
    # specifically, not general permit/embargo resolution, so this must
    # still degrade to a graceful empty response.
    api._runtime = api._SCENARIO_BUILDERS["referral"]()

    resp = api.get_token_governance("patientRecordAccessPermitByRole")

    assert resp.token_name == "patientRecordAccessPermitByRole"
    assert resp.governing_element is None
    assert resp.normative_policies == []


def test_burden_resolves_to_element_with_no_normative_policies(api):
    # referralInitiationBurden's favoured_by lives in GPPracticeCommunity
    # (initiateReferral action), which declares no normative_policy of its
    # own — a real governing element, distinct from "unresolved", that
    # still yields an empty policy list.
    api._runtime = api._SCENARIO_BUILDERS["referral"]()

    resp = api.get_token_governance("referralInitiationBurden")

    assert resp.governing_element == "GPPracticeCommunity"
    assert resp.normative_policies == []


def test_unknown_token_returns_404(api):
    with pytest.raises(HTTPException) as exc:
        api.get_token_governance("nonexistentToken")
    assert exc.value.status_code == 404
