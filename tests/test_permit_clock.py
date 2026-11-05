"""
2.5.0-1 — a permit's clock runs from its first activation.

Before, a permit that was suspended and restored by `effect activate` or an
event got a new activated_at_tick, so its clock restarted, while a restore by
reinstate wrote no stamp at all. A permit that was not active and had no stamp
could have been active since grant or never active.

Now: a permit with no stamp that leaves active takes its grant tick as its
stamp, every restore keeps a stamp it finds, and a permit with no stamp gets
one on its first activation by any route. So a permit that is not active and
has no stamp has never been active, and has no clock (_permit_clock_start()).
Burdens and embargoes keep restamping on restore. The use check reads a
permit's clock (_permit_usable()), and nothing else does yet.

Fixture: as tests/test_activate_effect_pending_only.py. Operator performs the
acts and holds the tokens under test; Colleague fills no role and only holds
tokens. Tokens are granted at tick 3, so a grant-tick stamp cannot be mistaken
for tick 0.
"""
from dataclasses import replace

import pytest

from el_engine import (
    _permit_clock_start,
    enroll,
    grant_token,
    initial_state,
    token_from_spec,
)
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification PermitClockProbe

party Issuer
party Operator
party Colleague

community ProbeCommunity
    description: "Single role whose actions suspend and restore tokens"
    {
        objective: "Exercise the permit clock"
            satisfaction: any_discharged(siblingGroup)

        event heldEvent
        event waitingEvent

        role operatorRole
            description: "Performs the acts"
            {
                action pendHeld {
                    actor: operatorRole
                    effect pend heldPermit
                }

                action activateHeld {
                    actor: operatorRole
                    effect activate heldPermit
                }

                action pendWaiting {
                    actor: operatorRole
                    effect pend waitingPermit
                }

                action activateWaiting {
                    actor: operatorRole
                    effect activate waitingPermit
                }

                action dischargeSibling {
                    actor: operatorRole
                }

                action pendBurden {
                    actor: operatorRole
                    effect pend probeBurden
                }

                action activateBurden {
                    actor: operatorRole
                    effect activate probeBurden
                }

                action pendEmbargo {
                    actor: operatorRole
                    effect pend probeEmbargo
                }

                action activateEmbargo {
                    actor: operatorRole
                    effect activate probeEmbargo
                }

                action unrelatedAction {
                    actor: operatorRole
                }
            }
    }

permit heldPermit {
    for_action: "unrelatedAction"
    state: active
    triggered_by: heldEvent
}

permit waitingPermit {
    for_action: "unrelatedAction"
    state: pending
    triggered_by: waitingEvent
}

permit siblingPermit {
    for_action: "unrelatedAction"
    state: active
}

burden siblingBurden {
    for_action: "dischargeSibling"
    state: active
    discharge_mode: eventual
}

burden probeBurden {
    state: active
    discharge_mode: eventual
}

embargo probeEmbargo {
    for_action: "unrelatedAction"
    state: active
}

embargo afterRevokeEmbargo {
    for_action: "unrelatedAction"
    state: pending
}

token_group siblingGroup {
    member: siblingBurden
    member: siblingPermit
}

commitment siblingBurdenCommitment {
    by: Issuer
    obligation: "Backs the group member siblingBurden"
    creates_burden: siblingBurden
}

commitment siblingPermitCommitment {
    by: Issuer
    obligation: "Backs the group member siblingPermit"
    creates_burden: siblingPermit
}

authorization HeldAuth {
    authority: Issuer
    to_agent: Operator
    grants_permit: heldPermit
    revocable: true
    on_revocation: activate afterRevokeEmbargo
}

authorization WaitingAuth {
    authority: Issuer
    to_agent: Operator
    grants_permit: waitingPermit
    revocable: true
    on_revocation: activate afterRevokeEmbargo
}

