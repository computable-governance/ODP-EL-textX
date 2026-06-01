# `el_grammar.tx` — Amendment Log
_Session: DSL walkthrough review_

---

## AM-01 — `for_action` in `DeonticTokenDecl`

**Location:** `DeonticTokenDecl`, line ~133

**Current:**
```
('for_action' ':' for_action=STRING)?
```

**Issue:**
- `for_action` is a `STRING` (prose), so it cannot be machine-checked against actual `ActionDecl` names.
- The standard definition states a deontic token *"expresses a constraint on the ability of an active enterprise object holding it to perform certain actions"* — implying the action relationship should be verifiable.
- Optionality is justifiable for `burden`-as-standing-obligation (e.g. a reporting obligation not tied to a single action), but not for `permit` or `embargo` where the action relationship is central.

**Proposed changes:**
1. Upgrade to a cross-reference:
   ```
   ('for_action' ':' for_action=[ActionDecl])?
   ```
2. Add validator rule: if a `permit` or `embargo` token is declared and no `ActionDecl` references it via `DeonticReqDecl`, emit a warning — an embargo that inhibits nothing is likely a specification error.
3. Keep optional (do not make mandatory) to preserve the `burden`-as-standing-obligation pattern.

**Standard reference:** §6.4.3–6.4.5, §6.4.6

---

## AM-02 — Token classification: action-specific vs state tokens

**Location:** `DeonticTokenDecl`, `DeonticKind`

**Observation:**
The standard's `burden | permit | embargo` taxonomy captures deontic flavour but not token *role*. Two distinct roles emerge from the grammar analysis:

- **Action-specific token** — gates or constrains the occurrence of a named action (the `for_action` relationship is meaningful). Permits and embargoes are typically this kind.
- **State token** — represents a standing deontic condition of the object, not tied to a single action (e.g. a reporting obligation, an authorisation status). Burdens are often this kind, but not exclusively.

This is a second classification axis the standard does not explicitly name.

**Proposed change (tentative — not to change the standard, but to qualify within it):**
Consider an optional `token_role` qualifier:
```
('token_role' ':' token_role=TokenRole)?
TokenRole : 'action_specific' | 'standing' ;
```
This would:
- Make the distinction explicit and machine-checkable
- Allow the validator to enforce that `action_specific` tokens have a `for_action` reference
- Allow the validator to warn when a `standing` burden has a `for_action` (likely a modelling error)
- Not conflict with the standard — it is a refinement within the existing token concept

**Standard reference:** §6.4.3–6.4.6

---

## AM-03 — `who_can_change` in `SettingBehaviourDecl`

**Location:** `SettingBehaviourDecl`, line ~205

**Current:**
```
('who_can_change' ':' who_can_change=STRING)?
```

**Issue:**
`who_can_change` is prose — it cannot be machine-checked against declared parties or agents. Given that `ObjectDecl` names all parties and agents explicitly, this is a missed cross-reference opportunity. The validator cannot confirm that the named object actually exists, nor can the reasoner use it in accountability chain queries.

**Proposed change:**
```
('who_can_change' ':' who_can_change=[ObjectDecl])?
```

This makes the reference machine-verifiable and allows the reasoner to answer queries like *"which policies can this party change?"* directly from the model.

**Note:** If multiple objects may share policy-setting authority, consider upgrading to a list:
```
('who_can_change' ':' who_can_change+=[ObjectDecl]
    (',' who_can_change+=[ObjectDecl])*
)?
```

**Standard reference:** §7.9.3

---

## V-NEW-01 — Empty contract block validation

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
`ContractDecl` is mandatory but all its internal collections are optional (`*`), making `contract {}` syntactically valid. An empty contract is almost certainly a modelling oversight.

**Proposed change:**
Add a validator rule checking that at least one of `invariants`, `assignment_policies`, or `join_leave_effects` is non-empty. If all three are empty, emit:
> *"Contract block in community '{name}' is empty — at least one invariant, assignment policy, or join/leave effect is required."*

**Classification:** Validator change only — grammar stays as-is. This is correctly a semantic constraint, not a syntactic one.

**Standard reference:** §7.3.1

---

## AM-04 — Scoped cross-references for role names in `AssignmentPolicyDecl` and `JoinLeaveEffect`

**Location:** `AssignmentPolicyDecl` line ~293, `JoinLeaveEffect` line ~316

**Current:**
```
AssignmentPolicyDecl:
    'assignment_policy' 'for' role_name=ID '{'
        rules+=AssignmentRule+
    '}'
;

JoinLeaveEffect:
    (
        ('on_join'  role_name=ID 'transfer' token=[DeonticTokenDecl])
        | ('on_leave' role_name=ID 'revert'   token=[DeonticTokenDecl])
    )
;
```

**Issue:**
`role_name=ID` is a plain identifier — not a cross-reference. The validator must manually check that the named role exists in the enclosing community. This is fragile and duplicates logic that the grammar could express directly.

**Proposed change:**
Use textX scoped cross-reference path syntax to resolve against the enclosing community's `roles` list:
```
AssignmentPolicyDecl:
    'assignment_policy' 'for' role_name=[RoleDecl|ID|^roles] '{'
        rules+=AssignmentRule+
    '}'
;

JoinLeaveEffect:
    (
        ('on_join'  role_name=[RoleDecl|ID|^roles] 'transfer' token=[DeonticTokenDecl])
        | ('on_leave' role_name=[RoleDecl|ID|^roles] 'revert'   token=[DeonticTokenDecl])
    )
;
```

