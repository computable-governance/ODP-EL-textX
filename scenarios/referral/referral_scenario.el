/*
 * ================================================================
 * referral_scenario.el
 * ODP Enterprise Language DSL — Unified GP-to-specialist referral governance
 *
 * CANDIDATE REFERENCE SCENARIO (see scenarios/README.md) — supersedes
 * gp_referral_scenario.el and ereferral_model.el once promoted.
 *
 * Two-tier structure:
 *
 *   ReferralNetworkFederation (STANDING, never created) — the durable
 *   organisational relationship between GP practice and specialist
 *   practice, joining GPPracticeCommunity and SpecialistPracticeCommunity via
 *   CommunityObject role-filling (AM-26). Carries the normative_policy
 *   citations. Exists independently of any specific referral.
 *
 *   ReferralEpisodeCommunity (CREATED, per §7.3.2 / Part 2 §9.18) — the
 *   transient, per-referral thing. Established via AM-33's
 *   established_by (a real, resolved trigger — the referral submission
 *   event). Scopes referral-specific burdens/permits for this episode
 *   only; dissolved on objective achievement. Note: the Creation act
 *   itself (initiateReferral) lives in GPPracticeCommunity, the
 *   *creating* community — not inside the episode it creates (Annex B
 *   pattern; see docs/CONCEPTS_INDEX.md "Creation-style / episodic
 *   community").
 *
 * Federation membership is restricted to communities, not individual
 * enterprise objects — confirmed directly against the standard, not
 * merely an artifact of how MemberRef happens to be typed in this
 * toolchain (grammar/v2/el_grammar.tx: community=[Community]). §7.5.2:
 * "An <X>-federation community is a community of a number of
 * pre-existing communities cooperating to achieve a shared objective."
 * Individuals participate only through a community — directly, via
 * CommunityObject role-filling (§6.2.2, AM-26), or via interface roles/
 * interactions (§7.3.2) — never as a bare enterprise object sitting
 * alongside communities in a federation's membership list. The
 * episode's participants are individual clinicians/agents, so it is a
 * plain community, not a federation, regardless of how
 * cross-organisational its membership is.
 *
 * ACCOUNTABILITY CHAIN — three distinct moments, deliberately modelled
 * with two different uses of the same construct pair:
 *
 *   1. Internal, standing (GPPracticeParty... now GPPractice, below):
 *      GPPractice ──[principal_of, no reciprocal delegated_from]──► GPClinician
 *      SpecialistPractice ──[principal_of, no reciprocal delegated_from]──► SpecialistClinician
 *      principal_of ALONE expresses organisational affiliation of an
 *      independently-accountable party (HPI-I registered) — deliberately
 *      NOT full subordinate agency.
 *
 *   2. Cross-organisational, episode-scoped, the true referral delegation
 *      (Option B — settled 2026-07-07, clinician-to-clinician, not
 *      practice-to-practice):
 *      GPClinician ──[principal_of + reciprocal delegated_from, both
 *        episode-scoped]──► SpecialistClinician
 *      This pairing (principal_of + delegated_from together) is what
 *      marks a GENUINE, if temporary, delegated principal-agent
 *      relationship — layered ON TOP OF SpecialistClinician's own
 *      independent standing accountability via SpecialistPractice, not
 *      replacing it. SpecialistClinician ends up with two simultaneous
 *      principals: SpecialistPractice (standing) and GPClinician
 *      (episode-scoped).
 *
 *   3. Trivial (per Zoran) — SpecialistClinician ──[principal_of +
 *      delegated_from]──► SpecialistAIAgent, ordinary human-delegates-
 *      to-software-agent, episode-scoped.
 *
 * The broader ACCOUNTABILITY CHAIN (GPPractice → GPClinician →
 * SpecialistClinician → SpecialistAIAgent, composing standing
 * affiliation with episode delegation) is broader than the DELEGATION
 * CHAIN alone (GPClinician → SpecialistClinician → SpecialistAIAgent) —
 * see docs/CONCEPTS_INDEX.md, "Accountability chain composition".
 *
 * ALTERNATIVE MODELLING NOTE: GPPractice's standing accountability for
 * GPClinician (and SpecialistPractice's for SpecialistClinician) could
 * equally be expressed as a Domain (controlling_object/controlled_object,
 * §7.5.1) rather than principal_of — both are legitimate for the same
 * underlying fact. principal_of is used here as the lighter mechanism
 * for a single practice-clinician pair; Domain is the natural choice
 * when one controlling authority reaches across several controlled
 * objects at once, as PatientDataDomain does below for data governance
 * specifically. See docs/CONCEPTS_INDEX.md, "Standing accountability:
 * principal_of/delegated_from vs. Domain".
 *
 * Authorization (separate from delegation, §4.0b): Patient
 * ──[authorizes, NOT delegation, PatientParty not a co-principal]──►
 * SpecialistAIAgent. Runs parallel to the delegation chain, not through
 * it — the AI agent has both a delegated OBLIGATION (from its principal,
 * SpecialistClinician) and a separate PERMISSION (from Patient's
 * authorization) to access the data it needs to fulfil that obligation.
 *
 * Patient fills a role in all three communities (GPPracticeCommunity,
 * SpecialistPracticeCommunity, ReferralEpisodeCommunity) concurrently, accepting
 * each community's own contract/invariants at once. Role-filling and
 * party-hood are orthogonal — this does not compromise Patient's
 * independent party status.
 *
 * Token groups:
 *   referralBurdenGroup   = { referralInitiationBurden, clinicalHandoverBurden,
 *                             referralResponseBurden, assessmentSchedulingBurden,
 *                             aiExaminationBurden }
 *     — ReferralEpisodeCommunity's own objective satisfaction condition
 *       (all_discharged); the episode dissolves once satisfied. Includes
 *       the AI's own diagnostic work, not just the human-side burdens.
 *   specialistBurdenGroup = { referralResponseBurden, assessmentSchedulingBurden }
 *
 * Layer 4 verification questions (el_kripke.py) — matching
 * gp_referral_scenario.el's pattern, extended for aiExaminationBurden:
 *   Q1: AF(discharged:referralInitiationBurden)? YES — discharge_mode: strict.
 *   Q2: AF(discharged:referralResponseBurden)?  NO  — discharge_mode: eventual;
 *       EF holds (some path discharges it).
 *   Q3: AF(discharged:aiExaminationBurden)? NO — discharge_mode: eventual;
 *       EF holds. Same compelled-vs-detectable distinction, now applied
 *       to the AI agent's own diagnostic work, not just the specialist's
 *       response.
 *   Q4: objective_satisfied:ReferralEpisodeCommunity? EF only (blocked by
 *       eventual referralResponseBurden and aiExaminationBurden).
 *
 * NOTE on creates_reporting_burden (used below on both delegation acts):
 * this flag is captured by el_reasoner.py for human-readable
 * accountability-chain explanations, but is NOT currently processed by
 * el_engine.py/el_kripke.py — it does not create a second, independently
 * Kripke-checkable obligation. Documented intent, not yet enforced
 * behaviour; consistent with how this flag is used everywhere else in
 * the toolchain (consent_scenario.el, generated_governance.el).
 *
 * ViolationResponse:
 *   If referralResponseBurden is violated (specialist does not respond),
 *   SpecialistPractice must escalate and notify GPPractice.
 * ================================================================
 */

