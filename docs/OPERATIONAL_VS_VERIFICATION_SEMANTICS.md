# Operational vs. Verification Semantics: Distinction and Common Ground

**Status:** design note, not yet acted on. Captures a distinction surfaced
2026-07-15 while scoping AM-39 (Encounter.status-driven token activation).
Candidate input for a future arXiv revision and for a future refactoring
pass unifying `el_engine.py` and `el_kripke.py`.

## The distinction

`el_engine.py` and `el_kripke.py` are not two implementations of the same
thing that happened to diverge — they are two different, both legitimate,
kinds of semantics for the same DSL-EL specification language, corresponding
to a standard split in formal verification:

- **`el_engine.py` — operational semantics.** Small-step transitions over a
  single concrete `WorldState`: given one real actor performing one real
  action (or, since AM-39, one externally-fired event), what is the next
  state? This is what actually runs — the simulator, the board UI, the
  live demo, and now the FHIR event bridge (`Runtime.fire_event()`).

- **`el_kripke.py` — Kripke-structure / model-checking semantics.** Builds
  the entire reachable state space as a graph via BFS and answers modal
  questions over all of it: AF (holds on every path), EF (holds on some
  path), AG (holds always). This is the ISO/IEC 15414 Annex C
  implementation the paper claims as a first — the specification-time
  proof mode.

Every serious verification framework has this same shape (a reference/
operational semantics people actually run, and a separate verification
semantics used to prove properties about all possible runs). The pairing
itself is expected and correct. **The distinction is not the problem.**

## The common semantics underneath

Both layers interpret the same abstract object: the ISO/IEC 15414 §7.8.7 /
Annex A deontic token lifecycle (`pending → active → discharged / violated
/ expired`), driven by the same grammar constructs —
`DeonticToken`, `EventDecl`, `triggered_by`, `discharged_by` (AM-22). The
grammar is the shared specification both semantics are interpretations
*of*. Concretely:

| Grammar construct | Operational reading (`el_engine.py`) | Verification reading (`el_kripke.py`) |
|---|---|---|
| `DeonticToken.state` | `TokenInstance.state` — plain string, mutated in place via `_transition()` | `ObligationState` — typed enum, computed per hypothetical world |
| `triggered_by` | Checked by `_activate_triggered_tokens()`, called from `advance()` Step 7c (action-driven) and `Runtime.fire_event()` (direct-call, AM-39) | Read into `ObligationDescriptor.triggered_by`; drives initial `WAITING` state in `build_kripke_from_runtime()` / the pure spec-only builder |
| `discharged_by` / `emits` | `event_discharged` set (Step 3 of `advance()`) | `ObligationDescriptor.fires_event`; drives the P6a cascade (`WAITING → PENDING`) |

## The open problem: correspondence

For any pair of an operational semantics and a model-checking semantics
over the same language, the property that actually matters is
**correspondence (soundness)**: does every trace the operational semantics
can produce correspond to a path the model-checking structure actually
contains? If not, the model checker can "prove" a guarantee about paths
that don't reflect what the live system can really do — or fail to
represent a real path at all.

This correspondence is **currently neither established nor implemented
consistently**:

1. **Two independent state vocabularies**, bridged only by a hand-written
   ternary in `build_kripke_from_runtime()` (`TokenInstance.state` →
   `ObligationState`), rather than one canonical representation both sides
   share.
2. **Two independently-written event-matching implementations** —
   `_activate_triggered_tokens()` (engine) and the P6a cascade (Kripke) —
   built 8 days apart (commits `18b243dd`, 2026-06-05 and `894afdbd`,
   2026-06-13), never cross-referenced in `docs/el_grammar_amendments.md`.
3. **A suspected gap, not yet confirmed**: `build_kripke_from_runtime()`'s
   ternary has no visible `WAITING` branch — if confirmed, a
   `pending → active` transition produced by `Runtime.fire_event()` (AM-39)
   would be invisible to that proof mode's output. This needs a targeted
   check before `Runtime.fire_event()` is treated as any kind of bridge
   between the two layers — which, currently, it is not; it only ever
   touches `el_engine.py`.

## What a shared design would and wouldn't merge

The operational/model-checking split itself should **not** be merged —
collapsing "what happened" into "what could happen" would blur the
compelled-vs-detectable distinction that is the paper's central finding.

What could be factored out, without touching that split:

1. **One canonical state vocabulary**, used by both layers, replacing the
   current two independent representations bridged by a hand-maintained
   ternary — removing the specific seam where the suspected `WAITING` gap
   lives.
2. **One event-matching function** (does event `X` activate token `Y`?),
   called by both the operational stepper and the Kripke BFS step — so the
   two layers cannot disagree about which tokens relate to which events;
   only *how* each layer processes that shared fact (commit one transition
   vs. explore all reachable ones) would differ.

A from-scratch version: a shared module owning the state enum and the
trigger-matching function, with `advance()`/`fire_event()` and the Kripke
BFS step built as thin layers over it. `build_kripke_from_runtime()` would
then be close to a formality — a type/view conversion — rather than a
hand-maintained classification with room to drift.

## Relevance beyond this toolchain

Correspondence between operational and verification semantics is a
standard, well-studied concern in formal methods generally (soundness of
a model checker relative to an implementation) — framing it this way
means the open problem here is not an implementation quirk specific to
this codebase, but an instance of a recognised question, with a
recognised vocabulary, that a reviewer would find legible.

## Candidate uses

- **arXiv revision**: strengthens the "Limitations and future work"
  section with a precisely-scoped statement — e.g. "the operational and
  verification semantics are currently independent implementations of the
  same specification language; establishing and mechanically checking
  their correspondence is future work" — rather than leaving the gap
  implicit.
- **Implementation refactoring**: gives a concrete target (shared state
  enum + shared matching function) for the next time either
  `el_engine.py` or `el_kripke.py` is touched, rather than continuing to
  extend both independently.
- **Future paper**: the correspondence question, and how it was surfaced
  (via a probe-tier feature addition — AM-39 — rather than a planned
  verification pass), may itself be worth a short methodological note in
  a future paper or the journal version of this one.

## Supporting evidence

- `docs/CONCEPTS_INDEX.md`: "Event-triggered activation (Step 7c) —
  implemented but untested" (commit `88633a4`)
- `docs/CONCEPTS_INDEX.md`: "Engine/Kripke event-model symmetry gap —
  undocumented, not deliberately designed" (commit `88633a4`)
- `docs/CONCEPTS_INDEX.md`: "Engine/Kripke unification — what a shared
  design would and wouldn't merge" (this session)
- `docs/el_grammar_amendments.md`: AM-22 (2026-06-05), AM-39 (2026-07-15)
- Two diagrams produced 2026-07-15 in chat (not yet exported to the repo):
  (1) the AM-39 shared-helper architecture, showing
  `_activate_triggered_tokens()` as the convergence point for
  `advance()` Step 7c and `Runtime.fire_event()`, with `el_kripke.py`
  shown disconnected; (2) the Kripke-side `WAITING`/P6a cascade shape, for
  comparison against (1).
