"""
2.5.0-2 — a violation response's `suspends:` and `expires:` clauses at run
time.

When a response fires, each `suspends: <Authorization>` line moves the permit
that Authorization grants from active to pending, and each `expires:
<Authorization>` line moves it from active or pending to expired, for the
Authorization's to_agent or for every actor filling its to_role. Another
holder's instance of the same permit is never touched. An instance in any
other state, an expired one included, stays as it is and gets a "had no
effect" line. The permit's activation stamp is kept, so its time limit keeps
running while it is suspended and a restore does not restart it; a pending
permit that was never active keeps no stamp when it expires. Both clauses run
after any revocation the response makes, every `suspends:` line before any
`expires:` line; they need no revocable Authorization, touch no embargo, and
act during a strict freeze. The tick advances once per firing call, as before.

The table cells for one holder in each state are in
tests/test_permit_transition_table.py.

Fixtures:
- the one-holder probe of tests/test_permit_transition_table.py: Operator
  holds timedPermit (5-minute limit) granted at tick 3 under TimedAuth, whose
  authority Issuer is the response's obligates;
- the two-holder probe of tests/test_permit_expired_final.py: TimedAuth is
  granted to HolderA, and HolderB may hold the same permit;
- a probe here whose Authorization is granted to a role with two fillers.
The burden a response answers is seeded already violated, so firing does not
depend on a sweep.
"""
import contextlib
import importlib
import io
from dataclasses import replace

from el_engine import (
    ViolationRecord,
    enroll,
    fire_violation_responses,
    grant_token,
    initial_state,
    token_from_spec,
)
from el_kripke import build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime
from test_permit_expired_final import _BREACH, _PROBE as _TWO_HOLDER_PROBE
from test_permit_transition_table import (
    _PROBE as _ONE_HOLDER_PROBE,
    _EXPIRING_RESPONSE,
    _SUSPENDING_RESPONSE,
    ELAPSED,
    EXPIRE_FIRED,
    GRANT_TICK,
    PAST_THE_LIMIT,
    SUSPEND_FIRED,
)


_TWO_HOLDER_RESPONSE = _BREACH + """
violation_response SuspendOnBreach {
    on_violation_of: breachedBurden
    obligates: Issuer
    response_kind: remediate
    suspends: TimedAuth
}
"""

_ROLE_PROBE = """
enterprise specification RoleSuspendProbe

party Issuer
party HolderA
party HolderB
party Outsider

community ProbeCommunity
    description: "Two fillers of one role share a permit granted to the role"
    {
        objective: "Suspend a permit granted to a role"

        role operatorRole
            description: "Uses the permit"
            {
                action useTimed {
                    actor: operatorRole
                    requires_permit timedPermit
                }

                action unrelatedAction {
                    actor: operatorRole
                }
            }

        role otherRole
            description: "Holds the permit without filling the role"
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

authorization RoleAuth {
    authority: Issuer
    to_role: operatorRole
    grants_permit: timedPermit
    revocable: true
    on_revocation: activate afterRevokeEmbargo
}

burden breachedBurden {
    for_action: "unrelatedAction"
    state: active
    deadline: "5 minutes"
}

violation_response SuspendOnBreach {
    on_violation_of: breachedBurden
    obligates: Issuer
    response_kind: remediate
    suspends: RoleAuth
}
"""

_EXPIRING_TWO_HOLDER_RESPONSE = _TWO_HOLDER_RESPONSE.replace(
    "violation_response SuspendOnBreach", "violation_response ExpireOnBreach"
).replace("suspends: TimedAuth", "expires: TimedAuth")

_EXPIRING_ROLE_PROBE = _ROLE_PROBE.replace(
    "violation_response SuspendOnBreach", "violation_response ExpireOnBreach"
).replace("suspends: RoleAuth", "expires: RoleAuth")

_ONE_HOLDER = (("Operator", "operatorRole"), ("Issuer", None))
_TWO_HOLDERS = (("HolderA", "operatorRole"), ("HolderB", "otherRole"), ("Issuer", None))


