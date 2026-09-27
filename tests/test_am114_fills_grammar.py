"""
AM-114 part 3 — `obj fills role` in Community and Federation bodies (§7.8.2).

The AM-40 `fills` idiom (Domain's DomainRoleFiller), without `via`. P11
(Community) and P9 (Federation) collect each statement as a RoleFillerRef
in `role_fillers`. V-NEW-22: the role must be declared in the same element.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_parser import parse, parse_string


_REPO = Path(__file__).resolve().parent.parent
_TOE_DIR = _REPO / "scenarios" / "terms_of_engagement"


def _parse(src, validate=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return parse_string(src, validate=validate)


def _fillers(el):
    return [(rf.obj.name, rf.role.name) for rf in el.role_fillers]


def _element(model, name):
    return next(el for el in model.elements if getattr(el, "name", None) == name)


_BOTH = """
enterprise specification FillsProbe
agent A
agent B
community C {
    objective: "probe"
    A fills cRole
    role cRole { action a { actor: cRole } }
}
federation F {
    objective: "probe"
    B fills fRole
    role fRole { action b { actor: fRole } }
}
"""


def test_fills_parses_in_community_and_federation():
    result = _parse(_BOTH)
    assert result.ok, result.errors
    assert _fillers(_element(result.model, "C")) == [("A", "cRole")]
    assert _fillers(_element(result.model, "F")) == [("B", "fRole")]


def test_community_without_fills_has_no_role_fillers():
    result = _parse("""
enterprise specification NoFills
community C {
    objective: "probe"
    role cRole { action a { actor: cRole } }
}
""")
    assert result.ok, result.errors
    assert _element(result.model, "C").role_fillers == []


def test_v_new_22_role_of_another_element_is_an_error():
    result = _parse("""
enterprise specification WrongElement
agent A
community C1 {
    objective: "probe"
    A fills otherRole
    role ownRole { action a { actor: ownRole } }
}
community C2 {
    objective: "probe"
    role otherRole { action b { actor: otherRole } }
}
""")
    assert not result.ok
    assert any("[V-NEW-22] Community 'C1': 'A fills otherRole'" in e
               for e in result.errors), result.errors


@pytest.mark.parametrize("path, fillers", [
    (_TOE_DIR / "public_data_portal_scenario.el", [
        ("ExternalAIAgent", "externalRequesterRole"),
        ("AgencyGateway", "accessGatewayRole"),
        ("AgencySecurityContact", "incidentContactRole"),
        ("AgentOperator", "accountablePrincipalRole"),
    ]),
    (_TOE_DIR / "external_agent_access_scenario.el", [
        ("VendorReferralAgent", "externalRequesterRole"),
        ("ProviderAPIGateway", "accessGatewayRole"),
        ("ProviderSecurityContact", "incidentContactRole"),
        ("VendorOrg", "accountablePrincipalRole"),
    ]),
], ids=lambda p: p.stem if isinstance(p, Path) else "")
def test_terms_of_engagement_scenarios_state_their_fillers(path, fillers):
    with contextlib.redirect_stdout(io.StringIO()):
        result = parse(path, validate=True)
    assert result.ok, result.errors
    community = next(el for el in result.model.elements
                     if type(el).__name__ == "Community")
    assert _fillers(community) == fillers
