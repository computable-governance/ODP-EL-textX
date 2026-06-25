# DSL-EL Design Notes
_ODP Enterprise Language DSL — ISO/IEC 15414:2015_
_Companion to `el_grammar.tx` and `el_grammar_amendments.md`_

---

## 1. Purpose

This document captures two things not covered by the grammar's inline comments or the amendments log:

1. **Cross-cutting design decisions** — philosophy and patterns that apply across the whole grammar
2. **Complete worked examples** — full `.el` specifications demonstrating the DSL as a whole

---

## 2. Cross-Cutting Design Decisions

### 2.1 Grammar handles structure; validator handles semantics

The grammar enforces **syntactic** constraints only — what keywords must appear, what is optional, what is a list. Semantic constraints — minimum cardinalities within heterogeneous lists, cross-concept consistency, standard-mandated relationships — are the responsibility of `el_validator.py`.

Examples:
- A `contract {}` block with no content is syntactically valid — the validator rejects it
- `on_objective_achieved: true` and `permanent: true` together are syntactically valid — the validator rejects them
- A `role` with no `ActionDecl` is syntactically valid — the validator rejects it

This separation keeps the grammar readable and maintainable. A rule that tried to express all semantic constraints would be unreadable and fragile.

---

### 2.2 The `body_items*=BodyItem` alternation pattern

Several rules use a unified alternation body rather than typed lists:

```
CommunityDecl   → items*=RoleBodyItem
ActionDecl      → items*=ActionBodyItem
DomainDecl      → body_items*=DomainBodyItem
FederationDecl  → body_items*=FedBodyItem
```

**Why:** Two reasons.

First, it gives the DSL user **order freedom** — they can write body items in any natural sequence rather than being forced into a grammar-imposed ordering.

Second, it avoids a **known arpeggio/textX bug**: when multiple cross-reference list assignments appear in the same rule body (e.g. `roles+=[RoleDecl]* processes+=[ProcessDecl]*`), the arpeggio backend continues consuming tokens as cross-reference candidates after one list ends, causing subsequent assignments to fail silently. The unified alternation sidesteps this entirely.

The tradeoff: `body_items` on the Python object is a flat heterogeneous list. The `el_parser.py` object processor sorts items by type into typed attributes (`roles`, `processes`, `policy_refs` etc.) for the validator and reasoner to use cleanly.

---

### 2.3 Natural English two-keyword openers

Top-level declarations use two-keyword openers where natural:

```
enterprise specification MySpec
```

Not `enterprise_specification` or `spec`. This is deliberate — ODP-EL is a governance language that non-programmers may read and review. Two-keyword openers read as natural English and make `.el` files more approachable as documents.

Single-keyword openers are used where the concept is already a natural English word (`community`, `policy`, `delegation`, `role`) and two words would be redundant.

---

### 2.4 `STRING` vs cross-reference — the decision criteria

Throughout the grammar, some attributes are `STRING` (quoted prose) and others are `[TypeName]` (cross-references). The decision criteria:

| Use `STRING` when | Use `[TypeName]` when |
|---|---|
| Value is human-readable prose | Value names a declared construct |
| Target lives in another viewpoint or document | Target is declared in this spec |
| The concept has no formal grammar representation | The concept has a named rule |
| Standard describes it narratively | Standard defines it as a named entity |

Examples:
- `obligation: STRING` — prose description of a commitment, not a formal construct
- `burden=[DeonticTokenDecl]` — names a declared token, machine-checkable
- `for_action: STRING` — currently prose; AM-01 proposes upgrading to `[ActionDecl]`
- `viewpoint_concept=ID` — lives in another viewpoint specification, cannot be cross-referenced

---

### 2.5 Colon separator for metadata, no separator for names

Metadata attributes always use `keyword ':' value`:
```
description:          "..."
field_of_application: "..."
state:                active
```

Names always follow the declaring keyword directly:
```
party Librarian
community BorrowingCommunity
delegation boardToDirectorDelegation
```

This visual distinction makes `.el` files scannable — names pop out at the start of declarations, metadata is indented below.

