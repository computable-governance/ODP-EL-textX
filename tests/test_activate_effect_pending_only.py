"""
2.4.1-1 — `effect activate` acts only on a pending instance.

Before, advance() Step 7b activated every instance of the name whose state
was not already active, so a violated or discharged burden returned to
active with its activation tick moved and its deadline restarted, and the
"activated" line was written whether or not anything changed.

Now: only pending instances are activated, for every token kind, matched by
name across all holders (as AM-100 part 2 does for events). An instance in
any other state is left exactly as it was, and the "activated" line is written
only when an instance was activated. Each instance neither pending nor active
gets a note line instead, without the word "activated". The act itself still
returns ok and advances the world tick by one.

Fixture: as tests/test_am100_engine_deadline_from_activation.py. Operator
performs the acts; Colleague fills no role and only holds tokens.
"""
from dataclasses import replace

import pytest

from el_engine import _parse_deadline_steps, enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification ActivateEffectPendingOnlyProbe

party Operator
party Colleague

community ProbeCommunity
    description: "Single role whose actions carry activate effects"
    {
        objective: "Exercise the activate effect against each token state"

        role operatorRole
            description: "Performs the acts"
            {
                action openFollowUp {
                    actor: operatorRole
                    effect activate followUpBurden
                }

                action closeAndActivate {
                    actor: operatorRole
                    effect destroy closingBurden
                    effect activate closingBurden
                }

                action activateMissing {
                    actor: operatorRole
                    effect activate neverGrantedBurden
                }

                action openPermit {
                    actor: operatorRole
                    effect activate probePermit
                }

                action openEmbargo {
                    actor: operatorRole
                    effect activate probeEmbargo
                }

                action severalEffects {
                    actor: operatorRole
                    effect activate followUpBurden
                    effect activate secondBurden
                    effect destroy closingBurden
                    effect create createdBurden
                }

                action unrelatedAction {
                    actor: operatorRole
                }
            }
    }

burden followUpBurden {
    state: pending
    deadline: "1 hour"
    discharge_mode: eventual
}

burden secondBurden {
    state: pending
    deadline: "1 hour"
    discharge_mode: eventual
}

burden closingBurden {
    state: active
    discharge_mode: eventual
}

burden neverGrantedBurden {
    state: pending
    discharge_mode: eventual
}

burden createdBurden {
    state: active
    discharge_mode: eventual
}

permit probePermit {
    for_action: "unrelatedAction"
    state: pending
}

embargo probeEmbargo {
    for_action: "unrelatedAction"
    state: pending
}

