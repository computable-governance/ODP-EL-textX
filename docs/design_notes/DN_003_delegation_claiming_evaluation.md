# DN_003 — Delegation Claiming: Accept/Reject as Evaluation-Gated Pool Membership

*Design note. **Implemented 2026-08-24** as AM-60 (grammar/parser/domain:
structured `Evaluation`, `claimable` `TokenState`), AM-61 (Layer 4
`el_kripke.py`: `CLAIMABLE`/`LAPSED` states, C1 claim transition), AM-62
(Layer 3 `el_engine.py`: `claimable → active` activation, sibling lapse),
and AM-63 (`erequesting_claiming_scenario.el`, the first named demonstration
scenario). See `docs/el_grammar_amendments.md` for the four log entries.
The evaluative pool-accept mechanism designed below (§5, the fork
resolved in favour of `Evaluation`-gated claiming) is what was built; the
declarative/atomic transfer alternative (§5.4) remains unimplemented and
deferred — see `docs/CONCEPTS_INDEX.md`'s "Delegation claiming (AM-60–63)"
entry.*

---

## 0. Status and scope

**Problem in one line:** the toolchain models `Delegation` as a unilateral,
always-successful speech act. A delegate cannot decline. There is no
representation of a delegated obligation being *claimed* (accepted) or
*refused* before it becomes the delegate's active burden.

**Where this came from:** the FHIR / Governed Autonomy analysis (§2.2)
identified this against AU eRequesting v1.0.0, which names *claiming of
diagnostic requests by fillers* as explicitly out of scope for Release 1,
and whose `Task.status` carries an explicit `rejected` state that the
DSL-EL `Delegation` and `TokenInstance.state` enum have no equivalent for.

**What this note decides:** the standards grounding, the general model
(pool, with bounce-back as a degenerate instance), and the mechanism
(acceptance as an `Evaluation`). It deliberately does **not** resolve the
escalation / re-entry / deadline edge cases — those are named as deferred
in §7 rather than left silently open.

**What this note did NOT do (at the time it was written):** propose code.
Implementation followed as a later, separately reviewed session — see
the status line above.

---

## 1. Is there a native FHIR answer? (No — and the boundary is more textured than first assumed)

Verbatim-checked against the published IG (`hl7.org.au/fhir/ereq/1.0.0-ballot`,
Home page and Workflow Guidance page), not against our own analysis's earlier
paraphrase of it. Two corrections to the original framing follow directly
from that check.

**"Claiming" is explicitly out of scope, and it is genuinely undefined —
not implicitly covered by `Task.status`.** The Home page's own scope
statement lists <cite index="17-1">"Claiming of diagnostic requests by
fillers"</cite> among the technical aspects "not considered priority for the
scope of Release 1," alongside authentication/authorisation/auditing and
provider discovery. This is a clean, named gap, not something we are
reading between the lines to find.

**But the word "claim" is *also* used informally inside the Task state
machine, for a *different* transition than acceptance** — and this changes
the design. The `received` state is glossed as: <cite index="31-1">"Indicates
that the task has been acknowledged and claimed by a filler. Some workflows
may not distinguish between 'received' and 'accepted'. In such cases,
implementations may transition directly from 'requested' to 'accepted'."</cite>
So the IG's own informal usage places "claim" *before* acceptance
(`requested → received → accepted`), with acceptance/rejection as a
separate, later act — while explicitly permitting the two to collapse into
one transition. Either reading is IG-conformant. **This means the acceptance
`Evaluation` (§2, §5.1) may need to gate either a single combined
claim-and-accept transition, or two separate ones** — the design should not
assume the collapsed form is the only shape.

