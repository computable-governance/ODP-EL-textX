# DN_014 — Per-world Permit/Embargo state + new T7/T8 rules for
authorization revoke/reinstate in `build_kripke_from_runtime()`

**Status:** Design complete (chat-level), ready for CC implementation.
**Date:** 2026-09-09. **Relates to:** `toolchain/el_kripke.py`
(`World`, `build_kripke_from_runtime()`, `build_kripke_model()`),
`toolchain/el_engine.py` (`revoke_authorization()`,
`reinstate_authorization()` — read, not modified).

---

## 1. The problem, precisely

Live-tested today: with `referralInitiationBurden` discharged and
`patientDataAuthorization` genuinely revoked (via the FHIR consent
event), the Reachability Path panel's check for `AI Examination
discharged (permit-gated, T6)` returned **`UNREACHABLE — no path to
this proposition on any explored world`** — not "reachable in 2 hops"
(revoke's own reverse action), which is what the live system actually
allows.

**Root cause, confirmed by direct code reading:** `World` (the Kripke
model's core frozen dataclass) tracks exactly four things —
`obligation_states`, `actor_states`, `occurred_actions`, `step`. **Permit
and Embargo state are not part of a world's identity at all.**
`permit_descriptors` is computed **once**, before BFS expansion even
starts, by reading whatever the live system's permit state happens to be
at that exact moment (`_build_referral_runtime`'s `state.tokens`,
filtered `if tok.state != "active": continue`) — then treated as a
**fixed, global constant for the entire graph**. T6's gate reads this
static dict, never anything per-world. Once a permit is revoked, T6's
gate fails identically at every explored world, because the model never
represented "permit state" as something a world could vary on in the
first place — not because it correctly reasoned that no path exists.

**Historical origin, confirmed via past-session search — not a new
mistake, a known-at-the-time shortcut that was never revisited:** when
hybrid-mode `PermitDescriptor` was first built, the explicit instruction
was *"filtered on `tok.state == 'active'` (live state, mirroring the
spec-static filter's logic but sourced from runtime instead)"* — i.e.
the static/pre-exec mode's timeless approach (correct there — a parsed
spec file never changes mid-verification) was ported directly into
hybrid mode without reconsidering that live permit state, unlike a
spec's declared state, can genuinely change mid-exploration via
revoke/reinstate.

**`T4` is not the mechanism to extend for this.** `T4 — REVOCATION`
already exists, documented, in `build_kripke_model()`'s own docstring —
but it's about **delegation** revocation (a Burden's holder going
`INACTIVE`, the obligation reverting to the delegator), a different
concept from **authorization/permit** revocation. Still unimplemented,
out of scope here, not to be confused with what this note adds.

## 2. Design decision: extend `World` with per-world Permit/Embargo
*state* only — structure stays static

Same principle already established in this codebase (from the same
historical session, applied to Burden/structure): *"structure extraction
is always spec-derived and mode-agnostic; state is always supplied
separately by whichever mode is running."* Extending that one step
further: **who can hold a permit (`holder`, `for_action`) stays a static,
spec-derived fact — `PermitDescriptor`/structure extraction is
unchanged.** What becomes per-world is **whether that permit is
currently active** — exactly mirroring how `ObligationDescriptor`
(holder, chain, deadline, discharge_mode — static) already sits
alongside `obligation_states` (PENDING/DISCHARGED/VIOLATED — per-world).

**New rules: `T7` and `T8`** (next free numbers after `T6`; `T4` stays
reserved for delegation-revocation, untouched):

- **`T7` — AUTHORIZATION REVOKE:** mirrors `revoke_authorization()`.
  Supersede the permit, activate (or freshly create) the embargo.
- **`T8` — AUTHORIZATION REINSTATE:** mirrors `reinstate_authorization()`.
  (Re-)activate the permit, lift the embargo if active.

**Scope: hybrid mode only (`build_kripke_from_runtime()`), not
`build_kripke_model()`.** Matches `T4`'s own precedent exactly — the
static/spec-only builder has no live runtime to revoke against in the
first place; adding these rules there would be meaningless, not just
unnecessary.

## 3. `World` — new fields, backward-compatible by construction

```python
class World:
    obligation_states: _ObligStates
    actor_states: _ActorStates
    occurred_actions: _ActionOccurrences
    permit_states: _PermitStates = frozenset()   # NEW — (permit_name, "active"|"superseded")
    embargo_states: _EmbargoStates = frozenset() # NEW — (embargo_name, "active"|"lifted")
    step: int
