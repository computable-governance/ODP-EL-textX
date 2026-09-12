# Synthetic AU eRequesting Claim/Cancellation Fixture — NOT Official IG Examples

*Created 2026-08-24 while investigating the mapper-level gap documented in
`docs/design_notes/DN_005_dynamic_claiming_gap.md`'s addendum. Kept here as
a small, clearly-labeled test fixture for whenever that gap is picked up.
`Task-undirected-unclaimed.json` added 2026-09-12 — see its own section
below.*

## What this is

Two `Task` FHIR resources, hand-constructed to demonstrate the
`request-claimed` / `cancel-handled` business-status pattern:

- `Task-original-filler-now-claimed.json` — the original filler's Task,
  `status: cancelled`, `businessStatus: request-claimed`.
- `Task-alternate-filler-claimed.json` — the alternate filler's new Task,
  `status: requested`, for the same underlying request (same
  `groupIdentifier`).

A third, separate fixture, `Task-undirected-unclaimed.json` (added
2026-09-12), covers a different case — see its own section below.

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

## `Task-undirected-unclaimed.json` — a distinct, undirected-order fixture (added 2026-09-12)

**What this is:** a single `Task`, `status: requested`, with **no `owner`
element at all** — the undirected-order case confirmed as the real AU
eRequesting `$claim` mechanism: an order is lodged with no filler
assigned; a filler later calls `$claim` (requisition identifier + org
reference), which assigns `Task.owner` and returns a new group `Task`.
This is a create-and-link operation, not a same-`Task` `businessStatus`
transition — a different pattern from the `request-claimed` /
`cancel-handled` pair above, not a variant of it.

**Why it's separate from Task/209 (the live HAPI fixture):** Task/209
(`localhost:8081/fhir/Task/209`) has `status: requested` but already has
`owner: Organization/kioma-pathology` assigned — a *directed* order, so it
cannot exercise the `$claim` path. This fixture exists specifically to
cover the case Task/209 can't.

**Anchors reused, not fabricated:** `Patient/roberts-fred`,
`PractitionerRole/generalpractitioner-guthridge-jarred`, and
`Organization/elimbah-medical-centre` are the same real, published anchors
the other two files in this directory use. `groupIdentifier.value`
(`EMC4542244-5627`) and the `focus` reference
(`ServiceRequest/order-fbc-undirected-1`) are both new, synthetic values —
deliberately distinct from Task/209's `EMC4542244-5625` and from this
directory's existing pair's `EMC4542244-5624`/`order-xray-1`, so none of
the three can be mistaken for one another.

**Status as of 2026-09-12:** design/fixture step only. Not yet run through
`fhir_mapper.py`; no `$claim` runtime mechanism exists yet to act on it
(see DN_005 §3's Option C, not yet implemented). This fixture is here so
that work has something concrete to act on when it starts.
