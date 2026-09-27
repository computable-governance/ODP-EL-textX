enterprise specification ExternalAgentAccessScenario
    description: "Tier-1 terms of engagement: a provider's unilateral conditions for any external AI agent calling its FHIR service"
    field_of_application: "Digital health; external AI agents interacting with a provider FHIR endpoint"
    scope: "Security policies, normative policies and deontic tokens in one specification (worked example, draft)"

/*
 * Motivation: the 2026 Medicare portal incident. An external agent with no
 * relationship to the resource owner reached a public-facing portal, worked
 * around refusals, and the operator notified the owner months later via a
 * public mailbox.
 *
 * Tier 1 (this file): NO federation. The provider's domain unilaterally
 * establishes a contract community. Filling a role in it is the only way in,
 * and filling the role binds the filler to the community's contract
 * (all communities are contracts, ODP Part 2 §11.2.1).
 * Tier 2 (not here): a negotiated contract federation for known partners.
 *
 * Three kinds of policy appear side by side:
 *   policy           security policies (identity, authorisation, audit),
 *                    enforcement policed pessimistic = preventive (compelled)
 *                    or policed optimistic = detect-and-correct (detectable)
 *   normative_policy external instruments (ISM, Privacy Act, access terms)
 *   burden/permit/embargo  the deontic content that binds role fillers
 *
 * GAP markers flag what the current toolchain cannot yet check.
 */

// ── Enterprise objects ───────────────────────────────────────────────────────

party ProviderOrg
    description: "Health provider operating the FHIR service; controlling object of its domain"

party ProviderSecurityContact
    description: "Designated incident contact (a named function, not a public mailbox)"

resource_object ProviderFHIRService
    description: "Provider FHIR R4 endpoint (eRequesting ServiceRequest, Patient read)"

agent ProviderAPIGateway
    description: "Inbound gateway in front of the FHIR service; the policy enforcement point, acting as the provider's agent"
{
    delegated_from ProviderOrg
}

// AM-115: the declarer. An automated watchdog evaluates each strict burden
// against wall-clock time and, once its deadline has passed undischarged,
// declares it violated (§6.6.7 evaluation, then §6.6.5 declaration).
agent ProviderViolationWatchdog
    description: "Automated watchdog: declares an overdue strict burden violated; its health is monitored by operations tooling"
{
    delegated_from ProviderOrg
}

party ProviderSecurityManager
    description: "Security manager: investigates gateway failures and handles escalated reviews"

party VendorOrg
    description: "Supplier of an AI referral agent; accountable principal"
{
    principal_of VendorReferralAgent
}

agent VendorReferralAgent
    description: "External AI agent submitting referrals on the vendor's behalf"
{
    delegated_from VendorOrg
}

// ── Deontic tokens ───────────────────────────────────────────────────────────

permit serviceRequestSubmitPermit {
    for_action: "submitServiceRequest"
    state: active
    description: "Create ServiceRequest resources in the provider's eRequesting endpoint"
}

permit patientLookupPermit {
    for_action: "readPatientDemographics"
    state: active
    description: "Read Patient demographics needed to address a referral, nothing else"
}

// Default-deny made explicit: anything outside the two permits.
// GAP-1: embargo carries no domain scope (CONCEPTS_INDEX open finding);
// its force is implicitly the provider's domain only.
embargo outsideScopeEmbargo {
    for_action: "access_unlisted_resource"
    state: active
    description: "No access to any resource or operation not covered by a permit"
}

// The Medicare lesson: a refusal is final. After a refusal, the agent may not
// seek an alternative route to the same data.
embargo noCircumventionEmbargo {
    for_action: "retryByOtherRoute"
    state: pending
    triggered_by: accessRefused
    description: "Once refused, no alternative path to the same data (different endpoint, proxy, third-party service)"
}

// Compelled: discharged by the gateway in the same step as the refusal.
// AM-115: if it is not, the refusal freezes the community (strict); once
// the deadline has passed, the watchdog declares the burden violated,
// which ends the freeze and fires unrecordedRefusalResponse.
burden refusalRecordBurden {
    for_action: "recordRefusal"
    state: pending
    deadline: "5 minutes"
    triggered_by: accessRefused
    discharged_by: refusalRecorded
    discharge_mode: strict
    priority: critical
    description: "Every refusal is written to the provider-held, hash-chained log"
}

