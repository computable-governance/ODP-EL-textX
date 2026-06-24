// eReferral enterprise model
// Developed during Forum paper session, June 2026
// Combines two Introduction-style domains and a Creation-style episode community
// Supports both governance (compelled/AF) and coordination (detectable/EF) readings
// Design decisions documented in coordination_design_note_v3.md §13.5, §13.6

enterprise specification eReferralGovernanceSystem
    description: "eReferral governance: GP-to-specialist referral accountability"
    field_of_application: "Primary and specialist care referral pathways"
    scope: "Accountability and deontic governance for a single referral episode"

// ── Enterprise Objects ──────────────────────────────────────────────────────

party GPPractice
    description: "GP practice -- HPI-O registered legal entity"

party GPClinician
    description: "GP clinician -- HPI-I registered; accountable party in own right; agent of GP practice"
    {
        delegated_from GPPractice
            duration: "ongoing practice membership"
    }

party SpecialistPractice
    description: "Specialist practice -- HPI-O registered legal entity"

party SpecialistClinician
    description: "Specialist clinician -- HPI-I registered; accountable party in own right; organisationally controlled by SpecialistPractice"

agent SpecialistAIAgent
    description: "AI diagnostic assistant; no standing delegation relationship until activated within an episode community"

// ── Deontic Tokens for Referral Episode ────────────────────────────────────
// discharge_mode is a toolchain extension (AM-13), not ISO/IEC 15414.
// strict  -> AF holds (compelled): violation state unreachable
// eventual -> EF only (detectable): violation observable after the fact

burden referralBurden {
    for_action: "submitReferral"
    state: active
    discharge_mode: strict
    description: "Obligation on referringClinicianRole to submit referral; AF holds by construction"
}

burden examinationBurden {
    state: pending
    discharge_mode: eventual
    description: "Obligation on referredToSpecialistRole; EF holds, AF may not"
}

burden aiExaminationBurden {
    for_action: "conductAIExamination"
    state: pending
    discharge_mode: eventual
    description: "Obligation on aiExaminationRole; EF holds, AF may not"
}

// ── Permit and Artefact ────────────────────────────────────────────────────
// patientRecordAccessPermit: granted to aiExaminationRole on_join (§7.8.7).
// discharge_mode does not apply to permits (AM-13 applies to burdens only).

permit patientRecordAccessPermit {
    for_action: "access_patient_clinical_records"
    state: active
    description: "Permission for AI agent to access patient records for examination"
}

artefact_object patientRecord
    description: "Patient clinical record — referenced by referral and examination actions"

// ── Token Group ────────────────────────────────────────────────────────────
// Groups all three episode burdens for objective satisfaction checking.
// all_discharged: episode objective met only when every burden is discharged.

token_group episodeBurdenGroup {
    member: referralBurden
    member: examinationBurden
    member: aiExaminationBurden
}

// ── Organisational Domains (Introduction-style, durable) ───────────────────
// Per §7.5: domain is a lightweight community expressing structural
// accountability boundary only -- no objective, role, or lifecycle.
// Per §7.8.8.2-3: domain is the unit of authorization scope for
// permit and embargo (not burden -- see §13.5).

domain GPPracticeDomain
    characterized_by: "Organisational accountability boundary; implicit authorization established at domain formation"
    {
        controlling_object: GPPractice
        controlled_object:  GPClinician
    }

domain SpecialistPracticeDomain
    characterized_by: "Organisational accountability boundary; implicit authorization established at domain formation"
    {
        controlling_object: SpecialistPractice
        controlled_object:  SpecialistClinician
    }

// ── Referral Episode Community (Creation-style, transient) ─────────────────
// Per X.902 §9.18: Creation -- instantiated by an action of objects
// in the model (the referral commitment by GPClinician).

community ReferralEpisodeCommunity
    description: "Creation-style community; instantiated by the referral commitment; scopes all principal-agent relationships for this episode only; dissolved on objective achievement"
    {
        objective: "Complete specialist examination for the referred patient"
            satisfaction: all_discharged(episodeBurdenGroup)

        invariant episodeScopedAccountability:
            "principal_of and delegated_from relationships established here -- including SpecialistClinician's delegation to SpecialistAIAgent -- are dissolved when this community terminates"

        on_join aiExaminationRole transfer patientRecordAccessPermit
        on_leave aiExaminationRole revert patientRecordAccessPermit

        role referringClinicianRole
            description: "GPClinician, principal for this episode"
            {
                holds referralBurden
                // AF(discharged) holds -- discharge_mode: strict on referralBurden

                action submitReferral {
                    description: "GP clinician submits referral to specialist practice; Creation act that instantiates the episode"
                    actor: referringClinicianRole
                    artefact: patientRecord
                    favoured_by_burden referralBurden
                    effect activate examinationBurden
                }
            }

        role referredToSpecialistRole
            description: "SpecialistClinician, agent of GPClinician for this episode; principal of SpecialistAIAgent for this episode only"
            {
                holds examinationBurden
                // EF(discharged) holds -- discharge_mode: eventual on examinationBurden

                action acknowledgeReferral {
                    description: "Specialist clinician acknowledges receipt of referral and confirms clinical review"
                    actor: referredToSpecialistRole
                    artefact: patientRecord
                }

                action scheduleAssessment {
                    description: "Specialist clinician schedules patient assessment; discharges examination burden and activates AI examination burden"
                    actor: referredToSpecialistRole
                    favoured_by_burden examinationBurden
                    effect activate aiExaminationBurden
                }
            }

        role aiExaminationRole
            description: "SpecialistAIAgent, agent of SpecialistClinician for this episode only; not a standing relationship under SpecialistPractice"
            {
                holds aiExaminationBurden
                holds patientRecordAccessPermit
                // EF(discharged) holds -- discharge_mode: eventual on aiExaminationBurden

                action access_patient_clinical_records {
                    description: "AI agent accesses patient clinical records; requires permit granted on episode join"
                    actor: aiExaminationRole
                    artefact: patientRecord
                    requires_permit patientRecordAccessPermit for aiExaminationRole
                }

                action conductAIExamination {
                    description: "AI agent conducts diagnostic examination of patient record"
                    actor: aiExaminationRole
                    artefact: patientRecord
                    requires_permit patientRecordAccessPermit for aiExaminationRole
                    favoured_by_burden aiExaminationBurden
                }
            }

        lifecycle {
            establishing {
                commitment by referringClinicianRole:
                    "Referral act (Creation, X.902 §9.18) instantiates this community"
            }
            terminating {
                on_objective_achieved: true
                description: "Episode concludes once examination is complete and reported"
            }
        }
    }

// ── Violation Responses ────────────────────────────────────────────────────
// Only detectable (eventual) burdens have violation responses.
// referralBurden (strict) has no ViolationResponse -- violation is
// unreachable by construction; declaring one would be misleading.

violation_response examinationViolation {
    on_violation_of: examinationBurden
    obligates: SpecialistPractice
    response_kind: escalate
    escalate_to: GPPractice
    description: "If specialist clinician fails to complete examination, SpecialistPractice must escalate to GPPractice"
}

violation_response aiExaminationViolation {
    on_violation_of: aiExaminationBurden
    obligates: SpecialistClinician
    response_kind: remediate
    description: "If AI agent fails to conduct examination, SpecialistClinician as principal must remediate"
}
