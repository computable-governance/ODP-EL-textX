/*
 * ================================================================
 * referral_claiming_scenario.el
 * ODP Enterprise Language DSL — pool claiming of a delegated
 * diagnostic referral (accept-side sibling of
 * specialist_pool_scenario.el's discharge-side any_discharged
 * demonstration)
 *
 * Purpose: first named demonstration of the pool-claiming mechanism
 * designed in DN_003 (delegation claiming design note) and
 * implemented as AM-60 (grammar/parser/domain: structured Evaluation,
 * claimable TokenState), AM-61 (Layer 4 el_kripke.py: CLAIMABLE/LAPSED
 * ObligationStates and the C1 claim transition), and AM-62 (Layer 3
 * el_engine.py: claimable -> active activation and sibling lapse).
 * A burden offered to an any_discharged pool starts `claimable`; a
 * structured accept Evaluation by the holder claims it (claimable ->
 * active / CLAIMABLE -> PENDING), lapsing the sibling's claim
 * opportunity; a reject (or absent) Evaluation is a deliberate no-op
 * leaving the burden claimable and available to the residual pool.
 *
 * DN_003's own working draft of this file (written before AM-60–62
 * landed, per its §6 "write the scenario before touching grammar"
 * sequencing) empirically exposed the two gaps this mechanism closes:
 * `Evaluation` had zero runtime handlers, and the live engine had no
 * `pending -> active` activation step at all — broader than AM-57's
 * stated scope (which only covered `active`-state sibling
 * supersession). Both are now closed on the accept/claiming side by
 * this scenario's mechanism; see tests/test_referral_claiming_scenario.py
 * for the empirical checks (both layers, real parsed model / real
 * engine, not asserted from design).
 *
 * Standards anchor: named directly against AU eRequesting's own
 * out-of-scope item ("claiming of diagnostic requests by fillers")
 * and its Task Group aggregation caveat ("expected... however this is
 * not enforced") — see DN_003 §1 for the verbatim-checked citations
 * from the published R1 IG.
 *
 * Token group:
 *   referralClaimGroup = { providerAClaimBurden, providerBClaimBurden }
 *
 * Community objective:
 *   DiagnosticReferralPoolCommunity: any_discharged(referralClaimGroup)
 *
 * Verification questions — EMPIRICALLY VERIFIED against the real
 * parser/Kripke model and the real live engine (2026-08-24):
 *
 *   Q1 (Layer 4): EF(objective_satisfied:DiagnosticReferralPoolCommunity)?
 *       TRUE. Both pool members start CLAIMABLE (not PENDING/WAITING);
 *       C1 (claim) reaches the objective-satisfying world.
 *   Qc (Layer 4): EF(discharged:providerAClaimBurden)? TRUE — the full
 *       claim -> discharge path is reachable via C1 then T1.
 *   Ql (Layer 4): EF(lapsed:providerBClaimBurden)? TRUE — the sibling's
 *       claim opportunity correctly lapses once Provider A claims first.
 *   Live engine (Layer 3): claiming providerAClaimBurden via
 *       DiagnosticProviderA's accept Evaluation activates it
 *       (claimable -> active) and lapses providerBClaimBurden
 *       (claimable -> lapsed) in the same `advance()` call; a second
 *       `advance()` then discharges the now-active burden normally.
 *       Flipping the Evaluation to reject leaves both burdens
 *       claimable — a deliberate no-op, not an error.
 * ================================================================
 */

enterprise specification ReferralClaimingScenario
    description: "Two diagnostic providers eligible to claim a single delegated referral; Provider A's accept Evaluation claims the referral, activating Provider A's burden and lapsing Provider B's claim opportunity"

party ReferringClinician
    description: "GP who places the diagnostic referral. Not itself a member of the claiming pool; the referral has already been delegated onward to the pool of eligible diagnostic providers by the time this scenario begins."

party DiagnosticProviderA
    description: "First diagnostic provider eligible to claim the referral. Submits the accept Evaluation that claims the referral."

party DiagnosticProviderB
    description: "Second diagnostic provider, equally eligible to claim the referral. Its claim opportunity lapses once Provider A claims first."

// ================================================================
// §6.2, §7.3, §7.7 — DIAGNOSTIC REFERRAL POOL COMMUNITY
// ================================================================