def _runtime(src, actors, permits, violated, validate=True) -> Runtime:
    """actors: (name, role or None), enrolled in order. permits: (holder,
    state) instances of timedPermit, granted at GRANT_TICK. violated: holders
    of breachedBurden, seeded violated. The clock stands at GRANT_TICK."""
    result = parse_string(src, validate=validate)
    if validate:
        assert result.ok, result.errors
    spec = result.model
    state = initial_state()
    for name, role in actors:
        state = enroll(state, name, role_name=role)
    state = state.with_tick(GRANT_TICK)
    for holder, permit_state in permits:
        token = token_from_spec(spec, "timedPermit", holder, GRANT_TICK)
        state = grant_token(state, replace(token, state=permit_state))
    for holder in violated:
        burden = token_from_spec(spec, "breachedBurden", holder, GRANT_TICK)
        state = grant_token(state, replace(burden, state="violated"))
    return Runtime(state, spec)


def _one_holder(permit_state="active", response=_SUSPENDING_RESPONSE, extra="",
                validate=True) -> Runtime:
    return _runtime(_ONE_HOLDER_PROBE + response + extra, _ONE_HOLDER,
                    [("Operator", permit_state)], ["Operator"], validate)


def _permits(rt):
    """(holder, state, stamp) for every instance of timedPermit, in order."""
    return [(t.holder, t.state, t.activated_at_tick)
            for t in rt.current_state().tokens if t.token_name == "timedPermit"]


def _permit_events(record):
    return [(e.event, e.holder, e.from_state, e.to_state)
            for e in record.token_events if e.token_name == "timedPermit"]


def _clock_to(rt, tick):
    ticks = tick - rt.current_state().tick
    if ticks:
        assert rt.advance_clock(ticks).outcome == "ok"
    assert rt.current_state().tick == tick


# ── Which instances a suspension reaches ─────────────────────────────────────

def test_to_agent_leaves_another_holders_instance_alone():
    rt = _runtime(_TWO_HOLDER_PROBE + _TWO_HOLDER_RESPONSE, _TWO_HOLDERS,
                  [("HolderA", "active"), ("HolderB", "active")], ["HolderB"])

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("HolderA", "pending", GRANT_TICK), ("HolderB", "active", None)]
    assert record.effects == (
        "fired 'SuspendOnBreach' (remediate) on violation of 'breachedBurden' by 'HolderB'",
        "suspended 'TimedAuth' (to 'HolderA')",
        "  pended permit 'timedPermit' held by 'HolderA'",
    )
    assert _permit_events(record) == [("pending", "HolderA", "active", "pending")]


def test_to_role_suspends_every_fillers_instance():
    actors = (("HolderA", "operatorRole"), ("HolderB", "operatorRole"),
              ("Outsider", "otherRole"), ("Issuer", None))
    rt = _runtime(_ROLE_PROBE, actors,
                  [("HolderA", "active"), ("Outsider", "active"), ("HolderB", "active")],
                  ["Issuer"])

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("HolderA", "pending", GRANT_TICK),
                            ("Outsider", "active", None),
                            ("HolderB", "pending", GRANT_TICK)]
    assert record.effects[1:] == (
        "suspended 'RoleAuth' (to role 'operatorRole')",
        "  pended permit 'timedPermit' held by 'HolderA'",
        "  pended permit 'timedPermit' held by 'HolderB'",
    )


def test_to_role_with_no_filler_changes_nothing():
    actors = (("HolderA", None), ("HolderB", "otherRole"), ("Issuer", None))
    rt = _runtime(_ROLE_PROBE, actors,
                  [("HolderA", "active"), ("HolderB", "active")], ["Issuer"])

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("SuspendOnBreach",)
    assert _permits(rt) == [("HolderA", "active", None), ("HolderB", "active", None)]
    assert record.effects[1:] == (
        "not suspended 'RoleAuth': no actor fills role 'operatorRole'",)
    assert _permit_events(record) == []


