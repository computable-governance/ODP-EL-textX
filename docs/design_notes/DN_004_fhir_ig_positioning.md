# DN_004 — FHIR IG Positioning: ODP-EL Governance as a Verification Layer over FHIR Obligations, in the Sparked / AU Context

*Design/positioning note — companion to DN_003. Addresses: how the ODP-EL
governance extension (the claiming/delegation work of DN_003, and the
governance layer generally) should be positioned relative to AU eRequesting
as a FHIR Implementation Guide — whether a new FHIR profile or extension is
needed, and where the work sits in the Australian (Sparked) ecosystem
specifically. Grounded in current FHIR R5/R6 Obligation mechanics and
current Sparked/HL7-AU sources, verified 2026-08-24, not assumed.*

---

## 0. The two questions, answered up front

**Q: Do we need a new FHIR profile or data-model extension to position this
against eRequesting?**
A: **No — and needing one would be a strategic error.** A new
`StructureDefinition` profile or an extension element on
`Task`/`ServiceRequest` would contradict the settled non-invasive mediator
architecture (analysis §1: the governance semantics are carried externally
in `fhir_mapper.py`/`fhir_event_handler.py`; no FHIR server modification;
the year-old "native FHIR extension" question already answered *no*). The
claiming work of DN_003 changes nothing here — claim/lapse states and the
accept/reject evaluation are token-layer concepts, read from existing
`Task.status`/`businessStatus`, requiring no new FHIR element.

**Q: Then how *is* it positioned?**
A: **As a verification-and-lifecycle layer anchored to FHIR's own
Obligations + ActorDefinition mechanism** — not a freestanding companion
document, and not a data-model change. FHIR now has a native way to
*declare* per-actor behavioural expectations; it does not yet have a way to
*verify* them or to express obligation *lifecycles*. That gap is precisely
the ODP-EL layer's contribution.

---

## 1. FHIR already has a behavioural-specification layer — and it stops exactly where ODP-EL begins

This is the key finding, and it sharpens the positioning considerably.
FHIR's behavioural-spec story is more developed than a data-model-only
reading assumes. Three current pieces (verified against the R5 spec and R6
ballot):

- **FHIR Obligations** (R5 Implementation Obligations, Trial-Use; carried
  into R6 ballot): an IG can attach machine-processable behavioural codes
  to profile elements via the `obligation` feature of `ElementDefinition`.
  The spec's own framing: the base FHIR spec covers interfaces and resource
  content, while IGs "are also concerned with application behavior — what
  information must be provided under what conditions, and setting
  expectations for how particular data elements are handled," expressed via
  `mustSupport` and `obligation`.
- **ActorDefinition** (R5): formally names the actors those obligations
  bind — "a human or an application that plays a role in data exchange, and
  that may have obligations associated with the role the actor plays."
- **Live in the AU ecosystem:** AU Core carries mustSupport/obligation/actor
  definitions, and profiles deriving from AU Core inherit them. My Health
  Record's FHIR IG already uses obligation codes (handle / display /
  process / populate-if-known) bound to actors like the MHR Gateway
  Requester.

**But note precisely what a FHIR Obligation is and is not:**

- It binds to a **single profile element** and says "for *this data
  element*, *this actor* SHALL handle / display / populate-if-known it." It
  is an **element-scoped, static, per-actor data-handling expectation**,
  drawn from a fixed code value set.
- It is **not** a state machine, **not** a deontic lifecycle, and carries
  **no** notion of: an obligation *arising from a violation*; an
  *accountability chain* across a delegation; *who is authorised to drive a
  state transition*; or *what new obligation falls on whom* when a
  transition does or doesn't happen.

