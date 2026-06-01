/*
 * ================================================================
 * ecommerce_scenario.el
 * ODP Enterprise Language DSL — e-commerce governance scenario
 *
 * Source: ISO/IEC 15414:2015 Annex B (canonical ODP-EL example)
 *
 * Scenario: e.com widget e-commerce system
 * Covers: community, roles, commitment, delegation, authorization,
 *         declaration, prescription, evaluation, accountability chain
 *
 * Delegation chain:
 *   CFO → eSystem → pricingService
 *
 * Key obligations:
 *   paymentObligation    — customer committed to pay on order placement
 *   deliveryObligation   — e.com committed to deliver on payment
 *   restockingObligation — declared on late cancellation
 *
 * Layer 4 verification question:
 *   Does AF(discharged:deliveryObligation) hold?
 *
 * Expected answer: YES — delivery is a strict obligation
 *   once payment is confirmed
 * ================================================================
 */

enterprise specification ECommerceGovernanceSystem
    description: "Enterprise governance specification for e.com widget e-commerce system"
    field_of_application: "Trade and electronic business transactions"
    scope: "Order placement, payment, delivery, pricing, and inventory management"


// ================================================================
// §6.6.1 / §6.6.8 — PARTIES AND AGENTS
// Annex B.1.9.5
// ================================================================

party ECom
    description: "e.com — root principal; ultimately accountable for all e-commerce operations"
    {
        principal_of eSystem
    }

party CFO
    description: "Chief Financial Officer of e.com; sets pricing policy and delegates to eSystem"
    {
        principal_of eSystem
        principal_of pricingService
    }

agent eSystem
    description: "e-commerce system — automated agent handling orders, payments, and catalogue"
    {
        delegated_from ECom
            duration: "operational period"
        delegated_from CFO
            duration: "operational period"
        principal_of pricingService
        principal_of shippingSubsystem
        principal_of purchasingSubsystem
    }

agent pricingService
    description: "Federated pricing service — agent of CFO for price setting during evenings and weekends"
    {
        delegated_from eSystem
            duration: "evenings and weekends"
        sub_delegation_allowed: false
    }

agent shippingSubsystem
    description: "Shipping subsystem — responsible for order delivery"
    {
        delegated_from eSystem
            duration: "order fulfillment period"
    }

agent purchasingSubsystem
    description: "Purchasing subsystem — handles supplier bid evaluation and inventory replenishment"
    {
        delegated_from eSystem
            duration: "operational period"
    }

agent webBrowser
    description: "Customer web browser — agent of customer for order placement"
    {
        delegated_from Customer
            duration: "browsing session"
    }


// ================================================================
// §6.2 — COMMUNITY
// Annex B.1.5
// ================================================================

community eCommerceCommunity {
    description: "Community enabling exchange of goods and money between e.com and its customers"
    objective: "Enable exchange of widgets for money to the satisfaction of all parties"

    role catalogueServer {
        description: "Role of eSystem serving product catalogue and pricing to customers"
        actions: ["displayWelcomePage", "displayCataloguePage", "searchWidgets", "offerPrice"]
    }

    role orderTaker {
        description: "Role of eSystem accepting and processing customer orders"
        actions: ["acceptOrder", "processPayment", "confirmOrder", "cancelOrder"]
    }

    role customer {
        description: "Role fulfilled by persons or automated systems placing orders"
        actions: ["placeOrder", "makePayment", "cancelOrder"]
        -- An auditor may not fulfil the customer role (Annex B.1.5.4)
        excludes: auditor
    }

    role supplier {
        description: "Role fulfilled by widget suppliers responding to procurement bids"
        actions: ["submitBid", "fulfillOrder"]
    }

    role auditor {
        description: "Role fulfilled by e.com employees performing audit functions"
        actions: ["auditTransaction", "reviewCompliance"]
        excludes: customer
    }

    role eComManager {
        description: "Role fulfilled by e.com managers; may also fulfil customer role"
        actions: ["approveCredit", "overridePolicy"]
    }
}