**And there is a third, distinct outcome the IG defines that our original
framing conflated with rejection: losing a claim to a competing filler.**
The Task Business Status value set includes a code named `claimed`, glossed
as <cite index="31-1">"The service request has been claimed by an
alternative filler,"</cite> mapped not to `rejected` but to
`Task.status = cancelled`. The state-transition table independently confirms
the same pattern from the losing filler's side: a task transitions to
`cancelled` when <cite index="31-1">"the task is cancelled because it has
been claimed by an alternative filler."</cite> This is **structurally
distinct** from `rejected`, which the IG defines as <cite index="31-1">"the
filler has declined to perform the task before beginning any work."</cite>
`rejected` = a genuine decline by the filler holding the task. `cancelled`
(via `claimed`-by-alternative) = the filler's claim opportunity was
overtaken by a peer, with no decision made by that filler at all.

**Consequence for §5:** the DSL-EL side needs (at minimum) two distinct
outcomes for a non-accepting pool member, not one — a genuine decline, and
a claim lost to a peer — matching the IG's own `rejected`/`cancelled`
split. This independently supports preferring a new, distinct interim/lapsed
state (§5.2 Option B) over collapsing everything into a
`pending`/`rejected` binary: the pool's "your claim lapsed because a peer
claimed it first" branch is closer in kind to the sibling-supersession
pattern (§3, §5.3) than to a rejection.

**The underlying division of labour is unchanged, only more precise now:**

> FHIR owns the **state fields** (`Task.status = rejected` /
> `cancelled`+`claimed`, both real IG-defined outcomes). Governed Autonomy
> owns **who may set them, and what obligation-state change and
> accountability consequence follows** — a question the IG does not
> address for any of these transitions, per its own scope statement.

No rebuild of FHIR machinery. This is consistent with the mediator
pattern's settled shape (non-invasive, external; see analysis §1).

**Also confirmed directly from the IG, strengthening §4's leverage point
verbatim:** the Task Group relationship section states plainly:
<cite index="31-1">"It is expected that the status of the task group will
reflect the most appropriate status among the individual ... however this
is not enforced."</cite> This is the exact aggregation gap `any_discharged`/
SUPERSEDED already answers — now grounded in the IG's own wording rather
than a paraphrase of it.

---

## 2. Standards grounding — the acceptance primitive already exists in ISO 15414

This is the key finding, and it is stronger than "the toolchain has a gap."
The **standard itself already contains the acceptance mechanism**, under a
speech act the toolchain currently leaves inert.

### 2.1 Delegation is one-sided *by definition*

- **§6.6.6 delegation:** "The action that assigns something, such as
  authorization, responsibility or provision of a service to another
  object." Defined as the *assignor's* action. NOTE: "A delegation, once
  made, may later be withdrawn."

The standard's `delegation` is genuinely unilateral. The toolchain is
**faithful** here — the fix is *not* to make `delegation` two-sided. The
delegate's response is a *separate* act.

### 2.2 That separate act is `evaluation`

- **§6.6.7 evaluation:** "An action that assesses the value of something."
  NOTE 2: "Value can be considered in terms of usefulness, importance,
  preference, **acceptability**, etc.; the evaluated target may be, for
  example, a credit rating, a system state, a potential behaviour, etc."
  (emphasis on *acceptability* is the standard's own list.)

- **§B.1.9.6 (worked example):** bids are transmitted to suppliers, and
  "the e-com purchasing agent determines which bid or bids to **accept**.
  ... This assignment of status is an **evaluation** by e-system of the
  bids."

The standard's own answer to "how is something offered accepted or
declined?" is: **the recipient performs an `evaluation` whose result is
acceptability.** Accepting a delegated burden is structurally identical to
accepting a bid — an evaluation of a delegated thing, with an
accept/reject outcome.

### 2.3 The token lifecycle already has the slot for it

The delegated burden should sit in a **masked / not-yet-owned** state until
the acceptance evaluation resolves:

- ISO 15414 Annex A (Figure A.6): `pending → active → discharged /
  violated / expired`. `pending` is the masked state (constraint not yet
  applied to the holder).
- The Sepanosian summary of the standard notes a delegated obligation may
  sit `pending` "while an agent attempts to discharge it" — precisely the
  window an acceptance evaluation gates.

So the transition the acceptance evaluation gates is **`pending → active`
on accept**, and something-other-than-active on reject (see §5). The
delegate does not hold an *active* burden until they have accepted it.

### 2.4 Net grounding claim

Claiming = a delegate's **`evaluation`** (§6.6.7, acceptability, per
B.1.9.6) of a **`pending`** delegated burden, resolving it to `active`
(accept) or returning it to the pool (reject). Every piece is a named
standard construct. Nothing is invented.

