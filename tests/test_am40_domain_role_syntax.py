"""
AM-40 (proposed) — role-based Domain controlling/controlled syntax.

Grammar/parser/validator support for `controlling_role` / `controlled_role`
/ `fills` / `via` was added alongside the existing `controlling_object` /
`controlled_object` syntax (docs/el_grammar_amendments.md, AM-40). Neither
syntax was removed; a domain may use either. These are minimal
Layer 1 (grammar/parse) and Layer 2 (validator rule) tests per
tests/README.md's strategy — throwaway fixtures, not a full scenario.

referral_scenario.el's PatientDataDomain migration to this syntax is
deliberately deferred to a separate session (see AM-40 entry) and is not
exercised here.
"""
from el_parser import parse_string


_HEADER = 'enterprise specification Probe\n\n'

_TWO_COMMUNITIES = (
    'community PlantFed {\n'
    '    objective: "probe plant fed"\n'
    '}\n\n'
    'community VendorFed {\n'
    '    objective: "probe vendor fed"\n'
    '}\n\n'
)

_FEDERATION = (
    'federation OEMVendorFederation {\n'
    '    objective: "probe federation"\n'
    '    member: PlantFed\n'
    '    member: VendorFed\n'
    '}\n\n'
)


def _find(model, cls_name, name=None):
    matches = [e for e in model.elements if type(e).__name__ == cls_name]
    if name is None:
        return matches
    return next(e for e in matches if e.name == name)


def test_role_based_syntax_parses_and_populates_typed_lists():
    """controlling_role/controlled_role/fills parse and P8 populates the
    new typed lists, leaving the old-syntax lists empty for a domain that
    uses only the new syntax."""
    src = _HEADER + (
        'party Plant\n'
        'party OEMVendor\n\n'
        'domain PlantGovernanceDomain {\n'
        '    controlling_role role plantAuthority {}\n'
        '    controlled_role role deployedAgent {}\n'
        '    Plant fills plantAuthority\n'
        '    OEMVendor fills deployedAgent\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    domain = _find(result.model, 'Domain', 'PlantGovernanceDomain')
    assert [r.name for r in domain.controlling_roles] == ['plantAuthority']
    assert [r.name for r in domain.controlled_roles] == ['deployedAgent']
    assert domain.controlling_objects == []
    assert domain.controlled_objects == []


def test_role_filler_resolves_obj_and_role_by_identity():
    """Each DomainRoleFiller resolves obj=[EnterpriseObject] and
    role=[Role] to the actual objects declared elsewhere in the domain —
    not just matching names, but resolving to the same Role instance the
    domain itself declared (see V-NEW-21's identity-comparison rationale
    for why this distinction matters)."""
    src = _HEADER + (
        'party Plant\n'
        'party OEMVendor\n\n'
        'domain PlantGovernanceDomain {\n'
        '    controlling_role role plantAuthority {}\n'
        '    controlled_role role deployedAgent {}\n'
        '    Plant fills plantAuthority\n'
        '    OEMVendor fills deployedAgent\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    domain = _find(result.model, 'Domain', 'PlantGovernanceDomain')
    plant = _find(result.model, 'EnterpriseObject', 'Plant')
    vendor = _find(result.model, 'EnterpriseObject', 'OEMVendor')

    assert len(domain.role_fillers) == 2
    by_obj = {rf.obj.name: rf for rf in domain.role_fillers}

    assert by_obj['Plant'].obj is plant
    assert by_obj['Plant'].role is domain.controlling_roles[0]
    assert by_obj['OEMVendor'].obj is vendor
    assert by_obj['OEMVendor'].role is domain.controlled_roles[0]


def test_role_filler_via_federation_resolves():
    """The optional 'via' field on DomainRoleFiller resolves to the
    Federation that admitted the filler — the one genuinely new field
    AM-40 adds beyond generalizing MemberRef's existing 'fills' idiom."""
    src = _HEADER + _TWO_COMMUNITIES + _FEDERATION + (
        'party Plant\n'
        'party OEMVendor\n\n'
        'domain PlantGovernanceDomain {\n'
        '    controlling_role role plantAuthority {}\n'
        '    controlled_role role deployedAgent {}\n'
        '    Plant fills plantAuthority\n'
        '    OEMVendor fills deployedAgent via OEMVendorFederation\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    domain = _find(result.model, 'Domain', 'PlantGovernanceDomain')
    federation = _find(result.model, 'Federation', 'OEMVendorFederation')

    fillers_by_obj = {rf.obj.name: rf for rf in domain.role_fillers}
    assert fillers_by_obj['Plant'].via is None
    assert fillers_by_obj['OEMVendor'].via is federation


def test_role_based_domain_passes_v_new_21():
    """A domain using only the new syntax, with both roles actually
    filled, satisfies V-NEW-21 — the either-syntax controlling/controlled
    check added alongside this grammar work."""
    src = _HEADER + (
        'party Plant\n'
        'party OEMVendor\n\n'
        'domain PlantGovernanceDomain {\n'
        '    controlling_role role plantAuthority {}\n'
        '    controlled_role role deployedAgent {}\n'
        '    Plant fills plantAuthority\n'
        '    OEMVendor fills deployedAgent\n'
        '}\n'
    )
    result = parse_string(src, validate=True)
    assert result.ok, result.errors


def test_declared_but_unfilled_roles_fail_v_new_21():
    """A domain that declares controlling_role/controlled_role but never
    fills either one satisfies neither syntax and must be rejected by
    V-NEW-21 — declaring a role is not the same as it being filled."""
    src = _HEADER + (
        'domain EmptyDomain {\n'
        '    controlling_role role plantAuthority {}\n'
        '    controlled_role role deployedAgent {}\n'
        '}\n'
    )
    result = parse_string(src, validate=True)
    assert not result.ok
    assert any('V-NEW-21' in e for e in result.errors)
