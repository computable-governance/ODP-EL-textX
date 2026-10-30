"""
Layer 2 — 2.4.0-2: `effect fill <Role> with <Object>` in an action body.

The grammar rule RoleFillEffect (§7.6.2, §7.8.2) states that performing
the action makes the named enterprise object fill the named role. This
file pins the parse only: the rule resolves both cross-references, P4
collects the items in Action.role_fills (never deontic_effects), and the
construct is refused outside Action bodies. The engine applies it from
2.4.0-3.
"""
import contextlib
import io

from el_parser import parse_string


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _src(award_body, role_extra="", community_extra=""):
    return f"""
enterprise specification RoleFillProbe

embargo awardEmbargo {{ state: pending }}

party Buyer
party SupplierA
party Auditor

community C {{
    objective: "probe"
    Buyer fills buyerRole
    role buyerRole {{
        action award {{
            actor: buyerRole
{award_body}
        }}
{role_extra}
    }}
    role contractorRole {{
        action perform {{
            actor: contractorRole
        }}
    }}
    role auditorRole {{
        action audit {{
            actor: auditorRole
        }}
    }}
{community_extra}
}}
"""


def _parse(award_body, role_extra="", community_extra=""):
    return _quiet(parse_string, _src(award_body, role_extra, community_extra),
                  validate=False)


def _award(result):
    assert result.ok, result.errors
    community = next(e for e in result.model.elements if type(e).__name__ == "Community")
    buyer = next(r for r in community.roles if r.name == "buyerRole")
    return next(a for a in buyer.actions if a.name == "award")


def test_effect_fill_parses():
    award = _award(_parse("            effect fill contractorRole with SupplierA"))
    assert len(award.role_fills) == 1
    assert type(award.role_fills[0]).__name__ == "RoleFillEffect"


def test_role_and_filler_resolve_to_the_declared_objects():
    result = _parse("            effect fill contractorRole with SupplierA")
    award = _award(result)
    community = next(e for e in result.model.elements if type(e).__name__ == "Community")
    contractor = next(r for r in community.roles if r.name == "contractorRole")
    supplier = next(e for e in result.model.elements if getattr(e, "name", None) == "SupplierA")
    fill = award.role_fills[0]
    assert fill.role is contractor
    assert fill.filler is supplier


def test_several_fill_lines_are_kept_in_declared_order():
    award = _award(_parse("            effect fill contractorRole with SupplierA\n"
                          "            effect fill auditorRole with Auditor"))
    assert [(f.role.name, f.filler.name) for f in award.role_fills] == [
        ("contractorRole", "SupplierA"), ("auditorRole", "Auditor")]


def test_fills_go_to_role_fills_not_deontic_effects():
    award = _award(_parse("            effect fill contractorRole with SupplierA\n"
                          "            effect activate awardEmbargo"))
    assert [type(f).__name__ for f in award.role_fills] == ["RoleFillEffect"]
    assert [(e.operation, e.token.name) for e in award.deontic_effects] == [
        ("activate", "awardEmbargo")]
    assert award.items == []


def test_unknown_role_or_object_is_a_parse_error():
    unknown_role = _parse("            effect fill noSuchRole with SupplierA")
    assert not unknown_role.ok
    assert any(e.startswith("[SEMANTIC]") and "noSuchRole" in e for e in unknown_role.errors), unknown_role.errors
    unknown_object = _parse("            effect fill contractorRole with NoSuchParty")
    assert not unknown_object.ok
    assert any(e.startswith("[SEMANTIC]") and "NoSuchParty" in e for e in unknown_object.errors), unknown_object.errors


def _step(line):
    return ('        process P { initiates: "start" terminates: "end"\n'
            "            step s1 { actor: buyerRole\n"
            f"{line}\n"
            "            } }")


def _conditional_action(line):
    return f"        conditional_action c1 {{\n{line}\n        }}"


def test_effect_fill_in_a_step_body_is_a_parse_error():
    assert _parse("", community_extra=_step("")).ok
    result = _parse("", community_extra=_step(
        "                effect fill contractorRole with SupplierA"))
    assert not result.ok
    assert any(e.startswith("[SYNTAX]") for e in result.errors), result.errors


def test_effect_fill_in_a_conditional_action_body_is_a_parse_error():
    assert _parse("", role_extra=_conditional_action("")).ok
    result = _parse("", role_extra=_conditional_action(
        "            effect fill contractorRole with SupplierA"))
    assert not result.ok
    assert any(e.startswith("[SYNTAX]") for e in result.errors), result.errors
