"""
Layer 2 — 2.4.0-4: validator rules for an action that fills a role
(`effect fill <Role> with <Object>`).

New rules: [fill-one-filler] (error: one action fills a role twice,
§7.8.2); [W-fill-role-filled] (a `fills` statement already fills the role,
so the act is always refused, §7.8.2, §7.6.3); [W-fill-excluded-role] (the
filler fills, by a `fills` statement, a role excluded by either role's
assignment_policy, §7.8.2 NOTE 5, §7.6.2); [W-fill-not-modelled] (once per
filled role: the verifier does not model the fill, §7.6.2 NOTE 2, §7.8.2).

Existing rules read an effect fill as a possible filler: W-27/W-28 (the
element is in scope, and the filler fills the role) and W-29 (the role is
filled). [W-burden-not-modelled] gains a last hint for a burden granted
on_join, naming an action that fills the role.
"""
from el_parser import parse_string


def _src(award_body="            effect fill contractorRole with SupplierA",
         fills="", community_extra="", tokens=""):
    return f"""
enterprise specification RoleFillValidator

permit awardPermit {{ state: active }}
{tokens}
party Buyer {{ holds awardPermit }}
party SupplierA
party SupplierB
party Auditor

community C {{
    objective: "probe"
{community_extra}
    Buyer fills buyerRole
{fills}
    role buyerRole {{
        action award {{
            actor: buyerRole
            requires_permit awardPermit
{award_body}
        }}
    }}
    role contractorRole {{
        action notify {{
            actor: contractorRole
        }}
    }}
    role auditorRole {{
        action audit {{
            actor: auditorRole
        }}
    }}
}}
"""


def _parse(spec):
    result = parse_string(spec, validate=True)
    assert result.model is not None, result.errors
    return result


def _tagged(messages, tag):
    return [m for m in messages if m.startswith(tag)]


# ── [fill-one-filler] ──────────────────────────────────────────────────────

def test_fill_one_filler_fires_on_two_fills_of_one_role():
    result = _parse(_src(award_body="""
            effect fill contractorRole with SupplierA
            effect fill contractorRole with SupplierB"""))
    assert _tagged(result.errors, "[fill-one-filler]") == [
        "[fill-one-filler] Action 'award' fills role 'contractorRole' more than "
        "once: at most one object fills a role at any time. (§7.8.2)"
    ]
    assert not result.ok


def test_fill_one_filler_silent_on_fills_of_different_roles():
    result = _parse(_src(award_body="""
            effect fill contractorRole with SupplierA
            effect fill auditorRole with Auditor"""))
    assert _tagged(result.errors, "[fill-one-filler]") == []
    assert result.ok, result.errors


# ── [W-fill-role-filled] ───────────────────────────────────────────────────

def test_filling_a_filled_role_fires_when_a_fills_statement_fills_the_role():
    result = _parse(_src(fills="    SupplierB fills contractorRole"))
    assert _tagged(result.warnings, "[W-fill-role-filled]") == [
        "[W-fill-role-filled] Action 'award' fills role 'contractorRole', which "
        "'SupplierB' already fills (a fills statement): one object fills a role "
        "at a time and a filled role is not refilled, so the action is always "
        "refused. (§7.8.2, §7.6.3)"
    ]


def test_filling_a_filled_role_silent_when_no_fills_statement_fills_the_role():
    result = _parse(_src(fills="    SupplierB fills auditorRole"))
    assert _tagged(result.warnings, "[W-fill-role-filled]") == []


# ── [W-fill-excluded-role] ─────────────────────────────────────────────────

def test_fill_excluded_role_fires_when_the_new_roles_policy_excludes():
    result = _parse(_src(fills="    SupplierA fills auditorRole", community_extra="""
    assignment_policy for contractorRole {
        excludes_role auditorRole
    }"""))
    assert _tagged(result.warnings, "[W-fill-excluded-role]") == [
        "[W-fill-excluded-role] Action 'award' fills role 'contractorRole' with "
        "'SupplierA', which fills 'auditorRole'; the assignment policy of "
        "'contractorRole' excludes 'auditorRole', so the action is always "
        "refused. (§7.8.2 NOTE 5, §7.6.2)"
    ]


def test_fill_excluded_role_fires_when_the_held_roles_policy_excludes():
    result = _parse(_src(fills="    SupplierA fills auditorRole", community_extra="""
    assignment_policy for auditorRole {
        excludes_role contractorRole
    }"""))
    [w] = _tagged(result.warnings, "[W-fill-excluded-role]")
    assert ("the assignment policy of 'auditorRole' excludes 'contractorRole'"
            in w)


