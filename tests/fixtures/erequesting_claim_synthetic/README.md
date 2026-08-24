# Synthetic AU eRequesting Claim/Cancellation Fixture — NOT Official IG Examples

*Created 2026-08-24 while investigating the mapper-level gap documented in
`docs/design_notes/DN_005_dynamic_claiming_gap.md`'s addendum. Kept here as
a small, clearly-labeled test fixture for whenever that gap is picked up.*

## What this is

Two `Task` FHIR resources, hand-constructed to demonstrate the
`request-claimed` / `cancel-handled` business-status pattern:

- `Task-original-filler-now-claimed.json` — the original filler's Task,
  `status: cancelled`, `businessStatus: request-claimed`.
- `Task-alternate-filler-claimed.json` — the alternate filler's new Task,
  `status: requested`, for the same underlying request (same
  `groupIdentifier`).

## What this is NOT

**These are not official AU eRequesting IG examples.** They were
constructed because, as of 2026-08-24, none of the five officially
published Task examples in the IG happen to demonstrate this
business-status pattern in context (checked directly against
`build.fhir.org/ig/hl7au/au-fhir-erequesting/examples.html`).

## Why they can still be trusted as conformant

Every element that matters for the pattern being tested is drawn from
genuinely public sources, verified directly, not assumed:

- The `businessStatus` code system
  (`http://terminology.hl7.org.au/CodeSystem/task-business-status`) and the
  two codes used (`request-claimed`, `cancel-handled` — though only
  `request-claimed` is exercised in these two files) are copied verbatim
  from the IG's own public `ValueSet-au-erequesting-task-businessstatus`
  page, fetched directly from `build.fhir.org` (HL7 Australia's own build
  server — not a third-party or vendor source).
- The referenced `Organization`, `Patient`, and `PractitionerRole`
  resources (`mount-charlton-radiology`, `kioma-pathology`,
  `roberts-fred`, `generalpractitioner-guthridge-jarred`) are all real,
  officially published IG example resources, reused here as anchors so
  the fixture resolves against genuinely public data if loaded alongside
  the official example set.

## Known result when run through the current mapper (2026-08-24)

Running this pair through `FHIRConsentMapper.map_bundle()` produces two
entirely independent `delegation` constructs with no relationship between
them — `businessStatus` is not read by `_map_task` at all. This is the
exact, empirically-confirmed finding documented in DN_005's addendum. If
`_map_task` is ever extended to recognise this pattern, re-running this
fixture through the mapper is the natural first regression check.