That second list is exactly the ODP-EL token model's content, and exactly
what AU eRequesting names as out of scope ("who is authorised to transition
state"; the Task Group "not enforced" aggregation caveat). **FHIR
Obligations are element-scoped and static; ODP-EL tokens are
lifecycle-scoped and dynamic.** Neither replaces the other — they meet at a
clean, defensible boundary.

## 2. The layering, stated cleanly

The Australian stack already has an explicit "what vs how" split that this
extends by one layer. In AUeReqDI's own words, its data groups define *what*
clinical information is required for an eRequest but "do not specify how the
data is exchanged; this is the role of the FHIR standard." The natural
continuation:

| Layer | Question answered | Australian artefact |
|---|---|---|
| Clinical data requirements | *What* information is needed | AUCDI / AUeReqDI (Sparked) |
| FHIR profiles + interactions | *How* it is exchanged | AU Core / AU eRequesting IG |
| FHIR Obligations + ActorDefinition | *Which actor must handle which element, how* | AU Core obligations (element-scoped, static) |
| **ODP-EL governance (this work)** | ***Who is accountable across a delegation, who may claim/transition, and what obligation follows a violation*** | **the proposed companion governance layer** |

Each layer references the one above by canonical identity, adds nothing to
its data model, and answers a question the layers above deliberately do not.

## 3. The specific contribution: FHIR can now *declare* actor obligations but not yet *verify* them

This is the sharpest and most defensible framing, and it is stated by the
FHIR community itself — not something the project has to argue into
existence.

- The FHIR-Obligations movement's own thesis is that narrative "Must
  Support" conformance is not machine-testable and fragments responsibility
  across actors, and that coded obligations make behavioural expectations
  "explicit, coded, and testable."
- But an independent 2025 study applying FHIR Obligations to a national
  core dataset found, in its own conclusions, that current IG tooling does
  not yet support obligations, that conformance testing was not addressed,
  and that further work is needed to standardise ActorDefinition resources
  and **develop validation tooling** to realise obligation-driven
  specifications' full potential.

That is the opening, stated by the community: **the declarative obligation
layer exists; the verification/conformance layer for it does not.** The
ODP-EL Kripke verifier is exactly a formal conformance-checking engine for
obligation-driven behaviour — it proves properties (e.g. mutual exclusion:
no two fillers simultaneously active-claiming one request; eventual
resolution: every claim attempt terminates in a defined outcome) that a
static per-element obligation code cannot express, let alone check.

**Positioning statement (for the paper, the newsletter, and any Sparked /
R2 conversation):**

> FHIR now provides a way to *declare* per-actor obligations on data
> elements. It does not yet provide a way to *verify* obligation
> *lifecycles* — who is accountable across a delegation, who may claim or
> transition a request, and what obligation arises when one is not met.
> ODP-EL governance is a candidate formal semantics and verification layer
> for FHIR obligation-driven specifications, with AU eRequesting claiming
> as the worked example.

## 4. Concrete, low-friction engagement mechanics (no profile, no extension)

Ordered least-to-most ambitious; all avoid touching any FHIR data model:

1. **Anchor to ActorDefinition as shared vocabulary.** Map AU eRequesting's
   Placer / Filler / Patient / Server (and their `ActorDefinition`s) to the
   ODP-EL `role`/party constructs, so the governance spec and the IG
   provably refer to the same actors. This is a real FHIR resource used as
   the join point — not an invented bridge.

2. **Publish an obligation-code → token-state mapping.** Show that specific
   FHIR Obligation codes on eRequesting `Task`/`ServiceRequest` elements
   *correspond to* ODP-EL token states/transitions — e.g. a
   `SHALL:populate-if-known` obligation on a supporting-info element (an
   Adverse Reaction Risk Summary, a Problem/Diagnosis Summary) is, in the
   governance model, an undischarged burden gating progression, with a
   computed violation path if the request advances without it. This gives
   the R2 group something legible in *their own newest vocabulary* rather
   than asking them to learn ODP-EL cold.

3. **Contribute formal invariants back where FHIRPath can carry them.** The
   subset of governance properties expressible as FHIR `invariant`
   constraints or an `OperationDefinition` conformance rule on the claim
   operation (e.g. the mutual-exclusion property) can be handed to the R2
   group as formally-stated versions of rules the IG currently only
   describes in prose ("not enforced"). Narrower than the full model
   (FHIRPath cannot express accountability chains), but the slice that fits
   is a genuine standards contribution.

4. **Position ODP-EL as the verification layer for obligation-driven IGs
   generally.** The paper/journal framing: FHIR IGs specify what/when
   (resources, states, obligations); a companion ODP-EL specification
   specifies and *verifies* who-may / what-follows / who's-accountable.
   eRequesting is the reference worked example, not the whole claim.

## 5. Sparked-specific placement

The engagement path is Australian-specific and already mapped:

- **The venue exists and is open.** AU eRequesting is developed through the
  Sparked AU FHIR Accelerator (CSIRO AEHRC + Department of Health,
  Disability and Ageing + ADHA), via HL7 Australia Technical and Clinical
  Design Groups, with participation open and coordinated on the HL7-AU Zulip
  Australia stream. R2 scope is being defined now (analysis / session
  findings), which is the moment a verification-layer contribution is most
  useful.

- **The credibility asset is real and specific.** Direct involvement in the
  Sparked program's HL7 Australia FHIR Encounter customisation work (per
  standing project context) is a genuine standing-in-the-community asset for
  a contribution framed as *adding a verification layer to Sparked's own
  obligation-driven direction*, not as an outside proposal.

