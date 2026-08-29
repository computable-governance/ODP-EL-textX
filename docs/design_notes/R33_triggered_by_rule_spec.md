# R33 — Rule Specification: `triggered_by` Provenance from Discharge-Generated Requests

*Design artifact, not yet implemented. Written to the standard this
project already follows for every rule (R01–R31): FHIR source pattern,
DSL-EL target, grounded in the actual grammar syntax (verified by grep,
not assumed), with a real worked example from this session's own data.
Ready to hand to CC for implementation, or to add directly to
`toolchain/fhir_mapping_table.md` as its next entry.*

---

## Rule statement

**FHIR source pattern:** A `ServiceRequest` whose `.encounter` reference
points at an `Encounter` with `status: finished`, and whose `authoredOn`
timestamp is at or after that `Encounter.period.end`.

**DSL-EL target:** The `Burden` generated from that `ServiceRequest`
(via the existing R07 rule, unchanged) gains a `triggered_by` reference
to a newly-emitted `EventDecl` representing the discharge, **in addition
to** its normal `state: active` — not instead of it. See "Two sub-cases"
below for why.

## Grounded in the actual grammar (verified, not assumed)

```
('triggered_by'    ':' triggered_by=[EventDecl])?
('discharged_by'   ':' discharged_by=[EventDecl])?
```

```
EventDecl:
    'event' name=ID
    ('description' ':' description=STRING)?
;
```

`triggered_by` and `discharged_by` are both optional fields *alongside*
a burden's `state`, not replacements for it — confirmed by grep against
`grammar/v2/el_grammar.tx`, not inferred from the field name alone.

## Worked example — this session's real data

**Input (already in the fixture, `04-hospital-episode/`):**

- `Encounter/556` — `status: finished`, `period.end:
  "2024-06-10T14:00:00+10:00"`
- `ServiceRequest/558` — `authoredOn: "2024-06-10T14:00:00+10:00"`,
  `encounter: {reference: "Encounter/556"}`, `reasonCode: [{text:
  "Generated automatically on discharge from day-surgery encounter"}]`

**Current output (confirmed, R07 only):**

```
burden Id558Obligation {
    for_action: "follow-up_visit"
    state: active
    discharge_mode: eventual
    priority: normal
    description: "[R07] ... Obligation arising from ServiceRequest/558 ..."
}
```

No trace of *why* this burden exists, as documented in DN_008's addendum.

**Target output, with R33 applied:**

```
event Encounter556Discharge {
    description: "Encounter/556 discharged (period.end: 2024-06-10T14:00:00+10:00)"
}

burden Id558Obligation {
    for_action: "follow-up_visit"
    state: active
    triggered_by: Encounter556Discharge
    discharge_mode: eventual
    priority: normal
    description: "[R07][R33] Obligation arising from ServiceRequest/558, triggered by discharge of Encounter/556"
}
```

## Two sub-cases — this matters, don't collapse them

**R33a — static/batch (build this now).** The referenced `Encounter` is
*already* `finished` at the time the mapper runs — exactly our situation.
The burden is correctly `state: active` (the follow-up genuinely was
already ordered); `triggered_by` here is **provenance**, not masking —
it records *why* the burden came to exist, without changing whether it's
currently active. This is the only sub-case needed to fix DN_008's
"causality lost" finding.

**R33b — live/runtime (future work, not this rule).** If extraction
happened *before* the `Encounter` finished, the burden would need to
start `state: pending` (genuinely masked) and only transition to
`active` when a live event fires — this is the direct structural sibling
of R31 (`Consent.status → inactive`, live), and would belong in
`fhir_event_handler.py`, not `fhir_mapper.py`. Naming this explicitly so
it isn't silently conflated with R33a; not scoped for implementation now.

## Implementation notes for whoever picks this up

- **Detection logic:** for each `ServiceRequest` already producing a
  `Burden` via R07, check whether `.encounter` resolves to another
  resource in the same bundle with `status: finished` and a `period.end`
  at or before this `ServiceRequest.authoredOn`. If so, apply R33a.
- **Event naming:** `{EncounterId}Discharge` is a reasonable convention,
  matching this project's existing `Id{ResourceId}{ConstructType}`
  naming pattern elsewhere in generated output.
- **Does not require a new `EventDecl` per burden** — if multiple
  burdens are triggered by the same discharge, they should reference the
  *same* `EventDecl`, not one each. Worth a de-duplication check in the
  implementation.
- **Test fixture:** the `04-hospital-episode/` resources already built
  this session are a ready-made, real test case — no new fixture data
  needed, just a test asserting the `triggered_by` field appears
  correctly when this exact bundle is mapped.

## What this note deliberately does not do

No code written. No decision made on exact event-naming convention
beyond the suggestion above. R33b is named but explicitly out of scope.
Ready for CC to implement R33a directly against the worked example above
whenever this is picked up.