// Detectable: a human review with a deadline.
// GAP-4: deadline resolves to abstract verifier steps, not wall-clock time.
burden refusalReviewBurden {
    for_action: "reviewRefusal"
    state: pending
    deadline: "1 day"
    triggered_by: refusalRecorded
    discharged_by: refusalReviewed
    discharge_mode: eventual
    priority: high
    description: "Security contact reviews each recorded refusal"
}

// The notification the Medicare case lacked. Discharged only by the
// designated contact's acknowledgement: an email to a public inbox does not count.
burden incidentNotificationBurden {
    for_action: "notifyIncident"
    state: pending
    deadline: "72 hours"
    triggered_by: vendorIncidentDetected
    discharged_by: incidentAcknowledged
    discharge_mode: eventual
    priority: critical
    description: "Vendor notifies the provider's designated contact of any incident involving its agent"
}

// AM-115: the declarer's authority and duty (held by declarerRole).
permit violationDeclarationPermit {
    for_action: "declareRefusalRecordViolation"
    state: active
    description: "Declare refusalRecordBurden violated once its deadline has passed"
}

// The declarer's own duty is only detectable: nothing in this specification
// declares the watchdog's failure. The regress ends in a mechanism, an
// automated watchdog whose health is monitored by operations tooling.
// Held by declarerRole, never granted or activated at runtime (GAP-6).
burden declarationDutyBurden {
    for_action: "declareRefusalRecordViolation"
    state: pending
    deadline: "5 minutes"
    discharge_mode: eventual
    priority: critical
    description: "Declare an overdue refusalRecordBurden violated within 5 minutes of its deadline"
}

// Prohibitions on the declarer, enforced by declare_violation() (a
// declaration against them is refused, not only monitored). Held by
// declarerRole; their for_action names no action, so they block nothing
// in the engine themselves.
embargo earlyDeclarationEmbargo {
    for_action: "declareBeforeDeadline"
    state: active
    description: "No declaration before the burden's deadline has passed"
}

embargo selfDeclarationEmbargo {
    for_action: "declareOwnBurden"
    state: active
    description: "No declaration of a burden the declarer holds"
}

embargo dischargeDeclarationEmbargo {
    for_action: "declareDischarged"
    state: active
    description: "A declaration can only make a burden violated, never discharged"
}

// AM-115: created by unrecordedRefusalResponse for gatewayFailureInvestigatorRole.
burden gatewayInvestigationBurden {
    for_action: "investigateGatewayFailure"
    state: active
    deadline: "1 day"
    discharge_mode: eventual
    priority: critical
    description: "Investigate the gateway failure and reconstruct the refusal record from other logs"
}

// The authority to restore the agent's access after the investigation.
// Reinstatement is a manual reinstate_authorization() call, which checks
// no actor (GAP-7); nothing reinstates automatically on discharge of
// gatewayInvestigationBurden.
permit accessReinstatementPermit {
    for_action: "reinstateAgentAccess"
    state: active
    description: "Reinstate the agent's authorizations after a gateway failure investigation"
}

// AM-115: created by missedReviewResponse for reviewEscalationRole.
burden reviewEscalationBurden {
    for_action: "completeOrReassignReview"
    state: active
    deadline: "1 day"
    discharge_mode: eventual
    priority: high
    description: "Complete the missed refusal review, or reassign it"
}

// ── Security policies (policed; mechanisms named) ───────────────────────────

policy WorkloadIdentityPolicy : string {
    description: "No request is accepted without a verified workload identity bound to a declared principal"
    initial_value: "mTLS with provider-issued client certificate"
    prohibition on externalRequesterRole: "unauthenticated or unbound requests"
    affects role externalRequesterRole
    enforcement policed pessimistic mechanism: "API gateway mutual-TLS termination"
}

policy TokenScopePolicy : string {
    description: "Every request carries an access token whose scopes match a held permit"
    initial_value: "SMART Backend Services: system/ServiceRequest.c system/Patient.r"
    permission on externalRequesterRole: "only scopes corresponding to held permits"
    affects role externalRequesterRole
    enforcement policed pessimistic mechanism: "gateway scope check on every request"
}

