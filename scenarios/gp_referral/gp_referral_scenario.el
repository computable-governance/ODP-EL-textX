/*
 * ================================================================
 * gp_referral_scenario.el
 * ODP Enterprise Language DSL — GP-to-specialist referral governance
 *
 * Scenario: Federated multi-party referral governance spanning two
 * autonomous healthcare communities.
 *
 * Delegation chain (cross-community):
 *   GPPracticeParty ──[delegates referralResponseBurden]──► SpecialistClinicianAgent
 *   GPPracticeParty ──[authorizes patient data access]──► SpecialistClinicianAgent
 *
 * Token groups:
 *   referralBurdenGroup   = { referralInitiationBurden, clinicalHandoverBurden,
 *                             referralResponseBurden, assessmentSchedulingBurden }
 *   specialistBurdenGroup = { referralResponseBurden, assessmentSchedulingBurden }
 *
 * Federation:
 *   ReferralFederation = { GPPracticeCommunity, SpecialistCommunity }
 *   Federation objective: all_discharged(referralBurdenGroup)
 *   Specialist community objective: any_discharged(specialistBurdenGroup)
 *     → demonstrates both SatisfactionOp variants (AM-27)
 *
 * Layer 4 verification questions (el_kripke.py):
 *   Q1: AF(discharged:referralInitiationBurden)?
 *       YES — discharge_mode: strict; GP must act at first opportunity.
 *   Q2: AF(discharged:referralResponseBurden)?
 *       NO  — discharge_mode: eventual; specialist may delay indefinitely.
 *       EF(discharged:referralResponseBurden) holds (some path discharges it).
 *       FIX: change referralResponseBurden to discharge_mode: strict → AF holds.
 *   Q3: objective_satisfied:ReferralFederation?
 *       EF only (blocked by eventual referralResponseBurden).
 *       Requires strict on referralResponseBurden for AF to hold.
 *   Q4: objective_satisfied:SpecialistCommunity?
 *       EF — any_discharged(specialistBurdenGroup) satisfied when at least
 *       one specialist burden is discharged on some path.
 *
 * EF ≠ AF formal finding applies to cross-community delegation:
 *   delegation creates permission for the specialist to respond (EF),
 *   but without discharge_mode: strict the GP cannot guarantee the
 *   specialist will respond on every possible path (AF not guaranteed).
 *
 * ViolationResponse:
 *   If referralResponseBurden is violated (specialist does not respond),
 *   SpecialistParty must escalate and notify GPPracticeParty.
 *
 * Token state cascade (runtime — Layer 3 / Layer 4):
 *   On delegation: referralResponseBurden → PENDING on delegator,
 *                  ACTIVE on delegate.
 *   On violation:  referralResponseBurden → VIOLATED;
 *                  escalationNoticeBurden → ACTIVE on SpecialistParty.
 * ================================================================
 */

enterprise specification GPReferralGovernanceSystem
    description: "Multi-party specialist referral governance across GP and specialist communities"
    field_of_application: "Primary and specialist care coordination in a federated healthcare context"
    scope: "Referral obligation management across GPPracticeCommunity and SpecialistCommunity federation"


// ================================================================
// §6.6.1, §6.6.8, §7.4 — PARTIES AND AGENTS
// ================================================================

party GPPracticeParty
    description: "General practice — root principal; ultimately accountable for referral initiation and outcome"
    {
        principal_of GPClinician
    }

agent GPClinician
    description: "GP clinician agent — delegated to initiate referral and provide clinical handover"
    {
        holds referralInitiationBurden
        holds clinicalHandoverBurden
        delegated_from GPPracticeParty
            duration: "referral episode"
    }

party SpecialistParty
    description: "Specialist practice — autonomous community party; accountable for referral response"
    {
        principal_of SpecialistClinicianAgent
    }

agent SpecialistClinicianAgent
    description: "Specialist clinician agent — receives cross-community delegation; responds to and processes referral"
    {
        holds patientRecordAccessPermit
        delegated_from SpecialistParty
            duration: "referral episode"
    }

artefact_object patientRecord
    description: "Patient clinical record — referenced by referral initiation and clinical handover actions"


