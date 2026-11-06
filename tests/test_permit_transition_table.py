"""
2.5.0-1 — a permit with a time limit, by state and event.

One parametrised file for the cells of the permit's transition table. These
cells cover use: a permit with a 5-minute limit, granted at tick 3, used at
tick 20 in each of the six states, and the two restores that go through past
the limit and leave a permit the use check then refuses. They also cover a
response's revoke, which ignores the time limit: fired on a violated burden at
tick 20 in each of the six states, and at tick 4 on an active permit within the
limit. That makes seven cells, since active splits into elapsed and not elapsed.

The last section covers the sweep and the acts around it: the sweep in the
states it selects and those it leaves alone, a sibling discharged or claimed and
`effect pend` in all six states, and `effect activate` and event activation in
the five states other than pending. Tests that are not table cells are in
tests/test_permit_sweep.py.

The final section covers the acts around an expired permit: a direct
revoke and `effect create` in all six states, and a reinstate in active,
claimable, expired, superseded and lapsed. Tests with several holders and new
grants are in tests/test_permit_expired_final.py; consent events on an expired
permit are in tests/test_fhir_event_handler.py.

The last section covers a response's `suspends:` and `expires:` in all six
states (2.5.0-2).

Fixture: as tests/test_permit_clock.py. Operator performs the acts and holds
the permit.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from el_engine import DeadlineClock, enroll, grant_token, initial_state, token_from_spec
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

                action createTimed {
                    actor: operatorRole
                    effect create timedPermit
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

_RESPONSE = """
burden breachedBurden {
    for_action: "useTimed"
    state: active
    deadline: "5 minutes"
}

violation_response RevokeOnBreach {
    on_violation_of: breachedBurden
    obligates: Issuer
    response_kind: remediate
    revokes: TimedAuth
}
"""


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


def _responding_runtime(permit_state=None) -> Runtime:
    """As _runtime(), with a response that revokes TimedAuth and the burden it
    answers already violated, so firing does not depend on a sweep."""
    result = parse_string(_PROBE + _RESPONSE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = enroll(state, "Issuer")
    state = state.with_tick(GRANT_TICK)
    token = token_from_spec(spec, "timedPermit", "Operator", GRANT_TICK)
    if permit_state:
        token = replace(token, state=permit_state)
    burden = token_from_spec(spec, "breachedBurden", "Operator", GRANT_TICK)
    state = grant_token(grant_token(state, token), replace(burden, state="violated"))
    return Runtime(state, spec)


def _embargo_active(rt):
    return any(t.token_name == "afterRevokeEmbargo" and t.state == "active"
               for t in rt.current_state().tokens)


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


# ── A response's revoke ignores the time limit ───────────────────────────────

def test_response_revokes_an_active_permit_past_the_limit():
    rt = _responding_runtime()
    _clock_to(rt, PAST_THE_LIMIT)
    assert rt.advance("useTimed", "Operator").reason == ELAPSED
    assert _permit(rt).state == "active"

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("RevokeOnBreach",)
    assert "revoked 'TimedAuth' (to 'Operator')" in record.effects
    assert _permit(rt).state == "superseded"
    assert _embargo_active(rt)


def test_response_revokes_an_active_permit_within_the_limit():
    rt = _responding_runtime()
    _clock_to(rt, GRANT_TICK + 1)

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("RevokeOnBreach",)
    assert "revoked 'TimedAuth' (to 'Operator')" in record.effects
    assert _permit(rt).state == "superseded"
    assert _embargo_active(rt)


@pytest.mark.parametrize("permit_state", [
    "pending", "claimable", "expired", "superseded", "lapsed",
])
def test_response_does_not_revoke_a_permit_that_is_not_active(permit_state):
    rt = _responding_runtime(permit_state)
    _clock_to(rt, PAST_THE_LIMIT)

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("RevokeOnBreach",)
    assert ("not revoked 'TimedAuth': permit 'timedPermit' is not active"
            in record.effects)
    assert _permit(rt).state == permit_state
    assert not _embargo_active(rt)


def test_response_revoke_of_an_elapsed_permit_depends_on_which_came_first():
    # Before the sweep the record says active, so the revoke applies. After it
    # the permit is expired, so it is not revoked and no embargo follows.
    revoked_first = _responding_runtime()
    _clock_to(revoked_first, PAST_THE_LIMIT)
    fired = revoked_first.fire_violation_responses()
    assert "revoked 'TimedAuth' (to 'Operator')" in fired.effects
    assert _permit(revoked_first).state == "superseded"
    assert _embargo_active(revoked_first)
    swept = revoked_first.check_live_violations()
    assert swept.token_events == ()
    assert _permit(revoked_first).state == "superseded"

    swept_first = _responding_runtime()
    _clock_to(swept_first, PAST_THE_LIMIT)
    swept_first.check_live_violations()
    assert _permit(swept_first).state == "expired"
    fired = swept_first.fire_violation_responses()
    assert fired.fired_responses == ("RevokeOnBreach",)
    assert ("not revoked 'TimedAuth': permit 'timedPermit' is not active"
            in fired.effects)
    assert _permit(swept_first).state == "expired"
    assert not _embargo_active(swept_first)


# ── The sweep and the other acts, by state ───────────────────────────────────
#
# A second probe: timedPermit also has an event trigger and sits in a group
# with one burden to discharge and one to claim; datedPermit has a date limit.

_SWEEP_PROBE = """
enterprise specification PermitSweepTableProbe