community DiagnosticReferralPoolCommunity
    description: "Community governing which of two eligible diagnostic providers claims and fulfils a single delegated referral"
    {
        objective: "Ensure the referred patient's diagnostic request is claimed and fulfilled by one of the eligible providers"
            satisfaction: any_discharged(referralClaimGroup)
            sub_objective providerAClaimTask: "Provider A may claim the referral"
                assigned_to role eligibleProviderA
            sub_objective providerBClaimTask: "Provider B may claim the referral"
                assigned_to role eligibleProviderB

        invariant equivalentProviderEligibility:
            "Both diagnostic providers are equally eligible to claim the referral; neither is preferred over the other"

        role eligibleProviderA
            description: "First eligible provider's role"
            {
                action claimReferralA {
                    description: "Provider A claims the referral, taking on fulfilment responsibility"
                    actor: eligibleProviderA
                    favoured_by_burden providerAClaimBurden
                }
            }

        role eligibleProviderB
            description: "Second eligible provider's role"
            {
                action claimReferralB {
                    description: "Provider B claims the referral, taking on fulfilment responsibility"
                    actor: eligibleProviderB
                    favoured_by_burden providerBClaimBurden
                }
            }

        lifecycle {
            establishing {
                implicit: true
                description: "Community is pre-existing; activated upon the referral being delegated to the pool of eligible providers"
            }
            changes {
                description: "Both eligible providers are fixed for the duration of this referral episode (membership_dynamic omitted: absence means false per grammar)"
            }
            terminating {
                on_objective_achieved: true
                description: "Community obligations concluded once either provider claims and fulfils the referral"
            }
        }
    }

// ================================================================
// §7.8.7, §7.8.8.1 — DEONTIC TOKENS
// ================================================================

// state: claimable (AM-60 grammar; this scenario is AM-63 — see DN_003).
// Backed by a real, tested mechanism (2026-08-24): a matching accept
// Evaluation unlocks claimable -> active for the accepting holder, with
// the sibling's claimable opportunity lapsing to 'lapsed' (AM-61 Kripke,
// AM-62 live engine).
burden providerAClaimBurden {
    for_action: "claimReferralA"
    state: claimable
    deadline: "4 hours from referral delegation"
    discharge_mode: eventual
    priority: high
    description: "Obligation on Provider A to claim and fulfil the referral, offered to the pool pending an acceptance evaluation"
}

burden providerBClaimBurden {
    for_action: "claimReferralB"
    state: claimable
    deadline: "4 hours from referral delegation"
    discharge_mode: eventual
    priority: high
    description: "Obligation on Provider B to claim and fulfil the referral, offered to the pool pending an acceptance evaluation"
}

// ================================================================
// §6.4.2, AM-27 — TOKEN GROUP
// ================================================================

token_group referralClaimGroup {
    member: providerAClaimBurden
    member: providerBClaimBurden
}

// ================================================================
// §7.10 — COMMITMENTS (backs both group members, satisfies V-16a)
// ================================================================

commitment providerAClaimCommitment {
    by: DiagnosticProviderA
    obligation: "Claim and fulfil the referral if it becomes available to this provider"
    creates_burden: providerAClaimBurden
    description: "Provider A commits to claiming the referral, contingent on the pool's claiming mechanism"
}

commitment providerBClaimCommitment {
    by: DiagnosticProviderB
    obligation: "Claim and fulfil the referral if it becomes available to this provider"
    creates_burden: providerBClaimBurden
    description: "Provider B commits to claiming the referral, contingent on the pool's claiming mechanism"
}

// ================================================================
// §6.6.7 — EVALUATION (AM-60 grammar — see DN_003). Backed
// by a real engine mechanism (2026-08-24): the structured accept form
// (target_token + result_code, both new grammar) actually unlocks the
// claimable -> active transition for DiagnosticProviderA, and lapses
// providerBClaimBurden. See tests/test_referral_claiming_scenario.py
// for the empirical verification (Layer 3 live engine and Layer 4
// Kripke model, both checked directly, not merely asserted).
// ================================================================

evaluation providerAAcceptsReferral {
    by: DiagnosticProviderA
    of_target: providerAClaimBurden
    result: accept
    description: "Provider A accepts and claims the referral"
}