```

**Default `frozenset()` is the critical backward-compatibility choice.**
Every existing test/scenario that constructs a `World` without knowing
these fields exist gets an empty set — meaning "not tracked here" — and
T6's gate (below) is designed to treat "not tracked" as "fall back to
old behavior" rather than "treat as inactive." This should mean the vast
majority of the existing suite needs **zero changes** — only new
tests that specifically exercise `T7`/`T8` need to populate these
fields at all. Add matching convenience accessors
(`get_permit`/`permit_dict`, `get_embargo`/`embargo_dict`), mirroring
`get_obligation`/`obligation_dict` exactly.

## 4. `build_kripke_from_runtime()` — populate `w0` fully, not filtered

Currently (the bug): `if tok.state != "active": continue` — silently
**omits** non-active permits from `permit_descriptors` entirely.

**New:** record every permit/embargo token's real current state into
`init_permit_states`/`init_embargo_states` at `w0` construction —
active *and* superseded/lifted both recorded, nothing filtered out.
`permit_descriptors` (structure only — holder, for_action) keeps
existing behavior, still populated for every permit regardless of
current state (needed by `T7`/`T8` to know who holds what).

**Thread the new fields through every existing `_make_world()` call
site in the BFS loop** (T1, T2, T3, T5, T6) — none of them change
permit/embargo state, so each simply carries `w.permit_states`/
`w.embargo_states` through unchanged into whatever new world it
constructs, the same way they already carry `occurred` through
unchanged when they're not T5.

## 5. `T6`'s gate — read per-world state, fall back to static existence

Current gate (paraphrased): *"if permit's structural entry exists in
`permit_descriptors` and holder matches, allow."* This conflated
*existence* (static) with *active-right-now* (should be per-world).

**New gate, two-tier for backward compatibility:**
```python
permit_state = w.permit_dict().get(permit_name)
if permit_state is not None:
    permit_active = (permit_state == "active")   # per-world truth, when tracked
else:
    permit_active = permit_name in permit_descriptors  # old behavior, when untracked
```
This means: any existing scenario/test that never touches `T7`/`T8`
(so `permit_states` stays `frozenset()` throughout) sees **identical**
behavior to today — the fallback branch fires every time, exactly
matching current test expectations. Only worlds actually reached via a
`T7`/`T8` edge (or `w0` in a fresh hybrid-mode build, which now records
real state per §4) exercise the new per-world branch.

## 6. `T7`/`T8` edge-generation, precise

Mirror `revoke_authorization()`/`reinstate_authorization()`'s actual
logic (`el_engine.py`) as closely as the Kripke model's shape allows.
**Both gated by the same strict-burden condition already used by `T3`**
— not a new check, the identical boolean, since AM-78 left
`revoke_authorization()`/`reinstate_authorization()`'s live guard
unconditional (they never discharge anything, so they remain correctly
blocked whenever any strict burden is outstanding). Worth factoring this
shared condition into one small helper both `T3` and `T7`/`T8` call,
rather than duplicating the `any(...)` expression three times.

```python
# For each Authorization declared in the spec (need holder/permit_name/
# embargo_name — same fields revoke_authorization() reads from `auth`):
for auth in _collect(model_or_spec, "Authorization"):
    permit_name = auth.permit.name
    embargo_name = getattr(auth, "on_revocation_embargo", "")
    if not embargo_name:
        continue  # same defensive skip as the live engine's KeyError case

    if strict_burden_blocks(w):   # shared helper, same condition as T3
        continue  # no T7/T8 edge from this world at all

    permit_state = w.permit_dict().get(permit_name)
    if permit_state == "active":
        # T7 — Revoke
        new_permits = {**w.permit_dict(), permit_name: "superseded"}
        new_embargoes = {**w.embargo_dict(), embargo_name: "active"}
        w_revoked = _make_world(obligs, actors, occurred,
                                 frozenset(new_permits.items()),
                                 frozenset(new_embargoes.items()), w.step)
        edges.setdefault(w, set()).add(w_revoked)
        labels[(w, w_revoked)] = f"revoke:{auth.name}"

    if permit_state in ("superseded", None):  # None: never-yet-granted case
        # T8 — Reinstate
        new_permits = {**w.permit_dict(), permit_name: "active"}
        embargo_state = w.embargo_dict().get(embargo_name)
        new_embargoes = dict(w.embargo_dict())
        if embargo_state == "active":
            new_embargoes[embargo_name] = "lifted"
        w_reinstated = _make_world(obligs, actors, occurred,
                                    frozenset(new_permits.items()),
                                    frozenset(new_embargoes.items()), w.step)
        edges.setdefault(w, set()).add(w_reinstated)
        labels[(w, w_reinstated)] = f"reinstate:{auth.name}"
