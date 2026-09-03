"""
General coverage for the emits -> triggered_by event-activation mechanism
firing off a violation-response-created burden's own discharge — NOT tied
to referral_scenario.el, which used this mechanism for its
escalationNoticeBurden -> reviewNonResponseAndDetermineNextStepsBurden
step only briefly (AM-75, same day) before it was reverted in favour of
`effect create` (triggered_by needs a pre-existing pending token that
nothing in the live builder ever granted — see
docs/CONCEPTS_INDEX.md's same-day correction). Kept as a standalone probe
of the mechanism itself, since emits/triggered_by remains real, tested
machinery elsewhere (tests/test_referral_event_triggers.py's Step 7c
tests) even though this particular scenario no longer uses it for this
particular case.

Combines two existing probe patterns rather than inventing a third:
  - tests/test_fire_violation_responses.py's minimal inline probe via
    parse_string(), with a party/burden/violation_response shape built
    directly rather than pulled from a scenario file.
  - tests/test_referral_event_triggers.py's Step 7c pattern (an Action's
    `emits` activating a `triggered_by` token through a real advance()
    call, not a `_transition()` shortcut).

The probe below chains both together: fire_violation_responses() grants
escalationBurden to Responder (the general shape of a violation-created
burden reaching its holder); then a single real advance() call on
Responder's own real role/action (respondToEscalation) both discharges
escalationBurden and emits escalationNotified, which activates
consumerBurden — proving discharge and event-triggered activation land in
the same TransitionRecord.effects tuple, from one action. A generic
demonstration of the mechanism, not a mirror of any specific scenario's
current wiring.
"""
from el_engine import _transition, advance, fire_violation_responses, grant_token, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification GPEscalationNotificationChainProbe

party SourceHolder
party Responder
party EscalationTarget

burden sourceBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

community EscalationCommunity
    description: "Single role/action pair exercising the emits -> triggered_by chain fed by a violation-response-created burden"
    {
        objective: "Exercise the escalate_to notification chain in isolation from referral_scenario.el"

        event escalationNotified
            description: "Fired when respondToEscalation runs"

        role responderRole
            description: "Single role performing respondToEscalation"
            {
                action respondToEscalation {
                    description: "Discharges escalationBurden and notifies the escalation target"
                    actor: responderRole
                    favoured_by_burden escalationBurden
                    emits: escalationNotified
                }
            }
    }

burden escalationBurden {
    for_action: "respondToEscalation"
    state: active
    deadline: "1 hour"
    discharge_mode: strict
}

burden consumerBurden {
    for_action: "actUponEscalation"
    state: pending
    triggered_by: escalationNotified
    discharge_mode: eventual
    priority: normal
    description: "Should transition pending -> active when escalationNotified fires via respondToEscalation's emits"
}

violation_response probeViolationResponse {
    on_violation_of: sourceBurden
    obligates: Responder
    response_kind: escalate
    creates_burden: escalationBurden
    escalate_to: EscalationTarget
}
"""


def _build_probe_runtime():
    """Parses the probe and returns a Runtime whose sourceBurden is already
    'violated' (held by SourceHolder) and whose consumerBurden is
    pre-granted 'pending' to EscalationTarget — the two preconditions this
    test's chain operates on, built directly rather than driven through
    check_live_violations()/a prior advance() call."""
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    rt = Runtime.build_from_spec(spec)

    state = rt.current_state()
    violated_tok = _transition(
        token_from_spec(spec, "sourceBurden", "SourceHolder", state.tick),
        "violated",
    )
    state = grant_token(state, violated_tok)
    state = grant_token(
        state, token_from_spec(spec, "consumerBurden", "EscalationTarget", state.tick)
    )
    rt._state = state
    return rt


def _token(state, name, holder=None):
    return next(
        t for t in state.tokens
        if t.token_name == name and (holder is None or t.holder == holder)
    )


def test_violation_grant_then_real_action_discharge_activates_triggered_consumer_burden():
    rt = _build_probe_runtime()

    # Grant escalationBurden to Responder via the real violation-response
    # mechanism — mirrors how escalationNoticeBurden reaches
    # SpecialistPractice in referral_scenario.el's real chain.
    fire_state, fire_record = fire_violation_responses(rt.current_state(), rt._spec)
    assert fire_record.fired_responses == ("probeViolationResponse",)
    assert _token(fire_state, "escalationBurden", "Responder").state == "active"
    assert _token(fire_state, "consumerBurden", "EscalationTarget").state == "pending"

    # Now the real respondToEscalation action — not a _transition() shortcut.
    new_state, record = advance(fire_state, "respondToEscalation", rt._spec, "Responder")

    assert record.outcome == "ok"
    assert record.effects == (
        "discharged burden 'escalationBurden'",
        "event 'escalationNotified' triggered activation of 'consumerBurden'",
    )

    assert _token(new_state, "escalationBurden", "Responder").state == "discharged"
    assert _token(new_state, "consumerBurden", "EscalationTarget").state == "active"