enterprise specification ReferralGovernanceSystem
    description: "Unified GP-to-specialist referral governance: standing inter-practice federation plus created per-referral episode community"
    field_of_application: "Primary and specialist care coordination in a federated healthcare context"
    scope: "Referral obligation management across a standing GP/specialist practice federation and per-episode governance"


// ================================================================
// §6.6.1, §6.6.8, §7.4 — PARTIES AND AGENTS
// ================================================================

party GPPractice
    description: "General practice — root standing principal for GPClinician; organisational affiliation only (no reciprocal delegated_from — GPClinician is independently accountable)"
    {
        principal_of GPClinician
    }

// GPClinician is a party, not an agent (corrected 2026-07-05 from an
// earlier agent-typed draft) — HPI-I registered Australian clinicians
// bear personal legal/professional accountability regardless of practice
// affiliation. See docs/CONCEPTS_INDEX.md, "Party vs agent for clinicians".
//
// principal_of SpecialistClinician below is the EPISODE-SCOPED, genuine
// delegation relationship (Option B, settled 2026-07-07) — paired with
// SpecialistClinician's own reciprocal delegated_from GPClinician,
// marking this as real delegated principal-agent accountability, not
// mere affiliation.
party GPClinician
    description: "GP clinician — HPI-I registered; accountable party in own right; organisationally affiliated with GPPractice; fills gpClinicianRole in GPPracticeCommunity. Referral delegation is clinician-to-clinician (Option B), not practice-to-practice."
    {
        principal_of SpecialistClinician
    }