---

## 3. Ground-truth of the existing mechanism (verified against repo, not memory)

Checked against `computable-governance/ODP-EL-textX` @ `ba64f73`
(2026-08-24 clone), not against prior documentation:

**`Evaluation` is presently inert.** It exists in `grammar/v2` (§6.6.7
block: `by` / `of_target` / `result`, all free-text `STRING`) and in
`el_domain.py` (object model only). It has **zero** handlers in
`el_engine.py` or `el_reasoner.py` — confirmed by grep. Its current shape
is built for credit-rating-style value assessment: no structured link to a
burden, no accept/reject outcome, no state-change effect. So this work is
**giving a decorative construct its first runtime semantics**, not
refining a working one — cleaner (no behaviour to regress), but it does
require *extending* the `Evaluation` grammar, not just wiring it up.

**The pool mechanism (`any_discharged` / `SUPERSEDED`) is real and current:**
- `el_kripke.py` P6b (lines ~1939–1957): when a member of an
  `any_discharged` group discharges, `PENDING`/`WAITING` siblings become
  `SUPERSEDED`. Verified in source.
- `el_engine.py` (AM-57): live parity for `active`-state siblings only;
  `pending` (masked) siblings deliberately untouched — logged open gap in
  `CONCEPTS_INDEX.md`.
- `specialist_pool_scenario.el` (AM-58) exercises it end-to-end.

**State vocabularies (must be reused, not reinvented):**
- Engine `TokenInstance.state`: `active | pending | discharged | violated |
  superseded`.
- Kripke `ObligationState`: `PENDING | DISCHARGED | VIOLATED | EXPIRED |
  SUPERSEDED | WAITING`.

Note the asymmetry: the engine has no `WAITING`/`EXPIRED`; the Kripke layer
has no distinct `active`. Any new state introduced by this feature must be
declared in **both** layers or explicitly scoped to one (§5.3).

**The claiming scenario is the mirror image of an existing committed file.**
`specialist_pool_scenario.el` is a *discharge*-side pool: two equivalent
peers, `any_discharged(consultResponseGroup)`, both burdens start `active`,
either *discharges*. Claiming is the *accept*-side of the identical
structure: same two peers, same group, but the burden starts **unclaimed**
and the governed act is *taking it up*. This is a sibling of a tested file,
not a greenfield scenario — and it reuses the exact collective-obligation
backbone (§4).

---

## 4. The general model: pool, with bounce-back as the size-one instance

**Decision (per review): the pool is the general case, and it subsumes
bounce-back.**

- "Bounce back to the delegator" is a pool of size one — a decline returns
  the burden to a group whose only eligible re-taker is the original
  delegator.
- "Re-enter a filler pool of N" is the same mechanism, eligible set
  widened.
- Build the pool properly and bounce-back is a degenerate configuration,
  obtained for free. Building bounce-back first would force a rebuild when
  the pool arrives.

**Why the pool is the *right* general frame, not just the bigger one — it
is the structural mirror of `any_discharged`:**

| | `any_discharged` (discharge side, built) | Pool claiming (accept side, this note) |
|---|---|---|
| Trigger | one peer of N **discharges** | one peer of N **accepts** |
| Effect on siblings | others' burdens **SUPERSEDED** (relieved) | others' **opportunity to claim lapses** |
| Interim state | — | burden **collectively held, individually unclaimed** |

The "collectively held, individually unclaimed" interim state is exactly
the aggregation problem AU eRequesting's `Task Group` punts on ("status
... will reflect the most appropriate ... however this is not enforced")
and exactly what AM-57/58 already formalises on the discharge side.
Modelling claiming as a pool means **one collective-obligation mechanism
governs both who takes a burden up and who is relieved of it** — a single
spine, not two unrelated features. That is the strategically valuable
outcome and the reason to prefer the pool over bounce-back-first.