---

### 2.6 `?=` boolean flag pattern

Used throughout for binary properties:
```
interface?='interface'
negotiation_required?='true'
implicit?='true'
permanent?='true'
```

The keyword presence sets the flag to `True`; absence defaults to `False`. Never `flag: true/false` as a `STRING` — the grammar validates the value implicitly by only accepting the exact keyword.

---

### 2.7 Grammar maintainer ordering rule

textX uses PEG matching — alternatives are tried left-to-right, first match wins. Before adding a new alternative to any alternation rule, apply this check:

1. What is the **first token** of the new rule?
2. Does any **existing alternative** in the same alternation start with the same first token?
3. If **yes** — put the new (longer/more-specific) alternative **before** the shorter existing one.

Current first-token inventory for `SpecElement` (all safe — all distinct):

| Rule | First token |
|---|---|
| `DomainDecl` | `'domain'` |
| `FederationDecl` | `'federation'` |
| `CommunityDecl` | `'community'` |
| `ObjectDecl` | `ObjectKind` (`party`\|`agent`\|...) |
| `DeonticTokenDecl` | `DeonticKind` (`burden`\|`permit`\|`embargo`) |
| `TokenGroupDecl` | `'token_group'` |
| `PolicyDecl` | `'policy'` |
| `CommitmentDecl` | `'commitment'` |
| `DelegationDecl` | `'delegation'` |
| `AuthorizationDecl` | `'authorization'` |
| `PrescriptionDecl` | `'prescription'` |
| `DeclarationDecl` | `'declaration'` |
| `EvaluationDecl` | `'evaluation'` |
| `CorrespondenceDecl` | `'correspondence'` |

**Watch:** if `'delegation chain'` is ever added, it must precede `DelegationDecl`.

---

## 3. Complete Worked Examples

### 3.1 The Accountability Chain Pattern

The ODP-EL accountability chain runs:

```
CommitmentDecl  → party commits, creates burden (chain anchor)
DelegationDecl  → burden transferred to agent, reporting burden created
AuthorizationDecl → agent empowered with permit, authority takes burden
PrescriptionDecl  → rule established by empowered actor
DeclarationDecl   → state of affairs declared, effective on interaction
EvaluationDecl    → outcome assessed, obligation discharged
```

This chain is traceable end-to-end — the reasoner can walk from any evaluation backwards to the originating commitment. This traceability is the core accountability mechanism of ODP-EL and the primary motivation for the speech act section of the grammar.

**Complete library example:**

```
// ── STEP 1: Founding commitment ──────────────────────────────────
commitment boardResearchCommitment {
    by:              LibraryBoard
    obligation:      "Provide and maintain research access services
                      for all affiliated researchers"
    creates_burden:  researchServiceObligation
    principals_obligated: LibraryDirector, HeadLibrarian
    description:     "Founding commitment establishing research
                      access as a board-level obligation"
}

// ── STEP 2: Operational delegation ───────────────────────────────
delegation boardToDirectorDelegation {
    from:                     LibraryBoard
    to:                       LibraryDirector
    obligation:               "Operate and manage research access
                               services on behalf of the Board"
    transfers_burden:         researchServiceObligation
    creates_reporting_burden: true
    duration:                 "Annual — renewable by Board resolution"
    conditions:               "Subject to annual compliance review"
    sub_delegation_allowed:   true
    revocable:                true
}

// ── STEP 3: Empowerment ───────────────────────────────────────────
authorization directorAuthorizesHeadLibrarian {
    authority:                   LibraryDirector
    to_agent:                    HeadLibrarian
    grants_permit:               restrictedCollectionManagementPermit
    creates_burden_on_authority: managementSupportObligation
    duration:                    "Permanent while role held"
    conditions:                  "Valid professional library qualification"
    sub_delegation_allowed:      false
    revocable:                   true
    domain_scope:                "RestrictedCollectionsDomain"
}

// ── STEP 4: Rule establishment ────────────────────────────────────
prescription researchAccessRule {
    by:                       HeadLibrarian
    establishes_rule:         "Researchers may access restricted collections
                               only during staffed hours with valid credentials
                               and prior written approval from supervising faculty"
    requires_permit:          restrictedCollectionManagementPermit
    creates_oversight_burden: true
}

// ── STEP 5: State of affairs declaration ─────────────────────────
declaration researcherAccessGranted {
    by:                       HeadLibrarian
    state_of_affairs:         "Dr. Yuki Tanaka holds active restricted
                               collection access status until 31 Dec 2026"
    requires_permit:          restrictedCollectionManagementPermit
    effective_on_interaction: true
    description:              "Effective upon researcher's signed
                               acknowledgement of access conditions"
}

// ── STEP 6: Compliance evaluation ────────────────────────────────
evaluation annualAccessComplianceReview {
    by:          LibraryDirector
    of_target:   "researchServiceObligation compliance across all
                  restricted collection access grants in FY2026"
    result:      "Compliant — 47 access grants issued, all with valid
                  credentials and faculty approval. 2 incidents resolved.
                  Reporting burden discharged."
    description: "Annual compliance evaluation per delegation conditions
                  in boardToDirectorDelegation"
}
```

