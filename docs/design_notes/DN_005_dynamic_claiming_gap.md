# DN_005 — Dynamic Claiming: Closing the Static-Evaluation Gap Before Any FHIR Claim Bridge

*Design note — not implemented, no code changes proposed here. Surfaces a
real limitation found while live-testing AM-60–63 against the running API
(this session), and lays out options for resolving it. This is a
prerequisite for any future FHIR Task-event bridge (the "declarative/atomic
transfer path," DN_003 §5.4/§0) — not the bridge itself.*

---

## 1. The finding, precisely

AM-60–63's claim mechanism (`C1` in `el_kripke.py`, `7a-claim` in
`el_engine.py`) gates the `claimable → active` transition on finding a
matching entry in `accept_evaluations` — a set built once, per call, **from
`Evaluation` objects statically declared in the parsed spec**
(`spec.elements`). This was deliberate and correct for what AM-60–63 set
out to demonstrate: DN_003 §2 grounds acceptance-as-evaluation in ISO
15414 §6.6.7/§B.1.9.6, and the first scenario (`erequesting_claiming_scenario.el`)
correctly exercises this by declaring `providerAAcceptsReferral` up front
in the `.el` file.

**The gap:** a genuine live event — a real claim arriving through the API,
or eventually through a FHIR bridge — does not know in advance which
provider will claim or when. There is no way to author that `Evaluation`
into the spec ahead of time, because the spec is parsed once, at scenario
load, before any live event occurs. Confirmed directly this session: the
only way to make a live claim succeed today is if the spec *happened* to
already contain a matching accept `Evaluation` at parse time — which is
fine for a demonstration scenario, but does not generalise to a real
external event source.

**The correct precedent already exists in the codebase, and this
mechanism doesn't yet follow it.** `revoke_authorization()`/
`reinstate_authorization()` (AM-31, wired to live FHIR Consent events via
`handle_consent_event()`) are **direct, dynamically-callable `Runtime`
methods** — they don't require a pre-declared spec element describing the
revocation in advance; the event itself, arriving live, is what triggers
the transition. Claiming, as built, is architecturally closer to a
Commitment (a fact declared once, at spec-authoring time) than to a
Consent event (something that happens live and is only known at runtime).
That mismatch is the actual gap — not merely "no FHIR bridge exists yet,"
but "the claim mechanism's current shape wouldn't support a bridge even if
one were built."

## 2. Why this must be resolved before, not during, any FHIR bridge work

Building a `handle_task_event()`-style bridge (mirroring
`handle_consent_event()`) without first resolving this would mean either:
(a) discovering the gap mid-bridge-implementation and having to redesign
the claim mechanism anyway, under bridge-implementation pressure rather
than as a clean design decision, or (b) working around it badly — e.g. by
requiring every possible future claimant's `Evaluation` to be
speculatively pre-declared for every pool member at scenario-authoring
time, which does not scale and misrepresents "an evaluation that hasn't
happened yet" as "an evaluation that has."

## 3. Options for a dynamic claim mechanism

### Option A — Bare direct method, bypassing Evaluation entirely

`runtime.claim(token_name, actor_name) -> TransitionRecord` — checks the
token is `claimable` and held by `actor_name`, performs the
`claimable → active` transition and sibling-lapse walk directly, with no
Evaluation involved at all.

- **Pro:** simplest; directly mirrors `revoke_authorization()`'s shape.
- **Con:** discards the standards grounding DN_003 §2 carefully
  established — "claiming is an Evaluation, per §6.6.7/§B.1.9.6" — for the
  live path specifically. Would leave two claim mechanisms with different
  conceptual status (spec-declared claims are "evaluated," live claims are
  not), which is a real inconsistency, not merely a style difference.

### Option B — Dynamic Evaluation store, same gating logic

Add a runtime-side (not spec-side) live-evaluations store — e.g.
`runtime.record_evaluation(evaluator_name, token_name, result) ->
Evaluation` — that appends to a store `C1`/`7a-claim` check *in addition
to* `spec.elements`. The existing gating logic is otherwise unchanged;
only the source of truth for "does an accept Evaluation exist" widens to
include live-recorded ones.

- **Pro:** preserves the standards grounding — every claim, live or
  spec-declared, genuinely is an Evaluation. Minimal change to the
  transition logic itself (just widen the set-building step).
- **Con:** two Evaluation stores (static spec elements vs. a live
  runtime-side list) to reason about; provenance/audit story needs to
  distinguish them cleanly (which was this claim's Evaluation — authored
  or live-recorded?).

### Option C — `runtime.claim()` as sugar over a synthesized Evaluation (recommended)

