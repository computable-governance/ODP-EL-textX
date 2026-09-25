"""
AM-99a (part 2) — Rule T11: action-emitted events fire in the static builder.

build_kripke_model()'s P6a only fired events raised by burden discharge
(fires_event), so a burden triggered_by an event that an Action emits
(emits:, AM-22) stayed WAITING forever: external_agent_access_scenario.el
dead-ended at 4 worlds with AF and EF both false.

T11 adds an edge firing the event: matching WAITING obligations become
PENDING, the action is marked occurred, no step advance. Excluded:
gated actions (requires_permit), discharging actions (a descriptor's
for_action, or emitting a descriptor's discharged_by event), and any
T11 edge while a strict obligation is actionable (same guard as T3).
Static builder only; hybrid is AM-99b (docs/el_grammar_amendments.md).
"""
from pathlib import Path

from el_kripke import ObligationState, build_kripke_model
from el_parser import parse, parse_string


_REPO = Path(__file__).resolve().parent.parent
_TOE = _REPO / "scenarios" / "terms_of_engagement" / "external_agent_access_scenario.el"


def _km_from_file(path, horizon=10):
    result = parse(path, validate=False)
    assert result.ok, result.errors
    return build_kripke_model(result.model, horizon=horizon)


def _km_from_string(src, horizon=5):
    result = parse_string(src, validate=False)
    assert result.ok, result.errors
    return build_kripke_model(result.model, horizon=horizon)


def _labels_from(km, w):
    return {km.labels[(w, s)] for s in km.successors(w)}


def _all_labels(km):
    return set(km.labels.values())


# ── The motivating scenario ──────────────────────────────────────────────────

def test_toe_no_longer_dead_ends():
    km = _km_from_file(_TOE)
    assert len(km.worlds) > 4


def test_toe_all_three_burdens_reachable():
    km = _km_from_file(_TOE)
    for oid in ("refusalRecordBurden", "refusalReviewBurden",
                "incidentNotificationBurden"):
        assert km.check_permission(oid).satisfied is True, oid


def test_toe_t11_fires_only_the_two_non_discharging_emitters():
    """refuseRequest and detectIncident are the only eligible emitters:
    recordRefusal/reviewRefusal are for_action of a burden (discharge
    fires their events via P6a), and the gated submit/read actions
    emit nothing."""
    km = _km_from_file(_TOE)
    fired = {lbl for lbl in _all_labels(km) if lbl.startswith("fire:")}
    assert fired == {
        "fire:accessRefused via refuseRequest",
        "fire:vendorIncidentDetected via detectIncident",
    }


def test_toe_review_burden_still_activated_by_discharge_cascade():
    """refusalReviewBurden is triggered_by refusalRecorded, which only
    discharging refusalRecordBurden raises (P6a) — never T11."""
    km = _km_from_file(_TOE)
    activating = {
        km.labels[(w, s)]
        for w in km.worlds for s in km.successors(w)
        if w.get_obligation("refusalReviewBurden") == ObligationState.WAITING
        and s.get_obligation("refusalReviewBurden") == ObligationState.PENDING
    }
    assert activating == {"discharge:refusalRecordBurden by ProviderAPIGateway"}


# ── Exclusions, on minimal fixtures ──────────────────────────────────────────

def _spec(action_body, extra=""):
    return f"""
enterprise specification T11Probe

party Operator

community ProbeCommunity {{
    objective: "probe T11 event firing"
    event probeEvent
    role operatorRole {{
        action emitProbe {{
            actor: operatorRole
{action_body}
        }}
    }}
}}

burden waitingBurden {{
    for_action: "respond"
    state: pending
    triggered_by: probeEvent
    discharge_mode: eventual
}}

commitment OperatorResponds {{
    by: Operator
    obligation: "respond to the probe event"
    creates_burden: waitingBurden
}}
{extra}
"""


def test_ungated_emitter_fires_and_records_activation():
    km = _km_from_string(_spec("            emits: probeEvent"))
    assert _labels_from(km, km.initial) >= {"fire:probeEvent via emitProbe"}
    fired = next(
        s for s in km.successors(km.initial)
        if km.labels[(km.initial, s)] == "fire:probeEvent via emitProbe"
    )
    assert fired.get_obligation("waitingBurden") == ObligationState.PENDING
    assert fired.has_occurred("emitProbe")
    assert fired.step == km.initial.step
    assert dict(fired.activation_steps) == {"waitingBurden": 0}
    assert km.check_permission("waitingBurden").satisfied is True


def test_gated_emitter_does_not_fire():
    km = _km_from_string(
        _spec("            requires_permit probePermit\n"
              "            emits: probeEvent",
              extra=(
                  "permit probePermit {\n"
                  '    for_action: "emitProbe"\n'
                  "    state: active\n"
                  "}\n"
              )),
    )
    assert not any(lbl.startswith("fire:") for lbl in _all_labels(km))
    assert km.check_permission("waitingBurden").satisfied is False


def test_for_action_emitter_does_not_fire():
    """An action that is some burden's for_action is a discharging
    action — its event fires via T1/P6a, never T11."""
    km = _km_from_string(
        _spec("            emits: probeEvent",
              extra=(
                  "burden emitterBurden {\n"
                  '    for_action: "emitProbe"\n'
                  "    state: pending\n"
                  "    discharge_mode: eventual\n"
                  "}\n\n"
                  "commitment OperatorEmits {\n"
                  "    by: Operator\n"
                  '    obligation: "emit the probe"\n'
                  "    creates_burden: emitterBurden\n"
                  "}\n"
              )),
    )
    assert not any(lbl.startswith("fire:") for lbl in _all_labels(km))


def test_strict_obligation_blocks_t11_until_discharged():
    """While a strict obligation is PENDING with an ACTIVE holder, T11 is
    suppressed (same guard as T3 / engine Step 3.5); once it is
    discharged, the event can fire."""
    km = _km_from_string(
        _spec("            emits: probeEvent",
              extra=(
                  "burden strictBurden {\n"
                  '    for_action: "doStrict"\n'
                  "    state: pending\n"
                  "    discharge_mode: strict\n"
                  "}\n\n"
                  "commitment OperatorStrict {\n"
                  "    by: Operator\n"
                  '    obligation: "do the strict thing"\n'
                  "    creates_burden: strictBurden\n"
                  "}\n"
              )),
    )
    assert not any(lbl.startswith("fire:") for lbl in _labels_from(km, km.initial))
    after = next(
        s for s in km.successors(km.initial)
        if km.labels[(km.initial, s)] == "discharge:strictBurden by Operator"
    )
    assert "fire:probeEvent via emitProbe" in _labels_from(km, after)


def test_emitter_of_a_discharged_by_event_does_not_fire():
    """An action whose emitted event is some burden's discharged_by is
    also a discharging action (engine Step 3 discharges via that event);
    T11 must not fire it, or dependents would activate without the
    discharge."""
    km = _km_from_string(
        _spec("            emits: probeEvent",
              extra=(
                  "burden dischargedByEventBurden {\n"
                  '    for_action: "somethingElse"\n'
                  "    state: pending\n"
                  "    discharged_by: probeEvent\n"
                  "    discharge_mode: eventual\n"
                  "}\n\n"
                  "commitment OperatorDischargesByEvent {\n"
                  "    by: Operator\n"
                  '    obligation: "discharged by the probe event"\n'
                  "    creates_burden: dischargedByEventBurden\n"
                  "}\n"
              )),
    )
    assert not any(lbl.startswith("fire:") for lbl in _all_labels(km))
