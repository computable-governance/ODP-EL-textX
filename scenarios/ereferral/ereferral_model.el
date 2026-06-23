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
    for_action: "conductExamination"
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

        invariant episodeScopedAccountability:
            "principal_of and delegated_from relationships established here -- including SpecialistClinician's delegation to SpecialistAIAgent -- are dissolved when this community terminates"

        role referringClinicianRole
            description: "GPClinician, principal for this episode"
            {
                holds referralBurden
                // AF(discharged) holds -- discharge_mode: strict on referralBurden
            }

        role referredToSpecialistRole
            description: "SpecialistClinician, agent of GPClinician for this episode; principal of SpecialistAIAgent for this episode only"
            {
                holds examinationBurden
                // EF(discharged) holds -- discharge_mode: eventual on examinationBurden
            }

        role aiExaminationRole
            description: "SpecialistAIAgent, agent of SpecialistClinician for this episode only; not a standing relationship under SpecialistPractice"
            {
                holds aiExaminationBurden
                // EF(discharged) holds -- discharge_mode: eventual on aiExaminationBurden
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
