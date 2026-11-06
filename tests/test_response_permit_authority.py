"""
Validator — [response-permit-authority] (2.5.0-2).

Each Authorization a violation response names in `suspends:` or `expires:`
must have the response's obligates as its authority. Only the authority is
checked: suspending or expiring a grant needs neither `revocable` nor an
`on_revocation` embargo. One error is given per line, suspends lines first,
then expires lines.

The specification here is self-contained: its Authorizations are not
revocable, so they raise no other Authorization errors.
"""
import contextlib
import io

from el_parser import parse_string


_SPEC = """
enterprise specification ResponsePermitAuthorityProbe
party Org
party Other
agent Ag
burden recB {{
    for_action: "rec"
    state: active
    deadline: "5 minutes"
}}
permit useP {{
    for_action: "use"
    state: active
}}
embargo stopE {{
    for_action: "use"
    state: pending
}}
community C {{
    objective: "o"
    Org fills owner
    Ag fills user
    role owner {{ action rec {{ actor: owner }} }}
    role user {{ action use {{ actor: user requires_permit useP }} }}
}}
authorization OrgAuth {{
    authority: Org
    to_agent: Ag
    grants_permit: useP
}}
authorization OtherAuth {{
    authority: Other
    to_agent: Ag
    grants_permit: useP
    {other_revocation}
}}
violation_response R {{
    on_violation_of: recB
    obligates: Org
    response_kind: remediate
    {response_items}
}}
"""

_TAG = "[response-permit-authority]"


def _parse(response_items, other_revocation=""):
    src = _SPEC.format(response_items=response_items, other_revocation=other_revocation)
    with contextlib.redirect_stdout(io.StringIO()):
        result = parse_string(src)
    assert result.model is not None, result.errors
    return result


def _tagged(messages, tag):
    return [m for m in messages if m.startswith(tag)]


def test_suspending_a_grant_made_by_obligates_is_accepted():
    result = _parse("suspends: OrgAuth")
    assert _tagged(result.errors, _TAG) == []


def test_expiring_a_grant_made_by_obligates_is_accepted():
    result = _parse("expires: OrgAuth")
    assert _tagged(result.errors, _TAG) == []


def test_suspending_a_grant_made_by_another_party_is_an_error():
    result = _parse("suspends: OtherAuth")
    (err,) = _tagged(result.errors, _TAG)
    assert "suspends Authorization 'OtherAuth'" in err
    assert "granted by 'Other'" in err
    assert "obligates 'Org'" in err


def test_expiring_a_grant_made_by_another_party_is_an_error():
    result = _parse("expires: OtherAuth")
    (err,) = _tagged(result.errors, _TAG)
    assert "expires Authorization 'OtherAuth'" in err
    assert "granted by 'Other'" in err
    assert "obligates 'Org'" in err


def test_one_error_for_each_line():
    result = _parse("suspends: OtherAuth\n    expires: OtherAuth")
    errs = _tagged(result.errors, _TAG)
    assert len(errs) == 2
    assert "suspends Authorization" in errs[0]
    assert "expires Authorization" in errs[1]


def test_a_revokes_line_is_left_to_the_revocation_rule():
    result = _parse("revokes: OtherAuth",
                    other_revocation="revocable: true\n    on_revocation: activate stopE")
    assert _tagged(result.errors, "[V-NEW-23]") != []
    assert _tagged(result.errors, _TAG) == []
