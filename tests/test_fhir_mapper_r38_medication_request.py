"""
R38 verification — MedicationRequest -> Commitment + Burden, and R38a
static MedicationDispense-fulfilment provenance (touchpoint 5, medicines
management).

Mirrors R05-R08's ServiceRequest -> Commitment + Burden pipeline and
R37a's static-provenance pattern exactly:
  - _resolve_commitment_accountable_party (AM-71) reused unchanged —
    confirmed against the real au-medicationrequest profile that
    .requester's target types (Practitioner | PractitionerRole |
    Organization | Patient | RelatedPerson | Device) are identical to
    ServiceRequest.requester's, PractitionerRole included.
  - The AM-72 holds-clause emission pattern reused unchanged: the burden
    is granted directly to the resolved accountable party, only when
    that el_id names a declared object.
  - R38a mirrors R37a: MedicationDispense.status=completed with an
    authorizingPrescription reference back to this MedicationRequest
    tags the burden's description — no token.state change (TokenState
    grammar rule permits only active|pending|claimable as an AUTHORED
    state).

One rule number, R38, covers the whole MedicationRequest -> Commitment +
Burden job (mirrors the R37a/R37b precedent of no bare intermediate
number for a single resource type's mapping, rather than re-splitting
into R38/R39/R40/R41 the way R05-R08 happened to be split historically).

Confirmed against the real AU MedicationDispense profile (au-
medicationdispense.json): the linking field is .authorizingPrescription
(NOT .basedOn), and MedicationDispense.status has its own value set
(medicationdispense-status) — "declined" is this enum's explicit
negative, distinct from Procedure's "not-done".

tests/fixtures/medication_dispense_bundle.json covers three cases:

  MedicationRequest/701 — dispensed via MedicationDispense/801 (status
    "completed"). Positive case: [R38a] tag naming the dispense, burden
    stays 'state: active' (never authorable as 'discharged').

  MedicationRequest/702 — MedicationDispense/802 references it but has
    status "declined". Negative case: no [R38a] tag despite the
    authorizingPrescription link existing.

  MedicationRequest/703 — no MedicationDispense references it at all.
    Negative case: no [R38a] tag, description unchanged from R38's own
    text.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "medication_dispense_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def test_medication_request_creates_commitment_and_burden():
    """[R38] MedicationRequest/701 produces a burden held by the resolved
    accountable party (PractitionerRole -> Organization, AM-71), granted
    via a holds clause (AM-72)."""
    el = _generate()
    assert "burden Id701Obligation {" in el
    assert "commitment Id701Commitment {" in el
    commitment_block = el.split("commitment Id701Commitment {")[1].split("}")[0]
    assert "by: HarbourviewPharmacy001" in commitment_block

    assert "party HarbourviewPharmacy001" in el
    party_block = el.split("party HarbourviewPharmacy001")[1].split("party PatientMiaTran")[0]
    assert "holds Id701Obligation" in party_block


def test_r38a_dispensed_medication_tags_burden_description():
    """[R38a] MedicationDispense/801 (completed) authorizingPrescription
    -> MedicationRequest/701 — the resulting burden's description gains
    an [R38a] tag naming the dispense."""
    el = _generate()
    block = el.split("burden Id701Obligation {")[1].split("}")[0]
    assert "[R38a] Dispensed by MedicationDispense/801" in block
    assert "state: active" in block
    assert "state: discharged" not in block


def test_r38a_declined_dispense_does_not_tag():
    """[R38a] MedicationDispense/802 references MedicationRequest/702 but
    has status 'declined' (the enum's explicit negative) — the
    authorizingPrescription link exists but the status doesn't qualify,
    so no [R38a] tag."""
    el = _generate()
    block = el.split("burden Id702Obligation {")[1].split("}")[0]
    assert "[R38a]" not in block
    assert "state: active" in block


def test_r38a_no_dispense_at_all_leaves_burden_untagged():
    """[R38a] MedicationRequest/703 has no referencing MedicationDispense
    at all — no [R38a] tag anywhere in its burden's description."""
    el = _generate()
    block = el.split("burden Id703Obligation {")[1].split("}")[0]
    assert "[R38a]" not in block


def test_r38_bundle_output_parses_and_validates():
    """The generated spec — R38/R38a included — must be structurally
    valid, not just textually plausible: parses and passes all validator
    rules."""
    from el_parser import parse

    el = _generate()
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".el", mode="w", delete=False) as f:
        f.write(el)
        path = f.name
    try:
        result = parse(path, validate=True)
        assert result.ok, f"Validation errors: {result.errors}"
    finally:
        os.unlink(path)


def test_r38_holds_clause_produces_a_real_live_token_instance():
    """The regression check that actually matters: parsing the generated
    output and building a live Runtime via Runtime.build_from_spec() must
    produce a real, live TokenInstance for MedicationRequest/701's
    burden — not just plausible-looking `holds` text (AM-72)."""
    from el_parser import parse_string
    from el_runtime import Runtime

    result = parse_string(_generate(), validate=True)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)
    tokens = {t.token_name: t for t in rt.current_state().tokens}

    assert "Id701Obligation" in tokens
    assert tokens["Id701Obligation"].holder == "HarbourviewPharmacy001"
    assert tokens["Id701Obligation"].kind == "burden"
    assert tokens["Id701Obligation"].state == "active"
