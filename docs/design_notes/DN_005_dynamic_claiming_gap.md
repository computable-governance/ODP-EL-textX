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
