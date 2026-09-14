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
| **T1** | Discharge | For each `PENDING` obligation held by an `ACTIVE` actor, add an edge to `DISCHARGED`. | Implemented, both builders |
| **T2** | Deadline Expiry (Violate) | If `w.step >= deadline_steps` and still `PENDING`, add an edge to `VIOLATED`. | Implemented, both builders |
| **T3** | Tick | Add an edge advancing `step` by 1, obligations unchanged — suppressed if any `discharge_mode: strict` obligation is `PENDING` and actionable (held by an `ACTIVE` actor). This is the rule AM-49/AM-76/AM-78 mirror into the live engine's own guard. | Implemented, both builders |
| **T4** | Revocation (delegation) | For a revocable, `transfers_burden` Delegation: flip that delegation's own per-world state from `"active"` to `"revoked"` (`World.delegation_states`, scoped per delegation instance — not a global `ActorStatus` flip, which would incorrectly affect every other obligation the delegate separately holds; see the 2026-09-12 investigation finding in `docs/CONCEPTS_INDEX.md`). A resolved `_effective_holder()` is threaded through T1's discharge check/label, `strict_burden_blocks()`, and T6's holder/permit-ownership check, so the burden is judged/attributed against the delegator once revoked. **Distinct mechanism from T7/T8** — this is about Burden/delegation revocation, not Permit/Authorization revocation. | **Implemented, hybrid mode only — AM-81 (2026-09-14)**. `transfers_token_group` Delegations are out of scope; one-way only (no reinstate-delegation edge); `build_kripke_model()` (static/pre-exec) is untouched, same as T7/T8. |
| **T5** | Exercise | For a permit `_permit_active()` reports usable right now (hybrid mode: genuine per-world state via `w.permit_dict()`, as of AM-79 — previously ungated on activity at all) with a `for_action` held by an `ACTIVE` actor, mark that action as occurred (added to `occurred_actions`) — the Permit's own token state does not transition; a Permit is a standing grant, not consumed by exercise. Has its own Embargo guard (actor-scoped, same-holder check). | Implemented, both builders; hybrid-mode guard corrected — DN_014/AM-79 (2026-09-09) |
| **T6** | Examine (permit-gated discharge) | Discharges an obligation whose `for_action` is gated behind a required Permit being active, via the shared `_permit_active()` two-tier check (per-world truth when tracked, else the old existence-only fallback). | Implemented; hybrid-mode permit-check corrected — DN_014/AM-79 (2026-09-09) — was reading a static, one-time snapshot (`permit_descriptors`, filtered active-only, computed once before BFS starts) instead of genuine per-world state |
| **T7** | Authorization Revoke | Supersede the granted permit; activate (or freshly create) the `on_revocation` embargo. Mirrors `revoke_authorization()` (`el_engine.py`). Gated by the same strict-burden condition as T3 (revoke/reinstate never discharge anything, so they're correctly blocked unconditionally while any strict burden is outstanding — AM-78 left this guard unchanged in the live engine). | **Implemented, hybrid mode only — DN_014/AM-79 (2026-09-09)** |
| **T8** | Authorization Reinstate | (Re-)activate the permit; lift the `on_revocation` embargo if active. Mirrors `reinstate_authorization()`. Same guard as T7. | **Implemented, hybrid mode only — DN_014/AM-79 (2026-09-09)** |

## C-series (pool-claiming, `any_discharged` collective obligation)

| Rule | Name | What it does | Status |
|---|---|---|---|
| **C1** | Claim | For each `CLAIMABLE` obligation held by an `ACTIVE` actor, if a structured Evaluation (accept/reject) unlocks it, add an edge transitioning it to `PENDING` — and mark sibling `CLAIMABLE` obligations in the same group as `LAPSED`. | Implemented, AM-61 — see `DN_003` |

## Related, not a transition rule itself

- **`ObligationState.SUPERSEDED`** — not produced by its own rule; a side
  effect of T1 (discharge) when a sibling in an `any_discharged` group
  gets discharged first (AM-57/58).
- **`ObligationState.WAITING`** — the pre-claim state a pool member sits
  in before becoming `CLAIMABLE`; not itself a transition target of any
  rule above, structural/initial only.

---

*Last updated: 2026-09-14, alongside AM-81 (T4 implemented, hybrid mode
only; T6's holder/permit-ownership check also switched to the new
`_effective_holder()` resolution, alongside T1 and
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