`runtime.claim(token_name, actor_name)` as the public API — but internally,
it constructs and records a live `Evaluation`-equivalent fact (Option B's
store) with `result_code="accept"`, `evaluator=actor_name`,
`target_token=token_name`, then invokes the *same* underlying transition
logic C1/7a-claim already use. A `runtime.decline(token_name, actor_name)`
sibling records a `reject` fact, remaining a no-op per the existing design
(§5.3 of DN_003).

- **Pro:** gets Option A's simple call-site ergonomics (one direct method
  call, matching the `revoke_authorization()` precedent's usability) while
  keeping Option B's standards fidelity (every claim really is an
  Evaluation, auditable as one, provenance-traceable the same way
  `fhir_provenance` already stamps Consent-driven transitions). No
  duplicate gating logic — the direct method and the spec-declared path
  converge on one mechanism.
- **Con:** slightly more implementation work than Option A (needs the
  synthesis step + the live store), though not materially more than
  Option B alone.

**Recommendation: Option C.** It's the only option that doesn't force a
choice between "simple to call" and "standards-faithful" — it gets both,
at a small, justified implementation cost, and it keeps a single claim
mechanism rather than two philosophically different ones coexisting.

## 4. What this does NOT resolve (still separately deferred)

- The FHIR Task-event bridge itself (`handle_task_event()`, a new
  `POST /fhir/task-events` endpoint) — this note is a prerequisite for
  that work, not that work. Once a dynamic claim method exists (§3), the
  bridge becomes a mapping problem: translate a FHIR `Task` businessStatus
  transition into a `(token_name, actor_name)` pair and call
  `runtime.claim()`/`runtime.decline()` — a much smaller, better-scoped
  piece of work than attempting it against the current static-only
  mechanism.
- **Actor resolution is a real open question for that future bridge, not
  addressed here:** a live FHIR event names an `Organization` reference;
  the runtime's `actor_name` is an ODP-EL party name. Mapping between them
  (a stable, queryable correspondence — DN_003 never established this)
  needs its own small design pass when the bridge is actually built.
- DN_003 §5.4's declarative/atomic transfer path remains a distinct,
  larger piece of unrelated future work (no Evaluation involved at all,
  by design — see DN_003 §5.0's two-speech-act-shape distinction). This
  note's dynamic mechanism is for the *evaluative* path specifically; it
  does not bring the declarative/atomic path any closer to being built.

## 5. Suggested sequencing

1. This note (design review — no code yet).
2. If Option C is approved: implement `runtime.claim()`/`runtime.decline()`
   + the live-evaluation store, with new tests mirroring
   `test_erequesting_claiming_scenario.py`'s discipline (empirical, not
   asserted) — a self-contained, scoped piece of work, no FHIR involved
   yet.
3. Only then: scope the actual FHIR Task-event bridge as its own, later
   design note, addressing actor-resolution and the businessStatus-code
   mapping (candidate material: the O-05 row already sketched in
   `fhir_obligation_token_mapping.md`).

---

## Addendum (2026-08-24) — A second, prior gap confirmed empirically: `fhir_mapper.py` doesn't see claims at all

*Added after live-testing DN_004/DN_005 territory against real, public
AU eRequesting terminology — not assumed, run through the actual mapper.*

### What was tested

Confirmed via the IG's own public `ValueSet-au-erequesting-task-businessstatus`
(`terminology.hl7.org.au/CodeSystem/task-business-status`, genuinely public,
fetched directly from `build.fhir.org`) that AU eRequesting already defines
the exact claim/cancellation pattern this project has been reasoning about,
under real, citable public codes:
- `request-claimed` — "Task has been cancelled as the request has been
  claimed by another filler."
- `cancel-handled` — "Cancelled task has been handled by the filler."

None of the five officially published Task examples happen to demonstrate
these codes in context (checked directly — the published Task Group example
shows the ordinary happy path, `businessStatus: Service booked`). So a
synthetic-but-conformant pair of `Task` resources was constructed (real
public code system, real codes, real published example organisations as
anchors — clearly not an official IG example) and run through the actual
`FHIRConsentMapper.map_bundle()`.

### What it found

The mapper (R09, `_map_task`) produced **two entirely independent
`delegation` constructs** — one for the original filler's now-`cancelled`
Task, one for the alternate filler's new `requested` Task — with **no
relationship between them at all**. Nothing in the generated spec reflects
that the second superseded the first; `businessStatus` is not read by
`_map_task` anywhere (confirmed by inspection — only `Task.status` appears,
and only as a plain-text fragment in the generated description, never
acted on).

### Why this matters — a second, separate, and prior gap

This is **not** the same gap DN_005's main text covers. There are now two
distinct, stacked gaps between "a real FHIR claim event happens" and "the
governance layer correctly reflects it":

