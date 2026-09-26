"""
AM-104 — validator warnings on ViolationResponses.

[W-21] terminate response with nothing to revoke; [W-22] escalate response
with no creates_burden (a ledger entry only); [W-23] escalate_to missing or
not a party (the dormant V-NEW-16, as a warning). All advisory: .ok stays
True. Also pins where they fire across the tracked scenarios.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_parser import parse, parse_string

_ROOT = Path(__file__).resolve().parent.parent


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _warnings(src, prefix):
    result = _quiet(parse_string, src)
    assert result.ok, result.errors
    return [w for w in result.warnings if w.startswith(prefix)]


_HEADER = """
enterprise specification ResponseWarningProbe

party Agency
party OtherAuthority
party Operator
{
    principal_of Bot
}
agent Bot
{
    delegated_from Operator
}

permit botPermit { for_action: "readData" state: active }
embargo cutOffEmbargo { for_action: "readData" state: pending }

burden noticeBurden {
    for_action: "notify"
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}
burden followUpBurden {
    for_action: "followUp"
    state: pending
    deadline: "1 hour"
    discharge_mode: eventual
}

commitment OperatorNotifies {
    by: Operator
    obligation: "notify the agency"
    creates_burden: noticeBurden
}
"""

_AUTH = """
authorization BotAuthorization {{
    authority: {authority}
    to_agent: Bot
    grants_permit: botPermit
    revocable: true
    on_revocation: activate cutOffEmbargo
}}
"""

_TERMINATE = """
violation_response terminateResponse {
    on_violation_of: noticeBurden
    obligates: Agency
    response_kind: terminate
}
"""


def test_w21_silent_when_chain_holds_revocable_authorization():
    src = _HEADER + _AUTH.format(authority="Agency") + _TERMINATE
    assert _warnings(src, "[W-21]") == []


@pytest.mark.parametrize("auth", ["", _AUTH.format(authority="OtherAuthority")])
def test_w21_warns_when_nothing_to_revoke(auth):
    """No Authorization at all, or only one granted by another authority."""
    warnings = _warnings(_HEADER + auth + _TERMINATE, "[W-21]")
    assert len(warnings) == 1
    assert "Terminate response 'terminateResponse' has nothing to revoke" in warnings[0]
    assert "(Bot, Operator)" in warnings[0]


def test_w22_escalate_without_creates_burden():
    src = _HEADER + """
violation_response bareEscalation {
    on_violation_of: noticeBurden
    obligates: Agency
    response_kind: escalate
    escalate_to: Agency
}
violation_response burdenEscalation {
    on_violation_of: noticeBurden
    obligates: Agency
    response_kind: escalate
    creates_burden: followUpBurden
    escalate_to: Agency
}
"""
    assert _warnings(src, "[W-22]") == [
        "[W-22] Escalate response 'bareEscalation' has no creates_burden: it "
        "fires as a ledger entry only; nobody becomes obligated. "
        "(§6.3.8, §7.8.6 NOTE 2)"
    ]


def test_w23_escalate_to_must_be_a_party():
    src = _HEADER + """
violation_response toAgent {
    on_violation_of: noticeBurden
    obligates: Agency
    response_kind: escalate
    creates_burden: followUpBurden
    escalate_to: Bot
}
violation_response toNobody {
    on_violation_of: noticeBurden
    obligates: Agency
    response_kind: escalate
    creates_burden: followUpBurden
}
violation_response toParty {
    on_violation_of: noticeBurden
    obligates: Agency
    response_kind: escalate
    creates_burden: followUpBurden
    escalate_to: Agency
}
"""
    warnings = _warnings(src, "[W-23]")
    assert len(warnings) == 2
    assert "'toAgent' escalates to 'Bot' (agent), not a party" in warnings[0]
    assert "'toNobody' names no escalate_to" in warnings[1]


_EXPECTED_W22 = {
    "scenarios/ereferral/ereferral_model.el": 2,
    "scenarios/terms_of_engagement/public_data_portal_scenario.el": 1,
    "scenarios/terms_of_engagement/external_agent_access_scenario.el": 1,
    "scenarios/referral/referral_scenario.el": 0,
    "scenarios/gp_referral/gp_referral_scenario.el": 0,
}


@pytest.mark.parametrize("rel", sorted(_EXPECTED_W22))
def test_tracked_scenarios(rel):
    """W-22 on the four escalate responses without creates_burden; no
    tracked scenario triggers W-21 or W-23."""
    result = _quiet(parse, _ROOT / rel)
    assert len([w for w in result.warnings if w.startswith("[W-22]")]) == _EXPECTED_W22[rel]
    assert not [w for w in result.warnings if w.startswith(("[W-21]", "[W-23]"))]