// ================================================================
// §6.4, §7.8.7 — DEONTIC TOKENS
// ================================================================

// discharge_mode: strict — GP must initiate promptly; AF(discharged:referralInitiationBurden) holds.
burden referralInitiationBurden {
    for_action: "initiate_specialist_referral"
    state: active
    deadline: "48 hours from clinical decision"
    discharge_mode: strict
    priority: critical
    description: "Obligation on GP clinician to initiate and transmit specialist referral for the patient"
}

// discharge_mode: eventual — GP may delay handover; AF does not hold for clinicalHandoverBurden.
// Priority: normal — lower utility weight in Bellman planner (§C.3).
burden clinicalHandoverBurden {
    for_action: "provide_clinical_handover"
    state: active
    deadline: "referral episode"
    discharge_mode: eventual
    priority: normal
    description: "Obligation on GP clinician to provide complete clinical handover documentation to specialist"
}

// discharge_mode: eventual — specialist may delay response; EF holds but AF does not.
// This is the key Kripke verification target for the cross-community delegation.
// Change to discharge_mode: strict to restore AF(discharged:referralResponseBurden).
burden referralResponseBurden {
    for_action: "acknowledge_and_respond_to_referral"
    state: active
    deadline: "5 working days from referral receipt"
    discharge_mode: eventual
    priority: high
    description: "Obligation on specialist clinician to acknowledge and respond to the GP referral"
}

// discharge_mode: eventual — scheduling follows acknowledgement; demonstrates EF ≠ AF for secondary obligation.
burden assessmentSchedulingBurden {
    for_action: "schedule_specialist_assessment"
    state: active
    deadline: "14 days from referral receipt"
    discharge_mode: eventual
    priority: normal
    description: "Obligation on specialist clinician to schedule an assessment appointment for the referred patient"
}

// Created on violation of referralResponseBurden; SpecialistParty must discharge this promptly.
// discharge_mode: strict — escalation must happen at first opportunity once violation detected.
burden escalationNoticeBurden {
    for_action: "notify_gp_of_non_response"
    state: active
    deadline: "48 hours from violation detection"
    discharge_mode: strict
    priority: critical
    description: "Obligation on specialist party to notify GP practice of failure to respond to referral"
}

// Granted by GPPracticeParty to SpecialistClinicianAgent via Authorization (§7.10.2).
permit patientRecordAccessPermit {
    for_action: "access_patient_clinical_records"
    state: active
    description: "Permission for specialist clinician to access patient records for referral assessment"
}


// ================================================================
// §6.4.2, AM-26 — TOKEN GROUPS
// ================================================================

// Federation-level group: all four referral burdens must be discharged
// for ReferralFederation's objective to be satisfied (all_discharged).
token_group referralBurdenGroup {
    member: referralInitiationBurden
    member: clinicalHandoverBurden
    member: referralResponseBurden
    member: assessmentSchedulingBurden
}

// Specialist-community group: objective satisfied when any_discharged.
// Demonstrates the any_discharged operator (AM-27) — specialist shows
// governance progress as soon as one specialist burden is discharged.
token_group specialistBurdenGroup {
    member: referralResponseBurden
    member: assessmentSchedulingBurden
}


// ================================================================
// §6.5, §7.9 — REFERRAL TIMELINESS POLICY
// ================================================================

policy referralTimelinessPolicy : duration {
    description: "Maximum timeframe for specialist to acknowledge a GP referral"
    initial_value: 5 day
    envelope {
        one of [1 day, 2 day, 5 day, 10 day]
    }
    obligation on specialistRole: "Must acknowledge referral within the policy timeframe"
    affects role specialistRole
    setting_behaviour {
        description: "Referral response window agreed at federation governance level"
        who_can_change: "ReferralFederation governance board"
        negotiation_required: true
    }
    enforcement policed pessimistic
        mechanism: "Automated referral tracking system raises alert on breach"
}


// ================================================================
// §7.5.1 — PATIENT DATA DOMAIN
// ================================================================