community inventoryMaintenanceCommunity {
    description: "Community managing widget inventory replenishment through supplier bids"
    objective: "Maintain adequate widget inventory through competitive procurement"

    role procurementAgent {
        description: "Role of purchasingSubsystem issuing bid requests and evaluating responses"
        actions: ["issueBidRequest", "evaluateBid", "acceptBid", "rejectBid"]
    }

    role supplierSystem {
        description: "Role fulfilled by supplier automated systems submitting bids"
        actions: ["receiveBidRequest", "submitBid", "confirmDelivery"]
    }
}


// ================================================================
// §6.4 — DEONTIC TOKENS
// Annex B.1.9.2, B.1.9.3
// ================================================================

burden paymentObligation {
    for_action: "make_payment"
    state: active
    deadline: "invoice due date"
    discharge_mode: strict
    priority: critical
    description: "Obligation of customer to pay for goods when timely delivered — created by order commitment"
}

burden deliveryObligation {
    for_action: "deliver_order"
    state: active
    deadline: "agreed delivery date"
    discharge_mode: strict
    priority: critical
    description: "Obligation of e.com to deliver widget once payment is confirmed"
}

burden restockingObligation {
    for_action: "pay_restocking_charge"
    state: pending
    deadline: "thirty days from cancellation"
    discharge_mode: eventual
    priority: normal
    description: "5% restocking charge declared on cancellation within 24 hours of scheduled shipping — applies when accounts receivable exceed 60 days"
}

burden inventoryReplenishmentObligation {
    for_action: "replenish_inventory"
    state: active
    deadline: "reorder point"
    discharge_mode: eventual
    priority: normal
    description: "Obligation of purchasingSubsystem to issue bid requests when inventory falls below threshold"
}

permit priceSettingPermit {
    description: "Permission for eSystem to set prices during evenings and weekends — delegated by CFO"
    state: active
}

permit subDelegationPermit {
    description: "Permission for eSystem to further delegate price-setting to pricingService — delegated by CFO"
    state: active
}

embargo auditorCustomerEmargo {
    description: "Prohibition on an object fulfilling both auditor and customer roles simultaneously"
    state: active
}


// ================================================================
// §6.6.2 — COMMITMENT
// Annex B.1.9.2
// ================================================================

commitment OrderCommitment {
    -- Placing an order commits the customer firm to pay for goods when timely delivered
    by: Customer
    creates_burden: paymentObligation
    description: "Order placement by customer or their agent commits the customer to payment"
}

commitment DeliveryCommitment {
    -- e.com commits to deliver when order is accepted and payment confirmed
    by: ECom
    creates_burden: deliveryObligation
    description: "Order acceptance by e.com commits e.com to delivery"
}

commitment PriceOfferCommitment {
    -- Posting a changed price by pricingService constitutes an offer by e.com to sell at that price
    by: ECom
    creates_burden: deliveryObligation
    description: "Price posting by agent of e.com constitutes an offer; acceptance creates delivery obligation"
}


// ================================================================
// §6.6.5 — DECLARATION
// Annex B.1.9.3
// ================================================================

declaration RestockingChargeDeclaration {
    -- e-system automatically declares restocking charge on late cancellation
    by: eSystem
    creates_burden: restockingObligation
    description: "Cancellation within 24 hours of scheduled shipping date triggers automatic 5% restocking charge declaration"
}


// ================================================================
// §6.6.4 / §6.6.6 — DELEGATION AND AUTHORIZATION
// Annex B.1.9.4, B.1.9.5
// ================================================================

delegation PriceSettingDelegation {
    -- CFO delegates price-setting authorization to eSystem
    from: CFO
    to: eSystem
    transfers_burden: priceSettingPermit
    sub_delegation_allowed: true
    description: "CFO delegates authorization to set prices during evenings and weekends to eSystem"
}

delegation PricingServiceDelegation {
    -- eSystem sub-delegates price-setting to federated pricingService
    from: eSystem
    to: pricingService
    transfers_burden: priceSettingPermit
    sub_delegation_allowed: false
    description: "eSystem delegates price-setting to federated pricingService pursuant to CFO authorization"
}

