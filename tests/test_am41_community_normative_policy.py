"""
AM-41 — NormativePolicy widened from Domain/Federation-only to any
plain Community.

Grammar: Community's own rule gained `(normative_policies+=NormativePolicyRef)*`
alongside its other typed lists (docs/el_grammar_amendments.md, AM-41).
Parser: new object processor P11 (process_community) resolves each
NormativePolicyRef wrapper to its .policy, matching the resolved-policy
convention P8/P9 already use for Domain/Federation.
Validator: V-NEW-20 (which previously rejected NormativePolicy on plain
Community) is retired — it can no longer fire on anything the grammar
allows, since Community/Domain/Federation are now all permitted.

These are minimal Layer 1 (grammar/parse) and Layer 2 (validator) tests
per tests/README.md's strategy — throwaway fixtures, not a full scenario.
"""
from el_parser import parse_string


_HEADER = 'enterprise specification Probe\n\n'

_POLICY = (
    'normative_policy TestAct {\n'
    '    source: "Test Act 2026"\n'
    '    kind: legislation\n'
    '}\n\n'
)


def _find(model, cls_name, name=None):
    matches = [e for e in model.elements if type(e).__name__ == cls_name]
    if name is None:
        return matches
    return next(e for e in matches if e.name == name)


def test_plain_community_normative_policy_resolves_by_identity():
    """A plain Community's normative_policy: line resolves to the actual
    declared NormativePolicy instance, not a name string or wrapper."""
    src = _HEADER + _POLICY + (
        'community PlainCommunity {\n'
        '    objective: "probe plain community normative policy"\n'
        '    normative_policy: TestAct\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    community = _find(result.model, 'Community', 'PlainCommunity')
    policy = _find(result.model, 'NormativePolicy', 'TestAct')

    assert len(community.normative_policies) == 1
    assert community.normative_policies[0] is policy


def test_plain_community_normative_policy_passes_validation():
    """V-NEW-20's old restriction is retired — a plain Community citing a
    NormativePolicy must validate clean (AM-41)."""
    src = _HEADER + _POLICY + (
        'community PlainCommunity {\n'
        '    objective: "probe plain community normative policy"\n'
        '    normative_policy: TestAct\n'
        '}\n'
    )
    result = parse_string(src, validate=True)
    assert result.ok, result.errors
    assert not any('V-NEW-20' in e for e in result.errors)


def test_domain_normative_policy_still_resolves_unchanged():
    """Regression: Domain's own normative_policy handling (P8, AM-28) is
    unaffected by the new Community-level processor (P11) — Domain uses
    its own separate grammar rule and processor, not Community's."""
    src = _HEADER + _POLICY + (
        'party Controller\n'
        'party Controlled\n\n'
        'domain ProbeDomain {\n'
        '    controlling_object: Controller\n'
        '    controlled_object: Controlled\n'
        '    normative_policy: TestAct\n'
        '}\n'
    )
    result = parse_string(src, validate=True)
    assert result.ok, result.errors

    domain = _find(result.model, 'Domain', 'ProbeDomain')
    policy = _find(result.model, 'NormativePolicy', 'TestAct')
    assert domain.normative_policies == [policy]


def test_federation_normative_policy_still_resolves_unchanged():
    """Regression: Federation's own normative_policy handling (P9, AM-28)
    is unaffected — Federation is not a Community subclass and has its
    own separate grammar rule/processor."""
    src = _HEADER + _POLICY + (
        'community MemberOne {\n'
        '    objective: "probe federation member"\n'
        '}\n\n'
        'federation ProbeFederation {\n'
        '    objective: "probe federation"\n'
        '    member: MemberOne\n'
        '    normative_policy: TestAct\n'
        '}\n'
    )
    result = parse_string(src, validate=True)
    assert result.ok, result.errors

    federation = _find(result.model, 'Federation', 'ProbeFederation')
    policy = _find(result.model, 'NormativePolicy', 'TestAct')
    assert federation.normative_policies == [policy]


def test_community_with_multiple_normative_policies():
    """A plain Community may cite more than one NormativePolicy — no
    cardinality limit is imposed by the grammar or V-NEW-20's retirement."""
    src = _HEADER + _POLICY + (
        'normative_policy OtherAct {\n'
        '    source: "Other Act 2026"\n'
        '    kind: standard\n'
        '}\n\n'
        'community PlainCommunity {\n'
        '    objective: "probe multiple normative policies"\n'
        '    normative_policy: TestAct\n'
        '    normative_policy: OtherAct\n'
        '}\n'
    )
    result = parse_string(src, validate=True)
    assert result.ok, result.errors

    community = _find(result.model, 'Community', 'PlainCommunity')
    assert {p.name for p in community.normative_policies} == {'TestAct', 'OtherAct'}


def test_episodic_community_normative_policy_resolves():
    """Confirmed 2026-07-22 (docs/CONCEPTS_INDEX.md, AM-41 entry): an
    episodic community — created via the lifecycle/establishing pattern,
    established_by an event emitted from a separate, standing community,
    mirroring referral_scenario.el's real ReferralEpisodeCommunity — is
    parsed by the exact same Community grammar rule AM-41 modified. It
    can therefore also carry a normative_policy: reference and have it
    resolve by identity, with zero new grammar work."""
    src = _HEADER + _POLICY + (
        'party Referrer\n\n'
        'community CreatingCommunity {\n'
        '    objective: "probe creating community"\n'
        '    event referralSubmitted\n'
        '    role referringRole {\n'
        '        action initiateReferral {\n'
        '            actor: referringRole\n'
        '            emits: referralSubmitted\n'
        '        }\n'
        '    }\n'
        '}\n\n'
        'community EpisodicProbeCommunity {\n'
        '    objective: "probe episodic community with a normative policy"\n'
        '    normative_policy: TestAct\n'
        '    lifecycle {\n'
        '        establishing {\n'
        '            established_by: referralSubmitted\n'
        '        }\n'
        '    }\n'
        '}\n'
    )
    result = parse_string(src, validate=True)
    assert result.ok, result.errors

    episodic = _find(result.model, 'Community', 'EpisodicProbeCommunity')
    policy = _find(result.model, 'NormativePolicy', 'TestAct')

    assert type(episodic).__name__ == 'Community'
    assert episodic.normative_policies == [policy]
    assert episodic.normative_policies[0] is policy
    assert episodic.lifecycle.establishing.established_by.name == 'referralSubmitted'
