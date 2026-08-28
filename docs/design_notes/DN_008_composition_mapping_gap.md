# DN_008 — Composition-Based Document Bundles Are Entirely Unmapped

*Design note. Empirically confirmed against a real, live HAPI server
running the current stable `hl7.fhir.au.ps` (1.0.0) package, a real
`fhir_mapper.py` run, and real generated output — not inferred or
predicted. Grounds directly in AU Patient Summary's own "Referral to
Specialist and Allied Health" use case (2026-08-28 session).*

---

## 1. What was built and tested

A minimal but genuinely valid AU PS referral, end to end:

- `Composition` (AU PS profile, `au-ps-composition`) — three mandatory
  sections (Problem List, Allergies, Medications), correctly using
  `emptyReason` per the profile's own conformance rules, referencing a
  real `Patient` and `PractitionerRole`.
- `ServiceRequest` — a referral to endocrinology, with `supportingInfo`
  pointing at the `Composition` — matching AU PS's own described
  mechanism precisely: *"the referral... includes a patient summary."*

Both validated cleanly against the server. Both fetched live and run
through the real `FHIRConsentMapper.map_bundle()`.

## 2. The finding

**The `ServiceRequest` mapped correctly, exactly as expected** — R05
(`Commitment`, `by: GeneralpractitionerGuthridgeJarred`) and R07
(`Burden`), the same pattern confirmed repeatedly across every prior
`ServiceRequest` test this session. The `for_action` gap (SNOMED code not
in the mapper's action-lookup table) reproduced a **third** time, now
across a third independent code — further confirming that gap is real
and consistent, not a one-off.

**The `Composition` produced nothing at all.** Not an error, not a
warning — the mapper's provenance table contains zero lines referencing
`Composition/171`. It was present in the bundle and silently ignored.
Confirmed by direct inspection of `fhir_mapper.py`'s rule set: there is
no mapping rule for `Composition` today.

## 3. Why this matters — the actual content of AU PS is invisible to governance

The referral's *transaction* (who requested what, from whom) is
governed. The referral's *substance* — the clinical content AU PS exists
specifically to carry — has no governance representation whatsoever.
Given the use case's own name is "Clinician Driven Patient Summary (**as
Supplemental Information**)," this means the actual point of the use
case is the part currently invisible to the governance layer.

## 4. A direct, concrete connection to DN_004 — worth stating plainly

This is not a coincidental gap. Confirmed directly from the live server's
own `au-ps-composition` `StructureDefinition`: nearly every element
(`status`, `author`, each section, each `emptyReason`) carries real,
structured `http://hl7.org/fhir/StructureDefinition/obligation`
extensions — `SHALL:populate` for the producer actor, `SHALL:handle` for
the consumer actor, `SHOULD:display` for the consumer actor — the exact
FHIR Obligations mechanism DN_004 already grounds its whole positioning
in.

**DN_004's central claim, now demonstrated with real data rather than
argued abstractly:** FHIR Obligations declare what an actor must do with
an element (e.g. the receiving clinician's system `SHALL:handle` the
Problem List section). They do not — and this `Composition` profile is a
clean, concrete proof of it — express whether that handling *actually
happened*, what obligation exists on the receiving clinician to *act* on
what they were shown, or what follows if they don't. That is precisely
the "declare vs verify" gap DN_004 argued FHIR Obligations leave open,
and precisely the gap this toolchain is positioned to fill — except,
per this note, it currently doesn't, for this resource type.

## 5. What a mapping rule could look like — sketched, not committed

Not proposed for implementation here; recorded so the next design pass
has a starting point rather than a blank page.

**Option A — attach `Composition` as evidence on the existing burden.**
Extend R07 so that when a `ServiceRequest.supportingInfo` references a
`Composition`, the generated `Burden`'s description or a new field
records that a specific patient summary was attached — turning "was the
referral accompanied by the required clinical context" into a checkable
fact, without inventing a new construct.

**Option B — a new construct for shared clinical content itself.** Map
the `Composition`'s own `SHALL:handle`/`SHOULD:display` obligations
(per section, per actor) into new `Burden`/`Permit` tokens on the
*receiving* clinician — e.g. a burden to actually review the Problem
List before proceeding. This is more faithful to what the FHIR
Obligations actually say, but is real new design work: it would need its
own accountability model for "did the receiving system/clinician
discharge the obligation to review," which nothing in the current
toolchain does yet.

**Recommendation, tentative:** Option B is the more standards-faithful
answer and the stronger DN_004 tie-in, but Option A is smaller and could
be built first to prove the pattern before committing to B's larger
scope — mirroring how this project has sequenced other features (small,
tested step before larger commitment).

## 6. What this note deliberately does not do

No code proposed. No option chosen. This is a confirmed empirical
finding plus a scoped starting point for a future design pass — matching
this project's own standing discipline of naming gaps precisely rather
than leaving them implicit or rushing to close them.
