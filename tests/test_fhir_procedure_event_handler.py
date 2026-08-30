"""
Layer 1 -> Layer 3 — fhir_event_handler.handle_procedure_event() (R37b, live
half of DN_009 §2.5's static/live split; R37a, fhir_mapper.py, is the static
provenance-only half).

Unlike handle_consent_event()/handle_encounter_event() (R31/R30/R26-R29),
which each target a single fixed, scenario-specific name, handle_procedure_
event() derives which burden to discharge dynamically, per call, from the
incoming Procedure's own basedOn -> ServiceRequest reference — using the
exact naming convention fhir_mapper.py's R05/R07 rule uses to generate that
burden in the first place: f"{_sanitize_id(f'ServiceRequest/{sr_id}')}Obligation".

Minimal inline spec via parse_string(), same throwaway-probe pattern as
tests/test_discharge_burden.py — the burden is named Id401Obligation to
mirror exactly what fhir_mapper.py would generate for ServiceRequest/401
(_sanitize_id("ServiceRequest/401") == "Id401", since a leading digit gets
an "Id" prefix — see fhir_mapper.py's own docstring example).
"""
import pytest

from el_parser import parse_string
from el_runtime import Runtime
from fhir_event_handler import handle_procedure_event


_PROBE = """
enterprise specification ProcedureEventProbe

party Holder {
    holds Id401Obligation
    holds Id402Obligation
}

burden Id401Obligation {
    state: active
    discharge_mode: eventual
}

permit Id402Obligation {
    state: active
}
"""


def _build_probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


def _token(state, name):
    return next(t for t in state.tokens if t.token_name == name)


def _procedure(status: str, sr_ref: str = "ServiceRequest/401", procedure_id: str = "proc-1") -> dict:
    return {
        "resourceType": "Procedure",
        "id": procedure_id,
        "status": status,
        "basedOn": [{"reference": sr_ref}],
    }


def test_completed_procedure_discharges_the_derived_burden():
    rt = _build_probe_runtime()
    assert _token(rt.current_state(), "Id401Obligation").state == "active"

    result = handle_procedure_event(_procedure("completed"), rt)

    assert result.action_taken == "discharged"
    assert result.burden_name == "Id401Obligation"
    assert result.fhir_provenance == "proc-1"
    assert result.transition is not None
    assert result.transition.discharged == ("Id401Obligation",)
    assert _token(rt.current_state(), "Id401Obligation").state == "discharged"


def test_already_discharged_burden_is_idempotent_no_op():
    rt = _build_probe_runtime()
    handle_procedure_event(_procedure("completed"), rt)
    assert _token(rt.current_state(), "Id401Obligation").state == "discharged"

    result = handle_procedure_event(_procedure("completed", procedure_id="proc-2"), rt)

    assert result.action_taken == "already_discharged"
    assert result.burden_name == "Id401Obligation"
    assert result.transition is not None
    assert result.transition.discharged == ()
    assert result.transition.effects == ()
    assert _token(rt.current_state(), "Id401Obligation").state == "discharged"


def test_non_completed_status_is_a_no_op():
    rt = _build_probe_runtime()

    result = handle_procedure_event(_procedure("in-progress"), rt)

    assert result.action_taken == "no_op"
    assert result.burden_name is None
    assert result.transition is None
    assert _token(rt.current_state(), "Id401Obligation").state == "active"


def test_completed_with_no_service_request_based_on_is_a_no_op():
    rt = _build_probe_runtime()
    procedure = {
        "resourceType": "Procedure",
        "id": "proc-no-basedon",
        "status": "completed",
        "basedOn": [],
    }

    result = handle_procedure_event(procedure, rt)

    assert result.action_taken == "no_op"
    assert result.burden_name is None
    assert result.transition is None


def test_completed_procedure_targeting_undeclared_burden_is_unknown_burden():
    """basedOn resolves to ServiceRequest/999, whose derived burden name
    (Id999Obligation) is not declared anywhere in the probe spec."""
    rt = _build_probe_runtime()

    result = handle_procedure_event(_procedure("completed", sr_ref="ServiceRequest/999"), rt)

    assert result.action_taken == "unknown_burden"
    assert result.burden_name == "Id999Obligation"
    assert result.transition is None
    assert "Id999Obligation" in result.message


def test_completed_procedure_targeting_a_permit_name_is_unknown_burden():
    """basedOn resolves to ServiceRequest/402, whose derived name
    (Id402Obligation) IS declared in the probe spec — but as a permit, not
    a burden. discharge_burden() (AM-68) rejects a wrong-kind token with
    KeyError exactly like an undeclared name; this handler collapses both
    into the same "unknown_burden" outcome."""
    rt = _build_probe_runtime()

    result = handle_procedure_event(_procedure("completed", sr_ref="ServiceRequest/402"), rt)

    assert result.action_taken == "unknown_burden"
    assert result.burden_name == "Id402Obligation"
    assert result.transition is None
    assert _token(rt.current_state(), "Id402Obligation").state == "active"


def test_missing_id_raises_value_error():
    rt = _build_probe_runtime()
    with pytest.raises(ValueError):
        handle_procedure_event({"resourceType": "Procedure", "status": "completed"}, rt)


def test_missing_status_raises_value_error():
    rt = _build_probe_runtime()
    with pytest.raises(ValueError):
        handle_procedure_event({"resourceType": "Procedure", "id": "proc-x"}, rt)
