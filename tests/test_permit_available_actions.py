"""
2.5.0-1 — available-actions and a permit's time limit.

An active permit past its time limit is not listed as permitted, as the use
check refuses it. A date-form limit is not judged at use, so a permit past its
date stays listed. A permit that is not active is left out, whatever its time.
"""
from dataclasses import replace

import el_api
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification PermitAvailableActionsProbe

party Operator

community ProbeCommunity
    description: "Single role that uses permits with time limits"
    {
        objective: "Exercise permits with time limits"

        role operatorRole
            description: "Performs the acts"
            {
                action useShort {
                    actor: operatorRole
                    requires_permit shortPermit
                }

                action useLong {
                    actor: operatorRole
                    requires_permit longPermit
                }

                action useDated {
                    actor: operatorRole
                    requires_permit datedPermit
                }
            }
    }

permit shortPermit {
    for_action: "useShort"
    state: active
    deadline: "5 minutes"
}

permit longPermit {
    for_action: "useLong"
    state: active
    deadline: "1 hour"
}

permit datedPermit {
    for_action: "useDated"
    state: active
    deadline: "by 2026-01-01"
}
"""

GRANT_TICK = 3
PAST_THE_SHORT_LIMIT = 20


def _listed(monkeypatch, permit_name, permit_state=None, tick=PAST_THE_SHORT_LIMIT, also=()):
    """Permitted actions of Operator at `tick`, holding permit_name and `also`
    from GRANT_TICK; permit_state seeds permit_name's instance directly."""
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole").with_tick(GRANT_TICK)
    token = token_from_spec(spec, permit_name, "Operator", GRANT_TICK)
    if permit_state:
        token = replace(token, state=permit_state)
    state = grant_token(state, token)
    for other in also:
        state = grant_token(state, token_from_spec(spec, other, "Operator", GRANT_TICK))
    rt = Runtime(state, spec)
    assert rt.advance_clock(tick - GRANT_TICK).outcome == "ok"
    monkeypatch.setattr(el_api, "_runtime", rt)
    return el_api.get_available_actions("Operator").available_actions


def test_an_elapsed_active_permit_is_not_listed_while_an_unelapsed_one_is(monkeypatch):
    entries = _listed(monkeypatch, "shortPermit", also=("longPermit",))

    assert [(e.action, e.reason, e.token, e.deadline) for e in entries] == [
        ("useLong", "permitted", "longPermit", None),
    ]


def test_a_date_form_permit_past_its_date_is_still_listed(monkeypatch):
    entries = _listed(monkeypatch, "datedPermit")

    assert [(e.action, e.reason, e.token, e.deadline) for e in entries] == [
        ("useDated", "permitted", "datedPermit", None),
    ]


def test_a_permit_that_is_not_active_is_left_out_as_before(monkeypatch):
    within_the_limit = GRANT_TICK + 1
    for permit_state in ("pending", "claimable", "expired", "superseded", "lapsed"):
        assert _listed(monkeypatch, "shortPermit", permit_state, within_the_limit) == []
