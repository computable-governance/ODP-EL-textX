"""
AM-113 — `discharged_by` works whoever emits the event.

An emitted event discharges every active burden whose discharged_by names
it, whoever holds it; where a burden declares both, its for_action no
longer discharges it. fire_event() discharges the same way. Both Kripke
builders fire the event through T5/T11 and discharge on that edge.

The DN_019 replay (docs/design_notes/DN_019_incident_simulator_storyboard.md,
steps 2.2-2.10a) in both terms-of-engagement scenarios:
incidentNotificationBurden (holder: the operator/vendor) is discharged by
the contact's acknowledgeIncident, not by the operator's notifyIncident.
Before AM-113 it was the other way round (CONCEPTS_INDEX, "discharged_by
never fires for an event emitted by someone other than the holder").

[W-26] warns when a discharged_by event is emitted by no action.
"""
import contextlib
import io

import pytest

from el_api import (
    _SCENARIO_DEADLINE_SCALE,
    _build_external_agent_access_runtime,
    _build_public_data_portal_runtime,
)
from el_kripke import build_kripke_from_runtime
from el_parser import parse_string


_BURDEN = "incidentNotificationBurden"

_SCENARIOS = {
    "public_data_portal": dict(
        build=_build_public_data_portal_runtime, gateway="AgencyGateway",
        contact="AgencySecurityContact", operator="AgentOperator",
        agent="ExternalAIAgent", read="readPublishedDataset",
        detected="operatorIncidentDetected"),
    "external_agent_access": dict(
        build=_build_external_agent_access_runtime, gateway="ProviderAPIGateway",
        contact="ProviderSecurityContact", operator="VendorOrg",
        agent="VendorReferralAgent", read="submitServiceRequest",
        detected="vendorIncidentDetected"),
}


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _state(rt, name=_BURDEN):
    (tok,) = [t for t in rt.current_state().tokens if t.token_name == name]
    return tok.state


def _after_detection(s):
    """DN_019 steps 2.2, 2.4, 2.8 and 2.9: refusal recorded and reviewed,
    then the incident detected (the notification clock starts)."""
    rt = _quiet(s["build"])
    for action, actor in (("refuseRequest", s["gateway"]), ("recordRefusal", s["gateway"]),
                          ("reviewRefusal", s["contact"]), ("detectIncident", s["operator"])):
        assert rt.advance(action, actor).outcome == "ok", action
    assert _state(rt) == "active"
    return rt


@pytest.fixture(params=sorted(_SCENARIOS))
def scenario(request):
    return _SCENARIOS[request.param]


# ── Engine: the DN_019 replay ────────────────────────────────────────────────

def test_notify_alone_leaves_the_burden_active(scenario):
    rt = _after_detection(scenario)
    rec = rt.advance("notifyIncident", scenario["operator"])
    assert rec.outcome == "ok"
    assert rec.discharged == ()
    assert _state(rt) == "active"


def test_contact_acknowledgement_discharges_it(scenario):
    rt = _after_detection(scenario)
    rt.advance("notifyIncident", scenario["operator"])
    rec = rt.advance("acknowledgeIncident", scenario["contact"])
    assert rec.outcome == "ok"
    assert rec.discharged == (_BURDEN,)
    assert _state(rt) == "discharged"
    (tok,) = [t for t in rt.current_state().tokens if t.token_name == _BURDEN]
    assert tok.holder == scenario["operator"]  # discharged in the holder's name


def test_acknowledgement_during_strict_freeze_goes_through(scenario):
    """refusalRecordBurden (strict) is actionable after a refusal. The
    acknowledgement discharges a burden, so Step 3.5 lets it through;
    an action that discharges nothing is still blocked."""
    rt = _quiet(scenario["build"])
    assert rt.advance("detectIncident", scenario["operator"]).outcome == "ok"
    assert rt.advance("refuseRequest", scenario["gateway"]).outcome == "ok"
    blocked = rt.advance(scenario["read"], scenario["agent"])
    assert blocked.outcome == "blocked"
    assert "strict burden 'refusalRecordBurden'" in blocked.reason
    rec = rt.advance("acknowledgeIncident", scenario["contact"])
    assert rec.outcome == "ok", rec.reason
    assert rec.discharged == (_BURDEN,)
    assert _state(rt, "refusalRecordBurden") == "active"