1. **Mapper-level (this addendum, new finding):** `fhir_mapper.py`'s R09
   task-mapping rule has no concept of `businessStatus`, no concept of
   claim/cancellation, and treats every `Task` as independent. Two Tasks
   that are, in reality, the same request's before/after claim state
   produce two unrelated `delegation` declarations.
2. **Runtime-level (DN_005's main finding, unchanged):** even given a
   correctly-linked pair of constructs, there is still no dynamic
   `runtime.claim()`-style mechanism (§3) to actually drive a live
   `claimable → active`/`lapsed` transition from an external event.

**Sequencing consequence:** gap 1 sits *before* gap 2, not after it. A
future FHIR Task-event bridge needs `_map_task` (or a dedicated
claim-aware mapping rule — call it R09a or similar, TBD at implementation)
to first recognise `businessStatus: request-claimed`/`cancel-handled` and
correctly link the two Task resources as one request's before/after state,
*before* the dynamic runtime mechanism in §3 has anything coherent to be
called with. Both are real, both are scoped-out here, but the ordering
matters for whoever picks this up.

### Test fixture preserved

The synthetic pair (`Task-original-filler-now-claimed.json`,
`Task-alternate-filler-claimed.json`) is saved separately as a small,
clearly-labeled-as-constructed fixture for whenever this gap is picked up
— see the companion file note. Not an official IG example; safe to treat
as a synthetic conformance test case only.

---

## Addendum (2026-09-12) — Mapper-level ($claim shape) closed; runtime-level (§3) still open; two new findings along the way

*Added after a session of fixture-building and empirical mapper fixes,
prompted by re-scoping gap 2 (the 2026-08-24 addendum's mapper-level
gap) against the real AU eRequesting `$claim` operation rather than
only the `businessStatus`-linking pattern originally assumed.*

### A third, distinct pattern confirmed: `$claim`, separate from `businessStatus`-linking

The 2026-08-24 addendum's synthetic fixture demonstrates one real
pattern: two independently-created Tasks linked only by
`businessStatus` codes (`request-claimed`/`cancel-handled`) — a
same-Task-lifecycle read. Real AU eRequesting also defines a second,
structurally different mechanism for *undirected* orders: a Task is
lodged with **no `owner` at all**; a filler later calls the `$claim`
operation (requisition identifier + org reference), which assigns
`Task.owner` and returns a new group Task. This is a create-and-link
operation, not a `businessStatus` transition on an existing pair.
Confirmed against the real AU eRequesting Task Group profile (two
published examples, `Task-taskgroup-pathology-1`/`-imaging-1`) and
against the live HAPI fixture `Task/209` (directed — owner
pre-assigned, so it cannot exercise this path). Both patterns are now
real, distinct, and separately fixture-backed:
`tests/fixtures/erequesting_claim_synthetic/` holds the original
`businessStatus`-linked pair, plus a new `Task-undirected-unclaimed.json`
for the `$claim`/no-owner case.

**Decision taken:** target the `$claim`-shape specifically for gap-2
mapper work, since it's what the spec actually mandates for undirected
orders; the `businessStatus`-linking pattern remains the right model
for a *directed* Task later reassigned/cancelled by some other
mechanism, and stays separately open (see below).

### Grounding confirmed directly in the IG's own guidance text (not just examples)

Everything above was inferred from real published examples. The
IG's own "Diagnostic Request Grouping" guidance
(general-guidance.html#diagnostic-request-grouping, AU eRequesting
v1.0.1) confirms it directly, and adds a consequential detail the
examples alone didn't establish: **a Task Group SHALL always be
created, including when there is only a single request for a test or
exam** — this isn't a multi-item-order edge case, it's present on
every real AU eRequesting order. That makes today's Task Group
exclusion fix (below) load-bearing for essentially all real bundles,
not an occasional correction.

The same guidance text also states, as explicit implementation rules
rather than inferred convention: fulfilment Tasks use `Task.focus` to
reference the diagnostic request being fulfilled, `Task.partOf` to
reference the Task Group, and `Task.meta.tag` of `"fulfilment-task"`
(vs. the group's own `"fulfilment-task-group"`) — directly confirming
R12's `focus` fix and the Task Group exclusion's profile/tag marker,
not merely consistent with the examples that prompted them.

**A fourth Task shape this session never touched:** the guidance also
describes an "AU eRequesting Task Communication Request" profile —
tracking fulfilment of a `CommunicationRequest` (patient instructions,
urgent-results routing, copy-to-GP), structurally parallel to the
diagnostic-request Task but with `focus` pointing at a
`CommunicationRequest`, not a `ServiceRequest`. R12's obligation
lookup would find nothing to trace to for this shape and fall back to
the generic string — untested, not confirmed harmless, just not yet
examined at all. Logged as an open item, not acted on.

**A discrepancy worth flagging, not resolving here:** this same IG
version's own Home page lists "Claiming of diagnostic requests by
fillers" under aspects explicitly **not** considered a priority for
Release 1's scope. That sits oddly next to this note's own premise
that `$claim` is a confirmed, spec-mandated mechanism (per the
original brief's terminology-server check). Worth resolving which is
accurate — a not-yet-prioritised R1 scope item, or a genuinely defined
operation elsewhere in the spec — before treating `$claim` as
implementation-ready for gap 3.

### Mapper-level gap-2 ($claim shape): now closed, via two prerequisite fixes neither anticipated by this note

Empirically confirmed (2026-09-12): once `$claim` assigns `owner` on
the previously-ownerless Task, the **existing** R09–R15 pathway in
`_map_task` already produces a correct `ELDelegation` — no new mapping
rule needed for the core "recognize a claimed Task" requirement. But
getting there required fixing two pre-existing, unrelated bugs this
note didn't anticipate, both confirmed against real IG data rather
than assumed:

- **R10** resolved `Task.requester` with the bare `_ref_id()` helper —
  no `PractitionerRole` handling, unlike R06's equivalent fix
  (2026-08-30) for `ServiceRequest.requester`. Produced a dangling
  reference and a validation failure for any Task whose requester is a
  `PractitionerRole` — which is every real AU eRequesting Task,
  including `Task/209` itself. Fixed by routing R10 through the same
  `_resolve_commitment_accountable_party()` resolver R06 already uses.
- **R12** traced `Task.basedOn` to find the obligation-bearing
  ServiceRequest — but per FHIR's own Task resource definition,
  `basedOn` is "a higher-level authorization that triggered the
  creation of the task," distinct from "the request resource the task
  is seeking to fulfill," which is referenced by `focus`. No real AU
  eRequesting Task example populates `basedOn`; all populate `focus`.
  R12 had, in effect, never resolved a real obligation against any
  genuinely IG-shaped Task. Fixed by switching R12 to read `focus`,
  and correcting the one hand-authored bundle (`ai_diagnostic_bundle.json`)
  that happened to use `basedOn`, matching real convention.

A separately-triggered `[:200]` description-truncation bug in
`_render_delegation` was also fixed in the same pass (harmless before
R10's fix started producing longer, warning-bearing descriptions;
silently corrupted checked-in output otherwise).

### New finding, not anticipated by this note at all: Task Group resources duplicate their child fulfilment Task

The AU eRequesting Task Group profile (real published examples) was
found to populate `requester`/`owner` **identically** to its child
fulfilment Task — same PractitionerRole, same Organization, restated
at container level, not a different party in a delegation chain.
Unmapped, this would have produced a spurious duplicate delegation for
the group Task itself once R10/R12 were fixed. `_map_task` now
excludes Task Group resources by `meta.profile` marker before they
ever reach R09–R15 — see `docs/CONCEPTS_INDEX.md`'s corresponding
entry (now resolved) for the full empirical trace.

### What remains genuinely open

- **§3's runtime-level mechanism (Option C: `runtime.claim()`/
  `runtime.decline()`) — unchanged, not started.** Everything above
  closes the *mapper*-level half of gap 2; the *runtime* half (§1–§3 of
  this note's main text) is exactly as scoped before today's session.
- **The `businessStatus`-linking pattern (2026-08-24 addendum's
  original gap-1 finding)** — still entirely unaddressed. `$claim` was
  today's target because it's the mandated mechanism for undirected
  orders, but a directed Task later reassigned via `businessStatus`
  codes is a real, separate case with its own fixture, still unmapped.
- **Actor resolution** (FHIR `Organization` reference ↔ ODP-EL party
  name) — as this note already flagged in §4, still open, and now more
  concretely relevant: `$claim`'s `owner` assignment is exactly the
  kind of live event that will need this resolution once §3 exists.
- **Task Communication Request mapping** — an entirely separate,
  untested Task shape (see above); not yet run through the mapper at
  all.
- **The Release-1 scope discrepancy on `$claim`** (see above) — needs
  resolving before gap 3 is built on the assumption that `$claim` is a
  confirmed, in-scope mechanism for this IG version.

### Sequencing consequence

§5's original sequencing (design → implement §3 → then the FHIR
bridge) still holds, with mapper-level readiness now further along
than assumed: the mapper can already produce a correct delegation from
a `$claim`-completed Task. What's missing to actually *drive* a live
claim end-to-end is §3 itself — `runtime.claim()`/`runtime.decline()`
— which remains the next real piece of work.

---

