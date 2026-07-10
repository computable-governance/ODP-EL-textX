"""
Layer 1 extraction test for fhir_mapper.extract_federation_from_contract()
(R23+R24 — Contract.signer/.term -> FederationDecl membership +
normative_policy references; see
FHIR_ODP_EL_Positioning_Notes_2026-06-26.md §2).

EXTRACTION direction (FHIR -> ODP-EL), standing/static structure, not
wired into el_api.py — mirrors FHIRConsentMapper's R01-R22 pattern, not
fhir_event_handler.py's runtime pattern.

The synthetic bundle below reuses referral_scenario.el's real names
(GPPractice/SpecialistPractice, gpPracticeRole/specialistPracticeRole,
MyHealthRecordsAct/NationalClinicalGovernance/AIMedicalDeviceRegulation)
so the round-trip assertions are meaningful rather than arbitrary.
Organization.name values are given without spaces/hyphens ("GPPractice",
not "GP Practice") so they pass through _preserve_or_sanitize unchanged
and the generated identifiers match referral_scenario.el's exactly —
this is a deliberate fixture choice, not a general claim that FHIR
Organization.name is always identifier-shaped.

Follows the fixture pattern of tests/test_fhir_mapper_golden.py (bare
functions, no fixtures) and tests/test_fhir_event_handler.py (module
docstring explains what's being locked in and why).
"""
import pytest

from fhir_mapper import extract_federation_from_contract


def _referral_network_bundle(
    *,
    include_terms: bool = True,
    include_rule: bool = True,
) -> dict:
    """Synthetic Contract-based bundle shaped like referral_scenario.el's
    ReferralNetworkFederation. AIMedicalDeviceRegulation's term deliberately
    carries no .text and there is no legallyBindingReference for it to fall
    back to — it exercises the "source not derivable" path, distinct from
    MyHealthRecordsAct/NationalClinicalGovernance which do carry .text."""
    resources = [
        {
            "resourceType": "Organization",
            "id": "gp-practice",
            "name": "GPPractice",
        },
        {
            "resourceType": "Organization",
            "id": "specialist-practice",
            "name": "SpecialistPractice",
        },
    ]

    contract: dict = {
        "resourceType": "Contract",
        "id": "referral-network-federation",
        "title": "Referral Network Federation",
        "signer": [
            {
                "party": {"reference": "Organization/gp-practice"},
                "type": {"coding": [{
                    "code": "gpPracticeRole",
                    "display": "GP practice interface role",
                }]},
            },
            {
                "party": {"reference": "Organization/specialist-practice"},
                "type": {"coding": [{
                    "code": "specialistPracticeRole",
                    "display": "Specialist practice interface role",
                }]},
            },
        ],
    }

    if include_terms:
        contract["term"] = [
            {
                "type": {"coding": [{"code": "MyHealthRecordsAct"}]},
                "text": "My Health Records Act 2012 (Cth)",
            },
            {
                "type": {"coding": [{"code": "NationalClinicalGovernance"}]},
                "text": "National Model for Clinical Governance (ACSQHC, 2026)",
            },
            {
                "type": {"coding": [{"code": "AIMedicalDeviceRegulation"}]},
            },
        ]

    if include_rule:
        contract["rule"] = [
            {"contentReference": {"reference": "DocumentReference/referral-scenario-el"}}
        ]

    resources.append(contract)
    return {
        "resourceType": "Bundle",
        "id": "referral-network-federation-bundle",
        "entry": [{"resource": r} for r in resources],
    }


# ── Structural assertions on the generated text ────────────────────────────

def test_generates_federation_block_with_members_and_roles():
    el_text = extract_federation_from_contract(_referral_network_bundle())

    assert "contract federation ReferralNetworkFederation" in el_text
    assert "community_object GPPracticeObj" in el_text
    assert "abstracts: GPPracticeCommunity" in el_text
    assert "community_object SpecialistPracticeObj" in el_text
    assert "abstracts: SpecialistPracticeCommunity" in el_text

    assert "interface role gpPracticeRole" in el_text
    assert "interface role specialistPracticeRole" in el_text

    assert "member: GPPracticeCommunity" in el_text
    assert "represented_by GPPracticeObj" in el_text
    assert "fills gpPracticeRole" in el_text

    assert "member: SpecialistPracticeCommunity" in el_text
    assert "represented_by SpecialistPracticeObj" in el_text
    assert "fills specialistPracticeRole" in el_text


def test_generates_normative_policy_references():
    el_text = extract_federation_from_contract(_referral_network_bundle())

    assert "normative_policy: MyHealthRecordsAct" in el_text
    assert "normative_policy: NationalClinicalGovernance" in el_text
    assert "normative_policy: AIMedicalDeviceRegulation" in el_text