---

## 5. Mechanism design (for review — two forks resolved, edges deferred)

### 5.0 Two speech-act shapes for claiming — not one

*Provenance note: this subsection and §5.0a describe general patterns
Zoran relayed from R2-track material of uncertain publication status —
not the published R1 IG (which §1's citations draw from and which remain
fine to cite). Per standing practice for non-public/collaborator-supplied
material (cf. the XMPro convention), this is described generically, at the
pattern level, with no operation names, parameter names, or verbatim text
reproduced, and no claim that it is publicly citable standards text.*

Session discussion surfaced a claim-transfer pattern that changes the
shape of this section. The pattern, described generically: a claim/transfer
operation exists that is **not** an acceptability judgment. Given an
identifier for the request and a reference to the claiming organisation,
the operation either succeeds — atomically creating a new fulfilment
record for the claiming party and cancelling the original, with the
cancellation later separately acknowledged by the original holder so it
isn't rediscovered as outstanding (a two-phase lapse, not one transition)
— or it returns a precise structural reason it did not (bad identifier,
unresolvable organisation, a conflicting concurrent claim, or the request
already being held elsewhere/already held by the requesting party, the
latter treated as a harmless idempotent no-op rather than an error). The
underlying request-level record is left unchanged; only the
fulfilment/delegation layer moves.

**Neither this pattern nor the related variant discussed contains a
judgment step.** There is no filler weighing whether to accept;
the outcome is structural, not evaluative. This is closer to
**Declaration (§6.6.5)** — a state of affairs established by virtue of the
act itself, under authorisation, triggered by an external event — than to
**Evaluation (§6.6.7)**. An organisation-reference precondition of this
kind is an authorisation/domain-scope gate, not an acceptability
assessment.

**Consequence: this note's design should support two distinct speech-act
shapes, not pick one.**

1. **Evaluative acceptance** (§5.1 below, unchanged) — a delegate genuinely
   *judges* whether to take up an offered burden. This remains the right
   model wherever a real decision is being made: an AI agent or human
   deciding whether to accept a delegated obligation, the
   `specialist_pool_scenario.el`-style peer-response case, or any future
   scenario where "should I take this on" is a live question. Grounded in
   §6.6.7/§B.1.9.6 as before.
2. **Declarative/atomic transfer** (the pattern above, and the confirmed
   privacy point below) — an authorised, structurally-gated re-assignment
   with no evaluative content, triggered by an external event, resolved
   atomically with a precise outcome. This is a **`Declaration`**, not an
   `Evaluation` — and appears to be where real deployments' transfer
   mechanism actually lives.