domain PatientDataDomain
    characterized_by: "Data controller-processor relationship"
    description: "Domain governing access to and processing of patient clinical records"
    {
        controlling_object: GPPracticeParty
        controlled_object: GPClinician
        controlled_object: SpecialistClinicianAgent
    }


// ================================================================
// §6.2, §7.3 — GP PRACTICE COMMUNITY
// ================================================================

community GPPracticeCommunity
    description: "Community governing referral initiation and clinical handover by the GP practice"
    {
        objective: "Initiate specialist referral and provide complete clinical handover for the patient"
            sub_objective initiateReferralTask: "Initiate and transmit specialist referral"
                assigned_to role gpClinicianRole
            sub_objective documentHandoverTask: "Provide complete clinical handover documentation to specialist"
                assigned_to role gpClinicianRole

        invariant referralAuthorityMandatory:
            "GP clinician must hold referralInitiationBurden before a referral may be submitted"
        invariant handoverCompleteness:
            "Clinical handover must include patient history, current medications, and referral indication"

        assignment_policy for gpClinicianRole {
            requires_capability: "Must hold current GP registration and referral prescribing authority"
            requires_token burden: "Must hold referralInitiationBurden"
        }

        on_join gpClinicianRole transfer referralInitiationBurden
        on_join gpClinicianRole transfer clinicalHandoverBurden
        on_leave gpClinicianRole revert referralInitiationBurden
        on_leave gpClinicianRole revert clinicalHandoverBurden

        role gpClinicianRole
            description: "GP clinician role — initiates referral and provides clinical handover to specialist"
            {
                action initiateReferral {
                    description: "GP clinician initiates and transmits specialist referral for the patient"
                    actor: gpClinicianRole
                    artefact: patientRecord
                    precondition: "Patient must have an active episode of care and clinical indication for referral"
                    favoured_by_burden referralInitiationBurden
                    effect create referralResponseBurden to specialistRole
                    effect create assessmentSchedulingBurden to specialistRole
                }

                action provideHandover {
                    description: "GP clinician provides clinical handover documentation to specialist"
                    actor: gpClinicianRole
                    artefact: patientRecord
                    precondition: "Referral must be active and acknowledged by specialist"
                    favoured_by_burden clinicalHandoverBurden
                }
            }

        interaction with SpecialistCommunity {
            applies referralTimelinessPolicy to role specialistRole
            invariant crossCommunityReferralCompliance:
                "Referral obligations and response timeframes span both GP and specialist communities"
            description: "GP practice interacts with specialist community for referral management and patient handover"
        }

        lifecycle {
            establishing {
                implicit: true
                description: "GP practice community is pre-existing; referral episode triggers governance activation"
            }
            terminating {
                on_objective_achieved: true
                description: "GP practice referral obligations concluded when all GP burdens are discharged"
            }
        }
    }


// ================================================================
// §6.2, §7.3 — SPECIALIST COMMUNITY
// ================================================================

community SpecialistCommunity
    description: "Community governing specialist response, scheduling, and assessment of referred patients"
    {
        objective: "Process referral and schedule specialist assessment within the required timeframe"
            satisfaction: any_discharged(specialistBurdenGroup)
            sub_objective acknowledgeReferralTask: "Acknowledge receipt of referral from GP practice"
                assigned_to role specialistRole
            sub_objective scheduleAssessmentTask: "Schedule specialist assessment appointment for the patient"
                assigned_to role specialistRole

        invariant referralAcknowledgementMandatory:
            "Every received referral must be acknowledged or formally rejected within the policy timeframe"
        invariant assessmentQualityStandard:
            "Specialist assessment must be conducted by a registered specialist in the relevant clinical area"

        assignment_policy for specialistRole {
            requires_capability: "Must hold current specialist registration in the relevant clinical area"
            requires_token permit: "Must hold patientRecordAccessPermit"
        }

        on_join specialistRole transfer patientRecordAccessPermit
        on_leave specialistRole revert patientRecordAccessPermit

        role specialistRole
            description: "Specialist clinician role — responds to referrals and schedules assessments"
            {
                holds patientRecordAccessPermit

                action acknowledgeReferral {
                    description: "Specialist clinician acknowledges receipt of GP referral and initiates clinical review"
                    actor: specialistRole
                    artefact: patientRecord
                    requires_permit patientRecordAccessPermit for specialistRole
                    favoured_by_burden referralResponseBurden
                }

                action scheduleAssessment {
                    description: "Specialist clinician schedules patient assessment appointment"
                    actor: specialistRole
                    precondition: "Referral must be acknowledged and patient availability confirmed"
                    requires_permit patientRecordAccessPermit for specialistRole
                    favoured_by_burden assessmentSchedulingBurden
                }
            }

        interaction with GPPracticeCommunity {
            applies referralTimelinessPolicy to role gpClinicianRole
            description: "Specialist community interacts with GP practice for referral receipt and clinical handover"
        }

        lifecycle {
            establishing {
                implicit: true
                description: "Specialist community is pre-existing; activated upon referral receipt from GP practice"
            }
            changes {
                membership_dynamic: true
                description: "Specialist role may be filled by different clinicians across the referral episode"
            }
            terminating {
                on_objective_achieved: true
                description: "Specialist community obligations concluded when specialist burdens are discharged"
            }
        }
    }


