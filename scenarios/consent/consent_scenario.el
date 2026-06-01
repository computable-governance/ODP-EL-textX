/*
 * ================================================================
 * consent_scenario.el
 * ODP Enterprise Language DSL — consent governance scenario
 *
 * Scenario: Digital health consent for AI diagnostic analysis
 * (Position paper §6.4 validation case)
 *
 * Delegation chain:
 *   GPPracticeParty → SpecialistAgent → AIDiagnosticAgent
 *
 * Obligation: seekConsentObligation
 *   discharge_mode: strict   ← AM-13
 *
 * Layer 4 verification question:
 *   Does AF(discharged:seekConsentObligation) hold?
 *
 * Expected answer with discharge_mode: strict  → YES (AF satisfied)
 * Expected answer with discharge_mode: eventual → NO  (AF not satisfied)
 *
 * The difference captures the formal meaning of "must" vs "may":
 *   strict   = the holder is obliged to discharge at the first opportunity
 *   eventual = the holder may delay (only EF is guaranteed)
 * ================================================================
 */

enterprise specification ConsentGovernanceSystem
    description: "Digital health consent governance for AI diagnostic agents"
    field_of_application: "Clinical AI systems requiring informed patient consent"
    scope: "Consent obligation management across GP, specialist, and AI agent chain"


// ================================================================
// §6.6.1 / §6.6.8 — PARTIES AND AGENTS
// ================================================================

party GPPracticeParty
    description: "General practice — root principal; ultimately accountable for consent"
    {
        principal_of SpecialistAgent
    }

agent SpecialistAgent
    description: "Specialist who sub-delegates consent obligation to AI diagnostic agent"
    {
        delegated_from GPPracticeParty
            duration: "referral period"
        principal_of AIDiagnosticAgent
    }

agent AIDiagnosticAgent
    description: "AI agent performing diagnostic analysis; must seek consent before analysis"
    {
        delegated_from SpecialistAgent
            duration: "clinical session"
    }


// ================================================================
// §6.4 — DEONTIC TOKENS
// ================================================================

// AM-13: discharge_mode: strict
// AM-15: priority: critical — highest weight in utility function
// This tells Layer 4 (el_kripke.py) to suppress the TICK transition
// when this obligation is pending — the holder must act immediately.
// AF(discharged:seekConsentObligation) will hold.
burden seekConsentObligation {
    for_action: "seek_patient_consent"
    state: active
    deadline: "clinical session"
    discharge_mode: strict
    priority: critical
    description: "Obligation to seek informed patient consent before AI diagnostic analysis"
}

// AM-15: priority: low — minimal weight in utility function
// Discharge mode is eventual — reporting may be delayed (AF will not hold).
// Demonstrates §C.3 weighted utility: a world where consent is DISCHARGED
// and reporting is VIOLATED scores higher than the reverse.
burden reportingObligation {
    for_action: "submit_consent_report"
    state: active
    deadline: "end of session"
    discharge_mode: eventual
    priority: low
    description: "Obligation to submit a consent and analysis report after the session"
}

permit aiAnalysisPermit {
    for_action: "perform_ai_diagnostic_analysis"
    state: active
    description: "Permission to perform AI diagnostic analysis — requires prior consent"
}


// ================================================================
// §6.2, §7.3 — CONSENT COMMUNITY
// ================================================================

community ConsentCommunity
    description: "Community governing consent for AI-assisted clinical diagnosis"
    {
        objective: "Ensure informed consent is obtained before AI diagnostic analysis"
            sub_objective verify_consent_scope: "Verify patient understands scope of AI analysis"
                assigned_to role specialistRole
            sub_objective obtain_consent: "Obtain documented patient consent"
                assigned_to role aiAgentRole

        contract {
            invariant consentBeforeAnalysis:
                "AI diagnostic analysis must not proceed without documented patient consent"
            invariant consentDocumented:
                "Every consent interaction must be recorded in the patient record"

            assignment_policy for aiAgentRole {
                requires_capability: "Must hold a valid clinical AI certification"
                requires_token burden: "Must hold seekConsentObligation"
            }
        }

        role gpRole
            description: "GP role — coordinates the referral and consent process"
            {
                action initiateReferral {
                    description: "GP initiates specialist referral including consent delegation"
                    actor: gpRole
                    precondition: "Patient must have a current episode of care"
                    effect create seekConsentObligation to specialistRole
                }
            }

        role specialistRole
            description: "Specialist role — oversees AI diagnostic process and consent chain"
            {
                action reviewConsentScope {
                    description: "Specialist reviews and approves consent scope for AI analysis"
                    actor: specialistRole
                    precondition: "GP referral must be active"
                }
            }

        role aiAgentRole
            description: "AI agent role — must seek consent before performing analysis"
            {
                action seekConsent {
                    description: "AI agent seeks and records informed patient consent"
                    actor: aiAgentRole
                    precondition: "Patient must be contactable"
                    requires_permit aiAnalysisPermit for aiAgentRole
                }

                action performAnalysis {
                    description: "AI agent performs diagnostic analysis after consent obtained"
                    actor: aiAgentRole
                    requires_permit aiAnalysisPermit for aiAgentRole
                    precondition: "seekConsentObligation must be discharged"
                }
            }
    }


// ================================================================
// §6.6 / §7.10 — ACCOUNTABILITY CHAIN
// ================================================================

// Root commitment — GPPracticeParty is ultimately accountable
commitment consentCommitment {
    by: GPPracticeParty
    obligation: "Seek informed patient consent before AI diagnostic analysis"
    creates_burden: seekConsentObligation
    description: "GP practice commits to ensuring informed consent is obtained for AI analysis"
}

// Reporting commitment — GPPracticeParty also commits to session reporting
// priority: low on the burden; demonstrates §C.3 weighted utility
commitment reportingCommitment {
    by: GPPracticeParty
    obligation: "Submit consent and analysis report after AI diagnostic session"
    creates_burden: reportingObligation
    description: "GP practice commits to submitting a post-session report on consent and analysis"
}

// Delegation: GP → Specialist (sub-delegation allowed per §7.10.1)
delegation gpToSpecialistDelegation {
    from: GPPracticeParty
    to: SpecialistAgent
    obligation: "Seek informed patient consent before AI diagnostic analysis"
    transfers_burden: seekConsentObligation
    creates_reporting_burden: true
    duration: "referral period"
    conditions: "Active GP referral required"
    sub_delegation_allowed: true
    revocable: true
    description: "GP delegates consent responsibility to specialist; specialist reports back"
}

// Delegation: Specialist → AI Agent (sub-delegation of the obligation)
delegation specialistToAIDelegation {
    from: SpecialistAgent
    to: AIDiagnosticAgent
    obligation: "Seek informed patient consent before AI diagnostic analysis"
    transfers_burden: seekConsentObligation
    creates_reporting_burden: true
    duration: "clinical session"
    conditions: "Active specialist oversight required"
    revocable: true
    description: "Specialist sub-delegates consent obligation to AI agent for this session"
}


// ================================================================
// §11 — VIEWPOINT CORRESPONDENCES
// ================================================================

correspondence ConsentCommunity      to computational : ConsentService
correspondence GPPracticeParty       to computational : GPClientObject
correspondence SpecialistAgent       to computational : SpecialistServerObject
correspondence AIDiagnosticAgent     to engineering   : AIAgentNode
correspondence seekConsentObligation to information   : ConsentObligationRecord
correspondence reportingObligation   to information   : ReportingObligationRecord
correspondence aiAnalysisPermit      to information   : ConsentGrantRecord
