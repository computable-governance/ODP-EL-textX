# FHIR Bundle Verification Note — 2026-07-13

## Purpose

A small, hand-built FHIR R4 bundle representing the reference `referral`
scenario's clinical situation was run through all three current
`fhir_mapper.py` extraction functions, to check whether the mapper's
output is structurally consistent with the hand-authored
`scenarios/referral/referral_scenario.el`. This closes the loop flagged
in the 2026-07-11/12 diagramming sessions: the FHIR mapping components
had never actually been exercised against data resembling the specific
reference scenario.

**This is a verification exercise, not a scenario in its own right.** It
does not fit `scenarios/README.md`'s maturity tier system
(probe/candidate/reference/demo/historical/superseded), which classifies
DSL-EL `.el` governance specifications — this bundle is a FHIR test
fixture validating an existing one. Filing location (proposed):
`scenarios/referral/fhir_bundle_sample.json`, alongside the scenario it
validates, or `tests/fixtures/` if treated purely as test input.

## Bundle contents

`Organization` ×2 (GP Practice, Specialist Practice), `Practitioner` ×2
+ `PractitionerRole` ×2 (linking each practitioner to their
organisation), `Patient`, `Device` (Specialist AI Agent), `ServiceRequest`
(the referral, using SNOMED `306207001` verified in the 2026-07-10
session), `Consent` (provision: permit), `Contract` (signer × GP Practice
+ Specialist Practice, term × MyHealthRecordsAct + NationalClinicalGovernance),
`Encounter` (participant type=ATND → GP Clinician, serviceProvider → GP
Practice, episodeOfCare reference for traceability).

## Results

### extract_encounter_context() — R26-R29 — PASS

```
EncounterContext(
    referring_practitioner='GpClinician',
    gp_practice='GpPractice',
    episode_reference='EpisodeOfCare/ep-001'
)
```

Matches the reference scenario's `GPClinician`/`GPPractice` actors
(casing differs only because `_sanitize_id` title-cases each hyphen
segment — cosmetic, not structural).

### extract_federation_from_contract() — R23+R24 — PASS

Produced two `community_object` declarations, a `contract federation
ReferralNetworkFederation` block with both interface roles
(`gpPracticeRole`, `specialistPracticeRole`) and both `member:` entries
correctly assigned, plus commented `normative_policy` stubs for
`MyHealthRecordsAct` and `NationalClinicalGovernance` with `source`
pre-filled from `Contract.term.text` — exactly the behaviour documented
for this rule.

### FHIRConsentMapper (R01-R18 subset exercised) — PASS at field level, GAP at community-structure level

**Confirmed correct:**
- **R06** (2026-07-10 fix): `commitment.by: GpPractice` — the
  organisational party, not the individual clinician — confirming
  `ServiceRequest.requester` correctly resolves via
  `PractitionerRole.organization`.
- **R07**: the `ServiceRequest.note` text ("requires patient consent for
  AI-assisted diagnostic review") correctly triggered
  `discharge_mode: strict` and `priority: critical` automatically, with
  no manual flag — confirming `_is_consent_related()`.
- R01, R02, R03, R04, R05, R16, R18 all produced structurally valid
  output tracing correctly to their source resources.

**Real, substantive gap identified:** `FHIRConsentMapper` generates one
flat `community` per bundle (`FhirbundleCommunity` in this run). The
reference scenario has a materially richer structure —
`GPPracticeCommunity`, `SpecialistPracticeCommunity`,
`ReferralEpisodeCommunity`, `PatientDataAuthorshipDomain` and
`PatientDataConsentDomain` (split 2026-07-22 from the original single
`PatientDataDomain`), all connected via
`ReferralNetworkFederation`. These are not close enough in shape for a
direct structural comparison as-is. Closing this gap fully would require
extending `FHIRConsentMapper`'s community-generation logic to produce a
multi-community/domain/federation architecture from bundle content,
rather than one flat community — separate, non-trivial future work, not
attempted here.

**Two cosmetic issues in the test bundle itself** (not mapper bugs):
practitioner names rendered as `"Dr ()"` because the bundle used a flat
`name.text` field rather than FHIR's structured `family`/`given` fields;
and the bundle lacked a top-level `id`, so provenance comments read
"Bundle/unknown". Worth fixing if this bundle is reused, not significant
for this verification's purpose.

## Conclusion

The field-level mapping logic across R01-R07, R16, R18, R23+R24, and
R26-R29 is verified correct and consistent with the reference scenario's
actual design intent, using a bundle built independently of the scenario
file (not reverse-engineered from it). The community-structure generation
capability is a separate, coarser piece of `FHIRConsentMapper` that does
not yet produce output matching the reference scenario's richer
architecture — a real, now-documented gap rather than an assumed one.

## Recommendation

No immediate action required. If full Lane A → Lane B convergence
becomes a priority later, the next step would be extending
`FHIRConsentMapper`'s community-generation logic specifically, informed
by this note's findings, rather than treating today's flat-community
output as a defect to patch superficially.