// ================================================================
// §7.5.2 — REFERRAL FEDERATION
// ================================================================

federation ReferralFederation
    description: "Federation of GPPracticeCommunity and SpecialistCommunity for coordinated referral governance"
    {
        objective: "Ensure complete specialist assessment for the referred patient"
            satisfaction: all_discharged(referralBurdenGroup)
            sub_objective federationReferralCompletion: "All referral burdens across both member communities discharged"

        shared_objective: "Achieve timely, high-quality specialist assessment of referred patients while preserving community autonomy"

        member: GPPracticeCommunity
        member: SpecialistCommunity

        invariant federationDataProtection:
            "Patient data shared across community boundaries must comply with data protection obligations"
        invariant federationReferralContinuity:
            "Referral governance continuity must be maintained throughout the referral episode"

        withdrawal_behaviour: "Either community may withdraw upon community dissolution; outstanding burdens revert to federation root principal"

        conflict_resolution runtime_resolution
            description: "Policy conflicts between GP and specialist communities resolved at runtime through federation-level negotiation"
    }


// ================================================================
// §6.6, §7.10 — ACCOUNTABILITY CHAIN
// ================================================================

// Root commitment — GPPracticeParty is ultimately accountable for referral initiation
commitment referralCommitment {
    by: GPPracticeParty
    obligation: "Initiate specialist referral and provide clinical handover for the patient"
    creates_burden: referralInitiationBurden
    description: "GP practice commits to initiating a specialist referral and providing complete clinical handover"
}

// Second commitment root — GPPracticeParty is also accountable for ensuring the referral is responded to.
// This roots the cross-community delegation chain: GP bears ultimate accountability
// even though the burden is transferred to SpecialistClinicianAgent.
commitment referralResponseCommitment {
    by: GPPracticeParty
    obligation: "Respond to the specialist referral within the agreed timeframe and schedule assessment"
    creates_burden: referralResponseBurden
    description: "GP practice commits to ensuring specialist responds to the referral and schedules assessment"
}

// Third commitment — GPPracticeParty is accountable for clinical handover to the specialist.
commitment clinicalHandoverCommitment {
    by: GPPracticeParty
    obligation: "Provide complete clinical handover documentation to specialist"
    creates_burden: clinicalHandoverBurden
    description: "GP practice commits to providing complete clinical handover documentation to the specialist"
}

// Fourth commitment — SpecialistParty is accountable for scheduling a specialist assessment.
commitment assessmentSchedulingCommitment {
    by: SpecialistParty
    obligation: "Schedule specialist assessment appointment for the patient"
    creates_burden: assessmentSchedulingBurden
    description: "Specialist party commits to scheduling a specialist assessment appointment for the referred patient"
}

