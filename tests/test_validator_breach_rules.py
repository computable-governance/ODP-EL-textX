"""
Validator — violation records (2.3.0-5).

V-NEW-24 accepts a permit or embargo as the target of
declares_violation_of (a burden must still be strict, and the declaring
Action must still require a permit). Three new warnings:
  [W-breach-response-duty]    a response to a permit or embargo that
                              creates no burden and revokes nothing
                              (terminate exempt);
  [W-refused-attempts-burden] also_on_refused_attempts on a response to
                              a burden;
  [W-breach-undeclarable]     a declared permit or embargo that applies to
                              no declared action.
"""
from el_parser import parse_string
from test_violation_records import _SPEC, _quiet


def _messages(extra="", base=_SPEC):
    result = _quiet(parse_string, base + extra)
    assert result.model is not None, result.errors
    return result.errors, result.warnings


def _tagged(messages, tag):
    return [m for m in messages if m.startswith(tag)]


def test_declaring_a_permit_or_embargo_is_valid():
    errors, warnings = _messages()
    assert _tagged(errors, "[V-NEW-24]") == []
    assert _tagged(warnings, "[W-breach-undeclarable]") == []


def test_v_new_24_keeps_its_burden_and_permit_checks():
    base = _SPEC.replace("declares_violation_of stopE",
                         "declares_violation_of stopE\n            declares_violation_of recB")
    errors, _ = _messages(base=base)
    (err,) = _tagged(errors, "[V-NEW-24]")
    assert "'recB', an eventual burden" in err
    base = _SPEC.replace("            requires_permit declP\n            declares_violation_of stopE",
                         "            declares_violation_of stopE")
    errors, _ = _messages(base=base)
    (err,) = _tagged(errors, "[V-NEW-24]")
    assert "Declaration action 'declUse' requires no permit" in err


_VR = """
violation_response {name} {{
    on_violation_of: {target}
    obligates: Gate
    response_kind: {kind}
    {extra}
}}
"""


def test_breach_response_duty():
    for target, kind, extra, warned in (
        ("stopE", "remediate", "", True),
        ("useP", "penalise", "", True),
        ("stopE", "terminate", "", False),
        ("stopE", "remediate", "creates_burden: recB", False),
        ("recB", "remediate", "", False),          # a burden: W-22 territory, not this rule
    ):
        _, warnings = _messages(_VR.format(name="R", target=target, kind=kind, extra=extra))
        found = _tagged(warnings, "[W-breach-response-duty]")
        assert bool(found) is warned, (target, kind, extra)
    _, warnings = _messages(_VR.format(name="R", target="stopE", kind="remediate", extra=""))
    assert _tagged(warnings, "[W-breach-response-duty]") == [
        "[W-breach-response-duty] ViolationResponse 'R' responds to a violation of embargo "
        "'stopE' but obliges no action: add creates_burden (granted to obligates, or with "
        "creates_burden_for_role to the role's fillers) or a revokes line. "
        "(§6.3.8, §7.8.6 NOTE 2)"]


def test_breach_response_duty_accepts_a_revokes_line():
    extra = """
authorization AgUse {
    authority: Gate
    to_agent: Ag
    grants_permit: useP
    revocable: true
    on_revocation: activate stopE
}
""" + _VR.format(name="R", target="useP", kind="remediate", extra="revokes: AgUse")
    _, warnings = _messages(extra)
    assert _tagged(warnings, "[W-breach-response-duty]") == []


def test_refused_attempts_flag_on_a_burden_response():
    _, warnings = _messages(_VR.format(name="R", target="recB", kind="escalate",
                                       extra="creates_burden: recB\n    escalate_to: Dog\n"
                                             "    also_on_refused_attempts: true"))
    assert _tagged(warnings, "[W-refused-attempts-burden]") == [
        "[W-refused-attempts-burden] ViolationResponse 'R' sets also_on_refused_attempts but "
        "responds to burden 'recB': a refused attempt breaches only a permit or an embargo. "
        "(§6.3.8, §7.8.6)"]
    _, warnings = _messages(_VR.format(name="R", target="stopE", kind="terminate",
                                       extra="also_on_refused_attempts: true"))
    assert _tagged(warnings, "[W-refused-attempts-burden]") == []


def test_breach_undeclarable():
    base = (_SPEC.replace('permit readP { for_action: "read" state: active }',
                          'permit readP { for_action: "nothing" state: active }')
            .replace('embargo stopE { for_action: "use" state: active }',
                     'embargo stopE { for_action: "nothing" state: active }'))
    _, warnings = _messages(base=base)
    assert _tagged(warnings, "[W-breach-undeclarable]") == [
        "[W-breach-undeclarable] Action 'declUse' declares_violation_of embargo 'stopE', "
        "which applies to no declared action: every declaration of it would be refused. "
        "(§6.3.8, §6.6.5, §7.8.6)",
        "[W-breach-undeclarable] Action 'declRead' declares_violation_of permit 'readP', "
        "which applies to no declared action: every declaration of it would be refused. "
        "(§6.3.8, §6.6.5, §7.8.6)",
    ]
    # useP is still required by 'use', so it stays declarable.


def test_a_general_embargo_applies_to_every_action():
    base = _SPEC.replace('embargo stopE { for_action: "use" state: active }',
                         'embargo stopE { state: active }')
    _, warnings = _messages(base=base)
    assert _tagged(warnings, "[W-breach-undeclarable]") == []