The `^roles` path tells textX to resolve the name against the `roles` attribute of the nearest enclosing `CommunityDecl`, making the reference machine-checkable at parse time.

**Classification:** Realistic grammar improvement — needs careful testing of the textX path expression in context. Eliminates corresponding validator logic if successful.

**Standard reference:** §7.3.1, §7.8.2, §7.8.7 NOTE 3

---

## AM-05 — `isa` scope validation for `RoleDecl`

**Location:** `RoleDecl` line ~350

**Issue:**
```
('isa' type_ref=[RoleDecl])?
```
`[RoleDecl]` is a global cross-reference — textX will resolve it against any `RoleDecl` in the entire spec. But §7.8.2 implies role inheritance should be constrained to the same community or a parent community. A role in `BorrowingCommunity` inheriting from a role in `PaymentCommunity` is semantically meaningless.

**Proposed change:**
Add a validator rule: when `type_ref` is set, confirm that the referenced `RoleDecl` belongs to the same `CommunityDecl` or to a community referenced via `isa` on the enclosing `CommunityDecl`.

**Classification:** Validator change — grammar cross-reference stays global (textX limitation), scope check done in validator.

**Standard reference:** §7.8.2

---

## AM-06 — `SubObjectiveRef` and `SatisfiesObjective` resolution scope (UPDATED)

**Location:** `SubObjectiveRef` line ~362, `SatisfiesObjective` line ~466

**Issue:**
Both rules use the same cross-reference pattern:
```
SubObjectiveRef:
    'satisfies' objective=[SubObjectiveDecl]   ← in RoleBodyItem
;

SatisfiesObjective:
    'satisfies' objective=[SubObjectiveDecl]   ← in ProcessDecl header
;
```
`SubObjectiveDecl` is nested inside `ObjectiveDecl` inside `CommunityDecl` — not a top-level declaration. textX's global name resolution may not reliably index nested objects, making both cross-references fragile.

**Grammar fix — merge into single reusable rule:**
Both rules are syntactically identical — merge into one:
```
SatisfiesDecl:
    'satisfies' objective=[SubObjectiveDecl]
;
```
Used in both `RoleBodyItem` and `ProcessDecl` header. One rule, one fix point.

**Validator fix:**
Add a validator fallback: if textX fails to resolve, manually search the enclosing community's `objective.sub_objectives` list by name. Test carefully against textX version behaviour.

**Classification:** Grammar cleanup (merge) + validator robustness fix.

**Standard reference:** §7.7

---

## V-NEW-03 — Validate `refines` scope in `StepDecl`

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
```
StepDecl:
    'step' name=ID
    ('refines' parent=[StepDecl])?
    ...
;
```
`[StepDecl]` is a global cross-reference — textX could silently resolve `refines` to a step belonging to a completely different process, which is semantically wrong. A step can only refine another step within the same enclosing process.

**Proposed validator rule:**
```python
def check_step_refines_scope(step, enclosing_process):
    if step.parent is not None:
        enclosing_steps = get_all_steps(enclosing_process)
        if step.parent not in enclosing_steps:
            raise TextXSemanticError(
                f"Step '{step.name}' refines '{step.parent.name}' "
                f"which belongs to a different process."
            )
```

**What the DSL user sees:**
> *"Step 'recordLoan' refines a step that does not belong to the same process."*

**Classification:** Validator change only — grammar cross-reference stays global (textX limitation), scope check enforced in validator.

**Standard reference:** §7.8.5

---

## DOC-01 — Clarify `RoleDecl` as community role vs action participation

**Location:** `RoleDecl` line ~349, grammar file header

**Issue:**
The word "role" appears in three subtly different senses in the standard and the grammar:

| Sense | Standard concept | Grammar construct |
|---|---|---|
| Community role | §6.2 — named placeholder filled by an active EO | `RoleDecl` inside `CommunityDecl` |
| Action participation | §7.8.4 — actor/artefact/resource classification | `ActorRef`, `ArtefactRef`, `ResourceRef` |
| Interface role | §6.3.5 — community role interacting outside boundary | `interface?='interface'` flag on `RoleDecl` |

A DSL user or maintainer may conflate community role with action participation role. The grammar handles them correctly and distinctly, but this is not stated explicitly anywhere in the file.

**Proposed change:**
Add a comment above `RoleDecl`:
```
/*
 * RoleDecl models community role per §6.2 — a named placeholder
 * for behaviour within a community, filled by an active enterprise
 * object at runtime.
 *
 * Action participation (actor/artefact/resource per §7.8.4) is
 * modelled separately via ActionBodyItem — it is NOT a role in
 * the community sense, though the standard uses the word informally.
 *
 * Interface roles (§6.3.5) are community roles marked with the
 * 'interface' keyword, indicating cross-boundary interactions.
 */
```

**Classification:** Documentation only — no grammar or validator change.

**Standard reference:** §6.2, §6.3.5, §7.8.4

---

## AM-07 — `RoleDecl` scoping: design decision and gap in `ActorRef`

