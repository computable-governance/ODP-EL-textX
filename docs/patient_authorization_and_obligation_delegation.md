# Patient Authorization and Clinical Obligation: Two Independent Governance Mechanisms

*Governed Autonomy — reference note, 2026-08-14*

## Summary

The GP-to-specialist referral scenario is often described informally as a
single chain — "the patient's consent flows through the GP to the
specialist to the AI diagnostic agent." Direct inspection of the
underlying formal specification shows this is not quite right, and the
more precise picture is a better governance story than the informal one.

**There are two structurally independent mechanisms in play, not one
chain with three touchpoints.** They happen to both terminate at the same
actor — the AI diagnostic agent — but neither depends on, or flows
through, the other.

---

## Mechanism 1 — Data Access Authorization

The reference scenario (`referral_scenario.el`) currently models this as
a direct Patient-to-AI-agent grant: `authority: Patient, to_agent:
SpecialistAIAgent`. **This is a known simplification, not a considered
medico-legal position** — see "Realism caveat" below.

The authorization can be revoked and re-instated live, through two
independent trigger paths:

- **Direct action** — an explicit revoke/reinstate call.
- **External FHIR consent event** — a `Consent` resource with
  `status: inactive` (revoke) or `status: active` (reinstate).

These are two trigger mechanisms for the same single grant, not two
separate authorizations.

### Realism caveat

FHIR's own Consent resource definition describes a patient's agreement
as being with *"a party responsible for enforcing the patient's
choices"* — i.e., the treating organization, not each downstream tool
that organization happens to use. Real clinical consent practice matches
this: patients consent to their provider's data handling (including the
provider's use of AI tools), not to the AI tool as an independently
authorized party.

The scenario's own history confirms this was not always modeled as
Patient-direct. The predecessor scenario file, `gp_referral_scenario.el`
(the earlier, single-file design that `referral_scenario.el` superseded),
originally had `authority: GPPracticeParty` for its equivalent
authorization; commit `22b0d86` (2026-07-02, "AM-31b: ...change
patientDataAuthorization authority to PatientParty") changed it to a
direct patient grant, matching neither FHIR's definition nor this
project's own FHIR-generated paper example (`ConsentAiDiagnostic001Auth`,
`authority: GpPractice001`, `scenarios/fhir/generated_governance.el`).
`referral_scenario.el` was authored later, in a single commit
(`f66c892`), already inheriting the direct-patient-grant pattern from
that AM-31b decision — it has no separate history of its own showing an
earlier practice-direct version. (Note: `gp_referral_scenario.el` uses
the naming convention `GPPracticeParty`/`PatientParty`/`SpecialistParty`;
`referral_scenario.el` dropped the `Party` suffix, using
`GPPractice`/`Patient`/`SpecialistPractice` instead. The two files are
not kept in sync and diverge on this and other points.)

The current `Patient`-direct binding in `referral_scenario.el` appears to
have been introduced specifically to demonstrate the patient's proactive
role as ultimate authority over their own data in the board UI — a
legitimate demo goal, but one that traded away medico-legal realism
without an explicit decision to do so.

**Which entity should hold `authority` is not a single universal
answer** — it depends on practice structure:
- **Solo/sole-trader GP** — the individual clinician is the legal
  entity; both informed-consent-to-treat (a personal, AHPRA-governed
  obligation) and privacy/data-use consent (Privacy Act, APP entity)
  converge on the same person.
- **Incorporated or partnership practice** (the more common structure)
  — the *practice* is the APP entity for privacy/data-use purposes,
  while the *individual clinician* still personally holds the
  informed-consent-to-treat obligation. These diverge.

The DSL grammar requires no change to support either pattern —
`Authorization.authority` already accepts any `EnterpriseObject`
reference. This is a scenario-authoring choice, not an engineering task.

**Options considered for the reference scenario** (not yet decided):
- **A — Revert to `GPPractice`**: matches the pre-AM-31b predecessor
  design and the paper's FHIR example; loses the patient-empowerment demo
  narrative as currently built.
- **B — Two-tier model**: add `Patient → GPPractice` (new), restore
  `GPPractice → SpecialistAIAgent`. Most accurate; keeps the
  patient-empowerment story correctly scoped (patient consents to their
  provider); requires new design work (does revoking `Patient →
  GPPractice` cascade to `GPPractice → SpecialistAIAgent`, or are they
  independent?).