party SpecialistPractice
    description: "Specialist practice — root standing principal for SpecialistClinician; organisational affiliation only (no reciprocal delegated_from — SpecialistClinician is independently accountable)"
    {
        principal_of SpecialistClinician
    }

// SpecialistClinician carries TWO simultaneous principals: SpecialistPractice
// (standing, affiliation-only) and GPClinician (episode-scoped, genuine
// delegation — reciprocal to GPClinician's principal_of above).
party SpecialistClinician
    description: "Specialist clinician — HPI-I registered; accountable party in own right; organisationally affiliated with SpecialistPractice; fills specialistRole in SpecialistPracticeCommunity. Also episode-scoped delegate of GPClinician for this specific referral."
    {
        delegated_from GPClinician
            duration: "referral episode"
        principal_of SpecialistAIAgent
    }

// delegated_from is episode-scoped (duration: "referral episode"),
// mirroring the same relationship declared reciprocally on SpecialistClinician
// above (principal_of SpecialistAIAgent). "Trivial" per Zoran — ordinary
// human-delegates-to-software-agent case.
agent SpecialistAIAgent
    description: "AI diagnostic assistant — active object; agent of SpecialistClinician for referral episode only; not a standing relationship under SpecialistPractice. Governed as Software as a Medical Device — see AIMedicalDeviceRegulation."
    {
        delegated_from SpecialistClinician
            duration: "referral episode"
    }

party Patient
    description: "Patient — data subject; consents to and may revoke authorization for specialist AI agent access to their clinical records. Authorizing SpecialistAIAgent directly (AM-31b) does not make Patient a co-principal of it — see AM-31 design note §4.0b; SpecialistClinician remains sole principal via the separate delegated_from relationship above. Fills a role in GPPracticeCommunity, SpecialistPracticeCommunity, and ReferralEpisodeCommunity concurrently."

artefact_object patientRecord
    description: "Patient clinical record — referenced by referral initiation, clinical handover, and specialist review actions"


// ================================================================
// §6.4, §7.8.7 — DEONTIC TOKENS (episode-scoped)
// ================================================================

// discharge_mode: strict — GP must initiate promptly; AF(discharged:referralInitiationBurden) holds.
// Discharging this action also emits referralSubmitted (see GPPracticeCommunity's
// events list below), which triggers ReferralEpisodeCommunity's establishment (AM-33).
// triggered_by: encounterConcluded (R26-R29 probe, docs/CONCEPTS_INDEX.md item #1) —
// fired directly via Runtime.fire_event() from a FHIR Encounter.status=finished
// event, not from any DSL action's emits. See GPPracticeCommunity's events list
// below for the EventDecl.
burden referralInitiationBurden {
    for_action: "initiateReferral"
    state: active
    deadline: "48 hours from clinical decision"
    triggered_by: encounterConcluded
    discharge_mode: strict
    priority: critical
    description: "Obligation on GP clinician to initiate and transmit specialist referral for the patient"
}

// discharge_mode: eventual — GP may delay handover; AF does not hold for clinicalHandoverBurden.
burden clinicalHandoverBurden {
    for_action: "provideHandover"
    state: active
    deadline: "referral episode"
    discharge_mode: eventual
    priority: normal
    description: "Obligation on GP clinician to provide complete clinical handover documentation to specialist"
}

// discharge_mode: eventual — specialist may delay response; EF holds but AF does not.
// Key Kripke verification target for the cross-organisational delegation.
burden referralResponseBurden {
    for_action: "acknowledgeReferral"
    state: active
    deadline: "5 working days from referral receipt"
    discharge_mode: eventual
    priority: high
    description: "Obligation on specialist clinician to acknowledge and respond to the GP referral"
}