violation_response followUpResponse {
    on_violation_of: followUpBurden
    obligates: Operator
    response_kind: escalate
}
"""

DEADLINE_STEPS = _parse_deadline_steps("1 hour")

# kind -> (a token of that kind, the action whose effect activates it)
_BY_KIND = {
    "burden": ("followUpBurden", "openFollowUp"),
    "permit": ("probePermit", "openPermit"),
    "embargo": ("probeEmbargo", "openEmbargo"),
}


def _runtime(*grants) -> Runtime:
    """Each grant is (token name, holder), or (token name, holder, state)
    for an instance seeded directly in a state only a run can produce."""
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = enroll(state, "Colleague")
    for name, holder, *seeded in grants:
        token = token_from_spec(spec, name, holder, 0)
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


def _activated_lines(record):
    return [line for line in record.effects if "activated" in line]


def _violated_follow_up(rt):
    """Activate followUpBurden and run it past its deadline."""
    assert rt.advance("openFollowUp", "Operator").outcome == "ok"
    _clock_to(rt, _token(rt, "followUpBurden").activated_at_tick + DEADLINE_STEPS)
    assert rt.check_live_violations().violations == ("followUpBurden",)
    assert _token(rt, "followUpBurden").state == "violated"


# ── The pending path, every kind ─────────────────────────────────────────────

@pytest.mark.parametrize("kind", sorted(_BY_KIND))
def test_pending_becomes_active_stamped_and_logged(kind):
    name, action = _BY_KIND[kind]
    rt = _runtime((name, "Operator"))
    _clock_to(rt, 10)

    record = rt.advance(action, "Operator")

    assert record.outcome == "ok"
    tok = _token(rt, name)
    assert tok.kind == kind
    assert tok.state == "active"
    assert tok.activated_at_tick == 10
    assert tok.granted_at_tick == 0
    assert _activated_lines(record) == [f"activated '{name}'"]


# ── Closed instances are left exactly as they were ───────────────────────────

def test_violated_stays_violated_clock_unchanged():
    rt = _runtime(("followUpBurden", "Operator"))
    _clock_to(rt, 10)
    _violated_follow_up(rt)
    before = _token(rt, "followUpBurden")
    tick = rt.current_state().tick

    record = rt.advance("openFollowUp", "Operator")

    after = _token(rt, "followUpBurden")
    assert after == before
    assert after.state == "violated"
    assert after.activated_at_tick == 10
    assert after.granted_at_tick == 0
    assert after.deadline == "1 hour"
    assert _activated_lines(record) == []
    assert record.outcome == "ok"
    assert rt.current_state().tick == tick + 1


def test_violated_is_not_violated_again_and_response_key_unchanged():
    rt = _runtime(("followUpBurden", "Operator"))
    _violated_follow_up(rt)
    assert rt.fire_violation_responses().fired_responses == ("followUpResponse",)
    responded = rt.current_state().responded
    assert responded

    assert rt.advance("openFollowUp", "Operator").outcome == "ok"
    _clock_to(rt, rt.current_state().tick + 2 * DEADLINE_STEPS)

    assert rt.check_live_violations().violations == ()
    assert rt.fire_violation_responses().fired_responses == ()
    assert rt.current_state().responded == responded


def test_discharged_stays_discharged():
    rt = _runtime(("followUpBurden", "Operator", "discharged"))
    before = _token(rt, "followUpBurden")

    record = rt.advance("openFollowUp", "Operator")

    assert _token(rt, "followUpBurden") == before
    assert _activated_lines(record) == []
    assert record.outcome == "ok"


# ── Nothing to change: no line ───────────────────────────────────────────────

def test_already_active_keeps_clock_and_writes_no_line():
    rt = _runtime(("followUpBurden", "Operator"))
    _clock_to(rt, 10)
    assert rt.advance("openFollowUp", "Operator").outcome == "ok"
    before = _token(rt, "followUpBurden")
    _clock_to(rt, 20)

    record = rt.advance("openFollowUp", "Operator")

    assert _token(rt, "followUpBurden") == before
    assert before.activated_at_tick == 10
    assert _activated_lines(record) == []
    assert record.outcome == "ok"


def test_no_instance_writes_no_line():
    rt = _runtime()

    record = rt.advance("activateMissing", "Operator")

    assert record.outcome == "ok"
    assert record.effects == ()
    assert rt.current_state().tokens == ()
    assert rt.current_state().tick == 1


def test_no_token_event_when_nothing_changes():
    rt = _runtime(("followUpBurden", "Operator"))
    first = rt.advance("openFollowUp", "Operator")
    assert [(e.token_name, e.from_state, e.to_state) for e in first.token_events] == [
        ("followUpBurden", "pending", "active")]

    assert rt.advance("openFollowUp", "Operator").token_events == ()

    _clock_to(rt, _token(rt, "followUpBurden").activated_at_tick + DEADLINE_STEPS)
    assert rt.check_live_violations().violations == ("followUpBurden",)
    assert rt.advance("openFollowUp", "Operator").token_events == ()


# ── Within one act ───────────────────────────────────────────────────────────

def test_discharge_and_activate_same_token_in_one_act_stays_discharged():
    """Step 7a discharges the burden before 7b reads the activate effect."""
    rt = _runtime(("closingBurden", "Operator"))

    record = rt.advance("closeAndActivate", "Operator")

    assert record.outcome == "ok"
    assert record.discharged == ("closingBurden",)
    assert _token(rt, "closingBurden").state == "discharged"
    assert _activated_lines(record) == []


def test_other_effects_of_the_act_still_apply():
    rt = _runtime(("followUpBurden", "Operator", "violated"),
                  ("secondBurden", "Operator"),
                  ("closingBurden", "Operator"))
    before = _token(rt, "followUpBurden")

    record = rt.advance("severalEffects", "Operator")

    assert record.outcome == "ok"
    assert _token(rt, "followUpBurden") == before
    assert _token(rt, "secondBurden").state == "active"
    assert _token(rt, "closingBurden").state == "discharged"
    assert _token(rt, "createdBurden").state == "active"
    assert _activated_lines(record) == ["activated 'secondBurden'"]


# ── By name, across holders ──────────────────────────────────────────────────

def test_mixed_holders_only_pending_instance_activates():
    rt = _runtime(("followUpBurden", "Operator", "violated"),
                  ("followUpBurden", "Colleague"))
    closed = _token(rt, "followUpBurden", "Operator")
    _clock_to(rt, 10)

    record = rt.advance("openFollowUp", "Operator")

    assert _token(rt, "followUpBurden", "Operator") == closed
    activated = _token(rt, "followUpBurden", "Colleague")
    assert activated.state == "active"
    assert activated.activated_at_tick == 10
    assert _activated_lines(record) == ["activated 'followUpBurden'"]


def test_other_holders_token_still_activates():
    """The actor need not hold the token (the ereferral scenario's GP act
    activates a burden the specialist holds)."""
    rt = _runtime(("followUpBurden", "Colleague"))
    _clock_to(rt, 10)

    record = rt.advance("openFollowUp", "Operator")

    tok = _token(rt, "followUpBurden", "Colleague")
    assert tok.state == "active"
    assert tok.activated_at_tick == 10
    assert _activated_lines(record) == ["activated 'followUpBurden'"]


# ── The other states ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("state, kind", [
    ("claimable", "burden"),
    ("superseded", "burden"),
    ("superseded", "permit"),
    ("lapsed", "burden"),
    ("lifted", "embargo"),
])
def test_non_pending_states_unchanged(state, kind):
    name, action = _BY_KIND[kind]
    rt = _runtime((name, "Operator", state))
    before = _token(rt, name)
    assert before.kind == kind

    record = rt.advance(action, "Operator")

    assert record.outcome == "ok"
    assert _token(rt, name) == before
    assert _activated_lines(record) == []
    assert record.token_events == ()
    assert rt.current_state().tick == 1


# ── The note line for a closed instance ──────────────────────────────────────

@pytest.mark.parametrize("state, kind", [
    ("violated", "burden"),
    ("discharged", "burden"),
    ("claimable", "burden"),
    ("superseded", "burden"),
    ("lapsed", "burden"),
    ("lifted", "embargo"),
])
def test_closed_instance_gets_a_note_line_without_the_word_activated(state, kind):
    name, action = _BY_KIND[kind]
    rt = _runtime((name, "Operator", state))
    before = _token(rt, name)
    assert before.kind == kind

    record = rt.advance(action, "Operator")

    assert record.effects == (
        f"activate '{name}' had no effect: 'Operator' holds it {state}",)
    assert not any("activated" in line for line in record.effects)
    assert record.outcome == "ok"
    assert _token(rt, name) == before
    assert rt.current_state().tick == 1


def test_noop_act_stays_in_accountability_chain():
    rt = _runtime(("followUpBurden", "Operator", "violated"))

    record = rt.advance("openFollowUp", "Operator")

    assert record.discharged == () and record.violations == ()
    assert record in rt.accountability_chain("followUpBurden")


def test_mixed_holders_activated_line_then_note_line():
    rt = _runtime(("followUpBurden", "Operator", "violated"),
                  ("followUpBurden", "Colleague"))
    note = "activate 'followUpBurden' had no effect: 'Operator' holds it violated"

    first = rt.advance("openFollowUp", "Operator")

    assert first.effects == ("activated 'followUpBurden'", note)

    # Colleague's instance is active now: no line for it, the note stays.
    second = rt.advance("openFollowUp", "Operator")

    assert second.effects == (note,)


# ── What the accountability chain leaves out ─────────────────────────────────

def test_already_active_noop_not_in_accountability_chain():
    rt = _runtime(("followUpBurden", "Operator"))
    first = rt.advance("openFollowUp", "Operator")

    second = rt.advance("openFollowUp", "Operator")

    assert second not in rt.accountability_chain("followUpBurden")
    assert first in rt.accountability_chain("followUpBurden")
    assert second.outcome == "ok"
    assert second.effects == ()


def test_no_instance_noop_not_in_accountability_chain():
    rt = _runtime()

    record = rt.advance("activateMissing", "Operator")

    assert record not in rt.accountability_chain("neverGrantedBurden")
    assert rt.accountability_chain("neverGrantedBurden") == []
    assert record.outcome == "ok"
    assert record.effects == ()


def test_discharge_and_activate_note_text():
    """Step 7a writes its own discharge line before the note."""
    rt = _runtime(("closingBurden", "Operator"))

    record = rt.advance("closeAndActivate", "Operator")

    assert _token(rt, "closingBurden").state == "discharged"
    assert record.effects == (
        "discharged burden 'closingBurden'",
        "activate 'closingBurden' had no effect: 'Operator' holds it discharged",
    )