**Location:** `ActorRef` line ~397, `RoleDecl` line ~349

**Design decision (to document):**
`RoleDecl` is correctly community-scoped by containment and should remain so. ODP-EL does not delegate roles — it delegates tokens and obligations. Cross-community role referencing is either a modelling error or is better expressed through `DelegationDecl` and `AuthorizationDecl`. No top-level `RoleDecl` reference is needed or desirable.

**Gap identified:**
Despite this design intent, `ActorRef` currently uses a plain `ID`:
```
ActorRef : 'actor' ':' role_name=ID ;
```
This means a user can silently reference a role from a different community inside an action — the grammar does not prevent it, and the validator's name-matching is fragile.

**Proposed change:**
Extend AM-04's scoped cross-reference fix to `ActorRef`, `ArtefactRef`, and `ResourceRef`:
```
ActorRef    : 'actor'    ':' role_name=[RoleDecl|ID|^roles] ;
ArtefactRef : 'artefact' ':' ref_name=[ObjectDecl|ID|^roles] ;
ResourceRef : 'resource' ':' ref_name=[ObjectDecl|ID|^roles]
              ('consumable' consumable?='consumable')? ;
```
This enforces community scoping at parse time, making the design intent explicit and machine-checkable.

**Note:** AM-04 and AM-07 should be implemented together as a single coherent scoping pass across the grammar.

**Classification:** Grammar improvement — extends AM-04. Realistic but requires careful textX path expression testing.

**Standard reference:** §6.2, §7.8.2, §7.8.4

---

## AM-08 — Remove dead rule `BehaviourItem`

**Location:** Lines 366–368

**Issue:**
```
BehaviourItem:
    ActionDecl | ConditionalActionDecl
;
```
`BehaviourItem` is defined but never referenced anywhere in the grammar. It is a remnant from before `RoleBodyItem` was unified into a single alternation. It is unreachable, adds confusion, and may generate textX warnings depending on version.

**Proposed change:**
Delete lines 366–368 entirely.

**Classification:** Grammar cleanup — straightforward removal, no semantic impact.

---

## V-NEW-02 — Mandatory `ActionDecl` in `RoleDecl`

**Location:** `RoleDecl` line ~341, `el_validator.py`

**Issue:**
```
items*=RoleBodyItem
```
`*` permits zero items, making an empty role body syntactically valid. The standard §6.2 defines a role as a placeholder *for behaviour* — a role with no `ActionDecl` is a contradiction in terms.

**Proposed change:**
Add a validator rule: after parsing, check that `role.items` contains at least one `ActionDecl` instance. If not, emit:
> *"Role '{name}' in community '{community}' declares no actions — at least one ActionDecl is required per §6.2."*

**Note:** Cannot be expressed in PEG grammar directly because `items` is a heterogeneous list. Validator responsibility.

**Classification:** Validator change only.

**Standard reference:** §6.2, §7.8.3

---

## AM-09 (TENTATIVE) — Move `ConditionalActionDecl` from `RoleDecl` to `ObjectDecl`

**Location:** `RoleBodyItem` line ~358, `ObjectBody` line ~94

**Rationale:**
§6.4.6 defines a conditional action as one whose initiation depends on deontic tokens held by **active enterprise objects** — not by roles. The token-conditioning chain is:

```
object fills role → acquires token → token conditions action
```

Conditioning happens at the **object level**, even when the token originates from role-filling. This suggests:

| Construct | Correct home | Reason |
|---|---|---|
| `ActionDecl` | `RoleDecl` | Expected behaviour of any object filling the role |
| `ConditionalActionDecl` | `ObjectDecl` | Conditioned by tokens the object holds — object-scoped |

**Proposed change (tentative):**
1. Remove `ConditionalActionDecl` from `RoleBodyItem`
2. Add `ConditionalActionDecl` to `ObjectBody`
3. `ActionDecl` remains mandatory in `RoleDecl` per V-NEW-02

**IMPORTANT:** Requires verification against §7.8.3 and §7.8.4 before implementation. This is a meaningful structural change — the standard must confirm that conditional actions are object-scoped not role-scoped.

**Classification:** TENTATIVE — pending standard verification. Do not implement until §7.8.3–7.8.4 reviewed.

**Standard reference:** §6.2, §6.4.3, §6.4.6, §7.8.3, §7.8.4

---

## AM-10 — Remove `HoldsToken` from `RoleBodyItem`

**Location:** `RoleBodyItem` line ~359

**Issue:**
```
RoleBodyItem:
    HoldsToken | PolicyRef | SubObjectiveRef | ActionDecl | ConditionalActionDecl
;
```
`HoldsToken` inside `RoleBodyItem` is semantically incorrect. The standard §6.4.3 is explicit: deontic tokens are carried by **active enterprise objects**, not by roles. A role declaring `holds borrowingPermit` is ambiguous — if the intent is that filling the role grants the token, that is a different mechanism entirely and is currently expressed (incorrectly) in two places.

**Agreed action:**
Remove `HoldsToken` from `RoleBodyItem`. Token holding belongs exclusively in `ObjectBody` as a static initial state declaration.

Any intent to grant a token upon role-filling must be expressed via an explicit `ActionDecl` with a `DeonticEffectDecl` (`create` or `transfer`) inside the role — which is the standard-compliant mechanism per §6.4.7.

