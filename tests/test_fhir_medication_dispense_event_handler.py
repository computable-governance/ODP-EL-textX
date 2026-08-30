"""
Layer 1 -> Layer 3 — fhir_event_handler.handle_medication_dispense_event()
(R38b, live half of touchpoint 5's static/live split; R38a, fhir_mapper.py,
is the static provenance-only half).

Structurally identical to handle_procedure_event() (R37b) — same
dynamic burden_name derivation (no fixed target, derived per call from
the incoming MedicationDispense's own authorizingPrescription ->
MedicationRequest reference), same discharged/already_discharged/
unknown_burden split, same naming convention fhir_mapper.py's R38 rule
uses: f"{_sanitize_id(f'MedicationRequest/{mr_id}')}Obligation".

Minimal inline spec via parse_string(), same throwaway-probe pattern as
tests/test_fhir_procedure_event_handler.py — the burden is named
Id701Obligation to mirror exactly what fhir_mapper.py would generate for
MedicationRequest/701.
"""
import pytest

from el_parser import parse_string
from el_runtime import Runtime
from fhir_event_handler import handle_medication_dispense_event


_PROBE = """
enterprise specification MedicationDispenseEventProbe

party Holder {
    holds Id701Obligation
    holds Id702Obligation
}

burden Id701Obligation {
    state: active
    discharge_mode: eventual
}

permit Id702Obligation {
    state: active
}
"""


def _build_probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


def _token(state, name):
    return next(t for t in state.tokens if t.token_name == name)


def _dispense(status: str, mr_ref: str = "MedicationRequest/701", dispense_id: str = "disp-1") -> dict:
    return {
        "resourceType": "MedicationDispense",
        "id": dispense_id,
        "status": status,
        "authorizingPrescription": [{"reference": mr_ref}],
    }


def test_completed_dispense_discharges_the_derived_burden():
    rt = _build_probe_runtime()
    assert _token(rt.current_state(), "Id701Obligation").state == "active"

    result = handle_medication_dispense_event(_dispense("completed"), rt)

    assert result.action_taken == "discharged"
    assert result.burden_name == "Id701Obligation"
    assert result.fhir_provenance == "disp-1"
    assert result.transition is not None
    assert result.transition.discharged == ("Id701Obligation",)
    assert _token(rt.current_state(), "Id701Obligation").state == "discharged"


def test_already_discharged_burden_is_idempotent_no_op():
    rt = _build_probe_runtime()
    handle_medication_dispense_event(_dispense("completed"), rt)
    assert _token(rt.current_state(), "Id701Obligation").state == "discharged"

    result = handle_medication_dispense_event(_dispense("completed", dispense_id="disp-2"), rt)

    assert result.action_taken == "already_discharged"
    assert result.burden_name == "Id701Obligation"
    assert result.transition is not None
    assert result.transition.discharged == ()
    assert result.transition.effects == ()


def test_declined_status_is_a_no_op():
    """'declined' is medicationdispense-status's explicit negative — the
    dispense never happened, no discharge attempted."""
    rt = _build_probe_runtime()

    result = handle_medication_dispense_event(_dispense("declined"), rt)

    assert result.action_taken == "no_op"
    assert result.burden_name is None
    assert result.transition is None
    assert _token(rt.current_state(), "Id701Obligation").state == "active"


def test_completed_with_no_medication_request_authorizing_prescription_is_no_op():
    rt = _build_probe_runtime()
    dispense = {
        "resourceType": "MedicationDispense",
        "id": "disp-no-auth",
        "status": "completed",
        "authorizingPrescription": [],
    }

    result = handle_medication_dispense_event(dispense, rt)

    assert result.action_taken == "no_op"
    assert result.burden_name is None
    assert result.transition is None


def test_completed_dispense_targeting_undeclared_burden_is_unknown_burden():
    """authorizingPrescription resolves to MedicationRequest/999, whose
    derived burden name (Id999Obligation) is not declared anywhere in the
    probe spec."""
    rt = _build_probe_runtime()

    result = handle_medication_dispense_event(
        _dispense("completed", mr_ref="MedicationRequest/999"), rt
    )

    assert result.action_taken == "unknown_burden"
    assert result.burden_name == "Id999Obligation"
    assert result.transition is None
    assert "Id999Obligation" in result.message


def test_completed_dispense_targeting_a_permit_name_is_unknown_burden():
    """authorizingPrescription resolves to MedicationRequest/702, whose
    derived name (Id702Obligation) IS declared — but as a permit, not a
    burden. discharge_burden() (AM-68) rejects a wrong-kind token with
    KeyError; this handler collapses it into the same "unknown_burden"
    outcome as an undeclared name."""
    rt = _build_probe_runtime()

    result = handle_medication_dispense_event(
        _dispense("completed", mr_ref="MedicationRequest/702"), rt
    )

    assert result.action_taken == "unknown_burden"
    assert result.burden_name == "Id702Obligation"
    assert result.transition is None
    assert _token(rt.current_state(), "Id702Obligation").state == "active"


def test_missing_id_raises_value_error():
    rt = _build_probe_runtime()
    with pytest.raises(ValueError):
        handle_medication_dispense_event(
            {"resourceType": "MedicationDispense", "status": "completed"}, rt
        )


def test_missing_status_raises_value_error():
    rt = _build_probe_runtime()
    with pytest.raises(ValueError):
        handle_medication_dispense_event(
            {"resourceType": "MedicationDispense", "id": "disp-x"}, rt
        )
