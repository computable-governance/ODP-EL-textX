# DN_009 — Consolidated Mapping-Update Analysis: What Needs Fixing, and Where

*Rev. 2 — corrects Rev. 1's central claim after direct grep verification
against `grammar/v2/el_grammar.tx`. Rev. 1 asserted a new grammar
construct was needed for `artefact` objects; this was wrong, and the
correction changes the whole document's conclusion. Written after
completing all four `ConnectedCare` touchpoints (DN_007 v1 scope),
consolidating every finding from DN_008's addenda. Grounded against
ISO/IEC 15414:2015, its base standard (ISO/IEC 10746-2), and the actual
current grammar file throughout.*

---

## 0. The headline finding (corrected)

**None of the six findings from this build require any change to GA's
grammar or engine. This is, in its entirety, a `fhir_mapper.py`
rule-writing exercise.** Every mechanism needed — `artefact_object`
declarations, `ArtefactRef` participant references, `Process`/`Step`
constructs, `triggered_by` masking, `discharged` token states — already
exists in the grammar and engine, confirmed by direct inspection, not
inferred. The gap in every single case is that the mapper never wrote a
rule using what's already there.

**This is genuinely good news for scoping next-session work:** there is
no grammar-design decision to make, no risk of destabilising the core
DSL, and no dependency on any of the still-open design notes (DN_005's
Option C, DN_007's remaining touchpoints). This is contained,
well-understood, mapper-only work.

## 1. Summary table (corrected)

| Finding | What it is | Classification | Grounding |
|---|---|---|---|
| `Composition` unmapped | AU PS patient summary document | **Mapper-rule only** — `artefact_object` (§6.3.3) and `ArtefactRef` already exist in the grammar, confirmed by grep; the rule to emit them was simply never written | `el_grammar.tx` lines 87–98, 628–634 |
| `DiagnosticReport` unmapped | Pathology result | **Mapper-rule only** — same `artefact_object` mechanism as `Composition` | same |
| `Encounter` unmapped | Consultation/admission event | **Mapper-rule only** — maps naturally onto the existing `Process` construct (§7.8.5): `Encounter.period.start`/`.end` → `initiates`/`terminates`; resources occurring within the encounter → `steps` | `el_grammar.tx` lines ~690–700 (`Process` rule) |
| `Condition` unmapped | Clinical diagnosis | **Mapper-rule only, minor** — best treated as description-text enrichment on an existing `Commitment`/`Burden`, not a declared object at all | X.902 §6.2 (proposition) |
| `Procedure` unmapped | Recorded completed action | **Mapper-rule + bridge infrastructure** — should trigger a **discharge** of the `Burden` its ordering `ServiceRequest` created; the engine's `discharged` state already exists and needs no change | §7.8.4 (action roles); engine discharge mechanics already proven working |
| Causality lost (`triggered_by`) | Discharge → follow-up sequence indistinguishable from a planned commitment | **Mapper-rule only — the single highest-value item** | `triggered_by` masking already implemented and proven throughout `referral_scenario.el` |

## 2. Detail, per finding

### 2.1–2.2 `Composition` and `DiagnosticReport` — confirmed existing mechanism, not a gap

Direct grep of `el_grammar.tx`:

```
ObjectKind:
    'party' | 'agent' | 'active_object' | 'artefact_object' | 'resource_object'
;
```

with the grammar's own comment: *"artefact_object — §6.3.3 EO referenced
but not acting."* And separately, for referencing an artefact within an
action:

```
ArtefactRef : 'artefact' ':' ref_name=ID ;
```

with comment citing §6.3.3 and §7.8.4 directly. **Both constructs already
exist, fully implemented, standards-cited in the grammar's own inline
documentation.** The needed mapper rule is straightforward in shape:
recognise a `Composition` or `DiagnosticReport`, emit an
`artefact_object` declaration for it, and add an `ArtefactRef` to
whichever action (`Commitment`/`Delegation`) references it via FHIR's
own `supportingInfo`/`reasonReference` fields.

### 2.3 `Encounter` — corrected from Rev. 1's "activity" framing to the grammar's actual `Process` construct

Rev. 1 cited the base standard's abstract `activity`/`behaviour`
concepts (X.902 §8.6–8.7) as if they were a separate thing from what the
grammar implements. Checked directly, §6.3.6 of the enterprise-language
standard itself resolves this precisely — `process` is not a different
concept from `activity`, it is the enterprise-language-level term for
the same structural idea:

> *"process: A collection of steps taking place in a prescribed manner.
> ... NOTE 2 — The activity structure concepts provided in clause 13.1 of
> Rec. ITU-T X.902 | ISO/IEC 10746-2 may be used, after substitution of
> 'step' for 'action' and 'process' for 'activity', to specify the
> structure of a process."*

So Rev. 1's instinct (activity/behaviour-like structure fits `Encounter`
better than `artefact`) was right; it was only imprecise about which
grammar construct realises that idea. The grammar implements this
concretely as **`Process`** (§7.8.5), confirmed by direct inspection:

```
Process:
    'process' name=ID
    ...
    '{'
        'initiates' ':' initiation=STRING
        'terminates' ':' termination=STRING
        steps+=Step+
    '}'
;
```

