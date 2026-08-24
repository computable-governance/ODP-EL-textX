# FHIR Obligation Code → ODP-EL Token Lifecycle Mapping

*Companion artefact to DN_004 (FHIR IG positioning). This is engagement
mechanic #2 from DN_004 §4: a concrete, legible-in-FHIR's-own-vocabulary
mapping showing how FHIR Obligation codes (declared, static, element-scoped)
correspond to ODP-EL token states and transitions (verified, dynamic,
lifecycle-scoped). Intended as the artefact to put in front of an R2 / HL7-AU
Design Group conversation — it speaks their newest vocabulary first, and
introduces ODP-EL only as the lifecycle/verification counterpart.*

*Grounded in FHIR R5 Implementation Obligations, ActorDefinition, and the
existing R01–R32 mapping in `toolchain/fhir_mapping_table.md`. All FHIR
material public; no non-public R2 material referenced. Verified 2026-08-24.*

---

## 1. What this mapping is (and is not)

**Is:** a demonstration of *structural correspondence* between two layers —
FHIR's declarative obligation codes and ODP-EL's token lifecycle. It shows
that where a FHIR IG *declares* "this actor must handle this element this
way," the ODP-EL layer can *represent that as a token state and verify the
consequences of meeting or missing it*.

**Is not:** a claim that FHIR Obligations and ODP-EL tokens are the same
thing, nor that one is derivable from the other automatically. They meet at
a boundary (DN_004 §1): FHIR Obligations are **element-scoped and static**
(a code on one element, per actor); ODP-EL tokens are **lifecycle-scoped and
dynamic** (a held object with a holder, a state machine, an accountability
chain, and a violation consequence). The mapping is a correspondence at that
boundary, not an identity — this caveat must travel with the table, exactly
as the FMM/Contract-correspondence caveats do in the main mapping.

## 2. The core asymmetry the mapping makes visible

A FHIR Obligation answers **one static question per element**: *for this
data element, what must this actor do with it?* (handle, display, populate,
populate-if-known, etc.)

An ODP-EL token answers a **dynamic, cross-element, cross-actor** set of
questions: *is this obligation currently active / pending / discharged /
violated / claimable / lapsed? who holds it? who is accountable up the
delegation chain? what new obligation arises if it is violated?*

So the mapping is inherently **one-to-many in the lifecycle direction**: a
single FHIR obligation code corresponds to *one point* in a token's
lifecycle, and the token supplies the rest of the lifecycle FHIR does not
model. That is the whole value proposition in one sentence.

## 3. Obligation-code → token mapping

Obligation codes below are from the FHIR obligation code system (R5).
Token states are the ODP-EL live-engine / Kripke states
(`active | pending | discharged | violated | superseded | claimable |
lapsed`). "Ref R##" points at the existing element→construct rule in
`fhir_mapping_table.md` that establishes which construct the element already
maps to.

