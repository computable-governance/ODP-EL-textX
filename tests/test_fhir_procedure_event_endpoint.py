"""
Layer 1 -> Layer 3 integration test for FHIR Procedure event ingestion via
POST /fhir/procedure-events (R37b, live half of DN_009 §2.5's static/live
split; R37a, fhir_mapper.py, is the static provenance-only half).

Unlike tests/test_fhir_event_handler.py (which switches to the hand-authored
"referral" scenario — a fixed authorization name that scenario already
declares), R37b's whole point is discharging a burden fhir_mapper.py's R05/
R07 rule generates, named from a ServiceRequest id — no hand-authored
scenario has a burden shaped that way. So this file builds its Runtime
directly from tests/fixtures/procedure_fulfilment_bundle.json (the same
fixture R37a's own test file uses) via FHIRConsentMapper.map_bundle() ->
parse_string() -> Runtime.build_from_spec(), then monkeypatches el_api's
module-level _runtime/_active_community to point at it — closing the loop
from R37a's static output to R37b's live discharge through the real
generated .el text, not a synthetic probe.

Since the "mapper-generated burdens are declared but never granted"
fix (docs/CONCEPTS_INDEX.md, 2026-08-30 — the R05-R08 path specifically),
the generated community now emits a real `holds` clause for each burden
whose accountable party resolves to a declared object, so
Runtime.build_from_spec() grants a real live TokenInstance for
Id401Obligation (held by RiverbendClinic001) straight out of the mapper —
no manual injection needed any more. This means the FIRST live
procedure_event call now produces a genuine "discharged" transition, and
a SECOND call is what exercises discharge_burden()'s "already discharged"
idempotent no-op path (AM-68) — the reverse ordering from before this fix,
when the first call always hit the no-live-instance no-op because nothing
was ever granted at construction.
"""
import importlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "procedure_fulfilment_bundle.json"
GENERATED_COMMUNITY = "ProcedureFulfilmentBundle001Community"


def _build_procedure_fulfilment_runtime():
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
    the R37a fixture's generated spec (not one of the standard scenario
    builders — none of them have a mapper-shaped burden name)."""
    import el_api
    importlib.reload(el_api)
    el_api._runtime = _build_procedure_fulfilment_runtime()
    el_api._active_community = GENERATED_COMMUNITY
    return el_api


def _procedure(status: str, sr_ref: str = "ServiceRequest/401", procedure_id: str = "proc-1") -> dict:
    return {
        "resourceType": "Procedure",
        "id": procedure_id,
        "status": status,
        "basedOn": [{"reference": sr_ref}],
    }


def test_procedure_completed_discharges_the_mapper_granted_burden(api):
    """Straight out of the mapper: Id401Obligation is already a real, live,
    'active' TokenInstance held by RiverbendClinic001 (the holds-clause fix)
    — no manual injection needed. The first live procedure_event call
    produces a genuine 'discharged' transition."""
    resp = api.procedure_event(_procedure("completed"))

    assert resp.action_taken == "discharged"
    assert resp.burden_name == "Id401Obligation"
    assert resp.fhir_provenance == "proc-1"
    assert resp.outcome == "ok"
    assert resp.authority == "RiverbendClinic001"
    assert resp.effects and "Id401Obligation" in resp.effects[0]
    assert resp.tick is not None
    assert resp.updated_world is not None

    after = [t for t in api._runtime.current_state().tokens if t.token_name == "Id401Obligation"]
    assert after and after[0].state == "discharged"


def test_procedure_completed_second_call_is_idempotent_already_discharged(api):
    """A second live procedure_event call against the same (now-discharged)
    burden exercises discharge_burden()'s idempotent no-op path (AM-68) —
    reported as 'already_discharged', not an error."""
    first = api.procedure_event(_procedure("completed", procedure_id="proc-1"))
    assert first.action_taken == "discharged"

    second = api.procedure_event(_procedure("completed", procedure_id="proc-2"))

    assert second.action_taken == "already_discharged"
    assert second.burden_name == "Id401Obligation"
    assert second.outcome == "ok"
    assert second.effects == []

    after = [t for t in api._runtime.current_state().tokens if t.token_name == "Id401Obligation"]
    assert after and after[0].state == "discharged"


def test_procedure_non_completed_status_is_no_op(api):
    resp = api.procedure_event(_procedure("in-progress"))

    assert resp.action_taken == "no_op"
    assert resp.burden_name is None
    assert resp.tick is None
    assert resp.updated_world is None


def test_procedure_unknown_burden_returns_200_not_error(api):
    """basedOn resolves to ServiceRequest/999 — not in the fixture bundle at
    all, so its derived burden name isn't declared anywhere in the spec.
    Unlike consent_event's fixed-name 404 precheck, this is a normal 200
    response — the target is only ever knowable per-call."""
    resp = api.procedure_event(_procedure("completed", sr_ref="ServiceRequest/999"))

    assert resp.action_taken == "unknown_burden"
    # Gated the same way as ConsentEventResponse's own no-op fields — the
    # derived name still appears in `message`, just not as a structured
    # field outside the real/idempotent-discharge cases.
    assert resp.burden_name is None
    assert "Id999Obligation" in resp.message
    assert resp.tick is None


def test_procedure_missing_id_returns_400(api):
    with pytest.raises(HTTPException) as exc:
        api.procedure_event({"resourceType": "Procedure", "status": "completed"})
    assert exc.value.status_code == 400


def test_procedure_missing_status_returns_400(api):
    with pytest.raises(HTTPException) as exc:
        api.procedure_event({"resourceType": "Procedure", "id": "proc-x"})
    assert exc.value.status_code == 400