def test_target_with_no_instance_changes_nothing():
    rt = _runtime(_TWO_HOLDER_PROBE + _TWO_HOLDER_RESPONSE, _TWO_HOLDERS,
                  [("HolderB", "active")], ["HolderB"])

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("HolderB", "active", None)]
    assert record.effects[1:] == (
        "not suspended 'TimedAuth' (to 'HolderA'): no instance of permit 'timedPermit'",)
    assert _permit_events(record) == []


def test_authority_other_than_obligates_is_refused_at_run_time():
    # The validator rejects this specification; the engine guards it too.
    response = _SUSPENDING_RESPONSE.replace("obligates: Issuer", "obligates: Operator")
    with contextlib.redirect_stdout(io.StringIO()):
        checked = parse_string(_ONE_HOLDER_PROBE + response, validate=True)
    assert any(e.startswith("[response-permit-authority]") for e in checked.errors)
    rt = _one_holder(response=response, validate=False)

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("SuspendOnBreach",)
    assert _permits(rt) == [("Operator", "active", None)]
    assert record.effects == (
        "fired 'SuspendOnBreach' (remediate) on violation of 'breachedBurden' "
        "by 'Operator'",
        "not suspended 'TimedAuth': authority is 'Issuer', not 'Operator'",
    )


def test_identical_instances_both_move():
    rt = _runtime(_ONE_HOLDER_PROBE + _SUSPENDING_RESPONSE, _ONE_HOLDER,
                  [("Operator", "active"), ("Operator", "active")], ["Operator"])

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("Operator", "pending", GRANT_TICK)] * 2
    assert record.effects[1:] == (
        "suspended 'TimedAuth' (to 'Operator')",
        "  pended permit 'timedPermit' held by 'Operator'",
        "  pended permit 'timedPermit' held by 'Operator'",
    )
    assert _permit_events(record) == [("pending", "Operator", "active", "pending")] * 2


# ── Ledger and tick ──────────────────────────────────────────────────────────

def test_suspension_event_names_the_response():
    rt = _one_holder()

    record = rt.fire_violation_responses()

    [event] = [e for e in record.token_events if e.token_name == "timedPermit"]
    assert (event.event, event.token_kind, event.holder) == ("pending", "permit", "Operator")
    assert (event.from_state, event.to_state) == ("active", "pending")
    assert event.by == "system"
    assert (event.cause, event.cause_ref) == ("response", "SuspendOnBreach")
    assert event.tick == GRANT_TICK


def test_tick_advances_once_per_firing_call_even_with_no_change():
    rt = _one_holder("pending")

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("SuspendOnBreach",)
    assert record.effects[1:] == (
        "not suspended 'TimedAuth' (to 'Operator'): nothing to suspend",
        "  suspend 'timedPermit' had no effect: 'Operator' holds it pending",
    )
    assert record.token_events == ()
    assert rt.current_state().tick == GRANT_TICK + 1

    again = rt.fire_violation_responses()

    assert again.fired_responses == ()
    assert again.effects == ()
    assert rt.current_state().tick == GRANT_TICK + 1


# ── The time limit keeps running while suspended ─────────────────────────────

def test_restore_by_activate_effect_keeps_the_stamp_and_the_sweep_still_expires():
    rt = _one_holder()
    rt.fire_violation_responses()                       # tick 3 -> 4
    assert _permits(rt) == [("Operator", "pending", GRANT_TICK)]

    assert rt.advance("activateTimed", "Operator").outcome == "ok"     # -> 5

    assert _permits(rt) == [("Operator", "active", GRANT_TICK)]
    assert rt.advance("useTimed", "Operator").outcome == "ok"          # -> 6
    assert rt.advance("pendTimed", "Operator").outcome == "ok"         # -> 7
    assert _permits(rt) == [("Operator", "pending", GRANT_TICK)]
    # Four steps from the grant: not yet up.
    assert rt.check_live_violations().token_events == ()

    # Five steps from the grant, not from the restore.
    _clock_to(rt, GRANT_TICK + 5)
    record = rt.check_live_violations()

    assert _permits(rt) == [("Operator", "expired", GRANT_TICK)]
    assert [(e.event, e.from_state, e.cause, e.cause_ref) for e in record.token_events] == [
        ("expired", "pending", "deadline", None)]


