AM-31 Design Note: AuthorizationDecl as First-Class Grammar Construct
Drafted: 2 July 2026
Status: Design — pending grammar implementation in Claude Code
Triggered by: LLM-to-DSL mapping exercise on gp_referral_scenario.el
(2 July 2026)
Standard basis: ISO/IEC 15414:2015 §6.6.4, §7.8.8.4

1. Motivation
The eReferral mapping exercise (2 July 2026) identified that patient consent
cannot be expressed as an architectural constraint in the current grammar.
The patientRecordAccessPermit in gp_referral_scenario.el is granted via
authorization patientDataAuthorization (speech act level) but the grammar
does not yet support AuthorizationDecl as a first-class construct with
revocation and embargo activation.
The root cause: AuthorizationDecl is listed in the grammar coverage table
(EDOC 2026 Table 1, §7.8) and referenced in validator comments, but is not
yet implemented as a first-class grammar construct. It is the missing speech
act between the permit/embargo tokens (which exist) and the act that creates
and conditionally revokes them.

2. Standard Basis
§6.6.4 — Authorization (definition)
"An action indicating that a particular behaviour shall not be prevented.
NOTE 1 — Unlike a permission, an authorization is an empowerment.
NOTE 2 — The fact that an enterprise object has performed an authorization
is expressed by it issuing a required permit and itself undertaking a burden
describing its obligation to facilitate the behaviour."
Key insight: Authorization is simultaneously:

A permission — permit granted to the authorized agent
An obligation — burden on the authority to empower the agent

This dual nature distinguishes authorization from a simple permission grant.
The authority cannot merely issue the permit and walk away — it has a
continuing obligation to ensure the agent can use it.
§7.8.8.4 — Authorization (specification)
Authorization is modelled using a combination of permit and burden tokens:
Permit held by authorized agent:

An authorization domain that prescribes the authorization
An identified behaviour that is subject to that domain
A role or roles involved in that behaviour
A subset of that behaviour that is allowed to occur
Optionally, objects that may fulfil the roles involved

Burden on the authority:

A set of rules prescribing the obligation
An identified behaviour subject to those rules
A role or roles subject to the rules
A subset of behaviour that is required to occur
Optionally, objects that may fulfil the roles involved

"When the authorization applies, the enterprise objects fulfilling the
roles that are subject to the authorization shall not be prevented from
engaging in the authorized behaviour."
"Authorizations will not necessarily be effective outside the domain
controlling them. In federations, the effect of authorizations is
determined by the contract of the federation."
Revision Note §18 — Controlling-controlled as implicit authorization
The controlling-controlled relationship in a DomainDecl is essentially
an authorization speech act executed at domain establishment:

The controlling object is the authority
The controlled object is the authorized agent
Domain establishment is the authorization act — an empowerment

This means AuthorizationDecl has a deeper role than consent alone. It is
the formal underpinning of domain-level empowerment, not just episode-level
consent. AM-31 must accommodate both contexts.

3. Current State
grep -n "AuthorizationDecl|authorization" el_grammar.tx
→ Line 548: comment only — "DelegationDecl, CommitmentDecl, AuthorizationDecl"
→ No AuthorizationDecl grammar rule exists
→ No on_revocation syntax exists
→ EmbargoDecl exists but has no activation trigger mechanism
The permit and embargo tokens exist and parse correctly. What is missing
is the speech act that:

Grants a permit conditionally (subject to authority's empowerment burden)
Is revocable by the authority
On revocation, activates an embargo

Note: gp_referral_scenario.el already has an authorization block at the
speech act level (patientDataAuthorization) but this parses only because
the grammar currently treats authorization as a generic keyword, not a
typed construct with full field validation.

4. Proposed Grammar Construct

4.0 to_role vs to_agent — design decision

AuthorizationDecl must support both targeting modes:

**to_role** — grants permit to whoever fills the named role. General,
role-based. Appropriate for human clinician access where role membership
is the authorization basis. Consistent with on_join role transfer permit
pattern already in the grammar.

**to_agent** — grants permit explicitly to a named agent. Specific,
agent-targeted. Appropriate for AI agent access where explicit consent
is required and must be separately revocable from human access.

Why both matter in the eReferral scenario:
- SpecialistClinician accesses patient records via role membership
  (on_join specialistRole transfer patientRecordAccessPermit) —
  role-based, implicit authorization via domain membership
- SpecialistAIAgent accesses patient records via explicit authorization
  (to_agent: SpecialistAIAgent) — agent-targeted, explicitly consented,
  separately revocable under MyHealthRecordsAct

This distinction is the formal basis for governance of AI agent access
being separate from human clinician access. A single to_role authorization
cannot capture this — it would grant AI agent access implicitly via role
membership, which is insufficient for clinical AI consent governance.

Grammar implication: AuthorizationDecl should allow either:
  to_role: [RoleDecl]     // role-based authorization
  to_agent: [AgentDecl]   // agent-targeted authorization (AI consent case)
with a validator rule (AM-31-V5) that exactly one of to_role or
to_agent must be present, not both.

4.1 AuthorizationDecl — standalone and community-scoped
AuthorizationDecl should be valid in two contexts:

Standalone (top-level) — standing authorization, durable for the
lifetime of the enterprise specification (e.g. domain-level empowerment)
Community-scoped — episode authorization, valid only within the
community lifecycle (e.g. patient consent for a single referral episode)

Proposed grammar sketch (to be refined in Claude Code):
AuthorizationDecl:
'authorization' name=ID '{'
'authority'        ':' authority=[EnterpriseObject]
'grants_permit'    ':' grants_permit=[PermitDecl]
'to_role'          ':' to_role=[RoleDecl]
('revocable'       ':' revocable=BOOL)?
('on_revocation'   ':' 'activate' on_revocation=[EmbargoDecl])?
('normative_basis' ':' normative_basis=[NormativePolicyDecl])?
('description'     ':' description=STRING)?
'}'
;
4.2 Authority burden — implicit or explicit
Per §7.8.8.4, the authority has a burden to empower the agent. Two options:
Option A — Implicit burden (simpler)
The validator infers the authority's empowerment burden from the
AuthorizationDecl — it does not need to be declared separately. The
validator checks that no embargo is active on the granted permit at
authorization time (V-NEW-xx).
Option B — Explicit burden (more precise)
The grammar allows an optional authority_burden block inside
AuthorizationDecl, following the same structure as BurdenDecl. This
makes the dual nature of authorization fully explicit and computable.
Recommendation: Option A for AM-31, Option B deferred to AM-32.
4.3 Revocation and embargo activation
The on_revocation: activate <embargo> clause needs a runtime trigger.
When the authority revokes the authorization (a DeclarationDecl speech
act by the authority), the runtime must:

Set the permit to SUPERSEDED state
Set the named embargo to ACTIVE state
Record the revocation event in the ledger

This is a Layer 3 (runtime) change as well as a grammar change — the
el_domain.py speech act processor must handle revocation.

5. Validator Rules Required
V-NEW-xx (AM-31-V1): Authorization authority must be a party
The authority in an AuthorizationDecl must be a PartyDecl, not an
agent. Only parties (as defined in §6.6.1) can act as authorization
authorities. Agents may hold permits but cannot grant them.
V-NEW-xx (AM-31-V2): Revocable authorization must name an embargo
If revocable: true is declared, on_revocation must name a valid
EmbargoDecl. A revocable authorization without a revocation consequence
is semantically incomplete.
V-NEW-xx (AM-31-V3): Community-scoped authorization permit scope
If AuthorizationDecl appears inside a community block, the named permit
must be scoped to that community (i.e. listed in an on_join/on_leave
pair or declared within the community). Cross-community permit grants
require federation-level authorization.
V-NEW-xx (AM-31-V4): No active embargo on authorization grant
At authorization time, if an embargo exists for the same action as the
granted permit, the validator should warn that the authorization may be
ineffective (the embargo takes precedence).
V-NEW-xx (AM-31-V5): Exactly one of to_role or to_agent must be present
AuthorizationDecl must have either to_role or to_agent, not both and
not neither. A grant with no target is semantically void; a grant to
both a role and an agent simultaneously is ambiguous.

6. Impact on Existing Models
gp_referral_scenario.el — minimal impact. The existing authorization
patientDataAuthorization block parses currently; AM-31 will add typed
field validation to it. Fields already present (authority, to_agent,
grants_permit, revocable, domain_scope, description) will need to
align with the new AuthorizationDecl grammar rule.
Other models — no breaking changes expected. AuthorizationDecl is
additive; existing permit grants via on_join remain valid.

7. Relationship to Other Amendments
AM-13 (discharge_mode): Parallel — both extend deontic token semantics
AM-26 (CommunityObject): AM-31 community-scoped authorization references
roles defined via AM-26 patterns
AM-28 (NormativePolicy): AM-31 normative_basis references NormativePolicy
— AM-28 must be committed first (confirmed done)
AM-29 (SatisfactionCondition): No direct dependency
AM-32 (planned): Explicit authority burden — the full §7.8.8.4 implementation

8. Connection to FTI Pillar 4 (Consumer & Workforce Engagement)
AM-31 is the grammar foundation for making FTI Pillar 4 (consent)
architecturally enforceable rather than merely documented:

Without AM-31: consent is a documented process; the permit is granted
via speech act but grammar does not validate or enforce the authorization
structure
With AM-31: AuthorizationDecl is a typed, validated construct; revocation
immediately activates the embargo and blocks AI agent access;
normative_basis links consent to MyHealthRecordsAct

This is the difference between consent as a record and consent as an
architectural constraint — directly relevant to OAIC Privacy Act obligations,
MyHealthRecordsAct §70 (withdrawal of consent), and FTI Pillar 4.

8b. The superseded State — Materialisation Note

AM-31 introduced superseded as a new runtime token state in
el_engine.py. This is worth documenting explicitly because it
represents a semantic shift.

Before AM-31:
ObligationState.SUPERSEDED existed only in the Kripke verification
layer (el_kripke.py) as a formal reasoning concept — an obligation
overtaken by another or made moot by delegation. It was never
materialised in the actual runtime token vocabulary. Runtime tokens
could only be:
active | pending | discharged | violated

After AM-31:
superseded is now a concrete runtime state in TokenInstance.state.
When Runtime.revoke_authorization() is called:
1. The granted permit transitions to superseded — distinct from
   discharged (obligation met) and violated (obligation failed);
   means "validly in force but formally withdrawn by the granting
   authority"
2. The on_revocation embargo transitions to active
3. Both events are recorded as a TransitionRecord in the ledger

Why this matters:
- discharged would be semantically wrong — the permit wasn't
  fulfilled, it was revoked
- violated would be semantically wrong — no one failed, the
  authority exercised their right to withdraw
- superseded is the correct term — the token's lifecycle ended
  through revocation, not through obligation discharge or failure

Audit trail significance (FTI Pillar 6):
The revocation of consent is now a formally recorded,
machine-verifiable event in the governance ledger. A board can prove
exactly when consent was withdrawn and that the AI agent's access was
terminated at that precise moment — not just that a flag was set in a
database, but that a governance speech act occurred and was recorded
with full provenance. This is the difference between consent as a
documented process and consent as an architectural constraint with
traceable enforcement.

9. Next Steps

DONE — AM-30: verified complete in gp_referral_scenario.el
TODO — AM-31: Implement AuthorizationDecl grammar rule (Claude Code)

Grammar: el_grammar.tx
Runtime: el_domain.py (revocation speech act processing)
Validator: el_validator.py (V-NEW rules AM-31-V1 through V4)
Test: gp_referral_scenario.el should parse and validate cleanly
with typed AuthorizationDecl fields


TODO — AM-32: Explicit authority burden (Option B above)
TODO — Update el_grammar_amendments.md with AM-31 entry after
implementation
