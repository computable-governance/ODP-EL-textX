"""
AM-115 — grammar and validator for violation declaration and response
targets.

  - `declares_violation_of <burden>` in an Action body (DeclaresViolationItem,
    one per line; P4 collects Action.declares_violation_of) makes the Action a
    declaration (§6.6.5). V-NEW-24: the burden is strict, and the Action
    requires a permit (§7.10.4).
  - ViolationResponse `creates_burden_for_role: <Role>` (burden_role) grants
    creates_burden to the role's fillers; V-NEW-25 requires creates_burden;
    [W-29] warns when no object fills the role.
  - ViolationResponse `revokes: <Authorization>` (RevokesItem, one per line;
    P13 unwraps into ViolationResponse.revokes). V-NEW-23: each is revocable,
    has an on_revocation embargo, and is granted by obligates (§6.6.4).
  - [W-21] leaves a terminate response with an explicit revokes list to
    V-NEW-23; [W-23] accepts creates_burden_for_role as the escalation target.
"""
import pytest

from el_engine import _find_action
from el_parser import parse_string


_BASE = """
enterprise specification DeclarationProbe
party Org
party Other
agent Gate {{ delegated_from Org }}
agent Dog {{ delegated_from Org }}
party Mgr
agent Ag
burden recB {{
    for_action: "rec"
    state: active
    deadline: "5 minutes"
    discharge_mode: {rec_mode}
}}
burden otherB {{
    for_action: "rec"
    state: active
    deadline: "5 minutes"
    discharge_mode: strict
}}
burden invB {{
    for_action: "inv"
    state: active
    deadline: "1 day"
}}
permit declP {{
    for_action: "declRec"
    state: active
}}
permit useP {{
    for_action: "use"
    state: active
}}
embargo outE {{
    for_action: "use"
    state: pending
}}
community C {{
    objective: "o"
    Gate fills gw
    Dog fills dec
    {inv_filler}
    Ag fills user
    role gw {{ action rec {{ actor: gw }} }}
    role dec {{
        action declRec {{
            actor: dec
            {decl_items}
        }}
    }}
    role inv {{ action inv {{ actor: inv favoured_by_burden invB }} }}
    role user {{ action use {{ actor: user requires_permit useP }} }}
}}
authorization UseAuth {{
    authority: {use_authority}
    to_agent: Ag
    grants_permit: useP
    {use_revocable}
    {use_embargo}
}}
authorization DeclAuth {{
    authority: Org
    to_agent: Dog
    grants_permit: declP
}}
violation_response R {{
    on_violation_of: recB
    obligates: Org
    response_kind: {kind}
    {response_items}
}}
"""


def _src(**over):
    params = dict(
        rec_mode="strict",
        inv_filler="Mgr fills inv",
        decl_items="requires_permit declP\n            declares_violation_of recB",
        use_authority="Org",
        use_revocable="revocable: true",
        use_embargo="on_revocation: activate outE",
        kind="remediate",
        response_items=("creates_burden: invB\n    creates_burden_for_role: inv\n"
                        "    revokes: UseAuth"),
    )
    params.update(over)
    return _BASE.format(**params)


def _parse(**over):
    result = parse_string(_src(**over))
    assert result.model is not None, result.errors
    return result


def _codes(messages, code):
    return [m for m in messages if m.startswith(code)]


def _vr(result):
    return next(e for e in result.model.elements if type(e).__name__ == "ViolationResponse")


# ── Parsing ──────────────────────────────────────────────────────────────────

def test_clean_probe_parses_without_new_findings():
    result = _parse()
    assert result.ok, result.errors
    for code in ("[V-NEW-23]", "[V-NEW-24]", "[V-NEW-25]", "[W-29]"):
        assert not _codes(result.errors + result.warnings, code)


def test_declares_violation_of_collected_per_line():
    result = _parse(decl_items=("requires_permit declP\n"
                                "            declares_violation_of recB\n"
                                "            declares_violation_of otherB"))
    action, role = _find_action(result.model, "declRec")
    assert role.name == "dec"
    assert [t.name for t in action.declares_violation_of] == ["recB", "otherB"]
    assert action.items == []


