"""
2.4.1-2 — `effect pend` acts only on an active instance.

Before, advance() Step 7b moved every instance of the name to pending whatever
its state, so a violated or discharged burden became pending and a later
`effect activate` returned it to active. The "pended" line was written whether
or not anything changed.

Now: only active instances are pended, for every token kind, matched by name
across all holders. An instance in any other state is left exactly as it was,
and the "pended" line is written only when an instance was pended. There is no
note line. The act itself still returns ok and advances the world tick by one.

A pended instance that is activated again gets a new activation tick, so its
deadline restarts. 2.5.0-1: except a permit, which keeps its first activation
stamp (tests/test_permit_clock.py).

Fixture: as tests/test_activate_effect_pending_only.py. Operator performs the
acts; Colleague fills no role and only holds tokens.
"""
from dataclasses import replace

import pytest

from el_engine import _parse_deadline_steps, enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification PendEffectActiveOnlyProbe

party Operator
party Colleague

community ProbeCommunity
    description: "Single role whose actions carry pend and activate effects"
    {
        objective: "Exercise the pend effect against each token state"

        role operatorRole
            description: "Performs the acts"
            {
                action pendFollowUp {
                    actor: operatorRole
                    effect pend followUpBurden
                }

                action activateFollowUp {
                    actor: operatorRole
                    effect activate followUpBurden
                }

                action pendThenActivate {
                    actor: operatorRole
                    effect pend followUpBurden
                    effect activate followUpBurden
                }

                action closeAndPend {
                    actor: operatorRole
                    effect destroy closingBurden
                    effect pend closingBurden
                }

                action pendMissing {
                    actor: operatorRole
                    effect pend neverGrantedBurden
                }

                action pendPermit {
                    actor: operatorRole
                    effect pend probePermit
                }

                action activatePermit {
                    actor: operatorRole
                    effect activate probePermit
                }

                action pendEmbargo {
                    actor: operatorRole
                    effect pend probeEmbargo
                }

                action activateEmbargo {
                    actor: operatorRole
                    effect activate probeEmbargo
                }

                action severalEffects {
                    actor: operatorRole
                    effect pend followUpBurden
                    effect pend secondBurden
                    effect destroy closingBurden
                    effect create createdBurden
                }

                action unrelatedAction {
                    actor: operatorRole
                }
            }
    }

burden followUpBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden secondBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden closingBurden {
    state: active
    discharge_mode: eventual
}

burden neverGrantedBurden {
    state: active
    discharge_mode: eventual
}

burden createdBurden {
    state: active
    discharge_mode: eventual
}

permit probePermit {
    for_action: "unrelatedAction"
    state: active
}

embargo probeEmbargo {
    for_action: "unrelatedAction"
    state: active
}

