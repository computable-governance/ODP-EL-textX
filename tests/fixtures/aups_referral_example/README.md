# AU Patient Summary Referral Fixture

*Created 2026-08-28 while investigating the mapping gap documented in
`docs/design_notes/DN_008_composition_mapping_gap.md`. Kept here as a
small, real, standards-conformant test fixture for whenever that gap is
picked up.*

## What this is

Two FHIR resources demonstrating AU Patient Summary's own "Referral to
Specialist and Allied Health" use case (`build.fhir.org/ig/hl7au/au-fhir-ps/uc-referral.html`) —
a referral carrying a patient summary as supplemental information:

- `Composition-roberts-fred-summary.json` — a minimal but genuinely valid
  AU PS patient summary, `au-ps-composition` profile (`hl7.fhir.au.ps#1.0.0`).
  The three mandatory sections (Problem List, Allergies, Medications) are
  present using the profile's own `emptyReason` mechanism rather than
  fabricated clinical content.
- `ServiceRequest-referral-endocrinology.json` — a referral to
  endocrinology, with `supportingInfo` referencing the `Composition`
  above, matching the use case's own description exactly.

Both were built and validated live against a local HAPI FHIR server
running the real `hl7.fhir.au.ps@1.0.0`, `hl7.fhir.au.core@2.0.0`, and
`hl7.fhir.au.ereq@1.0.0` packages, referencing supporting resources
(`Patient`, `Organization`, `PractitionerRole`) already established
earlier in this session's work (see the eRequesting-claiming fixture in
this same `tests/fixtures/` directory for those).

## Why it's smaller than a full patient summary

A full AU PS document can include many clinical sections. This fixture
deliberately covers only the three *mandatory* ones, using `emptyReason`
rather than inventing conditions/medications/allergies data — enough to
be a genuinely valid, conformant document without the effort of building
out every possible section type.

## Known result when run through the current mapper (2026-08-28)

Running these two resources through `FHIRConsentMapper.map_bundle()`
produces a correctly-mapped `Commitment`/`Burden` pair from the
`ServiceRequest` (R05/R07) — and **nothing at all** from the
`Composition`. Confirmed by inspection: `fhir_mapper.py` has no mapping
rule for `Composition` resources today. This is the exact,
empirically-confirmed finding DN_008 documents. If a `Composition`
mapping rule is ever added, re-running this fixture is the natural first
check.
