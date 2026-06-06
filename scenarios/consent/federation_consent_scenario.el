enterprise specification FederationConsentScenario
    description: "Clinical AI governance federation: two-domain accountability chain"
    scope: "Multi-community clinical AI governance with cross-domain delegation (AM-25)"

// ── Enterprise Objects ────────────────────────────────────────────────────────

party GPPracticeParty { }

party GPParty {
    principal_of SpecialistParty
}

party SpecialistPracticeParty {
    principal_of SpecialistParty
}

party SpecialistParty {
    principal_of AISpecialistAgent
}

agent AISpecialistAgent {
    delegated_from SpecialistParty
}

// ── Domains ───────────────────────────────────────────────────────────────────

domain GPPracticeDomain
    characterized_by: "gp_practice_governance"
{
    controlling_object: GPPracticeParty
    controlled_object: GPParty
}

domain SpecialistPracticeDomain
    characterized_by: "specialist_practice_governance"
{
    controlling_object: SpecialistPracticeParty
    controlled_object: SpecialistParty
    controlled_object: AISpecialistAgent
}

// ── Federation ────────────────────────────────────────────────────────────────

contract federation ClinicalGovernanceFederation {
    objective: "ensure informed consent before AI specialist analysis"
    member: GPPracticeDomain
    member: SpecialistPracticeDomain
    invariant f1: "consent must be obtained before AI analysis"
    conflict_resolution specification_time_assurance
}

// ── Deontic Token ─────────────────────────────────────────────────────────────

burden seekConsentObligation {
    for_action: "seek_patient_consent"
    state: active
    discharge_mode: strict
    priority: critical
}

// ── Accountability Chain ──────────────────────────────────────────────────────

commitment GPConsentCommitment {
    by: GPPracticeParty
    obligation: "ensure patient consent for AI specialist analysis"
    creates_burden: seekConsentObligation
    principals_obligated: GPPracticeParty
}

delegation ConsentDelegation1 {
    from: GPParty
    to: SpecialistParty
    obligation: "ensure patient consent"
    transfers_burden: seekConsentObligation
}

delegation ConsentDelegation2 {
    from: SpecialistParty
    to: AISpecialistAgent
    obligation: "seek patient consent before analysis"
    transfers_burden: seekConsentObligation
}
