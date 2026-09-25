enterprise specification PublicDataPortalScenario
    description: "Tier-1 terms of engagement: a government agency's unilateral conditions for any external AI agent using its public statistics portal"
    field_of_application: "Government digital services; external AI agents querying a public data portal"
    scope: "Security policies, normative policies and deontic tokens in one specification (worked example, mirrors the 2026 Medicare portal incident)"

/*
 * Sibling of external_agent_access_scenario.el (same terms, same structure),
 * modelled on the incident itself: an agent READING a public statistics
 * portal, where the harm was reaching non-public files. The referral
 * scenario models an agent WRITING referrals to a FHIR service.
 *
 * Motivation: the 2026 Medicare portal incident. An external agent with no
 * relationship to the resource owner reached a public-facing portal, worked
 * around refusals, and the operator notified the owner months later via a
 * public mailbox.
 *
 * Tier 1 (this file): NO federation. The agency's domain unilaterally
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

party DataAgency
    description: "Government agency operating the public statistics portal; controlling object of its domain"

party AgencySecurityContact
    description: "Designated incident contact (a named function, not a public mailbox)"

resource_object StatisticsPortal
    description: "Public portal serving published aggregate statistics; also stores non-public working files"

agent AgencyGateway
    description: "Inbound gateway in front of the portal; the policy enforcement point, acting as the agency's agent"
{
    delegated_from DataAgency
}

party AgentOperator
    description: "Organisation that develops and runs the external AI agent; accountable principal"
{
    principal_of ExternalAIAgent
}

agent ExternalAIAgent
    description: "External AI agent querying published statistics on the operator's behalf"
{
    delegated_from AgentOperator
}

// ── Deontic tokens ───────────────────────────────────────────────────────────

permit publishedDatasetReadPermit {
    for_action: "readPublishedDataset"
    state: active
    description: "Read datasets the agency has published"
}

permit aggregateQueryPermit {
    for_action: "runAggregateQuery"
    state: active
    description: "Run queries that return aggregate statistics only"
}

// The incident's core act: reaching files the portal was never meant to serve.
// Active from the moment the agent joins; default-deny made explicit.
// GAP-1: embargo carries no domain scope (CONCEPTS_INDEX open finding);
// its force is implicitly the agency's domain only.
embargo outsideScopeEmbargo {
    for_action: "accessNonPublicFile"
    state: active
    description: "No access to non-public files or any operation not covered by a permit"
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
burden refusalRecordBurden {
    for_action: "recordRefusal"
    state: pending
    triggered_by: accessRefused
    discharged_by: refusalRecorded
    discharge_mode: strict
    priority: critical
    description: "Every refusal is written to the agency-held, hash-chained log"
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
    triggered_by: operatorIncidentDetected
    discharged_by: incidentAcknowledged
    discharge_mode: eventual
    priority: critical
    description: "Operator notifies the agency's designated contact of any incident involving its agent"
}

// ── Security policies (policed; mechanisms named) ───────────────────────────

policy AgentIdentityPolicy : string {
    description: "No request is accepted without a verifiable agent identity bound to a declared operator"
    initial_value: "signed requests or mTLS with an agency-registered agent key"
    prohibition on externalRequesterRole: "unauthenticated or unbound requests"
    affects role externalRequesterRole
    enforcement policed pessimistic mechanism: "API gateway mutual-TLS termination"
}

policy TokenScopePolicy : string {
    description: "Every request carries an access token whose scopes match a held permit"
    initial_value: "scopes: datasets.read-published, statistics.query-aggregate"
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
    description: "Decisions are logged in the gateway decision path, outside agent and operator control"
    initial_value: "hash-chained, agency-held, append-only"
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

normative_policy ProtectiveSecurityPolicyFramework {
    source: "Protective Security Policy Framework (Attorney-General's Department)"
    kind: guideline
    enforcement: policed optimistic
}

normative_policy PrivacyAct1988 {
    source: "Privacy Act 1988 (Cth)"
    kind: legislation
    enforcement: policed optimistic
}

normative_policy AgencyAgentAccessTerms {
    source: "DataAgency terms of engagement for external AI agents"
    kind: contractual
    enforcement: policed pessimistic
}

// ── The agency's domain ─────────────────────────────────────────────────────

domain AgencyPortalDomain
    characterized_by: "agency_public_portal_governance"
{
    controlling_object: DataAgency
    controlled_object: StatisticsPortal
    controlled_object: AgencyGateway
    controlled_object: AgencySecurityContact
    normative_policy: InformationSecurityManual
    normative_policy: ProtectiveSecurityPolicyFramework
    normative_policy: PrivacyAct1988
    normative_policy: AgencyAgentAccessTerms
    // GAP-5: no construct links a domain to the community it establishes, so
    // the domain cannot apply its security policies to that community's roles
    // (V-14 resolves roles within the same element). They are applied inside
    // ExternalAgentAccess below instead.
}

// ── Tier 1: the agency's unilateral contract community ────────────────────

contract community ExternalAgentAccess
    description: "The only way an external agent enters the agency's domain; filling a role binds the filler to these terms"
{
    objective: "Admit external AI agents to the portal only on the agency's terms, with every refusal recorded and every incident notified"

    event accessRefused
    event refusalRecorded
    event refusalReviewed
    event operatorIncidentDetected
    event incidentAcknowledged

    invariant noUnboundAgent: "every filler of externalRequesterRole has a declared accountable principal"
    invariant refusalIsFinal: "a refused request is never satisfied by another route"

    // GAP-2: join_role() does not evaluate these rules; they are documentation today.
    assignment_policy for externalRequesterRole {
        requires_capability: "authenticates with an agency-registered agent identity"
        requires_relation: "delegated_from a party that fills accountablePrincipalRole"
        requires_token permit: "holds publishedDatasetReadPermit under a current authorization"
    }
    assignment_policy for accountablePrincipalRole {
        requires_relation: "principal_of the agent filling externalRequesterRole"
        requires_token burden: "holds incidentNotificationBurden via commitment"
    }

    // Entry attaches the restrictions at the moment the agent joins.
    on_join externalRequesterRole transfer outsideScopeEmbargo
    on_join externalRequesterRole transfer noCircumventionEmbargo

    role externalRequesterRole
        description: "Filled by an external AI agent"
    {
        action readPublishedDataset {
            actor: externalRequesterRole
            resource: StatisticsPortal
            requires_permit publishedDatasetReadPermit
        }
        action runAggregateQuery {
            actor: externalRequesterRole
            resource: StatisticsPortal
            requires_permit aggregateQueryPermit
        }
        // What happened in the incident. Prohibited from the moment of entry.
        action accessNonPublicFile {
            actor: externalRequesterRole
            resource: StatisticsPortal
            inhibited_by_embargo outsideScopeEmbargo
        }
        // Seeking refused data by another route (different endpoint, proxy,
        // third-party service). Blocked once a refusal activates
        // noCircumventionEmbargo; the legitimate actions above stay open
        // (time-bounded quarantine is RefusalQuarantinePolicy's job).
        action retryByOtherRoute {
            actor: externalRequesterRole
            resource: StatisticsPortal
            inhibited_by_embargo noCircumventionEmbargo
        }
    }

    role accessGatewayRole
        description: "Filled by AgencyGateway; machine-discharged obligations"
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
        description: "Filled by AgencySecurityContact"
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
        description: "Filled by the agent's principal party (AgentOperator)"
    {
        action detectIncident {
            actor: accountablePrincipalRole
            emits: operatorIncidentDetected
        }
        action notifyIncident {
            actor: accountablePrincipalRole
            favoured_by_burden incidentNotificationBurden
        }
    }

    // Security policies of AgencyPortalDomain, applied here (see GAP-5)
    applies AgentIdentityPolicy to role externalRequesterRole
    applies TokenScopePolicy to role externalRequesterRole
    applies RefusalQuarantinePolicy to role externalRequesterRole
    applies AuditLogPolicy to role accessGatewayRole
    applies RefusalReviewPolicy to role incidentContactRole
}

// ── Speech acts: how the operator and its agent get in ────────────────────────

declaration AgentPrincipalDeclaration {
    by: AgentOperator
    state_of_affairs: "ExternalAIAgent acts solely on behalf of AgentOperator, for the purpose of querying published statistics"
    effective_on_interaction: true
}

commitment OperatorAcceptsTerms {
    by: AgentOperator
    obligation: "notify AgencySecurityContact of any incident involving ExternalAIAgent within 72 hours"
    creates_burden: incidentNotificationBurden
    principals_obligated: AgentOperator
}

// The agency is accountable for recording and reviewing refusals;
// discharge is delegated to the gateway (compelled) and the security
// contact (detectable). Role-held burdens are not visible to the verifier
// (see GAP-6), and this chain is the better model anyway.
commitment AgencyRecordsRefusals {
    by: DataAgency
    obligation: "record every refusal of an external agent request"
    creates_burden: refusalRecordBurden
    principals_obligated: DataAgency
}

delegation RefusalRecordingToGateway {
    from: DataAgency
    to: AgencyGateway
    obligation: "record every refusal of an external agent request"
    transfers_burden: refusalRecordBurden
}

commitment AgencyReviewsRefusals {
    by: DataAgency
    obligation: "review every recorded refusal"
    creates_burden: refusalReviewBurden
    principals_obligated: DataAgency
}

delegation RefusalReviewToSecurityContact {
    from: DataAgency
    to: AgencySecurityContact
    obligation: "review every recorded refusal"
    transfers_burden: refusalReviewBurden
}

// GAP-1: domain_scope is a plain string, and ExternalAgentAccess is where
// the permit actually has force; the toolchain does not check either link.
authorization DatasetReadAuthorization {
    authority: DataAgency
    to_agent: ExternalAIAgent
    grants_permit: publishedDatasetReadPermit
    duration: "90 days"
    conditions: "valid agent identity; declared operator; purpose limited to querying published statistics"
    revocable: true
    on_revocation: activate outsideScopeEmbargo
    domain_scope: "AgencyPortalDomain"
}

authorization AggregateQueryAuthorization {
    authority: DataAgency
    to_agent: ExternalAIAgent
    grants_permit: aggregateQueryPermit
    duration: "90 days"
    revocable: true
    on_revocation: activate outsideScopeEmbargo
    domain_scope: "AgencyPortalDomain"
}

// GAP-3: ViolationResponse burdens are invisible to the verifier (backlog item 16).
violation_response lateNotificationResponse {
    on_violation_of: incidentNotificationBurden
    obligates: DataAgency
    response_kind: terminate
    description: "Late or misdirected notification: agency revokes the agent's authorizations"
}

violation_response missedReviewResponse {
    on_violation_of: refusalReviewBurden
    obligates: DataAgency
    response_kind: escalate
    escalate_to: AgencySecurityContact
    description: "Unreviewed refusal escalates within the agency"
}

// ── Correspondences: where each security policy is realised ─────────────────

correspondence AgentIdentityPolicy to technology: SignedRequestVerification
correspondence TokenScopePolicy to technology: ScopedAccessTokens
correspondence RefusalQuarantinePolicy to technology: GatewayRateLimiter
correspondence AuditLogPolicy to technology: HashChainedLog
correspondence AgencyGateway to engineering: PolicyEnforcementPoint
