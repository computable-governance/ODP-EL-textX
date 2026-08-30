"""
Confirmation test — ServiceRequest.requester referencing a Patient
directly (touchpoint 6's "referral submitted via Consumer App" case),
against the existing R05-R08 pipeline.

Not a new rule, not a mapper code change — this test confirms the
existing pipeline already handles a Patient-direct requester correctly,
with zero new code. Unlike R38 (a genuinely new resource type), touchpoint
6's physiotherapy self-referral is still a plain ServiceRequest; the only
new shape is .requester pointing at Patient/roberts-fred instead of a
clinician/organisation.

Grounding, confirmed here with a real test rather than trusted from grep
alone: _resolve_commitment_accountable_party's case 1 ("requester does
not reference a Practitioner or PractitionerRole — return its el_id
unchanged, already resolved") fires for a Patient reference. This is
safe only because _map_patient (R02) declares every Patient resource
present in the bundle as an ELObject unconditionally — the same
blanket-declare pattern R01/R03 already give Organization/Practitioner.
The AM-72 holds-clause fix then grants the burden to that Patient object
exactly as it would any other declared object, with no special-casing
needed for "patient as accountable party."

No touchpoint-6 data exists yet on the live HAPI server (localhost:8081)
or in ~/fhir-scenarios/06-recovery-allied-health/ (checked, both empty) —
this fixture is a realistic AU-shaped bundle, following the same standard
as today's other new fixtures, continuing Fred Roberts' ConnectedCare
thread for narrative consistency with the rest of this session's real
data. Also includes a second ServiceRequest with a normal
PractitionerRole requester in the same bundle, confirming the new case
coexists correctly with the existing path rather than needing isolation
to pass.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "patient_requester_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def test_patient_direct_requester_resolves_commitment_by_to_the_patient():
    """(a) ServiceRequest/901's requester references Patient/roberts-fred
    directly — commitment.by resolves to the patient's own el_id, no
    'resolve up to an organisation' step (there is none for a
    self-submitted referral — the patient IS the accountable party)."""
    el = _generate()
    assert "commitment Id901Commitment {" in el
    block = el.split("commitment Id901Commitment {")[1].split("}")[0]
    assert "by: RobertsFred" in block


def test_patient_direct_requester_gets_a_holds_clause():
    """(b) AM-72's holds-clause pattern fires correctly for a Patient
    object exactly as it would for any other declared object — no
    special-casing needed."""
    el = _generate()
    assert "party RobertsFred" in el
    block = el.split("party RobertsFred")[1].split("party LindqvistAnya")[0]
    assert "holds Id901Obligation" in block


def test_patient_direct_requester_coexists_with_clinician_requester():
    """ServiceRequest/902 (PractitionerRole requester, same bundle)
    resolves independently to BrisbaneEndocrinology — confirms the new
    Patient-direct case doesn't interfere with the existing path."""
    el = _generate()
    block = el.split("commitment Id902Commitment {")[1].split("}")[0]
    assert "by: BrisbaneEndocrinology" in block


def test_patient_requester_bundle_parses_and_validates():
    """(c) Full parse+validate succeeds — not just plausible-looking
    text."""
    from el_parser import parse_string

    el = _generate()
    result = parse_string(el, validate=True)
    assert result.ok, f"Validation errors: {result.errors}"


def test_patient_requester_holds_clause_produces_a_real_live_token_instance():
    """(d) Building a live Runtime.build_from_spec() produces a real
    TokenInstance held by the Patient — not just plausible-looking
    `holds` text."""
    from el_parser import parse_string
    from el_runtime import Runtime

    result = parse_string(_generate(), validate=True)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)
    tokens = {t.token_name: t for t in rt.current_state().tokens}

    assert "Id901Obligation" in tokens
    assert tokens["Id901Obligation"].holder == "RobertsFred"
    assert tokens["Id901Obligation"].kind == "burden"
    assert tokens["Id901Obligation"].state == "active"