def test_acknowledgement_after_violation_has_no_effect(scenario):
    """Step 2.10b: once violated (and lateNotificationResponse fired) the
    burden is no longer active, so a late acknowledgement discharges
    nothing."""
    rt = _after_detection(scenario)
    rt.advance_clock(4320)  # "72 hours", one step per minute (AM-111)
    assert _BURDEN in rt.check_live_violations().violations
    rt.fire_violation_responses()
    rec = rt.advance("acknowledgeIncident", scenario["contact"])
    assert rec.discharged == ()
    assert _state(rt) == "violated"


# ── Engine: fire_event() ─────────────────────────────────────────────────────

def test_fire_event_discharges(scenario):
    rt = _after_detection(scenario)
    rec = rt.fire_event("incidentAcknowledged", source="external-ack")
    assert rec.outcome == "ok"
    assert rec.discharged == (_BURDEN,)
    assert f"discharged burden '{_BURDEN}'" in rec.effects
    assert _state(rt) == "discharged"


def test_fire_event_that_discharges_passes_the_strict_guard(scenario):
    rt = _quiet(scenario["build"])
    rt.advance("detectIncident", scenario["operator"])
    rt.advance("refuseRequest", scenario["gateway"])
    assert rt.fire_event("incidentAcknowledged").discharged == (_BURDEN,)


def test_fire_event_that_discharges_nothing_is_still_blocked(scenario):
    rt = _quiet(scenario["build"])
    rt.advance("refuseRequest", scenario["gateway"])
    rec = rt.fire_event(scenario["detected"])
    assert rec.outcome == "blocked"
    assert "strict burden 'refusalRecordBurden'" in rec.reason


# ── Verifier: the discharge is the acknowledgement ──────────────────────────

@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_hybrid_after_detection_discharges_through_acknowledgement(name):
    """After step 2.9, at the scenario's configured k: still "not
    compelled, detectable", but the EF witness is now the contact's
    acknowledgement, not the holder's notifyIncident."""
    rt = _after_detection(_SCENARIOS[name])
    km = _quiet(build_kripke_from_runtime, rt, horizon=10,
                deadline_scale=_SCENARIO_DEADLINE_SCALE[name])
    af, ef = km.check_obligation(_BURDEN), km.check_permission(_BURDEN)
    assert af.satisfied is False and af.status is None
    assert ef.satisfied is True
    labels = [label for _, label in ef.witness_path]
    assert f"discharge:{_BURDEN} via acknowledgeIncident (incidentAcknowledged)" in labels
    assert not any(l.startswith(f"discharge:{_BURDEN} by ") for l in km.labels.values())


# ── Validator: [W-26] ────────────────────────────────────────────────────────

_W26_PROBE = """
enterprise specification W26Probe

party Operator

burden unemittedBurden {
    for_action: "doIt"
    state: active
    discharged_by: neverEmitted
}

burden emittedBurden {
    for_action: "doOther"
    state: active
    discharged_by: emitted
}

community ProbeCommunity {
    objective: "probe W-26"
    event neverEmitted
    event emitted
    role operatorRole {
        action doIt { actor: operatorRole }
        action emitIt { actor: operatorRole emits: emitted }
        burden inlineBurden {
            for_action: "doInline"
            state: active
            discharged_by: neverEmitted
        }
    }
}

commitment C1 { by: Operator obligation: "do it" creates_burden: unemittedBurden }
commitment C2 { by: Operator obligation: "do other" creates_burden: emittedBurden }
"""


def _w26(src):
    result = _quiet(parse_string, src)
    return [w for w in result.warnings if w.startswith("[W-26]")]


def test_w26_names_burdens_whose_event_no_action_emits():
    warnings = _w26(_W26_PROBE)
    assert len(warnings) == 2
    assert any("'unemittedBurden'" in w for w in warnings)
    assert any("'inlineBurden'" in w for w in warnings)
    assert all("'neverEmitted'" in w and "can never be discharged by its event" in w
               for w in warnings)


@pytest.mark.parametrize("path", [
    "scenarios/terms_of_engagement/public_data_portal_scenario.el",
    "scenarios/terms_of_engagement/external_agent_access_scenario.el",
])
def test_w26_silent_on_terms_of_engagement(path):
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / path).read_text()
    assert _w26(src) == []
