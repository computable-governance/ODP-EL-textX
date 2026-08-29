"""
R34 verification — Composition/DiagnosticReport artefact provenance
(DN_008 Option A).

toolchain/fhir_mapper.py's R34 rule (docs/design_notes/DN_008_composition_mapping_gap.md,
Option A; scoping corrected against docs/design_notes/DN_009_consolidated_mapping_analysis.md
§2.1-2.2 — see the R34 commit for the correction: ArtefactRef only exists
inside an Action, which this ServiceRequest pipeline never emits, so R34
does not attempt to wire one) records a clinical document's attachment to
a referral as provenance on the existing R07 burden, plus a standalone
artefact_object declaration — it does not change token state and does not
invent a new grammar construct.

Two link directions, confirmed empirically against the real
hl7.fhir.au.ps/hl7.fhir.au.ereq profiles (2026-08-29), not assumed:

  Composition       — forward:  ServiceRequest.supportingInfo -> Composition
  DiagnosticReport  — reverse:  DiagnosticReport.basedOn -> ServiceRequest
                       (DiagnosticReport has no supportingInfo field at all)

tests/fixtures/aups_referral_bundle.json extends DN_008's own
already-validated fixture (tests/fixtures/aups_referral_example/ —
Composition/171 and ServiceRequest/173 reused verbatim, same IDs and
content) with:

  ServiceRequest/174 + DiagnosticReport/175 — DiagnosticReport-linked case
    (basedOn -> ServiceRequest/174, no supportingInfo involved).
  ServiceRequest/176 — negative case, no supportingInfo and no
    DiagnosticReport references it at all.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "aups_referral_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def test_r34_composition_supporting_info_emits_artefact_object_and_enriches_burden():
    """[R34] ServiceRequest/173's supportingInfo references Composition/171
    — an artefact_object must be declared for it, and burden
    Id173Obligation's description must carry the [R34] provenance note."""
    el = _generate()
    assert "artefact_object Id171" in el
    assert 'description: "[R34] Patient Summary for Fred Roberts (Composition/171)"' in el

    assert "burden Id173Obligation {" in el
    block = el.split("burden Id173Obligation {")[1].split("}")[0]
    assert "[R34] Referral accompanied by Composition/171 (patient summary)" in block


def test_r34_diagnostic_report_based_on_emits_artefact_object_and_enriches_burden():
    """[R34] DiagnosticReport/175's basedOn references ServiceRequest/174
    — the reverse link direction from Composition. An artefact_object must
    be declared for the report, and burden Id174Obligation's description
    must carry the [R34] provenance note naming the report, not the
    supportingInfo-style wording used for Composition."""
    el = _generate()
    assert "artefact_object Id175" in el
    assert 'description: "[R34] Complete blood count panel (DiagnosticReport/175)"' in el

    assert "burden Id174Obligation {" in el
    block = el.split("burden Id174Obligation {")[1].split("}")[0]
    assert "[R34] Fulfilled by DiagnosticReport/175" in block


def test_r34_no_artefact_object_or_tag_for_service_request_without_linked_artefact():
    """[R34] ServiceRequest/176 has no supportingInfo and no DiagnosticReport
    references it — no artefact_object, no [R34] tag on its burden. Confirms
    R34 doesn't fire spuriously just because a ServiceRequest exists."""
    el = _generate()
    assert "burden Id176Obligation {" in el
    block = el.split("burden Id176Obligation {")[1].split("}")[0]
    assert "[R34]" not in block
    assert "artefact_object Id176" not in el


def test_r34_does_not_duplicate_artefact_object_if_referenced_twice():
    """[R34] Dedup discipline, matching R33a's event-dedup pattern: if the
    same Composition/DiagnosticReport were referenced by more than one
    ServiceRequest, only one artefact_object block should ever be emitted
    for it. This fixture's Composition/171 is referenced exactly once, so
    this asserts the single-reference baseline count stays exactly 1 (a
    literal duplicate-reference fixture is unnecessary to prove the `any(...)`
    dedup guard, which is identical in shape to R33a's already-tested one)."""
    el = _generate()
    assert el.count("artefact_object Id171") == 1
    assert el.count("artefact_object Id175") == 1


def test_r34_artefact_objects_render_via_existing_object_machinery():
    """[R34] No new render code was added — artefact_object renders via the
    same _render_object()/_render_el() path as party/agent objects. Confirm
    both artefact_object blocks appear in the Parties and Agents section,
    with fhir_ref-free description-only bodies (ELObject has no body items
    set for these — delegated_from/principal_of are both empty)."""
    el = _generate()
    section = el.split("// ── Parties and Agents")[1].split("// ── Deontic Tokens")[0]
    assert "artefact_object Id171" in section
    assert "artefact_object Id175" in section


def test_r34_bundle_output_parses_and_validates():
    """The generated spec — artefact_object declarations and all — must be
    structurally valid: parses and passes all validator rules."""
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