party Operator

community ProbeCommunity
    description: "Single role that uses, suspends and restores the permits"
    {
        objective: "Exercise the sweep by state"
            satisfaction: any_discharged(siblingGroup)

        event wakeEvent

        role operatorRole
            description: "Performs the acts"
            {
                action useTimed {
                    actor: operatorRole
                    requires_permit timedPermit
                }

                action useDated {
                    actor: operatorRole
                    requires_permit datedPermit
                }

                action pendTimed {
                    actor: operatorRole
                    effect pend timedPermit
                }

                action activateTimed {
                    actor: operatorRole
                    effect activate timedPermit
                }

                action dischargeSibling {
                    actor: operatorRole
                }

                action claimSibling {
                    actor: operatorRole
                }
            }
    }

permit timedPermit {
    for_action: "useTimed"
    state: active
    deadline: "5 minutes"
    triggered_by: wakeEvent
}

permit datedPermit {
    for_action: "useDated"
    state: active
    deadline: "by 2026-05-20"
}

burden activeSibling {
    for_action: "dischargeSibling"
    state: active
    discharge_mode: eventual
}

burden claimableSibling {
    for_action: "claimSibling"
    state: claimable
    discharge_mode: eventual
}

token_group siblingGroup {
    member: activeSibling
    member: claimableSibling
    member: timedPermit
}

commitment activeSiblingCommitment {
    by: Operator
    obligation: "Backs the group member activeSibling"
    creates_burden: activeSibling
}

commitment claimableSiblingCommitment {
    by: Operator
    obligation: "Backs the group member claimableSibling"
    creates_burden: claimableSibling
}