Add validator rule: if a token is referenced in a role body (once cleaned up), check that a corresponding `DeonticEffectDecl` exists in an `ActionDecl` within that role.

**Classification:** Grammar change + validator rule. Related to AM-11.

**Standard reference:** §6.4.3, §6.4.7

---

## AM-11 — Reconsider `JoinLeaveEffect` — not an ODP-EL concept

**Location:** `ContractDecl` line ~278, `JoinLeaveEffect` line ~316

**Issue:**
`JoinLeaveEffect` was introduced as a grammar convenience:
```
JoinLeaveEffect:
    (
        ('on_join'  role_name=ID 'transfer' token=[DeonticTokenDecl])
        | ('on_leave' role_name=ID 'revert'   token=[DeonticTokenDecl])
    )
;
```
However `JoinLeaveEffect` has **no grounding in ODP-EL**. The standard does not define join/leave events or automatic token transfers triggered by role-filling. The correct standard mechanisms for token acquisition are:

| Mechanism | Standard concept | Grammar construct |
|---|---|---|
| Initial token state | §6.6.8 NOTE 3 | `HoldsToken` in `ObjectBody` |
| Token created by action | §6.4.7 | `DeonticEffectDecl` with `create` |
| Token transferred by action | §6.4.7 | `DeonticEffectDecl` with `transfer` |
| Token delegated | §6.6 | `DelegationDecl` |

**Agreed in session:**
Two options discussed:

- **Option A (preferred) — Remove `JoinLeaveEffect` entirely.** Token acquisition on role-filling is expressed via an explicit `ActionDecl` with `DeonticEffectDecl` inside the role body. Standard-compliant, unambiguous, consistent with AM-10.
- **Option B — Reframe as documented shorthand.** Keep the syntax but document explicitly as a derived convenience expanded by the reasoner into an implicit action. User-friendly but risks obscuring semantics.

**Option A is the agreed direction** — it is cleaner, honest to the standard, and consistent with the removal of `HoldsToken` from `RoleBodyItem` in AM-10.

**Note:** AM-10 and AM-11 are two facets of the same underlying issue — both stem from a conflation of role-level and object-level token semantics. They should be implemented together.

**Classification:** Grammar change — remove `JoinLeaveEffect` from `ContractDecl`. Implement together with AM-10.

**Standard reference:** §6.4.3, §6.4.7, §6.6.8 NOTE 3

---
---

## DOC-02 — `DomainDecl` is a community type, not a community reference

**Location:** `DomainDecl` line ~510, grammar file header

**Design decision (to document):**
`DomainDecl` is a **community type** per §7.5.1 — it is not a reference to a separately declared `CommunityDecl`. The domain declaration *itself* defines the community through its controlling and controlled objects. No `community:` reference attribute is needed or appropriate.

Add a comment above `DomainDecl`:
```
/*
 * DomainDecl models the <X>-domain community type per §7.5.1.
 * It IS the community declaration — not a reference to a CommunityDecl.
 * Controlling and controlled objects implicitly define membership.
 * Compare: FederationDecl which references existing CommunityDecls
 * as members — that is a different relationship entirely.
 */
```

**Classification:** Documentation only — no grammar or validator change.

**Standard reference:** §7.5.1

---

## V-NEW-04 — Validate `DomainDecl` mandatory objects and single controller

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
The grammar permits `body_items*` — zero items — making an empty domain body syntactically valid. Two semantic constraints must be enforced:

**Rule 1 — At least one controlling object and one controlled object required:**
```python
def check_domain_objects(domain):
    controlling = [i for i in domain.body_items 
                   if i.__class__.__name__ == 'DomainControllingObj']
    controlled  = [i for i in domain.body_items 
                   if i.__class__.__name__ == 'DomainControlledObj']
    if len(controlling) == 0:
        raise TextXSemanticError(
            f"Domain '{domain.name}' must declare at least one controlling_object."
        )
    if len(controlled) == 0:
        raise TextXSemanticError(
            f"Domain '{domain.name}' must declare at least one controlled_object."
        )
```

**Rule 2 — Exactly one controlling object (pending standard verification):**
```python
    if len(controlling) > 1:
        raise TextXSemanticError(
            f"Domain '{domain.name}' declares {len(controlling)} controlling objects "
            f"— §7.5.1 implies exactly one. Verify against standard."
        )
```

**Note:** Rule 2 should only be activated after §7.5.1 is verified — see AM-12.

**What the DSL user sees:**
> *"Domain 'ManagementDomain' must declare at least one controlling_object."*
> *"Domain 'ManagementDomain' declares 2 controlling objects — §7.5.1 implies exactly one."*

**Classification:** Validator change only.

**Standard reference:** §7.5.1

---

## AM-12 (TENTATIVE) — Consider making `DomainDecl` referenceable as a community

**Location:** `MemberRef` line ~586, `FederationDecl` line ~564

**Issue:**
`MemberRef` currently only accepts `CommunityDecl`:
```
MemberRef : 'member' ':' community=[CommunityDecl] ;
```
Since a domain *is* a community type (§7.5.1), it may be legitimate for a `DomainDecl` to participate as a federation member. Currently this is not possible — a domain cannot be referenced by `MemberRef`.