def test_elapsed_unswept_active_permit_is_suspended_then_swept():
    rt = _one_holder()
    _clock_to(rt, PAST_THE_LIMIT)
    assert rt.advance("useTimed", "Operator").reason == ELAPSED
    assert _permits(rt) == [("Operator", "active", None)]

    rt.fire_violation_responses()

    assert _permits(rt) == [("Operator", "pending", GRANT_TICK)]
    record = rt.check_live_violations()
    assert _permits(rt) == [("Operator", "expired", GRANT_TICK)]
    assert [(e.event, e.cause) for e in record.token_events] == [("expired", "deadline")]


def test_reinstate_after_a_suspension_restores_the_permit_and_keeps_the_stamp():
    rt = _one_holder()
    rt.fire_violation_responses()

    record = rt.reinstate_authorization("TimedAuth")

    assert record.outcome == "ok"
    assert record.effects == ("activated permit 'timedPermit'",)
    assert _permits(rt) == [("Operator", "active", GRANT_TICK)]


# ── Several lines, terminate, several occurrences ────────────────────────────

def test_suspends_written_twice_acts_once():
    response = _SUSPENDING_RESPONSE.replace(
        "suspends: TimedAuth", "suspends: TimedAuth\n    suspends: TimedAuth")
    rt = _one_holder(response=response)

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("Operator", "pending", GRANT_TICK)]
    assert record.effects == (
        SUSPEND_FIRED,
        "suspended 'TimedAuth' (to 'Operator')",
        "  pended permit 'timedPermit' held by 'Operator'",
        "not suspended 'TimedAuth' (to 'Operator'): nothing to suspend",
        "  suspend 'timedPermit' had no effect: 'Operator' holds it pending",
    )
    assert len(_permit_events(record)) == 1


def test_terminate_still_revokes_its_chain_and_the_suspension_finds_it_revoked():
    # Operator, the violator, holds TimedAuth, so terminate revokes it first.
    response = _SUSPENDING_RESPONSE.replace("response_kind: remediate",
                                            "response_kind: terminate")
    rt = _one_holder(response=response)

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("Operator", "superseded", GRANT_TICK)]
    assert record.effects == (
        "fired 'SuspendOnBreach' (terminate) on violation of 'breachedBurden' "
        "by 'Operator'",
        "revoked 'TimedAuth' (to 'Operator')",
        "  superseded permit 'timedPermit'",
        "  activated embargo 'afterRevokeEmbargo'",
        "not suspended 'TimedAuth' (to 'Operator'): nothing to suspend",
        "  suspend 'timedPermit' had no effect: 'Operator' holds it superseded",
    )
    assert [(e.cause, e.cause_ref) for e in record.token_events
            if e.token_name == "timedPermit"] == [("revocation", "TimedAuth")]


def test_terminate_whose_chain_misses_the_target_still_suspends():
    response = _TWO_HOLDER_RESPONSE.replace("response_kind: remediate",
                                            "response_kind: terminate")
    rt = _runtime(_TWO_HOLDER_PROBE + response, _TWO_HOLDERS,
                  [("HolderA", "active")], ["HolderB"])

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("HolderA", "pending", GRANT_TICK)]
    assert record.effects == (
        "fired 'SuspendOnBreach' (terminate) on violation of 'breachedBurden' by 'HolderB'",
        "suspended 'TimedAuth' (to 'HolderA')",
        "  pended permit 'timedPermit' held by 'HolderA'",
    )
    assert not any(t.token_name == "afterRevokeEmbargo" for t in rt.current_state().tokens)


