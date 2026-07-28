"""
Layer 2 — direct unit tests for el_kripke.find_governing_element_via_authorization
and its integration into find_normative_policies_for_token.

Board_NormativePolicy_Display_Investigation_2026-07-22.md's "combined
next-session scope" addendum, item 2: permit/embargo tokens are never
referenced via favoured_by, so the burden path
(_find_element_and_action_for_burden) can never resolve them. This adds a
second, narrower fallback path: a token that is the grants_permit or
on_revocation_embargo target of some Authorization resolves via that
Authorization's domain_scope (a plain, unvalidated STRING naming a model
element — see the still-open, tentative AM-14 amendment proposing to make
domain_scope a typed [DomainDecl] cross-reference instead).

This is deliberately narrower than "permit/embargo resolution" in general:
a permit/embargo referenced only via a role action's requires_permit or
inhibited_by_embargo, never via any Authorization, is still unresolvable —
tested here directly (not just via the real referral scenario) with a
throwaway fixture whose domain_scope points at nothing real, confirming
graceful (None, []) degradation rather than an error.
"""
from el_kripke import find_governing_element_via_authorization, find_normative_policies_for_token
from el_parser import parse, parse_string
from pathlib import Path


_HEADER = 'enterprise specification Probe\n\n'

_SCENARIO = Path(__file__).resolve().parent.parent / "scenarios" / "referral" / "referral_scenario.el"


def _find(model, cls_name, name=None):
    matches = [e for e in model.elements if type(e).__name__ == cls_name]
    if name is None:
        return matches
    return next(e for e in matches if e.name == name)


def test_domain_scope_matching_nothing_real_degrades_gracefully():
    """An Authorization's domain_scope naming no real model element must
    not raise — both the Authorization path directly and the combined
    find_normative_policies_for_token must return (None, [])."""
    src = _HEADER + (
        'party Authority\n'
        'agent Agent1\n\n'
        'permit TestPermit {\n'
        '    state: active\n'
        '}\n\n'
        'authorization TestAuth {\n'
        '    authority: Authority\n'
        '    to_agent: Agent1\n'
        '    grants_permit: TestPermit\n'
        '    domain_scope: "NoSuchElementAnywhereInThisModel"\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    element, policies = find_governing_element_via_authorization(result.model, "TestPermit")
    assert element is None
    assert policies == []

    element, policies = find_normative_policies_for_token(result.model, "TestPermit")
    assert element is None
    assert policies == []


def test_authorization_with_no_domain_scope_degrades_gracefully():
    """domain_scope itself is optional on Authorization — a matching
    Authorization with no domain_scope at all must also degrade to
    (None, []), not error on a missing attribute."""
    src = _HEADER + (
        'party Authority\n'
        'agent Agent1\n\n'
        'permit TestPermit {\n'
        '    state: active\n'
        '}\n\n'
        'authorization TestAuth {\n'
        '    authority: Authority\n'
        '    to_agent: Agent1\n'
        '    grants_permit: TestPermit\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    element, policies = find_governing_element_via_authorization(result.model, "TestPermit")
    assert element is None
    assert policies == []


def test_permit_and_embargo_resolve_via_real_authorization():
    """Direct (non-API) confirmation against the real referral scenario:
    both the granted permit and the revoked embargo of
    patientDataAuthorization resolve to PatientDataConsentDomain and its
    ConsentRightsBasis citation."""
    result = parse(_SCENARIO, validate=True)
    assert result.ok, result.errors

    for token_name in ("patientRecordAccessPermitByAuthorization", "patientRecordAccessEmbargo"):
        element, policies = find_normative_policies_for_token(result.model, token_name)
        assert element is not None
        assert element.name == "PatientDataConsentDomain"
        assert len(policies) == 1
        assert policies[0].name == "ConsentRightsBasis"
        assert policies[0].url == "https://www.legislation.gov.au/C2004A03712/latest"


def test_permit_referenced_only_via_role_action_is_still_unresolvable():
    """patientRecordAccessPermitByRole is referenced via requires_permit
    on aiExaminationRole but granted/revoked by no Authorization — the
    Authorization path's scope doesn't extend to it, so it must still
    fall through to (None, []), same as before this change."""
    result = parse(_SCENARIO, validate=True)
    assert result.ok, result.errors

    element, policies = find_normative_policies_for_token(result.model, "patientRecordAccessPermitByRole")
    assert element is None
    assert policies == []


def test_burden_path_still_tried_first_and_unaffected():
    """Regression guard at the el_kripke layer directly (not just via the
    API layer's existing test): the burden path's pre-existing behaviour
    must be completely unchanged by the new fallback."""
    result = parse(_SCENARIO, validate=True)
    assert result.ok, result.errors

    element, policies = find_normative_policies_for_token(result.model, "clinicalHandoverBurden")
    assert element.name == "ReferralEpisodeCommunity"
    assert len(policies) == 1
    assert policies[0].name == "ReferralEpisodeAccountability"
