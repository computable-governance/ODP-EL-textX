"""
R36 verification — Condition description enrichment.

toolchain/fhir_mapper.py's R36 rule (docs/design_notes/DN_009_consolidated_
mapping_analysis.md §2.4) enriches an existing R07 burden's description
with the diagnosis named by ServiceRequest.reasonReference, when that
reference resolves to a Condition resource in the bundle. A Condition is a
proposition (X.902 §6.2), not an object filling any action role, so this
is description-text enrichment only — no new dataclass, no artefact_object,
no token.state change. Enriches token.description (the burden), not
Commitment.description, for consistency with R33a/R34's established
target.

Scoped to ServiceRequest.reasonReference only. This mapper has no
_map_procedure (Procedure-discharge, DN_009 §2.5, remains future work), so
there is no other burden anywhere in the codebase that a Procedure's
reasonReference could enrich. reasonCode (inline CodeableConcept, no
resource to resolve) is out of scope.

tests/fixtures/condition_referral_bundle.json (new fixture — no existing
fixture in the repo carries a Condition resource) covers both required
cases:

  ServiceRequest/301 — reasonReference points at Condition/300 ("Type 2
    diabetes mellitus"). Exercises the positive case: an [R36] tag naming
    the diagnosis appears in the resulting burden's description.

  ServiceRequest/302 — no reasonReference at all. Exercises the negative
    case: no [R36] tag, description unchanged from R07's own text.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "condition_referral_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def test_r36_reason_reference_condition_enriches_burden_description():
    """[R36] ServiceRequest/301's reasonReference resolves to Condition/300
    — the resulting burden's description gains an [R36] tag naming the
    diagnosis."""
    el = _generate()
    assert "burden Id301Obligation {" in el
    block = el.split("burden Id301Obligation {")[1].split("}")[0]
    assert "[R36] Referral reason: Type 2 diabetes mellitus (Condition/300)" in block


def test_r36_no_reason_reference_leaves_burden_description_untagged():
    """[R36] ServiceRequest/302 has no reasonReference at all — no [R36]
    tag anywhere in its burden's description."""
    el = _generate()
    assert "burden Id302Obligation {" in el
    block = el.split("burden Id302Obligation {")[1].split("}")[0]
    assert "[R36]" not in block


def test_r36_does_not_declare_a_new_object_for_the_condition():
    """[R36] Condition is a proposition (X.902 §6.2), not an object filling
    an action role — no object declaration (artefact_object or otherwise)
    is emitted for Condition/300, unlike R34's Composition/DiagnosticReport
    handling. Only the [R36] enrichment tag and the mapping-log comment
    should mention it; the objects section itself must not."""
    el = _generate()
    objects_section = el.split("// ── Parties and Agents")[1].split("// ── Deontic Tokens")[0]
    assert "Id300" not in objects_section
    assert "artefact_object" not in el


def test_r36_bundle_output_parses_and_validates():
    """The generated spec — [R36]-enriched description included — must be
    structurally valid, not just textually plausible: parses and passes
    all validator rules."""
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
