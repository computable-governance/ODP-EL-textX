"""
Layer 2/3 — coverage for the AM-22 triggered_by/EventDecl event-activation
mechanism, previously implemented but entirely untested (see
docs/CONCEPTS_INDEX.md "Event-triggered activation (Step 7c) — implemented
but untested"). Covers, in order:

  1. _activate_triggered_tokens() (el_engine.py) directly — the helper
     extracted from advance() Step 7c, now shared with Runtime.fire_event().
  2. advance() Step 7c end-to-end — an Action's `emits` activating a
     matching `triggered_by` token, via a minimal synthetic spec (no
     scenario in the repo currently pairs `emits` with a matching
     `triggered_by`: referral_scenario.el's own `emits: referralSubmitted`
     has no consumer).
  3. Runtime.fire_event() (el_runtime.py) directly — the FHIR-facing
     direct-call path added alongside Step 7c's refactor.
  4/5. fhir_event_handler.handle_encounter_event() round-trip — the
     status=finished activation path and the status=cancelled/
     entered-in-error ValueError path.

Tests 3-5 use referral_scenario.el via the real _build_referral_runtime()
builder (not hand-rolled enroll()/grant_token() calls) to stay consistent
with tests/test_scenario_builders.py's drift-prevention rationale, then
override only referralInitiationBurden's state to 'pending' so the
transition being tested is real (pending -> active), not a same-value
active -> active no-op.
"""
import pytest

from el_api import _build_referral_runtime
from el_engine import (
    TokenInstance,
    _activate_triggered_tokens,
    advance,
    enroll,
    grant_token,
    initial_state,
)
from el_parser import parse_string
from el_runtime import Runtime
from fhir_event_handler import handle_encounter_event


@pytest.fixture(scope="module")
def spec():
    """The parsed referral_scenario.el model, via the real scenario builder
    rather than a second independent parse() call, so it can never drift
    from whatever _build_referral_runtime() actually loads."""
    return _build_referral_runtime()._spec


def _with_pending_referral_burden(runtime: Runtime) -> Runtime:
    """
    Return a NEW Runtime, built from `runtime`'s real state/spec, with
    referralInitiationBurden's state forced to 'pending'. All other fields
    on that token, and every other actor/token, are copied verbatim from
    the real builder output — only `state` is overridden, so nothing here
    can drift from referral_scenario.el's actual declarations.
    """
    state = runtime.current_state()
    new_tokens = tuple(
        TokenInstance(
            token_name=t.token_name,
            kind=t.kind,
            holder=t.holder,
            state="pending",
            discharge_mode=t.discharge_mode,
            priority=t.priority,
            deadline=t.deadline,
            for_action=t.for_action,
        )
        if t.token_name == "referralInitiationBurden" else t
        for t in state.tokens
    )
    return Runtime(state.with_tokens(new_tokens), runtime._spec)


def _referral_burden_state(runtime: Runtime, token_name: str) -> str:
    return [
        t for t in runtime.current_state().tokens if t.token_name == token_name
    ][0].state


# ── 1. _activate_triggered_tokens() direct ─────────────────────────────────────

def test_activate_triggered_tokens_activates_matching_and_skips_others(spec):
    pending = TokenInstance(
        token_name="referralInitiationBurden", kind="burden", holder="GPClinician",
        state="pending", discharge_mode="strict", priority="critical",
        deadline="48 hours from clinical decision", for_action="initiateReferral",
    )
    unrelated = TokenInstance(
        token_name="clinicalHandoverBurden", kind="burden", holder="GPClinician",
        state="pending", discharge_mode="eventual", priority="normal",
        deadline="referral episode", for_action="provideHandover",
    )

    tokens, log_lines = _activate_triggered_tokens(
        spec, [pending, unrelated], "encounterConcluded"
    )

    by_name = {t.token_name: t for t in tokens}
    assert by_name["referralInitiationBurden"].state == "active"
    # clinicalHandoverBurden has no triggered_by at all -> must be untouched
    assert by_name["clinicalHandoverBurden"].state == "pending"
    assert log_lines == [
        "event 'encounterConcluded' triggered activation of 'referralInitiationBurden'"
    ]


def test_activate_triggered_tokens_unmatched_event_is_untouched_noop(spec):
    pending = TokenInstance(
        token_name="referralInitiationBurden", kind="burden", holder="GPClinician",
        state="pending", discharge_mode="strict", priority="critical",
        deadline="48 hours from clinical decision", for_action="initiateReferral",
    )

    tokens, log_lines = _activate_triggered_tokens(spec, [pending], "noSuchEvent")

    assert tokens[0].state == "pending"
    assert log_lines == []


# ── 2. advance() Step 7c end-to-end, via a minimal synthetic spec ─────────────

_MINIMAL_TRIGGER_SPEC = """
enterprise specification MinimalTriggerTest
    description: "Isolated regression fixture for el_engine.py Step 7c (emits -> triggered_by)"

community TestCommunity
    description: "One action with emits, one burden with triggered_by, nothing else"
    {
        objective: "Exercise event-triggered activation in isolation from referral_scenario.el"

        event testEvent
            description: "Fired when testAction runs"

        role testRole
            description: "Single role performing testAction"
            {
                action testAction {
                    description: "Emits testEvent"
                    actor: testRole
                    emits: testEvent
                }
            }
    }

burden waitingBurden {
    for_action: "someOtherAction"
    state: pending
    triggered_by: testEvent
    discharge_mode: eventual
    priority: normal
    description: "Should transition pending -> active when testEvent fires via testAction's emits"
}
"""