Both belong in the toolchain eventually; they answer different questions
("should this delegate accept" vs. "was this authorised re-assignment
valid, and what accountability resulted"). The scenario in §6 should be
built to exercise **both**, not assume the evaluative form covers the real
mechanism — it doesn't.

### 5.0a A confirmed design tension: deliberate mutual anonymity

Per the same session discussion (see provenance note above — described
generically, not quoted): the claiming party and the original holder are
each deliberately prevented from learning the other's identity through
this operation.

Confirmed directly (not inferred, though not independently verified
against a public source): this is a deliberate privacy/commercial design
decision — competing diagnostic providers are not meant to see each
other's involvement in a single patient's care episode. This is a genuine
tension with this toolchain's central accountability-chain claim ("who is
ultimately accountable regardless of delegation depth"), and it should be
named plainly rather than smoothed over:

- **At the FHIR/inter-organisational layer, the accountability chain is
  deliberately severed at the point of transfer, by design, for competitive
  reasons.** No amount of FHIR extension work would remove this — the two
  organisations do not want to disclose this to each other, and a
  standards body cannot compel that disclosure without addressing the
  underlying competitive concern, which is out of scope for a data
  standard.
- **This does not mean accountability is lost — it means it is held
  somewhere the two FHIR endpoints cannot see.** A Governed Autonomy
  mediator sitting above both organisations' FHIR servers can hold the
  full accountability chain internally (exactly what a `WorldState`/chain

  is for) — "an authorised transfer occurred, from party A to party B, at
  time T, under rule R" — without either FHIR-facing party ever seeing the
  other's identity. The governance layer's knowledge and the FHIR-level
  exchange's disclosure are not in conflict; they are answering different
  questions for different audiences (a regulator or auditor vs. two
  competing operational systems).
- **This reframes what "claiming" governance is for, in the real
  deployment.** It is not to help two fillers negotiate a handoff (FHIR's
  atomic operation already does this correctly and efficiently). It is to
  give a **third party who legitimately needs the fuller picture** — a
  regulator, an auditor, the patient's own governance-aware advocate, or a
  neutral cross-vendor governance layer — an accountability record neither
  competing FHIR party is willing or able to hold. Worth carrying into the
  commercial framing (§9 of the analysis document) as a distinct value
  proposition, separate from the pool-claiming/evaluation story: **a
  privacy-preserving accountability ledger for a relationship the
  participants have deliberately kept opaque to each other.**

### 5.1 Acceptance as an extended `Evaluation`

Resolved (per review): **evaluation-based**, not a new bare `rejected`
state as the primary mechanism. Grounding is §2. Proposed grammar
extension (illustrative — exact syntax to be settled at implementation):

```
evaluation specialistAClaimsConsult {
    by:         SpecialistOnCallA
    of_target:  specialistAResponseBurden   // now a [DeonticToken] ref, not free-text
    result:     accept                        // new: AcceptabilityResult = accept | reject
    // description optional as today

}
```

Two grammar changes to `Evaluation`:
1. `of_target` gains the ability to reference a `[DeonticToken]` (keep
   free-text `STRING` form for the existing credit-rating use — alternation,
   longer/structured alternative first per the maintainer ordering rule in
   DSL_DESIGN_NOTES §2.7).
2. A new optional `result` value space `AcceptabilityResult : 'accept' |
   'reject'` (distinct from the existing free-text `result`, or a
   structured refinement of it — decide at implementation; do not overload
   silently).

Engine semantics (Layer 3, `el_engine.py`), new — Evaluation is currently
inert:
- On `result: accept` — the target burden transitions `pending → active`
  for the accepting delegate.
- On `result: reject` — the target burden is **not** activated for that
  delegate; pool re-offer applies (§5.2).

### 5.2 The interim "claimable" state — the one genuinely new state

A burden that has been delegated to a pool but not yet claimed is neither
`active` (nobody holds it as a live obligation) nor `pending` in the
existing masked-by-a-trigger sense. Two options:

- **Option A (reuse `pending`):** treat the unclaimed pool burden as
  `pending`, relying on "masked constraint, not yet applied to holder."
  Cheapest; risks overloading `pending`, which already has the
  triggered-by masking meaning (and AM-57's masked-sibling gap already
  lives here).
- **Option B (new `claimable` / `offered` state):** introduce a distinct
  state for "offered to a pool, awaiting an acceptance evaluation."
  Cleaner semantics, honest about the mirror-of-SUPERSEDED structure, but
  must be declared in **both** the engine enum and the Kripke
  `ObligationState` (§3 asymmetry warning), with T1/T2 verifier rules
  taught to treat it as neither dischargeable nor violable until claimed.

**Recommendation: Option B**, because the whole point of the pool frame is
that the interim collective-holding state is real and worth verifying — and
because reusing `pending` would entangle this with the known masked-sibling
gap. But Option B is the larger build; if the first implementation pass
wants to prove the accept/reject evaluation in isolation, Option A with an
explicit "collapses two meanings of `pending`, temporary" note is an
acceptable stepping stone. **Flag for decision at implementation.**

**Resolved 2026-08-24 (AM-60–62): Option B was implemented**, as `claimable`
(authorable `TokenState`) plus `ObligationState.CLAIMABLE`/`LAPSED` in the
Kripke layer — kept entirely separate from `pending`, exactly as
recommended. One correction to this section's own framing, surfaced
empirically during AM-62's ground-truth check (not assumed): the phrase
above, "AM-57's masked-sibling gap already lives here," undersold the
actual gap. The pre-AM-62 live engine had no `pending`/masked `→ active`
activation step **at all** — not merely an absent sibling-supersession
step layered on top of an otherwise-working activation path. Acting on a
masked burden was a silent, effect-free no-op (`outcome: "ok"`,
`effects: ()`), confirmed directly against an early draft of
`erequesting_claiming_scenario.el` before AM-62 landed. Separately: the
Kripke/verifier layer never had this gap at all — `el_kripke.py`'s
initial-world construction ignores the DSL's declared `state:` field and
starts every non-`triggered_by` obligation `PENDING`, so P6b already
covered PENDING/WAITING siblings symmetrically pre-AM-61. See
`docs/CONCEPTS_INDEX.md`'s "Delegation claiming (AM-60–63)" entry for the
full record.

### 5.3 Reject → pool re-offer, reusing the P6b sibling machinery

On accept, the *claiming* peer's burden goes `active`; the sibling
claim-opportunities should lapse — structurally the same sibling walk as
P6b, but marking siblings (say) `withdrawn`/`expired` rather than
`SUPERSEDED` (SUPERSEDED means "purpose fulfilled by a peer's *discharge*";
here the purpose is not yet fulfilled, only *claimed*, so a distinct label
is semantically honest). The `_build_group_index` /
`_build_any_discharged_groups` helpers (already duplicated across
`el_kripke.py` and `el_engine.py` per Layer 3/4 independence) are the reuse
point.

**Two distinct non-accepting outcomes, per §1's IG grounding — not one:**
- **Reject (`rejected`-equivalent):** the delegate holding the offer
  actively declines via an `evaluation` with `result: reject`. A genuine
  decision by that delegate. The burden remains offered to the residual
  pool.
- **Lapsed (`cancelled`-via-claimed-by-alternative-equivalent):** a delegate
  *takes no action* and a peer accepts first. No decision was made by the
  losing delegate — their claim opportunity is withdrawn out from under
  them, exactly the P6b sibling-lapse walk described above. This is *not*
  a rejection and should not share its label or its engine code path with
  one; conflating them would misrepresent an inactive delegate as having
  actively declined.

If the pool empties (all reject; none lapse into acceptance), escalation
applies — see §7, deferred.

### 5.4 The declarative/atomic path's consequences for the engine

*Provenance note: as with §5.0/§5.0a, this describes a general pattern
Zoran relayed, not published standards text — no specific field or code
names from that material are reproduced.*

Distinct from §5.1–5.3's evaluative flow. If a future session builds this
second speech-act shape (§5.0), the following design implications follow
from the general pattern discussed, not from any citable specification:

- **Two-phase lapse, not one transition.** The losing side's task is first
  marked lapsed, then separately *acknowledged* by the original holder to
  stop it being rediscovered as outstanding. This is a handshake — mark-
  lapsed → acknowledge-lapsed — not a single state flip. Whatever engine
  representation is chosen for §5.2/§5.3's "lapsed" state, it should
  support this two-step form for the declarative path (the evaluative
  path's simple sibling-walk lapse in §5.3 may not need it).
- **Idempotent retry is a first-class outcome, not an error.** A claimer
  who already holds the burden gets "no action needed, you already hold
  it," not a failure. Any engine/API surface for the declarative path
  should return this as a distinct, non-error result, not collapse it into
  either "accepted" or "rejected."
- **Concurrency guard needed.** A transfer attempt racing another attempt
  on the same request is a real case this kind of atomic operation
  typically defends against explicitly. Any engine implementation of this
  path needs its own concurrency story; this is not covered by the
  evaluative pool's sibling-lapse walk, which assumes serial resolution.
- **Infrastructure errors are not deontic and should not be modelled as
  token states.** Failures such as a bad identifier or an unresolvable
  organisation reference are request-level errors, not obligation-state
  outcomes — exclude them from the token/obligation model entirely,
  surface them as ordinary API errors.
- **The underlying request record stays untouched by a transfer** — only
  the fulfilment/delegation layer moves. This confirms
  the existing Layer 1/Layer 3 boundary (§1) rather than requiring a new
  one: a transfer is a delegation-layer event, never a commitment-layer
  one.

---

## 6. The scenario to build first (before any semantics)

Per process discipline (worked example before touching semantics), the
first artefact is a scenario, not code.

**Proposed: `scenarios/erequesting_claiming/erequesting_claiming_scenario.el`** —
a Filler claiming a delegated diagnostic referral, modelled on
`specialist_pool_scenario.el` but accept-side:

- Two equivalent fillers (e.g. two radiology providers) in a pool.
- A referral burden delegated to the pool (interim claimable state, §5.2).
- Filler A performs an acceptance `evaluation` → burden `active` for A;
  B's claim-opportunity lapses (§5.3).
- **The interesting branch:** Filler A *rejects* → burden stays offered →
  Filler B accepts. This is where the accountability chain visibly earns
  its keep over a bare `Task.status = rejected`: the burden's location and
  the accountable party are always answerable.

Standards-anchored (named eRequesting out-of-scope item), not synthetic;
sets up the two-sided handover handshake the broader care-handover thread
depends on.

**Scope note (per §5.0):** this first scenario exercises the *evaluative*
shape only — a delegate genuinely judging whether to accept. It does
**not** attempt to model the declarative/atomic transfer operations found
in R2 material (§5.0, §5.0a, §5.4); those involve no judgment and are
architecturally closer to `Declaration` than `Evaluation`. A second,
later scenario is the right place to exercise that path once it's
prioritised — building both into one scenario would blur two genuinely
different mechanisms together.

**Sequencing:** (1) write scenario; (2) confirm it parses/validates and
articulate the Layer 4 questions it *should* answer (EF(some filler
accepts)? does A's accept lapse B's opportunity?) — expected to fail /
be unexpressible today, documenting the gap concretely; (3) only then
design the grammar + engine changes against that failing scenario.

---

## 7. Deliberately deferred (named, not silently open)

Per the standing discipline of naming gaps rather than leaving them
implicit:

- **Claim deadline / escalation:** is there a time bound on claiming before
  the unclaimed burden escalates (to the delegator, or to a
  `ViolationResponse`)? The `ViolationResponse` construct (§6.3.8/§7.8.6
  NOTE 2) is the natural target but is not wired to the claimable state.
- **Re-entry after decline:** may a filler who declined re-enter the pool
  later? Assume **no** for the first build; revisit.
- **Pool membership source:** static enumerated members vs role-derived
  (community role → eligible pool). The `specialist_pool` scenario uses
  fixed membership ("both on-call specialists are fixed for the duration");
  role-derived membership is a later generalisation.
- **Option A vs B for the interim state (§5.2)** — decide at implementation.
- **Kripke-layer verification of the claimable state** — if Option B,
  T1/T2 must be taught the new state; scope of that change unestimated
  here.
- **Free-rider parallel:** the memory-noted `any_discharged` free-rider
  risk for agentic AI peers has an accept-side analogue — a
  reward-maximising agent could rationally *decline* to claim, waiting for
  a peer to take the burden. Worth a sentence in the eventual paper; not a
  design blocker.

---

## 8. Standards citations used in this note (for verbatim re-check before implementation)

- §6.6.6 delegation (unilateral assignor action; withdrawable)
- §6.6.7 evaluation (assess value; NOTE 2 *acceptability*)
- §B.1.9.6 (evaluation worked example: accepting bids)
- Annex A Fig. A.6 (`pending → active → discharged/violated/expired`)
- §6.3.8 / §7.8.6 NOTE 2 (ViolationResponse — for deferred escalation)

Per standing rule: verbatim-quote-verify each of these against
`BS_ISO_IEC_15414_2015.pdf` at implementation time before any "this
mirrors the standard" claim goes into code comments or the paper.