delegation ContractCancellationDelegation {
    -- eSystem delegated authorization to cancel contracts with suppliers or customers
    from: ECom
    to: eSystem
    sub_delegation_allowed: false
    description: "eSystem may automatically cancel orders subject to contract terms"
}

authorization CreditPolicyAuthorization {
    -- creditHistoryEvaluationSubsystem authorized to change some credit policy rules
    by: CFO
    for_action: "modify_credit_policy_rules"
    description: "CFO authorizes creditHistoryEvaluationSubsystem to adjust credit rules within policy bounds"
}


// ================================================================
// §6.6.7 — EVALUATION
// Annex B.1.9.6
// ================================================================

declaration BidEvaluationDeclaration {
    -- eSystem assigns relative status to each supplier bid
    by: eSystem
    description: "eSystem evaluates bids using price, delivery terms, supplier on-time performance, and quality records"
}


// ================================================================
// §6.6.3 — PRESCRIPTION (POLICY)
// Annex B.1.9.7
// ================================================================

community creditPolicyCommunity {
    description: "Community governing credit granting rules for established customers"
    objective: "Ensure credit is granted only within CFO-approved policy bounds"

    role creditPolicyManager {
        description: "Role of CFO setting credit policy rules"
        actions: ["setCreditRule", "approveCreditPolicy"]
    }

    role creditEvaluator {
        description: "Role of creditHistoryEvaluationSubsystem applying and adjusting credit rules"
        actions: ["evaluateCreditHistory", "adjustCreditRule"]
    }
}


// ================================================================
// §6.3.8 / §7.8.6 — VIOLATION RESPONSE
// Annex B.1.6.3
//
// NOTE: ViolationResponseDecl is the primary known gap in the v2
// grammar (AM-15 in el_grammar_amendments.md). The three constructs
// below specify the intended syntax and semantics. Once AM-15 is
// implemented in el_grammar.tx, these will parse correctly.
//
// Three violation types from Annex B.1.6.3:
//   1. Permit violation — securitySubsystem blocks auditor access
//   2. Embargo violation — databaseAdministrator displays salary record
//   3. Burden violation  — shippingSubsystem fails same-day shipment
// ================================================================

violation_response AuditorAccessViolation {
    -- §6.3.8: securitySubsystem preventing auditor from examining a record
    -- violates the rule that auditor holds a permit to examine any record
    triggered_by: auditorExaminationPermit
    violated_by: securitySubsystem
    condition: "securitySubsystem blocks auditor record examination"
    violation_type: permit_violation
    response: "log_violation_and_alert_CIO"
    notifies: CIO
    priority: critical
    description: "securitySubsystem action blocking auditor record access violates auditor authorization rule (B.1.7.2)"
}

violation_response SalaryDisplayViolation {
    -- §6.3.8: databaseAdministrator displaying salary record outside permitted roles
    -- violates the embargo that salary records may only be displayed for
    -- salary administrator, auditor, or manager of that employee
    triggered_by: salaryDisplayEmbargo
    violated_by: databaseAdministrator
    condition: "salary record displayed by role outside {salaryAdministrator, auditor, manager}"
    violation_type: embargo_violation
    response: "log_violation_revoke_session_alert_security"
    notifies: securitySubsystem
    priority: critical
    description: "Display of salary record by databaseAdministrator outside permitted roles violates prohibition rule (B.1.7.5)"
}

violation_response SameDayShipmentViolation {
    -- §6.3.8: shippingSubsystem failing to schedule same-day shipment
    -- for orders accepted before 4 PM where widgets are in stock
    -- violates the burden assigned by delegation from orderWidget speech act
    triggered_by: sameDayShipmentObligation
    violated_by: shippingSubsystem
    condition: "order accepted before 16:00 AND widget in stock AND shipment not scheduled same day"
    violation_type: burden_violation
    response: "escalate_to_fulfillmentDivisionExecutive_and_log_breach"
    notifies: fulfillmentDivisionExecutive
    priority: high
    description: "Failure by shippingSubsystem to schedule same-day shipment for pre-4PM in-stock orders violates obligation rule (B.1.7.3)"
}
