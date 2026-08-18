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

## T4 — Revocation *(reserved, not yet built)*

**Intended:** actor status transitions to `INACTIVE`; any obligation held
by that actor reverts to `PENDING` on the delegator.

Only a placeholder exists — referenced in `build_kripke_model()`'s own
docstring, never implemented. No example exists yet.

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