violation_response followUpResponse {
    on_violation_of: followUpBurden
    obligates: Operator
    response_kind: escalate
}
"""

DEADLINE_STEPS = _parse_deadline_steps("1 hour")

# kind -> (a token of that kind, the action that pends it, the action that
# activates it)
_BY_KIND = {
    "burden": ("followUpBurden", "pendFollowUp", "activateFollowUp"),
    "permit": ("probePermit", "pendPermit", "activatePermit"),
    "embargo": ("probeEmbargo", "pendEmbargo", "activateEmbargo"),
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


def _violated_follow_up(rt):
    """Run the active followUpBurden past its deadline."""
    _clock_to(rt, DEADLINE_STEPS)
    assert rt.check_live_violations().violations == ("followUpBurden",)
    assert _token(rt, "followUpBurden").state == "violated"


# ── Closed instances are left exactly as they were ───────────────────────────

def test_pend_leaves_violated_unchanged():
    rt = _runtime(("followUpBurden", "Operator"))
    _violated_follow_up(rt)
    assert rt.fire_violation_responses().fired_responses == ("followUpResponse",)
    responded = rt.current_state().responded
    before = _token(rt, "followUpBurden")
    tick = rt.current_state().tick

    record = rt.advance("pendFollowUp", "Operator")

    assert _token(rt, "followUpBurden") == before
    assert before.state == "violated"
    assert record.outcome == "ok"
    assert record.effects == ()
    assert record.token_events == ()
    assert rt.current_state().tick == tick + 1
    assert rt.check_live_violations().violations == ()
    assert rt.fire_violation_responses().fired_responses == ()
    assert rt.current_state().responded == responded


def test_pend_leaves_discharged_unchanged():
    rt = _runtime(("followUpBurden", "Operator", "discharged"))
    before = _token(rt, "followUpBurden")

    record = rt.advance("pendFollowUp", "Operator")

    assert _token(rt, "followUpBurden") == before
    assert record.outcome == "ok"
    assert record.effects == ()

    # Within one act: Step 7a discharges before 7b reads the pend effect.
    rt = _runtime(("closingBurden", "Operator"))

    record = rt.advance("closeAndPend", "Operator")

    assert record.outcome == "ok"
    assert record.discharged == ("closingBurden",)
    assert _token(rt, "closingBurden").state == "discharged"
    assert not any("pended" in line for line in record.effects)


@pytest.mark.parametrize("state, kind", [
    ("claimable", "burden"),
    ("superseded", "burden"),
    ("superseded", "permit"),
    ("lapsed", "burden"),
    ("lifted", "embargo"),
])
def test_pend_leaves_claimable_superseded_lapsed_lifted_unchanged(state, kind):
    name, pend, _ = _BY_KIND[kind]
    rt = _runtime((name, "Operator", state))
    before = _token(rt, name)
    assert before.kind == kind

    record = rt.advance(pend, "Operator")

    assert record.outcome == "ok"
    assert _token(rt, name) == before
    assert record.effects == ()
    assert record.token_events == ()
    assert rt.current_state().tick == 1


@pytest.mark.parametrize("acts", [
    ("pendThenActivate",),
    ("pendFollowUp", "activateFollowUp"),
], ids=["in_one_act", "in_two_acts"])
def test_pend_then_activate_cannot_revive(acts):
    rt = _runtime(("followUpBurden", "Operator"))
    _violated_follow_up(rt)
    before = _token(rt, "followUpBurden")
    tick = rt.current_state().tick

    records = [rt.advance(act, "Operator") for act in acts]

    assert _token(rt, "followUpBurden") == before
    assert before.state == "violated"
    assert all(r.outcome == "ok" for r in records)
    assert all(r.token_events == () for r in records)
    assert not any("pended" in line or "activated" in line
                   for r in records for line in r.effects)
    assert records[-1].effects == (
        "activate 'followUpBurden' had no effect: 'Operator' holds it violated",)
    assert rt.current_state().tick == tick + len(acts)

    _clock_to(rt, rt.current_state().tick + 2 * DEADLINE_STEPS)
    assert rt.check_live_violations().violations == ()


# ── The active path, every kind ──────────────────────────────────────────────

@pytest.mark.parametrize("kind", sorted(_BY_KIND))
def test_pend_active_then_activate_restores_it(kind):
    name, pend, activate = _BY_KIND[kind]
    rt = _runtime((name, "Operator"))
    _clock_to(rt, 10)

    pended = rt.advance(pend, "Operator")

    assert pended.outcome == "ok"
    assert pended.effects == (f"pended '{name}'",)
    assert [(e.token_name, e.from_state, e.to_state) for e in pended.token_events] == [
        (name, "active", "pending")]
    assert _token(rt, name).state == "pending"
    # 2.5.0-1: a permit leaving active records that it was active since grant.
    assert _token(rt, name).activated_at_tick == (0 if kind == "permit" else None)
    _clock_to(rt, 20)

    activated = rt.advance(activate, "Operator")

    assert activated.outcome == "ok"
    assert activated.effects == (f"activated '{name}'",)
    tok = _token(rt, name)
    assert tok.kind == kind
    assert tok.state == "active"
    assert tok.activated_at_tick == (0 if kind == "permit" else 20)
    assert tok.granted_at_tick == 0

    if kind == "burden":
        # The deadline counts from the new activation, not from the grant.
        _clock_to(rt, 20 + DEADLINE_STEPS - 1)
        assert rt.check_live_violations().violations == ()
        _clock_to(rt, 20 + DEADLINE_STEPS)
        assert rt.check_live_violations().violations == (name,)


# ── Nothing to change: no line ───────────────────────────────────────────────

def test_pend_already_pending_writes_no_line():
    rt = _runtime(("followUpBurden", "Operator", "pending"))
    before = _token(rt, "followUpBurden")

    record = rt.advance("pendFollowUp", "Operator")

    assert _token(rt, "followUpBurden") == before
    assert record.outcome == "ok"
    assert record.effects == ()
    assert record.token_events == ()
    assert rt.current_state().tick == 1
    assert record not in rt.accountability_chain("followUpBurden")


def test_pend_no_instance_writes_no_line():
    rt = _runtime()

    record = rt.advance("pendMissing", "Operator")

    assert record.outcome == "ok"
    assert record.effects == ()
    assert rt.current_state().tokens == ()
    assert rt.current_state().tick == 1


# ── By name, across holders ──────────────────────────────────────────────────

def test_pend_mixed_holders_only_active_instance_pends():
    rt = _runtime(("followUpBurden", "Operator", "violated"),
                  ("followUpBurden", "Colleague"))
    closed = _token(rt, "followUpBurden", "Operator")

    first = rt.advance("pendFollowUp", "Operator")

    assert _token(rt, "followUpBurden", "Operator") == closed
    assert _token(rt, "followUpBurden", "Colleague").state == "pending"
    assert first.effects == ("pended 'followUpBurden'",)

    # Colleague's instance is pending now: nothing is left to pend.
    second = rt.advance("pendFollowUp", "Operator")

    assert second.outcome == "ok"
    assert second.effects == ()
    assert _token(rt, "followUpBurden", "Operator") == closed


# ── Within one act ───────────────────────────────────────────────────────────

def test_pend_other_effects_of_the_act_still_apply():
    rt = _runtime(("followUpBurden", "Operator", "violated"),
                  ("secondBurden", "Operator"),
                  ("closingBurden", "Operator"))
    before = _token(rt, "followUpBurden")

    record = rt.advance("severalEffects", "Operator")

    assert record.outcome == "ok"
    assert _token(rt, "followUpBurden") == before
    assert _token(rt, "secondBurden").state == "pending"
    assert _token(rt, "closingBurden").state == "discharged"
    assert _token(rt, "createdBurden").state == "active"
    assert [line for line in record.effects if "pended" in line] == [
        "pended 'secondBurden'"]