def test_step7c_activates_token_via_action_emits():
    """
    Regression coverage for the Step 2 refactor (Step 7c's inline logic ->
    _activate_triggered_tokens() call): confirms an Action's `emits` still
    activates a matching `triggered_by` token through advance() — the
    original AM-22 behavior, never actually exercised by a test before
    this refactor. A minimal synthetic spec is used because no scenario in
    the repo currently pairs an `emits` with a matching `triggered_by`.
    """
    result = parse_string(_MINIMAL_TRIGGER_SPEC, validate=False)
    assert result.ok, result.errors
    minimal_spec = result.model

    state = initial_state()
    state = enroll(state, "Tester", role_name="testRole")
    state = grant_token(state, TokenInstance(
        token_name="waitingBurden", kind="burden", holder="Tester",
        state="pending", discharge_mode="eventual", priority="normal",
        deadline=None, for_action="someOtherAction",
    ))

    pre = [t for t in state.tokens if t.token_name == "waitingBurden"][0]
    assert pre.state == "pending"

    new_state, record = advance(state, "testAction", minimal_spec, "Tester")

    assert record.outcome == "ok"
    post = [t for t in new_state.tokens if t.token_name == "waitingBurden"][0]
    assert post.state == "active"
    assert record.effects == (
        "event 'testEvent' triggered activation of 'waitingBurden'",
    )


# ── 3. Runtime.fire_event() direct ─────────────────────────────────────────────

def test_fire_event_transitions_pending_burden_to_active():
    runtime = _with_pending_referral_burden(_build_referral_runtime())
    assert _referral_burden_state(runtime, "referralInitiationBurden") == "pending"

    record = runtime.fire_event("encounterConcluded", source="fhir:Encounter/enc-test")

    assert record.outcome == "ok"
    assert record.actor_name == "fhir:Encounter/enc-test"
    assert record.action_name == "fire_event:encounterConcluded"
    assert record.effects == (
        "event 'encounterConcluded' triggered activation of 'referralInitiationBurden'",
    )
    assert _referral_burden_state(runtime, "referralInitiationBurden") == "active"
    assert runtime.current_state().tick == 1


def test_fire_event_default_source_and_no_match_is_harmless():
    runtime = _with_pending_referral_burden(_build_referral_runtime())

    record = runtime.fire_event("noSuchEvent")

    assert record.outcome == "ok"
    assert record.actor_name == "external"  # default `source`
    assert record.effects == ()
    assert _referral_burden_state(runtime, "referralInitiationBurden") == "pending"


# ── 4/5. handle_encounter_event() round-trip ───────────────────────────────────

def test_handle_encounter_event_finished_activates_burden():
    runtime = _with_pending_referral_burden(_build_referral_runtime())

    encounter = {"resourceType": "Encounter", "id": "enc-round-trip", "status": "finished"}
    resp = handle_encounter_event(encounter, runtime)

    assert resp.action_taken == "fired"
    assert resp.fhir_provenance == "enc-round-trip"
    assert resp.event_name == "encounterConcluded"
    assert resp.transition is not None
    assert resp.transition.effects == (
        "event 'encounterConcluded' triggered activation of 'referralInitiationBurden'",
    )
    assert _referral_burden_state(runtime, "referralInitiationBurden") == "active"


def test_handle_encounter_event_finished_no_match_is_distinguished():
    """
    Locks in that a status=finished Encounter whose event matches no
    token's triggered_by is reported as "fired_no_match", not silently
    collapsed into the same "fired" outcome as a genuine activation.
    """
    runtime = _with_pending_referral_burden(_build_referral_runtime())

    encounter = {"resourceType": "Encounter", "id": "enc-no-match", "status": "finished"}
    resp = handle_encounter_event(encounter, runtime, event_name="noSuchEventAnywhere")

    assert resp.action_taken == "fired_no_match"
    assert resp.transition is not None
    assert resp.transition.effects == ()
    assert _referral_burden_state(runtime, "referralInitiationBurden") == "pending"


@pytest.mark.parametrize("status", ["cancelled", "entered-in-error"])
def test_handle_encounter_event_terminal_status_raises(status):
    runtime = _build_referral_runtime()
    encounter = {"resourceType": "Encounter", "id": f"enc-{status}", "status": status}

    with pytest.raises(ValueError, match="bootstrap-time integrity gap"):
        handle_encounter_event(encounter, runtime)


def test_handle_encounter_event_missing_id_raises():
    runtime = _build_referral_runtime()
    with pytest.raises(ValueError, match="missing required 'id'"):
        handle_encounter_event({"resourceType": "Encounter", "status": "finished"}, runtime)


def test_handle_encounter_event_missing_status_raises():
    runtime = _build_referral_runtime()
    with pytest.raises(ValueError, match="missing required 'status'"):
        handle_encounter_event({"resourceType": "Encounter", "id": "enc-x"}, runtime)