def test_two_occurrences_in_one_call_act_once_and_advance_the_tick_once():
    rt = _runtime(_TWO_HOLDER_PROBE + _TWO_HOLDER_RESPONSE, _TWO_HOLDERS,
                  [("HolderA", "active")], ["HolderA", "HolderB"])

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("SuspendOnBreach", "SuspendOnBreach")
    assert _permits(rt) == [("HolderA", "pending", GRANT_TICK)]
    assert record.effects == (
        "fired 'SuspendOnBreach' (remediate) on violation of 'breachedBurden' by 'HolderA'",
        "suspended 'TimedAuth' (to 'HolderA')",
        "  pended permit 'timedPermit' held by 'HolderA'",
        "fired 'SuspendOnBreach' (remediate) on violation of 'breachedBurden' by 'HolderB'",
        "not suspended 'TimedAuth' (to 'HolderA'): nothing to suspend",
        "  suspend 'timedPermit' had no effect: 'HolderA' holds it pending",
    )
    assert len(_permit_events(record)) == 1
    assert rt.current_state().tick == GRANT_TICK + 1


# ── Violation records ────────────────────────────────────────────────────────

_RECORD_RESPONSE = """
violation_response SuspendOnUse {
    on_violation_of: timedPermit
    obligates: Issuer
    response_kind: remediate
    suspends: TimedAuth
    FLAG
}
"""


def _record(source):
    return ViolationRecord(rule="timedPermit", kind="permit_requirement", violator="Operator",
                           behaviour="useTimed", declared_by="system",
                           occurred_at=GRANT_TICK, declared_at=GRANT_TICK, source=source)


def _fire_on_record(source, flag):
    response = _RECORD_RESPONSE.replace(
        "FLAG", "also_on_refused_attempts: true" if flag else "")
    rt = _runtime(_ONE_HOLDER_PROBE + response, _ONE_HOLDER, [("Operator", "active")], [])
    state = rt.current_state().with_violation_records((_record(source),))
    return fire_violation_responses(state, rt._spec)


def test_fires_on_a_declared_record_and_on_a_refused_attempt_only_with_the_flag():
    for source, flag, fires in (("declared", False, True),
                                ("refused_attempt", False, False),
                                ("refused_attempt", True, True)):
        new_state, record = _fire_on_record(source, flag)
        permit = next(t for t in new_state.tokens if t.token_name == "timedPermit")
        if fires:
            assert record.fired_responses == ("SuspendOnUse",)
            assert permit.state == "pending"
            assert record.effects == (
                "fired 'SuspendOnUse' (remediate) on violation of permit requirement "
                "'timedPermit' by 'Operator' in 'useTimed' at step 3",
                "suspended 'TimedAuth' (to 'Operator')",
                "  pended permit 'timedPermit' held by 'Operator'",
            )
        else:
            assert record.fired_responses == ()
            assert permit.state == "active"


# ── Strict freeze ────────────────────────────────────────────────────────────

_STRICT_DUTY = """
burden strictDuty {
    for_action: "unrelatedAction"
    state: active
    discharge_mode: strict
}
"""


def test_suspends_during_a_strict_freeze():
    rt = _one_holder(extra=_STRICT_DUTY)
    duty = token_from_spec(rt._spec, "strictDuty", "Operator", GRANT_TICK)
    rt._state = grant_token(rt.current_state(), duty)
    assert rt.revoke_authorization("TimedAuth").outcome == "blocked"

    record = rt.fire_violation_responses()

    assert record.outcome == "ok"
    assert _permits(rt) == [("Operator", "pending", GRANT_TICK)]
    assert "suspended 'TimedAuth' (to 'Operator')" in record.effects


# ── Expiry ───────────────────────────────────────────────────────────────────

_ROLE_ACTORS = (("HolderA", "operatorRole"), ("HolderB", "operatorRole"),
                ("Outsider", "otherRole"), ("Issuer", None))