- **Sparked already thinks in "what vs how" layers** (AUCDI/AUeReqDI =
  what; AU Core / eRequesting IG = how). A governance/verification layer
  presented as the *next* layer in a sequence the community already uses is
  a far easier sell than a novel category — it slots into an existing mental
  model rather than competing with it.

- **AI is already in Sparked's frame.** CSIRO AEHRC (which leads Sparked)
  publicly foregrounds AI/ML in health-system decision support. A
  governance layer whose distinguishing claim is that it governs *AI-agent*
  behaviour by observable speech acts (EDOC framing) lands into an
  ecosystem already primed for the AI angle — the "who is accountable when
  an AI agent claims or transitions a request" question is native to both
  this work and Sparked's stated interests.

## 6. What NOT to do (guardrails)

- **Do not propose a new `StructureDefinition` profile or a `Task`/
  `ServiceRequest` extension element** — it contradicts the non-invasive
  architecture and moves value away from where it actually is.
- **Do not frame this as "fixing" or "extending" eRequesting's data model.**
  Frame it as adding the verification/lifecycle layer above eRequesting's
  (and FHIR's) obligation layer.
- **Do not claim ODP-EL replaces FHIR Obligations.** They are
  complementary: element-scoped/static vs lifecycle-scoped/dynamic. Say so
  explicitly, every time.
- **Do not overstate the FHIRPath-invariant contribution.** Only a subset
  of governance properties is expressible as FHIR invariants; the
  accountability-chain content is not. Offer the expressible slice honestly
  and keep the rest in the companion layer.

## 7. Sources grounding this note (verified 2026-08-24)

- FHIR R5 Implementation Obligations (`hl7.org/fhir/R5/obligations.html`);
  R6 ballot conformance-rules and obligations pages.
- FHIR R5 ActorDefinition (`hl7.org/fhir/R5/actordefinition.html`).
- My Health Record FHIR IG conformance (obligation codes bound to actors).
- International Patient Access / IPA conformance (obligation-per-actor
  pattern in practice).
- MII Core Dataset FHIR-Obligations study (PubMed, Sept 2025) — the
  "declared but not yet verifiable / no validation tooling" finding.
- Sparked / HL7-AU: AU eRequesting IG, AUeReqDI ("what vs how" framing),
  AU Core IG, Sparked Program Review 2023–2025, CSIRO AEHRC.

*All FHIR/Sparked material cited here is public. This note references no
non-public R2 material; the claiming mechanism it points at is described at
the token-model level only, consistent with DN_003's provenance notes.*
