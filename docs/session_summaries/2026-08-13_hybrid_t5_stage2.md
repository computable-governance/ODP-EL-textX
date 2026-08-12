# Session Summary — 2026-08-13 (Stage 2 of hybrid-mode T5)

## Context
Direct continuation of Stage 1 (2026-08-11, commit `6ae1581`). Closes the
gap identified there: neither Kripke build mode could see a live runtime
event (grant or revoke) — hybrid mode read live state but only for
Burdens, spec-only mode (where T5 lives) never saw runtime state at all.
Stage 2 extends hybrid mode to handle Permit/Embargo and adds hybrid-mode
T5, making a live governance event (starting with revocation, since R31
already exists) formally verifiable end-to-end for the first time.

## Work completed — four diffs, all empirically verified, 98/98 passing

- **Diff 1** — split `_build_embargo_holder_index()` into pure
  `_extract_embargo_holder()` (structure only, single `HoldsToken` tier —
  simpler than Permit's split since Embargo has no `Authorization`-based
  tier) plus a thin spec-static-state wrapper. Empirically verified
  against real spec data (gp_referral/referral both declare
  `patientRecordAccessEmbargo`); ereferral correctly flagged vacuous
  (zero Embargo tokens in its spec).
- **Diff 2** — hybrid-mode Permit/Embargo descriptor sourcing in
  `build_kripke_from_runtime()`. Holder sourced from live `tok.holder`
  for both kinds (confirmed via `TokenInstance`'s shared field — no new
  lookup mechanism needed, simpler than originally estimated). Embargo's
  design-spec text was corrected mid-implementation: `tok.holder` directly,
  not `_extract_embargo_holder(spec)` as originally written, since
  `revoke_authorization()` bakes the correct holder into the embargo
  `TokenInstance` at creation time and no embargo exists in `state.tokens`
  before a revocation happens. Re-verified against the actual restructured
  code (not a hand-reconstruction) after an initial verification gap was
  caught — Burden and Permit `for_action` agreement both confirmed clean
  across all three scenarios.
- **Diff 3** — hybrid-mode T5 (Exercise) + Embargo guard ported into the
  existing BFS loop, after confirming `occurred_actions` propagation and
  `_build_propositions()` needed no upstream fixes (both already
  mode-agnostic). Verified beyond "doesn't crash": world counts roughly
  doubled per scenario (e.g. gp_referral 144→275) as T5 adds
  occurrence-branching; real `exercise:` edges and `occurred:`
  propositions confirmed present via direct inspection of
  `build_kripke_from_runtime()`'s actual output.
- **Diff 4** — `tests/test_hybrid_t5_exercise_embargo_guard.py`, 4 tests:
  three minimal-fixture cases mirroring pre-exec T5's original three
  (fire / same-holder-suppressed / different-holder-not-suppressed, using
  `km.EF()`), plus one real end-to-end test against the referral scenario
  using `revoke_authorization()` — asserting on the specific
  `exercise:patientRecordAccessPermitByAuthorization → ...` label's
  presence-then-absence in `km.labels.values()`, not a bare `EF()` check
  (see finding below for why). Includes an added third assertion
  confirming the unrelated `...ByRole` edge stays present after
  revocation — this is what explains, within the test itself, why a bare
  `EF()` query wouldn't have flipped.

## Findings surfaced during Stage 2

1. **`EF(occurred:...)` staying `True` after revocation — correct
   behavior, not a bug.** The referral scenario has two independent
   Permits for the same `for_action` (`patientRecordAccessPermitByRole`,
   held by `SpecialistClinician`; `patientRecordAccessPermitByAuthorization`,
   held by `SpecialistAIAgent`). Revoking the Authorization-based grant
   correctly leaves the Role-based grant intact — `EF` is existence-
   quantified over the whole model and can't distinguish which permit
   satisfies it, by design. This directly shaped Diff 4's revoke test to
   assert on the specific edge label rather than the aggregate `EF` verdict.

2. **T5 label-collision — a genuine, pre-existing explainability gap
   (both build modes), logged to `CONCEPTS_INDEX.md`, not fixed.**
   `KripkeModel.labels` is keyed only by `(w, w')`, not by which token
   caused the transition. When two Permits share a `for_action` and
   independently compute the same successor world, the second-processed
   permit's label silently overwrites the first's in the dict (the edge
   itself, in `edges`, is unaffected — only its label/attribution is
   lost). `AF`/`EF` results remain correct regardless, since they don't
   depend on attribution — but anything wanting to show "which specific
   grant enabled this action" (an audit or demo feature) could get a
   silently incomplete answer. Not introduced by Stage 2; discovered via
   the referral scenario's real two-permit structure while investigating
   finding #1.

3. **Pre-existing, unrelated bug in `Runtime.build_from_spec()`**
   (`el_runtime.py`): reads `getattr(el, "tokens", [])` to auto-grant
   `holds`-declared tokens, but the actual grammar/domain attribute is
   `holds_tokens` (confirmed against `el_grammar.tx:102` and
   `el_domain.py:321`) — so `build_from_spec()` silently grants zero
   tokens for any spec relying on `holds`. Discovered while building
   Diff 4's minimal test fixtures (mirroring pre-exec T5's `_T5_FIRE`
   pattern). Worked around using the existing pattern already established
   in `el_kripke.py`'s own `_run_hybrid_smoke_test()` (manual
   `grant_token(state, token_from_spec(...))` after `build_from_spec()`).
   Out of scope for Stage 2 — not fixed, only worked around, consistent
   with existing project convention.

## Verification discipline notes
Every diff empirically compared old-vs-new behavior directly against
live code output (not hand-reconstructed copies) after an initial gap
was caught and corrected mid-session; test-set identity confirmed against
the Stage 1 baseline after every diff, not just aggregate pass counts;
relevant existing tests (hybrid Burden AF/EF, pre-exec T5/Embargo guard)
confirmed passing by name after every diff, not folded into an aggregate
number.

## Deferred / not done today
- **R30 Option B (live grant)** — Stage 2 makes hybrid mode *capable* of
  verifying a grant's effect if one happened, but there's still no live
  grant path (per the 2026-08-11 finding). This is what's needed to
  complete the IT-governance demo's full "watch it respond" story for
  both grant and revoke — revoke's Kripke-level effect is now provable
  end-to-end (Diff 4's fourth test); grant's isn't yet, since nothing
  triggers it live.
- **T5 label-collision fix** — logged, not fixed; low urgency, doesn't
  affect AF/EF correctness.
- **`build_from_spec()` `holds`/`holds_tokens` bug** — logged via
  workaround pattern reuse, not filed as its own `CONCEPTS_INDEX.md`
  entry yet (worth doing, given it's unrelated to Stage 2 and could
  silently affect future hybrid-mode scenario authoring).

---
*Commits: `6ae1581` (Stage 1), `b864aaf` (Stage 1 session summary),
`3dedf96` (Stage 2: all 4 diffs, tests, and the label-collision finding).
All on `computable-governance/ODP-EL-textX` main, pushed to origin.*