// discharge_mode: eventual — scheduling follows acknowledgement.
burden assessmentSchedulingBurden {
    for_action: "scheduleAssessment"
    state: active
    deadline: "14 days from referral receipt"
    discharge_mode: eventual
    priority: normal
    description: "Obligation on specialist clinician to schedule an assessment appointment for the referred patient"
}

// discharge_mode: eventual — the AI's diagnostic completion is detectable,
// not compelled, matching referralResponseBurden's pattern one level
// further down the delegation chain. Carried from ereferral_model.el's
// original aiExaminationBurden, dropped when this file was first drafted
// from gp_referral_scenario.el (which never modelled the AI's actual
// diagnostic work as an obligation, only as permit-holding).
burden aiExaminationBurden {
    for_action: "conductAIExamination"
    state: active
    deadline: "referral episode"
    discharge_mode: eventual
    priority: normal
    description: "Obligation on the AI diagnostic agent to conduct examination of the referred patient's record and report findings back to the accountable clinician"
}

// Created on violation of referralResponseBurden; SpecialistPractice must discharge this promptly.
burden escalationNoticeBurden {
    for_action: "notify_gp_of_non_response"
    state: active
    deadline: "48 hours from violation detection"
    discharge_mode: strict
    priority: critical
    description: "Obligation on specialist practice to notify GP practice of failure to respond to referral"
}

// AM-31b: two permits, reflecting two distinct ODP-EL grant mechanisms
// (role transfer vs. AuthorizationDecl, §6.6.4). See AM-31 design note §4.0/§4.0b.
permit patientRecordAccessPermitByRole {
    for_action: "access_patient_clinical_records"
    state: active
    description: "Permission for specialist clinician to access patient records for referral assessment, via specialistRole (episode-scoped) membership"
}

permit patientRecordAccessPermitByAuthorization {
    for_action: "access_patient_clinical_records"
    state: active
    description: "Permission for specialist AI diagnostic agent to access patient records for referral assessment, via explicit patient authorization"
}

// AM-31: activated on revocation of patientDataAuthorization.
embargo patientRecordAccessEmbargo {
    for_action: "access_patient_clinical_records"
    state: pending
    description: "Blocks specialist AI agent access to patient records after patient revokes patientDataAuthorization"
}


// ================================================================
// §6.4.2, AM-26 — TOKEN GROUPS
// ================================================================

// Episode-level group: all five burdens (including the AI's own
// diagnostic work) must be discharged for ReferralEpisodeCommunity's
// objective to be satisfied (all_discharged); the episode dissolves on
// satisfaction (terminating: on_objective_achieved).
token_group referralBurdenGroup {
    member: referralInitiationBurden
    member: clinicalHandoverBurden
    member: referralResponseBurden
    member: assessmentSchedulingBurden
    member: aiExaminationBurden
}

token_group specialistBurdenGroup {
    member: referralResponseBurden
    member: assessmentSchedulingBurden
}


// ================================================================
// §7.5.1 — PATIENT DATA DOMAIN
// (genuine cross-cutting characterizing relationship — not an
// organisational unit; see docs/CONCEPTS_INDEX.md "Domain" entry.
// Cuts across GPClinician/SpecialistClinician/SpecialistAIAgent
// regardless of which community/episode they currently participate in.
// Contrast with principal_of above: this Domain reaches across THREE
// controlled objects under one controlling authority at once — exactly
// the case where Domain is the natural mechanism, per the header note.)
// ================================================================

domain PatientDataDomain
    characterized_by: "Data controller-processor relationship"
    description: "Domain governing access to and processing of patient clinical records"
    {
        controlling_object: GPPractice
        controlled_object: GPClinician
        controlled_object: SpecialistClinician
        controlled_object: SpecialistAIAgent
    }


// ================================================================
// §6.2.2, §7.4 — COMMUNITY OBJECTS (AM-26)
// abstracts=[Community] — GPPracticeCommunity/SpecialistPracticeCommunity
// (plain communities, not domains — corrected 2026-07-06 from
// ereferral_model.el's original Domain-abstracting pattern).
// ================================================================

community_object GPPracticeObj
    description: "Community object representing GPPracticeCommunity in the standing referral network federation"
    {
        abstracts: GPPracticeCommunity
    }

