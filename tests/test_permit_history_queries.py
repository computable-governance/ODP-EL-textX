"""
2.5.0-1 — the history queries and a permit's time limit.

Runtime.in_force_at() answers True for a permit only if the token events show
it active at the tick and it had not elapsed at that tick (_permit_elapsed()).
Runtime.token_states_at() stays the raw record of states, so an elapsed permit
still reads active there. The clock start and the deadline come from the
holder's current instance; when that is gone and the specification gives a
duration limit, the answer is unknown (None). Runtime.declare_breach() reads
in_force_at(), so its declarations of a permit follow the limit.

Fixture: as tests/test_permit_use_check.py. Operator performs the acts and holds
the permits, Colleague is the third party who prevents an act, Worker takes a
transfer and Watchdog declares. Tokens are granted at tick 3, so a clock that
starts at grant cannot be mistaken for one that starts at tick 0.
"""
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification PermitHistoryProbe

party Operator
party Colleague
party Worker
party Watchdog

community ProbeCommunity
    description: "Actions gated by permits with different time limits"
    {
        objective: "Exercise the history queries"

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

                action useOpen {
                    actor: operatorRole
                    requires_permit openPermit
                }

                action transferTimed {
                    actor: operatorRole
                    effect transfer timedPermit to workerRole
                }

                action transferOpen {
                    actor: operatorRole
                    effect transfer openPermit to workerRole
                }

                action suspendTimed {
                    actor: operatorRole
                    effect pend timedPermit
                }

                action restoreTimed {
                    actor: operatorRole
                    effect activate timedPermit
                }
            }

        role workerRole
            description: "Takes a transferred permit"
            {
                action useAsWorker {
                    actor: workerRole
                    requires_permit timedPermit
                }
            }

        role watchdogRole
            description: "Declares a breach of the timed permit"
            {
                action declareTimed {
                    actor: watchdogRole
                    requires_permit declarePermit
                    declares_violation_of timedPermit
                }
            }
    }

permit timedPermit {
    for_action: "useTimed"
    state: active
    deadline: "5 minutes"
}

permit datedPermit {
    for_action: "useDated"
    state: active
    deadline: "by 2026-05-20"
}

permit openPermit {
    for_action: "useOpen"
    state: active
}

