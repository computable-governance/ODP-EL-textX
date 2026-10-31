/*
 * ================================================================
 * procurement_tender_scenario.el
 * ODP Enterprise Language DSL — a public-sector tender, from bid
 * claim to award and the first post-award clauses
 *
 * Purpose: a procurement scenario built only from constructs that run
 * on the current release. It covers:
 *   - claim-and-award: each bid is a claimable burden in an
 *     any_discharged group; the buyer's award makes that bidder the
 *     contractor; the winning supplier's acceptance claims its burden and
 *     the other bid lapses
 *   - panel sign-off as a strict burden, with a probity officer who may
 *     declare it violated once overdue, and "no award before sign-off"
 *     as an ordering constraint: the award action requires a permit
 *     that only the sign-off creates
 *   - the contractor role: the award fills it with the winner (effect
 *     fill), and the contractor's duties come with the role (on_join), so
 *     they are written once for any number of bidders. Neither the panel
 *     nor the probity officer may fill it (excludes_role)
 *   - incident notification: an eventual burden, triggered by the
 *     contractor's own incident report, deadline "24 hours"
 *   - subcontracting: a role action gated by a permit granted through an
 *     authorization, with an embargo activated on revocation
 *   - public liability cover, in two parts: at submission, a comparison
 *     precondition on the award against an amount policy; for the term,
 *     a standing duty on the contractor, ended when the buyer certifies
 *     completion
 *   - a tender addendum as a declarative prescription
 *
 * Limits of the current release this scenario runs into (see README.md):
 *   - the verifier does not model standing duties
 *     ([W-standing-not-modelled] on the cover duty)
 *   - the verifier does not model a role filled by an action
 *     ([W-fill-not-modelled] on contractorRole), so it has no obligation
 *     for the contractor's incident duty ([W-burden-not-modelled])
 *   - a role is filled once and not left: there is no act to terminate
 *     the contractor and fill the role again
 *   - `effect destroy` discharges burdens only, so a single award is
 *     enforced by an embargo the award activates
 *
 * All parties and values are illustrative.
 * Contributed by Andy Bond, BIDLOGIQ Pty Ltd.
 * ================================================================
 */

enterprise specification ProcurementTenderScenario
    description: "A buyer agency runs a tender with two bidders: an evaluation panel signs off, the buyer awards, the winner accepts, and post-award incident notification and subcontracting clauses apply"

// ================================================================
// §6.6.1 — PARTIES
// Per the maintainer's guidance, the panel chair and the suppliers are
// parties filling roles. None is modelled as an agent: no delegation of
// authority to staff is represented here.
// ================================================================

party BuyerAgency
    description: "Government agency issuing the tender; the principal"

party PanelChair
    description: "Chair of the evaluation panel, filling the panel role"

party ProbityOfficer
    description: "Independent probity officer; may declare an overdue panel sign-off violated"

party SupplierA
    description: "First bidder; proposes to subcontract civil works"

party SupplierB
    description: "Second bidder"

// ================================================================
// §6.4 — DEONTIC TOKENS
// ================================================================

// ---- Claim-and-award core -------------------------------------

burden supplierAContractBurden {
    for_action: "performContract"
    state: claimable
    deadline: "30 days"
    discharge_mode: eventual
    priority: high
    description: "Supplier A's bid: deliver the contracted services if awarded, offered to the pool pending acceptance of an award"
}

burden supplierBContractBurden {
    for_action: "performContract"
    state: claimable
    deadline: "30 days"
    discharge_mode: eventual
    priority: high
    description: "Supplier B's bid: deliver the contracted services if awarded, offered to the pool pending acceptance of an award"
}

token_group contractGroup {
    member: supplierAContractBurden
    member: supplierBContractBurden
}

burden panelSignOffBurden {
    for_action: "signOffEvaluation"
    state: pending
    deadline: "10 working days"
    triggered_by: tenderClosed
    discharged_by: evaluationSignedOff
    discharge_mode: strict
    priority: critical
    description: "The panel signs off its evaluation once the tender closes; the process waits on it"
}

permit awardPermit {
    for_action: "award"
    state: active
    description: "Authority to award the contract; created for the principal only by the panel's sign-off"
}

// WORKAROUND (effect destroy acts on burdens only; see docs/
// DSL_TOOLCHAIN_REFERENCE.md, Known Limitations): destroying awardPermit
// after one award would do nothing, so the award activates this embargo
// instead. Not the intended pattern for a single award.
embargo awardMadeEmbargo {
    state: pending
    description: "Once one award is made, no further award; activated by the award action"
}