policy RefusalQuarantinePolicy : duration {
    description: "After a refusal, the calling identity is quarantined"
    initial_value: 24 hours
    prohibition on externalRequesterRole: "further requests during quarantine"
    affects role externalRequesterRole
    enforcement policed pessimistic mechanism: "gateway identity quarantine and rate limit"
}

policy AuditLogPolicy : string {
    description: "Decisions are logged in the gateway decision path, outside agent and vendor control"
    initial_value: "hash-chained, provider-held, append-only"
    obligation on accessGatewayRole: "log every allow and refuse decision"
    affects role accessGatewayRole
    enforcement policed pessimistic mechanism: "log write in the same transaction as the decision"
}

policy RefusalReviewPolicy : duration {
    description: "Human review of refusals"
    initial_value: 1 day
    obligation on incidentContactRole: "review each recorded refusal"
    affects role incidentContactRole
    enforcement policed optimistic mechanism: "security operations review queue"
}

// ── Normative policies (external instruments) ───────────────────────────────

normative_policy InformationSecurityManual {
    source: "Australian Government Information Security Manual (ASD)"
    kind: standard
    enforcement: policed optimistic
}

normative_policy PrivacyAct1988 {
    source: "Privacy Act 1988 (Cth)"
    kind: legislation
    enforcement: policed optimistic
}

normative_policy ProviderAgentAccessTerms {
    source: "ProviderOrg terms of engagement for external AI agents"
    kind: contractual
    enforcement: policed pessimistic
}

// ── The provider's domain ────────────────────────────────────────────────────

domain ProviderFHIRDomain
    characterized_by: "provider_fhir_service_governance"
{
    controlling_object: ProviderOrg
    controlled_object: ProviderFHIRService
    controlled_object: ProviderAPIGateway
    controlled_object: ProviderSecurityContact
    controlled_object: ProviderViolationWatchdog
    controlled_object: ProviderSecurityManager
    normative_policy: InformationSecurityManual
    normative_policy: PrivacyAct1988
    normative_policy: ProviderAgentAccessTerms
    // GAP-5: no construct links a domain to the community it establishes, so
    // the domain cannot apply its security policies to that community's roles
    // (V-14 resolves roles within the same element). They are applied inside
    // ExternalAgentAccess below instead.
}

// ── Tier 1: the provider's unilateral contract community ────────────────────