**Chain visualised:**
```
LibraryBoard
    │ commitment: boardResearchCommitment
    │ creates burden: researchServiceObligation
    ▼
LibraryDirector  ◄── principals_obligated
    │ delegation: boardToDirectorDelegation
    │ transfers burden: researchServiceObligation
    │ creates reporting burden
    ▼
LibraryDirector (accountable)
    │ authorization: directorAuthorizesHeadLibrarian
    │ grants permit: restrictedCollectionManagementPermit
    │ creates burden on authority: managementSupportObligation
    ▼
HeadLibrarian (empowered)
    │ prescription: researchAccessRule
    │ declaration:  researcherAccessGranted
    ▼
LibraryDirector
    │ evaluation: annualAccessComplianceReview
    ▼
Chain closed — obligation discharged
```

---

### 3.2 Community Lifecycle — Explicit Establishing

Demonstrates the difference between implicit and explicit community establishing, dynamic membership, and permanent termination.

```
community ResearchAccessCommunity
    description: "Governs access to restricted research collections"
{
    objective: "Provide vetted researchers with access to restricted materials"
        sub_objective researcherVetting:
            "All members hold valid research credentials"
            assigned_to role Researcher

    contract {
        invariant credentialCheck:
            "All members must hold valid research credentials"
        assignment_policy for Researcher {
            requires_capability: "Valid university research affiliation"
            requires_token permit: "researchAccessPermit"
        }
    }

    role Researcher {
        description: "An affiliated researcher with vetted credentials"
        action apply_for_access {
            description: "Submit application for restricted collection access"
            actor:    Researcher
            artefact: AccessApplication
            effect create researchAccessPermit
        }
    }

    role LibraryDirector {
        description: "Approves and manages researcher access"
        action approve_access {
            actor:    LibraryDirector
            artefact: AccessApplication
            requires_permit restrictedCollectionManagementPermit
            effect activate researchAccessPermit
        }
    }

    lifecycle {
        establishing {
            implicit:    false
            description: "Community established by formal agreement between
                          Library and Research Office"
            commitment by LibraryDirector:
                "Library Director commits to providing access to
                 restricted collections for vetted researchers"
            commitment by ResearchOfficeHead:
                "Research Office commits to vetting researcher
                 credentials before community admission"
        }
        changes {
            membership_dynamic: true
        }
        terminating {
            permanent:   true
            description: "Standing community — persists as institutional structure"
        }
    }
}
```

---

### 3.3 Federation with Conflict Resolution

Demonstrates federation of autonomous communities with shared objective, withdrawal behaviour, and conflict resolution strategy.