commitment timedPermitCommitment {
    by: Operator
    obligation: "Backs the group member timedPermit"
    creates_burden: timedPermit
}
"""

CLOCK = DeadlineClock(utc_offset=timezone(timedelta(hours=10)))
BEFORE_THE_DATE = datetime(2026, 5, 20, 12, 0, tzinfo=timezone(timedelta(hours=10)))
PAST_THE_DATE = datetime(2026, 5, 21, 0, 0, tzinfo=timezone(timedelta(hours=10)))
ALL_STATES = ["active", "pending", "claimable", "expired", "superseded", "lapsed"]
NOT_PENDING = ["active", "claimable", "expired", "superseded", "lapsed"]
NOT_SWEPT = ["claimable", "expired", "superseded", "lapsed"]


def _sweep_runtime(*seeded, siblings=False) -> Runtime:
    """Operator holds each (permit name, state) from GRANT_TICK; state None
    keeps the declared state. siblings also grants the group's two burdens."""
    result = parse_string(_SWEEP_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = state.with_tick(GRANT_TICK)
    for name, permit_state in seeded:
        token = token_from_spec(spec, name, "Operator", GRANT_TICK)
        if permit_state:
            token = replace(token, state=permit_state)
        state = grant_token(state, token)
    if siblings:
        for name in ("activeSibling", "claimableSibling"):
            state = grant_token(state, token_from_spec(spec, name, "Operator", GRANT_TICK))
    return Runtime(state, spec, clock=CLOCK)


def _token(rt, name):
    return next(t for t in rt.current_state().tokens if t.token_name == name)


# Sweep

def test_sweep_expires_an_active_permit_past_its_duration():
    rt = _sweep_runtime(("timedPermit", None))
    _clock_to(rt, PAST_THE_LIMIT)

    rt.check_live_violations()

    assert _token(rt, "timedPermit").state == "expired"
    assert rt.current_state().tick == PAST_THE_LIMIT + 1


def test_sweep_expires_an_active_permit_past_its_date():
    rt = _sweep_runtime(("datedPermit", None))

    rt.check_live_violations(as_at=PAST_THE_DATE)

    assert _token(rt, "datedPermit").state == "expired"
    assert rt.current_state().tick == GRANT_TICK + 1


def test_sweep_leaves_an_active_permit_not_yet_due():
    rt = _sweep_runtime(("timedPermit", None), ("datedPermit", None))
    _clock_to(rt, GRANT_TICK + 4)

    record = rt.check_live_violations(as_at=BEFORE_THE_DATE)

    assert _token(rt, "timedPermit").state == "active"
    assert _token(rt, "datedPermit").state == "active"
    assert record.effects == ()
    assert rt.current_state().tick == GRANT_TICK + 4


def test_sweep_expires_a_pending_permit_whose_clock_ran_on():
    # Active since grant, then pended: the clock counts from grant and keeps
    # running while pending. One step before the limit, then at it.
    rt = _sweep_runtime(("timedPermit", None))
    assert rt.advance("pendTimed", "Operator").outcome == "ok"
    _clock_to(rt, GRANT_TICK + 4)

    rt.check_live_violations()
    assert _token(rt, "timedPermit").state == "pending"

    _clock_to(rt, GRANT_TICK + 5)
    rt.check_live_violations()
    assert _token(rt, "timedPermit").state == "expired"


def test_sweep_leaves_a_never_active_pending_permit_until_its_clock_starts():
    # R-a: never active, so no clock. Time then counts from its first activation.
    rt = _sweep_runtime(("timedPermit", "pending"))
    _clock_to(rt, PAST_THE_LIMIT)

    record = rt.check_live_violations()

    assert _token(rt, "timedPermit").state == "pending"
    assert record.effects == ()
    assert rt.current_state().tick == PAST_THE_LIMIT

    assert rt.advance("activateTimed", "Operator").outcome == "ok"
    assert _token(rt, "timedPermit").activated_at_tick == PAST_THE_LIMIT
    _clock_to(rt, PAST_THE_LIMIT + 4)
    rt.check_live_violations()
    assert _token(rt, "timedPermit").state == "active"
    _clock_to(rt, PAST_THE_LIMIT + 5)
    rt.check_live_violations()
    assert _token(rt, "timedPermit").state == "expired"


def test_sweep_expires_a_never_active_pending_permit_past_its_date():
    rt = _sweep_runtime(("datedPermit", "pending"))

    rt.check_live_violations(as_at=PAST_THE_DATE)

    assert _token(rt, "datedPermit").state == "expired"
    assert _token(rt, "datedPermit").activated_at_tick is None


@pytest.mark.parametrize("permit_state", NOT_SWEPT)
def test_sweep_leaves_other_states_alone(permit_state):
    rt = _sweep_runtime(("timedPermit", permit_state), ("datedPermit", permit_state))
    _clock_to(rt, PAST_THE_LIMIT)

    record = rt.check_live_violations(as_at=PAST_THE_DATE)

    assert _token(rt, "timedPermit").state == permit_state
    assert _token(rt, "datedPermit").state == permit_state
    assert record.effects == () and record.token_events == ()
    assert rt.current_state().tick == PAST_THE_LIMIT


# Sibling rules

@pytest.mark.parametrize("permit_state", ALL_STATES)
def test_sibling_discharged_in_each_state(permit_state):
    rt = _sweep_runtime(("timedPermit", permit_state), siblings=True)

    record = rt.advance("dischargeSibling", "Operator")

    assert record.discharged == ("activeSibling",)
    if permit_state == "active":
        assert _token(rt, "timedPermit").state == "superseded"
        event = next(e for e in record.token_events if e.token_name == "timedPermit")
        assert (event.cause, event.cause_ref) == ("sibling", "activeSibling")
    else:
        assert _token(rt, "timedPermit").state == permit_state
        assert not [e for e in record.token_events if e.token_name == "timedPermit"]


@pytest.mark.parametrize("permit_state", ALL_STATES)
def test_sibling_claimed_in_each_state(permit_state):
    rt = _sweep_runtime(("timedPermit", permit_state), siblings=True)

    record = rt.claim("claimableSibling", "Operator")

    assert record.outcome == "ok"
    assert _token(rt, "claimableSibling").state == "active"
    if permit_state == "claimable":
        assert _token(rt, "timedPermit").state == "lapsed"
        event = next(e for e in record.token_events if e.token_name == "timedPermit")
        assert (event.cause, event.cause_ref) == ("sibling", "claimableSibling")
    else:
        assert _token(rt, "timedPermit").state == permit_state
        assert not [e for e in record.token_events if e.token_name == "timedPermit"]


# effect pend

@pytest.mark.parametrize("permit_state", ALL_STATES)
def test_effect_pend_in_each_state(permit_state):
    rt = _sweep_runtime(("timedPermit", permit_state))

    record = rt.advance("pendTimed", "Operator")

    assert record.outcome == "ok"
    if permit_state == "active":
        assert _token(rt, "timedPermit").state == "pending"
        assert record.effects == ("pended 'timedPermit'",)
    else:
        assert _token(rt, "timedPermit").state == permit_state
        assert record.effects == ()


# effect activate and event activation, in the states other than pending

@pytest.mark.parametrize("permit_state", NOT_PENDING)
def test_effect_activate_in_each_other_state(permit_state):
    rt = _sweep_runtime(("timedPermit", permit_state))

    record = rt.advance("activateTimed", "Operator")

    assert record.outcome == "ok"
    assert _token(rt, "timedPermit").state == permit_state
    if permit_state == "active":
        assert record.effects == ()
    else:
        assert record.effects == (
            f"activate 'timedPermit' had no effect: 'Operator' holds it {permit_state}",)


@pytest.mark.parametrize("permit_state", NOT_PENDING)
def test_event_activation_in_each_other_state(permit_state):
    rt = _sweep_runtime(("timedPermit", permit_state))

    record = rt.fire_event("wakeEvent")

    assert record.outcome == "ok"
    assert _token(rt, "timedPermit").state == permit_state
    assert record.effects == ()


# ── A direct revoke, a reinstate and effect create, by state ─────────────────

REVOKED_LINES = ("superseded permit 'timedPermit'", "activated embargo 'afterRevokeEmbargo'")
REINSTATED_LINES = ("activated permit 'timedPermit'", "lifted embargo 'afterRevokeEmbargo'")


def _seed_embargo(rt, embargo_state):
    """The on_revocation embargo, already granted in embargo_state."""
    embargo = token_from_spec(rt._spec, "afterRevokeEmbargo", "Operator", GRANT_TICK)
    rt._state = grant_token(rt.current_state(), replace(embargo, state=embargo_state))


def _embargo_states(rt):
    return [t.state for t in rt.current_state().tokens if t.token_name == "afterRevokeEmbargo"]


def _permit_events(record):
    return [e for e in record.token_events if e.token_name == "timedPermit"]


# Direct revoke

@pytest.mark.parametrize("permit_state", ALL_STATES)
def test_direct_revoke_in_each_state(permit_state):
    rt = _runtime(permit_state)
    _clock_to(rt, PAST_THE_LIMIT)
    # In superseded the embargo is active again, even from lifted.
    if permit_state == "superseded":
        _seed_embargo(rt, "lifted")

    record = rt.revoke_authorization("TimedAuth")

    assert record.outcome == "ok"
    if permit_state == "expired":
        assert _permit(rt).state == "expired"
        assert _permit(rt).activated_at_tick is None
        assert _embargo_states(rt) == []
        assert rt.current_state().tick == PAST_THE_LIMIT
        assert record.token_events == ()
        assert record.effects == (
            "revoke 'timedPermit' had no effect: 'Operator' holds it expired",)
        return
    assert _permit(rt).state == "superseded"
    # An active permit has been active since grant, so it takes that stamp.
    assert _permit(rt).activated_at_tick == (GRANT_TICK if permit_state == "active" else None)
    assert _embargo_states(rt) == ["active"]
    assert rt.current_state().tick == PAST_THE_LIMIT + 1
    assert record.effects == REVOKED_LINES
    if permit_state == "superseded":
        assert _permit_events(record) == []
    else:
        assert [e.event for e in _permit_events(record)] == ["superseded"]


# Reinstate

@pytest.mark.parametrize("permit_state", [
    "active", "claimable", "expired", "superseded", "lapsed",
])
def test_reinstate_in_each_state(permit_state):
    rt = _runtime(permit_state)
    _clock_to(rt, PAST_THE_LIMIT)
    _seed_embargo(rt, "active")

    record = rt.reinstate_authorization("TimedAuth")

    if permit_state == "expired":
        assert record.outcome == "blocked"
        assert record.reason == "permit 'timedPermit' has expired; only a new grant restores it"
        assert record.effects == ()
        assert record.token_events == ()
        assert record.blocked_by is None
        assert _permit(rt).state == "expired"
        assert _embargo_states(rt) == ["active"]
        assert rt.current_state().tick == PAST_THE_LIMIT
        return
    assert record.outcome == "ok"
    assert _permit(rt).state == "active"
    assert _embargo_states(rt) == ["lifted"]
    assert rt.current_state().tick == PAST_THE_LIMIT + 1
    if permit_state == "active":
        assert _permit(rt).activated_at_tick is None
        assert record.effects == ("lifted embargo 'afterRevokeEmbargo'",)
    else:
        # Never active before, so this is its first activation.
        assert _permit(rt).activated_at_tick == PAST_THE_LIMIT
        assert record.effects == REINSTATED_LINES


# effect create

@pytest.mark.parametrize("permit_state", ALL_STATES)
def test_effect_create_in_each_state(permit_state):
    rt = _runtime(permit_state)
    _clock_to(rt, PAST_THE_LIMIT)
    before = _permit(rt)

    record = rt.advance("createTimed", "Operator")

    assert record.outcome == "ok"
    assert [t for t in rt.current_state().tokens if t.token_name == "timedPermit"] == [before]
    assert record.effects == ()
    assert record.token_events == ()
    assert rt.current_state().tick == PAST_THE_LIMIT + 1


# ── A response's `suspends:` and `expires:`, by state (2.5.0-2) ──────────────
#
# The same probe with a response that suspends, or expires, TimedAuth instead
# of revoking it. Tests that are not table cells are in
# tests/test_response_suspends_expires.py.

_SUSPENDING_RESPONSE = _RESPONSE.replace(
    "violation_response RevokeOnBreach", "violation_response SuspendOnBreach"
).replace("revokes: TimedAuth", "suspends: TimedAuth")

_EXPIRING_RESPONSE = _RESPONSE.replace(
    "violation_response RevokeOnBreach", "violation_response ExpireOnBreach"
).replace("revokes: TimedAuth", "expires: TimedAuth")

SUSPEND_FIRED = ("fired 'SuspendOnBreach' (remediate) on violation of 'breachedBurden' "
                 "by 'Operator'")

EXPIRE_FIRED = ("fired 'ExpireOnBreach' (remediate) on violation of 'breachedBurden' "
                "by 'Operator'")


def _suspending_runtime(permit_state=None) -> Runtime:
    """As _responding_runtime(), with the response that suspends TimedAuth."""
    return _runtime_with_response(_SUSPENDING_RESPONSE, permit_state)


def _expiring_runtime(permit_state=None) -> Runtime:
    """As _responding_runtime(), with the response that expires TimedAuth."""
    return _runtime_with_response(_EXPIRING_RESPONSE, permit_state)


def _runtime_with_response(response, permit_state) -> Runtime:
    result = parse_string(_PROBE + response, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = enroll(state, "Issuer")
    state = state.with_tick(GRANT_TICK)
    token = token_from_spec(spec, "timedPermit", "Operator", GRANT_TICK)
    if permit_state:
        token = replace(token, state=permit_state)
    burden = token_from_spec(spec, "breachedBurden", "Operator", GRANT_TICK)
    state = grant_token(grant_token(state, token), replace(burden, state="violated"))
    return Runtime(state, spec)


@pytest.mark.parametrize("permit_state", ALL_STATES)
def test_response_suspends_in_each_state(permit_state):
    rt = _suspending_runtime(permit_state)
    _clock_to(rt, PAST_THE_LIMIT)

    record = rt.fire_violation_responses()

    assert record.outcome == "ok"
    assert record.fired_responses == ("SuspendOnBreach",)
    assert _embargo_states(rt) == []
    assert rt.current_state().tick == PAST_THE_LIMIT + 1
    if permit_state == "active":
        # Active since grant, so leaving active stamps the grant tick.
        assert _permit(rt).state == "pending"
        assert _permit(rt).activated_at_tick == GRANT_TICK
        assert record.effects == (
            SUSPEND_FIRED,
            "suspended 'TimedAuth' (to 'Operator')",
            "  pended permit 'timedPermit' held by 'Operator'",
        )
        assert [(e.from_state, e.to_state) for e in _permit_events(record)] == [
            ("active", "pending")]
        return
    assert _permit(rt).state == permit_state
    assert _permit(rt).activated_at_tick is None
    assert record.effects == (
        SUSPEND_FIRED,
        "not suspended 'TimedAuth' (to 'Operator'): nothing to suspend",
        f"  suspend 'timedPermit' had no effect: 'Operator' holds it {permit_state}",
    )
    assert _permit_events(record) == []


@pytest.mark.parametrize("permit_state", ALL_STATES)
def test_response_expires_in_each_state(permit_state):
    rt = _expiring_runtime(permit_state)
    _clock_to(rt, PAST_THE_LIMIT)

    record = rt.fire_violation_responses()

    assert record.outcome == "ok"
    assert record.fired_responses == ("ExpireOnBreach",)
    assert _embargo_states(rt) == []
    assert rt.current_state().tick == PAST_THE_LIMIT + 1
    if permit_state in ("active", "pending"):
        assert _permit(rt).state == "expired"
        # Active since grant, so leaving active stamps the grant tick; a
        # seeded pending permit was never active and keeps no stamp.
        assert _permit(rt).activated_at_tick == (
            GRANT_TICK if permit_state == "active" else None)
        assert record.effects == (
            EXPIRE_FIRED,
            "expired 'TimedAuth' (to 'Operator')",
            "  expired permit 'timedPermit' held by 'Operator'",
        )
        assert [(e.event, e.from_state, e.to_state, e.cause, e.cause_ref)
                for e in _permit_events(record)] == [
            ("expired", permit_state, "expired", "response", "ExpireOnBreach")]
        return
    assert _permit(rt).state == permit_state
    assert _permit(rt).activated_at_tick is None
    assert record.effects == (
        EXPIRE_FIRED,
        "not expired 'TimedAuth' (to 'Operator'): nothing to expire",
        f"  expire 'timedPermit' had no effect: 'Operator' holds it {permit_state}",
    )
    assert _permit_events(record) == []
