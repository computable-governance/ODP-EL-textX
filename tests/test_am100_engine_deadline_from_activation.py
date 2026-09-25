"""
AM-100 (part 1) — the live engine counts deadlines from activation.

Engine counterpart of AM-99a part 1 (static Kripke builder,
World.activation_steps). Before AM-100, check_live_violations() computed
`elapsed = tick - granted_at_tick`, and activating a pending token
(_transition()) preserved granted_at_tick, so an event-triggered burden's
deadline ran from its grant, not from when it became live. A burden
triggered late enough violated on the first sweep after activation.

Fix: TokenInstance.activated_at_tick, stamped on pending -> active by an
event (Step 7c `emits`, fire_event()) or by a DeonticEffect `activate`;
check_live_violations() counts from it when set, else from
granted_at_tick. granted_at_tick is unchanged (grant provenance).

Part 2: an event activates only 'pending' tokens, mirroring the static
builder's P6a/T11 (only WAITING obligations activate). Before, a repeated
event moved a matching token to 'active' whatever its state, reviving
discharged and violated tokens.

C1 claim (claimable -> active) deliberately still counts from grant: pool
deadlines are worded from the offer ("4 hours from referral delegation"),
and the static builder's C1 does not record activation_steps either
(docs/el_grammar_amendments.md, AM-100).

Fixture: every burden has deadline "1 hour" (5 steps, eventual). Tokens
are granted at tick 0; triggered ones are activated at tick 10, so they
must violate at tick 15 and not at 14.
"""
from el_engine import TokenInstance, enroll, grant_token, initial_state, token_from_spec
from el_parser import parse, parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification EngineDeadlineFromActivationProbe

party Operator

community ProbeCommunity
    description: "Single role whose actions activate pending burdens"
    {
        objective: "Exercise engine deadline counting for activated burdens"

        event workStarted
            description: "Fired when startWork runs"

        event externallyStarted
            description: "Fired directly via fire_event(), by no action"

        role operatorRole
            description: "Performs the activating actions"
            {
                action startWork {
                    description: "Emits workStarted"
                    actor: operatorRole
                    emits: workStarted
                }

                action finishWork {
                    description: "Discharges fireTriggeredBurden"
                    actor: operatorRole
                    favoured_by_burden fireTriggeredBurden
                }

                action openFollowUp {
                    description: "Activates followUpBurden via a DeonticEffect"
                    actor: operatorRole
                    effect activate followUpBurden
                }
            }
    }

burden emitTriggeredBurden {
    state: pending
    deadline: "1 hour"
    triggered_by: workStarted
    discharge_mode: eventual
}

burden fireTriggeredBurden {
    for_action: "finishWork"
    state: pending
    deadline: "1 hour"
    triggered_by: externallyStarted
    discharge_mode: eventual
}

burden followUpBurden {
    state: pending
    deadline: "1 hour"
    discharge_mode: eventual
}