This maps onto `Encounter` almost exactly as-is: `Encounter.period.start`
→ `initiates`, `Encounter.period.end` (once `status: finished`) →
`terminates`, and the resources that reference the encounter (the
`Procedure`, the follow-up `ServiceRequest`) → `steps` — each `Step`
itself an abstraction of an action per §6.3.7, which may leave some
participants unspecified, matching how loosely a FHIR-derived step would
be populated. No new grammar needed; a mapper rule emitting a `Process`
block from an `Encounter` and its referencing resources is the whole
task.

### 2.4 `Condition` — unchanged from Rev. 1, still minor

A `Condition` remains best understood as a proposition (X.902 §6.2), not
an object filling any action role. Lowest-priority item; enriching an
existing `Commitment`'s description text is plausible value, not
structurally significant.

### 2.5 `Procedure` — unchanged from Rev. 1, still mapper + bridge, no grammar change

A completed `Procedure` should discharge the `Burden` its ordering
`ServiceRequest` created. The engine's `discharged` state already exists
and needs no change — the gap is purely: (a) a mapper rule connecting
`Procedure.status: completed` to a discharge call, matched to its
ordering `ServiceRequest`, and (b) if live (not just batch) discharge
is wanted, a bridge endpoint mirroring the already-working
`POST /fhir/consent-events` pattern.

**Honest note, unchanged from Rev. 1:** our own `Procedure/557` doesn't
carry a `basedOn` reference to `ServiceRequest/554` — only `encounter`
and `reasonReference` to `Condition/553`. Any real rule needs a reliable
way to find the ordering `ServiceRequest`; worth correcting in the
fixture data itself before this rule is designed.

### 2.6 Causality lost — unchanged from Rev. 1, still the top-priority item

GA's `triggered_by` masking mechanism already exists and is proven
working throughout `referral_scenario.el`. Nothing about GA's core needs
to change. The entire gap is that `fhir_mapper.py` has no rule
recognising "this `ServiceRequest.authoredOn` matches a referenced
`Encounter`'s discharge timestamp" as the FHIR-side signature of a
`triggered_by` relationship.

## 3. Prioritisation for the next mapper-focused session

All six items are now confirmed same-tier in risk (mapper-only, no
grammar/engine exposure). Ordered by value:

1. **`triggered_by` rule (§2.6)** — highest value. The one thing that
   lets the generated spec actually demonstrate "obligation-driven, not
   template-driven" rather than merely produce plausible-looking output.
2. **`Procedure`-discharge rule (§2.5)** — second highest, same proven
   shape as the working Consent bridge; fix the fixture's missing
   `basedOn` reference first.
3. **`artefact_object`/`ArtefactRef` rule for `Composition`/
   `DiagnosticReport` (§2.1–2.2)** — genuinely easy now that it's
   confirmed to be "use an existing construct," not "design a new one."
   Could reasonably be done before item 2, if preferred, given the
   grammar work is already done.
4. **`Process` rule for `Encounter` (§2.3)** — moderate value, same
   "existing construct, just needs a rule" shape.
5. **`Condition` description enrichment (§2.4)** — lowest priority, do
   last or skip.

## 4. What this note deliberately does not do

No mapper code written. No rule numbering assigned (would be `R33`
onward, per the established convention). No decision made on which item
to build first — §3 is a recommendation, not a commitment. This is
scoping only, ready for whenever mapper-focused work resumes.

## 5. The process to follow — this is not a new pattern, it continues an existing one

*Added after checking the historical record (`FHIR_ODP_EL_Positioning_
Notes_2026-06-26.md`, the EDOC26 revision notes). Two of §3's priority
items turn out to be the direct continuation of a design already scoped
once before, for `Consent`, and never generalised.*

**The precedent: R30/R31.** A prior design session identified that some
FHIR signals are live events, not static facts — specifically
`Consent.status → inactive` mid-episode. This produced an explicit
architectural split, confirmed in the record:

- **Static extraction** → `fhir_mapper.py`, at session start (R01–R30)
- **Runtime events** → a separate module, `fhir_event_handler.py`,
  firing mid-session (R31)
- **Both confined to Layer 1 only** — *"Layers 2–4 require no
  modification. The governance and verification machinery is
  FHIR-agnostic by design."*

This is the same conclusion §0 reached independently, for a completely
different set of resources — good convergent confirmation, not a
coincidence worth ignoring.

**Mapping this session's priorities onto that precedent:**

- **`Procedure`-discharge (§2.5)** is structurally identical to R31: a
  live status change should propagate into token state. This is the
  next rule in the `fhir_event_handler.py` runtime-event lineage, not a
  new kind of design.
- **`triggered_by` (§2.6)** can start static (recognise the pattern at
  mapper-run time, matching how it was actually tested this session)
  with an R31-style live extension as a natural later step.
- **`artefact_object`/`Process` rules (§2.1–2.3)** are genuinely static,
  `fhir_mapper.py`-only, no event dimension — simpler in this specific
  sense than the other two.

**The concrete steps, distilled from how R01–R31 were actually built:**

1. Assign the next rule number (`R33` onward — `R32` is already
   reserved/deferred per the existing audit table).
2. Add a table entry to `toolchain/fhir_mapping_table.md`, same format
   as every existing rule (Rule | FHIR source | DSL-EL target), plus
   prose elaboration.
3. Classify static vs. runtime-event explicitly; file runtime ones in
   `fhir_event_handler.py` with a corresponding `el_api.py` endpoint,
   mirroring `POST /fhir/consent-events` precisely.
4. Implement, write a fixture + test file (matching
   `test_erequesting_claiming_scenario.py`'s pattern), run the full
   suite, and reproduce the result independently via CC before
   committing — same discipline as every other change this session.