def test_fill_excluded_role_silent_when_another_object_fills_the_excluded_role():
    result = _parse(_src(fills="    Auditor fills auditorRole", community_extra="""
    assignment_policy for contractorRole {
        excludes_role auditorRole
    }"""))
    assert _tagged(result.warnings, "[W-fill-excluded-role]") == []


# ── [W-fill-not-modelled] ──────────────────────────────────────────────────

def test_fill_not_modelled_fires_once_per_role_naming_the_actions():
    result = _parse(_src().replace("""            actor: auditorRole
""", """            actor: auditorRole
            effect fill contractorRole with SupplierB
"""))
    assert _tagged(result.warnings, "[W-fill-not-modelled]") == [
        "[W-fill-not-modelled] Role 'contractorRole' is filled by an action "
        "(award, audit): the verifier does not model the fill. A static model "
        "has no filler from it, so the role's actions and on_join tokens are "
        "missing for that filler; a hybrid model sees the filler only once the "
        "act has run. (§7.6.2 NOTE 2, §7.8.2)"
    ]


def test_fill_not_modelled_silent_without_an_effect_fill():
    result = _parse(_src(award_body=""))
    assert _tagged(result.warnings, "[W-fill-not-modelled]") == []


# ── Existing rules read an effect fill as a possible filler ────────────────

def test_w27_silenced_when_an_effect_fill_is_the_holders_only_role():
    tokens = """burden notifyBurden { for_action: "notify" state: active deadline: "1 day" }
commitment supplierCommits { by: SupplierA obligation: "notify" creates_burden: notifyBurden }"""
    without = _parse(_src(award_body="", tokens=tokens))
    assert len(_tagged(without.warnings, "[W-27]")) == 1
    result = _parse(_src(tokens=tokens))
    assert _tagged(result.warnings, "[W-27]") == []


def test_w28_silenced_when_an_effect_fill_is_the_holders_only_role():
    tokens = 'permit notifyPermit { for_action: "notify" state: active }'
    src = _src(tokens=tokens).replace("party SupplierA\n",
                                      "party SupplierA { holds notifyPermit }\n")
    without = _parse(src.replace(
        "            effect fill contractorRole with SupplierA\n", ""))
    assert len(_tagged(without.warnings, "[W-28]")) == 1
    result = _parse(src)
    assert _tagged(result.warnings, "[W-28]") == []


def test_w29_silenced_when_an_action_fills_the_role():
    tokens = """burden notifyBurden { for_action: "notify" state: active deadline: "1 day" }
burden remedyBurden { state: pending deadline: "1 day" }
commitment buyerCommits { by: Buyer obligation: "notify" creates_burden: notifyBurden }
violation_response R {
    on_violation_of: notifyBurden
    obligates: Buyer
    response_kind: remediate
    creates_burden: remedyBurden
    creates_burden_for_role: contractorRole
}"""
    without = _parse(_src(award_body="", tokens=tokens))
    assert len(_tagged(without.warnings, "[W-29]")) == 1
    result = _parse(_src(tokens=tokens))
    assert _tagged(result.warnings, "[W-29]") == []


# ── [W-burden-not-modelled]: the on_join hint ──────────────────────────────

_ON_JOIN = """    on_join contractorRole transfer incidentBurden"""
_INCIDENT = 'burden incidentBurden { for_action: "notify" state: active deadline: "1 day" }'


def test_burden_not_modelled_on_join_hint_without_a_filling_action():
    result = _parse(_src(award_body="", tokens=_INCIDENT, community_extra=_ON_JOIN))
    assert _tagged(result.warnings, "[W-burden-not-modelled]") == [
        "[W-burden-not-modelled] Burden 'incidentBurden' has no root: no "
        "Commitment or other construct creates it for a holder, so the "
        "pre-execution model has no obligation for it and the verifier gives no "
        "verdict on it. Add a Commitment by the object accountable for it. Role "
        "'contractorRole' grants it on joining (on_join); the runtime grants it "
        "to whoever fills contractorRole, and only a hybrid model sees it. "
        "(§7.8.7, §6.4.1, §7.10.3)"
    ]


def test_burden_not_modelled_on_join_hint_names_the_filling_action():
    result = _parse(_src(tokens=_INCIDENT, community_extra=_ON_JOIN))
    assert _tagged(result.warnings, "[W-burden-not-modelled]") == [
        "[W-burden-not-modelled] Burden 'incidentBurden' has no root: no "
        "Commitment or other construct creates it for a holder, so the "
        "pre-execution model has no obligation for it and the verifier gives no "
        "verdict on it. Add a Commitment by the object accountable for it. Role "
        "'contractorRole' grants it on joining (on_join); the runtime grants it "
        "to whoever fills contractorRole, and only a hybrid model sees it. "
        "Action 'award' fills contractorRole (effect fill). "
        "(§7.8.7, §6.4.1, §7.10.3)"
    ]
