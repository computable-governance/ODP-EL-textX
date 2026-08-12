# Session Summary — 2026-08-11

## Context
Follow-on from yesterday's T5 (Exercise)/V-17 work. Two threads: (1) the
Bellman planner's relationship to Compelled obligations, flagged as
highest-priority from the 2026-08-10 FTI conversation; (2) scoping the
IT-governance demo, which led to discovering a structural gap between the
runtime layer and both Kripke build modes, and doing the first stage of
work needed to close it.

## Thread 1: Recommended vs. Compelled — RESOLVED

Checked ground truth directly against `el_kripke.py` rather than reasoning
from the framing note alone. Two findings:

- **`discharge_mode` does not affect valuation.** `utility()`/
  `bellman_values()` never read it — a `strict` (Compelled) obligation is
  scored identically to `eventual` at every state. `discharge_mode: strict`
  only suppresses the T3 (Tick) edge, narrowing `max(successors)` to fewer
  candidates — structural compulsion, not a distinct reward.
- **Permit-exercise (T5) is entirely utility-neutral**, confirmed by
  reading T5's world construction directly: `obligation_states` is
  unchanged by a T5 edge, and `utility()` is a pure function of
  `obligation_states`.

**Conclusion:** the planner's silence on Permission is correct, not a
gap. Burden asks "ought this happen" (the planner has an opinion because
deontic obligation semantics give it one); Permit asks "may this happen"
(a modal possibility question, never an "ought" — no normative pressure
toward exercising a mere permission). "Recommended" is a Burden-only
concept; there was never a competing category to reconcile it against.
Logged to `CONCEPTS_INDEX.md` as RESOLVED (commit `7c1db62`). Left open,
not a gap: if a future scenario needs the planner to value *exercising* a
Permit specifically, that's a genuine new extension, not implied by
anything found today.

## Thread 2: IT-governance demo scoping — reframed, then blocked on a deeper finding

**Reframed the demo from "build a new IT-governance scenario" to
"surface what already exists."** `patientRecordAccessPermitByAuthorization`
in the referral scenario is already an IT-governance-shaped (access
control) rule, FHIR-Consent-grounded via R23/R24/R30/R31, coexisting with
the clinical Burden-driven rules in the same spec. The story is stronger
using real production content than a constructed example. Performance
(infrastructure telemetry) confirmed out of scope — not deontic, a
different kind of extension, kept as a separate future thread.

**Investigating what a live "watch it respond" demo would need surfaced
that it isn't currently possible, for either grant or revoke, under
either Kripke build mode** — logged as its own finding (commit `254abaf`),
found by tracing R31 (revocation) end to end:

- R31 works correctly, but only at the runtime/ledger level
  (`revoke_authorization()`, `el_engine.py:490-557`) — mutates
  `Runtime._state`/`_ledger`, never the parsed spec model.