| ID | FHIR Obligation code (on an element, for an actor) | ODP-EL correspondence | Lifecycle content ODP-EL adds that the code does not carry | Ref |
|----|-----|-----|-----|-----|
| O-01 | `SHALL:populate-if-known` on a supporting-info element (e.g. Adverse Reaction Risk Summary, Problem/Diagnosis Summary) | An **undischarged `burden`** on the populating actor, gating progression | Whether it is *currently* discharged; whether request progression should be *blocked* while it is pending; the *violation path* if the request advances without it | R07 |
| O-02 | `SHALL:handle` on an element the receiving actor must process | A `burden` on the receiving actor to perform the handling action | The handling action as a *discharge event*; the deadline; the accountable party if handling never occurs | R07, R15 |
| O-03 | `SHOULD:display` / `SHALL:display` | A `permit` (the actor *may*/*is expected to* surface the element) | That display is a *permitted* action, not an obligation to complete a workflow step; distinct from a burden | R16 |
| O-04 | Obligation bound to a specific **actor** via `ActorDefinition` | The token's **holder** (and its position in the accountability chain) | Which party is *accountable* if the obligation is unmet, traced up the delegation chain (R09–R13), not just which actor was named | R01–R04, R09–R11 |
| O-05 | An obligation on a `Task`-state-driving element (who may move `requested`→`received`→`accepted`) | The **claim/accept `evaluation`** gating `claimable → active` (DN_003) | *Who is authorised* to make the transition, and the *lapse* of peers' claim opportunity — the exact eRequesting out-of-scope item | R15 |
| O-06 | (No FHIR obligation code exists for this) — obligation arising *because another was violated* | A `ViolationResponse.obligates` creating a **new burden** on violation (§7.8.6 NOTE 2) | The entire notion of a *derived* obligation; FHIR Obligations have no violation-triggered obligation concept at all | R15 (VIOLATED) |
| O-07 | (No FHIR obligation code exists for this) — aggregate status of a Task Group | An `any_discharged` / `all_discharged` **group satisfaction** condition over a `token_group` | Machine-checkable group roll-up — precisely the eRequesting Task Group "expected … however this is not enforced" gap | R09, group rules |

## 4. Reading the table: three honest observations

**O-01 through O-05 are genuine correspondences** — a FHIR obligation code
does exist, and it maps to *one point* in a token's lifecycle. These are the
"legible in FHIR's own vocabulary" rows: an R2 participant can look at
`SHALL:populate-if-known` on an Adverse Reaction element and see immediately
what the governance layer does with it.

**O-06 and O-07 have no FHIR obligation code at all** — and that is the
point, not a defect in the table. They are the rows where FHIR Obligations
structurally cannot reach (violation-derived obligations; verified group
roll-up), and where the ODP-EL layer is not a *mapping* of FHIR but a
*genuine extension beyond* it. These two rows are the strongest
contribution-to-R2 material: they name two things R2 will need and FHIR
Obligations cannot express.

**The `display` vs `handle`/`populate` split (O-02/O-03) matters
semantically:** display-type obligations map to *permits* (the actor may
surface the element), while handle/populate-type obligations map to
*burdens* (the actor must act). Collapsing these would misrepresent a
standing permission as a workflow obligation — the same permit/burden
distinction the toolchain already enforces elsewhere.

## 5. How to use this in an R2 / Sparked conversation

1. **Lead with O-01.** The supporting-info gating case (Adverse Reaction /
   Problem-Diagnosis Summary) is a named eRequesting out-of-scope item, it
   uses a FHIR obligation code the audience already knows, and the value ODP-EL
   adds (gate progression; compute the violation path) is immediately
   intuitive to a clinician or an implementer.
2. **Use O-05 to connect to claiming.** It ties the mapping directly to the
   DN_003 claiming work and the R2 transfer-of-fulfilment workstream.
3. **Close with O-06 and O-07** as the "here is what FHIR Obligations cannot
   express, and where a verification layer becomes necessary" — the
   DN_004 §3 "declare vs verify" argument, made concrete.
4. **Keep the §1 caveat visible throughout:** correspondence, not identity;
   complementary layers, not replacement.

## 6. Deferred / open

- Exact FHIR obligation *code system* URIs and the precise AU Core /
  eRequesting obligation bindings should be pinned to the specific published
  code values before this table goes into any external document — the codes
  above (`SHALL:populate-if-known`, `SHALL:handle`, `SHALL:display`) are the
  documented pattern but the exact AU-bound set should be verified against
  the current AU Core obligation value set at use time.
- O-05's mapping to the claim `evaluation` depends on DN_003's mechanism,
  implemented 2026-08-24 as AM-60–63 (`docs/el_grammar_amendments.md`).
- Whether O-07's group roll-up should be offered as a FHIR `invariant`
  (the FHIRPath-expressible slice, DN_004 §4.3) or kept entirely in the
  companion layer is an open engagement-tactics question, not resolved here.
