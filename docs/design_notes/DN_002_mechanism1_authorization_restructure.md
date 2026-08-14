# Design Note DN-002: Mechanism 1 Restructure — Patient → GP Practice → Specialist Clinician → AI Agent (Option B′)

**Status:** Not started — design brief only, not yet scoped for implementation
**Priority:** TBD
**Date:** 2026-08-14
**Relates to:** `referral_scenario.el` (`patientDataAuthorization`), `docs/patient_authorization_and_obligation_delegation.md`, `docs/CONCEPTS_INDEX.md` ("`conductAIExamination` has no enforced link to data-access authorization", 2026-08-14)

Design context established 2026-08-14, following the medico-legal
realism discussion and the discovery that `conductAIExamination` has no
enforced coupling to data-access authorization (separate open finding,
`docs/CONCEPTS_INDEX.md`). Not yet scoped for implementation — this is a
brief for a future design session, same discipline as T5/R30.

## Motivation

Mechanism 1 (`patientDataAuthorization`, `referral_scenario.el`)
currently models data-access authorization as a single hop: `Patient →
SpecialistAIAgent`. This does not match real clinical consent practice
(FHIR's own Consent definition; the project's own FHIR-generated paper
example) and does not mirror Mechanism 2's proven, more realistic
three-actor shape (`GPPractice → SpecialistClinician →
SpecialistAIAgent`, via `gpToSpecialistDelegation` →
`specialistToAIDelegation`).

Option B′ restructures Mechanism 1 to mirror Mechanism 2's shape while
preserving the patient-facing demo narrative (patient as root, ultimate
authority) that motivated the original single-hop design.

## Target structure

Three `Authorization` blocks, replacing the current single
`patientDataAuthorization`:

1. **`patientToGPAuthorization`** (new) — `authority: Patient`,
   `to_agent`/`to_role`: GPPractice (or GPClinician — TBD, see "Solo vs.
   corporate practice" note below).
2. **`gpToSpecialistAuthorization`** (new) — `authority: GPPractice`,
   `to_agent`/`to_role`: SpecialistClinician.
3. **`specialistToAIAuthorization`** (replaces the current
   `patientDataAuthorization`) — `authority: SpecialistClinician`,
   `to_agent: SpecialistAIAgent`.

**Mechanical note, confirmed 2026-08-14 (verified against
`grammar/v2/el_grammar.tx:1007-1023` and `el_kripke.py:1549`'s
`walk_chain()`):** `Authorization` has no chain construct (unlike
`Delegation`'s `transfers_burden`/chain-walking, proven correct on
Mechanism 2's two hops). These would be **three independent grants**,
not one walked chain — `el_kripke.py`'s `walk_chain()` logic operates
only on the Delegation graph and does not apply here, and would need no
changes — but nothing today automatically links the three
Authorizations' validity to one another.

## Open decision — must be resolved before implementation

**Does revoking an upstream Authorization cascade to downstream ones?**

Two real options, not yet decided:

- **(a) Independent** — each of the three Authorizations is revoked
  separately; the Patient revoking `patientToGPAuthorization` does *not*
  automatically deactivate `specialistToAIAuthorization`. Simple to
  implement (each is just its own `revoke_authorization`/
  `reinstate_authorization` call, reusing existing R30/R31 machinery
  unchanged). But arguably wrong in practice — if the patient withdraws
  consent at the root, the AI agent's downstream access should
  presumably stop too, and "independent" would not guarantee that.
- **(b) Cascading** — revoking an upstream Authorization should also
  deactivate (or otherwise constrain) downstream ones. This is
  structurally the *same missing-coupling problem* already logged as an
  open finding for `conductAIExamination` (a downstream action currently
  unaware of upstream authorization state) — solving it properly here
  might mean solving it once, generally, rather than as two separate
  patches. Real new engine work, not a config flag.

Given the parallel to the `conductAIExamination` finding, worth
discussing whether these two problems ("does this action check its
authorization" and "does revoking authorization upstream propagate
downstream") should be designed together, as one general coupling
mechanism, rather than two independent fixes landing at different times.

## Downstream impacts (not yet scoped in detail)

- **Board UI consent panel** — currently shows one Authorization
  (`patientDataAuthorization`). Would need to show either the full
  three-hop chain, or be redesigned around whichever hop is most
  relevant to the demo narrative (likely the root, Patient→GPPractice,
  to preserve "patient as ultimate authority").
- **R30/R31 endpoints** — `/authorizations/{name}/revoke` and
  `/reinstate` are already name-parameterized, so they should work
  against any of the three new Authorization names without engine
  changes — but the *board UI's* buttons are currently hardcoded to
  `patientDataAuthorization` specifically and would need updating to
  target the correct hop(s).
- **`patientRecordAccessPermitByRole`** — the separate, non-Authorization,
  role-membership-driven grant to `SpecialistClinician` (confirmed
  earlier this week) is unaffected by this restructure — it's a
  structurally different mechanism and stays as-is.

## Solo vs. corporate practice note

Per the medico-legal research: `patientToGPAuthorization`'s `to_agent`
target (`GPPractice` vs. `GPClinician`) should reflect which practice
structure the reference scenario is meant to represent — solo/sole-trader
(individual clinician is the legal entity) vs. incorporated/partnership
(practice is the APP entity). `referral_scenario.el` currently uses
`GPPractice` as a party throughout, suggesting the corporate-practice
model is already the implicit choice — worth confirming this is
deliberate before building on it further.

## Explicitly out of scope for this brief

- Fixing `conductAIExamination`'s precondition-enforcement gap — separate
  open finding, may or may not be designed together per the cascading
  question above, but is its own decision either way.
- Any grammar/engine changes — none are currently believed necessary;
  `Authorization` already supports this shape. Should be confirmed with
  a ground-truth check at the start of the actual design session, not
  assumed.

## Suggested first steps for the future session

1. Resolve the cascading-revocation question (independent vs. coupled),
   and decide whether to design it alongside the `conductAIExamination`
   fix as one general mechanism.
2. Confirm solo vs. corporate practice framing for
   `patientToGPAuthorization`'s target.
3. Ground-truth check: confirm no existing code assumes exactly one
   Authorization per actor-pair before adding three new blocks (mirroring
   the dual-grant conflict check already done for Burden+Permit
   coexistence on `SpecialistAIAgent` this week).
4. Only then: scope the actual diffs (new Authorization declarations,
   UI changes, test coverage), following the same diff-by-diff,
   empirically-verified discipline used for T5/R30 all week.