```

**Open question for CC to resolve empirically, not assume:** exactly how
`_collect(model_or_spec, "Authorization")` should be sourced inside
`build_kripke_from_runtime()` specifically — check whether it should
come from `spec.elements` (matching how `revoke_authorization()` itself
finds `auth` in `el_engine.py`) or from an existing helper already used
elsewhere in this function. Don't invent a third pattern; use whichever
of these two the function already leans on for similar lookups.

## 7. Test plan

- **Regression, first:** full suite re-run *before* writing any new
  tests, confirming the `World` field addition alone (all existing call
  sites updated to thread `permit_states`/`embargo_states` through
  unchanged) causes zero failures. This isolates "did the default+
  fallback design actually preserve old behavior" from "does the new
  logic work," same staged-verification discipline as AM-76/AM-78.
- **New tests, mirroring today's live finding exactly:** revoke
  `patientDataAuthorization` (build a hybrid-mode model from a runtime
  where it's genuinely revoked, e.g. via calling
  `revoke_authorization()` in test setup after discharging
  `referralInitiationBurden`), then check `AI Examination discharged
  (permit-gated, T6)` reachability — expect `w0(permit superseded) →
  w1(reinstate) → w2(examine)`, not `UNREACHABLE`.
- **Guard test:** with `referralInitiationBurden` still outstanding,
  confirm `T7`/`T8` edges are correctly *absent* from `w0` (mirroring
  `revoke_authorization()`'s own live block under this condition).
- **Backward-compat spot-check:** re-run a few of `test_referral_kripke_t6_permit_gate.py`'s
  existing cases explicitly, confirming identical witness paths to
  before this change, for scenarios that never touch revoke/reinstate.

## 8. Docs

- **AM-79** in `docs/el_grammar_amendments.md` — Status/Problem (cite
  this note + today's live finding)/What changed (`World` fields, `T7`/
  `T8`, `T6`'s two-tier gate, `w0` construction no longer filtering)/
  Standard reference (`T4`'s own docstring, as the precedent this
  extends without colliding with)/Empirical verification/Files changed.
- Close the OPEN FINDING this session would otherwise leave hanging —
  log it properly in `docs/CONCEPTS_INDEX.md` first if AM-79 doesn't
  land in one sitting, same discipline as every prior finding this
  project has tracked.

## 9. Files changed (anticipated)

`toolchain/el_kripke.py` (`World`, `_make_world()`, `build_kripke_from_runtime()`'s
`w0` construction and BFS loop, `T6`'s gate, new `T7`/`T8` edge
generation, new shared `strict_burden_blocks()` helper); new/updated
tests; `docs/el_grammar_amendments.md`; `docs/CONCEPTS_INDEX.md`.

**Not touched:** `build_kripke_model()` (out of scope, no live runtime),
`toolchain/el_engine.py` (read for reference only — live engine's
`revoke_authorization()`/`reinstate_authorization()` are already
correct and unchanged by this note).

---

*Same discipline as always: step-by-step diff review, one file at a
time, nothing pushed until confirmed on remote; explicit "commit now"
instruction required.*