- Neither Kripke builder can see a runtime event: spec-only mode (where
  T5 lives) only reads the static parsed model; hybrid mode reads live
  runtime state but only for Burdens, never calls the Permit/Embargo
  descriptor builders, and has no T5 (`build_kripke_from_runtime`'s own
  docstring documents Revocation as "Not yet implemented — placeholder
  for hybrid mode").
- AM-34's 6 tests all assert against runtime/ledger state directly; none
  build a Kripke model or check an AF/EF verdict after revocation.

**Decision:** pursue the real fix — extend hybrid mode to handle
Permit/Embargo and add hybrid-mode T5 — rather than a re-serialize bridge
or rescoping the demo to a static before/after comparison. Same
design-first discipline as T5 itself, staged in two parts to separate
regression risk on existing code from new-feature risk.

## Stage 1 (of hybrid-mode T5): general structure/state unification — COMPLETE

Before building hybrid-mode Permit handling, generalized the underlying
pattern for **both** token kinds: structure extraction is always
spec-derived and mode-agnostic; state is always supplied separately by
whichever mode is running. Landed as two diffs in `el_kripke.py`, each
empirically verified (not just reasoned about) via direct old-vs-new
comparison scripts, full dataclass equality, across all three registered
scenarios — full suite 94/94 after each diff, identical test set to
baseline (byte-for-byte diff of collected test names), relevant tests
(hybrid Burden AF/EF, T5, V-17) confirmed passing individually by name.

- **Diff 1** — `build_kripke_from_runtime()` now sources Burden structure
  from `_build_obligation_descriptors(spec)` when a spec-level Commitment/
  Delegation.token_group entry exists, falling back to the original
  inline computation (empirically verified byte-identical) when it
  doesn't.
- **Diff 2** — `_build_permit_descriptors()` split into pure
  `_extract_permit_structure()` (no state read) plus a thin wrapper
  reapplying the spec-static active filter — empirically verified
  byte-identical to the pre-split version.

**Two real findings surfaced during Stage 1, neither anticipated in the
original spec:**

1. **Holder/chain semantic conflict.** `_build_obligation_descriptors(spec)`'s
   holder/chain (a structural prediction from walking the static
   delegation graph) disagreed with hybrid mode's live `tok.holder` for
   4 of 5 burdens in the referral scenario — not a small margin, naming a
   different entity entirely (community/practice vs. the actual clinician/
   agent). Root cause: holder/chain are accountability *state* in hybrid
   mode (who holds the token right now, after real transfers), not
   spec-structure — correctly excluded from the merge, kept live-sourced
   in both modes. Would have silently corrupted `GET /obligations/
   {token}/status`'s holder field without failing any existing test,
   since no test asserts on holder identity today.
2. **ereferral coverage gap.** `_build_obligation_descriptors(spec)`
   produces zero entries for any of ereferral's 4 burden tokens — it only
   covers Commitment/Delegation.token_group-declared tokens, and
   ereferral's scenario builder grants tokens directly in Python without
   matching Commitments (a gap already documented in `el_api.py`'s
   docstring, now independently confirmed three times over the course of
   this session). Resolved via explicit, documented fallback to the
   original inline computation — preserves ereferral's behavior exactly
   rather than forcing a spec change to fit the refactor.

Both findings resolved via interactive design discussion mid-implementation
(field-level merge for holder/chain; fallback-with-empirical-proof for the
coverage gap) rather than deferred — consistent with the "no shortcuts"
instruction for this session.

## Naming/process note
One extended back-and-forth mid-session was caused by a misread diff
convention on my (the chat assistant's) part — reading an old-block-then-
new-block diff preview as if both landed simultaneously, incorrectly
flagging a non-existent duplicate-keyword bug three times before `grep`
confirmed the file was correct throughout. No actual code defect; worth
noting only so a future review defaults to trusting direct tool output
(`grep`, empirical comparison scripts) over diff-preview reading when the
two seem to disagree.

## Deferred / not done today
- **Stage 2 of hybrid-mode T5** — actual Permit state-sourcing from
  `runtime.current_state()` and the hybrid-mode T5 edge-generation rule
  itself, built on top of Stage 1's now-unified foundation. Not started.
- LinkedIn Post 1 ("Fast to draft, hard to verify") — staleness fix (the
  "we're building that now" line) and the generic industrial-governance
  addition, both drafted-in-chat but not yet applied to the actual post
  file. Still targeted for Friday.
- Performance/infrastructure-telemetry as a governance signal — confirmed
  out of scope for the IT-governance demo, not scoped as its own item.

---
*Commits: `7c1db62` (Bellman/Recommended-vs-Compelled RESOLVED), `254abaf`
(R30 Option B blocked on runtime-to-Kripke visibility gap), `6ae1581`
(Stage 1: unify structure/state extraction for hybrid-mode Burden/Permit
descriptors). All on `computable-governance/ODP-EL-textX` main, pushed to
origin.*
