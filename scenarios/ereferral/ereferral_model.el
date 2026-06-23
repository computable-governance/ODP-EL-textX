// eReferral enterprise model
// Developed during Forum paper session, June 2026
// Combines two Introduction-style domains and a Creation-style episode community
// Supports both governance (compelled/AF) and coordination (detectable/EF) readings
// Design decisions documented in coordination_design_note_v3.md §13.5, §13.6

// ── Enterprise Objects ──────────────────────────────────────────────────────

party GPPractice
    description: "GP practice -- HPI-O registered legal entity"

party GPClinician
    description: "GP clinician -- HPI-I registered; accountable party in
                  own right; agent of GP practice"
    delegated_from: GPPractice
        duration: "ongoing practice membership"

party SpecialistPractice
    description: "Specialist practice -- HPI-O registered legal entity"

party SpecialistClinician
    description: "Specialist clinician -- HPI-I registered; accountable
                  party in own right; organisationally controlled by
                  SpecialistPractice"

agent SpecialistAIAgent
    description: "AI diagnostic assistant; no standing delegation
                  relationship until activated within an episode community"

// ── Organisational Domains (Introduction-style, durable) ───────────────────
// Per §7.5: domain is a lightweight community expressing structural
// accountability boundary only -- no objective, role, or lifecycle.
// Per §7.8.8.2-3: domain is the unit of authorization scope for
// permit and embargo (not burden -- see §13.5).

domain GPPracticeDomain
    characterized_by: "Organisational accountability boundary; implicit
                       authorization established at domain formation"
    {
        controlling_object: GPPractice
        controlled_object:  GPClinician
    }

domain SpecialistPracticeDomain
    characterized_by: "Organisational accountability boundary; implicit
                       authorization established at domain formation"
    {
        controlling_object: SpecialistPractice
        controlled_object:  SpecialistClinician
    }

// ── Referral Episode Community (Creation-style, transient) ─────────────────
// Per X.902 §9.18: Creation -- instantiated by an action of objects
// in the model (the referral commitment by GPClinician).
// discharge_mode is a toolchain extension (AM-13), not ISO/IEC 15414.
// strict  -> AF holds (compelled): violation state unreachable
// eventual -> EF only (detectable): violation observable after the fact

community ReferralEpisodeCommunity
    description: "Creation-style community; instantiated by the referral
                  commitment; scopes all principal-agent relationships
                  for this episode only, including the AI agent's
                  involvement; dissolved on objective achievement"
    {
        objective: "Complete specialist examination for the referred patient"

        invariant episodeScopedAccountability:
            "principal_of and delegated_from relationships established here
             -- including SpecialistClinician's delegation to
             SpecialistAIAgent -- are dissolved when this community
             terminates"

        role referringClinicianRole
            description: "GPClinician, principal for this episode"
        {
            holds referralBurden
                discharge_mode: strict
                // AF(discharged) holds -- GP clinician must act
        }

        role referredToSpecialistRole
            description: "SpecialistClinician, agent of GPClinician for
                          this episode; principal of SpecialistAIAgent
                          for this episode only"
        {
            holds examinationBurden
                discharge_mode: eventual
                // AF fails; EF(discharged) holds -- detectable only
        }

        role aiExaminationRole
            description: "SpecialistAIAgent, agent of SpecialistClinician
                          for this episode only -- not a standing
                          relationship under SpecialistPractice"
        {
            holds aiExaminationBurden
                discharge_mode: eventual
                // AF fails; EF(discharged) holds -- detectable only
        }

        lifecycle {
            establishing {
                implicit: false
                commitment by referringClinicianRole:
                    "Referral act (Creation, X.902 §9.18) instantiates
                     this community"
            }
            terminating {
                on_objective_achieved: true
                description: "Episode concludes once examination is
                              complete and reported"
            }
        }
    }
