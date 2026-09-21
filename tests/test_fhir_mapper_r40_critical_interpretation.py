"""
R40 verification — Observation.interpretation (critical tier) -> strict/
critical notification burden, causally linked to a new EventDecl via
triggered_by (mirrors R33's provenance shape), with the same holder-
resolution helper R39 already uses.

No grammar change: reuses existing constructs only (burden, EventDecl,
triggered_by, discharge_mode, priority — all already emitted by R07/R33/
R39). Static (mapper-only) — fires at map time from the Observation's own
coded .interpretation field, no runtime-event dimension.

Critical-tier codes, confirmed against the real v3-ObservationInterpretation
CodeSystem (~/.fhir/packages/hl7.fhir.r4.core#4.0.1/package/
CodeSystem-v3-ObservationInterpretation.json): HH "Critical high", LL
"Critical low", AA "Critical abnormal". Plain abnormal (H/L/A) and absent
interpretation both deliberately do NOT trigger this rule.

Holder resolution is .basedOn -> ServiceRequest -> that ServiceRequest's
own already-resolved Commitment.by, NOT .performer directly — identical to
R39, reused rather than reimplemented.

tests/fixtures/observation_critical_interpretation_bundle.json covers:

  ServiceRequest/500 — pathology referral (authoredOn 2024-08-25), Coastal
    Pathology — this is what the notification burden's holder must resolve
    to via Observation/970's .basedOn.

  Observation/970 — .basedOn -> ServiceRequest/500, .interpretation HH
    (Critical high). Positive case: strict/critical notification burden
    created, triggered_by a new CriticalResult event.

  Observation/971 — .basedOn -> ServiceRequest/500, .interpretation N
    (Normal). Negative case: plain/normal interpretation must NOT create
    the burden.

  Observation/972 — .basedOn -> ServiceRequest/500, no .interpretation
    field at all. Negative case: absent interpretation must NOT create
    the burden either — distinct assertion from the normal-interpretation
    case above, not just an absence-of-assertion.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "observation_critical_interpretation_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def test_critical_interpretation_creates_strict_critical_burden():
    """[Positive] Observation/970's HH (Critical high) interpretation
    creates a strict/critical notification burden, granted to
    CoastalPathology (resolved via .basedOn -> ServiceRequest/500's own
    Commitment.by)."""
    el = _generate()
    assert "burden Id970CriticalNotificationObligation {" in el
    block = el.split("burden Id970CriticalNotificationObligation {")[1].split("}")[0]
    assert "discharge_mode: strict" in block
    assert "priority: critical" in block
    assert 'for_action: "notify_critical_result"' in block

    assert "party CoastalPathology" in el
    party_block = el.split("party CoastalPathology")[1].split("}")[0]
    assert "holds Id970CriticalNotificationObligation" in party_block

    commitment_block = el.split("commitment Id970CriticalNotificationCommitment {")[1].split("}")[0]
    assert "by: CoastalPathology" in commitment_block


def test_critical_interpretation_burden_triggered_by_new_event():
    """The notification burden carries triggered_by pointing at a newly
    emitted EventDecl representing the critical result — same causal-link
    shape as R33, not a bare Commitment/Burden pair."""
    el = _generate()
    assert "event Id970CriticalResult" in el
    block = el.split("burden Id970CriticalNotificationObligation {")[1].split("}")[0]
    assert "triggered_by: Id970CriticalResult" in block


def test_normal_interpretation_creates_nothing():
    """[Negative] Observation/971 has a plain Normal (N) interpretation —
    not critical-tier — so no burden, event, or commitment is created for
    it at all."""
    el = _generate()
    assert "Id971CriticalNotificationObligation" not in el
    assert "Id971CriticalResult" not in el
    assert "Id971CriticalNotificationCommitment" not in el


def test_absent_interpretation_creates_nothing():
    """[Negative] Observation/972 has no .interpretation field at all —
    distinct from the normal-interpretation case: absence of the field,
    not presence of a non-critical code. Must also create nothing."""
    el = _generate()
    assert "Id972CriticalNotificationObligation" not in el
    assert "Id972CriticalResult" not in el
    assert "Id972CriticalNotificationCommitment" not in el


def test_r40_bundle_output_parses_and_validates():
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