def test_ordinary_action_declares_nothing():
    result = _parse()
    action, _ = _find_action(result.model, "rec")
    assert action.declares_violation_of == []


def test_response_role_target_and_revokes_list():
    result = _parse(use_authority="Org",
                    response_items=("creates_burden: invB\n    creates_burden_for_role: inv\n"
                                    "    revokes: UseAuth\n    revokes: UseAuth"))
    vr = _vr(result)
    assert vr.burden_role.name == "inv"
    assert [a.name for a in vr.revokes] == ["UseAuth", "UseAuth"]
    assert all(type(a).__name__ == "Authorization" for a in vr.revokes)


def test_response_without_new_fields_has_defaults():
    vr = _vr(_parse(response_items="creates_burden: invB"))
    assert vr.burden_role is None
    assert vr.revokes == []


def test_revokes_unknown_authorization_is_a_parse_error():
    result = parse_string(_src(response_items="revokes: NoSuchAuth"))
    assert not result.ok


# ── V-NEW-23: revoked Authorizations ─────────────────────────────────────────

@pytest.mark.parametrize("over,fragment", [
    (dict(use_revocable=""), "is not revocable"),
    (dict(use_embargo=""), "has no on_revocation embargo"),
    (dict(use_authority="Other"), "is granted by 'Other', not by obligates 'Org'"),
])
def test_v_new_23_names_each_problem(over, fragment):
    result = _parse(**over)
    errs = _codes(result.errors, "[V-NEW-23]")
    assert len(errs) == 1 and "'UseAuth'" in errs[0] and fragment in errs[0]
    assert not result.ok


def test_v_new_23_non_revocable_declaration_authorization():
    result = _parse(response_items="revokes: DeclAuth")
    (err,) = _codes(result.errors, "[V-NEW-23]")
    assert "'DeclAuth'" in err and "is not revocable and has no on_revocation embargo" in err


# ── V-NEW-24: declaration actions ────────────────────────────────────────────

def test_v_new_24_eventual_burden():
    result = _parse(rec_mode="eventual")
    (err,) = _codes(result.errors, "[V-NEW-24]")
    assert "'recB', an eventual burden" in err


def test_v_new_24_not_a_burden():
    result = _parse(decl_items="requires_permit declP\n            declares_violation_of useP")
    (err,) = _codes(result.errors, "[V-NEW-24]")
    assert "'useP', a permit" in err


def test_v_new_24_no_permit():
    result = _parse(decl_items="declares_violation_of recB")
    (err,) = _codes(result.errors, "[V-NEW-24]")
    assert "requires no permit" in err


# ── V-NEW-25 and W-29: role target ───────────────────────────────────────────

def test_v_new_25_role_without_burden():
    result = _parse(response_items="creates_burden_for_role: inv")
    (err,) = _codes(result.errors, "[V-NEW-25]")
    assert "'R'" in err and "'inv'" in err


def test_w29_unfilled_role():
    result = _parse(inv_filler="")
    (warn,) = _codes(result.warnings, "[W-29]")
    assert "'invB'" in warn and "'inv'" in warn


# ── W-21 / W-23 adjustments ──────────────────────────────────────────────────

def test_w21_silent_for_terminate_with_revokes():
    result = _parse(kind="terminate", response_items="revokes: UseAuth")
    assert not _codes(result.warnings, "[W-21]")


def test_w21_still_fires_for_terminate_without_revokes():
    # recB's holder (Gate) has no agent Authorization granted by Org.
    result = parse_string(_src(kind="terminate", response_items="") + """
commitment OrgRecords {
    by: Org
    obligation: "record"
    creates_burden: recB
    principals_obligated: Org
}
""")
    assert _codes(result.warnings, "[W-21]")


def test_w23_accepts_role_target():
    result = _parse(kind="escalate",
                    response_items="creates_burden: invB\n    creates_burden_for_role: inv")
    assert not _codes(result.warnings, "[W-23]")
    assert not _codes(result.warnings, "[W-22]")


def test_w23_still_fires_with_neither_target():
    result = _parse(kind="escalate", response_items="creates_burden: invB")
    assert _codes(result.warnings, "[W-23]")
