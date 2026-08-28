# CC Handover — FHIR Integration Notes

*Docs only, no code changes.*

## File to add

`docs/fhir_integration_notes.md`

## What this is, and why it's not a design note

Unlike `docs/design_notes/DN_00X` files (which propose or scope future
work), this documents **verified current state**: the real HAPI setup,
the accountability-resolution behaviour (`Practitioner` vs
`PractitionerRole` reference resolution, confirmed live), the
`Composition` mapping gap (cross-referencing DN_008), and — new in this
version — the exact root cause and fix for a real HAPI persistence bug
(H2 defaults to in-memory; needed an explicit `spring.datasource.url`
override to a file-based database, verified by an actual
restart-and-recheck test, not assumed).

## Verification before committing

Read through §8 (the persistence section) specifically and confirm the
YAML snippet shown (`spring.datasource.url: jdbc:h2:file:/app/data/h2`)
is syntactically valid and internally consistent with the note's own
description. No live-server reproduction needed for this one — it's
documentation of infrastructure configuration, not a toolchain code
claim.

## Commit

Single docs-only commit. Suggested message: `Docs: FHIR integration
notes — architecture, accountability resolution, HAPI persistence root
cause`. Show diff before committing; hold push until confirmed.
