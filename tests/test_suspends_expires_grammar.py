"""
Grammar and parser for the `suspends:` and `expires:` clauses of a
violation response (2.5.0).

Each clause names one Authorization, one per line, as `revokes:` does, and
may be repeated. The clause order is fixed: revokes, then suspends, then
expires. The parser unwraps each line, so the response's `suspends` and
`expires` lists hold the Authorization objects themselves.

Only parsing is tested here; what a response does with these lists at run
time is not.
"""
from el_parser import parse_string


_BASE = """
enterprise specification SuspendsExpiresProbe
party Org
agent Ag
agent Bg
burden recB {{
    for_action: "rec"
    state: active
    deadline: "5 minutes"
}}
permit useP {{
    for_action: "use"
    state: active
}}
permit readP {{
    for_action: "read"
    state: active
}}
community C {{
    objective: "o"
    Org fills owner
    Ag fills user
    Bg fills reader
    role owner {{ action rec {{ actor: owner }} }}
    role user {{ action use {{ actor: user requires_permit useP }} }}
    role reader {{ action read {{ actor: reader requires_permit readP }} }}
}}
authorization UseAuth {{
    authority: Org
    to_agent: Ag
    grants_permit: useP
    revocable: true
}}
authorization ReadAuth {{
    authority: Org
    to_agent: Bg
    grants_permit: readP
    revocable: true
}}
violation_response R {{
    on_violation_of: recB
    obligates: Org
    response_kind: remediate
    {response_items}
}}
"""


def _src(response_items):
    return _BASE.format(response_items=response_items)


def _vr(response_items):
    result = parse_string(_src(response_items))
    assert result.model is not None, result.errors
    return next(e for e in result.model.elements
                if type(e).__name__ == "ViolationResponse")


def _names(auths):
    return [a.name for a in auths]


def _all_authorizations(auths):
    return all(type(a).__name__ == "Authorization" for a in auths)


def test_suspends_holds_the_authorization():
    vr = _vr("suspends: UseAuth")
    assert _names(vr.suspends) == ["UseAuth"]
    assert _all_authorizations(vr.suspends)
    assert vr.revokes == []
    assert vr.expires == []


def test_expires_holds_the_authorization():
    vr = _vr("expires: UseAuth")
    assert _names(vr.expires) == ["UseAuth"]
    assert _all_authorizations(vr.expires)
    assert vr.revokes == []
    assert vr.suspends == []


def test_revokes_suspends_and_expires_together_keep_their_own_lists():
    # Written in the fixed order: revokes, then suspends, then expires.
    vr = _vr("revokes: UseAuth\n    suspends: ReadAuth\n    expires: UseAuth")
    assert _names(vr.revokes) == ["UseAuth"]
    assert _names(vr.suspends) == ["ReadAuth"]
    assert _names(vr.expires) == ["UseAuth"]
    for auths in (vr.revokes, vr.suspends, vr.expires):
        assert _all_authorizations(auths)


def test_response_without_any_of_the_three_has_empty_lists():
    vr = _vr("description: \"no authorization clauses\"")
    assert vr.revokes == []
    assert vr.suspends == []
    assert vr.expires == []


def test_unknown_authorization_in_suspends_or_expires_is_a_parse_error():
    for clause in ("suspends: NoSuchAuth", "expires: NoSuchAuth"):
        result = parse_string(_src(clause))
        assert not result.ok, clause
        assert result.model is None, clause


def test_repeated_suspends_line_keeps_both_entries():
    vr = _vr("suspends: UseAuth\n    suspends: ReadAuth")
    assert _names(vr.suspends) == ["UseAuth", "ReadAuth"]
    assert _all_authorizations(vr.suspends)