def test_expires_to_agent_leaves_another_holders_instance_alone():
    rt = _runtime(_TWO_HOLDER_PROBE + _EXPIRING_TWO_HOLDER_RESPONSE, _TWO_HOLDERS,
                  [("HolderA", "active"), ("HolderB", "active")], ["HolderB"])

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("HolderA", "expired", GRANT_TICK), ("HolderB", "active", None)]
    assert record.effects == (
        "fired 'ExpireOnBreach' (remediate) on violation of 'breachedBurden' by 'HolderB'",
        "expired 'TimedAuth' (to 'HolderA')",
        "  expired permit 'timedPermit' held by 'HolderA'",
    )
    assert _permit_events(record) == [("expired", "HolderA", "active", "expired")]


def test_expires_to_role_expires_every_fillers_instance():
    rt = _runtime(_EXPIRING_ROLE_PROBE, _ROLE_ACTORS,
                  [("HolderA", "active"), ("Outsider", "active"), ("HolderB", "active")],
                  ["Issuer"])

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("HolderA", "expired", GRANT_TICK),
                            ("Outsider", "active", None),
                            ("HolderB", "expired", GRANT_TICK)]
    assert record.effects[1:] == (
        "expired 'RoleAuth' (to role 'operatorRole')",
        "  expired permit 'timedPermit' held by 'HolderA'",
        "  expired permit 'timedPermit' held by 'HolderB'",
    )


def test_expires_to_role_with_no_filler_changes_nothing():
    actors = (("HolderA", None), ("HolderB", "otherRole"), ("Issuer", None))
    rt = _runtime(_EXPIRING_ROLE_PROBE, actors,
                  [("HolderA", "active"), ("HolderB", "active")], ["Issuer"])

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("ExpireOnBreach",)
    assert _permits(rt) == [("HolderA", "active", None), ("HolderB", "active", None)]
    assert record.effects[1:] == (
        "not expired 'RoleAuth': no actor fills role 'operatorRole'",)
    assert _permit_events(record) == []


def test_expires_with_authority_other_than_obligates_is_refused_at_run_time():
    # The validator rejects this specification; the engine guards it too.
    response = _EXPIRING_RESPONSE.replace("obligates: Issuer", "obligates: Operator")
    with contextlib.redirect_stdout(io.StringIO()):
        checked = parse_string(_ONE_HOLDER_PROBE + response, validate=True)
    assert any(e.startswith("[response-permit-authority]") and "expires" in e
               for e in checked.errors)
    rt = _one_holder(response=response, validate=False)

    record = rt.fire_violation_responses()

    assert record.fired_responses == ("ExpireOnBreach",)
    assert _permits(rt) == [("Operator", "active", None)]
    assert record.effects == (
        EXPIRE_FIRED,
        "not expired 'TimedAuth': authority is 'Issuer', not 'Operator'",
    )
    assert _permit_events(record) == []


def test_expiry_event_names_the_response():
    for permit_state in ("active", "pending"):
        rt = _one_holder(permit_state, response=_EXPIRING_RESPONSE)

        record = rt.fire_violation_responses()

        [event] = [e for e in record.token_events if e.token_name == "timedPermit"]
        assert (event.event, event.token_kind, event.holder) == ("expired", "permit", "Operator")
        assert (event.from_state, event.to_state) == (permit_state, "expired")
        assert event.by == "system"
        assert (event.cause, event.cause_ref) == ("response", "ExpireOnBreach")
        assert event.tick == GRANT_TICK


def test_elapsed_unswept_active_permit_is_expired_and_the_sweep_finds_nothing():
    rt = _one_holder(response=_EXPIRING_RESPONSE)
    _clock_to(rt, PAST_THE_LIMIT)
    assert rt.advance("useTimed", "Operator").reason == ELAPSED
    assert _permits(rt) == [("Operator", "active", None)]

    rt.fire_violation_responses()

    assert _permits(rt) == [("Operator", "expired", GRANT_TICK)]
    tick = rt.current_state().tick
    record = rt.check_live_violations()
    assert record.token_events == ()
    assert rt.current_state().tick == tick
    assert _permits(rt) == [("Operator", "expired", GRANT_TICK)]