community_object SpecialistPracticeObj
    description: "Community object representing SpecialistPracticeCommunity in the standing referral network federation"
    {
        abstracts: SpecialistPracticeCommunity
    }


// ================================================================
// §6.2, §7.3 — GP PRACTICE COMMUNITY (standing, holds the Creation act)
// ================================================================

community GPPracticeCommunity
    description: "Standing organisational community for the GP practice. Deliberately holds the referral-CREATING action (initiateReferral) even though most other referral work lives in ReferralEpisodeCommunity — per the Annex B pattern (docs/CONCEPTS_INDEX.md, 'Creation-style / episodic community'), creation behaviour lives in the creating community's specification, not the created community's own establishing block."
    {
        objective: "Maintain a registered, capable GP clinician workforce able to initiate and participate in specialist referrals"

        event referralSubmitted
            description: "Emitted when GP clinician submits the specialist referral — the Creation act (Part 2 §9.18) that instantiates ReferralEpisodeCommunity"

        event encounterConcluded
            description: "R26-R29 probe: fired directly from Python (Runtime.fire_event()) when a FHIR Encounter resource transitions to status=finished — not emitted by any DSL action"

        invariant gpRegistrationCurrency:
            "GP clinician must hold current GP registration and referral prescribing authority to remain a member"

        assignment_policy for gpClinicianRole {
            requires_capability: "Must hold current GP registration and referral prescribing authority"
            requires_token burden: "Must hold referralInitiationBurden"
        }

        on_join gpClinicianRole transfer referralInitiationBurden
        on_leave gpClinicianRole revert referralInitiationBurden

        role gpClinicianRole
            description: "GP clinician role — standing membership in the GP practice; holds the referral-initiation obligation"
            {
                holds referralInitiationBurden

                action initiateReferral {
                    description: "GP clinician initiates and transmits specialist referral for the patient; Creation act that instantiates ReferralEpisodeCommunity"
                    actor: gpClinicianRole
                    artefact: patientRecord
                    precondition: "Patient must have an active episode of care and clinical indication for referral"
                    favoured_by_burden referralInitiationBurden
                    emits: referralSubmitted
                    effect create referralResponseBurden to referredToRole
                    effect create assessmentSchedulingBurden to referredToRole
                }
            }

        role patientRole
            description: "Patient role — GPPracticeCommunity's own contract/invariants apply while the patient is under this practice's care"
            {}

        lifecycle {
            establishing {
                implicit: true
                description: "GP practice community is pre-existing"
            }
        }
    }


// ================================================================
// §6.2, §7.3 — SPECIALIST COMMUNITY (standing, lightweight)
// ================================================================

community SpecialistPracticeCommunity
    description: "Standing organisational community for the specialist practice — membership/employment only; referral-specific work lives in ReferralEpisodeCommunity"
    {
        objective: "Maintain a registered, capable specialist clinician workforce able to accept referrals"

        invariant specialistRegistrationCurrency:
            "Specialist clinician must hold current specialist registration in the relevant clinical area to remain a member"

        assignment_policy for specialistRole {
            requires_capability: "Must hold current specialist registration in the relevant clinical area"
        }

        role specialistRole
            description: "Specialist clinician role — standing membership in the specialist practice"
            {}

        role patientRole
            description: "Patient role — SpecialistPracticeCommunity's own contract/invariants apply while the patient is under this practice's referred care"
            {}

        lifecycle {
            establishing {
                implicit: true
                description: "Specialist community is pre-existing"
            }
        }
    }


// ================================================================
// §7.5.2 — REFERRAL NETWORK FEDERATION (standing, never created)
// ================================================================

contract federation ReferralNetworkFederation
    description: "Durable referral network governance contract between GP and specialist practices"
    {
        objective: "Ensure governed, timely specialist referral capability between GP practice and specialist practice"

        normative_policy: MyHealthRecordsAct
        normative_policy: NationalClinicalGovernance
        normative_policy: AIMedicalDeviceRegulation

        interface role gpPracticeRole
            description: "GP practice role in the referral network federation"
            {}

        interface role specialistPracticeRole
            description: "Specialist practice role in the referral network federation"
            {}

        member: GPPracticeCommunity
            represented_by GPPracticeObj
            fills gpPracticeRole

        member: SpecialistPracticeCommunity
            represented_by SpecialistPracticeObj
            fills specialistPracticeRole

        invariant federationDataProtection:
            "Patient data shared across community boundaries must comply with data protection obligations"

        conflict_resolution specification_time_assurance
    }


