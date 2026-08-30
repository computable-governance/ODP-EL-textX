"""
Layer 1 -> Layer 3 integration test for FHIR MedicationDispense event
ingestion via POST /fhir/medication-dispense-events (R38b, live half of
touchpoint 5's static/live split; R38a, fhir_mapper.py, is the static
provenance-only half).

Mirrors tests/test_fhir_procedure_event_endpoint.py exactly. Builds its
Runtime directly from tests/fixtures/medication_dispense_bundle.json (the
same fixture R38/R38a's own test file uses) via
FHIRConsentMapper.map_bundle() -> parse_string() -> Runtime.build_from_spec(),
then monkeypatches el_api's module-level _runtime/_active_community to
point at it — closing the loop from R38a's static output to R38b's live
discharge through the real generated .el text, not a synthetic probe.

Since the holds-clause fix (AM-72), the generated community already emits
a real `holds` clause for MedicationRequest/701's burden, so
Runtime.build_from_spec() grants a real live TokenInstance for
Id701Obligation (held by HarbourviewPharmacy001) straight out of the
mapper — the first live medication_dispense_event call produces a genuine
"discharged" transition, and a second call exercises the idempotent
"already_discharged" no-op path (AM-68).
"""
import importlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "medication_dispense_bundle.json"
GENERATED_COMMUNITY = "MedicationDispenseBundle001Community"


def _build_medication_dispense_runtime():
    import sys
    sys.path.insert(0, str(REPO_ROOT / "toolchain"))
    from fhir_mapper import FHIRConsentMapper
    from el_parser import parse_string
    from el_runtime import Runtime

    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    el_text = mapper.map_bundle(bundle)
    result = parse_string(el_text, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


@pytest.fixture
def api():
    """Fresh el_api module, _runtime replaced with one built directly from
    the R38/R38a fixture's generated spec (not one of the standard
    scenario builders — none of them have a mapper-shaped burden name)."""
    import el_api
    importlib.reload(el_api)
    el_api._runtime = _build_medication_dispense_runtime()
    el_api._active_community = GENERATED_COMMUNITY
    return el_api


def _dispense(status: str, mr_ref: str = "MedicationRequest/701", dispense_id: str = "disp-1") -> dict:
    return {
        "resourceType": "MedicationDispense",
        "id": dispense_id,
        "status": status,
        "authorizingPrescription": [{"reference": mr_ref}],
    }


def test_dispense_completed_discharges_the_mapper_granted_burden(api):
    """Straight out of the mapper: Id701Obligation is already a real, live,
    'active' TokenInstance held by HarbourviewPharmacy001 (the holds-clause
    fix) — no manual injection needed. The first live
    medication_dispense_event call produces a genuine 'discharged'
    transition."""
    resp = api.medication_dispense_event(_dispense("completed"))

    assert resp.action_taken == "discharged"
    assert resp.burden_name == "Id701Obligation"
    assert resp.fhir_provenance == "disp-1"
    assert resp.outcome == "ok"
    assert resp.authority == "HarbourviewPharmacy001"
    assert resp.effects and "Id701Obligation" in resp.effects[0]
    assert resp.tick is not None
    assert resp.updated_world is not None

    after = [t for t in api._runtime.current_state().tokens if t.token_name == "Id701Obligation"]
    assert after and after[0].state == "discharged"


def test_dispense_completed_second_call_is_idempotent_already_discharged(api):
    first = api.medication_dispense_event(_dispense("completed", dispense_id="disp-1"))
    assert first.action_taken == "discharged"

    second = api.medication_dispense_event(_dispense("completed", dispense_id="disp-2"))

    assert second.action_taken == "already_discharged"
    assert second.burden_name == "Id701Obligation"
    assert second.outcome == "ok"
    assert second.effects == []

    after = [t for t in api._runtime.current_state().tokens if t.token_name == "Id701Obligation"]
    assert after and after[0].state == "discharged"


def test_dispense_declined_status_is_no_op(api):
    resp = api.medication_dispense_event(_dispense("declined"))

    assert resp.action_taken == "no_op"
    assert resp.burden_name is None
    assert resp.tick is None
    assert resp.updated_world is None


def test_dispense_unknown_burden_returns_200_not_error(api):
    """authorizingPrescription resolves to MedicationRequest/999 — not in
    the fixture bundle at all, so its derived burden name isn't declared
    anywhere in the spec. Unlike consent_event's fixed-name 404 precheck,
    this is a normal 200 response — the target is only ever knowable
    per-call."""
    resp = api.medication_dispense_event(_dispense("completed", mr_ref="MedicationRequest/999"))

    assert resp.action_taken == "unknown_burden"
    assert resp.burden_name is None
    assert "Id999Obligation" in resp.message
    assert resp.tick is None


def test_dispense_missing_id_returns_400(api):
    with pytest.raises(HTTPException) as exc:
        api.medication_dispense_event({"resourceType": "MedicationDispense", "status": "completed"})
    assert exc.value.status_code == 400


def test_dispense_missing_status_returns_400(api):
    with pytest.raises(HTTPException) as exc:
        api.medication_dispense_event({"resourceType": "MedicationDispense", "id": "disp-x"})
    assert exc.value.status_code == 400
