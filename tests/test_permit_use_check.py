"""
2.5.0-1 — a permit's time limit is enforced at use.

A permit is usable only if it is active and its time has not elapsed
(_permit_usable()). Elapsed means the instance's deadline is a duration with a
measurable magnitude and the tick has reached that many ticks from the permit's
clock start. A date deadline, a deadline with no magnitude and no deadline never
count as elapsed. The refusal writes nothing, so an elapsed permit stays active.

Fixture: as tests/test_permit_clock.py. Operator performs the acts and holds
the permits, Colleague takes a clone, Worker takes a transfer and Watchdog
declares. Tokens are granted at tick 3, so a clock that starts at grant cannot
be mistaken for one that starts at tick 0.
"""
from dataclasses import replace

from el_engine import _permit_usable, enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification PermitUseProbe

party Issuer
party Operator
party Colleague
party Worker
party Watchdog

policy ShortNotice : duration { initial_value: 5 minutes }

community ProbeCommunity
    description: "Actions gated by permits with different time limits"
    {
        objective: "Exercise the use check"

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

                action useWorded {
                    actor: operatorRole
                    requires_permit wordedPermit
                }

                action usePolicyFed {
                    actor: operatorRole
                    requires_permit policyFedPermit
                }

                action useOpen {
                    actor: operatorRole
                    requires_permit openPermit
                }

                action cloneTimed {
                    actor: operatorRole
                    effect clone timedPermit
                }

                action transferTimed {
                    actor: operatorRole
                    effect transfer timedPermit to workerRole
                }

                action dischargeStrict {
                    actor: operatorRole
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
            description: "Declares an overdue strict burden violated"
            {
                action declareStrict {
                    actor: watchdogRole
                    requires_permit declarePermit
                    declares_violation_of strictBurden
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

permit wordedPermit {
    for_action: "useWorded"
    state: active
    deadline: "thirty days"
}

permit policyFedPermit {
    for_action: "usePolicyFed"
    state: active
    deadline: ShortNotice
}

permit openPermit {
    for_action: "useOpen"
    state: active
}

permit declarePermit {
    for_action: "declareStrict"
    state: active
    deadline: "5 minutes"
}

burden strictBurden {
    for_action: "dischargeStrict"
    state: active
    deadline: "1 minute"
    discharge_mode: strict
}
"""

GRANT_TICK = 3
LIMIT_REACHED = GRANT_TICK + 5
PAST_THE_LIMIT = 20

ELAPSED = "required permit 'timedPermit' time has elapsed for actor"


def _runtime(*grants, start_tick=GRANT_TICK) -> Runtime:
    """Each grant is (token name, holder), or (token name, holder, granted at
    tick). The runtime starts at start_tick, which can lie past a grant: the
    clock cannot be advanced while a strict burden is active."""
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = enroll(state, "Colleague", role_name="operatorRole")
    state = enroll(state, "Worker", role_name="workerRole")
    state = enroll(state, "Watchdog", role_name="watchdogRole")
    state = state.with_tick(start_tick)
    for name, holder, *granted_at in grants:
        tick = granted_at[0] if granted_at else GRANT_TICK
        state = grant_token(state, token_from_spec(spec, name, holder, tick))
    return Runtime(state, spec)


def _token(rt, name, holder="Operator"):
    return next(t for t in rt.current_state().tokens
                if t.token_name == name and t.holder == holder)


def _clock_to(rt, tick):
    ticks = tick - rt.current_state().tick
    if ticks:
        assert rt.advance_clock(ticks).outcome == "ok"
    assert rt.current_state().tick == tick


# ── The limit ────────────────────────────────────────────────────────────────

def test_allowed_one_tick_before_the_limit_and_refused_at_it():
    rt = _runtime(("timedPermit", "Operator"))
    _clock_to(rt, LIMIT_REACHED - 1)

    assert rt.advance("useTimed", "Operator").outcome == "ok"

    assert rt.current_state().tick == LIMIT_REACHED
    assert rt.advance("useTimed", "Operator").outcome == "blocked"


# ── The refusal ──────────────────────────────────────────────────────────────

def test_refusal_reason_says_the_time_has_elapsed():
    rt = _runtime(("timedPermit", "Operator"))
    _clock_to(rt, PAST_THE_LIMIT)

    assert rt.advance("useTimed", "Operator").reason == ELAPSED


def test_blocked_by_shows_the_true_instance_of_an_elapsed_permit():
    rt = _runtime(("timedPermit", "Operator"))
    _clock_to(rt, PAST_THE_LIMIT)

    ref = rt.advance("useTimed", "Operator").blocked_by

    assert ref.token_name == "timedPermit"
    assert ref.token_kind == "permit"
    assert ref.holder == "Operator"
    assert ref.state == "active"
    assert ref.granted_at_tick == GRANT_TICK


def test_blocked_by_names_the_active_instance_not_a_later_superseded_one():
    start = _runtime(("timedPermit", "Operator"), start_tick=10)
    superseded = replace(token_from_spec(start._spec, "timedPermit", "Operator", 10),
                         state="superseded")
    rt = Runtime(grant_token(start.current_state(), superseded), start._spec)
    _clock_to(rt, PAST_THE_LIMIT)

    record = rt.advance("useTimed", "Operator")

    assert record.outcome == "blocked"
    assert record.reason == ELAPSED
    assert record.blocked_by.state == "active"
    assert record.blocked_by.granted_at_tick == GRANT_TICK


def test_refused_attempt_is_recorded_as_a_permit_requirement_violation():
    rt = _runtime(("timedPermit", "Operator"))
    _clock_to(rt, PAST_THE_LIMIT)

    record = rt.advance("useTimed", "Operator")

    assert record.outcome == "blocked"
    assert len(record.violation_records) == 1
    violation = record.violation_records[0]
    assert violation in rt.current_state().violation_records
    assert violation.rule == "timedPermit"
    assert violation.kind == "permit_requirement"
    assert violation.violator == "Operator"
    assert violation.behaviour == "useTimed"
    assert violation.source == "refused_attempt"
    assert violation.occurred_at == PAST_THE_LIMIT


def test_refused_use_writes_no_token_change():
    rt = _runtime(("timedPermit", "Operator"))
    _clock_to(rt, PAST_THE_LIMIT)
    before = rt.current_state()

    record = rt.advance("useTimed", "Operator")

    after = rt.current_state()
    assert record.token_events == ()
    assert after.tokens == before.tokens
    assert after.tick == before.tick
    assert _token(rt, "timedPermit").state == "active"


# ── Limits that never elapse ─────────────────────────────────────────────────

def test_date_deadline_past_due_is_still_usable():
    rt = _runtime(("datedPermit", "Operator"))
    _clock_to(rt, 100000)

    assert rt.advance("useDated", "Operator").outcome == "ok"


def test_deadline_with_no_magnitude_never_elapses():
    rt = _runtime(("wordedPermit", "Operator"))
    # Past the one day _parse_deadline_steps() reads from the word "days".
    _clock_to(rt, 100000)

    assert rt.advance("useWorded", "Operator").outcome == "ok"

    # Past the default of 5 that _parse_deadline_steps() gives a deadline
    # with no unit word.
    no_unit = replace(_token(rt, "wordedPermit"), deadline="referral episode")
    assert _permit_usable(no_unit, GRANT_TICK + 5)


def test_permit_with_no_deadline_never_elapses():
    rt = _runtime(("openPermit", "Operator"))
    _clock_to(rt, 100000)

    assert rt.advance("useOpen", "Operator").outcome == "ok"


# ── A policy-fed limit ───────────────────────────────────────────────────────

def test_policy_fed_duration_acts_through_the_instance_resolved_text():
    rt = _runtime(("policyFedPermit", "Operator"))
    tok = _token(rt, "policyFedPermit")
    assert tok.deadline == "5 minutes"
    _clock_to(rt, LIMIT_REACHED - 1)

    assert rt.advance("usePolicyFed", "Operator").outcome == "ok"

    record = rt.advance("usePolicyFed", "Operator")
    assert record.outcome == "blocked"
    assert record.reason == "required permit 'policyFedPermit' time has elapsed for actor"
    # The instance's own text decides, not the specification's.
    assert _permit_usable(replace(tok, deadline="1 hour"), LIMIT_REACHED)


# ── Two instances ────────────────────────────────────────────────────────────

def test_one_elapsed_and_one_usable_instance_allows_the_act():
    rt = _runtime(("timedPermit", "Operator"),
                  ("timedPermit", "Operator", PAST_THE_LIMIT),
                  start_tick=PAST_THE_LIMIT)
    instances = [t for t in rt.current_state().tokens if t.token_name == "timedPermit"]
    assert [_permit_usable(t, PAST_THE_LIMIT) for t in instances] == [False, True]

    assert rt.advance("useTimed", "Operator").outcome == "ok"


# ── A declaration ────────────────────────────────────────────────────────────

def test_elapsed_declarer_permit_refuses_declare_violation():
    grants = (("strictBurden", "Operator"), ("declarePermit", "Watchdog"))

    within = _runtime(*grants, start_tick=LIMIT_REACHED - 1)
    assert within.declare_violation("strictBurden", "Watchdog",
                                    at_tick=PAST_THE_LIMIT).outcome == "violation"

    elapsed = _runtime(*grants, start_tick=LIMIT_REACHED)
    record = elapsed.declare_violation("strictBurden", "Watchdog", at_tick=PAST_THE_LIMIT)

    assert record.outcome == "blocked"
    assert record.reason == "required permit 'declarePermit' time has elapsed for actor"
    assert record.blocked_by.state == "active"
    assert _token(elapsed, "strictBurden").state == "active"


# ── A clone and a transfer carry the clock ───────────────────────────────────

def test_clone_of_an_elapsed_permit_is_also_elapsed():
    rt = _runtime(("timedPermit", "Operator"))
    _clock_to(rt, PAST_THE_LIMIT)

    assert rt.advance("cloneTimed", "Colleague").outcome == "ok"

    clone = _token(rt, "timedPermit", "Colleague")
    assert clone.state == "active"
    assert clone.granted_at_tick == GRANT_TICK
    record = rt.advance("useTimed", "Colleague")
    assert record.outcome == "blocked"
    assert record.reason == ELAPSED


def test_transfer_of_an_elapsed_permit_carries_the_clock():
    rt = _runtime(("timedPermit", "Operator"))
    _clock_to(rt, PAST_THE_LIMIT)

    assert rt.advance("transferTimed", "Operator").outcome == "ok"

    moved = _token(rt, "timedPermit", "Worker")
    assert moved.state == "active"
    assert moved.granted_at_tick == GRANT_TICK
    record = rt.advance("useAsWorker", "Worker")
    assert record.outcome == "blocked"
    assert record.reason == ELAPSED
    assert record.blocked_by.holder == "Worker"