permit signOffDeclarationPermit {
    for_action: "declareSignOffOverdue"
    state: active
    description: "Declare panelSignOffBurden violated once its deadline has passed"
}

burden reconvenePanelBurden {
    for_action: "reconvenePanel"
    state: active
    deadline: "5 working days"
    discharge_mode: eventual
    priority: critical
    description: "The principal reconvenes or replaces the panel after an overdue sign-off"
}

// ---- Incident notification ------------------------------------
// Granted to the contractor when the award fills contractorRole (on_join),
// in its declared state: pending until the contractor reports an incident,
// so the deadline runs from the incident, not from the award.

burden incidentNotificationBurden {
    for_action: "notifyIncident"
    state: pending
    deadline: "24 hours"
    triggered_by: incidentOccurs
    discharged_by: incidentNotified
    discharge_mode: eventual
    priority: high
    description: "The contractor notifies the principal of any work health and safety incident within 24 hours"
}

burden incidentFollowUpBurden {
    for_action: "reviewLateNotification"
    state: active
    deadline: "5 working days"
    discharge_mode: eventual
    priority: normal
    description: "The principal reviews a late incident notification with the contractor"
}

// ---- Public liability cover for the term (2.1.0 standing duties) ----
// Granted to the contractor when the award fills contractorRole (on_join),
// active from that tick, and ended when the buyer certifies completion.
// One duty and one fact key, whoever wins.

burden keepPublicLiability {
    standing
    keeps: "Contractor public liability cover" >= minPublicLiability
    ended_by: contractCompleted
    state: active
    priority: high
    description: "The contractor keeps public liability cover of at least the policy minimum for the term of the contract"
}

burden coverLapseReviewBurden {
    for_action: "reviewCoverLapse"
    state: active
    deadline: "5 working days"
    discharge_mode: eventual
    priority: high
    description: "The principal requires the contractor to restore its cover after a reported lapse"
}

// ---- Subcontracting -------------------------------------------

permit subcontractApproval {
    for_action: "subcontractCivilWorks"
    state: active
    description: "Prior written approval to subcontract the civil works package"
}

embargo subcontractEmbargo {
    for_action: "subcontractCivilWorks"
    state: pending
    description: "No subcontracting of the civil works once approval is withdrawn"
}

// ================================================================
// §6.5, §7.9 — POLICIES (declarative in the current release)
// ================================================================

policy minPublicLiability : amount {
    description: "Minimum public liability cover: held at submission (checked at award) and kept for the term"
    initial_value: 20000000 AUD
    envelope { set of [10000000 AUD, 20000000 AUD, 50000000 AUD] }
}

// ================================================================
// §7.8 — COMMUNITY
// ================================================================

contract community TenderCommunity
    description: "One tender, from close of bids to the first post-award obligations"
{
    objective: "Award the contract to one compliant bidder and have it performed"
        satisfaction: any_discharged(contractGroup)

    event tenderClosed
    event evaluationSignedOff
    event incidentOccurs
    event incidentNotified
    event contractCompleted

    invariant oneAward: "At most one bidder is awarded the contract"
    invariant awardAfterSignOff: "The contract is not awarded before the panel signs off its evaluation"

    // Conflict of interest: whoever evaluates the bids or oversees the
    // evaluation's probity may not become the contractor (§7.8.2 NOTE 5).
    assignment_policy for contractorRole {
        excludes_role evaluationPanelRole
        excludes_role probityRole
    }

    on_join buyerRole transfer awardMadeEmbargo
    on_join contractorRole transfer incidentNotificationBurden
    on_join contractorRole transfer keepPublicLiability
    BuyerAgency fills buyerRole
    PanelChair fills evaluationPanelRole
    ProbityOfficer fills probityRole

    role buyerRole
        description: "The buyer agency"
    {
        action closeTender {
            actor: buyerRole
            emits: tenderClosed
        }
        action awardToSupplierA {
            actor: buyerRole
            precondition: "Supplier A public liability cover at submission" >= minPublicLiability
            requires_permit awardPermit
            inhibited_by_embargo awardMadeEmbargo
            effect fill contractorRole with SupplierA
            effect activate awardMadeEmbargo
        }
        action awardToSupplierB {
            actor: buyerRole
            precondition: "Supplier B public liability cover at submission" >= minPublicLiability
            requires_permit awardPermit
            inhibited_by_embargo awardMadeEmbargo
            effect fill contractorRole with SupplierB
            effect activate awardMadeEmbargo
        }
        action reconvenePanel {
            actor: buyerRole
            favoured_by_burden reconvenePanelBurden
        }
        action reviewLateNotification {
            actor: buyerRole
            favoured_by_burden incidentFollowUpBurden
        }
        action reviewCoverLapse {
            actor: buyerRole
            favoured_by_burden coverLapseReviewBurden
        }
        action certifyCompletion {
            actor: buyerRole
            emits: contractCompleted
        }
    }

    role evaluationPanelRole
        description: "The evaluation panel, through its chair"
    {
        action signOffEvaluation {
            actor: evaluationPanelRole
            favoured_by_burden panelSignOffBurden
            emits: evaluationSignedOff
            effect create awardPermit to buyerRole
        }
    }

    role probityRole
        description: "The probity officer: declares, never evaluates"
    {
        action declareSignOffOverdue {
            actor: probityRole
            requires_permit signOffDeclarationPermit
            declares_violation_of panelSignOffBurden
        }
    }

    role contractorRole
        description: "Filled by the winning bidder when the award is made"
    {
        action performContract {
            actor: contractorRole
            favoured_by_burden supplierAContractBurden
            favoured_by_burden supplierBContractBurden
        }
        action reportIncident {
            actor: contractorRole
            emits: incidentOccurs
        }
        action notifyIncident {
            actor: contractorRole
            favoured_by_burden incidentNotificationBurden
            emits: incidentNotified
        }
        action subcontractCivilWorks {
            actor: contractorRole
            requires_permit subcontractApproval
            inhibited_by_embargo subcontractEmbargo
        }
    }

    applies minPublicLiability to role contractorRole

    lifecycle {
        establishing {
            implicit: true
            description: "The community exists from publication of the tender; this scenario starts at close of bids"
        }
        terminating {
            on_objective_achieved: true
            description: "Ends when the awarded contract is performed"
        }
    }
}

