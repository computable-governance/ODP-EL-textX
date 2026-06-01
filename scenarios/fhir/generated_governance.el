/*
 * Generated governance specification
 * Source: FHIR Bundle/ai-diagnostic-governance-bundle-001
 * Generator: fhir_mapper.py (ComputableGovernance toolchain)
 * Mapping rules applied: R01, R02, R03, R04, R05, R07, R09, R16, R17, R18
 *
 * This file is machine-generated. Do not edit manually.
 * Re-generate by running: python fhir_mapper.py
 */

enterprise specification AiDiagnosticGovernanceBundle001GovernanceSpec
    description: "Generated from FHIR Bundle/ai-diagnostic-governance-bundle-001"
    field_of_application: "Clinical AI governance — FHIR-sourced"
    scope: "Consent, delegation, and authorization governance for AI-assisted clinical workflows"

// ── Parties and Agents ──────────────────────────────────────
party GpPractice001
    description: "[R01] Data controller: Northside GP Practice"
    {
        principal_of SpecialistDrOkonkwo
    }

party PatientJaneSmith
    description: "[R02] Data subject (patient): Jane Smith"

party GpDrChen
    description: "[R03] Party: Dr Wei Chen (General practitioner)"

agent SpecialistDrOkonkwo
    description: "[R03] Agent: Dr Chidi Okonkwo (Radiologist)"
    {
        delegated_from GpPractice001
        principal_of AiDiagnosticAgent001
    }

agent AiDiagnosticAgent001
    description: "[R04] AI agent: AI Diagnostic Analysis System"
    {
        delegated_from SpecialistDrOkonkwo
    }

// ── Deontic Tokens ─────────────────────────────────────────
burden ReferralSr001Obligation {
    for_action: "imaging"
    state: active
    deadline: "2026-05-20"
    discharge_mode: strict
    priority: critical
    description: "[R07] Obligation arising from ServiceRequest/referral-sr-001"
}

permit ConsentAiDiagnostic001Permit {
    for_action: "access"
    state: active
    deadline: "by 2026-05-20"
    description: "[R16] Permit from Consent/consent-ai-diagnostic-001"
}

embargo ConsentAiDiagnostic001SubProv2Embargo {
    for_action: "disclose"
    state: active
    description: "[R17] Sub-provision from Consent/consent-ai-diagnostic-001"
}

// ── Community (generated) ───────────────────────────────────
community AiDiagnosticGovernanceBundle001Community
    description: "Generated governance community for AiDiagnosticGovernanceBundle001"
    {
        objective: "Seek informed patient consent before AI diagnostic analysis. GP practice is ultimately accountable for consent chain."

        contract {
            invariant consentBeforeAnalysis:
                "AI diagnostic analysis must not proceed without documented patient consent"
            assignment_policy for specialistDrOkonkwoRole {
                requires_capability: "Must hold delegated obligation"
                requires_token burden: "Must hold ReferralSr001Obligation"
            }
            assignment_policy for aiDiagnosticAgent001Role {
                requires_capability: "Must hold delegated obligation"
                requires_token burden: "Must hold ReferralSr001Obligation"
            }
        }
        role specialistDrOkonkwoRole
            description: "Role for SpecialistDrOkonkwo"
            {}
        role aiDiagnosticAgent001Role
            description: "Role for AiDiagnosticAgent001"
            {}
    }

// ── Commitments ────────────────────────────────────────────
commitment ReferralSr001Commitment {
    by: GpPractice001
    obligation: "Seek informed patient consent before AI diagnostic analysis. GP practice is ultimately accountable for consent chain."
    creates_burden: ReferralSr001Obligation
    description: "[R05] Commitment from ServiceRequest/referral-sr-001"
}

// ── Delegations ────────────────────────────────────────────
delegation TaskSpecialist001Delegation {
    from: GpPractice001
    to: SpecialistDrOkonkwo
    obligation: "Seek informed patient consent before AI diagnostic analysis. GP practice is ultimately accountable for consent chain."
    transfers_burden: ReferralSr001Obligation
    creates_reporting_burden: true
    duration: "2026-05-20T17:00:00Z"
    sub_delegation_allowed: true
    revocable: true
    description: "[R09] Delegation from Task/task-specialist-001 (status=requested). Specialist accepts referral and oversees AI diagnostic process"
}

delegation TaskAiAgent001Delegation {
    from: SpecialistDrOkonkwo
    to: AiDiagnosticAgent001
    obligation: "Seek informed patient consent before AI diagnostic analysis. GP practice is ultimately accountable for consent chain."
    transfers_burden: ReferralSr001Obligation
    creates_reporting_burden: true
    duration: "2026-05-20T17:00:00Z"
    revocable: true
    description: "[R09] Delegation from Task/task-ai-agent-001 (status=requested). AI agent performs diagnostic analysis — must seek informed consent before proceeding"
}

// ── Authorizations ─────────────────────────────────────────
authorization ConsentAiDiagnostic001Auth {
    authority: GpPractice001
    to_agent: SpecialistDrOkonkwo
    grants_permit: ConsentAiDiagnostic001Permit
    duration: "by 2026-05-20"
    revocable: true
    description: "[R18] Authorization from Consent/consent-ai-diagnostic-001"
}


/*
 * Mapping provenance — FHIR resource → DSL-EL construct
 *
 * [R01] Organization/gp-practice-001                  → GpPractice001  (party (data controller))
 * [R02] Patient/patient-jane-smith                    → PatientJaneSmith  (party (data subject))
 * [R03] Practitioner/gp-dr-chen                       → GpDrChen  (party or agent (role-dependent))
 * [R03] Practitioner/specialist-dr-okonkwo            → SpecialistDrOkonkwo  (party or agent (role-dependent))
 * [R04] Device/ai-diagnostic-agent-001                → AiDiagnosticAgent001  (agent (AI system))
 * [R07] ServiceRequest/referral-sr-001                → ReferralSr001Obligation  (obligation text + burden token)
 * [R05] ServiceRequest/referral-sr-001                → ReferralSr001Commitment  (CommitmentDecl)
 * [R09] Task/task-specialist-001                      → TaskSpecialist001Delegation  (DelegationDecl)
 * [R09] Task/task-ai-agent-001                        → TaskAiAgent001Delegation  (DelegationDecl)
 * [R16] Consent/consent-ai-diagnostic-001             → ConsentAiDiagnostic001Permit  (permit token + AuthorizationDecl)
 * [R17] Consent/consent-ai-diagnostic-001             → ConsentAiDiagnostic001SubProv2Embargo  (embargo token)
 * [R18] Consent/consent-ai-diagnostic-001             → ConsentAiDiagnostic001Auth  (AuthorizationDecl)
 */