def test_reinstate_after_expiry_is_refused():
    rt = _one_holder(response=_EXPIRING_RESPONSE)
    rt.fire_violation_responses()
    tick = rt.current_state().tick

    record = rt.reinstate_authorization("TimedAuth")

    assert record.outcome == "blocked"
    assert record.reason == "permit 'timedPermit' has expired; only a new grant restores it"
    assert record.effects == ()
    assert record.token_events == ()
    assert rt.current_state().tick == tick
    assert _permits(rt) == [("Operator", "expired", GRANT_TICK)]


def test_direct_revoke_after_expiry_has_no_effect():
    rt = _one_holder(response=_EXPIRING_RESPONSE)
    rt.fire_violation_responses()
    tick = rt.current_state().tick

    record = rt.revoke_authorization("TimedAuth")

    assert record.outcome == "ok"
    assert record.effects == (
        "revoke 'timedPermit' had no effect: 'Operator' holds it expired",)
    assert record.token_events == ()
    assert rt.current_state().tick == tick
    assert _permits(rt) == [("Operator", "expired", GRANT_TICK)]
    assert not any(t.token_name == "afterRevokeEmbargo" for t in rt.current_state().tokens)


def test_suspends_then_expires_in_one_response_ledgers_one_expiry():
    response = _EXPIRING_RESPONSE.replace(
        "expires: TimedAuth", "suspends: TimedAuth\n    expires: TimedAuth")
    rt = _one_holder(response=response)

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("Operator", "expired", GRANT_TICK)]
    assert record.effects == (
        EXPIRE_FIRED,
        "suspended 'TimedAuth' (to 'Operator')",
        "  pended permit 'timedPermit' held by 'Operator'",
        "expired 'TimedAuth' (to 'Operator')",
        "  expired permit 'timedPermit' held by 'Operator'",
    )
    # Only the change across the whole call is ledgered.
    assert _permit_events(record) == [("expired", "Operator", "active", "expired")]


def test_revokes_suspends_and_expires_in_one_response():
    response = _EXPIRING_RESPONSE.replace(
        "expires: TimedAuth",
        "revokes: TimedAuth\n    suspends: TimedAuth\n    expires: TimedAuth")
    rt = _one_holder(response=response)

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("Operator", "superseded", GRANT_TICK)]
    assert any(t.token_name == "afterRevokeEmbargo" and t.state == "active"
               for t in rt.current_state().tokens)
    assert record.effects == (
        EXPIRE_FIRED,
        "revoked 'TimedAuth' (to 'Operator')",
        "  superseded permit 'timedPermit'",
        "  activated embargo 'afterRevokeEmbargo'",
        "not suspended 'TimedAuth' (to 'Operator'): nothing to suspend",
        "  suspend 'timedPermit' had no effect: 'Operator' holds it superseded",
        "not expired 'TimedAuth' (to 'Operator'): nothing to expire",
        "  expire 'timedPermit' had no effect: 'Operator' holds it superseded",
    )


def test_expires_written_twice_acts_once():
    response = _EXPIRING_RESPONSE.replace(
        "expires: TimedAuth", "expires: TimedAuth\n    expires: TimedAuth")
    rt = _one_holder(response=response)

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("Operator", "expired", GRANT_TICK)]
    assert record.effects == (
        EXPIRE_FIRED,
        "expired 'TimedAuth' (to 'Operator')",
        "  expired permit 'timedPermit' held by 'Operator'",
        "not expired 'TimedAuth' (to 'Operator'): nothing to expire",
        "  expire 'timedPermit' had no effect: 'Operator' holds it expired",
    )
    assert len(_permit_events(record)) == 1


