"""
R39 verification — Observation (progress/PROM score) -> Burden with a
governance-policy deadline, wired to the existing violation_response
mechanism to escalate to the GP if unreviewed (touchpoint 6, recovery/
allied health).

Grounded against the real base FHIR R4 core package (no AU-specific
Observation profile exists anywhere in ~/fhir-docker-folder/package/ —
confirmed by a full search, not assumed):
tests/fixtures/observation_progress_score_bundle.json's ~/.fhir/packages/
hl7.fhir.r4.core#4.0.1/package/StructureDefinition-Observation.json
confirms .basedOn's target types include ServiceRequest and .performer's
target types include Patient.

Holder resolution is .basedOn -> ServiceRequest -> that ServiceRequest's
own already-resolved Commitment.by, NOT .performer directly — a self-
reported PROM commonly has the patient as performer (confirmed by the
profile above), which would incorrectly obligate the patient to review
their own score. .performer is only a fallback when .basedOn doesn't
resolve.

One rule number, R39, no static/live split like R37/R38 — there is no
new live bridge to build: check_live_violations()/fire_violation_
responses() (el_engine.py) are already-existing, generic engine
functions operating over any declared burden/ViolationResponse.

escalate_to (the GP practice) is the accountable party of whichever
ServiceRequest has the earliest .authoredOn in the bundle — the referral
that started the patient's journey.

The escalation-notice burden mirrors escalationNoticeBurden in the real
referral_scenario.el exactly: state: active, discharge_mode: strict,
priority: critical, deadline: "48 hours from violation detection", no
holds clause anywhere (fire_violation_responses() grants it dynamically
only when it actually fires).

tests/fixtures/observation_progress_score_bundle.json covers:

  ServiceRequest/210 — the earliest referral (authoredOn 2024-05-01),
    GP practice Elimbah Medical Centre — this is what escalate_to must
    resolve to.

  ServiceRequest/950 — physiotherapy referral (authoredOn 2024-07-15),
    Riverside Physiotherapy — the review burden's holder.

  Observation/960 — .basedOn -> ServiceRequest/950 AND .performer ->
    Patient/roberts-fred (deliberately both set). Positive case: holder
    resolves to RiversidePhysio (the .basedOn path), NOT RobertsFred —
    confirms .basedOn takes priority over .performer.

  Observation/961 — no .basedOn, .performer -> PractitionerRole/
    physio-dr-cole. Fallback case: holder still resolves to
    RiversidePhysio, via the .performer fallback path this time.

  Observation/962 — neither .basedOn nor .performer at all. Degenerate
    case: no accountable-party reference exists anywhere, so nothing is
    created for it at all (a bare "commitment.by:" with nothing after it
    would be a textX PARSE failure, not just a validator warning — this
    is skipped entirely, not tagged-and-ungranted like AM-71/AM-72's
    "reference exists but doesn't resolve" tiers).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "observation_progress_score_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def test_based_on_service_request_resolves_holder_not_performer():
    """[Positive] Observation/960's .basedOn -> ServiceRequest/950 resolves
    the review burden's holder to RiversidePhysio — NOT RobertsFred, even
    though .performer is also set to the patient."""
    el = _generate()
    assert "burden Id960Obligation {" in el
    assert "party RiversidePhysio" in el
    block = el.split("party RiversidePhysio")[1].split("party RobertsFred")[0]
    assert "holds Id960Obligation" in block

    commitment_block = el.split("commitment Id960Commitment {")[1].split("}")[0]
    assert "by: RiversidePhysio" in commitment_block


def test_review_burden_has_governance_policy_deadline_not_a_fhir_derived_one():
    """The 7-day deadline is a hardcoded governance-policy constant, not
    derived from any Observation field — present verbatim regardless of
    what (if anything) the source FHIR data carries about timing."""
    el = _generate()
    block = el.split("burden Id960Obligation {")[1].split("}")[0]
    assert 'deadline: "7 days"' in block
    assert "discharge_mode: eventual" in block  # must stay eventual, not strict


def test_performer_fallback_resolves_when_based_on_is_absent():
    """[Fallback] Observation/961 has no .basedOn at all — resolves via
    .performer -> PractitionerRole/physio-dr-cole -> RiversidePhysio."""
    el = _generate()
    commitment_block = el.split("commitment Id961Commitment {")[1].split("}")[0]
    assert "by: RiversidePhysio" in commitment_block


def test_neither_based_on_nor_performer_creates_nothing():
    """[Degenerate] Observation/962 has neither .basedOn nor .performer —
    nothing is created for it at all (not a tagged/ungranted burden;
    there's no accountable-party reference to tag in the first place)."""
    el = _generate()
    assert "Id962Obligation" not in el
    assert "Observation/962" not in el


def test_violation_response_references_correct_burden_and_escalation_target():
    """The violation_response for Observation/960's review burden
    obligates RiversidePhysio, creates the escalation-notice burden, and
    escalates to Elimbah Medical Centre — the accountable party of
    ServiceRequest/210, the earliest referral in the bundle (authoredOn
    2024-05-01, vs. ServiceRequest/950's 2024-07-15)."""
    el = _generate()
    assert "violation_response Id960ViolationResponse {" in el
    block = el.split("violation_response Id960ViolationResponse {")[1].split("}")[0]
    assert "on_violation_of: Id960Obligation" in block
    assert "obligates: RiversidePhysio" in block
    assert "response_kind: escalate" in block
    assert "creates_burden: Id960EscalationNoticeObligation" in block
    assert "escalate_to: ElimbahMedicalCentre" in block


def test_escalation_notice_burden_has_no_holds_clause_anywhere():
    """Mirrors escalationNoticeBurden in referral_scenario.el exactly: the
    escalation-notice burden is declared but never granted via holds —
    fire_violation_responses() grants it dynamically only when it fires."""
    el = _generate()
    assert "burden Id960EscalationNoticeObligation {" in el
    block = el.split("burden Id960EscalationNoticeObligation {")[1].split("}")[0]
    assert "discharge_mode: strict" in block
    assert "priority: critical" in block
    assert "holds Id960EscalationNoticeObligation" not in el


def test_r39_bundle_output_parses_and_validates():
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


def test_deadline_elapsed_actually_fires_violation_and_creates_escalation_burden():
    """The real proof, not just plausible-looking text: build a live
    Runtime, advance the clock past the 7-day deadline (56 ticks —
    _DEADLINE_UNIT_STEPS["day"] == 8), call check_live_violations() (must
    transition Id960Obligation to 'violated'), then
    fire_violation_responses() (must grant Id960EscalationNoticeObligation
    to RiversidePhysio, and log the escalation to ElimbahMedicalCentre)."""
    from el_parser import parse_string
    from el_runtime import Runtime

    result = parse_string(_generate(), validate=True)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)
    tokens_before = {t.token_name: t for t in rt.current_state().tokens}
    assert tokens_before["Id960Obligation"].state == "active"
    assert tokens_before["Id960Obligation"].holder == "RiversidePhysio"

    rt._state = rt._state.with_tick(56)
    violation_record = rt.check_live_violations()

    assert violation_record.outcome == "violation"
    assert "Id960Obligation" in violation_record.violations
    after_violation = {t.token_name: t for t in rt.current_state().tokens}
    assert after_violation["Id960Obligation"].state == "violated"

    response_record = rt.fire_violation_responses()

    assert "Id960ViolationResponse" in response_record.fired_responses
    assert any(
        "Id960EscalationNoticeObligation" in e and "RiversidePhysio" in e
        for e in response_record.effects
    )
    assert any(
        "Id960ViolationResponse" in e and "ElimbahMedicalCentre" in e
        for e in response_record.effects
    )

    escalation = [
        t for t in rt.current_state().tokens
        if t.token_name == "Id960EscalationNoticeObligation"
    ]
    assert escalation, "escalation-notice burden must be granted after the response fires"
    assert escalation[0].holder == "RiversidePhysio"
    assert escalation[0].state == "active"
    assert escalation[0].discharge_mode == "strict"