// ================================================================
// §7.10 — ACCOUNTABILITY
// ================================================================

commitment supplierABid {
    by: SupplierA
    obligation: "Deliver the contracted services if awarded the contract"
    creates_burden: supplierAContractBurden
    description: "Supplier A's bid submission"
}

commitment supplierBBid {
    by: SupplierB
    obligation: "Deliver the contracted services if awarded the contract"
    creates_burden: supplierBContractBurden
    description: "Supplier B's bid submission"
}

commitment buyerEvaluatesBids {
    by: BuyerAgency
    obligation: "Evaluate the bids and sign off the evaluation before any award"
    creates_burden: panelSignOffBurden
    principals_obligated: BuyerAgency
}

delegation evaluationToPanel {
    from: BuyerAgency
    to: PanelChair
    obligation: "Evaluate the bids and sign off the evaluation"
    transfers_burden: panelSignOffBurden
}

authorization probityDeclarationAuthority {
    authority: BuyerAgency
    to_agent: ProbityOfficer
    grants_permit: signOffDeclarationPermit
    conditions: "Declare only an overdue panel sign-off, judged against the calendar"
}

authorization subcontractApprovalForContractor {
    authority: BuyerAgency
    to_role: contractorRole
    grants_permit: subcontractApproval
    conditions: "Civil works package only, to the subcontractor named in the winning bid"
    revocable: true
    on_revocation: activate subcontractEmbargo
}

// The award is accepted at runtime, not declared here: the accepting
// supplier's claim (el_runtime Runtime.claim()) is a live accept
// Evaluation by the holder of the claimable burden. Writing a spec-level
// `evaluation ... result: accept` would fix the winner in the
// specification itself.

prescription tenderAddendum1 {
    by: BuyerAgency
    establishes_rule: "Addendum 1: the closing date is extended by 5 working days"
    description: "Declarative only in the current release: the engine does not change existing tokens or deadlines"
}

violation_response overdueSignOff {
    on_violation_of: panelSignOffBurden
    obligates: BuyerAgency
    response_kind: escalate
    creates_burden: reconvenePanelBurden
    creates_burden_for_role: buyerRole
    description: "An overdue panel sign-off, once declared, obliges the principal to reconvene or replace the panel"
}

violation_response lateIncidentNotification {
    on_violation_of: incidentNotificationBurden
    obligates: BuyerAgency
    response_kind: escalate
    creates_burden: incidentFollowUpBurden
    creates_burden_for_role: buyerRole
    description: "A late incident notification is escalated for review by the principal"
}

violation_response coverLapse {
    on_violation_of: keepPublicLiability
    obligates: BuyerAgency
    response_kind: remediate
    creates_burden: coverLapseReviewBurden
    creates_burden_for_role: buyerRole
    description: "A reported lapse in the contractor's cover obliges the principal to require it restored"
}
