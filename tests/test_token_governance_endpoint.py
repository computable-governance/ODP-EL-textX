"""
Layer 4 — integration test for GET /tokens/{token_name}/governance.

This endpoint resolves the Community/Domain/Federation that governs a
token (via el_kripke.find_normative_policies_for_token's favoured_by
traversal) and surfaces that element's normative_policies (AM-28/AM-41)
citations. Most tokens will NOT resolve to a governing element or a
citation — that is a normal, expected outcome (empty list, 200 OK), not
an error. See docs/Board_NormativePolicy_Display_Investigation_2026-07-22.md
(computable-governance-ui) for the design trace; and el_kripke.py's
find_normative_policies_for_token docstring for the KNOWN LIMITATION that
permit/embargo tokens never resolve via this traversal (governed by
Domain controlling_object/controlled_object membership instead, not
implemented here).

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


def test_resolved_policy_enforcement_surfaces_mode_and_unpoliced(api):
    # ReferralEpisodeAccountability declares `enforcement: unpoliced` (no
    # mode keyword) — mode should surface as None and unpoliced as True.
    # (The only other enforcement-bearing policies in this scenario,
    # AuthorshipBasis/ConsentRightsBasis with `enforcement: policed
    # pessimistic`, sit on PatientDataAuthorshipDomain/PatientDataConsentDomain,
    # which are governed by actor membership, not favoured_by — unreachable
    # by this endpoint per the KNOWN LIMITATION.)
    api._runtime = api._SCENARIO_BUILDERS["referral"]()

    resp = api.get_token_governance("assessmentSchedulingBurden")

    assert resp.governing_element == "ReferralEpisodeCommunity"
    policy = resp.normative_policies[0]
    assert policy.name == "ReferralEpisodeAccountability"
    assert policy.enforcement is not None
    assert policy.enforcement.mode is None
    assert policy.enforcement.unpoliced is True


def test_permit_token_has_no_resolvable_governance(api):
    # Permit/embargo tokens are never referenced via favoured_by, so this
    # traversal can't reach them — must be a graceful empty response, not
    # an error.
    api._runtime = api._SCENARIO_BUILDERS["referral"]()

    resp = api.get_token_governance("patientRecordAccessPermitByAuthorization")

    assert resp.token_name == "patientRecordAccessPermitByAuthorization"
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