authorization SiblingAuth {
    authority: Issuer
    to_agent: Operator
    grants_permit: siblingPermit
    revocable: true
    on_revocation: activate afterRevokeEmbargo
}
"""

GRANT_TICK = 3

# A route that restores a pending permit, for the permit that has been active
# since grant and the permit that has never been active.
_RESTORES = {
    "effect_activate": {
        "heldPermit": lambda rt: rt.advance("activateHeld", "Operator"),
        "waitingPermit": lambda rt: rt.advance("activateWaiting", "Operator"),
    },
    "event": {
        "heldPermit": lambda rt: rt.fire_event("heldEvent"),
        "waitingPermit": lambda rt: rt.fire_event("waitingEvent"),
    },
    "reinstate": {
        "heldPermit": lambda rt: rt.reinstate_authorization("HeldAuth"),
        "waitingPermit": lambda rt: rt.reinstate_authorization("WaitingAuth"),
    },
}


def _runtime(*grants) -> Runtime:
    """Each grant is (token name, holder), or (token name, holder, state)
    for an instance seeded directly in a state only a run can produce."""
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = enroll(state, "Colleague")
    state = enroll(state, "Issuer")
    state = state.with_tick(GRANT_TICK)
    for name, holder, *seeded in grants:
        token = token_from_spec(spec, name, holder, GRANT_TICK)
        if seeded:
            token = replace(token, state=seeded[0])
        state = grant_token(state, token)
    return Runtime(state, spec)


def _token(rt, name, holder="Operator"):
    return next(t for t in rt.current_state().tokens
                if t.token_name == name and t.holder == holder)


def _clock_to(rt, tick):
    ticks = tick - rt.current_state().tick
    if ticks:
        assert rt.advance_clock(ticks).outcome == "ok"
    assert rt.current_state().tick == tick


def _act(rt, action):
    assert rt.advance(action, "Operator").outcome == "ok"


# ── A pending permit restored, by each route ─────────────────────────────────

@pytest.mark.parametrize("route", sorted(_RESTORES))
def test_restore_of_a_permit_active_before_keeps_the_stamp(route):
    rt = _runtime(("heldPermit", "Operator"))
    assert _token(rt, "heldPermit").activated_at_tick is None
    assert _permit_clock_start(_token(rt, "heldPermit")) == GRANT_TICK
    _clock_to(rt, 10)
    _act(rt, "pendHeld")
    assert _token(rt, "heldPermit").state == "pending"
    assert _token(rt, "heldPermit").activated_at_tick == GRANT_TICK
    _clock_to(rt, 20)

    record = _RESTORES[route]["heldPermit"](rt)

    assert record.outcome == "ok"
    tok = _token(rt, "heldPermit")
    assert tok.state == "active"
    assert tok.activated_at_tick == GRANT_TICK
    assert tok.granted_at_tick == GRANT_TICK
    assert _permit_clock_start(tok) == GRANT_TICK


@pytest.mark.parametrize("route", sorted(_RESTORES))
def test_first_activation_of_a_permit_never_active_is_stamped_now(route):
    # Colleague's instance is already active. Every route matches by name
    # across holders, and none may start a new clock on that instance.
    rt = _runtime(("waitingPermit", "Operator"),
                  ("waitingPermit", "Colleague", "active"))
    other = _token(rt, "waitingPermit", "Colleague")
    assert _token(rt, "waitingPermit").state == "pending"
    assert _token(rt, "waitingPermit").activated_at_tick is None
    assert _permit_clock_start(_token(rt, "waitingPermit")) is None
    _clock_to(rt, 20)

    record = _RESTORES[route]["waitingPermit"](rt)

    assert record.outcome == "ok"
    tok = _token(rt, "waitingPermit")
    assert tok.state == "active"
    assert tok.activated_at_tick == 20
    assert tok.granted_at_tick == GRANT_TICK
    assert _permit_clock_start(tok) == 20
    assert _token(rt, "waitingPermit", "Colleague") == other
    assert _permit_clock_start(other) == GRANT_TICK


# ── Further suspensions ──────────────────────────────────────────────────────

def test_second_suspend_and_restore_cycle_keeps_the_stamp():
    rt = _runtime(("waitingPermit", "Operator"))
    _clock_to(rt, 10)
    _act(rt, "activateWaiting")
    assert _token(rt, "waitingPermit").activated_at_tick == 10

    for pend_at, restore_at in ((15, 20), (25, 30)):
        _clock_to(rt, pend_at)
        _act(rt, "pendWaiting")
        assert _token(rt, "waitingPermit").state == "pending"
        assert _token(rt, "waitingPermit").activated_at_tick == 10
        _clock_to(rt, restore_at)
        _act(rt, "activateWaiting")
        assert _token(rt, "waitingPermit").state == "active"
        assert _token(rt, "waitingPermit").activated_at_tick == 10


# ── Revoked, or superseded by a sibling, then reinstated ─────────────────────

def test_active_since_grant_revoked_then_reinstated_keeps_the_grant_clock():
    rt = _runtime(("heldPermit", "Operator"))
    _clock_to(rt, 10)

    assert rt.revoke_authorization("HeldAuth").outcome == "ok"

    assert _token(rt, "heldPermit").state == "superseded"
    assert _token(rt, "heldPermit").activated_at_tick == GRANT_TICK
    _clock_to(rt, 20)

    assert rt.reinstate_authorization("HeldAuth").outcome == "ok"

    tok = _token(rt, "heldPermit")
    assert tok.state == "active"
    assert tok.activated_at_tick == GRANT_TICK
    assert _permit_clock_start(tok) == GRANT_TICK


def test_never_active_revoked_then_reinstated_is_stamped_now():
    rt = _runtime(("waitingPermit", "Operator"))
    _clock_to(rt, 10)

    assert rt.revoke_authorization("WaitingAuth").outcome == "ok"

    assert _token(rt, "waitingPermit").state == "superseded"
    assert _token(rt, "waitingPermit").activated_at_tick is None
    assert _permit_clock_start(_token(rt, "waitingPermit")) is None
    _clock_to(rt, 20)

    assert rt.reinstate_authorization("WaitingAuth").outcome == "ok"

    tok = _token(rt, "waitingPermit")
    assert tok.state == "active"
    assert tok.activated_at_tick == 20
    assert _permit_clock_start(tok) == 20


def test_permit_superseded_by_a_sibling_then_reinstated_keeps_its_clock():
    rt = _runtime(("siblingBurden", "Operator"), ("siblingPermit", "Operator"))
    _clock_to(rt, 10)

    record = rt.advance("dischargeSibling", "Operator")

    assert record.discharged == ("siblingBurden",)
    assert _token(rt, "siblingPermit").state == "superseded"
    assert _token(rt, "siblingPermit").activated_at_tick == GRANT_TICK
    _clock_to(rt, 20)

    assert rt.reinstate_authorization("SiblingAuth").outcome == "ok"

    tok = _token(rt, "siblingPermit")
    assert tok.state == "active"
    assert tok.activated_at_tick == GRANT_TICK


# ── Burdens and embargoes still restamp ──────────────────────────────────────

@pytest.mark.parametrize("name, pend, activate", [
    ("probeBurden", "pendBurden", "activateBurden"),
    ("probeEmbargo", "pendEmbargo", "activateEmbargo"),
], ids=["burden", "embargo"])
def test_burden_and_embargo_still_restamp_on_restore(name, pend, activate):
    rt = _runtime((name, "Operator"))
    _clock_to(rt, 10)
    _act(rt, pend)
    assert _token(rt, name).state == "pending"
    assert _token(rt, name).activated_at_tick is None
    _clock_to(rt, 20)
    _act(rt, activate)
    assert _token(rt, name).activated_at_tick == 20

    _clock_to(rt, 25)
    _act(rt, pend)
    assert _token(rt, name).activated_at_tick == 20
    _clock_to(rt, 30)
    _act(rt, activate)

    assert _token(rt, name).state == "active"
    assert _token(rt, name).activated_at_tick == 30


# ── Reinstate's first-time grant ─────────────────────────────────────────────

def test_first_time_grant_by_reinstate_leaves_the_stamp_none():
    """Granted now, so the grant tick is the activation tick."""
    rt = _runtime()
    _clock_to(rt, 20)

    assert rt.reinstate_authorization("WaitingAuth").outcome == "ok"

    tok = _token(rt, "waitingPermit")
    assert tok.state == "active"
    assert tok.granted_at_tick == 20
    assert tok.activated_at_tick is None
    assert _permit_clock_start(tok) == 20