**Proposed change (tentative):**
Two options:

- **Option A** — Introduce a shared base type or union reference:
```
MemberRef : 'member' ':' community=[CommunityDecl|DomainDecl] ;
```
textX supports union cross-references in some versions — needs testing.

- **Option B** — Require domain communities to also have a `CommunityDecl` — but this duplicates declarations and is not preferred.

**IMPORTANT:** Requires verification against §7.5.1 and §7.5.2 — specifically whether the standard permits domain communities to be federation members.

**Classification:** TENTATIVE — pending standard verification. Do not implement until §7.5.1–7.5.2 reviewed.

**Standard reference:** §7.5.1, §7.5.2

---
---

## V-NEW-05 — Validate `FederationDecl` minimum membership

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
`body_items*` permits an empty federation body. A federation with fewer than two member communities is semantically invalid — a federation of zero or one community is not a federation.

**Proposed validator rule:**
```python
def check_federation_membership(federation):
    members = [i for i in federation.body_items
               if i.__class__.__name__ == 'MemberRef']
    if len(members) < 2:
        raise TextXSemanticError(
            f"Federation '{federation.name}' must declare at least two members "
            f"— a federation of {len(members)} community is not a federation."
        )
```

**What the DSL user sees:**
> *"Federation 'LibraryFederation' must declare at least two members — a federation of 1 community is not a federation."*

**Classification:** Validator change only.

**Standard reference:** §7.5.2

---

## V-NEW-06 — Validate single `ConflictResolutionDecl` per federation

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
`body_items*=FedBodyItem` allows `ConflictResolutionDecl` to appear multiple times — a federation could declare both `runtime_prevention` and `failure_handling`. §7.9.2 NOTE 3 implies one conflict resolution strategy per federation.

**Proposed validator rule:**
```python
def check_federation_conflict_resolution(federation):
    resolutions = [i for i in federation.body_items
                   if i.__class__.__name__ == 'ConflictResolutionDecl']
    if len(resolutions) > 1:
        raise TextXSemanticError(
            f"Federation '{federation.name}' declares {len(resolutions)} "
            f"conflict_resolution strategies — at most one is permitted per §7.9.2."
        )
```

**What the DSL user sees:**
> *"Federation 'LibraryFederation' declares 2 conflict_resolution strategies — at most one is permitted per §7.9.2."*

**Note:** Pending standard verification — §7.9.2 NOTE 3 should be checked to confirm whether multiple strategies are ever permissible (e.g. one per policy domain within the federation).

**Classification:** Validator change only — pending §7.9.2 verification.

**Standard reference:** §7.9.2 NOTE 3

---

## AM-12 (TENTATIVE) — updated: `MemberRef` concrete impact

**Cross-reference to AM-12 logged earlier.**

The concrete grammar location where AM-12 bites is:
```
MemberRef : 'member' ':' community=[CommunityDecl] ;
```
A `DomainDecl` cannot currently be a federation member. If §7.5.1–7.5.2 verification confirms domains may federate, this is the exact line to change. See AM-12 for proposed options.

---
---

## AM-13 — Rename `LifecycleDecl` to `CommunityLifecycleDecl`

**Location:** `LifecycleDecl` line ~610, `CommunityDecl` line ~236

**Issue:**
`LifecycleDecl` is ambiguous — lifecycles could apply to communities, tokens, federations, or objects. The name gives no indication of scope.

**Proposed change:**
Rename `LifecycleDecl` to `CommunityLifecycleDecl` throughout the grammar:

```
// Current
(lifecycle=LifecycleDecl)?

// Proposed
(lifecycle=CommunityLifecycleDecl)?
```

And rename the rule itself:
```
// Current
LifecycleDecl:
    'lifecycle' '{'
        ...
    '}'
;

// Proposed
CommunityLifecycleDecl:
    'lifecycle' '{'
        ...
    '}'
;
```

**Rationale:**
- Unambiguous — immediately signals what is governed
- Consistent with existing naming pattern (`CommunityDecl`, `CommunityInteraction`)
- Directly maps to §7.6 — Community Lifecycle

**Note:** Pure rename — no semantic, validator, or DSL syntax changes required. The keyword `'lifecycle'` in the source file remains unchanged — only the grammar rule name changes.

**Classification:** Grammar rename — straightforward, no semantic impact.

**Standard reference:** §7.6

---
---

## V-NEW-07 — Warn on empty `ChangesDecl`

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
A `changes {}` block with no dynamic flags set but only a `description` is syntactically valid but semantically empty — declaring a changes block implies something changes.

**Proposed validator rule:**
```python
def check_changes_not_empty(changes):
    if not any([changes.roles_dynamic,
                changes.policies_dynamic,
                changes.membership_dynamic]):
        raise TextXSemanticWarning(
            f"'changes' block declared but no dynamic flags set "
            f"(roles_dynamic, policies_dynamic, membership_dynamic). "
            f"If nothing is dynamic, omit the changes block entirely."
        )
```

**Note:** This should be a **warning** not an error — the specifier may be using the description field alone as a documentation note. Severity: warning.

**What the DSL user sees:**
> *"'changes' block declared but no dynamic flags set — if nothing is dynamic, omit the changes block entirely."*

**Classification:** Validator warning only.

**Standard reference:** §7.6.3

