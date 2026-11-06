"""
2.5.0-1 — `expired` is final for that instance.

Only a new grant brings an expired permit back, and it starts a new clock. A
revoke or a reinstate skips an expired instance beside other holders; the direct
route and the response routes share that skip (_apply_revocation()). A clone or a
transfer of an expired instance carries its state and clock, so it is not a new
grant. The table cells for one holder are in tests/test_permit_transition_table.py.

Fixture: one permit name, with up to three holders seeded directly in states
only a run can produce. The Authorization names HolderA.
"""
from dataclasses import replace

import el_engine
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification PermitExpiredProbe

party Issuer
party HolderA
party HolderB

community ProbeCommunity
    description: "Holders of one permit name"
    {
        objective: "Exercise an expired permit"

        role operatorRole
            description: "Performs the acts"
            {
                action useTimed {
                    actor: operatorRole
                    requires_permit timedPermit
                }

                action cloneTimed {
                    actor: operatorRole
                    effect clone timedPermit
                }

                action transferTimed {
                    actor: operatorRole
                    effect transfer timedPermit from operatorRole to otherRole
                }

                action unrelatedAction {
                    actor: operatorRole
                }
            }

        role otherRole
            description: "Second holder"
            {
                action otherAction {
                    actor: otherRole
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
    to_agent: HolderA
    grants_permit: timedPermit
    revocable: true
    on_revocation: activate afterRevokeEmbargo
}
"""

_BREACH = """
burden breachedBurden {
    for_action: "unrelatedAction"
    state: active
    deadline: "5 minutes"
}
"""

_REVOKING_RESPONSE = _BREACH + """
violation_response RevokeOnBreach {
    on_violation_of: breachedBurden
    obligates: Issuer
    response_kind: remediate
    revokes: TimedAuth
}
"""

_GRANTING_RESPONSE = _BREACH + """
violation_response GrantOnBreach {
    on_violation_of: breachedBurden
    obligates: HolderA
    response_kind: remediate
    creates_burden: timedPermit
}
"""

GRANT_TICK = 3
NOW = 20
ELAPSED = "required permit 'timedPermit' time has elapsed for actor"
NOT_HELD = "required permit 'timedPermit' not held by actor"
NOTE_A = "revoke 'timedPermit' had no effect: 'HolderA' holds it expired"
NOTE_B = "revoke 'timedPermit' had no effect: 'HolderB' holds it expired"


def _runtime(*instances, embargo=None, extra="") -> Runtime:
    """Each instance is (holder, state, activated_at_tick), granted at
    GRANT_TICK. The clock stands at NOW. embargo seeds HolderA's embargo in that
    state. With extra, HolderB's breachedBurden is already violated, so firing
    does not depend on a sweep."""
    result = parse_string(_PROBE + extra, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "HolderA", role_name="operatorRole")
    state = enroll(state, "HolderB", role_name="otherRole")
    state = enroll(state, "Issuer").with_tick(GRANT_TICK)
    for holder, permit_state, stamp in instances:
        token = token_from_spec(spec, "timedPermit", holder, GRANT_TICK)
        state = grant_token(state, replace(token, state=permit_state, activated_at_tick=stamp))
    if embargo:
        token = token_from_spec(spec, "afterRevokeEmbargo", "HolderA", GRANT_TICK)
        state = grant_token(state, replace(token, state=embargo))
    if extra:
        token = token_from_spec(spec, "breachedBurden", "HolderB", GRANT_TICK)
        state = grant_token(state, replace(token, state="violated"))
    return Runtime(state.with_tick(NOW), spec)


def _permits(rt):
    """(holder, state, grant tick, stamp), sorted, for every instance."""
    return sorted(
        (t.holder, t.state, t.granted_at_tick, t.activated_at_tick)
        for t in rt.current_state().tokens
        if t.token_name == "timedPermit"
    )


def _embargoes(rt):
    return [(t.holder, t.state) for t in rt.current_state().tokens
            if t.token_name == "afterRevokeEmbargo"]


def _permit_events(record):
    return [(e.event, e.holder) for e in record.token_events if e.token_name == "timedPermit"]


# ── Revoke and reinstate with several holders ────────────────────────────────

def test_revoke_skips_an_expired_holder_and_revokes_the_other():
    rt = _runtime(("HolderA", "expired", None), ("HolderB", "active", None))

    record = rt.revoke_authorization("TimedAuth")

    assert record.outcome == "ok"
    assert _permits(rt) == [("HolderA", "expired", GRANT_TICK, None),
                            ("HolderB", "superseded", GRANT_TICK, GRANT_TICK)]
    # A new embargo goes to the first holder not expired.
    assert _embargoes(rt) == [("HolderB", "active")]
    assert record.effects == ("superseded permit 'timedPermit'", NOTE_A,
                              "activated embargo 'afterRevokeEmbargo'")
    assert _permit_events(record) == [("superseded", "HolderB")]
    assert rt.current_state().tick == NOW + 1

    # An embargo that already exists keeps its holder.
    rt = _runtime(("HolderA", "expired", None), ("HolderB", "active", None), embargo="lifted")
    rt.revoke_authorization("TimedAuth")
    assert _embargoes(rt) == [("HolderA", "active")]

    # With every holder expired there is no one left to revoke: one line each,
    # and nothing moves.
    rt = _runtime(("HolderA", "expired", None), ("HolderB", "expired", None), embargo="lifted")
    record = rt.revoke_authorization("TimedAuth")
    assert record.outcome == "ok"
    assert record.effects == (NOTE_A, NOTE_B)
    assert record.token_events == ()
    assert _embargoes(rt) == [("HolderA", "lifted")]
    assert rt.current_state().tick == NOW


def test_reinstate_skips_an_expired_holder_and_acts_on_the_other():
    rt = _runtime(("HolderA", "expired", None), ("HolderB", "superseded", 5), embargo="active")

    record = rt.reinstate_authorization("TimedAuth")

    assert record.outcome == "ok"
    assert _permits(rt) == [("HolderA", "expired", GRANT_TICK, None),
                            ("HolderB", "active", GRANT_TICK, 5)]
    # No note line: it would read as a real reinstate where nothing changed.
    assert record.effects == ("activated permit 'timedPermit'",
                              "lifted embargo 'afterRevokeEmbargo'")
    assert _embargoes(rt) == [("HolderA", "lifted")]
    assert rt.current_state().tick == NOW + 1

    # The first instance not expired decides. Active, so nothing moves, and a
    # superseded instance after it stays superseded; the embargo is still lifted.
    rt = _runtime(("HolderA", "expired", None), ("HolderB", "active", None),
                  ("Issuer", "superseded", 5), embargo="active")
    record = rt.reinstate_authorization("TimedAuth")
    assert record.outcome == "ok"
    assert _permits(rt) == [("HolderA", "expired", GRANT_TICK, None),
                            ("HolderB", "active", GRANT_TICK, None),
                            ("Issuer", "superseded", GRANT_TICK, 5)]
    assert record.effects == ("lifted embargo 'afterRevokeEmbargo'",)
    assert _embargoes(rt) == [("HolderA", "lifted")]


def test_response_revoke_skips_an_expired_holder():
    # A response's revoke ignores time: B is active past its limit and is
    # revoked; A is expired and stays so. The skip tests the state, not use.
    rt = _runtime(("HolderA", "expired", None), ("HolderB", "active", None),
                  extra=_REVOKING_RESPONSE)

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("RevokeOnBreach",)
    assert "revoked 'TimedAuth' (to 'HolderA')" in record.effects
    assert f"  {NOTE_A}" in record.effects
    assert _permits(rt) == [("HolderA", "expired", GRANT_TICK, None),
                            ("HolderB", "superseded", GRANT_TICK, GRANT_TICK)]
    assert _embargoes(rt) == [("HolderB", "active")]
    assert _permit_events(record) == [("superseded", "HolderB")]


# ── A new grant starts a new clock ───────────────────────────────────────────

def test_grant_token_beside_an_expired_instance_starts_a_new_clock():
    rt = _runtime(("HolderA", "expired", None))
    new = token_from_spec(rt._spec, "timedPermit", "HolderA", NOW)
    rt._state = grant_token(rt.current_state(), new)

    assert rt.advance("useTimed", "HolderA").outcome == "ok"

    assert rt.advance_clock(NOW + 5 - rt.current_state().tick).outcome == "ok"
    record = rt.advance("useTimed", "HolderA")
    assert record.outcome == "blocked"
    assert record.reason == ELAPSED

    rt.check_live_violations()
    assert _permits(rt) == [("HolderA", "expired", GRANT_TICK, None),
                            ("HolderA", "expired", NOW, NOW)]


def test_response_creates_burden_beside_an_expired_instance_starts_a_new_clock():
    rt = _runtime(("HolderA", "expired", None), extra=_GRANTING_RESPONSE)

    record = rt.fire_violation_responses()

    assert "fired 'GrantOnBreach': granted 'timedPermit' to 'HolderA'" in record.effects
    assert _permits(rt) == [("HolderA", "active", NOW, None),
                            ("HolderA", "expired", GRANT_TICK, None)]
    assert rt.advance("useTimed", "HolderA").outcome == "ok"
    assert rt.advance_clock(NOW + 5 - rt.current_state().tick).outcome == "ok"
    record = rt.advance("useTimed", "HolderA")
    assert record.outcome == "blocked"
    assert record.reason == ELAPSED


# ── A clone or a transfer is not a new grant ─────────────────────────────────

def test_clone_of_an_expired_instance_carries_state_and_clock():
    rt = _runtime(("HolderB", "expired", 7))

    record = rt.advance("cloneTimed", "HolderA")

    assert record.outcome == "ok"
    assert _permits(rt) == [("HolderA", "expired", GRANT_TICK, 7),
                            ("HolderB", "expired", GRANT_TICK, 7)]
    assert [(e.event, e.holder, e.to_state) for e in record.token_events] == [
        ("granted", "HolderA", "expired")]
    refused = rt.advance("useTimed", "HolderA")
    assert refused.outcome == "blocked"
    assert refused.reason == NOT_HELD


def test_transfer_of_an_expired_instance_carries_state_and_clock():
    rt = _runtime(("HolderA", "expired", 7))

    record = rt.advance("transferTimed", "HolderA")

    assert record.outcome == "ok"
    assert _permits(rt) == [("HolderB", "expired", GRANT_TICK, 7)]
    assert _permit_events(record) == [("granted", "HolderB"), ("removed", "HolderA")]
    assert not any(el_engine._permit_usable(t, rt.current_state().tick)
                   for t in rt.current_state().tokens if t.token_name == "timedPermit")
