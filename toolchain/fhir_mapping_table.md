# FHIR R4 → DSL-EL Governance Mapping Specification

**Version:** 1.0 — May 2026  
**Authors:** ComputableGovernance Research Programme  
**Status:** Draft — for inclusion in EDOC 2026 submission

---

## 1. Purpose

This document specifies the formal mapping between FHIR R4 resources and
ODP-EL governance constructs (ISO/IEC 15414:2015). It extends Table 2 of
the position paper "DSL + LLM as Complementary Layers" (May 2026) from a
conceptual comparison to a validated, implemented transformation.

The mapping is implemented in `fhir_mapper.py` and validated end-to-end:
a FHIR R4 Bundle is transformed into a DSL-EL `.el` specification, which
is then parsed, semantically validated (15 rules), and run through the
Layer 4 Kripke verifier (`el_kripke.py`).

---

## 2. Architectural Context

```
FHIR R4 Server (Layer 1 — data layer)
  Consent, ServiceRequest, Task, Practitioner, Organization, Patient, Device
        │
        │  fhir_mapper.py  (Mediator — translation layer)
        ▼
DSL-EL Specification (Layer 2 — governance layer)
  party, agent, burden, permit, embargo, commitment, delegation, authorization
        │
        ├──► el_validator.py  (structural consistency)
        ├──► el_reasoner.py   (accountability chain queries)
        └──► el_kripke.py     (modal verification + BDI recommendation)
```

**Key principle:** FHIR records *what* happened (data layer). DSL-EL specifies
*who is accountable* and *what must happen* (governance layer). The mapping
makes the governance layer computable from the data layer.

---

## 3. Mapping Rules

### 3.1 Demographic Resources → Object Declarations

| ID  | FHIR Source | FHIR Element | DSL-EL Target | Notes |
|-----|-------------|--------------|---------------|-------|
| R01 | Organization | Organization.name | `party` | Data controller; root of accountability chain |
| R02 | Patient | Patient.name | `party` | Data subject; not in delegation chain |
| R03 | Practitioner | Practitioner.qualification | `party` or `agent` | Agent if appears as Task.owner; party otherwise |
| R04 | Device | Device.deviceName | `agent` | AI system acting under delegation |

**R03 elaboration:** A Practitioner who requests services (appears in
`ServiceRequest.requester`) is a party — accountable in their own right.
A Practitioner who fulfils tasks (appears in `Task.owner`) is an agent —
acting on behalf of the requesting party.

---

### 3.2 ServiceRequest → Commitment and Burden

| ID  | FHIR Element | DSL-EL Target | Notes |
|-----|--------------|---------------|-------|
| R05 | ServiceRequest | `CommitmentDecl` | Root of the accountability chain |
| R06 | ServiceRequest.requester | `CommitmentDecl.by` | Party making the commitment |
| R07 | ServiceRequest.code / .note | obligation text + `burden` token | Note text preferred; code.text as fallback |
| R08 | ServiceRequest.occurrenceDateTime | `deadline` on burden | Converted to abstract step count by Kripke builder |

**R07 elaboration:** If the ServiceRequest note contains keywords "consent",
"inform", or "seek", the generated burden receives `discharge_mode: strict`
and `priority: critical`. This implements the governance intent that consent
obligations are non-deferrable.

---

### 3.3 Task → Delegation Chain

| ID  | FHIR Element | DSL-EL Target | Notes |
|-----|--------------|---------------|-------|
| R09 | Task | `DelegationDecl` | One delegation per Task |
| R10 | Task.requester | `DelegationDecl.from` | Delegator (principal) |
| R11 | Task.owner | `DelegationDecl.to` | Delegate (agent) |
| R12 | Task.basedOn → ServiceRequest | traces to root commitment | Used to resolve obligation text and burden token |
| R13 | Task.partOf → Task | `sub_delegation_allowed: true` on parent | The *parent* delegation must allow sub-delegation |
| R14 | Task.restriction.period.end | `duration` on delegation | Deadline for task completion |
| R15 | Task.status | observation note | Maps to ObligationState: requested→PENDING, completed→DISCHARGED, failed→VIOLATED |

**R13 elaboration:** When a Task references a parent via `partOf`, the *parent*
Task's delegation is marked `sub_delegation_allowed: true`. The child Task then
creates a valid sub-delegation. This correctly implements §7.10.1 of ISO 15414.

**R15 elaboration:** Task.status is not directly encoded in the generated spec
(which represents the governance structure, not runtime state). It is recorded
as a comment and available for hybrid mode Kripke initialisation.

---

### 3.4 Consent → Tokens and Authorization

| ID  | FHIR Element | DSL-EL Target | Notes |
|-----|--------------|---------------|-------|
| R16 | Consent.provision.type = permit | `permit` token + `AuthorizationDecl` | One permit per provision |
| R17 | Consent.provision.type = deny | `embargo` token | Prohibition on the named action |
| R18 | Consent (creation act) | `AuthorizationDecl` | Consent is a formal speech act, not just a state |
| R19 | Consent.performer | `AuthorizationDecl.to_agent` | Agent receiving the authorization |
| R20 | Consent.organization | `AuthorizationDecl.authority` | Organization granting the authorization |
| R21 | Consent.provision.period | `deadline` on token | Consent validity window |
| R22 | Consent.status = inactive | `DeclarationDecl` | Withdrawal is a formal declaration |

**R16/R18 distinction:** FHIR records `provision.type = permit` as a state.
DSL-EL treats the corresponding consent act as an `AuthorizationDecl` —
a speech act with formal deontic consequences. This is the core of the
"consent as formal act" finding in Table 2 of the position paper.