// ================================================================
// §6.5, §7.5.1 — NORMATIVE POLICIES (AM-28)
// Valid at Federation level today without further amendment (V-NEW-20).
// ================================================================

normative_policy MyHealthRecordsAct {
    description: "Governs access to and use of My Health Record data"
    source: "My Health Records Act 2012 (Cth)"
    kind: legislation
    type: string
    initial_value: "2012 provisions as amended to 2026"
    policy_setting_behaviour: "Parliamentary amendment"
}

normative_policy NationalClinicalGovernance {
    description: "National model for clinical governance, including explicit guidance on governing digitally enabled care and AI-supported clinical decision-making"
    source: "National Model for Clinical Governance: The foundations of high-quality care (ACSQHC, 2026), superseding the 2017 National Model Clinical Governance Framework"
    kind: standard
    type: string
    initial_value: "2026 edition — six foundations of clinical governance"
    policy_setting_behaviour: "ACSQHC review and republication"
}

normative_policy AIMedicalDeviceRegulation {
    description: "AI-based diagnostic support software is regulated as Software as a Medical Device (SaMD); governs SpecialistAIAgent's use in clinical decision support"
    source: "Therapeutic Goods Administration regulation of Software as a Medical Device, under the Therapeutic Goods Act 1989 (Cth) and associated Regulations"
    kind: regulation
    type: string
    initial_value: "TGA conformity assessment and post-market surveillance requirements for AI/software-based medical devices"
    policy_setting_behaviour: "TGA regulatory update"
}


// ================================================================
// §7.3.2, Part 2 §9.18 — REFERRAL EPISODE COMMUNITY (created, transient)
// Established via AM-33's established_by — a real, resolved trigger,
// not the free-text prose ereferral_model.el could only express before
// AM-33 existed.
// ================================================================

community ReferralEpisodeCommunity
    description: "Creation-style community; instantiated by GP clinician's referral submission; scopes referral-specific burdens/permits for this episode only; dissolved on objective achievement"
    {
        objective: "Complete specialist assessment for the referred patient"
            satisfaction: all_discharged(referralBurdenGroup)

        invariant episodeScopedAccountability:
            "Episode-scoped principal/agent relationships established here — GPClinician's delegation to SpecialistClinician, and SpecialistClinician's delegation to SpecialistAIAgent — are understood to be scoped to this episode; standing organisational relationships (GPPractice/SpecialistPractice to their own clinicians) are unaffected by this community's lifecycle"

        assignment_policy for referredToRole {
            requires_token permit: "Must hold patientRecordAccessPermitByRole"
        }

        on_join referringRole transfer clinicalHandoverBurden
        on_join referredToRole transfer patientRecordAccessPermitByRole
        on_leave referringRole revert clinicalHandoverBurden
        on_leave referredToRole revert patientRecordAccessPermitByRole

        role referringRole
            description: "GPClinician, principal for this episode. Note: initiateReferral (the Creation act) lives in GPPracticeCommunity, not here — see that community's description for why."
            {
                action provideHandover {
                    description: "GP clinician provides clinical handover documentation to specialist"
                    actor: referringRole
                    artefact: patientRecord
                    precondition: "Referral must be active and acknowledged by specialist"
                    favoured_by_burden clinicalHandoverBurden
                }
            }

        role referredToRole
            description: "SpecialistClinician, delegate of GPClinician for this episode; principal of SpecialistAIAgent for this episode only"
            {
                holds patientRecordAccessPermitByRole

                action acknowledgeReferral {
                    description: "Specialist clinician acknowledges receipt of GP referral and initiates clinical review"
                    actor: referredToRole
                    artefact: patientRecord
                    requires_permit patientRecordAccessPermitByRole for referredToRole
                    favoured_by_burden referralResponseBurden
                }

                action scheduleAssessment {
                    description: "Specialist clinician schedules patient assessment appointment"
                    actor: referredToRole
                    precondition: "Referral must be acknowledged and patient availability confirmed"
                    requires_permit patientRecordAccessPermitByRole for referredToRole
                    favoured_by_burden assessmentSchedulingBurden
                }
            }

        role aiExaminationRole
            description: "SpecialistAIAgent, delegate of SpecialistClinician for this episode only; not a standing relationship under SpecialistPractice"
            {
                action access_patient_clinical_records {
                    description: "AI agent accesses patient clinical records; requires the authorization-based permit"
                    actor: aiExaminationRole
                    artefact: patientRecord
                    requires_permit patientRecordAccessPermitByAuthorization for aiExaminationRole
                }

                action conductAIExamination {
                    description: "AI agent conducts diagnostic examination of the referred patient's record and reports findings back to the accountable specialist clinician"
                    actor: aiExaminationRole
                    artefact: patientRecord
                    precondition: "AI agent must hold patientRecordAccessPermitByAuthorization"
                    favoured_by_burden aiExaminationBurden
                }
            }

        role episodePatientRole
            description: "Patient — consents to and may revoke authorization for AI agent record access, scoped to this episode"
            {}

        lifecycle {
            establishing {
                established_by: referralSubmitted
                description: "Creation (Part 2 §9.18): instantiated by GP clinician's referral submission action, which emits referralSubmitted"
            }
            terminating {
                on_objective_achieved: true
                description: "Episode concludes once all referral burdens (including the AI's own diagnostic work) are discharged"
            }
        }
    }