// Cross-community delegation — GP practice delegates referral response to specialist clinician.
// §7.10.1: SpecialistClinicianAgent becomes accountable for referralResponseBurden;
// GPPracticeParty retains ultimate accountability for the referral outcome.
// This is the cross-community delegation that makes EF(discharged:referralResponseBurden) hold;
// AF does not hold because discharge_mode: eventual allows the specialist to delay.
delegation gpToSpecialistDelegation {
    from: GPPracticeParty
    to: SpecialistClinicianAgent
    obligation: "Respond to the specialist referral within the agreed timeframe and schedule assessment"
    transfers_burden: referralResponseBurden
    transfers_token_group: referralBurdenGroup
    creates_reporting_burden: true
    duration: "referral episode"
    conditions: "Active GP referral transmitted and received by specialist community"
    sub_delegation_allowed: true
    revocable: true
    description: "GP practice delegates referral response and scheduling obligations to specialist clinician across community boundary"
}

// Authorization — GPPracticeParty grants patient data access to SpecialistClinicianAgent.
// §7.10.2: empowerment that enables the specialist to fulfill the delegated obligation.
authorization patientDataAuthorization {
    authority: GPPracticeParty
    to_agent: SpecialistClinicianAgent
    grants_permit: patientRecordAccessPermit
    duration: "referral episode"
    conditions: "Active GP referral and patient data sharing consent on file"
    revocable: true
    domain_scope: "PatientDataDomain"
    description: "GP practice authorizes specialist clinician to access patient records for referral assessment"
}


// ================================================================
// §6.3.8, §7.8.6 — VIOLATION RESPONSE
// ================================================================

// If specialist does not respond to referral within deadline:
// SpecialistParty (as principal of SpecialistClinicianAgent) is obligated to
// escalate and notify GPPracticeParty; escalationNoticeBurden is created.
violation_response referralNoResponseViolation {
    on_violation_of: referralResponseBurden
    obligates: SpecialistParty
    response_kind: escalate
    creates_burden: escalationNoticeBurden
    escalate_to: GPPracticeParty
    description: "If specialist fails to respond to referral, specialist party must escalate and notify GP practice"
}


// ================================================================
// §6.6.3, §7.10.5 — PRESCRIPTION
// ================================================================

prescription referralResponseStandard {
    by: GPPracticeParty
    establishes_rule: "Specialist must acknowledge referral within 5 working days and schedule assessment within 14 days"
    creates_oversight_burden: true
    description: "GP practice prescribes the standard referral response and scheduling timeframe for the federation"
}


// ================================================================
// §6.6.5, §7.10.4 — DECLARATION
// ================================================================

// Specialist declares referral acceptance; effective upon interaction with GP practice.
// requires_permit enforces that declaration is only valid when the specialist holds the permit.
declaration referralAccepted {
    by: SpecialistClinicianAgent
    state_of_affairs: "Specialist referral has been accepted and is under clinical review"
    requires_permit: patientRecordAccessPermit
    effective_on_interaction: true
    description: "Specialist clinician declares referral acceptance; effective on interaction with GP practice"
}


// ================================================================
// §6.6.7 — EVALUATION
// ================================================================

evaluation referralOutcomeEvaluation {
    by: GPPracticeParty
    of_target: "referral episode governance compliance"
    result: "All referral burdens discharged within policy timeframes; federation objective satisfied"
    description: "GP practice evaluates overall governance compliance of the referral episode"
}


// ================================================================
// §11 — VIEWPOINT CORRESPONDENCES
// ================================================================

correspondence ReferralFederation          to computational : ReferralFederationService
correspondence GPPracticeCommunity         to computational : GPPracticeService
correspondence SpecialistCommunity         to computational : SpecialistService
correspondence GPPracticeParty             to computational : GPPracticeClientObject
correspondence SpecialistParty             to computational : SpecialistServerObject
correspondence GPClinician                 to engineering   : GPClinicianNode
correspondence SpecialistClinicianAgent    to engineering   : SpecialistAgentNode
correspondence patientRecord               to information   : PatientClinicalRecord
correspondence referralInitiationBurden    to information   : ReferralInitiationRecord
correspondence referralResponseBurden      to information   : ReferralResponseRecord
correspondence clinicalHandoverBurden      to information   : ClinicalHandoverRecord
correspondence patientRecordAccessPermit   to information   : DataAccessGrantRecord
correspondence referralBurdenGroup         to information   : ReferralBurdenGroupRecord