burden freshBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}
"""

ACTIVATION_TICK = 10
DEADLINE_STEPS = 5


def _runtime(*token_names) -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    for name in token_names:
        state = grant_token(state, token_from_spec(spec, name, "Operator", 0))
    return Runtime(state, spec)


def _token(rt, name):
    return next(t for t in rt.current_state().tokens if t.token_name == name)


def _clock_to(rt, tick):
    ticks = tick - rt.current_state().tick
    if ticks:
        assert rt.advance_clock(ticks).outcome == "ok"
    assert rt.current_state().tick == tick


def _assert_violates_at_activation_plus_deadline(rt, name):
    _clock_to(rt, ACTIVATION_TICK + DEADLINE_STEPS - 1)
    record = rt.check_live_violations()
    assert record.outcome == "ok", record.effects
    assert _token(rt, name).state == "active"

    _clock_to(rt, ACTIVATION_TICK + DEADLINE_STEPS)
    record = rt.check_live_violations()
    assert record.violations == (name,)
    assert _token(rt, name).state == "violated"


def test_emits_triggered_burden_deadline_counts_from_activation():
    rt = _runtime("emitTriggeredBurden")
    _clock_to(rt, ACTIVATION_TICK)

    assert rt.advance("startWork", "Operator").outcome == "ok"
    tok = _token(rt, "emitTriggeredBurden")
    assert tok.state == "active"
    assert tok.activated_at_tick == ACTIVATION_TICK
    assert tok.granted_at_tick == 0

    _assert_violates_at_activation_plus_deadline(rt, "emitTriggeredBurden")
    assert _token(rt, "emitTriggeredBurden").granted_at_tick == 0


def test_fire_event_triggered_burden_deadline_counts_from_activation():
    rt = _runtime("fireTriggeredBurden")
    _clock_to(rt, ACTIVATION_TICK)

    assert rt.fire_event("externallyStarted").outcome == "ok"
    tok = _token(rt, "fireTriggeredBurden")
    assert tok.state == "active"
    assert tok.activated_at_tick == ACTIVATION_TICK
    assert tok.granted_at_tick == 0

    _assert_violates_at_activation_plus_deadline(rt, "fireTriggeredBurden")
    assert _token(rt, "fireTriggeredBurden").granted_at_tick == 0


def test_activate_effect_burden_deadline_counts_from_activation():
    """7b `effect activate`: same principle as event activation. Not
    modelled by the Kripke builders, so no layer mismatch."""
    rt = _runtime("followUpBurden")
    _clock_to(rt, ACTIVATION_TICK)

    assert rt.advance("openFollowUp", "Operator").outcome == "ok"
    tok = _token(rt, "followUpBurden")
    assert tok.state == "active"
    assert tok.activated_at_tick == ACTIVATION_TICK
    assert tok.granted_at_tick == 0

    _assert_violates_at_activation_plus_deadline(rt, "followUpBurden")


def test_freshly_granted_token_counts_from_grant():
    """Grant and activation coincide: activated_at_tick stays None and the
    deadline counts from granted_at_tick, exactly as before AM-100."""
    rt = _runtime()
    _clock_to(rt, 3)
    rt._state = grant_token(
        rt.current_state(), token_from_spec(rt._spec, "freshBurden", "Operator", 3)
    )
    assert _token(rt, "freshBurden").activated_at_tick is None

    _clock_to(rt, 3 + DEADLINE_STEPS - 1)
    assert rt.check_live_violations().outcome == "ok"

    _clock_to(rt, 3 + DEADLINE_STEPS)
    assert rt.check_live_violations().violations == ("freshBurden",)


def test_repeated_event_does_not_restart_deadline():
    rt = _runtime("fireTriggeredBurden")
    _clock_to(rt, ACTIVATION_TICK)
    assert rt.fire_event("externallyStarted").outcome == "ok"

    _clock_to(rt, ACTIVATION_TICK + DEADLINE_STEPS - 1)
    assert rt.check_live_violations().outcome == "ok"

    # Re-fire while still active: fire_event() advances the tick to
    # ACTIVATION_TICK + DEADLINE_STEPS, and the original clock keeps running.
    assert rt.fire_event("externallyStarted").outcome == "ok"
    assert _token(rt, "fireTriggeredBurden").activated_at_tick == ACTIVATION_TICK
    assert rt.current_state().tick == ACTIVATION_TICK + DEADLINE_STEPS

    assert rt.check_live_violations().violations == ("fireTriggeredBurden",)


# ── C1 claim: deliberately still counts from grant ──────────────────────────

_CLAIMING_SCENARIO = "scenarios/erequesting_claiming/erequesting_claiming_scenario.el"
_CLAIM_DEADLINE_STEPS = 20  # "4 hours from referral delegation", Commitment-derived


def _claiming_runtime():
    result = parse(_CLAIMING_SCENARIO, validate=True)
    assert result.ok, result.errors
    state = initial_state()
    state = enroll(state, "DiagnosticProviderA", role_name="eligibleProviderA")
    state = enroll(state, "DiagnosticProviderB", role_name="eligibleProviderB")
    for name, holder, action in (
        ("providerAClaimBurden", "DiagnosticProviderA", "claimReferralA"),
        ("providerBClaimBurden", "DiagnosticProviderB", "claimReferralB"),
    ):
        state = grant_token(state, TokenInstance(
            token_name=name, kind="burden", holder=holder,
            state="claimable", discharge_mode="eventual", priority="high",
            granted_at_tick=0, deadline="4 hours from referral delegation",
            for_action=action,
        ))
    return Runtime(state, result.model)


def test_c1_claimed_burden_deadline_counts_from_grant():
    """The pool deadline is worded from the offer, so a claim at tick 10
    does not restart it: the claimed burden violates at grant (0) + 20."""
    rt = _claiming_runtime()
    _clock_to(rt, ACTIVATION_TICK)

    assert rt.claim("providerAClaimBurden", "DiagnosticProviderA").outcome == "ok"
    tok = _token(rt, "providerAClaimBurden")
    assert tok.state == "active"
    assert tok.activated_at_tick is None
    assert tok.granted_at_tick == 0

    _clock_to(rt, _CLAIM_DEADLINE_STEPS - 1)
    assert rt.check_live_violations().outcome == "ok"

    _clock_to(rt, _CLAIM_DEADLINE_STEPS)
    assert rt.check_live_violations().violations == ("providerAClaimBurden",)


# ── Part 2: an event activates only pending tokens ──────────────────────────

def test_repeated_event_leaves_discharged_token_discharged():
    rt = _runtime("fireTriggeredBurden")
    assert rt.fire_event("externallyStarted").outcome == "ok"
    assert rt.advance("finishWork", "Operator").outcome == "ok"
    assert _token(rt, "fireTriggeredBurden").state == "discharged"

    assert rt.fire_event("externallyStarted").outcome == "ok"
    assert _token(rt, "fireTriggeredBurden").state == "discharged"


def test_repeated_event_leaves_violated_token_violated():
    rt = _runtime("fireTriggeredBurden")
    assert rt.fire_event("externallyStarted").outcome == "ok"
    _clock_to(rt, 1 + DEADLINE_STEPS)
    assert rt.check_live_violations().violations == ("fireTriggeredBurden",)

    assert rt.fire_event("externallyStarted").outcome == "ok"
    assert _token(rt, "fireTriggeredBurden").state == "violated"