---

## V-NEW-08 — Mutual exclusion of `on_objective_achieved` and `permanent` in `TerminatingDecl`

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
`on_objective_achieved: true` and `permanent: true` are mutually exclusive — a community cannot both terminate when its objective is achieved and never terminate. The grammar permits both flags simultaneously.

**Proposed validator rule:**
```python
def check_terminating_flags(terminating):
    if terminating.on_objective and terminating.permanent:
        raise TextXSemanticError(
            f"'terminating' block declares both 'on_objective_achieved' "
            f"and 'permanent' — these are mutually exclusive per §7.6.4."
        )
```

**What the DSL user sees:**
> *"'terminating' block declares both 'on_objective_achieved' and 'permanent' — these are mutually exclusive per §7.6.4."*

**Classification:** Validator error.

**Standard reference:** §7.6.4 NOTE 2

---

## V-NEW-09 — Validate `EmbeddedCommitment` actor references in `EstablishingDecl`

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
```
EmbeddedCommitment:
    'commitment' 'by' actor_name=ID ':' description=STRING
;
```
`actor_name=ID` is a plain identifier — not a cross-reference to `ObjectDecl`. At establishing time, actors may not yet be formally declared, so strict cross-reference resolution is not appropriate at grammar level. However the validator should loosely check that the named actor is eventually declared somewhere in the spec.

**Proposed validator rule:**
```python
def check_embedded_commitment_actors(spec):
    declared_names = {obj.name for obj in spec.elements
                      if obj.__class__.__name__ == 'ObjectDecl'}
    for community in get_communities(spec):
        if community.lifecycle and community.lifecycle.establishing:
            for commitment in community.lifecycle.establishing.commitments:
                if commitment.actor_name not in declared_names:
                    raise TextXSemanticWarning(
                        f"EmbeddedCommitment actor '{commitment.actor_name}' "
                        f"in community '{community.name}' is not declared "
                        f"as an ObjectDecl in this specification."
                    )
```

**Note:** Warning not error — founding actors may legitimately be external to the spec scope. Severity: warning.

**What the DSL user sees:**
> *"EmbeddedCommitment actor 'ResearchOfficeHead' in community 'ResearchAccessCommunity' is not declared as an ObjectDecl in this specification."*

**Classification:** Validator warning only.

**Standard reference:** §7.6.1

---
---

## V-NEW-10 — Mutual exclusion of `transfers_burden` and `transfers_token_group` in `DelegationDecl`

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
```
('transfers_burden'      ':' burden=[DeonticTokenDecl])?
('transfers_token_group' ':' token_group=[TokenGroupDecl])?
```
Both are optional but mutually exclusive — a delegation either transfers a single burden or a token group, not both. The grammar permits both simultaneously.

**Proposed validator rule:**
```python
def check_delegation_transfer(delegation):
    if delegation.burden and delegation.token_group:
        raise TextXSemanticError(
            f"Delegation '{delegation.name}' declares both "
            f"'transfers_burden' and 'transfers_token_group' "
            f"— these are mutually exclusive."
        )
```

**What the DSL user sees:**
> *"Delegation 'boardToDirectorDelegation' declares both 'transfers_burden' and 'transfers_token_group' — these are mutually exclusive."*

**Classification:** Validator error.

**Standard reference:** §6.6.6, §7.10.1

---

## AM-13 — `discharge_mode` in `DeonticTokenDecl` (modal obligation construct)

**Location:** `DeonticTokenDecl`, after `deadline` field

**Motivation:**
Layer 4 (Kripke semantics, `el_kripke.py`) revealed a formal gap: the delegation
chain `GPPracticeParty → SpecialistAgent → AIDiagnosticAgent` creates the
obligation but does not compel discharge. The modal operator AF(discharged)
fails because the agent can defer action indefinitely until the deadline is
violated. The delegation structure guarantees permission (EF) but not
inevitability (AF).

To make AF hold by construction, the obligation must express that the holder
is required to act at the first available opportunity — no delay is permitted.
This requires a grammar construct that instructs the Layer 4 engine to suppress
the TICK transition (time-passing without acting) when the obligation is pending
and the holder is active.

**Grammar change:**

```
DeonticTokenDecl:
    kind=DeonticKind name=ID '{'
        ('for_action'      ':' for_action=STRING)?
        'state'            ':' state=TokenState
        ('deadline'        ':' deadline=STRING)?
        ('discharge_mode'  ':' discharge_mode=DischargeMode)?   ← NEW
        ('description'     ':' description=STRING)?
        ...
    '}'
;

DischargeMode  : 'eventual' | 'strict' ;   ← NEW
```

**Semantics:**

| `discharge_mode` | TICK available? | AF(discharged) | EF(discharged) | Meaning |
|---|---|---|---|---|
| `eventual` (default) | Yes | May fail | Yes | Holder *may* delay; obligation will possibly discharge |
| `strict` | No | Yes | Yes | Holder *must* discharge at first opportunity |

`eventual` preserves existing behaviour — unspecified discharge_mode defaults
to `eventual`. No existing specifications are broken.

**Layer 4 effect (`el_kripke.py`):**