permit declarePermit {
    for_action: "declareTimed"
    state: active
}
"""

GRANT_TICK = 3
LIMIT_REACHED = GRANT_TICK + 5
PAST_THE_LIMIT = 20


def _runtime(*grants) -> Runtime:
    """Each grant is (token name, holder)."""
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = enroll(state, "Colleague", role_name="operatorRole")
    state = enroll(state, "Worker", role_name="workerRole")
    state = enroll(state, "Watchdog", role_name="watchdogRole")
    state = state.with_tick(GRANT_TICK)
    for name, holder in grants:
        state = grant_token(state, token_from_spec(spec, name, holder, GRANT_TICK))
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


# ── The limit, against the raw record of states ──────────────────────────────

def test_in_force_at_applies_the_limit_and_token_states_at_stays_raw():
    rt = _runtime(("timedPermit", "Operator"))
    _clock_to(rt, PAST_THE_LIMIT)

    assert rt.in_force_at("timedPermit", "Operator", LIMIT_REACHED - 1) is True
    assert rt.in_force_at("timedPermit", "Operator", LIMIT_REACHED) is False
    assert rt.in_force_at("timedPermit", "Operator", PAST_THE_LIMIT) is False

    for tick in (LIMIT_REACHED - 1, LIMIT_REACHED, PAST_THE_LIMIT):
        assert rt.token_states_at("timedPermit", "Operator", tick) == ("active",)


# ── Limits that never elapse ─────────────────────────────────────────────────

def test_date_deadline_past_its_date_is_in_force():
    rt = _runtime(("datedPermit", "Operator"))
    _clock_to(rt, 100000)

    assert rt.in_force_at("datedPermit", "Operator", 100000) is True


def test_permit_with_no_deadline_is_in_force():
    rt = _runtime(("openPermit", "Operator"))
    _clock_to(rt, 100000)

    assert rt.in_force_at("openPermit", "Operator", 100000) is True


# ── A holder who transferred the permit away ─────────────────────────────────

def test_transferred_permit_is_unknown_only_when_the_spec_gives_a_duration():
    rt = _runtime(("timedPermit", "Operator"), ("openPermit", "Operator"))
    transfer_tick = rt.current_state().tick
    _act(rt, "transferTimed")
    open_transfer_tick = rt.current_state().tick
    _act(rt, "transferOpen")
    after = rt.current_state().tick

    # The fold still shows the instance active before the transfer.
    assert rt.token_states_at("timedPermit", "Operator", transfer_tick) == ("active",)
    assert rt.in_force_at("timedPermit", "Operator", transfer_tick) is None
    assert rt.in_force_at("openPermit", "Operator", open_transfer_tick) is True

    # After the transfer the old holder holds nothing, and the new holder's
    # instance carries the clock.
    assert rt.in_force_at("timedPermit", "Operator", after) is False
    assert rt.in_force_at("openPermit", "Operator", after) is False
    assert rt.in_force_at("timedPermit", "Worker", after) is True
    _clock_to(rt, LIMIT_REACHED)
    assert rt.in_force_at("timedPermit", "Worker", LIMIT_REACHED) is False


# ── declare_breach reads the answer ──────────────────────────────────────────

def test_declared_acting_without_the_permit_accepted_once_it_had_elapsed():
    rt = _runtime(("timedPermit", "Operator"), ("declarePermit", "Watchdog"))
    _clock_to(rt, PAST_THE_LIMIT)

    within = rt.declare_breach("timedPermit", "permit_requirement", "Operator", "useTimed",
                               "Watchdog", occurred_at=LIMIT_REACHED - 1)
    assert within.outcome == "blocked"
    assert within.reason == (f"'Operator' held permit 'timedPermit' at step {LIMIT_REACHED - 1}: "
                             f"acting under it is not a violation")

    elapsed = rt.declare_breach("timedPermit", "permit_requirement", "Operator", "useTimed",
                                "Watchdog", occurred_at=LIMIT_REACHED)
    assert elapsed.outcome == "violation"
    (violation,) = elapsed.violation_records
    assert violation.kind == "permit_requirement"
    assert violation.occurred_at == LIMIT_REACHED
    assert violation.warnings == ()


def test_declared_prevention_refused_for_a_permit_that_had_elapsed():
    rt = _runtime(("timedPermit", "Operator"), ("declarePermit", "Watchdog"))
    _clock_to(rt, PAST_THE_LIMIT)

    elapsed = rt.declare_breach("timedPermit", "permit", "Colleague", "useTimed", "Watchdog",
                                occurred_at=LIMIT_REACHED, rule_holder="Operator")
    assert elapsed.outcome == "blocked"
    assert elapsed.reason == (f"'Operator' did not hold permit 'timedPermit' in force "
                              f"at step {LIMIT_REACHED}")

    within = rt.declare_breach("timedPermit", "permit", "Colleague", "useTimed", "Watchdog",
                               occurred_at=LIMIT_REACHED - 1, rule_holder="Operator")
    assert within.outcome == "violation"


# ── A suspension and a restore past the limit ────────────────────────────────

def test_restore_past_the_limit_is_not_in_force_and_earlier_ticks_are_unchanged():
    rt = _runtime(("timedPermit", "Operator"))
    suspended_at = rt.current_state().tick + 1
    _clock_to(rt, suspended_at)
    _act(rt, "suspendTimed")
    while_suspended = rt.current_state().tick
    _clock_to(rt, PAST_THE_LIMIT)
    _act(rt, "restoreTimed")
    restored = rt.current_state().tick

    assert _token(rt, "timedPermit").state == "active"
    assert rt.token_states_at("timedPermit", "Operator", restored) == ("active",)
    assert rt.in_force_at("timedPermit", "Operator", restored) is False

    assert rt.in_force_at("timedPermit", "Operator", suspended_at) is True
    assert rt.token_states_at("timedPermit", "Operator", while_suspended) == ("pending",)
    assert rt.in_force_at("timedPermit", "Operator", while_suspended) is False