def test_normative_policy_stub_emitted_only_where_source_is_derivable():
    el_text = extract_federation_from_contract(_referral_network_bundle())

    # MyHealthRecordsAct's term carries .text -> a commented stub with
    # that citation as 'source' is emitted, and 'kind' is left for the
    # caller — never guessed (see extract_federation_from_contract's
    # "What is NOT emitted" docstring section).
    assert '// normative_policy MyHealthRecordsAct {' in el_text
    assert '//     source: "My Health Records Act 2012 (Cth)"' in el_text
    assert "kind: <FILL IN" in el_text

    # AIMedicalDeviceRegulation's term has neither .text nor a resolvable
    # legallyBindingReference -> no source is derivable -> no stub at all,
    # per the confirmed fallback behaviour.
    assert "// normative_policy AIMedicalDeviceRegulation {" not in el_text


def test_legally_binding_reference_fallback_used_when_term_text_absent():
    bundle = _referral_network_bundle(include_terms=False, include_rule=False)
    contract = next(
        e["resource"] for e in bundle["entry"]
        if e["resource"]["resourceType"] == "Contract"
    )
    contract["legallyBindingReference"] = {
        "reference": "DocumentReference/mhr-act-citation"
    }
    contract["term"] = [
        {"type": {"coding": [{"code": "MyHealthRecordsAct"}]}},  # no .text
    ]
    bundle["entry"].append({
        "resource": {
            "resourceType": "DocumentReference",
            "id": "mhr-act-citation",
            "description": "My Health Records Act 2012 (Cth) — consolidated text",
        }
    })

    el_text = extract_federation_from_contract(bundle)

    assert (
        '//     source: "My Health Records Act 2012 (Cth) — consolidated text"'
        in el_text
    )


def test_rule_recorded_as_provenance_comment_only():
    el_text = extract_federation_from_contract(_referral_network_bundle())

    assert "DocumentReference/referral-scenario-el" in el_text
    assert "traceability only; not rendered" in el_text


def test_no_rule_present_omits_provenance_comment():
    el_text = extract_federation_from_contract(
        _referral_network_bundle(include_rule=False)
    )
    assert "provenance" not in el_text


# ── Round-trip: generated text must actually parse with the real grammar ──

def test_generated_federation_round_trips_through_real_parser():
    """
    A string-matching test alone doesn't prove the output is valid ODP-EL —
    it must actually parse. extract_federation_from_contract() deliberately
    does not emit the 'community' or 'normative_policy' declarations it
    references by name (see its docstring's "What is NOT emitted" section),
    so this test supplies minimal companion stubs for those, mirroring how
    referral_scenario.el declares GPPracticeCommunity/SpecialistPracticeCommunity
    and the three normative policies as separate top-level elements
    alongside ReferralNetworkFederation itself.

    validate=False: this asserts syntactic validity via the real textX
    grammar (the specific claim under test) without also asserting that
    these hand-authored minimal companion stubs satisfy every unrelated
    el_validator.py semantic rule, which is out of scope for this test.
    """
    from el_parser import parse_string

    generated = extract_federation_from_contract(_referral_network_bundle())

    companion = """
community GPPracticeCommunity
    description: "Standing organisational community for the GP practice"
    {
        objective: "Maintain a registered, capable GP clinician workforce"
    }

community SpecialistPracticeCommunity
    description: "Standing organisational community for the specialist practice"
    {
        objective: "Maintain a registered, capable specialist clinician workforce"
    }

normative_policy MyHealthRecordsAct {
    source: "My Health Records Act 2012 (Cth)"
    kind: legislation
}

normative_policy NationalClinicalGovernance {
    source: "National Model for Clinical Governance (ACSQHC, 2026)"
    kind: standard
}

normative_policy AIMedicalDeviceRegulation {
    source: "TGA regulation of Software as a Medical Device"
    kind: regulation
}
"""

    full_spec = (
        "enterprise specification GeneratedFederationRoundTrip\n"
        f"{companion}\n{generated}\n"
    )

    result = parse_string(full_spec, validate=False)
    assert result.ok, f"Parse errors: {result.errors}"


# ── Error handling ──────────────────────────────────────────────────────────

def test_missing_contract_resource_raises_value_error():
    bundle = {
        "resourceType": "Bundle",
        "id": "no-contract-bundle",
        "entry": [
            {"resource": {"resourceType": "Organization", "id": "gp-practice", "name": "GPPractice"}},
        ],
    }
    with pytest.raises(ValueError, match="no Contract resource"):
        extract_federation_from_contract(bundle)


def test_unresolvable_signer_party_raises_value_error():
    bundle = _referral_network_bundle()
    contract = next(
        e["resource"] for e in bundle["entry"]
        if e["resource"]["resourceType"] == "Contract"
    )
    contract["signer"].append({
        "party": {"reference": "Organization/does-not-exist"},
        "type": {"coding": [{"code": "unknownRole"}]},
    })

    with pytest.raises(ValueError, match="does not resolve to an Organization"):
        extract_federation_from_contract(bundle)