T3 (TICK) is only added as a transition if at least one pending obligation
has `discharge_mode == 'eventual'`. If all pending obligations are `strict`,
TICK is suppressed — the only available transitions are T1 (discharge) or
T2 (violation if past deadline). Since T1 is always available when the holder
is active and step < deadline, every path reaches DISCHARGED and AF holds.

**Validation:**

```
Payment processing spec  (eventual, default): AF ✗ NOT SATISFIED
Consent scenario spec    (strict):            AF ✓ SATISFIED
```

Model sizes:
- eventual: 31 worlds (includes tick chain and violation worlds)
- strict:   2 worlds  (PENDING → DISCHARGED only; no delay permitted)

**DSL example:**

```
burden seekConsentObligation {
    for_action: "seek_patient_consent"
    state: active
    deadline: "clinical session"
    discharge_mode: strict
    description: "..."
}
```

**Standard reference:** §6.4.3 (burden semantics), Annex C §C.2 (AF operator),
Annex C §C.4 (utility-prioritised behaviour).

**Classification:** Grammar addition — new optional field and rule. No changes
to existing constructs. Backwards compatible.

**Files changed:** `el_grammar.tx` (DeonticTokenDecl, DischargeMode rule),
`el_kripke.py` (ObligationDescriptor.discharge_mode, T3 rule),
`consent_scenario.el` (new validation spec).

---

## AM-15 — `priority` in `DeonticTokenDecl` (weighted utility for §C.3)

**Location:** `DeonticTokenDecl`, after `discharge_mode` field

**Motivation:**
Annex C §C.3 states that the binary satisfaction relation "gives no guidance
on how to approximate an objective that cannot be fully satisfied." The utility
function must be defined "on the basis of the variables that characterise"
each world — implying weights should be specifiable by the modeller, not
hardcoded uniformly.

Without priority weights, the utility function treats a violated consent
obligation identically to a violated reporting obligation. This contradicts
the governance intent: consent is a patient safety matter; reporting is an
administrative burden. The utility function should reflect this ordering.

**Grammar change:**

```
DeonticTokenDecl:
    kind=DeonticKind name=ID '{'
        ...
        ('priority'  ':' priority=PriorityLevel)?   ← NEW
        ...
    '}'
;

PriorityLevel  : 'critical' | 'high' | 'normal' | 'low' ;   ← NEW
```

**Priority-to-weight mapping:**

| PriorityLevel | Weight | Governance meaning |
|---|---|---|
| `critical` | 1.00 | Must not be violated — patient safety, regulatory |
| `high`     | 0.75 | Strongly preferred to discharge |
| `normal`   | 0.50 | Default — equal weight (absent = normal) |
| `low`      | 0.25 | Desirable but secondary |

**Weighted utility formula (§C.3):**

```
utility(w) = Σ(score(state_i) × weight_i) / Σ(weight_i)
```

Outcome scores: DISCHARGED=+1.0, PENDING=+0.3, EXPIRED=0.0, VIOLATED=-1.0.
Result normalised to [-1, +1].

**Example — consent (critical) + reporting (low):**

| World | Utility | Reasoning |
|---|---|---|
| consent=DISCHARGED, reporting=DISCHARGED | +1.000 | Both met |
| consent=DISCHARGED, reporting=PENDING   | +0.860 | Critical met, low in progress |
| consent=DISCHARGED, reporting=VIOLATED  | +0.600 | Critical met, low missed — still acceptable |
| consent=PENDING, reporting=DISCHARGED   | +0.440 | Critical unresolved — poor |
| consent=VIOLATED, reporting=DISCHARGED  | −0.600 | Critical violated — unacceptable |

The ranking correctly reflects governance intent: a violated consent obligation
dominates even when reporting is discharged.

**Interaction with AM-13 (discharge_mode):**

The T3 TICK rule was also refined: TICK is blocked if any strict obligation
is PENDING and its holder is ACTIVE — even when eventual obligations also
exist. This ensures strict obligations are always discharged before time
can pass, regardless of co-existing eventual obligations.

**DSL example:**

```
burden seekConsentObligation {
    state: active
    deadline: "clinical session"
    discharge_mode: strict
    priority: critical
}

burden reportingObligation {
    state: active
    deadline: "end of session"
    discharge_mode: eventual
    priority: low
}
```

**Standard reference:** §C.3 (utility function), §C.4 (prioritising behaviours),
§6.4.3 (burden semantics).

**Classification:** Grammar addition — new optional field and rule. Fully
backwards compatible; absent priority defaults to `normal` (weight=0.5).

**Files changed:** `el_grammar.tx` (DeonticTokenDecl, PriorityLevel rule),
`el_kripke.py` (_priority_weight helper, ObligationDescriptor.priority_weight,
utility() weighted formula, T3 rule refinement), `consent_scenario.el`
(priority fields on both burdens, reportingObligation added).

---

## AM-14 — `domain_scope` in `AuthorizationDecl` should be `[DomainDecl]`

**Location:** `AuthorizationDecl` line ~730

**Current:**
```
('domain_scope' ':' domain_scope=STRING)?
```

**Issue:**
`domain_scope` names the domain within which the authorization is valid. `DomainDecl` exists in the grammar — this should be a proper cross-reference, not prose.

**Proposed change:**
```
('domain_scope' ':' domain_scope=[DomainDecl])?
```

This makes the domain scope machine-verifiable — the validator can confirm the named domain exists and that the authorized agent operates within it.

