# Session Summary — June 16, 2026
## GP-Referral Scenario: Build, Bug Fixes, and First Coordination-Field Kripke Verification

This session picked up from the end of the previous session (June 14–16
continuation), which had completed `coordination_design_note_v3.md` §12
(community objective vs. collective obligations) and §13 (open items),
and handed off to Claude Code with the instruction to build the
GP-referral scenario per CLAUDE.md §13.1.

The previous session window hit ~90% usage mid-build and was deliberately
stopped to avoid context loss, to be resumed in a fresh window. This
session is that resumption.

---

## 1. Outcome summary

The GP-referral scenario is now built, validated, and formally verified
against all four Kripke verification questions defined in its header
comment. This is the **first time the coordination field of application
has been exercised end-to-end** — federation-level objective
(`all_discharged`), community-level objective (`any_discharged`),
cross-community delegation, and the EF≠AF distinction all verified
together in one scenario, rather than separately as in the consent
scenario (governance field only) or in design discussion alone.

Two genuine bugs were found and fixed along the way, not just the
scenario build itself.

---

## 2. `el_reasoner.py` — AM-18 class names + P2/P3 dissolution fixes

Commit: `ebefde7` (combined with scenario addition)

Seven stale pre-AM-18 class names were still in use in `el_reasoner.py`,
meaning these functions had likely never worked correctly against any
real parsed model since AM-18 was applied (the same class of bug
previously found and fixed in `el_kripke.py` and `el_validator.py` in
earlier sessions — this is the third file affected by the same historical
renaming gap):

- `DelegationDecl` → `Delegation` (`delegation_graph`, `ultimate_accountability` ×2)
- `CommitmentDecl` → `Commitment` (`ultimate_accountability`)
- `ObjectDecl` → `EnterpriseObject` (`can_perform`)
- `CommunityDecl` → `Community` (`can_perform`, `policy_conflicts`)
- `ActionDecl` → `Action` (`can_perform`)

Two further structural fixes were needed for object-processor dissolution
(P2, P3) that had changed the shape of parsed objects since these
functions were last correct:

- `can_perform`: `actor_obj.body.holds_tokens` (pre-P2 path) →
  `actor_obj.holds_tokens` (flat `DeonticToken` list after P2 dissolved
  the `body` wrapper)
- `can_perform`: `role.behaviour_items` / `ActionDecl` check (pre-P3
  path) → `role.actions` (typed list after P3)

**Verification:** the consent scenario's two-hop delegation chain now
resolves correctly, and — more significantly — the GP-referral scenario's
**cross-community** chain resolves: `GPPracticeParty → SpecialistClinicianAgent`
via `gpToSpecialistDelegation`. `can_perform` checks return correct
results. This is the first confirmation that `el_reasoner.py`'s
accountability-chain walking works across a federation boundary, not
just within a single community.

---

## 3. GP-referral scenario — `scenarios/gp_referral/gp_referral_scenario.el`

Commit: `ebefde7` (initial build), `4b25855` (Commitment fix, see §5)

Built per CLAUDE.md §13.1. Structure:

- **Federation**: `ReferralFederation` = `{ GPPracticeCommunity, SpecialistCommunity }`
- **Cross-community delegation**: `GPPracticeParty` delegates
  `referralResponseBurden` to `SpecialistClinicianAgent`
  (`gpToSpecialistDelegation`); GP practice also authorizes patient data
  access to the specialist
- **TokenGroups**:
  - `referralBurdenGroup` = `{ referralInitiationBurden, clinicalHandoverBurden, referralResponseBurden, assessmentSchedulingBurden }` — federation-level, `all_discharged`
  - `specialistBurdenGroup` = `{ referralResponseBurden, assessmentSchedulingBurden }` — specialist-community-level, `any_discharged`
  - Both AM-27 `SatisfactionCondition` operators exercised together for
    the first time in one scenario
- **ViolationResponse**: non-response to `referralResponseBurden`
  triggers specialist escalation and notification back to
  `GPPracticeParty`

Initial parse and validation: clean, 39 elements, 0 errors.

### 3.1 Verification questions (as designed)

| Q | Property | Expected |
|---|---|---|
| Q1 | `AF(discharged:referralInitiationBurden)` | YES — `discharge_mode: strict` |
| Q2 | `AF(discharged:referralResponseBurden)` | NO — `discharge_mode: eventual`; `EF` holds |
| Q3 | `objective_satisfied:ReferralFederation` | EF only — blocked by eventual `referralResponseBurden` |
| Q4 | `objective_satisfied:SpecialistCommunity` | EF — `any_discharged` satisfied on at least one path |

This set was deliberately designed so the EF≠AF formal finding applies
*across* a federation boundary, not just within one community: delegation
creates the *permission* for the specialist to respond (EF), but without
`discharge_mode: strict` on `referralResponseBurden`, the GP cannot
guarantee the specialist will respond on every possible path (AF not
guaranteed).

---

## 4. `verify_gp_referral.py` — verification script

Commit: `4b25855`

Written following the pattern of existing scripts in `scenarios/consent/`.
Parses the scenario, builds the Kripke model, runs Q1–Q4, and prints a
PASS/FAIL summary against the expected values encoded from the header
comment. Kept as a permanent, re-runnable artefact alongside the scenario
file rather than a throwaway check.

---

## 5. Bug found during first verification run: untracked TokenGroup members

First run: **6/7 checks PASS, Q3 EF FAIL** (`objective_satisfied:ReferralFederation`
under EF returned NO, expected YES).

### Root cause