```
federation LibraryServicesFederation {
    description: "Coordinates borrowing, reservation, and catalogue services
                  across all campus libraries"

    shared_objective: "Provide seamless integrated library services
                       to all affiliated users across campuses"

    member: BorrowingCommunity
    member: ReservationCommunity
    member: CatalogueCommunity

    invariant itemConsistency:
        "An item cannot be simultaneously borrowed and reserved"
    invariant membershipConsistency:
        "A user's borrowing privileges apply uniformly across all campuses"

    applies itemAvailabilityPolicy to community BorrowingCommunity
    applies itemAvailabilityPolicy to community ReservationCommunity

    withdrawal_behaviour: "Withdrawing community retains its internal
                           governance but loses access to shared catalogue
                           and cross-campus borrowing privileges"

    conflict_resolution runtime_prevention
        description: "System prevents conflicting item states
                      (borrowed + reserved) from arising at runtime"
}
```

---

### 3.4 Viewpoint Correspondences

Demonstrates `CorrespondenceDecl` mapping enterprise concepts to all four other ODP viewpoints.

```
// Enterprise → Information
correspondence BorrowingCommunity
    to information: BorrowingSchema
    description: "BorrowingCommunity structure maps to BorrowingSchema
                  information model per §11.2"

correspondence Borrower
    to information: BorrowerRecord
    description: "Borrower role maps to BorrowerRecord per §11.2"

// Enterprise → Computational
correspondence BorrowingCommunity
    to computational: IBorrowingService
    description: "BorrowingCommunity maps to IBorrowingService
                  computational interface per §11.3"

correspondence LoanProcess
    to computational: ILoanProcessingInterface
    description: "LoanProcess maps to computational interface per §11.3"

// Enterprise → Engineering
correspondence LoanProcess
    to engineering: LoanProcessingChannel
    description: "LoanProcess maps to engineering channel per §11.4"

// Enterprise → Technology
correspondence LibrarySystem
    to technology: LibraryManagementPlatform
    description: "Overall system maps to technology platform per §11.5"
```

---

### 3.5 Violation Response

Demonstrates `ViolationResponseDecl` — the specification-level construct for prescribing behaviour upon rule violation, per §6.3.8 and §7.8.6 NOTE 2.

The key point: the violation response rule is itself an obligation. Failure to execute the prescribed response is itself a violation — closing the accountability loop back into the deontic chain.

```
// ── The violated token ────────────────────────────────────────────
embargo periodicalEmbargo {
    state:       active
    for_action:  "borrow_periodical"
    description: "Prohibits undergraduates from borrowing periodicals"
}

// ── The violation response ────────────────────────────────────────
// Triggered when an Undergraduate breaches periodicalEmbargo.
// Response: suspension of borrowing privileges.
// Creates a reporting burden on the LibraryDirector —
// failure to report is itself a violation per §7.8.6 NOTE 2.

violation_response unauthorisedPeriodicalAccess {
    on_violation_of:  "periodicalEmbargo — accessing periodicals
                       without permit"
    by:               Undergraduate
    response:         suspension
    creates_burden:   accessViolationReportingObligation
    description:      "Undergraduate borrowing privileges suspended
                       pending review. Reporting obligation created
                       on LibraryDirector."
}

// ── The reporting burden triggered by the response ────────────────
burden accessViolationReportingObligation {
    state:       pending
    description: "LibraryDirector must file incident report within
                  5 working days of detected violation"
}

// ── The evaluation that closes the loop ──────────────────────────
evaluation violationIncidentReview {
    by:          LibraryDirector
    of_target:   "accessViolationReportingObligation discharge
                  for periodical embargo breach by Undergraduate"
    result:      "Incident report filed. Borrowing privileges
                  reinstated after 14-day suspension. Obligation
                  discharged."
    description: "Closes accountability chain for embargo violation"
}
```

**The violation chain visualised:**
```
Embargo breached by Undergraduate
    │
    │ violation_response: unauthorisedPeriodicalAccess
    │ response: suspension
    │ creates burden: accessViolationReportingObligation
    ▼
LibraryDirector (now accountable)
    │
    │ evaluation: violationIncidentReview
    │ obligation discharged
    ▼
Chain closed
```



The following amendments are logged as tentative and require verification against specific standard sections before implementation:

| Amendment | What to verify | Sections |
|---|---|---|
| AM-09 | `ConditionalActionDecl` belongs to `ObjectDecl` not `RoleDecl` | §7.8.3, §7.8.4 |
| AM-12 | `DomainDecl` may participate as federation member | §7.5.1, §7.5.2 |
| V-NEW-04 Rule 2 | Exactly one controlling object per domain | §7.5.1 |
| V-NEW-06 | Single conflict resolution strategy per federation | §7.9.2 NOTE 3 |
| AM-15 | `ViolationResponseKind` enumeration completeness | §7.8.6 |

---

## 4. Amendment Summary

| ID | Type | Description |
|---|---|---|
| AM-01 | Grammar | `for_action` upgrade to `[ActionDecl]` |
| AM-02 | Grammar | Token classification axis — `token_role` qualifier |
| AM-03 | Grammar | `who_can_change` upgrade to `[ObjectDecl]` |
| AM-04 | Grammar | Scoped cross-references in `AssignmentPolicyDecl`, `JoinLeaveEffect` |
| AM-05 | Validator | `isa` scope validation for `RoleDecl` |
| AM-06 | Grammar + Validator | Merge `SubObjectiveRef`/`SatisfiesObjective` into `SatisfiesDecl` |
| AM-07 | Grammar | Scoped cross-references in `ActorRef`, `ArtefactRef`, `ResourceRef` |
| AM-08 | Grammar | Remove dead rule `BehaviourItem` |
| AM-09 | Grammar (tentative) | Move `ConditionalActionDecl` to `ObjectDecl` |
| AM-10 | Grammar | Remove `HoldsToken` from `RoleBodyItem` |
| AM-11 | Grammar | Remove `JoinLeaveEffect` — not ODP-EL concept |
| AM-12 | Grammar (tentative) | `DomainDecl` referenceable as community |
| AM-13 | Grammar | Rename `LifecycleDecl` to `CommunityLifecycleDecl` |
| AM-14 | Grammar | `domain_scope` upgrade to `[DomainDecl]` |
| AM-15 | Grammar | Add `ViolationResponseDecl` — missing §6.3.8/§7.8.6 |
| V-NEW-01 | Validator | Empty contract block |
| V-NEW-02 | Validator | Mandatory `ActionDecl` in `RoleDecl` |
| V-NEW-03 | Validator | `refines` scope in `StepDecl` |
| V-NEW-04 | Validator | `DomainDecl` mandatory objects and single controller |
| V-NEW-05 | Validator | `FederationDecl` minimum two members |
| V-NEW-06 | Validator | Single `ConflictResolutionDecl` per federation |
| V-NEW-07 | Validator | Empty `ChangesDecl` warning |
| V-NEW-08 | Validator | Mutual exclusion `on_objective_achieved` / `permanent` |
| V-NEW-09 | Validator | `EmbeddedCommitment` actor reference check |
| V-NEW-10 | Validator | Mutual exclusion `transfers_burden` / `transfers_token_group` |
| V-NEW-11 | Validator | Prescribing actor authority check |
| V-NEW-12 | Validator | `principals_obligated` against `principal_of` consistency |
| V-NEW-13 | Validator | `enterprise_concept` existence check |
| V-NEW-14 | Validator | Duplicate `CorrespondenceDecl` warning |
| DOC-01 | Documentation | Clarify community role vs action participation |
| DOC-02 | Documentation | `DomainDecl` as community type design decision |

---

_End of DSL-EL Design Notes v1.0_
_Produced during grammar walkthrough session, May 2026_

---

## 4. Object Processor Pipeline (Px)

### 4.1 What object processors are

textX object processors are post-parse hooks registered via
`mm.register_obj_processors()` in `el_parser.py`. They are called
automatically by textX after each grammar rule is instantiated from
the parse tree — before application code sees the model.

The registration call maps grammar rule names to Python callables:

```python
mm.register_obj_processors({
    'Community':          process_community,           # P2
    'Role':               process_role,                # P3
    'Action':             process_action,              # P4
    'ConditionalAction':  process_conditional_action,  # P5
    ...
})
```