**Classification:** Grammar change — straightforward cross-reference upgrade.

**Standard reference:** §6.6.4, §7.10.2

---

## V-NEW-11 — Validate prescribing actor authority in `PrescriptionDecl`

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
§6.6.3 requires the prescribing actor to have legitimate authority — either a `party` by kind, previously specified to establish rules, or delegated the permit to prescribe. The grammar captures the permit case via `requires_permit` but does not enforce the party-by-nature case.

**Proposed validator rule:**
```python
def check_prescription_authority(prescription, spec):
    actor = prescription.actor
    if prescription.permit is None:
        # No permit declared — actor must be a party by kind
        if actor.kind != 'party':
            raise TextXSemanticError(
                f"PrescriptionDecl '{prescription.name}': actor "
                f"'{actor.name}' is not a party and declares no "
                f"requires_permit — prescribing authority cannot "
                f"be established per §6.6.3."
            )
```

**What the DSL user sees:**
> *"PrescriptionDecl 'researchAccessRule': actor 'HeadLibrarian' is not a party and declares no requires_permit — prescribing authority cannot be established per §6.6.3."*

**Classification:** Validator error.

**Standard reference:** §6.6.3, §7.10.5

---

## V-NEW-12 — Validate `principals_obligated` against `principal_of` in `CommitmentDecl`

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
```
('principals_obligated' ':'
    principals+=[ObjectDecl]
    (',' principals+=[ObjectDecl])*
)?
```
Each named principal should be declared as `principal_of` the committing actor in their `ObjectBody`. Currently the grammar accepts any `ObjectDecl` as a principal — the validator must check the relationship is properly declared.

**Proposed validator rule:**
```python
def check_commitment_principals(commitment, spec):
    actor = commitment.actor
    declared_principals = {
        p.agent.name
        for p in (actor.body.principal_of if actor.body else [])
    }
    for principal in commitment.principals:
        if principal.name not in declared_principals:
            raise TextXSemanticError(
                f"CommitmentDecl '{commitment.name}': "
                f"'{principal.name}' is listed as principals_obligated "
                f"but is not declared as principal_of '{actor.name}' "
                f"in their ObjectDecl."
            )
```

**What the DSL user sees:**
> *"CommitmentDecl 'boardResearchCommitment': 'HeadLibrarian' is listed as principals_obligated but is not declared as principal_of 'LibraryBoard' in their ObjectDecl."*

**Classification:** Validator error.

**Standard reference:** §6.6.2, §7.10.3

---
---

## V-NEW-13 — Validate `enterprise_concept` in `CorrespondenceDecl`

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
```
'correspondence' enterprise_concept=ID
```
`enterprise_concept` is a plain identifier — not a cross-reference. The validator should check that it names an actual declared element in the specification.

**Proposed validator rule:**
```python
def check_correspondence_enterprise_concept(correspondence, spec):
    declared_names = {
        el.name for el in spec.elements
        if hasattr(el, 'name')
    }
    if correspondence.enterprise_concept not in declared_names:
        raise TextXSemanticError(
            f"CorrespondenceDecl references enterprise concept "
            f"'{correspondence.enterprise_concept}' which is not "
            f"declared anywhere in this specification."
        )
```

**Note:** `hasattr(el, 'name')` covers all named constructs — `CommunityDecl`, `ObjectDecl`, `RoleDecl`, `ProcessDecl`, `DeonticTokenDecl`, and all speech act declarations. RoleDecl requires special handling since it is nested inside CommunityDecl — the check must recurse into community bodies.

**What the DSL user sees:**
> *"CorrespondenceDecl references enterprise concept 'BorrowingComunity' which is not declared anywhere in this specification."*

**Classification:** Validator error.

**Standard reference:** §11.2–11.5

---

## V-NEW-14 — Warn on duplicate `CorrespondenceDecl` entries

**Location:** `el_validator.py` (not a grammar change)

**Issue:**
Multiple `CorrespondenceDecl` entries with the same `enterprise_concept`, `viewpoint`, and `viewpoint_concept` are syntactically valid but almost certainly a copy-paste error.

**Proposed validator rule:**
```python
def check_duplicate_correspondences(spec):
    seen = set()
    correspondences = [el for el in spec.elements
                       if el.__class__.__name__ == 'CorrespondenceDecl']
    for c in correspondences:
        key = (c.enterprise_concept, c.viewpoint, c.viewpoint_concept)
        if key in seen:
            raise TextXSemanticWarning(
                f"Duplicate CorrespondenceDecl: '{c.enterprise_concept}' "
                f"to {c.viewpoint}:'{c.viewpoint_concept}' "
                f"is declared more than once."
            )
        seen.add(key)
```

**Note:** Warning not error — one enterprise concept mapping to multiple concepts in the same viewpoint is legitimate (e.g. `BorrowingCommunity` mapping to both `IBorrowingService` and `IReservationService` in computational). Only exact triples are flagged. Severity: warning.

**What the DSL user sees:**
> *"Duplicate CorrespondenceDecl: 'BorrowingCommunity' to computational:'IBorrowingService' is declared more than once."*

**Classification:** Validator warning only.

**Standard reference:** §11.2–11.5

---
_Further amendments to be added during walkthrough._