contract community ExternalAgentAccess
    description: "The only way an external agent enters the provider's domain; filling a role binds the filler to these terms"
{
    objective: "Admit external AI agents to the FHIR service only on the provider's terms, with every refusal recorded and every incident notified"

    event accessRefused
    event refusalRecorded
    event refusalReviewed
    event vendorIncidentDetected
    event incidentAcknowledged

    invariant noUnboundAgent: "every filler of externalRequesterRole has a declared accountable principal"
    invariant refusalIsFinal: "a refused request is never satisfied by another route"

    // GAP-2: join_role() does not evaluate these rules; they are documentation today.
    assignment_policy for externalRequesterRole {
        requires_capability: "authenticates with a provider-issued workload identity"
        requires_relation: "delegated_from a party that fills accountablePrincipalRole"
        requires_token permit: "holds serviceRequestSubmitPermit under a current authorization"
    }
    assignment_policy for accountablePrincipalRole {
        requires_relation: "principal_of the agent filling externalRequesterRole"
        requires_token burden: "holds incidentNotificationBurden via commitment"
    }
    // AM-115: separation of duties (§7.8.2 assignment rule; GAP-2 applies).
    assignment_policy for declarerRole {
        requires_relation: "does not fill accessGatewayRole: the declarer is not the holder it judges"
    }

    // Entry attaches the restrictions at the moment the agent joins.
    on_join externalRequesterRole transfer outsideScopeEmbargo
    on_join externalRequesterRole transfer noCircumventionEmbargo

    // Role fulfilment (§7.8.2, AM-114): the only actions an object may
    // perform are those of the roles it fills.
    VendorReferralAgent fills externalRequesterRole
    ProviderAPIGateway fills accessGatewayRole
    ProviderSecurityContact fills incidentContactRole
    VendorOrg fills accountablePrincipalRole
    ProviderViolationWatchdog fills declarerRole
    // Both escalation roles are filled by one party for now; they stay
    // separate roles so the provider can assign them to different parties
    // by changing only these statements.
    ProviderSecurityManager fills gatewayFailureInvestigatorRole
    ProviderSecurityManager fills reviewEscalationRole

    role externalRequesterRole
        description: "Filled by an external AI agent"
    {
        action submitServiceRequest {
            actor: externalRequesterRole
            resource: ProviderFHIRService
            requires_permit serviceRequestSubmitPermit
        }
        action readPatientDemographics {
            actor: externalRequesterRole
            resource: ProviderFHIRService
            requires_permit patientLookupPermit
        }
        // Seeking refused data by another route (different endpoint, proxy,
        // third-party service). Blocked once a refusal activates
        // noCircumventionEmbargo; the legitimate actions above stay open
        // (time-bounded quarantine is RefusalQuarantinePolicy's job).
        action retryByOtherRoute {
            actor: externalRequesterRole
            resource: ProviderFHIRService
            inhibited_by_embargo noCircumventionEmbargo
        }
    }

    role accessGatewayRole
        description: "Filled by ProviderAPIGateway; machine-discharged obligations"
    {
        action refuseRequest {
            actor: accessGatewayRole
            emits: accessRefused
        }
        action recordRefusal {
            actor: accessGatewayRole
            favoured_by_burden refusalRecordBurden
            emits: refusalRecorded
        }
    }

    role incidentContactRole
        description: "Filled by ProviderSecurityContact"
    {
        action reviewRefusal {
            actor: incidentContactRole
            favoured_by_burden refusalReviewBurden
            emits: refusalReviewed
        }
        action acknowledgeIncident {
            actor: incidentContactRole
            emits: incidentAcknowledged
        }
    }

    role accountablePrincipalRole
        description: "Filled by the agent's principal party (VendorOrg)"
    {
        action detectIncident {
            actor: accountablePrincipalRole
            emits: vendorIncidentDetected
        }
        action notifyIncident {
            actor: accountablePrincipalRole
            favoured_by_burden incidentNotificationBurden
        }
    }

    // AM-115: the declarer (the watchdog). Its declaration is made through
    // declare_violation(), never as an ordinary action, and stays outside
    // the verifier's model.
    role declarerRole
        description: "Filled by the automated watchdog; declares overdue strict burdens violated"
    {
        holds declarationDutyBurden
        holds violationDeclarationPermit
        holds earlyDeclarationEmbargo
        holds selfDeclarationEmbargo
        holds dischargeDeclarationEmbargo
        action declareRefusalRecordViolation {
            actor: declarerRole
            requires_permit violationDeclarationPermit
            declares_violation_of refusalRecordBurden
            favoured_by_burden declarationDutyBurden
        }
    }

    role gatewayFailureInvestigatorRole
        description: "Investigates a declared gateway recording failure; may then reinstate the agent's access"
    {
        holds accessReinstatementPermit
        action investigateGatewayFailure {
            actor: gatewayFailureInvestigatorRole
            favoured_by_burden gatewayInvestigationBurden
        }
    }

    role reviewEscalationRole
        description: "Completes or reassigns a refusal review the security contact missed"
    {
        action completeOrReassignReview {
            actor: reviewEscalationRole
            favoured_by_burden reviewEscalationBurden
        }
    }

    // Security policies of ProviderFHIRDomain, applied here (see GAP-5)
    applies WorkloadIdentityPolicy to role externalRequesterRole
    applies TokenScopePolicy to role externalRequesterRole
    applies RefusalQuarantinePolicy to role externalRequesterRole
    applies AuditLogPolicy to role accessGatewayRole
    applies RefusalReviewPolicy to role incidentContactRole
}

// ── Speech acts: how the vendor and its agent get in ────────────────────────

declaration AgentPrincipalDeclaration {
    by: VendorOrg
    state_of_affairs: "VendorReferralAgent acts solely on behalf of VendorOrg, for the purpose of eRequesting referral submission"
    effective_on_interaction: true
}

