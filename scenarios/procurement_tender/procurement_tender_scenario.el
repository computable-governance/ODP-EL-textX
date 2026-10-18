/*
 * ================================================================
 * procurement_tender_scenario.el
 * ODP Enterprise Language DSL — a public-sector tender, from bid
 * claim to award and the first post-award clauses
 *
 * Purpose: a procurement scenario built only from constructs that run
 * on the current release. It covers:
 *   - claim-and-award: each bid is a claimable burden in an
 *     any_discharged group; the buyer's award issues an award notice
 *     permit; the winning supplier's acceptance claims its burden and
 *     the other bid lapses
 *   - panel sign-off as a strict burden, with a probity officer who may
 *     declare it violated once overdue, and "no award before sign-off"
 *     as an ordering constraint: the award action requires a permit
 *     that only the sign-off creates
 *   - incident notification: an eventual burden, triggered by the
 *     contractor's own incident report, deadline "24 hours"
 *   - subcontracting: a role action gated by a permit granted through an
 *     authorization, with an embargo activated on revocation
 *   - public liability cover, in two parts: at submission, a comparison
 *     precondition on the award against an amount policy; for the term,
 *     a standing duty on the winner, ended by performance of the contract
 *   - a tender addendum as a declarative prescription
 *
 * Limits of the current release this scenario runs into (see README.md):
 *   - the verifier does not model standing duties
 *     ([W-standing-not-modelled] on both cover duties)
 *   - a role cannot change hands while a specification runs, so there is
 *     no contractor role for the winner to join. Each bidder has its own
 *     role and holds its post-award duties from the start, as conditional
 *     commitments that only the award makes reachable
 *   - two engine behaviours shaped the award (see README.md): `effect
 *     destroy` discharges burdens only, so a single award is enforced by
 *     an embargo the award activates; and `effect create` grants a token
 *     active whatever its declared state, so post-award duties are held
 *     from the start rather than created at award
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
    for_action: "performContractA"
    state: claimable
    deadline: "30 days"
    discharge_mode: eventual
    priority: high
    description: "Supplier A's bid: deliver the contracted services if awarded, offered to the pool pending acceptance of an award"
}

burden supplierBContractBurden {
    for_action: "performContractB"
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

permit awardNoticeA {
    for_action: "performContractA"
    state: active
    description: "Notice of award to Supplier A; created by the award action"
}

permit awardNoticeB {
    for_action: "performContractB"
    state: active
    description: "Notice of award to Supplier B; created by the award action"
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
// WORKAROUND (effect create grants the token active; see docs/
// DSL_TOOLCHAIN_REFERENCE.md, Known Limitations): a triggered duty created
// at award would start its deadline at the award, not at the trigger. So
// each bidder holds its post-award duties from the start, as conditional
// commitments that only the award makes reachable. The cover duties below
// follow the same pattern. Not the intended pattern for duties that arise
// at award.

burden incidentNotificationBurdenA {
    for_action: "notifyIncidentA"
    state: pending
    deadline: "24 hours"
    triggered_by: incidentOccursA
    discharged_by: incidentNotifiedA
    discharge_mode: eventual
    priority: high
    description: "If awarded, Supplier A notifies the principal of any work health and safety incident within 24 hours"
}

burden incidentNotificationBurdenB {
    for_action: "notifyIncidentB"
    state: pending
    deadline: "24 hours"
    triggered_by: incidentOccursB
    discharged_by: incidentNotifiedB
    discharge_mode: eventual
    priority: high
    description: "If awarded, Supplier B notifies the principal of any work health and safety incident within 24 hours"
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
// Held from the start like the incident duties (same WORKAROUND), triggered by the bidder's
// own award event, and ended when that bidder performs the contract. One
// fact key per bidder ([W-standing-shared-fact]).

burden keepPublicLiabilityA {
    standing
    keeps: "Supplier A public liability cover" >= minPublicLiability
    ended_by: contractCompletedA
    state: pending
    triggered_by: awardedToA
    priority: high
    description: "If awarded, Supplier A keeps public liability cover of at least the policy minimum for the term of the contract"
}

burden keepPublicLiabilityB {
    standing
    keeps: "Supplier B public liability cover" >= minPublicLiability
    ended_by: contractCompletedB
    state: pending
    triggered_by: awardedToB
    priority: high
    description: "If awarded, Supplier B keeps public liability cover of at least the policy minimum for the term of the contract"
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
    event incidentOccursA
    event incidentNotifiedA
    event incidentOccursB
    event incidentNotifiedB
    event awardedToA
    event awardedToB
    event contractCompletedA
    event contractCompletedB

    invariant oneAward: "At most one bidder is awarded the contract"
    invariant awardAfterSignOff: "The contract is not awarded before the panel signs off its evaluation"

    on_join buyerRole transfer awardMadeEmbargo
    BuyerAgency fills buyerRole
    PanelChair fills evaluationPanelRole
    ProbityOfficer fills probityRole
    SupplierA fills bidderARole
    SupplierB fills bidderBRole

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
            effect create awardNoticeA to bidderARole
            effect activate awardMadeEmbargo
            emits: awardedToA
        }
        action awardToSupplierB {
            actor: buyerRole
            precondition: "Supplier B public liability cover at submission" >= minPublicLiability
            requires_permit awardPermit
            inhibited_by_embargo awardMadeEmbargo
            effect create awardNoticeB to bidderBRole
            effect activate awardMadeEmbargo
            emits: awardedToB
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

    role bidderARole
        description: "Filled by Supplier A"
    {
        action performContractA {
            actor: bidderARole
            requires_permit awardNoticeA
            favoured_by_burden supplierAContractBurden
            emits: contractCompletedA
        }
        action reportIncidentA {
            actor: bidderARole
            requires_permit awardNoticeA
            emits: incidentOccursA
        }
        action notifyIncidentA {
            actor: bidderARole
            favoured_by_burden incidentNotificationBurdenA
            emits: incidentNotifiedA
        }
        action subcontractCivilWorks {
            actor: bidderARole
            requires_permit awardNoticeA
            requires_permit subcontractApproval
            inhibited_by_embargo subcontractEmbargo
        }
    }

    role bidderBRole
        description: "Filled by Supplier B"
    {
        action performContractB {
            actor: bidderBRole
            requires_permit awardNoticeB
            favoured_by_burden supplierBContractBurden
            emits: contractCompletedB
        }
        action reportIncidentB {
            actor: bidderBRole
            requires_permit awardNoticeB
            emits: incidentOccursB
        }
        action notifyIncidentB {
            actor: bidderBRole
            favoured_by_burden incidentNotificationBurdenB
            emits: incidentNotifiedB
        }
    }

    applies minPublicLiability to role bidderARole
    applies minPublicLiability to role bidderBRole

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

commitment supplierANotifiesIncidents {
    by: SupplierA
    obligation: "If awarded, notify the principal of any work health and safety incident within 24 hours"
    creates_burden: incidentNotificationBurdenA
    principals_obligated: SupplierA
}

commitment supplierBNotifiesIncidents {
    by: SupplierB
    obligation: "If awarded, notify the principal of any work health and safety incident within 24 hours"
    creates_burden: incidentNotificationBurdenB
    principals_obligated: SupplierB
}

commitment supplierAKeepsCover {
    by: SupplierA
    obligation: "If awarded, keep public liability cover of at least the policy minimum for the term of the contract"
    creates_burden: keepPublicLiabilityA
    principals_obligated: SupplierA
}

commitment supplierBKeepsCover {
    by: SupplierB
    obligation: "If awarded, keep public liability cover of at least the policy minimum for the term of the contract"
    creates_burden: keepPublicLiabilityB
    principals_obligated: SupplierB
}

authorization subcontractApprovalForSupplierA {
    authority: BuyerAgency
    to_role: bidderARole
    grants_permit: subcontractApproval
    conditions: "Civil works package only, to the subcontractor named in Supplier A's bid"
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

violation_response lateIncidentNotificationA {
    on_violation_of: incidentNotificationBurdenA
    obligates: BuyerAgency
    response_kind: escalate
    creates_burden: incidentFollowUpBurden
    creates_burden_for_role: buyerRole
    description: "A late incident notification is escalated for review by the principal"
}

violation_response lateIncidentNotificationB {
    on_violation_of: incidentNotificationBurdenB
    obligates: BuyerAgency
    response_kind: escalate
    creates_burden: incidentFollowUpBurden
    creates_burden_for_role: buyerRole
    description: "A late incident notification is escalated for review by the principal"
}

violation_response coverLapseA {
    on_violation_of: keepPublicLiabilityA
    obligates: BuyerAgency
    response_kind: remediate
    creates_burden: coverLapseReviewBurden
    creates_burden_for_role: buyerRole
    description: "A reported lapse in Supplier A's cover obliges the principal to require it restored"
}

violation_response coverLapseB {
    on_violation_of: keepPublicLiabilityB
    obligates: BuyerAgency
    response_kind: remediate
    creates_burden: coverLapseReviewBurden
    creates_burden_for_role: buyerRole
    description: "A reported lapse in Supplier B's cover obliges the principal to require it restored"
}
