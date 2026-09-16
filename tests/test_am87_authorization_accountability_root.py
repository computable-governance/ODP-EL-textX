"""
AM-87: Authorization.auth_burden as a fifth accountability root in
el_reasoner.ultimate_accountability().

AM-86 added Authorization.auth_burden as a third root in
toolchain/el_engine.py's _build_obligation_descriptors() (Layer 4 feed)
and, in the same pass, logged an open question in docs/CONCEPTS_INDEX.md:
whether el_reasoner.py's ultimate_accountability() has the identical
blind spot for this construct, since AM-56 only confirmed coverage for
ViolationResponse.creates_burden. Direct inspection confirmed it does:
grep -n "Authorization\\|auth_burden" toolchain/el_reasoner.py returned
zero matches before this fix. A burden created purely via
'authorization { creates_burden_on_authority: ... }' -- no Commitment, no
Delegation, no Role.holds, no ViolationResponse -- fell through every
existing branch and returned [], the same "genuinely not found" symptom
AM-53/AM-56 already fixed for the role-anchor and violation-response
cases respectively.

Zero live usage of creates_burden_on_authority/auth_burden anywhere in
scenarios/ (confirmed via grep at fix time, same as AM-86's own probe) --
this is a proactive-closure test, not a regression test against a real
scenario. Reuses AM-86's exact probe spec (_AUTH_BURDEN_PROBE in
tests/test_am86_obligation_descriptor_roots.py) for consistency between
the Layer-2 and Layer-4 checks on the identical construct.
"""
from el_parser import parse_string
from el_reasoner import AccountabilityChain, StaticRoleAnchor, ultimate_accountability

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
    description: "AM-87 probe: burden created via Authorization.creates_burden_on_authority"
}

authorization probeAuthorization {
    authority: Authority
    to_agent: Agent
    grants_permit: accessPermit
    creates_burden_on_authority: facilitationBurden
}
"""


def test_authorization_auth_burden_resolves_to_authorization_root():
    """actor_name resolves from .authority (the grammar's own comment:
    "the authority grants a permit AND undertakes a burden to
    facilitate"), not .to_agent -- the party being authorized, not the
    one taking on the burden. Reported as a genuine AccountabilityChain,
    not a StaticRoleAnchor, since Authorization.authority carries no
    filler ambiguity to flag (mirrors AM-56's ViolationResponse
    reasoning exactly)."""
    result = parse_string(_AUTH_BURDEN_PROBE, validate=True)
    assert result.ok, result.errors

    results = ultimate_accountability(result.model, "facilitationBurden")
    assert len(results) == 1
    chain = results[0]
    assert isinstance(chain, AccountabilityChain)
    assert not isinstance(chain, StaticRoleAnchor)
    assert chain.root_party == "Authority"
    assert chain.current_holder == "Authority"
    assert chain.root_commitment is None
    assert chain.root_violation_response is None
    assert chain.root_authorization == "probeAuthorization"


def test_authorization_without_auth_burden_still_returns_not_found():
    """Sanity/negative case: an Authorization with no auth_burden set must
    not manufacture a root (mirrors how ViolationResponse.creates_burden
    absent yields nothing, AM-56)."""
    probe = _AUTH_BURDEN_PROBE.replace(
        "    creates_burden_on_authority: facilitationBurden\n", ""
    )
    result = parse_string(probe, validate=True)
    assert result.ok, result.errors

    assert ultimate_accountability(result.model, "facilitationBurden") == []


def test_existing_violation_response_root_unaffected_no_regression():
    """Regression guard: AM-87's new fallback sits after AM-56's in the
    same branch -- confirm the real escalationNoticeBurden case (AM-56)
    still resolves via ViolationResponse, not accidentally shadowed by
    the new Authorization check."""
    from el_parser import parse

    result = parse("scenarios/referral/referral_scenario.el", validate=False)
    assert result.ok, result.errors

    results = ultimate_accountability(result.model, "escalationNoticeBurden")
    assert len(results) == 1
    chain = results[0]
    assert chain.root_violation_response == "referralNoResponseViolation"
    assert chain.root_authorization is None