// ================================================================
// §6.6, §7.10 — ACCOUNTABILITY CHAIN
// ================================================================

commitment referralCommitment {
    by: GPPractice
    obligation: "Initiate specialist referral and provide clinical handover for the patient"
    creates_burden: referralInitiationBurden
    description: "GP practice commits to initiating a specialist referral and providing complete clinical handover"
}

commitment referralResponseCommitment {
    by: GPPractice
    obligation: "Respond to the specialist referral within the agreed timeframe and schedule assessment"
    creates_burden: referralResponseBurden
    description: "GP practice commits to ensuring specialist responds to the referral and schedules assessment"
}

commitment clinicalHandoverCommitment {
    by: GPPractice
    obligation: "Provide complete clinical handover documentation to specialist"
    creates_burden: clinicalHandoverBurden
    description: "GP practice commits to providing complete clinical handover documentation to the specialist"
}

commitment assessmentSchedulingCommitment {
    by: SpecialistPractice
    obligation: "Schedule specialist assessment appointment for the patient"
    creates_burden: assessmentSchedulingBurden
    description: "Specialist practice commits to scheduling a specialist assessment appointment for the referred patient"
}

commitment aiExaminationCommitment {
    by: SpecialistClinician
    obligation: "Conduct AI diagnostic examination of the referred patient and report findings back to the accountable clinician"
    creates_burden: aiExaminationBurden
    description: "Specialist clinician commits to ensuring AI-assisted diagnostic examination is conducted for the referred patient, prior to sub-delegating the work to the AI agent"
}

// Cross-organisational delegation — the TRUE referral delegation
// (Option B, settled 2026-07-07): clinician-to-clinician, not
// practice-to-practice. GPClinician's principal_of SpecialistClinician
// (declared above) and SpecialistClinician's reciprocal delegated_from
// GPClinician together mark this as genuine delegated principal-agent
// accountability, layered on top of SpecialistClinician's own standing
// relationship with SpecialistPractice.
delegation gpToSpecialistDelegation {
    from: GPClinician
    to: SpecialistClinician
    obligation: "Respond to the specialist referral within the agreed timeframe and schedule assessment"
    transfers_burden: referralResponseBurden
    transfers_token_group: referralBurdenGroup
    creates_reporting_burden: true
    duration: "referral episode"
    conditions: "Active GP referral transmitted and received by specialist community"
    sub_delegation_allowed: true
    revocable: true
    description: "GP clinician delegates referral response and scheduling obligations to specialist clinician — clinician-to-clinician, not institution-to-institution"
}

