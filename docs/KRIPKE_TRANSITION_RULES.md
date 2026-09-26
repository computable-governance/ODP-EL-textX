# Kripke Transition Rules — Reference

A single place tracking every transition rule the Kripke model uses,
across both builders (`build_kripke_model()` — static/spec-only,
`build_kripke_from_runtime()` — hybrid/live). Update this alongside any
change to `el_kripke.py`'s rule set, the same discipline as
`el_grammar_amendments.md` — don't let it drift the way other records on
this project have drifted before.

Two independent lettering schemes exist: **`T`** for the main
obligation/permit/embargo transitions, **`C`** for pool-claiming
transitions (a separate mechanism, added later, numbered on its own
track rather than continuing the T-series).

## T-series

| Rule | Name | What it does | Status |
|---|---|---|---|
| **T1** | Discharge | For each `PENDING` obligation held by an `ACTIVE` actor, add an edge to `DISCHARGED`. P6a: the obligation's `discharged_by` event activates every `WAITING` obligation `triggered_by` it (activation step recorded). **Hybrid builder** (AM-99b): the same event also activates any `pending` Permit/Embargo it triggers, per world, as the engine's Step 7c does. P6b (`any_discharged` sibling supersession) runs in the static builder only; **hybrid has no P6b** (open). **Embargo guard** (AM-102): suppressed if an active embargo held by the (effective) holder covers the obligation's `for_action` — the engine's Step 5 applies to discharging actions too. | Implemented, both builders; hybrid P6a — AM-99b part 2 (2026-09-25) |
| **T2** | Deadline Expiry (Violate) | If still `PENDING` and the deadline has elapsed, add an edge to `VIOLATED`. **Static builder:** elapsed is `w.step - activated_at`, where `activated_at` is the step the obligation became `PENDING` (`World.activation_steps`, recorded by P6a; 0 for an obligation `PENDING` at w0). **Hybrid builder** (AM-99b part 1): the same `w.step - activated_at`, with w0 seeded from the engine — every obligation `PENDING` at w0 gets its engine activation tick (`activated_at_tick`, else `granted_at_tick`), in the same absolute-tick unit as hybrid `w.step` (w0.step is the runtime's tick). Previously `w.step >= deadline_steps`, counting from tick 0 rather than from grant or activation. The live engine counts the same way since AM-100 (`TokenInstance.activated_at_tick`, stamped on event or `activate`-effect activation). C1-claimed obligations (`CLAIMABLE` → `PENDING`) count from step 0 in the static builder, and from grant in the engine — deliberate, since pool deadlines are worded from the offer (AM-100). **AM-105:** the same edge activates (`WAITING` → `PENDING`, activation step = this step) every burden a ViolationResponse creates from the violated obligation (`KripkeModel.violation_activation`); a violated world is enqueued (below the horizon) only when its edge activated one, and is otherwise terminal. **AM-106:** in hybrid mode T2 is its own loop over every `PENDING` obligation, as in static — previously it sat inside the T1 loop after the permit gate, so a permit-gated burden was never violated in a hybrid model. The permit gate applies to T1 only. Hybrid label `violate:<oid>`; static `violate:<oid> (deadline=N steps)`. Neither builder's T2 excludes `strict` burdens, while the engine never clock-violates one (AM-103; see CONCEPTS_INDEX "Strict mode, model vs deployment"). **AM-108:** only for an obligation whose deadline has an elapsed-time magnitude (`el_engine._has_deadline_magnitude()`; `KripkeModel.enforceable_deadlines`). A prose deadline ("referral episode"), a bare number, or none is never clock-violated — the engine never does — though its descriptor keeps the parser's default of 5; see T2b. | Implemented, both builders; static builder counts from activation — AM-99a part 1; hybrid too — AM-99b part 1 (2026-09-25); response activation — AM-105; hybrid gated burdens — AM-106; enforceable deadlines only — AM-108 (2026-09-26) |
| **T2b** | Episode Conclusion (Violate) | For a `PENDING`, `eventual` obligation with no enforceable deadline (see T2): if a satisfaction group it belongs to, of a Community/Federation/Domain that opts in with `terminating { on_objective_achieved: true }`, has concluded around it — every other member `DISCHARGED` or `SUPERSEDED` (`all_discharged`), or at least one (`any_discharged`); the obligation itself excluded, as are groups with no other member — add an edge to `VIOLATED` at the same step, labelled `violate:<oid> (episode concluded)`. Mirrors the engine's `check_live_violations()` / `_owning_group_concluded()` (DN_010 option b). Same AM-105 activation and terminal rule as T2. | Implemented, both builders — AM-108 (2026-09-26) |
| **T3** | Tick | Add an edge advancing `step` by 1, obligations unchanged — suppressed if any `discharge_mode: strict` obligation is `PENDING` and actionable (held by an `ACTIVE` actor). This is the rule AM-49/AM-76/AM-78 mirror into the live engine's own guard. | Implemented, both builders |
| **T4** | Delegation Revoke | For a revocable, `transfers_burden` Delegation currently `"active"`: flip that delegation's own per-world state to `"revoked"` (`World.delegation_states`, scoped per delegation instance — not a global `ActorStatus` flip, which would incorrectly affect every other obligation the delegate separately holds; see the 2026-09-12 investigation finding in `docs/CONCEPTS_INDEX.md`). A resolved `_effective_holder()` is threaded through T1's discharge check/label, `strict_burden_blocks()`, and T6's holder/permit-ownership check, so the burden is judged/attributed against the delegator once revoked. **Distinct mechanism from T7/T8** — this is about Burden/delegation revocation, not Permit/Authorization revocation. Mirrors `revoke_delegation()` (`el_engine.py`). | **Implemented, hybrid mode only — AM-81 (2026-09-14)**. `transfers_token_group` Delegations are out of scope; `build_kripke_model()` (static/pre-exec) is untouched, same as T7/T8. |
| **T10** | Delegation Reinstate | The reverse of T4: for a revocable, `transfers_burden` Delegation currently `"revoked"`, flip that delegation's per-world state back to `"active"`, restoring `_effective_holder()`'s fall-through to the original delegate everywhere T4 redirected it (T1, `strict_burden_blocks()`, T6). Closes the one-way gap T4 deliberately left open at AM-81. Mirrors `reinstate_delegation()` (`el_engine.py`). Same strict-burden guard, same instantaneous/no-step-advance shape as T4. | **Implemented, hybrid mode only — AM-84 (2026-09-14)**. Same scope as T4 (`transfers_burden` only); `build_kripke_model()` (static/pre-exec) is untouched, same as T4/T7/T8/T9. |
| **T5** | Exercise | For a permit `_permit_active()` reports usable right now (hybrid mode: genuine per-world state via `w.permit_dict()`, as of AM-79 — previously ungated on activity at all) with a `for_action` held by an `ACTIVE` actor, mark that action as occurred (added to `occurred_actions`) — the Permit's own token state does not transition; a Permit is a standing grant, not consumed by exercise. Has its own Embargo guard (actor-scoped, same-holder check; since AM-102 it reads `el_engine._embargo_coverage()`, the engine's Step 5 rule: the Actions naming the embargo via `inhibited_by_embargo`, else its `for_action`, else every action); in the hybrid builder the guard reads per-world Embargo state via `_embargo_active()` (AM-99b — it previously read only the w0 state, so an embargo activated inside the model never blocked). **Fires the exercised action's event** (AM-99b): if the `for_action` emits an event, `WAITING` obligations `triggered_by` it become `PENDING` on the same edge (hybrid: also `pending` Permits/Embargoes). This is how gated actions fire their events — T11 excludes them — matching the engine, which fires Step 7c after its Step 6 permit check. An event that is some obligation's `discharged_by` is not fired here (left to T1/T6). **Strict guard** (AM-101): suppressed while a strict obligation is `PENDING` with an `ACTIVE` holder (the T3 condition; hybrid: `strict_burden_blocks()`, effective holder), unless the exercised action discharges a `PENDING` burden the permit holder holds — destroy effect, matching `for_action`, or emitting its `discharged_by` event (`_discharges_any()`). Mirrors the engine's Step 3.5 and its Step 3 `dischargeable` exemption; a kept exercise does not itself discharge (T1/T6 draw that edge). | Implemented, both builders; hybrid-mode guard corrected — DN_014/AM-79 (2026-09-09); per-world Embargo guard and event firing — AM-99b parts 2–3 (2026-09-25); strict guard — AM-101 (2026-09-26) |
| **T6** | Examine (permit-gated discharge) | Discharges an obligation whose `for_action` is gated behind a required Permit being active, via the shared `_permit_active()` two-tier check (per-world truth when tracked, else the old existence-only fallback). AM-99b: runs P6a on the obligation's `discharged_by` event and fires the gated action's own emitted event, in both builders; the hybrid Embargo guard reads per-world state (`_embargo_active()`), as T5's; coverage from `_embargo_coverage()` (AM-102). No P6b (safe today: no gated obligation is an `any_discharged` group member). | Implemented; P6a and event firing — AM-99b part 3 (2026-09-25); hybrid-mode permit-check corrected — DN_014/AM-79 (2026-09-09) — was reading a static, one-time snapshot (`permit_descriptors`, filtered active-only, computed once before BFS starts) instead of genuine per-world state |
| **T7** | Authorization Revoke | Supersede the granted permit; activate (or freshly create) the `on_revocation` embargo. Mirrors `revoke_authorization()` (`el_engine.py`). Gated by the same strict-burden condition as T3 (revoke/reinstate never discharge anything, so they're correctly blocked unconditionally while any strict burden is outstanding — AM-78 left this guard unchanged in the live engine). | **Implemented, hybrid mode only — DN_014/AM-79 (2026-09-09)** |
| **T8** | Authorization Reinstate | (Re-)activate the permit; lift the `on_revocation` embargo if active. Mirrors `reinstate_authorization()`. Same guard as T7. | **Implemented, hybrid mode only — DN_014/AM-79 (2026-09-09)** |
| **T9** | Transfer | For each Burden-kind `effect transfer` DeonticEffect (§6.4.7/§7.8.7) whose `from_role`/`to_role` each resolve to exactly one live actor via current role membership: if the token's current effective holder (via `_effective_holder()`) is that from-actor and the from-actor is `ACTIVE`, and the carrying Action hasn't already occurred in this world, add an edge reassigning the obligation's holder (`World.holder_overrides`, a field separate from `delegation_states`) to the to-actor and marking the Action occurred. Formal-verification counterpart to the already-live `transfer` DeonticEffect (`el_engine.py`, `elif op == "transfer":`) — Layer 3 is unaffected. Single-source/single-target only (no `from_role` at all, or `from_role`/`to_role` resolving to zero or multiple actors, is skipped); Permit/Embargo-kind tokens are out of scope. **Known, deliberately unfixed asymmetry:** `el_engine.py`'s own `transfer` handler resolves `to_role` via role membership but matches `from_role` directly against `TokenInstance.holder` with no role resolution at all — T9 resolves BOTH through the same role→actor lookup (the semantically correct behavior), not a mirror of that asymmetry. Gated by the same `strict_burden_blocks()` condition as T4/T7/T8 (a transfer doesn't discharge anything either). **Embargo guard** (AM-102): the carrying action may be performed by any enrolled actor (`from_role` resolves the source holder, not the performer), and the engine's Step 5 refuses it only for an actor holding a covering embargo — so the edge is suppressed only when every enrolled actor holds one. | **Implemented, hybrid mode only — AM-82 (2026-09-14)**. `build_kripke_model()` (static/pre-exec) is untouched, same as T4/T7/T8. |
| **T11** | Event Firing (action-emitted trigger) | For each event that some `WAITING` obligation is `triggered_by` and that an eligible Action `emits`, if the Action hasn't already occurred in this world, add an edge where every `WAITING` obligation triggered by that event becomes `PENDING` (activation step recorded in `World.activation_steps`, as P6a does) and the Action is added to `occurred_actions`. No step advance. Eligible = has `emits`, no `requires_permit`, and is not a discharging action (not any obligation's `for_action`, and its event is not any obligation's `discharged_by`) — events raised by discharge already fire through T1's P6a cascade (`_build_event_firing_index()`). Suppressed while a strict obligation is `PENDING` with an `ACTIVE` holder — same condition as T3, mirroring the engine's Step 3.5 guard (a T11 action discharges nothing). Verifier counterpart of the engine's Step 7c (`_activate_triggered_tokens()`, `el_engine.py`). Gated actions fire their events through T5/T6 instead (AM-99b part 3), so T11's exclusion no longer leaves them unfired. **Embargo guard** (AM-102): an ungated action may be performed by any actor, so the edge is suppressed only when every performer holds a covering embargo (static: every `ACTIVE` actor; hybrid: every enrolled actor). **Hybrid builder** (AM-99b part 2): same eligibility and strict guard, over the live-sourced descriptors, and the event also activates `pending` Permits/Embargoes per world (`_fire_event()`, using the engine's own `_find_spec_tokens_for_event()` lookup); the edge is taken only if the event activates something in the world. **Remaining asymmetries:** the static builder does not track Embargo/Permit state per world, so a static T11 activates obligations only; neither builder models events fired from outside the DSL (`Runtime.fire_event()`, e.g. FHIR-driven `encounterConcluded`). | **Implemented, both builders — static AM-99a part 2, hybrid AM-99b part 2 (2026-09-25)** |

## C-series (pool-claiming, `any_discharged` collective obligation)

| Rule | Name | What it does | Status |
|---|---|---|---|
| **C1** | Claim | For each `CLAIMABLE` obligation held by an `ACTIVE` actor, if a structured Evaluation (accept/reject) unlocks it, add an edge transitioning it to `PENDING` — and mark sibling `CLAIMABLE` obligations in the same group as `LAPSED`. | Implemented, AM-61 — see `DN_003` |

## Related, not a transition rule itself

- **`ObligationState.SUPERSEDED`** — not produced by its own rule; a side
  effect of T1 (discharge) when a sibling in an `any_discharged` group
  gets discharged first (AM-57/58).
- **Bounded response verdict (AM-99a part 3, both builders since
  AM-99b)** — not a transition rule but a change to how
  `check_obligation()` reads the model: for an obligation with
  `triggered_by`, the verdict is the bounded response property
  ("within horizon"), AG(pending → AF discharged) from every `PENDING`
  world with `step < initial.step + horizon`. AM-99b removed the
  temporary `KripkeModel.response_semantics` flag that limited this to
  the static builder. "not triggered within horizon" / "not resolved within
  horizon" are never reported as satisfied. See the open finding on
  horizon-step enqueueing in `docs/CONCEPTS_INDEX.md` for why horizon-step
  worlds are excluded.
- **`ObligationState.WAITING`** — an obligation whose `triggered_by`
  event has not fired; initial only, left by P6a (T1/T6), T5 and T11.
  Hybrid w0 maps an engine `pending` token with `triggered_by` to
  `WAITING` (AM-99b); a `pending` token without one (masked while
  delegated, §7.8.7) stays `PENDING`, and a `claimable` token still maps
  to `PENDING` — hybrid mode has no C1 yet (deferred).
- **Hybrid horizon (AM-99b part 4)** — `build_kripke_from_runtime()`
  expands worlds up to step `state.tick + horizon`; `KripkeModel.horizon`
  stays relative (counted from `initial.step`) in both builders.
  Previously absolute, so a runtime at tick ≥ horizon expanded only w0.

---

*Last updated: 2026-09-26, alongside AM-108 (T2 only for deadlines with
an elapsed-time magnitude; new T2b, the engine's episode-conclusion
violation). Previously updated the same day, alongside AM-106 (hybrid T2 its own loop,
applying to permit-gated burdens; the hybrid fallback descriptor takes the
live token's `for_action` and static deadline parsing) and AM-105 (T2
activates burdens a ViolationResponse creates; such a violated world
continues). Previously updated the same day, alongside AM-102 (one embargo blocking rule
for the engine and the verifier, `el_engine._embargo_coverage()`; embargo
guards added to T1, T11 and T9; T5/T6 read the shared rule). Previously
updated the same day, alongside AM-101 (T5 strict guard in both
builders, mirroring the engine's Step 3.5 and its `dischargeable`
exemption). Previously updated 2026-09-25, alongside AM-99b (hybrid mode mirrors the
engine's event model: T1 P6a, T2 from activation, T5/T6 fire action
events in both builders, T11 in hybrid, per-world Embargo guard,
relative hybrid horizon; the `response_semantics` flag removed; the
`WAITING` note corrected — it had described a pool-claiming state).
Previously updated the same day, alongside AM-100 (T2 row: the engine now
counts from activation too; C1 counting from grant recorded as
deliberate). Previously updated the same day, alongside AM-99a part 3
(bounded response verdict noted under "Related, not a transition rule
itself"). Previously
updated the same day, alongside AM-99a part 2 (T11 added — static
builder only, hybrid is AM-99b; T10 is taken by AM-84). Previously updated
the same day, alongside AM-99a part 1 (T2 in the static
builder now counts a deadline from the step the obligation became
`PENDING` — new `World.activation_steps` field, recorded by P6a — not
from step 0; hybrid T2 unchanged). Previously updated 2026-09-14, alongside AM-84 (T10 added — the reverse of
T4, closing the one-way gap AM-81 deliberately left open; T4's own row
retitled "Delegation Revoke" and its "one-way only" framing dropped,
now that T10 exists). Previously updated the same day, alongside AM-82
(T9 added — new `World.holder_overrides` field, separate from AM-81's
`delegation_states`; `_effective_holder()` extended with one additive
branch for it). Previously updated the same day, alongside AM-81 (T4
implemented, hybrid mode only; T6's holder/permit-ownership check also
switched to the new `_effective_holder()` resolution, alongside T1 and
`strict_burden_blocks()` — found necessary while live-verifying against
`referral_scenario.el`'s only in-scope Delegation, whose burden turned
out to be permit-gated). Previously updated 2026-09-09, alongside
DN_014/AM-79 (T7/T8 implemented; T6 corrected to genuine per-world
Permit state via the new shared `_permit_active()` helper; T5 gained
the same per-world guard as a necessary consequence of no longer
filtering `permit_descriptors` to active-only — found empirically while
implementing T7/T8, not called out in DN_014's own text). If a new rule
is added or an existing one's behavior changes, update this table in
the same commit — don't let it become a second place this project has
to remember to back-fill later.*