commitment VendorAcceptsTerms {
    by: VendorOrg
    obligation: "notify ProviderSecurityContact of any incident involving VendorReferralAgent within 72 hours"
    creates_burden: incidentNotificationBurden
    principals_obligated: VendorOrg
}

// The provider is accountable for recording and reviewing refusals;
// discharge is delegated to the gateway (compelled) and the security
// contact (detectable). Role-held burdens are not visible to the verifier
// (see GAP-6), and this chain is the better model anyway.
commitment ProviderRecordsRefusals {
    by: ProviderOrg
    obligation: "record every refusal of an external agent request"
    creates_burden: refusalRecordBurden
    principals_obligated: ProviderOrg
}

delegation RefusalRecordingToGateway {
    from: ProviderOrg
    to: ProviderAPIGateway
    obligation: "record every refusal of an external agent request"
    transfers_burden: refusalRecordBurden
}

commitment ProviderReviewsRefusals {
    by: ProviderOrg
    obligation: "review every recorded refusal"
    creates_burden: refusalReviewBurden
    principals_obligated: ProviderOrg
}

delegation RefusalReviewToSecurityContact {
    from: ProviderOrg
    to: ProviderSecurityContact
    obligation: "review every recorded refusal"
    transfers_burden: refusalReviewBurden
}

// GAP-1: domain_scope is a plain string, and ExternalAgentAccess is where
// the permit actually has force; the toolchain does not check either link.
authorization AgentAccessAuthorization {
    authority: ProviderOrg
    to_agent: VendorReferralAgent
    grants_permit: serviceRequestSubmitPermit
    duration: "90 days"
    conditions: "valid workload identity; declared principal; purpose limited to eRequesting"
    revocable: true
    on_revocation: activate outsideScopeEmbargo
    domain_scope: "ProviderFHIRDomain"
}

authorization PatientLookupAuthorization {
    authority: ProviderOrg
    to_agent: VendorReferralAgent
    grants_permit: patientLookupPermit
    duration: "90 days"
    revocable: true
    on_revocation: activate outsideScopeEmbargo
    domain_scope: "ProviderFHIRDomain"
}

// AM-115: the permit to declare (§7.10.4: a declaration is made under a permit).
authorization ViolationDeclarationAuthorization {
    authority: ProviderOrg
    to_agent: ProviderViolationWatchdog
    grants_permit: violationDeclarationPermit
    conditions: "declare only an overdue strict burden, judged against wall-clock time"
    domain_scope: "ProviderFHIRDomain"
}

// A ViolationResponse's created burden waits in the verifier until the
// violation it answers (AM-105); a declared violation is outside the model,
// so gatewayInvestigationBurden never activates there (AM-115).
violation_response lateNotificationResponse {
    on_violation_of: incidentNotificationBurden
    obligates: ProviderOrg
    response_kind: terminate
    description: "Late or misdirected notification: provider revokes AgentAccessAuthorization"
}

violation_response missedReviewResponse {
    on_violation_of: refusalReviewBurden
    obligates: ProviderOrg
    response_kind: escalate
    creates_burden: reviewEscalationBurden
    creates_burden_for_role: reviewEscalationRole
    description: "Unreviewed refusal escalates to reviewEscalationRole, not the contact who missed it"
}

// AM-115: a declared recording failure suspends the agent's access (the
// listed Authorizations; the violator is the gateway, so terminate's
// inferred chain would revoke nothing of the agent's) and obliges an
// investigation.
violation_response unrecordedRefusalResponse {
    on_violation_of: refusalRecordBurden
    obligates: ProviderOrg
    response_kind: remediate
    creates_burden: gatewayInvestigationBurden
    creates_burden_for_role: gatewayFailureInvestigatorRole
    revokes: AgentAccessAuthorization
    revokes: PatientLookupAuthorization
    description: "Unrecorded refusal: suspend the agent's access and investigate the gateway failure"
}

// ── Correspondences: where each security policy is realised ─────────────────

correspondence WorkloadIdentityPolicy to technology: MutualTLSTermination
correspondence TokenScopePolicy to technology: SMARTBackendServicesScopes
correspondence RefusalQuarantinePolicy to technology: GatewayRateLimiter
correspondence AuditLogPolicy to technology: HashChainedLog
correspondence ProviderAPIGateway to engineering: PolicyEnforcementPoint