def test_terminate_revokes_its_chain_before_the_expiry_finds_it_revoked():
    # Operator, the violator, holds TimedAuth, so terminate revokes it first.
    response = _EXPIRING_RESPONSE.replace("response_kind: remediate",
                                          "response_kind: terminate")
    rt = _one_holder(response=response)

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("Operator", "superseded", GRANT_TICK)]
    assert record.effects == (
        "fired 'ExpireOnBreach' (terminate) on violation of 'breachedBurden' "
        "by 'Operator'",
        "revoked 'TimedAuth' (to 'Operator')",
        "  superseded permit 'timedPermit'",
        "  activated embargo 'afterRevokeEmbargo'",
        "not expired 'TimedAuth' (to 'Operator'): nothing to expire",
        "  expire 'timedPermit' had no effect: 'Operator' holds it superseded",
    )
    assert [(e.cause, e.cause_ref) for e in record.token_events
            if e.token_name == "timedPermit"] == [("revocation", "TimedAuth")]


def test_expires_to_role_with_one_filler_already_expired():
    rt = _runtime(_EXPIRING_ROLE_PROBE, _ROLE_ACTORS,
                  [("HolderA", "expired"), ("HolderB", "active")], ["Issuer"])

    record = rt.fire_violation_responses()

    assert _permits(rt) == [("HolderA", "expired", None),
                            ("HolderB", "expired", GRANT_TICK)]
    assert record.effects[1:] == (
        "expired 'RoleAuth' (to role 'operatorRole')",
        "  expire 'timedPermit' had no effect: 'HolderA' holds it expired",
        "  expired permit 'timedPermit' held by 'HolderB'",
    )
    assert _permit_events(record) == [("expired", "HolderB", "active", "expired")]


# ── Through the API, and the verifier ────────────────────────────────────────

def test_fire_violation_responses_endpoint_suspends_the_permit():
    # Same direct-call style as tests/test_fire_violation_responses_endpoint.py.
    import el_api
    importlib.reload(el_api)
    el_api._runtime = _one_holder()

    resp = el_api.fire_violation_responses_endpoint()

    assert resp.fired == ["SuspendOnBreach"]
    assert "suspended 'TimedAuth' (to 'Operator')" in resp.effects
    assert "  pended permit 'timedPermit' held by 'Operator'" in resp.effects
    assert [t["state"] for t in el_api.debug_tokens()
            if t["token_name"] == "timedPermit"] == ["pending"]


def _static_summary(src):
    # Compared as tests/test_policy_values_invisible_to_verifier.py compares
    # the hybrid model: world count, edge labels, AF/EF verdict per burden.
    result = parse_string(src, validate=True)
    assert result.ok, result.errors
    with contextlib.redirect_stdout(io.StringIO()):
        km = build_kripke_model(result.model)
    verdicts = {}
    for name in ("breachedBurden",):
        af, ef = km.check_obligation(name), km.check_permission(name)
        verdicts[name] = (af.satisfied, af.status, ef.satisfied)
    return len(km.worlds), sorted(set(km.labels.values())), verdicts


# A commitment gives breachedBurden a holder in the verifier's model, so it
# gets an AF/EF verdict; without one the model has no obligation to judge.
_COMMITMENT = """
commitment breachedCommitment {
    by: Operator
    obligation: "use the timed permit"
    creates_burden: breachedBurden
}
"""


def test_suspends_does_not_change_the_static_verifier_model():
    without = _SUSPENDING_RESPONSE.replace("    suspends: TimedAuth\n", "")
    assert "suspends" not in without

    with_clause = _static_summary(_ONE_HOLDER_PROBE + _SUSPENDING_RESPONSE + _COMMITMENT)
    without_clause = _static_summary(_ONE_HOLDER_PROBE + without + _COMMITMENT)

    # Not vacuous: the burden is pending in the model, AF is decided (no
    # "not triggered" or "not resolved" status) and EF finds a discharge.
    worlds, labels, verdicts = with_clause
    assert worlds > 2
    assert any(label.startswith("examine:breachedBurden") for label in labels)
    af_satisfied, af_status, ef_satisfied = verdicts["breachedBurden"]
    assert af_status is None and af_satisfied is False and ef_satisfied is True
    assert with_clause == without_clause
