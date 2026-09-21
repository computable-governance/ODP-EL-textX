"""
R05-R08 + R40 composition verification — ConnectedCare Stage 1 (pathology).

No new mapper code: both rules already exist and are already generic
(R05-R08: ServiceRequest -> Commitment/Burden; R40: Observation.interpretation
critical-tier -> Commitment/Burden/EventDecl, see
tests/test_fhir_mapper_r40_critical_interpretation.py). This file proves the
two rules chain together correctly for the pathology stage specifically, the
same way test_fhir_mapper_referral.py proves R05-R08 alone and
test_fhir_mapper_golden.py (ai_diagnostic_bundle.json) proves R05-R08 +
R09-R15 + R16-R22 chain together for the specialist-referral/consent case.

tests/fixtures/connectedcare_pathology_stage1_bundle.json is built so R40's
holder resolution can be told apart from a coincidence: the ServiceRequest's
requester (WestlakePathologyServices) and the fallback .performer's
organisation (BrightwaterCytologyLab, via PractitionerRole/
cytopathologist-dr-alvarez) are two DIFFERENT organisations, not the same
one restated. That makes "which holder did R40 actually resolve to" a real
discriminator between the .basedOn path and the .performer fallback path,
not just plausible-looking text.

  ServiceRequest/pathology-sr-001 — requester is the pathology provider org
    itself (Westlake Pathology Services), not a GP practice referring
    outward — R05-R08's holder for this stage.

  Observation/pathology-obs-001 — .basedOn -> ServiceRequest/pathology-sr-001
    AND .performer -> PractitionerRole/cytopathologist-dr-alvarez
    (Brightwater), deliberately both set, mirroring R39's own
    both-set-basedOn-wins fixture design. Proves R40's holder resolution
    genuinely chains onto R05-R08's already-resolved Commitment.by for this
    stage — not just structurally similar output in the standalone R40
    fixture, where holder resolution was exercised in isolation.

  Observation/pathology-obs-002 — no .basedOn at all, same .performer.
    Proves the documented .performer fallback still resolves correctly
    in this pathology context, to the fallback organisation
    (BrightwaterCytologyLab) — provably NOT WestlakePathologyServices,
    since the two orgs are distinct.

R39 also fires generically on both Observations (any Observation with a
resolvable holder gets a review burden, independent of .interpretation) —
expected, pre-existing generic behaviour, not part of what this file is
proving; assertions below are scoped to the R05-R08 and R40 blocks only.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "connectedcare_pathology_stage1_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def _commitment_by(el: str, commitment_id: str) -> str:
    block = el.split(f"commitment {commitment_id} {{")[1].split("}")[0]
    line = next(l for l in block.splitlines() if l.strip().startswith("by:"))
    return line.split("by:")[1].strip()


def test_r05_r08_fires_on_pathology_service_request():
    """[R05-R08] The pathology ServiceRequest itself gets a Commitment +
    Burden, held by the pathology provider org (WestlakePathologyServices),
    not a GP practice — closing the "not yet built as its own worked
    example" gap for this stage."""
    el = _generate()
    assert "commitment PathologySr001Commitment {" in el
    assert _commitment_by(el, "PathologySr001Commitment") == "WestlakePathologyServices"

    assert "burden PathologySr001Obligation {" in el
    party_block = el.split("party WestlakePathologyServices")[1].split("}")[0]
    assert "holds PathologySr001Obligation" in party_block


def test_r40_basedon_traces_to_same_commitment_by_as_r05_r08():
    """[R40] Observation/pathology-obs-001's .basedOn resolves the critical-
    notification burden's holder to the SAME el_id as R05-R08's own
    Commitment.by (WestlakePathologyServices) — genuinely chaining onto
    R05-R08's output, not coincidentally matching it. Must NOT fall through
    to .performer, which is deliberately set to a different org
    (BrightwaterCytologyLab) to make this a real discriminator."""
    el = _generate()

    r05_r08_holder = _commitment_by(el, "PathologySr001Commitment")
    r40_holder = _commitment_by(el, "PathologyObs001CriticalNotificationCommitment")
    assert r05_r08_holder == r40_holder == "WestlakePathologyServices"

    assert "burden PathologyObs001CriticalNotificationObligation {" in el
    block = el.split("burden PathologyObs001CriticalNotificationObligation {")[1].split("}")[0]
    assert "discharge_mode: strict" in block
    assert "priority: critical" in block
    assert "triggered_by: PathologyObs001CriticalResult" in block

    party_block = el.split("party WestlakePathologyServices")[1].split("}")[0]
    assert "holds PathologyObs001CriticalNotificationObligation" in party_block

    # Never granted to the performer org instead.
    brightwater_block = el.split("party BrightwaterCytologyLab")[1].split("}")[0]
    assert "holds PathologyObs001CriticalNotificationObligation" not in brightwater_block


def test_r40_performer_fallback_resolves_correctly_when_basedon_absent():
    """[R40] Observation/pathology-obs-002 has no .basedOn at all — the
    documented .performer fallback still applies correctly in this
    pathology context: holder resolves to BrightwaterCytologyLab (the
    performer's organisation via PractitionerRole), provably distinct from
    WestlakePathologyServices (the ServiceRequest's own requester), not a
    coincidental match."""
    el = _generate()

    fallback_holder = _commitment_by(el, "PathologyObs002CriticalNotificationCommitment")
    assert fallback_holder == "BrightwaterCytologyLab"
    assert fallback_holder != _commitment_by(el, "PathologySr001Commitment")

    party_block = el.split("party BrightwaterCytologyLab")[1].split("}")[0]
    assert "holds PathologyObs002CriticalNotificationObligation" in party_block


def test_pathology_stage1_bundle_output_parses_and_validates():
    """The generated spec must be structurally valid, not just textually
    plausible — parses and passes all validator rules."""
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