### 4.2 Why they exist

textX parses everything into flat heterogeneous `items` lists (see §2.2
on unified alternation). Application code — the validator, engine, Kripke
model — needs typed sublists, unwrapped strings, and resolved references.
The Px processors bridge that gap for each grammar construct.

The pattern is consistent across all processors:
1. Iterate `obj.items`
2. Dispatch by `type(item).__name__`
3. Append to the appropriate typed sublist on the domain object
4. Set `obj.items = []` to signal that raw items have been consumed

### 4.3 Current processors

| Processor | Grammar rule | Key transformations |
|-----------|-------------|---------------------|
| P1 | `DescriptionAttr` (all elements) | Unwraps quoted string values |
| P2 | `Community` | Dissolves body into `roles`, `processes`, `policy_refs`, `lifecycle`, etc. |
| P3 | `Role` | Dissolves `role.items` → `role.actions`, `role.holds_tokens`, `role.conditional_actions`, etc. |
| P4 | `Action` | Dissolves `action.items` → `action.actors`, `action.artefacts`, `action.deontic_effects`, `action.favoured_by`, `action.emits`, etc. |
| P5 | `ConditionalAction` | Dissolves `ca.items` → `ca.favoured_by`, `ca.requires_permits`, `ca.inhibited_by`, `ca.deontic_effects`, etc. |
| P6 | `Step` | Dissolves step body items into typed sublists |
| P7 | `Process` | Unwraps `SatisfiesObjective` wrappers |

### 4.4 Bottom-up execution guarantee

textX calls processors **bottom-up** through the object graph. For a
`ConditionalAction` nested inside an `Action` inside a `Role`, the
execution order is:

P5 (ConditionalAction) → P4 (Action) → P3 (Role)

This means:
- When P4 runs on an `Action`, P5 has already populated `ca.favoured_by`
  on all nested `ConditionalAction` objects
- When P3 runs on a `Role`, P4 has already populated `action.favoured_by`
  on all nested `Action` objects

Application code can always depend on child processors having run before
parent processors. This makes the pipeline reliable for multi-level
transformations.

### 4.5 The ordered-choice pitfall (AM-25 lesson)

A subtle interaction exists between textX grammar ordered-choice semantics
and the Px pipeline. In a grammar alternation like:

```
ActionBodyItem:
    ActorRef | ArtefactRef | ResourceRef
  | PreconditionDecl | FavouredByItem | DeonticRequirement | DeonticEffect
  | EmitsDecl
;
```

**Order matters.** textX tries each alternative left-to-right and takes
the first match. If a broad rule (`DeonticRequirement`) precedes a specific
one (`FavouredByItem`), and both can match the same keyword
(`favoured_by_burden`), the broad rule wins and the specific rule is never
tried — silently.

AM-25 fixed exactly this: `FavouredByItem` was missing from `ActionBodyItem`
entirely, so `favoured_by_burden` in a plain `Action` body was consumed by
`DeonticRequirement` and discarded by P4 (which had no handler for
`DeonticRequirement` entries that were actually favour declarations).

**Rule:** when adding a new specific construct to an existing alternation,
always place it *before* any broader catch-all rule that could match the
same keyword. textX does not warn about shadowing.

### 4.6 Post-parse attribute names — always use Px output

After parsing, always use the **post-Px attributes**, never `obj.items`
(which is emptied by each processor). Key reminders:

| Raw (pre-Px, always empty post-parse) | Correct post-Px attribute |
|---------------------------------------|--------------------------|
| `role.items` | `role.actions`, `role.holds_tokens`, etc. |
| `action.items` | `action.deontic_effects`, `action.favoured_by`, etc. |
| `ca.items` | `ca.favoured_by`, `ca.requires_permits`, etc. |
| `ca.favoured_by_burden` | `ca.favoured_by` (P5 renames) |

This has been the source of several bugs (see commit history: 89a3a5b,
0157223, 5144fb7, ab22c87) where code used pre-Px attributes and silently
found empty lists.