`_build_obligation_descriptors` in `el_kripke.py` only tracks burdens that
appear in a `Commitment.burden` cross-reference (i.e. a burden only gets a
Kripke world-state entry if some `Commitment` declares `creates_burden:`
for it). The scenario declared `clinicalHandoverBurden` and
`assessmentSchedulingBurden` as `TokenGroup` members, used in the
`all_discharged(referralBurdenGroup)` federation objective, but neither
had a backing `Commitment`. With no world-state entry, the obligation
lookup returns `None` for those two members, and `all_discharged` over
the full four-member group can never become true — `EF` for the
federation objective was vacuously unsatisfiable, not genuinely false.

This is **not a toolchain bug** — `_build_obligation_descriptors`'s
behaviour is correct given its inputs. It is a **scenario-authoring gap**:
a `TokenGroup` member used in a satisfaction condition silently has no
formal existence in the Kripke model unless it is also independently
given a `Commitment`.

### Fix

Two `Commitment` declarations added to the scenario:

```
commitment clinicalHandoverCommitment {
    by: GPPracticeParty
    obligation: "Provide complete clinical handover documentation to specialist"
    creates_burden: clinicalHandoverBurden
}

commitment assessmentSchedulingCommitment {
    by: SpecialistParty
    obligation: "Schedule specialist assessment appointment for the patient"
    creates_burden: assessmentSchedulingBurden
}
```

`SpecialistParty` was confirmed as an already-established party name in
the scenario (used elsewhere as the `by:` party in an existing
commitment) before this was approved, rather than assumed.

### Result after fix

**7/7 PASS.** Full results:

| Q | Check | Result | Note |
|---|---|---|---|
| Q1 | `AF(discharged:referralInitiationBurden)` | YES | strict — tick suppressed while GP can act |
| Q2 | `AF(discharged:referralResponseBurden)` | NO | eventual — counterexample: tick→tick→violate |
| Q2 | `EF(discharged:referralResponseBurden)` | YES | witness: direct discharge at step 0 |
| Q3 | `AF(objective_satisfied:ReferralFederation)` | NO | blocked by eventual `referralResponseBurden` |
| Q3 | `EF(objective_satisfied:ReferralFederation)` | YES | all 4 group members now tracked; satisfiable on one path |
| Q4 | `AF(objective_satisfied:SpecialistCommunity)` | NO | both specialist burdens eventual; no guarantee either fires |
| Q4 | `EF(objective_satisfied:SpecialistCommunity)` | YES | `any_discharged` satisfied when `referralResponseBurden` discharges |

**Model size**: grew from 27 → 102 worlds once the two previously-untracked
burdens were added to the tracked set — reflecting the larger branching
tree across four concurrent obligations instead of two.

### Side-effect observed: P6b interaction confirmed correct

In the Q2 AF counterexample path, `assessmentSchedulingBurden` discharging
first causes `referralResponseBurden` to transition to `SUPERSEDED`. Both
tokens are members of `specialistBurdenGroup`, an `any_discharged` group.
This is correct semantics — the group's purpose (at least one specialist
burden discharged) is fulfilled by whichever member discharges first, and
the sibling is rightly superseded rather than left dangling.

This also serves as **corroborating evidence for the P6b fix made earlier
in the day** (commit `1802c70`, "P6b SUPERSEDED suppression limited to
`any_discharged` groups only") — this is the first time that fix has been
exercised by a real multi-burden `any_discharged` group in an actual
verification run, and it behaved as intended.

---

## 6. Commits this session

- `ebefde7` — AM-18 class names + P2/P3 dissolution fixes in
  `el_reasoner.py`; GP-referral scenario added (initial version, before
  the Commitment fix)
- `1802c70` — P6b SUPERSEDED suppression limited to `any_discharged`
  groups only (carried over from the tail end of the prior session window,
  confirmed working in §5 above)
- `4b25855` — Fix: add missing Commitments for `clinicalHandoverBurden`
  and `assessmentSchedulingBurden`; add `verify_gp_referral.py`

---

## 7. Open items arising from this session

1. **Should `el_validator.py` gain a new rule (V-16?) flagging `TokenGroup`
   members with no backing `Commitment`?** Currently this class of error
   is only caught at Layer 4 (Kripke) verification time, and even then
   only surfaces as an unexpected `EF`/`AF` result rather than a clear
   diagnostic — it took manual root-cause tracing in `el_kripke.py` to
   identify. A static check at validation time (Layer 2) would catch this
   far earlier and with a direct error message naming the unbacked token.
   This is a design decision, not yet implemented — needs discussion on
   whether it's a hard error or a warning (a `TokenGroup` member without a
   `Commitment` may be intentional in some modelling cases, e.g. if the
   burden is meant to be created by a `Delegation` or `Authorization`
   instead — needs checking against the grammar before deciding).

2. **`coordination_design_note_v3.md` §13 item 1** (GP-referral scenario
   "not yet built") should be marked complete, with the verification
   results from §5 above recorded. See companion update to that file.

3. The world-count growth (27→102) when going from 2 tracked obligations
   to 4 is worth a passing note in the design document as a concrete data
   point on how state-space size scales with concurrent obligation count
   — relevant context for the EDOC26 31-vs-30-worlds discrepancy
   discussion and for any future scalability remarks in the safety paper.

4. Items 2–6 from the prior session's §13 (31-vs-30 worlds discrepancy,
   Domain objective grammar amendment, fill_role/leave_role speech acts,
   CommunityObject, agent-facing query surface) remain open and untouched
   this session.
