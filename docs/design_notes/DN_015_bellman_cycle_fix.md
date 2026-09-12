# DN_015 — AM-80: Fix `bellman_values()`'s cycle-handling crash
(T7/T8 broke the algorithm's DAG assumption)

**Status:** Implemented (2026-09-09). **Relates to:** `toolchain/el_kripke.py`
(`bellman_values()`, `optimal_path()` — unaffected), `toolchain/el_api.py`
(`get_recommended_action()` — caller, unmodified).
**Found:** live-testing after AM-79 landed, same session, same day.

---

## 1. The crash, precisely

```
File "toolchain/el_api.py", line 969, in get_recommended_action
    V = km.bellman_values(gamma=gamma)
File "toolchain/el_kripke.py", line 1087, in bellman_values
    V[w] = max(
        self.utility(w_prime) + gamma * V[w_prime]
        for w_prime in succs
    )
File "toolchain/el_kripke.py", line 1088, in <genexpr>
    self.utility(w_prime) + gamma * V[w_prime]
KeyError: World(step=9, [all five referral burdens DISCHARGED])
```

Reproduces on the very first board-view load after a fresh server
restart, once the referral episode has genuinely progressed —
confirmed live 2026-09-09, same session AM-79 landed in.

## 2. Root cause — not a T7/T8 coding bug, an algorithm/assumption mismatch

`bellman_values()` ordered worlds via **Kahn's algorithm** (topological
sort), then computed each world's value in one reverse-topological pass,
assuming every successor's value is already computed by the time it's
needed. **Kahn's algorithm is only correct for DAGs** — worlds caught in
a cycle never reach in-degree zero, never enter `topo_order`, and are
silently skipped. When an already-processed world looks one up as a
successor, it's simply absent from `V` — the exact `KeyError`.

**Every transition rule before AM-79 is monotonic** — `PENDING →
DISCHARGED`, not-occurred → occurred — inherently acyclic; you can never
return to a prior world by only ever moving those states forward. **T7/T8
are the first genuinely reversible pair** — revoke → `superseded`,
reinstate → `active`. Revoke-then-reinstate, with nothing else changed
in between, returns to a world **identical** to the starting one — a
real cycle.

**Not limited to mid-episode states.** T7/T8 only depend on permit state
and strict-burden status — not on whether obligations are complete — so
even a fully-discharged terminal world can still revoke → reinstate →
back to itself, forever. That's exactly the crashing world: `step=9, all
five burdens DISCHARGED`, stuck in a 2-cycle with its own
permit-revoked variant.

**Confirmed not a graph-construction problem** — `build_kripke_from_runtime()`'s
BFS already dedupes on `World` equality (`if w_revoked not in worlds`),
so it correctly builds a finite graph even with cycles in it; the queue
never spins. The bug is isolated entirely to `bellman_values()`'s
*value-computation* step, downstream of a correctly-built graph.

## 3. The fix — switch to standard iterative value iteration

Not a workaround — this is the textbook-correct algorithm for exactly
this situation (an MDP with cycles, discount factor `gamma < 1`),
replacing the one-pass topological approach entirely. Implemented as
described in `docs/el_grammar_amendments.md` AM-80.

Two new parameters, `epsilon` (convergence threshold, default `1e-6`)
and `max_iterations` (safety cap, default `1000`) — both empirically
confirmed against the real referral scenario rather than trusted blind
(see AM-80's Empirical verification section: ~133 iterations to
converge at the default `epsilon` on the 1352-world graph;
`max_iterations` never binds).

**Performance:** switches the algorithm's complexity from a single
O(worlds + edges) pass to O(worlds × edges × iterations). Measured (not
assumed): `successors(w)`/`utility(w)` are loop-invariant but not free
(`utility()` rebuilds a dict and sums over obligations per call), so
both are precomputed once before the iteration loop — cut wall-clock
time from 2.56s to 0.91s on the 1352-world graph. `horizon=15` (2072
worlds) measured at 1.47s. Practical for an interactive API call.

## 4. What doesn't need to change

**`optimal_path()`** — already has its own explicit cycle detection
while *walking* a path (per its docstring: "stops when ... a cycle is
detected"). It depends on `bellman_values()` succeeding first; fixing
§3 transitively unblocks it — confirmed by test, not assumed.

**T7/T8 themselves, `build_kripke_from_runtime()`'s BFS, `World`'s
structure** — all unaffected. This is purely a `bellman_values()` fix;
the graph these cycles live in was always being built correctly.

**Governance/permit enforcement** — entirely unaffected by this bug.
Only the *recommendation* feature (`recommended-action`,
`objective-score` — both call `bellman_values()`) was crashing; the
actual live engine's permit/precondition checks never touched this code
path at all.

## 5. Test plan (as implemented)

`tests/test_am80_bellman_cycle_fix.py`, 6 tests:

- **Fixture sanity** — confirms the direct-reproduction graph (all five
  discharge-able referral burdens DISCHARGED) genuinely contains a
  cycle, via an independent DFS check (not `bellman_values()` itself).
- **Direct reproduction** — `bellman_values()` completes on that exact
  scenario and returns a value for every world in `self.worlds`,
  including the cyclic ones.
- **Convergence-equivalence, synthetic DAG** — a small hand-built
  4-world DAG (plain strings, duck-typed against
  `KripkeModel.bellman_values`), comparing against the pre-AM-80
  algorithm reimplemented inline as a stable regression fixture. The
  real referral scenario turned out *not* to be a stable "acyclic"
  fixture — at sufficient horizon even a fresh `w0` reaches
  revoke/reinstate cycles once `referralInitiationBurden` clears down
  some path — so the equivalence check needed a synthetic graph instead.
- **Fixed-point correctness on the real cyclic graph** — since the old
  algorithm cannot run there at all, verified instead that AM-80's
  output satisfies the Bellman fixed-point equation for every world.
- **Convergence regression guard** — confirms the default `epsilon`
  actually converges (not silently bottoming out at `max_iterations`),
  by comparing against a looser `epsilon` run.
- **`optimal_path()` composition** — confirms it still runs end-to-end
  post-fix.

Full suite: 339 passed, 1 xfailed (pre-existing AM-76 xfail) — zero
regressions against the pre-AM-80 baseline (333 passed, 1 xfailed).

## 6. Docs

- **AM-80** in `docs/el_grammar_amendments.md` — landed.
- `docs/CONCEPTS_INDEX.md` — landed same day (OPEN FINDING, RESOLVED
  same day).

## 7. Files changed

`toolchain/el_kripke.py` (`bellman_values()` only); new
`tests/test_am80_bellman_cycle_fix.py`; `docs/el_grammar_amendments.md`;
`docs/CONCEPTS_INDEX.md`; this file.

**Not touched:** `el_api.py` (caller, unmodified — same call signature),
`build_kripke_from_runtime()`, `World`, T7/T8 (all correct as landed).

---

*Same discipline as always: step-by-step diff review, one file at a
time, nothing pushed until confirmed on remote; explicit "commit now"
instruction required.*
