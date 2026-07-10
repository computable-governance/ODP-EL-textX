"""
R05–R08 verification — referral-shaped ServiceRequest mapping.

toolchain/fhir_mapper.py's R05–R08 rules had never been exercised against
a referral-shaped bundle before 2026-07-10 (see
R05-R08_Verification_Note_2026-07-10.md) — the only prior golden test,
test_fhir_mapper_golden.py, regenerates from the older clinical-AI-consent
bundle (ai_diagnostic_bundle.json), which happens not to exercise the
Practitioner-requester resolution path (R06) or the for_action mapping
table (R07) at all.

tests/fixtures/referral_service_request_bundle.json carries two
ServiceRequests designed to hit both branches of R06 and R07 together:

  referral-sr-002 — requester is a Practitioner with a PractitionerRole
    naming an Organization (R06 happy path); priority "urgent" (R07
    time-critical signal, no consent keywords); code.coding matches
    SERVICE_REQUEST_ACTION_MAP (R07 for_action resolves); no SLA-style
    deadline field exists on ServiceRequest (R08 — deadline stays blank).

  referral-sr-003 — requester is a Practitioner with NO PractitionerRole
    in the bundle (R06 fallback: falls back to the practitioner, warning
    surfaced in commitment.description); note text contains a consent
    keyword (R07 consent-related signal); code.coding ("Imaging",
    363679005) has no SERVICE_REQUEST_ACTION_MAP entry (R07 for_action
    unresolved, flagged rather than guessed).

This file is deliberately separate from test_fhir_mapper_golden.py's
ai_diagnostic_bundle.json path — a new fixture, not a change to the
existing golden-file regeneration test.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "referral_service_request_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def test_r06_resolves_practitioner_requester_through_practitioner_role():
    """[R06] Practitioner requester with a PractitionerRole.organization
    resolves commitment.by to the organisation, not the practitioner."""
    el = _generate()
    assert (
        "commitment ReferralSr002Commitment {\n"
        "    by: GpPracticeReferral001\n"
        in el
    )


def test_r06_falls_back_to_practitioner_with_warning_when_unresolved():
    """[R06] Practitioner requester with no PractitionerRole in the bundle
    falls back to the practitioner directly and surfaces a warning —
    never silently misattributes to a fabricated organisation."""
    el = _generate()
    assert (
        "commitment ReferralSr003Commitment {\n"
        "    by: GpDrNguyen\n"
        in el
    )
    assert "[R06] UNRESOLVED organisational affiliation for Practitioner/gp-dr-nguyen" in el
    assert "no PractitionerRole.organization found in bundle" in el


def test_r07_discharge_mode_time_critical_signal():
    """[R07] ServiceRequest.priority == urgent sets discharge_mode: strict
    / priority: critical via the time-criticality check, independent of
    any consent keyword (referral-sr-002 has none)."""
    el = _generate()
    assert "burden ReferralSr002Obligation {" in el
    block = el.split("burden ReferralSr002Obligation {")[1].split("}")[0]
    assert "discharge_mode: strict" in block
    assert "priority: critical" in block
    assert "[R07] strict: time-critical" in block
    assert "consent-related" not in block


def test_r07_discharge_mode_consent_related_signal():
    """[R07] Consent-keyword note text sets discharge_mode: strict /
    priority: critical via the consent-related check (referral-sr-003 has
    priority: routine, so this isolates the consent signal)."""
    el = _generate()
    assert "burden ReferralSr003Obligation {" in el
    block = el.split("burden ReferralSr003Obligation {")[1].split("}")[0]
    assert "discharge_mode: strict" in block
    assert "priority: critical" in block
    assert "[R07] strict: consent-related" in block
    assert "time-critical" not in block


def test_r07_for_action_resolves_via_mapping_table():
    """[R07] A code.coding entry present in SERVICE_REQUEST_ACTION_MAP
    (SNOMED 306207001, "Referral to specialist") resolves for_action to
    the DSL action identifier it's mapped to, not a sanitised display
    string."""
    el = _generate()
    block = el.split("burden ReferralSr002Obligation {")[1].split("}")[0]
    assert 'for_action: "initiateReferral"' in block
    assert "UNRESOLVED for_action" not in block


def test_r07_for_action_flagged_when_unresolved():
    """[R07] A code.coding entry with no SERVICE_REQUEST_ACTION_MAP entry
    falls back to the sanitised display string and is flagged UNRESOLVED
    in the description — never silently guessed."""
    el = _generate()
    block = el.split("burden ReferralSr003Obligation {")[1].split("}")[0]
    assert 'for_action: "imaging"' in block
    assert "[R07] UNRESOLVED for_action — no DSL action mapping, verify manually" in block


def test_r08_deadline_left_blank():
    """[R08] occurrenceDateTime is a scheduling field, not an SLA
    deadline — both burdens must have no deadline line at all, despite
    both ServiceRequests carrying an occurrenceDateTime."""
    el = _generate()
    for burden_id in ("ReferralSr002Obligation", "ReferralSr003Obligation"):
        block = el.split(f"burden {burden_id} {{")[1].split("}")[0]
        assert "deadline:" not in block


def test_referral_bundle_output_parses_and_validates():
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