// Second delegation hop — SpecialistClinician sub-delegates the AI's
// diagnostic work, enabled by sub_delegation_allowed above. Mirrors
// consent_scenario.el's specialistToAIDelegation pattern.
delegation specialistToAIDelegation {
    from: SpecialistClinician
    to: SpecialistAIAgent
    obligation: "Conduct AI diagnostic examination of the referred patient and report findings back to the accountable clinician"
    transfers_burden: aiExaminationBurden
    creates_reporting_burden: true
    duration: "referral episode"
    conditions: "Active patient authorization on file; referral acknowledged by specialist"
    revocable: true
    description: "Specialist clinician delegates diagnostic examination to the AI agent; clinician remains accountable and requires results reported back"
}

// Authorization — Patient grants patient data access to SpecialistAIAgent.
// AM-31b: this is an authorization (§6.6.4), not a delegation (§6.6.6); it
// does not make Patient a co-principal of SpecialistAIAgent (§4.0b). Runs
// parallel to the delegation chain above, not through it.
authorization patientDataAuthorization {
    authority: Patient
    to_agent: SpecialistAIAgent
    grants_permit: patientRecordAccessPermitByAuthorization
    duration: "referral episode"
    conditions: "Active GP referral and patient data sharing consent on file"
    revocable: true
    on_revocation: activate patientRecordAccessEmbargo
    domain_scope: "PatientDataDomain"
    description: "Patient authorizes specialist AI diagnostic agent to access their clinical records for referral assessment; consent may be withdrawn by the patient at any time"
}


// ================================================================
// §6.3.8, §7.8.6 — VIOLATION RESPONSE
// ================================================================

violation_response referralNoResponseViolation {
    on_violation_of: referralResponseBurden
    obligates: SpecialistPractice
    response_kind: escalate
    creates_burden: escalationNoticeBurden
    escalate_to: GPPractice
    description: "If specialist fails to respond to referral, specialist practice must escalate and notify GP practice"
}


// ================================================================
// §6.6.3, §7.10.5 — PRESCRIPTION
// ================================================================

prescription referralResponseStandard {
    by: GPPractice
    establishes_rule: "Specialist must acknowledge referral within 5 working days and schedule assessment within 14 days"
    creates_oversight_burden: true
    description: "GP practice prescribes the standard referral response and scheduling timeframe for the federation"
}


// ================================================================
// §6.6.5, §7.10.4 — DECLARATION
// ================================================================

declaration referralAccepted {
    by: SpecialistClinician
    state_of_affairs: "Specialist referral has been accepted and is under clinical review"
    requires_permit: patientRecordAccessPermitByRole
    effective_on_interaction: true
    description: "Specialist clinician declares referral acceptance; effective on interaction with GP practice"
}


// ================================================================
// §6.6.7 — EVALUATION
// ================================================================

evaluation referralOutcomeEvaluation {
    by: GPPractice
    of_target: "referral episode governance compliance"
    result: "All referral burdens discharged within policy timeframes; episode objective satisfied"
    description: "GP practice evaluates overall governance compliance of the referral episode"
}


// ================================================================
// §11 — VIEWPOINT CORRESPONDENCES
// ================================================================

correspondence ReferralNetworkFederation    to computational : ReferralNetworkFederationService
correspondence ReferralEpisodeCommunity     to computational : ReferralEpisodeService
correspondence GPPracticeCommunity          to computational : GPPracticeService
correspondence SpecialistPracticeCommunity          to computational : SpecialistService
correspondence GPPractice                   to computational : GPPracticeClientObject
correspondence Patient                      to computational : PatientClientObject
correspondence SpecialistPractice           to computational : SpecialistServerObject
correspondence GPClinician                  to engineering   : GPClinicianNode
correspondence SpecialistClinician          to engineering   : SpecialistClinicianNode
correspondence SpecialistAIAgent            to engineering   : SpecialistAIAgentNode
correspondence patientRecord                to information   : PatientClinicalRecord
correspondence referralInitiationBurden     to information   : ReferralInitiationRecord
correspondence referralResponseBurden       to information   : ReferralResponseRecord
correspondence clinicalHandoverBurden       to information   : ClinicalHandoverRecord
correspondence aiExaminationBurden          to information   : AIExaminationRecord
correspondence patientRecordAccessPermitByRole          to information : DataAccessGrantRecordRole
correspondence patientRecordAccessPermitByAuthorization to information : DataAccessGrantRecordAuthorization
correspondence referralBurdenGroup          to information   : ReferralBurdenGroupRecord