- **C — Leave as-is**, documented here as a known simplification.

## Mechanism 2 — Clinical Obligation Delegation

Separately, the *obligation* to examine the referred patient is
delegated along an accountability chain rooted at the GP Practice, with
no structural connection to Patient authorization:

**GP Practice → Specialist Clinician → AI Diagnostic Agent**
(`gpToSpecialistDelegation` → `specialistToAIDelegation`,
`referral_scenario.el`)

The GP Practice is the ultimate, non-transferable root of accountability.
The Patient has no structural role in this chain — the scenario's own
source comment is explicit that the Authorization "does not make Patient
a co-principal" of anything in the delegation chain
(`referral_scenario.el:746`).

## Why the AI Agent Needs Both, Independently — In Principle

For the AI diagnostic agent to lawfully perform its role, it should need:

1. **Permission** to access the patient's data (Mechanism 1), **and**
2. **An active, undischarged obligation** to perform the examination
   (Mechanism 2).

**Important qualification, discovered 2026-08-14:** today, these two are
*not actually coupled at the engine or verification layer* — see the
"`conductAIExamination` has no enforced link to data-access
authorization" finding in `docs/CONCEPTS_INDEX.md`. The precondition
that should enforce this ("AI agent must hold
`patientRecordAccessPermitByAuthorization`") is currently self-asserted
by the API caller, not checked against live Permit state. This section
describes the intended design; the finding describes the current,
unenforced reality.

## Why This Separation Is the Right Design, Once Properly Enforced

A single unified "Patient → GP → Specialist → AI" chain would imply that
consent and clinical accountability are the same kind of thing. They are
not:

- **Who may act** is a data-subject rights question, revocable at will,
  independent of clinical workflow.
- **Who must act** is a professional and organizational accountability
  question, independent of patient consent state.

Keeping these formally separate means each can be reasoned about,
audited, and changed on its own terms. A governance system that could
only express a single merged chain would not be able to answer, cleanly,
"is this AI agent currently permitted to act, and separately, is it
currently obligated to act" — both real, independently meaningful
governance questions, *once the coupling between them that should exist
at the moment of action is actually enforced*.

## Real-World Precedent for AI-Specialist Collaboration

Worth grounding the "AI conducts examination on behalf of specialist"
framing against what autonomous diagnostic AI actually does today, since
this bears on how `conductAIExamination`'s semantics should eventually
be modeled.

**IDx-DR / LumineticsCore** (FDA De Novo authorization, 2018; rebranded
2023) — autonomous detection of diabetic retinopathy from retinal
photographs. Genuinely autonomous in the FDA's sense: makes a clinical
determination without a physician reviewing the image first. But its
real-world role does **not** match "AI acts on behalf of a specialist" —
its explicit purpose is to bring screening "from the specialist's office
to primary care," letting a GP office screen *without* a specialist
referral at all. Not a delegation-chain precedent.

**Viz.ai** — reads head CT angiograms to detect suspected large-vessel
occlusion strokes, then alerts neurointerventional (specialist) teams.
Its own description is explicit: "does not make a diagnosis
independently, but serves as a critical rapid triage aid." This is a
closer real-world match to the scenario's delegation shape — AI performs
a bounded analysis, then reports/alerts a human specialist for judgment
and action, rather than replacing the specialist's role outright.

**Implication for modeling `conductAIExamination`:** the stronger,
better-precedented framing is "AI performs a bounded analysis and
emits an alert/report back to the accountable specialist" (Viz.ai's
shape), not "AI conducts an open-ended diagnostic examination on the
specialist's behalf." Once the enforced-precondition gap above is
addressed, the Action's `emits`/reporting-back semantics should probably
be built to reflect this — a genuine event fired back to
`SpecialistClinician`, not left as unstructured description text.

---

*Reference implementation: `referral_scenario.el`
(`computable-governance/ODP-EL-textX`). Authorization mechanism:
`patientDataAuthorization`. Obligation delegation chain:
`gpToSpecialistDelegation` → `specialistToAIDelegation`. Related open
finding: `conductAIExamination` has no enforced link to data-access
authorization (`docs/CONCEPTS_INDEX.md`, 2026-08-14).*
