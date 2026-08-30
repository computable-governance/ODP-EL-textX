"""
PractitionerRole-as-requester fix verification (fhir_mapper.py's
_resolve_commitment_accountable_party, ~line 307).

Fixes the crash documented in docs/CONCEPTS_INDEX.md's "PractitionerRole-
as-requester crashes validation entirely" (2026-08-30): a ServiceRequest.
requester referencing a PractitionerRole directly (standard AU Core
practice, confirmed against real ConnectedCare touchpoint 3+4 data) used
to fall through to a bare _ref_id(requester) return with no check that
anything actually declares a matching object — since no _map_* function
ever turns a PractitionerRole into a declared ELObject, this produced a
hard validator failure ([SEMANTIC] Unknown object ... of class
"EnterpriseObject") for realistic input, not an edge case.

The fix adds a direct by_ref.get(ref) lookup (no search needed — the
reference already names the exact resource) with a three-tier resolution:

  0a. PractitionerRole found, .organization set -> that organisation's
      el_id, no warning. The main fix.
  0b. PractitionerRole found, no .organization -> falls back to its own
      .practitioner.reference, WITH a warning. Safe because _map_practitioner
      (R03) declares every Practitioner resource present in the bundle as
      an ELObject unconditionally, independent of its role.
  0c. PractitionerRole not found in the bundle at all, or found but has
      neither .organization nor .practitioner -> falls back to the raw
      PractitionerRole reference, WITH a warning that it may not resolve
      to any declared object. This CAN still fail downstream validation —
      same worst-case risk tier the pre-existing Practitioner-only case 3
      fallback already accepted, not a new category of risk. Tested here
      explicitly so that risk stays documented, not silently reintroduced.

tests/fixtures/practitioner_role_requester_bundle.json adapts the real
touchpoint-3 data (organization-brisbane-endocrinology.json,
practitioner-lindqvist-anya.json,
practitionerrole-endocrinologist-lindqvist-anya.json,
servicerequest-thyroidectomy-booking.json — the actual resources that
surfaced this bug during the 2026-08-30 investigation) for the tier 0a
positive case, plus one synthetic PractitionerRole (no .organization) for
tier 0b and one dangling reference for tier 0c.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "practitioner_role_requester_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate(bundle: dict) -> str:
    mapper = FHIRConsentMapper()
    return mapper.map_bundle(bundle)


def _load_bundle() -> dict:
    return json.loads(FIXTURE.read_text())


def _entries_by_ids(bundle: dict, keep_sr_ids: set) -> dict:
    """Filter the fixture bundle down to just the resources needed for a
    given ServiceRequest id — demographics plus that one ServiceRequest's
    requester chain — dropping the other ServiceRequests entirely."""
    kept = []
    for entry in bundle["entry"]:
        r = entry["resource"]
        if r["resourceType"] == "ServiceRequest" and r["id"] not in keep_sr_ids:
            continue
        kept.append(entry)
    return {**bundle, "entry": kept}


def test_practitioner_role_with_organization_resolves_cleanly():
    """[Tier 0a] ServiceRequest/554's requester is PractitionerRole/
    endocrinologist-lindqvist-anya, which has .organization set —
    commitment.by resolves straight to the organisation, no warning."""
    el = _generate(_load_bundle())
    assert "commitment Id554Commitment {" in el
    block = el.split("commitment Id554Commitment {")[1].split("}")[0]
    assert "by: BrisbaneEndocrinology" in block
    assert "[R06]" not in block


def test_practitioner_role_without_organization_falls_back_to_practitioner():
    """[Tier 0b] ServiceRequest/555's requester is PractitionerRole/
    locum-oconnor-liam, which has no .organization — commitment.by falls
    back to Practitioner/oconnor-liam directly, with an [R06] warning."""
    el = _generate(_load_bundle())
    assert "commitment Id555Commitment {" in el
    block = el.split("commitment Id555Commitment {")[1].split("}")[0]
    assert "by: OconnorLiam" in block
    assert "[R06] UNRESOLVED organisational affiliation" in block
    assert "has no .organization set" in block


def test_dangling_practitioner_role_falls_back_to_raw_reference_with_warning():
    """[Tier 0c] ServiceRequest/560's requester is PractitionerRole/
    dangling-not-in-bundle — not present in the bundle at all.
    commitment.by falls back to the raw reference, with a warning — and
    this el_id is genuinely undeclared, so the generated spec is expected
    to still fail validation for this case (documented risk, not a
    regression: the pre-existing Practitioner-only case 3 fallback
    accepted the same risk)."""
    from el_parser import parse_string

    bundle = _load_bundle()
    el = _generate(bundle)
    assert "commitment Id560Commitment {" in el
    block = el.split("commitment Id560Commitment {")[1].split("}")[0]
    assert "by: DanglingNotInBundle" in block
    assert "[R06] UNRESOLVED organisational affiliation" in block
    assert "PractitionerRole not found in bundle" in block

    result = parse_string(el, validate=True)
    assert not result.ok
    assert any(
        'Unknown object "DanglingNotInBundle"' in e for e in result.errors
    ), result.errors


def test_previously_crashing_real_shape_now_parses_and_validates():
    """The exact shape that crashed 2026-08-30 (PractitionerRole-as-
    requester, with .organization set — tier 0a, the real touchpoint-3
    data) now produces a spec that parses and passes all validator rules
    end to end, not just plausible-looking text. Filtered to just
    ServiceRequest/554 so the tier-0c dangling case (expected to still
    fail, per the test above) doesn't mask this regression check."""
    from el_parser import parse_string

    bundle = _entries_by_ids(_load_bundle(), keep_sr_ids={"554"})
    el = _generate(bundle)
    result = parse_string(el, validate=True)
    assert result.ok, f"Validation errors: {result.errors}"
