# Kripke Transition Rules — T1 through T6

*Reference note, 2026-08-18. Companion to `docs/CONCEPTS_INDEX.md`'s
`conductAIExamination` finding and the T6 design work following it.*

Each rule below transitions one Kripke world to another by mutating
part of the world's state: `obligation_states` (T1-T4) or
`occurred_actions` (T5-T6). All examples are drawn from
`scenarios/referral/referral_scenario.el`, the production reference
scenario.

---

## What "ACTIVE" means, precisely

Every rule above checks an actor's `ActorStatus.ACTIVE` status — worth
being precise about what this tracks, since it's easy to conflate with
other uses of "active" in this project (a Permit's own `state: active`,
or "the community that defines Referral processes").

**`ActorStatus.ACTIVE` is the runtime counterpart of the grammar's
`ActiveEO` (Active Enterprise Object) classification** — per ISO 15414
§6.3.1: *"active enterprise object: An enterprise object that is able to
fill an action role."* Every `party` and `agent` declaration in the
grammar is a specialization of `ActiveEO` (§6.6.8: *"An agent is an
active enterprise object that has been delegated something by, and acts
for, a party"*) — the toolchain's `party`/`agent` keywords are how
`ActiveEO` is expressed structurally.

The distinction that matters: `ActiveEO` is a **type classification**,
fixed at declaration time — a `party` or `agent` is permanently
`ActiveEO`-typed. `ActorStatus.ACTIVE` is a **runtime state** — whether
this particular `ActiveEO` can currently act, which can in principle
change per-world (once T4/Revocation is built; today nothing ever flips
an actor to `INACTIVE`, so every actor is `ACTIVE` throughout every
scenario).

**Two things `ActorStatus.ACTIVE` is *not*:**
- It is **not community- or role-scoped**. An actor's status is a
  single, flat, global flag per actor name in the `WorldState`
  (`current_actors.get(desc.holder) != ActorStatus.ACTIVE`, a plain
  dict lookup with no role/community qualifier) — even though the same
  actor may be *enrolled* in multiple roles across multiple communities
  simultaneously (e.g. `SpecialistClinician` holds both a standing role
  in `SpecialistPracticeCommunity` and an episode-scoped role in
  `ReferralEpisodeCommunity`). The model cannot currently express "active
  for one role, suspended from another."
- It is **unrelated to any Permit's own `state` field.** A Permit being
  `active` (in force) and its holder being an `ACTIVE` actor are two
  independent conditions — T5 (Exercise) requires both to hold
  separately; neither implies the other.

---

## T1 — Discharge

**A `PENDING` obligation, held by an `ACTIVE` actor, transitions to
`DISCHARGED`.**

No awareness of Permits today — this is exactly the gap this document's
"known gaps" section covers.

*Example:* `referralInitiationBurden` is `PENDING`, held by
`GPPractice`. If `GPPractice` is `ACTIVE`, T1 fires,
transitioning the obligation to `DISCHARGED` in the successor world.

## T2 — Violation

**A `PENDING` obligation past its deadline transitions to `VIOLATED`.**

Terminal — the resulting world is not enqueued for further expansion.

*Example:* `referralResponseBurden` has a deadline of "5 working days
from referral receipt". If the world's `step` counter passes that
deadline while the obligation is still `PENDING`, T2 fires, producing a
`VIOLATED` world with no further transitions from it.

## T3 — Tick

**Advances the step counter, when an `eventual` obligation is pending and
no dischargeable `strict` obligation is blocking it.**

The eventual/strict interaction rule: `strict` obligations (e.g.
`referralInitiationBurden`, `discharge_mode: strict`) must be resolved
before time is allowed to pass, if they're currently dischargeable —
this is what gives `strict` its "compelled" character in the model.

*Example:* if `clinicalHandoverBurden` (`eventual`) is `PENDING` and no
`strict` obligation is simultaneously dischargeable, T3 fires,
incrementing `step` with no other state change.

## T4 — Revocation *(implemented, hybrid mode only — AM-81, 2026-09-14)*

**Intended:** actor status transitions to `INACTIVE`; any obligation held
by that actor reverts to `PENDING` on the delegator.

Only a placeholder exists — referenced in `build_kripke_model()`'s own
docstring, never implemented. No example exists yet.

**Investigation findings (2026-09-12), before any implementation:**

Prompted by considering T4 as the formal mechanism for DN_005's
still-open businessStatus-linking gap (a delegation being superseded
when an alternate filler claims a previously-directed request).

- **T4 as currently documented is the wrong shape for that use case.**
  `ActorStatus.ACTIVE`/`INACTIVE` is a single, flat, global flag per
  actor name (confirmed: no role/community/delegation scoping exists
  anywhere in `el_kripke.py`'s actor-state handling). Revoking one
  delegation to an actor should not flip that actor `INACTIVE`
  everywhere, for every other obligation they may separately hold —
  that would be a real correctness bug, not a faithful implementation
  of "this one delegation is revoked."
- **A naive whole-actor implementation would also need a reverse
  direction to be usable** (an actor legitimately returns to active
  elsewhere after one displacement) — which would reintroduce a
  reversible cycle in the world-graph, the same shape as T7/T8's
  revoke/reinstate pair (AM-79). That specific failure mode is no
  longer dangerous on its own: `bellman_values()` was generalized to
  iterative value iteration in AM-80 specifically because it no longer
  assumes an acyclic graph, so a future cycle here would not crash the
  same way T7/T8's did. This does not make a whole-actor design
  correct — see the point above — but it does mean the cycle
  question itself is not a blocker.
- **Nothing partially built exists to extend.** Checked directly: no
  `revoke`/`Revocation` grammar keyword exists anywhere in
  `grammar/v2/el_grammar.tx`. `ELDelegation.revocable` is a static
  boolean flag only (no event/trigger mechanism). `JoinLeaveEffect` is
  an unrelated community-membership construct. T4 needs real design
  work from scratch regardless of scope.

**Recommended direction, not yet designed in detail:** scope T4 per
*delegation instance*, mirroring how T7/T8 themselves are correctly
scoped per specific Permit/Embargo instance (`permit_states`/
`embargo_states`) rather than as a blunt per-actor flag. This would
resolve the correctness concern above and give DN_005's
businessStatus-linking gap a formally verifiable target, not just a
descriptive/mapper-level one.

**Resolution (AM-81, 2026-09-14):** built exactly along the recommended
direction above. `World` gained `delegation_states` (per delegation
instance, `"active"|"revoked"`), not a per-actor `ActorStatus` flip —
`ActorStatus.INACTIVE` remains completely unused anywhere in
`el_kripke.py`, by design; the correctness concern this investigation
raised about a global actor flag is avoided entirely rather than fixed
after the fact. A new `_effective_holder()` resolves a burden's genuine
current holder (the delegator, once its delegation is flagged
`"revoked"` in a given world) and is threaded through T1's discharge
check/label, `strict_burden_blocks()`, and T6's holder/permit-ownership
check.

**What was built:**
- `el_engine.revoke_delegation()` (Layer 3) and hybrid-mode Rule T4
  (Layer 4) — see `docs/el_grammar_amendments.md`'s AM-81 entry for the
  full change list and empirical verification.
- Scoped to single `transfers_burden` Delegations only — matches this
  investigation's own framing (a delegation-instance-scoped mechanism);
  `transfers_token_group` Delegations are explicitly out of scope.
- `.revocable` is enforced as a real runtime precondition in
  `revoke_delegation()` — `revoke_authorization()`'s corresponding check
  is a known, separately-tracked looseness, not carried into this path.

**Explicitly deferred, not built this pass:**
- **Reinstate-delegation (the reverse direction).** One-way revoke
  only. The investigation above flagged that a *whole-actor* design
  would need a reverse direction to be usable, and noted the resulting
  cycle risk is no longer a crash risk since AM-80 generalized
  `bellman_values()` to handle cycles — that observation carries over
  unchanged to this narrower, correctly-scoped design too, so a future
  reinstate-delegation edge remains straightforward to add without
  reopening the cycle question.
- **`transfers_token_group` Delegations.** Only a Delegation's direct
  `.burden` reference is indexed; group-transfer Delegations never
  enter `delegation_index` at all and are unaffected by T4.
- **DN_005's businessStatus-linking gap itself.** This amendment gives
  that gap a formally verifiable target (as this investigation hoped),
  but does not itself wire T4 into the FHIR mapper or DN_005's live
  event handling — that remains separate follow-on work.

## T5 — Exercise

**An `ACTIVE` Permit, held by an `ACTIVE` actor, adds its `for_action` to
`occurred_actions`** — without transitioning the Permit's own state
(a standing grant isn't consumed by use). Gated by the actor-scoped
Embargo guard.

*Example:* `patientRecordAccessPermitByAuthorization` is `ACTIVE`, held
by `SpecialistAIAgent`, `for_action: "access_patient_clinical_records"`.
T5 fires, adding `"access_patient_clinical_records"` to
`occurred_actions` — making `EF(occurred:access_patient_clinical_records)`
provable from that world onward.

## T6 — Examine *(proposed, not yet built)*

**Intended:** discharge a Burden *and* record its associated action's
occurrence, atomically, gated on the live state of any Permit that
Burden's Action `requires_permit`s — closing the Layer 4 counterpart to
the Layer 3 fix already shipped (`docs/CONCEPTS_INDEX.md`,
"`conductAIExamination` has no enforced link to data-access
authorization").

Not yet designed in detail. Ground-truth work (2026-08-18) established
this needs to be a **general** rule, not a single-Burden carve-out — see
"Known gap: T1 is blind to `requires_permit`" below.

*Example (intended behavior, not yet real):* `aiExaminationBurden` is
`PENDING`, discharge Action is `conductAIExamination`, which
`requires_permit patientRecordAccessPermitByAuthorization`. If that
Permit is `ACTIVE` and the holder is `ACTIVE`, T6 would fire: transition
the Burden to `DISCHARGED` *and* add `"conductAIExamination"` to
`occurred_actions`, in one atomic edge. If the Permit is not `ACTIVE`,
neither happens — T1 must not independently discharge this Burden via
its own unconditional path.

---

## Known gap: T1 is blind to `requires_permit` (pre-existing, not introduced by today's fix)

Confirmed by full inventory across all three registered scenarios
(2026-08-18): **T1 discharges any Burden unconditionally**, with zero
awareness of whether that Burden's discharge Action carries a
`requires_permit` clause. This affects three Burdens, not one:

| Burden | Discharge action | Requires permit | Scenario(s) |
|---|---|---|---|
| `referralResponseBurden` | `acknowledgeReferral` | `patientRecordAccessPermitByRole` | `referral_scenario.el`, `gp_referral_scenario.el` |
| `assessmentSchedulingBurden` | `scheduleAssessment` | `patientRecordAccessPermitByRole` | `referral_scenario.el`, `gp_referral_scenario.el` |
| `aiExaminationBurden` | `conductAIExamination` | `patientRecordAccessPermitByAuthorization` (or plain `patientRecordAccessPermit` in `ereferral_model.el`) | all three |

This has been latent since these scenarios were first authored
(`gp_referral_scenario.el`, 2026-06-16) — **not introduced by today's
Layer 3 fix**. Two of the three Burdens were already correctly gated at
the engine (Layer 3, `advance()` Step 6) the whole time; only the
Kripke/Layer 4 side (T1) has always been blind to the requirement. This
means **T6's design must be general** — detecting "does this Burden's
Action have a `requires_permit` link" as a property, not hardcoding
`conductAIExamination` specifically — and **T1 must correspondingly
exclude** any Burden whose Action carries this link, deferring those
cases to T6, or the ungated T1 edge would remain reachable and undermine
the fix.

Five other Burden-discharging Actions across the three scenarios
(`initiateReferral`, `provideHandover`, `submitReferral`,
`acknowledgeReferral`/`scheduleAssessment` in `ereferral_model.el`
specifically, which never declared the permit requirement) have no
`requires_permit` link at all and are correctly unaffected — they
continue through T1's existing path exactly as today.