**R17 elaboration:** Sub-provisions (`provision.provision[]`) within a Consent
resource map to additional embargo tokens. This handles the common pattern
of a top-level permit with specific purpose-based denials (e.g., permit for
treatment but deny for research).

**R22 elaboration:** When `Consent.status = inactive`, a `DeclarationDecl`
is generated. This makes withdrawal a traceable governance event — the
declaration discharges the accountability obligation to maintain consent.

---

### 3.5 Deferred Rules

| ID  | FHIR Resource | Rationale for deferral |
|-----|---------------|------------------------|
| R32 | AuditEvent | Belongs to the governance ledger (future work) |
| —   | Bidirectional mapping | DSL speech act → FHIR update requires running FHIR server |
| —   | FHIR R5 differences | R4 is current HL7 Australia eRequesting target |

---

## 4. Validation Pipeline

The generated `.el` specification is validated at three levels:

**Level 1 — Parse validation:** textX grammar checks syntax. All constructs
must conform to `el_grammar.tx`.

**Level 2 — Semantic validation:** `el_validator.py` checks 15 rules against
ISO/IEC 15414:2015. Key rules exercised by the FHIR mapping:
- V-07: delegation from/to must be party or agent kind
- V-08: sub-delegation only if parent has `sub_delegation_allowed: true` (R13)
- V-10: commitment actor must be party or agent (R06)
- V-15: delegation obligation traces back to a CommitmentDecl (R12)

**Level 3 — Modal verification:** `el_kripke.py` verifies AF/EF properties.
For a consent obligation with `discharge_mode: strict` (generated by R07 when
consent keywords detected): AF(discharged) = ✓ SATISFIED.

---

## 5. Worked Example — AI Diagnostic Consent Scenario

### 5.1 FHIR Bundle Contents

`ai_diagnostic_bundle.json` contains:

| Resource | ID | Role |
|----------|----|------|
| Organization | gp-practice-001 | GP Practice (data controller) |
| Patient | patient-jane-smith | Patient (data subject) |
| Practitioner | gp-dr-chen | GP (ordering clinician) |
| Practitioner | specialist-dr-okonkwo | Specialist (Task owner → agent) |
| Device | ai-diagnostic-agent-001 | AI agent (Task owner → agent) |
| ServiceRequest | referral-sr-001 | Commitment root (R05) |
| Task | task-specialist-001 | First delegation hop (R09) |
| Task | task-ai-agent-001 | Sub-delegation (R09, R13) |
| Consent | consent-ai-diagnostic-001 | Authorization + permit + embargo (R16–R21) |

### 5.2 Generated Governance Structure

```
GpPractice001 (party)
  ├── principal_of SpecialistDrOkonkwo
  └── principal_of AiDiagnosticAgent001

SpecialistDrOkonkwo (agent)
  └── delegated_from GpPractice001

AiDiagnosticAgent001 (agent)
  └── delegated_from SpecialistDrOkonkwo

ReferralSr001Obligation (burden)
  discharge_mode: strict   ← consent keyword detected in ServiceRequest.note
  priority: critical

Delegation chain:
  GpPractice001 → SpecialistDrOkonkwo → AiDiagnosticAgent001
```

### 5.3 Layer 4 Verification Results

```
Obligation: ReferralSr001Obligation
Chain: GpPractice001 → SpecialistDrOkonkwo → AiDiagnosticAgent001
Holder: AiDiagnosticAgent001
Mode: strict   Priority: critical

AF (obligation): ✓ SATISFIED
  — AiDiagnosticAgent001 must discharge the obligation at the first
    available opportunity; no path exists where it is avoided.

EF (permission): ✓ SATISFIED
  — Discharge is achievable (witness: immediate discharge at step 0).

§C.4 Recommended action: discharge:ReferralSr001Obligation by AiDiagnosticAgent001
  Expected future utility: +1.000
```

---

## 6. Governance Gap Analysis (from Table 2 — position paper)

This mapping closes the following gaps identified in Table 2:

| Gap | How the mapping addresses it |
|-----|------------------------------|
| No formal record that the seeker was obligated | R07: ServiceRequest.note → burden token with obligation text |
| Cannot trace why a second party has access | R09–R13: Task chain → DelegationDecl chain with provenance |
| Cannot answer: who is ultimately responsible? | R06 + R12: ServiceRequest.requester + Task.basedOn → root party |
| FHIR records withdrawal; ODP-EL propagates it | R22: Consent.status=inactive → DeclarationDecl |
| Consent is a state change, not a traceable act | R18: Consent creation → AuthorizationDecl (formal speech act) |

---

## 7. Files

| File | Description |
|------|-------------|
| `fhir_mapper.py` | Python mapper implementing R01–R22 |
| `ai_diagnostic_bundle.json` | Sample FHIR R4 Bundle (AI diagnostic consent scenario) |
| `generated_governance.el` | Generated DSL-EL spec (mapper output) |
| `fhir_mapping_table.md` | This document |

---

## 8. Next Steps

1. **Bidirectional mapping:** when a DSL-EL speech act is performed (e.g.,
   delegation revoked), update the corresponding FHIR resource. This is the
   full Mediator component from the EDOC 2024 paper.

2. **AuditEvent → ledger (R32):** map FHIR AuditEvent to governance ledger
   entries once the governance ledger module is built.

3. **HL7 Australia eRequesting:** apply the mapping to the eRequesting FHIR
   profile — `ServiceRequest` for pathology/radiology orders, `Task` for
   laboratory fulfilment, `DiagnosticReport` as the output. The governance
   question is the same: who is accountable for the delegation chain?

4. **FHIR R5 extensions:** FHIR R5 Consent adds `policyBasis` and refined
   `provision` structures. Map these to DSL-EL policy declarations.
