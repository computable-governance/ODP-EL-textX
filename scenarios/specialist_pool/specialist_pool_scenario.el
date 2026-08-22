/*
 * ================================================================
 * specialist_pool_scenario.el
 * ODP Enterprise Language DSL — collective obligation over
 * equivalent peers (any_discharged / SUPERSEDED demonstration)
 *
 * Purpose: a minimal, standalone scenario exercising the toolchain's
 * any_discharged collective-obligation semantics — Zoran Milosevic's
 * own formalization of a challenge the standard's supporting
 * literature (Linington/Milosevic/Tanaka/Vallecillo, "Building
 * Enterprise Systems with ODP") explicitly names as unsolved: "few
 * tool builders have yet risen to this challenge." Grounded in
 * §7.8.7 NOTE 6 (token cloning/pending-reversion over community
 * roles) as the closest standard mechanism, though this scenario's
 * two-equivalent-peer case is not itself a standard example.
 *
 * Peter Linington's own framing of this challenge (shared 2026-06-16,
 * confirmed as the passage motivating this whole line of work):
 * "it is much more difficult... to see what I am expected to do if I am
 * one of a number of equal members of a community and an obligation is
 * placed on the community. If the thing is not getting done, what
 * personal costs should I accept so that the whole group meets its
 * obligation? Why not leave it to one of the others to do it?" — the two
 * specialists' personal-cost framing below is a direct illustration of
 * exactly this question.
 *
 * Deliberately does NOT model either specialist's actual intention to
 * act or wait. Checked directly: ODP-EL's Declaration (§6.6.5) is a
 * performative that establishes a state of affairs under authorization
 * — not a private, behaviourally-inferable intention — and Commitment
 * (§6.6.2) creates an enforceable burden, the opposite of an
 * unaccountable intention. Neither fits. This is a confirmed gap in the
 * standard's vocabulary, not an oversight of this scenario — intention
 * remains open future work, pending a fuller treatment.
 *
 * Deliberately not a modification of referral_scenario.el or
 * gp_referral_scenario.el — those exercise all_discharged only, and
 * are heavily tested/demo-ready as-is (decision: keep them
 * untouched). AM-57 (2026-08-23) implemented the live-engine
 * mechanism; nothing exercised it end-to-end in a named scenario
 * until this file.
 *
 * Deliberately excludes triggered_by/state: pending on any group
 * member (see docs/CONCEPTS_INDEX.md, AM-57's masked-sibling gap) —
 * both consultResponseGroup members are plain state: active,
 * discharge_mode: eventual, so the live sibling-supersession
 * mechanism applies cleanly with no known gap in play.
 *
 * Token group:
 *   consultResponseGroup = { specialistAResponseBurden,
 *                            specialistBResponseBurden }
 *
 * Community objective:
 *   OnCallConsultCommunity: any_discharged(consultResponseGroup)
 *
 * Layer 4 verification questions (el_kripke.py) — VERIFY EMPIRICALLY,
 * do not just assert (see verification steps below):
 *   Q1: EF(objective_satisfied:OnCallConsultCommunity)?
 *       Expected YES — either specialist discharging satisfies it.
 *   Q2: does discharging specialistAResponseBurden supersede
 *       specialistBResponseBurden in the resulting world (P6b)?
 *       Expected YES.
 * ================================================================
 */

enterprise specification SpecialistPoolScenario
    description: "Two equivalent on-call specialists; either accepting an urgent consult satisfies the community, and any_discharged/SUPERSEDED honestly relieves the other's obligation"

party SpecialistOnCallA
    description: "First on-call specialist. Just came off a demanding overnight shift — accepting this consult carries a real personal cost (further postponed rest)."

party SpecialistOnCallB
    description: "Second on-call specialist, equally qualified. Currently has spare capacity — accepting this consult carries comparatively little personal cost right now."

// ================================================================
// §6.2, §7.3, §7.7 — ON-CALL CONSULT COMMUNITY
// ================================================================

community OnCallConsultCommunity
    description: "Community governing urgent specialist consult response, where either of two equivalent on-call specialists may respond"
    {
        objective: "Ensure the referred patient receives specialist assessment from an on-call specialist"
            satisfaction: any_discharged(consultResponseGroup)
            sub_objective specialistAAcceptTask: "Specialist A may accept the urgent consult"
                assigned_to role onCallSpecialistA
            sub_objective specialistBAcceptTask: "Specialist B may accept the urgent consult"
                assigned_to role onCallSpecialistB

        invariant equivalentPeerCapability:
            "Both on-call specialists hold equivalent qualification to accept the consult; neither is preferred over the other"

        role onCallSpecialistA
            description: "First on-call specialist's role"
            {
                action acceptConsultA {
                    description: "Specialist A accepts the urgent consult request"
                    actor: onCallSpecialistA
                    favoured_by_burden specialistAResponseBurden
                }
            }

        role onCallSpecialistB
            description: "Second on-call specialist's role"
            {
                action acceptConsultB {
                    description: "Specialist B accepts the urgent consult request"
                    actor: onCallSpecialistB
                    favoured_by_burden specialistBResponseBurden
                }
            }

        lifecycle {
            establishing {
                implicit: true
                description: "Community is pre-existing; activated upon urgent consult request"
            }
            changes {
                description: "Both on-call specialists are fixed for the duration of this consult episode (membership_dynamic omitted: absence means false per grammar, a bare presence flag with no false form)"
            }
            terminating {
                on_objective_achieved: true
                description: "Community obligations concluded once either specialist accepts the consult"
            }
        }
    }

// ================================================================
// §7.8.7, §7.8.8.1 — DEONTIC TOKENS
// ================================================================

// discharge_mode: eventual, no triggered_by — deliberately kept clear
// of AM-57's masked-sibling (pending) gap, see header comment above.
burden specialistAResponseBurden {
    for_action: "acceptConsultA"
    state: active
    deadline: "2 hours from consult request"
    discharge_mode: eventual
    priority: high
    description: "Obligation on Specialist A to accept and respond to the urgent consult"
}

burden specialistBResponseBurden {
    for_action: "acceptConsultB"
    state: active
    deadline: "2 hours from consult request"
    discharge_mode: eventual
    priority: high
    description: "Obligation on Specialist B to accept and respond to the urgent consult"
}

// ================================================================
// §6.4.2, AM-27 — TOKEN GROUP
// ================================================================

token_group consultResponseGroup {
    member: specialistAResponseBurden
    member: specialistBResponseBurden
}

// ================================================================
// §7.10 — COMMITMENTS (backs both group members, satisfies V-16a)
// ================================================================

commitment specialistAResponseCommitment {
    by: SpecialistOnCallA
    obligation: "Accept and respond to the urgent consult request"
    creates_burden: specialistAResponseBurden
    description: "Specialist A commits to accepting the urgent consult if called upon"
}

commitment specialistBResponseCommitment {
    by: SpecialistOnCallB
    obligation: "Accept and respond to the urgent consult request"
    creates_burden: specialistBResponseBurden
    description: "Specialist B commits to accepting the urgent consult if called upon"
}
