"""
2.5.0-1 — a permit with a time limit, by state and event.

One parametrised file for the cells of the permit's transition table. These
cells cover use: a permit with a 5-minute limit, granted at tick 3, used at
tick 20 in each of the six states, and the two restores that go through past
the limit and leave a permit the use check then refuses.

Fixture: as tests/test_permit_clock.py. Operator performs the acts and holds
the permit.
"""
from dataclasses import replace

import pytest

from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification PermitTableProbe

party Issuer
party Operator

community ProbeCommunity
    description: "Single role that uses, suspends and restores one permit"
    {
        objective: "Exercise a permit with a time limit"

        role operatorRole
            description: "Performs the acts"
            {
                action useTimed {
                    actor: operatorRole
                    requires_permit timedPermit
                }

                action pendTimed {
                    actor: operatorRole
                    effect pend timedPermit
                }

                action activateTimed {
                    actor: operatorRole
                    effect activate timedPermit
                }

                action unrelatedAction {
                    actor: operatorRole
                }
            }
    }

permit timedPermit {
    for_action: "useTimed"
    state: active
    deadline: "5 minutes"
}

embargo afterRevokeEmbargo {
    for_action: "unrelatedAction"
    state: pending
}

authorization TimedAuth {
    authority: Issuer
    to_agent: Operator
    grants_permit: timedPermit
    revocable: true
    on_revocation: activate afterRevokeEmbargo
}
"""

GRANT_TICK = 3
PAST_THE_LIMIT = 20

ELAPSED = "required permit 'timedPermit' time has elapsed for actor"
NOT_HELD = "required permit 'timedPermit' not held by actor"


def _runtime(permit_state=None) -> Runtime:
    """Operator holds timedPermit from GRANT_TICK. permit_state seeds the
    instance directly in a state only a run can produce."""
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = enroll(state, "Issuer")
    state = state.with_tick(GRANT_TICK)
    token = token_from_spec(spec, "timedPermit", "Operator", GRANT_TICK)
    if permit_state:
        token = replace(token, state=permit_state)
    return Runtime(grant_token(state, token), spec)


def _permit(rt):
    return next(t for t in rt.current_state().tokens if t.token_name == "timedPermit")


def _clock_to(rt, tick):
    ticks = tick - rt.current_state().tick
    if ticks:
        assert rt.advance_clock(ticks).outcome == "ok"
    assert rt.current_state().tick == tick


# ── Use past the limit, in each state ────────────────────────────────────────

@pytest.mark.parametrize("permit_state, reason", [
    ("active", ELAPSED),
    ("pending", NOT_HELD),
    ("claimable", NOT_HELD),
    ("expired", NOT_HELD),
    ("superseded", NOT_HELD),
    ("lapsed", NOT_HELD),
])
def test_use_past_the_limit_in_each_state(permit_state, reason):
    rt = _runtime(permit_state)
    _clock_to(rt, PAST_THE_LIMIT)

    record = rt.advance("useTimed", "Operator")

    assert record.outcome == "blocked"
    assert record.reason == reason
    assert _permit(rt).state == permit_state


# ── Use within the limit ─────────────────────────────────────────────────────

def test_use_of_an_active_permit_within_the_limit_is_allowed():
    rt = _runtime()
    _clock_to(rt, GRANT_TICK + 1)

    assert rt.advance("useTimed", "Operator").outcome == "ok"

    assert _permit(rt).state == "active"


# ── A restore past the limit goes through; the use check then refuses ────────

def test_pending_permit_restored_past_the_limit_is_active_and_elapsed():
    rt = _runtime()
    assert rt.advance("pendTimed", "Operator").outcome == "ok"
    assert _permit(rt).state == "pending"
    _clock_to(rt, PAST_THE_LIMIT)

    assert rt.advance("activateTimed", "Operator").outcome == "ok"

    assert _permit(rt).state == "active"
    record = rt.advance("useTimed", "Operator")
    assert record.outcome == "blocked"
    assert record.reason == ELAPSED


def test_superseded_permit_reinstated_past_the_limit_is_active_and_elapsed():
    rt = _runtime()
    assert rt.revoke_authorization("TimedAuth").outcome == "ok"
    assert _permit(rt).state == "superseded"
    _clock_to(rt, PAST_THE_LIMIT)

    assert rt.reinstate_authorization("TimedAuth").outcome == "ok"

    assert _permit(rt).state == "active"
    record = rt.advance("useTimed", "Operator")
    assert record.outcome == "blocked"
    assert record.reason == ELAPSED
