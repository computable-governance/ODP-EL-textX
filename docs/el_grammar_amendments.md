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

**Status:** IMPLEMENTED (2026-08-22, AM-51). Registered in
`el_validator.py::_validate_delegations()`, wired into `validate_spec()`'s
existing dispatch (already called for V-07/V-08). Message text matches the
proposed rule below verbatim, as an appended error string (this validator's
established convention — no rule here raises `TextXSemanticError` directly,
including the pre-existing V-07/V-08 in the same function) rather than the
raise-based pseudocode. See AM-51 for the accompanying `el_kripke.py` fix
this rule's registration depended on, and `docs/CONCEPTS_INDEX.md`'s AM-51
entry for the full causal story.

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

---

## AM-26 — Fix `TokenGroup` arpeggio cross-reference list bug; add `TokenGroupMember`

**Standard references:** ISO 15414 §6.4.2

**Rationale:**
The original `TokenGroup` rule used a comma-separated `[DeonticToken]*` list:
```
TokenGroup:
    'token_group' name=ID '{'
        tokens+=[DeonticToken]
        (',' tokens+=[DeonticToken])*
    '}'
;
```
This triggers the confirmed arpeggio/textX bug (CLAUDE.md §5.3): a
comma-separated `[Rule]*` cross-reference list causes arpeggio to continue
consuming tokens as cross-reference candidates, silently breaking subsequent
sub-rule matches. No existing scenario used `token_group`, so clean
replacement (no migration) was possible.

**Grammar changes (`grammar/v2/el_grammar.tx`):**
- Replaced the `TokenGroup` body with `(members+=TokenGroupMember)*` —
  one `member: <token>` declaration per member, mirroring the `MemberRef`
  pattern used in `Federation`.
- Added new `TokenGroupMember` rule: `'member' ':' token=[DeonticToken]`.

**Domain class changes (`toolchain/el_domain.py`):**
- `TokenGroup`: replaced single `tokens: List` field with two fields:
  `members: List` (populated by textX from grammar; cleared by P10) and
  `tokens: List` (populated by P10 from unwrapped members). Callers always
  read `group.tokens` — the `members` list is a parsing artefact only.
- Added new `TokenGroupMember` dataclass with single `token: Optional[object]`
  field (cross-reference to `DeonticToken`).
- Added `TokenGroupMember` to `DOMAIN_CLASSES`.

**Parser changes (`toolchain/el_parser.py`):**
- Added `process_token_group` (P10): iterates `group.members`, appends
  `m.token` to `group.tokens` for each non-None member, then clears
  `group.members`.
- Registered `'TokenGroup': process_token_group` in
  `mm.register_obj_processors`.

**Status:** CONFIRMED

---

## AM-27 — `SatisfactionCondition` on `Objective`: machine-checkable community goal

**Standard references:** ISO 15414 §6.2, §7.7

**Rationale:**
The `Objective` rule previously held only a free-text `description` string. This
gave no way for the toolchain to determine programmatically whether a community
objective had been achieved. The Layer 4 Kripke verifier needed a structured
condition it could evaluate against world state to emit
`objective_satisfied:<community>` propositions, enabling CTL reasoning over
goal achievement.

**Grammar changes (`grammar/v2/el_grammar.tx`):**
- Added optional `('satisfaction' ':' satisfaction=SatisfactionCondition)?`
  to the `Objective` rule, between `description` and `sub_objectives`.
- Added new `SatisfactionCondition` rule:
  ```
  SatisfactionCondition:
      operator=SatisfactionOp '(' group=[TokenGroup] ')'
  ;
  SatisfactionOp: 'all_discharged' | 'any_discharged' ;
  ```
  `group` is a cross-reference to a top-level `TokenGroup` declaration.
  Operator semantics:
  - `all_discharged` — every member of the group is DISCHARGED or SUPERSEDED
  - `any_discharged` — at least one member of the group is DISCHARGED

**Domain class changes (`toolchain/el_domain.py`):**
- Added `SatisfactionCondition` dataclass with fields `operator: str` and
  `group: Optional[object]` (→ `TokenGroup` ref).
- Added `satisfaction: Optional[object]` field to `Objective` (→
  `SatisfactionCondition`).
- Added `SatisfactionCondition` to `DOMAIN_CLASSES`.

**Kripke verifier changes (`toolchain/el_kripke.py`):**
- Added `_build_satisfaction_conditions(model)` helper: scans all
  `Community`, `Federation`, and `Domain` elements for objectives with a
  `SatisfactionCondition`; returns
  `{community_name: (operator, [member_token_ids])}`.
- Extended `_build_propositions(world, satisfaction_conditions=None)`:
  evaluates each condition against the world's `obligation_states` and adds
  `objective_satisfied:<community_name>` to the proposition set when satisfied.
  SUPERSEDED counts as resolved for `all_discharged`; only DISCHARGED satisfies
  `any_discharged`.
- `KripkeModel` carries a `satisfaction_conditions` field populated by both
  `build_kripke_model()` and `build_kripke_from_runtime()`.

**Usage in `.el` files:**
```
token_group ConsentGroup {
  member: seekConsentObligation
  member: informPatientObligation
}

community ConsentCommunity {
  objective: "Obtain patient consent before AI diagnosis"
    satisfaction: all_discharged(ConsentGroup)
  ...
}
```

**Status:** CONFIRMED

---

## AM-25 — Federation as community type: `contract` qualifier, mandatory `objective`, `EventDecl` body, `Domain` inherits `Community`

**Standard references:** ISO 15414 §7.5, §7.5.1, §7.5.2, §7.7

**Rationale:**
§7.5 states that `<X>-domain` and `<X>-federation` are both **community types** —
they ARE communities, not separate structural concepts. The grammar modelled
`Domain` and `Federation` as independent rules, causing `MemberRef` (which
references `[Community]`) to fail when federation members are `Domain`
declarations. This is AM-12 (tentative) resolved.

**Grammar changes (`grammar/v2/el_grammar.tx`):**

1. `Federation`: add `(contract?='contract')?` qualifier before `'federation'`
   keyword — mirrors the same qualifier on `Community` (AM-21); federation
   documents a contractual arrangement between autonomous communities.

2. `Federation`: add mandatory `objective=Objective` as the first item inside
   the body block — every community type requires an objective per §7.7.
   Matches the structural pattern of `Community`.

3. `FedBodyItem`: add `| EventDecl` alternative — federations may declare
   scoped events for cross-community state changes (AM-22 pattern).

**Domain class changes (`toolchain/el_domain.py`):**

4. `Domain` now inherits `Community` instead of `_ELNode`. textX uses
   `isinstance()` when resolving `[Community]` cross-references; making
   `Domain` a Python subclass of `Community` makes Domain instances valid
   targets for `MemberRef.community`. Fields already present in Community
   (`name`, `description`, `policy_refs`, `events`, `invariants`) are
   inherited and not redeclared. Domain-specific fields retained:
   `relationship` (characterized_by), `body_items`, `controlling_objects`,
   `controlled_objects`.

5. `Federation`: added `contract: bool = False`, `objective: Optional[Objective] = None`,
   and `events: List` fields to mirror the grammar additions.

**Parser change (`toolchain/el_parser.py`):**

6. `process_federation` (P9): added `EventDecl` branch — appends items to
   `fed.events`. Note: `objective` is set directly by textX as a grammar
   attribute and requires no P9 handling.

**Resolves:** AM-12 (tentative) — `MemberRef` accepting Domain as a community
member. AM-12 is now CONFIRMED and closed by this amendment.

**Status:** CONFIRMED

---

## AM-19 — Capture `kind` in `JoinLeaveEffect`; boolean flag for `unpoliced` in `Enforcement`

**Location:** `JoinLeaveEffect` line ~331; `Enforcement` line ~232

**Fix 1 — `JoinLeaveEffect`:**

Without a named attribute, textX has no field to record which alternative
(`on_join` vs `on_leave`) matched — the keyword was consumed but not stored.
Object processors and downstream code could not distinguish the two cases.

```
// Before
JoinLeaveEffect:
    (
        ('on_join' role_name=ID 'transfer' token=[DeonticToken])
        | ('on_leave' role_name=ID 'revert' token=[DeonticToken])
    )
;

// After
JoinLeaveEffect:
    ( kind='on_join'  role_name=ID 'transfer' token=[DeonticToken] )
    | ( kind='on_leave' role_name=ID 'revert'   token=[DeonticToken] )
;
```

`kind` is a string assignment — textX sets it to `'on_join'` or `'on_leave'`
depending on which alternative matched.

**Fix 2 — `Enforcement`:**

`'unpoliced'` as a bare keyword was consumed but produced no field on the
object — code could not test whether enforcement was policed or unpoliced
without checking for the absence of `mode`.

```
// Before
        | 'unpoliced'

// After
        | (unpoliced?='unpoliced')
```

`unpoliced?=` is a boolean assignment — textX sets `unpoliced = True` when
the keyword is matched.

**Standard reference:** §7.8.7 NOTE 3 (join/leave effects); §7.9.4 (enforcement modes)

**Status:** CONFIRMED

---

## AM-15 — Rename `ObjectDecl` → `EnterpriseObjectDecl`

**Location:** `ObjectDecl` rule definition and all 16 cross-references throughout
the grammar.

**Motivation:**
The generic name `ObjectDecl` creates a namespace collision risk as the
computable-governance project develops separate DSLs for the other four ODP
viewpoints (computational, information, engineering, technology). Each viewpoint
has its own object taxonomy (computational object, information object, etc.),
and if each viewpoint DSL uses `ObjectDecl` as its object rule name, cross-
viewpoint tooling that loads multiple grammars will face both keyword and Python
class name collisions.

Renaming to `EnterpriseObjectDecl` at this stage:
1. Makes the viewpoint origin self-documenting in the grammar
2. Allows future viewpoint DSLs to follow the same convention
   (`ComputationalObjectDecl`, `InformationObjectDecl`, etc.) without collision
3. Aligns the grammar rule name directly with the target Python class name
   `EnterpriseObject` — no surprise renaming needed in the `classes=` mapping

**Cross-viewpoint naming convention established:**
`<Viewpoint>ObjectDecl` in grammar → `<Viewpoint>Object` in Python domain class.
All future viewpoint DSLs should follow this pattern.

**Changes applied:**
- Rule definition: `ObjectDecl:` → `EnterpriseObjectDecl:`
- `SpecElement` dispatch: `| ObjectDecl` → `| EnterpriseObjectDecl`
- `isa` self-reference: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `DelegatedFromDecl.delegator`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `PrincipalOfDecl.agent`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `DomainControllingObj.obj`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `DomainControlledObj.obj`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `CommitmentDecl.actor`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `CommitmentDecl.principals`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `DelegationDecl.delegator`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `DelegationDecl.delegate`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `AuthorizationDecl.authority`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `AuthorizationDecl.authorized_agent`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `PrescriptionDecl.actor`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `DeclarationDecl.actor`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- `EvaluationDecl.evaluator`: `[ObjectDecl]` → `[EnterpriseObjectDecl]`
- Header comment: `→ ObjectDecl` → `→ EnterpriseObjectDecl`

**Standard reference:** §6.3, §6.6.1, §6.6.8, §7.4

**Status:** CONFIRMED

---

## AM-16 — Remove dead `BehaviourItem` rule

**Location:** Lines ~376–378 in the original grammar (between `SubObjectiveRef`
and the `ActionDecl` section header).

**Current (removed):**
```
BehaviourItem:
    ActionDecl | ConditionalActionDecl
;
```

**Issue:**
`BehaviourItem` is defined but never referenced by any other grammar rule.
`RoleBodyItem` (the actual dispatch rule used in `RoleDecl`) already includes
`ActionDecl` and `ConditionalActionDecl` directly. `BehaviourItem` is therefore
a dead rule that adds noise without contributing to the grammar.

**Change:** Rule deleted entirely.

**Impact:** None — no other rule references `BehaviourItem`. Confirmed by
`grep BehaviourItem el_grammar.tx` returning no results after deletion.

**Standard reference:** §6.3.6, §6.4.6 (the concepts remain; only the dead
rule is removed)

**Status:** CONFIRMED

---

## AM-17 — Add `ViolationResponseDecl` as a top-level declaration

**Standard references:** §6.3.8, §7.8.6, §7.8.6 NOTE 2

**Standard basis (read directly from ISO/IEC 15414:2015):**

§6.3.8 defines: *"violation: A behaviour contrary to that required by a
rule. NOTE — A rule or policy may provide behaviour which is to occur upon
violation of that, or some other, rule or policy."*

§7.8.6 states: *"An enterprise specification can provide mechanisms for
detecting violations and for appropriate recovery or sanction mechanisms."*

§7.8.6 NOTE 2 states: *"An enterprise specification may include a rule
prescribing types of actions to be taken by an object in the event of
certain types of violations. That rule is an obligation, which applies to
that object. Failure to take the prescribed actions is a violation of
that rule."*

**Design rationale:**

§7.8.6 NOTE 2 makes the modelling decision explicit: a violation response
is itself a *prescribed obligation* (a burden) on the responding actor —
not a property of the violated token. This rules out an inline sub-block
inside `DeonticTokenDecl` and points instead to a top-level declaration
that:

1. References the burden whose violation triggers the response
2. Identifies which actor is obligated to respond
3. Creates a new burden on that actor as the prescribed consequence
4. Optionally specifies the response kind and description

This keeps `ViolationResponseDecl` within the existing speech act
vocabulary (it is a specialised form of prescription/obligation) and
means violation response participates in the same accountability chain
reasoning as any other obligation. A violation of the response burden
is itself a violation of a rule (§7.8.6 NOTE 2, second sentence) —
this nesting is handled correctly because `creates_burden` is a
cross-reference to a `DeonticTokenDecl`.

**Grammar addition — new rule added to `SpecElement` dispatch and
defined after `EvaluationDecl`:**

```
SpecElement:
    ...
    | EvaluationDecl
    | ViolationResponseDecl     ← added
    | CorrespondenceDecl
;

/*
 * ViolationResponseDecl — §6.3.8, §7.8.6, §7.8.6 NOTE 2
 *
 * Declares the prescribed obligation that applies to a specified actor
 * when a named burden is violated (i.e. not discharged by its deadline).
 *
 * §7.8.6 NOTE 2: "A rule prescribing types of actions to be taken by
 * an object in the event of certain types of violations. That rule is
 * an obligation, which applies to that object."
 *
 * response_kind values:
 *   escalate   — notify the principal / next level of accountability chain
 *   remediate  — take corrective action to address the violation
 *   penalise   — apply a specified sanction
 *   terminate  — terminate the community / delegation / session
 */
ViolationResponseDecl:
    'violation_response' name=ID '{'
        'on_violation_of'  ':' violated_burden=[DeonticTokenDecl]
        'obligates'        ':' responding_actor=[EnterpriseObjectDecl]
        'response_kind'    ':' response_kind=ViolationResponseKind
        ('creates_burden'  ':' creates_burden=[DeonticTokenDecl])?
        ('escalate_to'     ':' escalate_to=[EnterpriseObjectDecl])?
        ('description'     ':' description=STRING)?
    '}'
;

ViolationResponseKind:
    'escalate' | 'remediate' | 'penalise' | 'terminate'
;
```

**Example usage (consent scenario):**

```
burden consentViolationRemedyBurden {
    state: active
    discharge_mode: strict
    priority: critical
    for_action: "suspend_session_and_notify"
}

violation_response ConsentViolationResponse {
    on_violation_of: seekConsentObligation
    obligates:       GPPracticeParty
    response_kind:   escalate
    creates_burden:  consentViolationRemedyBurden
    escalate_to:     GPPracticeParty
    description:     "§7.8.6: GP practice notified; session suspended pending consent"
}
```

**Validator rule required:**

V-NEW-15: `on_violation_of` must reference a `burden` token (not a
`permit` or `embargo`) — violations in the obligation-discharge sense
apply only to burdens. Trace: §6.4.3, §6.3.8.

V-NEW-16: If `response_kind` is `escalate`, `escalate_to` must be
present and must be a `party` (not an `agent`). Trace: §7.10.1 — the
ultimate accountable party is always a party.

**Impact on Step 1 mapping table:**

Add to Group I (Accountability Speech Acts):

| Class | `ViolationResponse` |
|---|---|
| `name` | `str` |
| `violated_burden` | `DeonticToken` (Ref) |
| `responding_actor` | `EnterpriseObject` (Ref) |
| `response_kind` | `ViolationResponseKind` (Enum) |
| `creates_burden` | `Optional[DeonticToken]` (Ref) |
| `escalate_to` | `Optional[EnterpriseObject]` (Ref) |
| `description` | `Optional[str]` |

Add to enum table: `ViolationResponseKind`: `escalate, remediate, penalise, terminate`

**Status:** CONFIRMED

---

## DOC-03 — Clarify Community Role (§6.3.5) vs Action-Role participants (§6.3.2–6.3.4); `for_action` informational note

**Location:** `Role` rule (§7.8.2–7.8.3 section); `ActorRef`, `ArtefactRef`, `ResourceRef` definitions (§7.8.4 section); `DeonticToken.for_action` field.

**Issue:**
The word "role" is used in two distinct senses in ISO/IEC 15414:2015:

| Sense | Standard reference | Grammar construct |
|---|---|---|
| Community role | §6.3.5, §6.2 — structural position in a community | `Role` rule inside `Community` |
| Action participation kind | §6.3.2–6.3.4 — actor/artefact/resource for one action | `ActorRef`, `ArtefactRef`, `ResourceRef` in `ActionBodyItem` |

A community role is durable — it persists for the lifetime of the community and carries obligations, permits, and policy references.  Action participation kinds classify how objects relate to a single action execution.  A DSL user or maintainer may conflate the two because both use the word "role" informally.

Additionally, `DeonticToken.for_action` is a plain `STRING` field — it names an action for human readability but cannot be machine-checked against declared `Action` names (see AM-01 for the proposed typed upgrade).

**Changes applied:**
1. Added a DOC-03 comment block above the `Role:` rule (§7.8.2–7.8.3 section) explaining the community-role vs action-role distinction.
2. Added a DOC-03 comment before `ActorRef` / `ArtefactRef` / `ResourceRef` (§7.8.4 section) clarifying they are action participation kinds (§6.3.2–6.3.4), not community roles.
3. Added an inline DOC-03 comment on `for_action` in `DeonticToken` noting it is informational only and referencing AM-01.

**Classification:** Documentation only — no grammar or validator change.

**Standard reference:** §6.2, §6.3.2–6.3.5, §7.8.4

**Status:** CONFIRMED

---

## AM-18 — Strip `Decl` suffix from all grammar rule names; align with domain class names

**Location:** `grammar/v2/el_grammar.tx` — all rule definitions and cross-references.
Also: `toolchain/el_parser.py` — `GRAMMAR_PATH` fix and `classes=` registration.

**Motivation:**
textX matches custom classes to grammar rules by `cls.__name__`. The domain
classes in `el_domain.py` were written with clean names (`Community`,
`DeonticToken`, `Commitment`, etc.) while the grammar rules carried a `Decl`
suffix (`CommunityDecl`, `DeonticTokenDecl`, `CommitmentDecl`, etc.). This
mismatch meant all 37 affected classes would be silently ignored by textX —
only the 28 rules whose names already matched their domain class would receive
typed instances. The `classes=` parameter would be effectively dead weight for
more than half the class list.

**Resolution:** Grammar wins (invariant §10.1). Strip the `Decl` suffix from
every grammar rule name where the corresponding domain class does not carry
the suffix. The `.el` surface syntax is unaffected — keywords (`community`,
`delegation`, `burden`, etc.) drive parsing, not rule names. Cross-references
(`[OldRule]`) are updated throughout.

**Note — AM-13 interaction:** AM-13 (tentative) proposed renaming `LifecycleDecl`
to `CommunityLifecycleDecl`. AM-18 supersedes that proposal; the rule is
renamed to `Lifecycle` (matching the domain class) instead.

**Note — `PreconditionDecl` exception:** `PreconditionDecl` is NOT renamed.
Its domain class is also `PreconditionDecl` — the names already match.
Renaming the grammar rule would create a new mismatch.

**Rule renames applied (36 total):**

| Old grammar rule | New grammar rule | Domain class |
|---|---|---|
| `EnterpriseObjectDecl` | `EnterpriseObject` | `EnterpriseObject` |
| `DelegatedFromDecl` | `DelegatedFrom` | `DelegatedFrom` |
| `PrincipalOfDecl` | `PrincipalOf` | `PrincipalOf` |
| `DeonticTokenDecl` | `DeonticToken` | `DeonticToken` |
| `TokenGroupDecl` | `TokenGroup` | `TokenGroup` |
| `PolicyDecl` | `Policy` | `Policy` |
| `SettingBehaviourDecl` | `SettingBehaviour` | `SettingBehaviour` |
| `EnforcementDecl` | `Enforcement` | `Enforcement` |
| `CommunityDecl` | `Community` | `Community` |
| `ObjectiveDecl` | `Objective` | `Objective` |
| `SubObjectiveDecl` | `SubObjective` | `SubObjective` |
| `ContractDecl` | `Contract` | `Contract` |
| `InvariantDecl` | `Invariant` | `Invariant` |
| `AssignmentPolicyDecl` | `AssignmentPolicy` | `AssignmentPolicy` |
| `RoleDecl` | `Role` | `Role` |
| `ActionDecl` | `Action` | `Action` |
| `DeonticReqDecl` | `DeonticRequirement` | `DeonticRequirement` |
| `DeonticEffectDecl` | `DeonticEffect` | `DeonticEffect` |
| `ConditionalActionDecl` | `ConditionalAction` | `ConditionalAction` |
| `ProcessDecl` | `Process` | `Process` |
| `StepDecl` | `Step` | `Step` |
| `LifecycleDecl` | `Lifecycle` | `Lifecycle` |
| `EstablishingDecl` | `Establishing` | `Establishing` |
| `ChangesDecl` | `Changes` | `Changes` |
| `TerminatingDecl` | `Terminating` | `Terminating` |
| `DomainDecl` | `Domain` | `Domain` |
| `FederationDecl` | `Federation` | `Federation` |
| `ConflictResolutionDecl` | `ConflictResolution` | `ConflictResolution` |
| `CommitmentDecl` | `Commitment` | `Commitment` |
| `DelegationDecl` | `Delegation` | `Delegation` |
| `AuthorizationDecl` | `Authorization` | `Authorization` |
| `PrescriptionDecl` | `Prescription` | `Prescription` |
| `DeclarationDecl` | `Declaration` | `Declaration` |
| `EvaluationDecl` | `Evaluation` | `Evaluation` |
| `ViolationResponseDecl` | `ViolationResponse` | `ViolationResponse` |
| `CorrespondenceDecl` | `Correspondence` | `Correspondence` |

**Cross-references updated** (`[OldName]` → `[NewName]` in every attribute):
`[EnterpriseObject]`, `[DeonticToken]`, `[TokenGroup]`, `[Policy]`,
`[Community]`, `[SubObjective]`, `[Role]`, `[Step]`.

**Rule-reference sites updated** (alternation and composition rules):
`SpecElement`, `ObjectBody`, `Policy`, `Community`, `Objective`, `Contract`,
`CommunityInteraction`, `FedBodyItem`, `RoleBodyItem`, `ActionBodyItem`,
`CondActionBodyItem`, `StepBodyItem`, `Process`, `Lifecycle`.

**`el_parser.py` changes (Bug 1 + Bug 2, applied in same commit):**
- Bug 1 — wrong path: `GRAMMAR_PATH = _HERE / "el_grammar.tx"` →
  `GRAMMAR_PATH = _HERE.parent / "grammar" / "v2" / "el_grammar.tx"`
  (`_HERE` is `toolchain/`; the grammar lives in `grammar/v2/`).
- Bug 2 — no registration: `metamodel_from_file(str(GRAMMAR_PATH))` →
  `metamodel_from_file(str(GRAMMAR_PATH), classes=DOMAIN_CLASSES)` with
  `from el_domain import DOMAIN_CLASSES` import added.

**Standard reference:** §6–§7, §11 (rule names are implementation artefacts,
not standard terms; all standard mappings are preserved).

**Status:** CONFIRMED

---

## AM-21 — Dissolve `Contract` sub-block; promote contents to community body

**Standard references:** ODP Part 2 §11.2.1, ISO 15414 §7.3, §7.3.1, §7.7

**Rationale:**
A Community IS a contract — it is the governance specification that constitutes the contractual agreement. Having a `contract {}` sub-block inside a community creates a contract-within-a-contract, which is a category error. V1 correctly used `contract?='contract'` as an optional qualifier keyword on the community declaration.

**Grammar changes:**
- Removed the `Contract` rule entirely.
- Added optional `(contract?='contract')?` qualifier before the `community` keyword in the `Community` rule.
- Promoted `(invariants+=Invariant)*`, `(assignment_policies+=AssignmentPolicy)*`, and `(join_leave_effects+=JoinLeaveEffect)*` to direct body items of `Community`.
- Removed reference to `Contract` from grammar file header comment (§7.3 line).

**el_domain.py changes:**
- Removed `Contract` dataclass.
- Updated `Community`: replaced `contract: Optional[Contract]` with `contract: bool = False`; added `invariants`, `assignment_policies`, `join_leave_effects` as direct fields.
- Removed `Contract` from `DOMAIN_CLASSES`.

**Scenario changes:**
- `scenarios/consent/consent_scenario.el`: removed `contract { ... }` wrapper; promoted invariants and assignment_policy one level up.
- `scenarios/fhir/generated_governance.el`: same.
- `scenarios/ecommerce/ecommerce_scenario.el`: no `contract {}` block present; no change needed.

**Status:** CONFIRMED

---

## AM-22 — Add `EventDecl` scoped to community; event-driven token lifecycle

**Standard references:** ODP Part 2 §8.4, ISO 15414 §3.1

**Rationale:**
Events are explicitly imported into ISO 15414 §3.1 from ODP Part 2, making them normatively in scope. V2 omitted events entirely — a gap relative to both standards. Events are named facts, scoped to a community. Token lifecycle: `triggered_by` activates a token; `discharged_by` discharges a burden.

**Grammar changes:**
- Added `(events+=EventDecl)*` to `Community` body (after `objective`).
- Added new `EventDecl` rule (ODP Part 2 §8.4) in the Community section.
- Added `('triggered_by' ':' triggered_by=[EventDecl])?` and `('discharged_by' ':' discharged_by=[EventDecl])?` to `DeonticToken`, after `deadline`.
- Added `EmitsDecl` as a new `ActionBodyItem` alternative.
- Added new `EmitsDecl` rule: `'emits' ':' event=[EventDecl]`.

**Note on cross-reference scope:** `[EventDecl]` in top-level `DeonticToken` declarations crosses the community boundary. textX global resolution will attempt to resolve across the whole spec. If this causes issues, a scope provider will be added in a follow-up amendment.

**el_domain.py changes:**
- Added `EventDecl` dataclass (Group E).
- Added `EmitsDecl` dataclass (Group F).
- Added `triggered_by: Optional[object]` and `discharged_by: Optional[object]` to `DeonticToken`.
- Added `emits: Optional[object]` to `Action` (populated by object processor P4).
- Added `events: List` to `Community`.
- Added `EventDecl` and `EmitsDecl` to `DOMAIN_CLASSES`.

**el_parser.py changes (object processors):**
- P4 (`process_action`): added `EmitsDecl` branch — extracts `item.event` into `action.emits`.
- P1 (`_inject_token_defaults`): documents `triggered_by`/`discharged_by` default to `None`.

**el_engine.py changes:**
- Added `_find_spec_tokens_for_event(spec, event_name, attr)` helper.
- Step 3: added event-based discharge — burdens whose `discharged_by` matches `grammar_action.emits` are added to `dischargeable`.
- Step 7c (new): event-triggered activation — tokens whose `triggered_by` matches emitted event are transitioned to `active`.

**Status:** CONFIRMED

---

## AM-23 — Restore V1 typed policy values; add typed `PolicyEnvelope`

**Standard references:** ISO 15414 Figure A.4, ODP Part 2 §11.2.1

**Rationale:**
Figure A.4 shows `Policy → PolicyEnvelope → PolicyValue` with `PolicyValue` as a typed value. V2 collapsed policy values to plain `STRING` — losing type safety entirely. V1 implemented typed `PolicyValue` correctly.

**Grammar changes:**
- Replaced the `Policy` rule: added `':' policy_type=PolicyType` after the name; replaced `envelope: STRING` and `default_value: STRING` with `initial_value: PolicyValue` and optional `(envelope=PolicyEnvelope)?`; made `rules+=PolicyRule` optional (`*`).
- Added new rules: `PolicyType` (`integer | number | string | boolean | duration | ID`), `PolicyValue` (ordered alternatives: `Duration | NumberInterval | FLOAT | INT | STRING | BOOL | ID`), `Duration` (`value=INT unit=DurationUnit`), `DurationUnit` (all time units), `NumberInterval` (`lower=INT '..' upper=INT` — renamed from `from/to` to avoid Python keyword conflict), `PolicyEnvelope` (`'envelope' '{' envelope_rules+=EnvelopeRule+ '}'`), `EnvelopeRule` (`kind=EnvelopeRuleKind 'of' '[' values+=PolicyValue[','] ']'`), `EnvelopeRuleKind` (`'one' | 'set' | 'list'`).

**Note on `values+=PolicyValue[',']`:** This is a comma-separated list of inline rule matches, not a `[Rule]` cross-reference list — it does not trigger the arpeggio bug documented in §5.3.

**el_domain.py changes:**
- Added `DurationUnit` and `EnvelopeRuleKind` enums.
- Added `Duration`, `NumberInterval`, `EnvelopeRule`, `PolicyEnvelope` dataclasses (Group D).
- Updated `Policy`: added `policy_type: str`; replaced `envelope: str` and `default_value` with `initial_value: Optional[object]` and `envelope: Optional[PolicyEnvelope]`.
- Added `Duration`, `NumberInterval`, `EnvelopeRule`, `PolicyEnvelope` to `DOMAIN_CLASSES`.

**Status:** CONFIRMED

---

## AM-24 — Inline token shorthand on roles

**Standard references:** ISO 15414 §6.4, §7.8.2

**Rationale:**
For simple scenarios where a token applies to exactly one role and is not shared or delegated, requiring a top-level declaration creates unnecessary non-locality. V1 allowed inline token declarations on roles. V2 now supports both top-level (for shared/delegated tokens) and inline (for locally-scoped tokens).

**Grammar changes:**
- Added `InlineToken` as an alternative in `RoleBodyItem` (after `HoldsToken`).
- Added new `InlineToken` rule with the same fields as `DeonticToken` (minus the conditional-action fields `requires_permit_for`, `inhibited_by_embargo`, `favoured_by_burden`). Includes `triggered_by` and `discharged_by` from AM-22.
- `InlineToken` is NOT added to `SpecElement` — it is only reachable via `RoleBodyItem`.

**Validator rule required:**
V-NEW-18: An `InlineToken` may not be referenced by name from a `DelegationDecl`, `CommitmentDecl`, or `AuthorizationDecl`. It is local to its role. Trace: §6.4, §7.10.

**el_domain.py changes:**
- Added `InlineToken` dataclass (Group F, same fields as `DeonticToken` minus conditional-action fields).
- Added `InlineToken` to `DOMAIN_CLASSES`.

**el_parser.py changes:**
- P3 (`process_role`): added `InlineToken` branch — appends the `InlineToken` instance directly to `role.holds_tokens` (it is the token itself, not a wrapper around a reference).
- Added `process_inline_token` (P1b): applies same `discharge_mode`/`priority` defaults as P1; registered for `'InlineToken'`.

**Status:** CONFIRMED

---

## Validator fixes applied 2026-06-14 — consequences of AM-18, AM-21, and P2

**Location:** `toolchain/el_validator.py`

Three silent bugs made V-01–V-15 effective no-ops at runtime. All three
stem from the validator not tracking grammar/parser changes.

**Bug 1 — AM-18 class name mismatch (all `_collect` calls):**
Every `_collect(model, "XxxDecl")` call used the pre-AM-18 grammar rule
names. After AM-18 stripped the `Decl` suffix from all rule names and
the custom classes were registered, `type(obj).__name__` returns the new
name (`"Community"`, `"EnterpriseObject"`, etc.). All eight affected
`_collect` calls were updated:

| Old string | New string |
|---|---|
| `"ObjectDecl"` | `"EnterpriseObject"` |
| `"DeonticTokenDecl"` | `"DeonticToken"` |
| `"CommunityDecl"` | `"Community"` |
| `"PolicyDecl"` | `"Policy"` |
| `"CommitmentDecl"` | `"Commitment"` |
| `"DelegationDecl"` | `"Delegation"` |
| `"FederationDecl"` | `"Federation"` |
| `"PrescriptionDecl"` | `"Prescription"` |

**Bug 2 — AM-21 contract dissolution (V-05):**
V-05 accessed `c.contract.assignment_policies` treating `contract` as a
sub-object. AM-21 dissolved the `Contract` sub-block: `contract` is now
a `bool` flag and `assignment_policies` is a direct field on `Community`.
Fixed: iterate `c.assignment_policies` directly, removing the `contract`
guard.

**Bug 3 — P2 body dissolution (V-09):**
V-09 guarded with `if not body: continue`. P2 (`process_enterprise_object`)
dissolves `ObjectBody` into the parent `EnterpriseObject` and sets
`obj.body = None`. The guard therefore skipped every object. Fixed:
iterate `obj.holds_tokens` directly (a `List[DeonticToken]` populated by P2).

**Status:** CONFIRMED

---

## V-01 extended to Federation; V-12 extended to Domain — consequence of AM-25

**Location:** `toolchain/el_validator.py`

**V-01 for Federation:**
AM-25 added a mandatory `objective=Objective` to the `Federation` grammar
rule, making federation a fully-fledged community type per §7.7.
V-01 now runs an independent loop over `Federation` elements in addition
to the existing `Community` loop. The two loops are kept separate because
Federation has no roles, processes, or assignment policies — per-community
rules V-02–V-06 and V-14 must not run against Federation instances.

**V-12 Domain inclusion:**
AM-25 made `Domain` inherit `Community` in Python so that Domain instances
satisfy `[Community]` cross-references in `MemberRef`. The `all_communities`
index used by V-12 previously contained only `Community` instances; Domain
members of a federation were therefore falsely flagged as undeclared.
Fixed: `all_communities` now includes all elements whose `type().__name__`
is `"Community"` or `"Domain"`.

**Why Domain does NOT receive V-01:**
The `Domain` grammar rule has no `objective=Objective` field. A Domain
instance's `.objective` attribute is `None` at all times — it exists only
because `Domain` inherits the `Community` dataclass, which declares
`objective: Optional[Objective] = None`. Applying V-01 to Domain would
produce a false error on every domain in every specification. Adding an
objective to the Domain grammar rule is a separate future amendment (see
§7.5.1 — "An enterprise specification should include an objective for each
community"). Until that amendment is made, V-01 is scoped to Community and
Federation only.

**Standard reference:** §7.5, §7.5.1, §7.5.2, §7.7

**Status:** CONFIRMED

## AM-25 — Add FavouredByItem to ActionBodyItem

**Status:** Implemented
**Date:** 2026-06-25
**File:** grammar/v2/el_grammar.tx

**Problem:** `favoured_by_burden` declared directly in an `Action` body was
parsed as a `DeonticRequirement` (generic keyword match) rather than as a
`FavouredByItem`. `FavouredByItem` only appeared in `CondActionBodyItem`
(ConditionalAction body), not in `ActionBodyItem` (plain Action body).

**Fix:** Add `FavouredByItem` to `ActionBodyItem` alternation, before
`DeonticRequirement` (ordered choice — must precede or DeonticRequirement
consumes the keyword first).

**Companion changes:**
- `el_domain.py`: `Action.favoured_by: List` field added (commit 604e0b0)
- `el_parser.py`: P4 `process_action()` FavouredByItem handler added (commit 0157223)
- `el_engine.py` + `el_kripke.py`: `_find_action_for_burden()` checks
  `action.favoured_by` directly before `conditional_actions` (commit 0157223)

---

## AM-29 — `SatisfactionCondition` extended to accept direct `DeonticToken` references

**Standard references:** ISO 15414 §6.2, §7.7, §7.5.1

**Rationale:**
The existing `SatisfactionCondition` rule (AM-27) required a `TokenGroup`
cross-reference as its sole argument.  This forced scenario authors to declare
a named `token_group` wrapper even when the set of tokens was obvious from
the community context.  Multi-role, multi-burden objectives could not express
their satisfaction condition directly.

The AM-27 design used a typed cross-reference `[TokenGroup]` which is
expressive but rigid.  A comma-separated inline list of `DeonticToken` names
is equally expressive and more ergonomic for two-to-three token conditions
that don't need a reusable name.

**Grammar changes (`grammar/v2/el_grammar.tx`):**
```
// Before (AM-27):
SatisfactionCondition:
    operator=SatisfactionOp '(' group=[TokenGroup] ')'
;

// After (AM-29):
SatisfactionCondition:
    operator=SatisfactionOp '('
        raw_args+=SatisfactionArg[',']
    ')'
;

SatisfactionArg:
    name=ID
;
```

The alternation `(group=[TokenGroup] | members+=[DeonticToken][','])` was
considered but rejected: arpeggio does not backtrack after consuming an ID
as a cross-reference, making ordered alternation on two cross-reference
rules unreliable (see CLAUDE.md §5.3, Key Invariant #4).  The `SatisfactionArg`
wrapper uses a plain `name=ID` attribute; resolution of which form is in use
(TokenGroup vs inline DeonticToken list) happens in Python code at model
analysis time.

**Resolution rule (Python code):**
- If `raw_args` contains exactly one name that matches a declared `TokenGroup`
  element: AM-27 form — expand via `_build_group_index()`.
- Otherwise: AM-29 inline form — each arg name is treated as a `DeonticToken` name.

**Usage in `.el` files (both forms remain valid):**
```
// AM-27 form (unchanged):
token_group ConsentGroup {
  member: seekConsentObligation
  member: informPatientObligation
}
community ConsentCommunity {
  objective: "Obtain patient consent"
    satisfaction: all_discharged(ConsentGroup)
}

// AM-29 inline form (new):
community ReferralCommunity {
  objective: "Complete referral episode"
    satisfaction: all_discharged(referralBurden, acknowledgementBurden)
}
```

**Domain class changes (`toolchain/el_domain.py`):**
- Removed `group: Optional[object]` and `members: List` from `SatisfactionCondition`.
- Added `raw_args: List` to `SatisfactionCondition` (→ `List[SatisfactionArg]`).
- Added new `SatisfactionArg` dataclass with `name: str`.
- Added `SatisfactionArg` to `DOMAIN_CLASSES`.

**Kripke verifier changes (`toolchain/el_kripke.py`):**
- Added `_resolve_sat_member_ids(sat, group_index)` helper: applies the
  resolution rule above; returns `[member_token_id, ...]`.
- Rewrote `_build_satisfaction_conditions()` to use `_resolve_sat_member_ids()`.
- Rewrote `_build_any_discharged_groups()` to use `raw_args` directly; for
  AM-29 inline `any_discharged` conditions the community name is used as the
  index key (no named group exists).

**Validator changes (`toolchain/el_validator.py`):**
- Added `_validate_satisfaction_singleton()` implementing V-16b:
  warns (`[W-16b]`) when a `SatisfactionCondition` has exactly one effective
  member (either a TokenGroup with one token, or a single inline arg).
  A singleton condition has no collective semantics and may indicate a
  modelling error.

**Status:** CONFIRMED

---

## AM-30 (2026-07-02) — Deadline and action coverage verified

**Status:** CONFIRMED — no grammar changes required

**Triggered by:** LLM-to-DSL mapping exercise, 2 July 2026

**Finding:** Mapping exercise against gp_referral_scenario.el confirmed
that the scenario already contains:
- deadline fields on referralResponseBurden ("5 working days from
  referral receipt") and assessmentSchedulingBurden ("14 days from
  referral receipt")
- scheduleAssessment action covering specialist response obligation
- authorization patientDataAuthorization covering patient data access
  empowerment (speech act level)

**Note:** Mapping exercise was initially conducted against an earlier
draft (gp_referral.el) that does not match the current repo version
(gp_referral_scenario.el). All gaps identified in the earlier draft
are already addressed in the current scenario file.

**Files changed:** docs/el_grammar_amendments.md (this entry only)

---

## AM-31 (2026-07-02) — AuthorizationDecl: to_role, on_revocation, normative_basis

**Status:** CONFIRMED

**Triggered by:** `docs/AM31_AuthorizationDecl_design_note.md` (drafted
2026-07-02) — LLM-to-DSL mapping exercise identified that
`AuthorizationDecl` parsed only as a generic keyword construct with no
typed field validation and no revocation semantics.

**Grammar changes (`grammar/v2/el_grammar.tx`, `Authorization` rule):**
- `to_agent` changed from required to optional.
- Added `('to_role' ':' authorized_role=ID)?` as an alternative to
  `to_agent`. Mutual exclusion (exactly one of the two) is enforced by
  the validator (AM-31-V3), not the grammar — both are grammar-optional.
- Added `('on_revocation' ':' 'activate' on_revocation_embargo=ID)?`.
- Added `('normative_basis' ':' normative_basis=[NormativePolicy])?`
  (note: the design note's draft sketch named this type
  `NormativePolicyDecl`; the actual grammar rule is `NormativePolicy` —
  corrected during implementation).
- `authorized_role` and `on_revocation_embargo` are plain `ID` fields
  (known design smell per §5.4), not typed cross-references — roles are
  nested inside community `Role` bodies and are not independently
  addressable at the top level, and validators resolve `on_revocation_embargo`
  by scanning declared `DeonticToken` names with `kind == "embargo"`.

**Domain class changes (`toolchain/el_domain.py`, `Authorization`):**
- Added `authorized_role: Optional[str]`, `on_revocation_embargo:
  Optional[str]`, `normative_basis: Optional[object]` fields, matching
  the grammar exactly (custom-classes architecture, §6.1).

**Validator changes (`toolchain/el_validator.py`):** new
`_validate_authorization()`, called for every top-level `Authorization`:
- **AM-31-V1** — `authority` must be a declared object of kind `party`
  (§6.6.4); agents cannot grant authorizations.
- **AM-31-V2** — `revocable: true` requires a non-empty
  `on_revocation_embargo`.
- **AM-31-V3** — exactly one of `to_agent` / `to_role` must be present
  (not both, not neither).
- **AM-31-V4** — `grants_permit` must reference a `DeonticToken` with
  `kind == "permit"`.
- **AM-31-V5** — `on_revocation_embargo`, if set, must resolve to a
  declared `DeonticToken` with `kind == "embargo"`.

Note on numbering: the design note's draft (§5) proposed V3 = "community-
scoped authorization permit scope" and V4 = "no active embargo on
authorization grant" as additional rules, with the to_role/to_agent
exclusivity check numbered V5. The rules actually implemented (per
direct implementation instructions, 2026-07-02) renumber
to_role/to_agent exclusivity as V3, and add permit-kind/embargo-kind
resolution checks as V4/V5 instead. The design note's original V3
(community-scoped permit scope) and V4 (no-active-embargo warning) are
**not yet implemented** — deferred, no AM number assigned yet.

**Runtime changes (Layer 3):** `el_domain.py` has no runtime state or
ledger machinery (it is the static, parse-time domain model), so
revocation processing was implemented in the actual runtime layer
instead:
- `toolchain/el_engine.py`: new `revoke_authorization(state, spec,
  authorization_name)` stateless transition — supersedes the granted
  permit `TokenInstance`(s), activates the named embargo (transitioning
  it if already granted, else instantiating and granting it fresh to
  the permit's former holder), and returns a `TransitionRecord`.
  `TokenInstance.state` vocabulary extended with a new `'superseded'`
  value (previously `'active'|'pending'|'discharged'|'violated'`).
- `toolchain/el_runtime.py`: new `Runtime.revoke_authorization()` method,
  mirroring the existing `advance()` pattern — mutates `self._state` and
  appends the `TransitionRecord` to `self._ledger`.

**Scenario changes (`scenarios/gp_referral/gp_referral_scenario.el`):**
- Added `embargo patientRecordAccessEmbargo` (state: pending, same
  `for_action` as `patientRecordAccessPermit`).
- Added `on_revocation: activate patientRecordAccessEmbargo` to
  `patientDataAuthorization`, which was `revocable: true` with no
  revocation consequence (would otherwise now fail AM-31-V2).

**Known gap — resolved 2026-07-03 (see AM-31c below).**

**Files changed:** `grammar/v2/el_grammar.tx`, `toolchain/el_domain.py`,
`toolchain/el_validator.py`, `toolchain/el_engine.py`,
`toolchain/el_runtime.py`, `scenarios/gp_referral/gp_referral_scenario.el`,
`docs/el_grammar_amendments.md` (this entry).

---

## AM-31b (2026-07-02) — Split patientRecordAccessPermit into role-based and authorization-based permits

**Status:** CONFIRMED

**Triggered by:** AM-31 design note §4.0 (to_role vs to_agent), and follow-up
review of `patientDataAuthorization`'s consent authority — `patientRecordAccessPermit`
was transferred via two distinct mechanisms (role-based `on_join`/`on_leave`, and
agent-targeted `AuthorizationDecl`) under a single permit name, which the AM-31
entry above flagged as an architectural ambiguity to be resolved separately.

**Consent authority change:** `patientDataAuthorization.authority` changed from
`GPPracticeParty` to `PatientParty` (new `party` declaration). Reflects that
patient consent, not GP practice authorization, is the correct empowerment
basis for AI agent access to clinical records under `MyHealthRecordsAct`.

**Permit split (`scenarios/gp_referral/gp_referral_scenario.el`):**
`patientRecordAccessPermit` replaced with two permits, sharing the same
`for_action` (`"access_patient_clinical_records"`) but distinct grant mechanisms:
- `patientRecordAccessPermitByRole` — transferred via `on_join`/`on_leave
  specialistRole`; tracks role occupancy, held by `SpecialistClinician`.
- `patientRecordAccessPermitByAuthorization` — granted via
  `patientDataAuthorization` (`AuthorizationDecl`, `to_agent`); tracks the named
  grant to `SpecialistAIAgent`; separately revocable via the existing AM-31
  `on_revocation: activate patientRecordAccessEmbargo` mechanism.

**Design clarification (§4.0b, added to `AM31_AuthorizationDecl_design_note.md`):**
`AuthorizationDecl` (§6.6.4) does not, by itself, establish §6.6.9 principal/agent
accountability — that requires a `DelegationDecl` act (§6.6.6, §7.10.1).
`PatientParty` authorizing `SpecialistAIAgent` directly does not make `PatientParty`
a co-principal of it; `SpecialistClinician` remains sole principal via the existing
`agent SpecialistAIAgent { delegated_from SpecialistClinician }` declaration.
Modelling patient consent as a `DelegationDecl` instead would have incorrectly
shared that accountability with the patient.

**Naming note:** `ByRole` / `ByAuthorization` chosen over `Role`/`Agent` —
the grammar's `to_agent` keyword accepts any `EnterpriseObject`, not only
§6.6.8-agent-kind objects (no validator rule restricts it), so naming the
permits after the ODP-EL construct that grants them (`RoleDecl` transfer vs.
`AuthorizationDecl`) avoids implying a principal/delegate relationship the
grant itself doesn't establish.

**No grammar, validator, domain, or runtime changes** — AM-31b is scenario-only,
built entirely on AM-31's existing `to_agent`/`to_role` grammar and AM-31-V1
through V5 validator rules. `PatientParty` satisfies AM-31-V1 (authority must
be a declared `party`).

**Verification:** `scenarios/gp_referral/verify_gp_referral.py` — Parse OK, 0
validation errors, 7/7 PASS (Q1–Q4 Layer 4 Kripke checks unchanged from
pre-AM-31b baseline, as expected — the permit split does not touch the
burden/delegation chain those questions verify).

**Files changed:** `scenarios/gp_referral/gp_referral_scenario.el`,
`docs/AM31_AuthorizationDecl_design_note.md` (§4.0b addendum),
`docs/el_grammar_amendments.md` (this entry).

---

## AM-31c (2026-07-03) — fhir_mapper.py: link on_revocation embargo; fix stray contract{} wrapper

**Status:** CONFIRMED

**Triggered by:** AM-31's own "Known gap" note — `scenarios/fhir/generated_governance.el`'s
`ConsentAiDiagnostic001Auth` was `revocable: true` with no `on_revocation`
embargo, failing AM-31-V2. `fhir_mapper.py`'s `ELAuthorization` /
`_render_authorization()` did not emit `on_revocation`, and no mapping logic
linked the R17 deny-provision embargo to the R18 authorization.

**Fix (`toolchain/fhir_mapper.py`):**
- `ELAuthorization` gains an `on_revocation: str = ""` field; emitted by
  `_render_authorization()` as `on_revocation: activate <embargo_id>`.
- `_map_consent()` now links the most recent deny-type sub-provision embargo
  (R17) as the `on_revocation` target for the consent's authorization (R18).
  `revocable` is now only set `True` when such an embargo exists — an
  authorization can't be meaningfully revocable with no architectural
  consequence to revoke into.
- `_render_token()`: an embargo not yet triggered now renders `state: pending`
  rather than `state: active`, matching the AM-31 convention already
  established in `gp_referral_scenario.el`.

**Known limitation (not fixed, not currently exercised):** if a Consent has
more than one deny sub-provision, only the last is linked as `on_revocation`
— the grammar allows an `AuthorizationDecl` to reference exactly one embargo
(§7.10.2). A multi-embargo Consent would need either a `TokenGroup` or a
design decision on which embargo governs withdrawal. No test bundle currently
has more than one deny sub-provision per consent.

**Also fixed, unrelated to AM-31-V2:** `_render_community()` was emitting a
hardcoded `contract { ... }` wrapper around `invariant`/`assignment_policy`
body items with no basis in the grammar — `contract` is a boolean qualifier
on the community/federation declaration itself (`(contract?='contract')?`),
not a nested block. This meant `fhir_mapper.py` could not regenerate any
valid `.el` file from scratch, independent of AM-31-V2; the checked-in
`generated_governance.el` predated whoever introduced the regression.
Removed the wrapper; `invariant`/`assignment_policy` are now emitted as
direct community body items, matching the grammar.

**No grammar or validator changes** — both fixes are entirely within
`fhir_mapper.py`'s generation logic.

**Verification:** regenerated `scenarios/fhir/generated_governance.el` from
`toolchain/ai_diagnostic_bundle.json` via `fhir_mapper.py`; parsed and
validated via `el_parser.parse(..., validate=True)` — 0 errors, confirmed
locally with `/Users/zoki/miniforge3/bin/python`.

**Files changed:** `toolchain/fhir_mapper.py`,
`scenarios/fhir/generated_governance.el`,
`docs/el_grammar_amendments.md` (this entry).

---

## AM-32 (candidate, not yet implemented) — `inactive` TokenState for untriggered embargoes

**Status:** CANDIDATE — logged only, no grammar change made

**Triggered by:** AM-31 follow-up review, 2026-07-02. `patientRecordAccessEmbargo`
in `gp_referral_scenario.el` is declared before `patientDataAuthorization`
has ever been revoked — i.e. it has never been triggered. Neither
existing `TokenState` value fits cleanly: `active` would mean the
embargo is already blocking the action (wrong — nothing has been
revoked yet), and `pending` is documented elsewhere (§7.8.7, CLAUDE.md
§2) as "masked/suspended," which is obligation-flavoured language that
doesn't describe an embargo that simply hasn't fired yet.

**Current workaround:** `patientRecordAccessEmbargo` keeps
`state: pending` (the nearest of the two valid values) with an inline
comment explaining the rationale. This is safe in practice because
`el_engine.py`'s `revoke_authorization()` (AM-31) forces
`state="active"` on the embargo at activation time regardless of its
declared initial state — the declared value is only descriptive
pre-activation, never read as an activation precondition.

**Candidate change:** extend `grammar/v2/el_grammar.tx:166`'s
`TokenState` rule from `'active' | 'pending'` to
`'active' | 'pending' | 'inactive'`, restricted to embargo-kind tokens
(a burden/permit declared `inactive` would need separate semantics
review). Would require updating `toolchain/el_domain.py`'s `TokenState`
enum and any code that pattern-matches on the two-value enum.

**Next action:** none scheduled. Revisit if a second scenario needs the
same "declared but not yet triggered" embargo pattern. (AM-31b —
splitting `patientRecordAccessPermit` into
`patientRecordAccessPermitByRole`/`ByAuthorization` — implemented
2026-07-02; did not require this TokenState.)

---

## AM-33 (2026-07-06) — established_by trigger for community/federation/domain establishment; Federation and Domain gain Lifecycle support

**Status:** CONFIRMED

**Triggered by:** `docs/CONCEPTS_INDEX.md`'s "Establishing behaviour" and
"Federation" entries — `Establishing` (§7.6.1) had no structured trigger,
asymmetric with `Terminating`'s `on_objective_achieved`; and `Federation`/
`Domain` had no `Lifecycle` support at all (`FedBodyItem`/`DomainBodyItem`
never included it), despite both being community types (§7.5) that should
inherit community lifecycle per the standard. Motivated concretely by the
decision to model the referral episode as a created Federation over two
pre-existing practice communities (Annex B library Case 5 pattern).

**Mechanism chosen:** `established_by: [EventDecl]`, mirroring
`DeonticToken.triggered_by`/`discharged_by` (AM-22) and `Action.emits`.
Considered and rejected `[Action]` (unprecedented — `for_action` on tokens
is deliberately a plain string, not a cross-reference) and `[Step]`
(unprecedented — `Process`/`Step` has zero usage anywhere in any scenario
or in the runtime). `EventDecl` was chosen as the only option with a real,
implemented precedent, even though — corrected after initial drafting —
that precedent itself has zero usage in any scenario to date; it is
implemented-but-unexercised, the same status as `Process`/`Step`, not
"actively exercised" as first claimed in the concept index (corrected).

**Grammar (`grammar/v2/el_grammar.tx`):**
- `Establishing` gains `established_by: [EventDecl]` (optional), alongside
  the existing `implicit`/`description`/`commitments`.
- `FedBodyItem` gains `| Lifecycle`.
- `DomainBodyItem` gains `| Lifecycle`.

**Domain classes (`toolchain/el_domain.py`):**
- `Establishing` dataclass gains `established_by: Optional[object] = None`.
- `Federation` dataclass gains `lifecycle: Optional[object] = None`
  (`Domain` already had this field via inheritance from `Community` —
  only `Federation` needed a new field).

**Object processors (`toolchain/el_parser.py`):**
- `process_federation` (P9) gains an `elif cls == 'Lifecycle': fed.lifecycle
  = item` branch — without it, a parsed `Lifecycle` body item was silently
  dropped when `body_items` is cleared, with no error raised.
- `process_domain` (P8) gains the same branch for `domain.lifecycle`.

**Known limitation:** `established_by`'s cross-reference uses textX's
default global name-based resolution (confirmed: no custom scope provider
is registered for `EventDecl` anywhere in the toolchain) — an event name
must be unique across the entire model, not just within its declaring
community. Not currently a problem (no scenario has more than a handful
of events), but worth remembering if event-name collisions ever become
plausible across a larger federation of communities.

**Verification:**
- Existing scenario regression: `gp_referral_scenario.el` re-parsed and
  re-validated clean (0 errors) after all edits — confirms no regression
  for scenarios that don't use the new fields.
- Full pytest suite (Layers 4/5/6, 7 tests) re-run clean after all edits.
- Positive end-to-end test (throwaway, not committed): a `Federation`
  with `lifecycle { establishing { established_by: <event> } }`, referencing
  an event emitted by an action inside a pre-existing member `Community`,
  parsed and validated with 0 errors, and
  `fed.lifecycle.establishing.established_by.name` correctly resolved to
  the event's name — confirming the full chain (grammar → parse →
  validator → object processor → custom-class field → cross-reference
  resolution), not merely successful parsing.

**Not yet implemented (deferred, tracked in `docs/CONCEPTS_INDEX.md`):**
- Kripke/runtime awareness of community/federation *existence* as a
  modelled world-state dimension (`community_states`) — `established_by`
  is now expressible in the grammar, but nothing in `el_kripke.py` yet
  treats a community as not-existing before its establishing event fires.
- The unified `referral_scenario.el` itself does not yet use this
  mechanism — this AM only adds the capability.
- V-NEW-20 widening (NormativePolicy on any Community) — separate,
  still-open AM candidate, not part of this amendment.
- `Community`/`Domain`/`Federation` grammar-level syntax unification —
  consciously deferred structural refactor, not part of this amendment
  (see `docs/CONCEPTS_INDEX.md`).

**Files changed:** `grammar/v2/el_grammar.tx`, `toolchain/el_domain.py`,
`toolchain/el_parser.py`, `docs/el_grammar_amendments.md` (this entry).

---

## AM-34 (2026-07-09) — fhir_event_handler.py: R31 Consent revoke + R30 bootstrap note

**Status:** CONFIRMED

**Commit:** `8a200fa`

**Summary:** Added `toolchain/fhir_event_handler.py`, implementing R31
(FHIR `Consent.status` transition to `inactive` → authorization
revocation) and an R30 bootstrap note. Wired into `toolchain/el_api.py`
(`POST /fhir/consent-events`).

**Files changed:** `toolchain/fhir_event_handler.py` (new),
`toolchain/el_api.py`, `tests/test_fhir_event_handler.py` (new, 114 lines).

---

## AM-35 (2026-07-10) — extract_federation_from_contract(): R23+R24 Contract-based federation extraction

**Status:** CONFIRMED

**Commit:** `c2b9852`

**Summary:** Added `extract_federation_from_contract()` to
`toolchain/fhir_mapper.py` — the merged R23+R24 rule (superseding earlier
OrganizationAffiliation-/Consent.policyRule-based proposals). Maps FHIR
`Contract.signer[]`/`.term[]`/`.rule[]` to an ODP-EL `contract federation`
block plus `community_object` declarations and commented
`normative_policy` stubs. Standalone extraction function, not wired into
`el_api.py` (federation membership is standing structure, not a runtime
event).

**Files changed:** `toolchain/fhir_mapper.py`,
`tests/test_fhir_federation_mapper.py` (new, 279 lines).

---

## AM-36 (2026-07-10) — R05-R08 corrections against referral_scenario.el

**Status:** CONFIRMED

**Commit:** `c6aa5db`

**Summary:** Corrected four issues in `_map_service_request()` found while
checking R05-R08 against the reference `referral_scenario.el`:
- **R06:** resolve `Practitioner` requester to organisational
  accountability via `PractitionerRole.organization`, with a flagged
  fallback when unresolved (`_resolve_commitment_accountable_party()`).
- **R07:** split the `discharge_mode` heuristic into independent
  time-criticality (`_is_time_critical()`) and consent-related
  (`_is_consent_related()`) signals — previously consent-keyword-only.
- **R07:** resolve `for_action` via an explicit `SERVICE_REQUEST_ACTION_MAP`
  (FHIR coding → DSL action identifier) instead of sanitized display
  text; unresolved codes are flagged rather than guessed.
- **R08:** dropped the `occurrenceDateTime` → deadline mapping
  (a scheduling field, not an SLA deadline) — left blank pending an
  extension-based approach.

**Files changed:** `toolchain/fhir_mapper.py`,
`tests/test_fhir_mapper_referral.py` (new, 8 tests),
`tests/fixtures/referral_service_request_bundle.json` (new),
`scenarios/fhir/generated_governance.el` (regenerated).

**Verification:** 43/43 tests passing.

---

## AM-37 (2026-07-13) — R26-R29 (partial): Encounter-based episode grounding

**Status:** CONFIRMED

**Commit:** `f8543ab`

**Summary:** Added `EncounterContext` dataclass and
`extract_encounter_context()` to `toolchain/fhir_mapper.py`, mapping FHIR
`Encounter.participant[type=ATND]` → `referring_practitioner`,
`Encounter.serviceProvider` → `gp_practice`, and
`Encounter.episodeOfCare[0]` → `episode_reference` (traceability only).
Reuses `_ref_id()` and the `by_ref` reference-resolution dict pattern
from `_resolve_commitment_accountable_party()` /
`extract_federation_from_contract()` — no new resolution helper
introduced. Errors (missing `Encounter`, no `ATND` participant,
unresolvable `serviceProvider`) raise `ValueError`, matching
`extract_federation_from_contract()`'s philosophy that a mis-grounded
episode is a governance-integrity gap, not a recoverable detail.

`_build_referral_runtime()` in `toolchain/el_api.py` made optionally
parametrizable: `encounter_context: Optional[EncounterContext] = None`.
When supplied, only the GP side is substituted — `GPClinician` and
`GPPractice` (both role enrollments plus the two GP-held burdens,
`referralInitiationBurden`/`clinicalHandoverBurden`) are replaced by
`encounter_context.referring_practitioner`/`.gp_practice`.
`SpecialistClinician`, `SpecialistAIAgent`, `SpecialistPractice`, and
`Patient` are untouched in all cases. Default behavior (`encounter_context`
omitted or `None`) is unchanged — the module-level
`_runtime = _build_referral_runtime()` call at startup is unaffected.

**Not covered by this entry (remains open):** status-driven token-state
initialisation from `Encounter.status` (e.g. using `finished` vs.
`in-progress` to seed initial burden/permit token states) is NOT part of
this amendment. `EncounterContext` currently only grounds actor identity
(who), not token lifecycle state (what state things start in).

**Files changed:** `toolchain/fhir_mapper.py`, `toolchain/el_api.py`,
`tests/test_scenario_builders.py`.

**Verification:** 45/45 tests passing (43 pre-existing + 2 new:
`test_referral_runtime_default_matches_hardcoded_gp_actors`,
`test_referral_runtime_encounter_context_grounds_gp_side_only`).

---

## AM-39 (2026-07-15) — Encounter.status=finished triggers referralInitiationBurden activation via Runtime.fire_event() (R26-R29 probe)

**Standard references:** ODP Part 2 §8.4 (events), ISO 15414 §6.4/§7.8
(DeonticToken lifecycle).

**Rationale:**
`referralInitiationBurden` should not be treated as in force until the
originating clinical Encounter concludes. Rather than a Python-side
conditional, this reuses the existing-but-previously-untested AM-22
`triggered_by`/`EventDecl` mechanism (Step 7c), extended with a new
direct-call path (`Runtime.fire_event()`) for externally-driven events
that have no corresponding DSL action — mirroring AM-31's
`revoke_authorization()` direct-call pattern rather than routing through
`advance()`.

**Note on prior state:** Step 7c (`el_engine.py`'s event-triggered
activation, AM-22, commit `18b243dd`, 2026-06-05) and its companion
`event_discharged` discharge path were fully implemented but had zero test
coverage anywhere in the repo before this amendment — see
`docs/CONCEPTS_INDEX.md`, "Event-triggered activation (Step 7c) —
implemented but untested" (logged separately, commit `88633a4`). That
same entry also logs an unresolved symmetry gap between this engine-level
mechanism and the Kripke layer's independent `WAITING`/P6 cascade (built 8
days apart, 2026-06-13, never cross-referenced with AM-22). This amendment
is the first thing in the repo to actually exercise Step 7c end-to-end.

**Scenario changes (`scenarios/referral/referral_scenario.el`):**
- Added `event encounterConcluded` to `GPPracticeCommunity`'s events list
  (alongside the existing `event referralSubmitted`), described as fired
  directly from Python via `Runtime.fire_event()`, not emitted by any DSL
  action.
- Added `triggered_by: encounterConcluded` to the top-level
  `referralInitiationBurden` `DeonticToken` declaration. This is the first
  real, parseable usage of `DeonticToken.triggered_by` in the repo — the
  only prior occurrences of the literal text `triggered_by` were in
  `scenarios/ecommerce/ecommerce_scenario.el`'s `violation_response`
  blocks, which use a field set (`violated_by`, `condition`,
  `violation_type`, `notifies`) that does not match the current
  `ViolationResponse` grammar rule at all (unrelated construct, and that
  file has a separate pre-existing syntax error, CLAUDE.md §4/§9).
  Confirmed by parse: the cross-community `[EventDecl]` reference resolves
  correctly (AM-22's changelog entry had flagged this as an unconfirmed
  risk — "textX global resolution will attempt to resolve across the
  whole spec... a scope provider will be added in a follow-up amendment
  [if needed]" — no scope provider was needed).

**el_engine.py changes:**
- Step 7c's inline activation logic extracted into a shared helper
  `_activate_triggered_tokens(spec, tokens, event_name)`, called both by
  `advance()` Step 7c (action-driven, via `Action.emits`) and the new
  `fire_event(state, spec, event_name, source="external")` (direct-call).
  Pure refactor of Step 7c — confirmed behavior-identical via a regression
  test (`test_step7c_activates_token_via_action_emits`) and via `git
  blame` showing every line of the pre-refactor block traced to the
  original AM-22 commit with no intervening edits.
- New `fire_event(state, spec, event_name, source="external")`: directly
  fires a named event against `state`, activating any token whose
  `triggered_by` matches it, without requiring an `Action`/`emits`.
  Mirrors `revoke_authorization()`'s direct-call pattern (AM-31): no
  calling actor exists the way `advance()` has one, so `source` documents
  the event's origin in the returned `TransitionRecord.actor_name`
  (analogous to `advance()`'s `actor_name` parameter) instead of
  attributing it to an `EnterpriseObject`. `source` defaults to
  `"external"`; this module stays domain-generic and assumes nothing
  about the calling context (no FHIR-specific strings in `el_engine.py`).
  Never raises for an unmatched event name — see `fhir_event_handler.py`
  changes below for how that's surfaced.

**el_runtime.py changes:**
- New `Runtime.fire_event(event_name, source="external")`: thin wrapper
  matching `revoke_authorization()`'s pattern exactly — imports
  `fire_event` from `el_engine.py` as `_engine_fire_event`, calls it,
  updates `self._state`, appends the `TransitionRecord` to `self._ledger`,
  returns the record.

**fhir_event_handler.py changes:**
- New `ENCOUNTER_CONCLUDED_EVENT = "encounterConcluded"` module constant
  (scenario-specific default, same pattern as the existing
  `PATIENT_DATA_AUTHORIZATION` constant).
- New `EncounterEventResult` dataclass, matching `ConsentEventResult`'s
  shape/spirit (`fhir_encounter_id`, `fhir_status`, `action_taken`,
  `message`, `fhir_provenance`, `event_name`, `transition`).
- New `handle_encounter_event(encounter, runtime, event_name=
  ENCOUNTER_CONCLUDED_EVENT)`:
  - `status == "finished"` fires the event via `Runtime.fire_event()` and
    distinguishes `action_taken="fired"` (genuine activation —
    `TransitionRecord.effects` non-empty) from `action_taken=
    "fired_no_match"` (event fired, tick advanced, ledger entry recorded,
    but no token's `triggered_by` matched — `effects` empty). This
    distinction exists because `Runtime.fire_event()` never raises on an
    unmatched event name, unlike `revoke_authorization()`; without it,
    "fired and matched nothing" would be indistinguishable from "fired and
    activated something," silently masking a mis-wired or typo'd event
    name. Both outcomes carry the real `transition`/`event_name` on the
    result.
  - `status in ("cancelled", "entered-in-error")` raises `ValueError` — no
    clinical decision occurred; a bootstrap-time integrity gap, not a
    recoverable no-op, mirroring `extract_encounter_context()`'s existing
    error philosophy (`fhir_mapper.py`, R26-R29).
  - Any other status is `action_taken="no_op"`; `fire_event()` is not
    called, and `event_name`/`transition` stay `None`.
  - Missing `'id'`/`'status'` on the input resource raises `ValueError`,
    matching `handle_consent_event()`.

**Tests (`tests/test_referral_event_triggers.py`, new file, 11 tests):**
- `_activate_triggered_tokens()` directly — matching token activates,
  unrelated token with no `triggered_by` is untouched, and an unmatched
  event name is a no-op that leaves tokens/log empty.
- `advance()` Step 7c end-to-end, via a minimal synthetic spec
  (`parse_string()`, not a fixture file) — no scenario in the repo pairs a
  real `emits` with a matching `triggered_by`, so this is the only test
  exercising a genuine `Action.emits` → token activation.
- `Runtime.fire_event()` directly, including the default `source`
  parameter and the unmatched-event no-op case.
- `handle_encounter_event()` round-trip: `status="finished"` activating a
  real `pending`-state token (not the scenario's default `active` state —
  a manually-overridden `TokenInstance`, so the transition being tested is
  real, not a same-value no-op), the `"fired_no_match"` distinction, and
  both `ValueError` paths (`cancelled`/`entered-in-error`, missing
  `id`/`status`).
- Mutation-checked: confirmed these tests fail (`ImportError: cannot
  import name 'fire_event'`) when run against `el_engine.py` reverted to
  its pre-Step-2/3 state via `git stash`; confirmed byte-identical
  restoration (`git stash pop`, diff compared hash-for-hash against the
  approved version) and 56/56 passing afterward.

**Note on scope:** this is a probe-tier implementation of item #1
(`docs/CONCEPTS_INDEX.md`, "Toolchain implementation priority
sequencing") — it wires the mechanism end-to-end for
`referralInitiationBurden` specifically, but does NOT implement the full
Encounter.status-driven token-state seeding design (a complete
status→state mapping table across all nine FHIR Encounter statuses,
deadline computation, etc.). That remains future work under item #1.

**Files changed:** `scenarios/referral/referral_scenario.el`,
`toolchain/el_engine.py`, `toolchain/el_runtime.py`,
`toolchain/fhir_event_handler.py`, `tests/test_referral_event_triggers.py`
(new), `docs/el_grammar_amendments.md` (this entry).

**Status:** CONFIRMED

---

## AM-40 (2026-07-19) — Domain controlling_object/controlled_object as roles

**Status:** PARTIALLY IMPLEMENTED (2026-07-21) — grammar, parser, and
validator support both syntaxes; `PatientDataDomain` migration and
old-syntax removal still pending. See "Implementation notes" below for
what actually landed and how it differs from the original proposal text
that follows.

**Standard reference:** §7.5.1 — "An <X>-domain community comprises an
<X>-domain of enterprise objects in the roles of controlled objects and an
enterprise object in the role of controlling object."

**Problem:** `Domain`'s `controlling_object`/`controlled_object` are
currently implemented as bare `EnterpriseObject` references, with no role
machinery at all:
```
DomainControllingObj: 'controlling_object' ':' obj=[EnterpriseObject]
DomainControlledObj:  'controlled_object' ':' obj=[EnterpriseObject]
```
This conflicts with the standard's own language quoted above — explicit
role language, not fixed object slots.

**Blast radius check (2026-07-19):** `controlling_object`/
`controlled_object` have zero references in `el_kripke.py`,
`el_engine.py`, `el_reasoner.py`, `el_validator.py`, or `el_api.py` — only
`el_parser.py`'s P8 processor and `referral_scenario.el`'s
`PatientDataDomain` use them. This is a grammar + parser + one migrated
scenario change, not a runtime rewrite.

**Proposed grammar (`grammar/v2/el_grammar.tx`), as originally drafted:**
```
DomainBodyItem:
    DomainControllingRole | DomainControlledRole | DomainRoleFiller
    | PolicyRef | NormativePolicyRef | Lifecycle
;

DomainControllingRole:
    'controlling_role' role=Role
;

DomainControlledRole:
    'controlled_role' role=Role
;

DomainRoleFiller:
    obj=[EnterpriseObject] 'fills' role=[Role]
    ('via' via=[Federation])?
;
```
**Correction — what actually landed differs in one respect:** the scope
for this session's implementation pass was explicitly dual-syntax, not a
replacement — see "Implementation notes" below. `DomainControllingRole`,
`DomainControlledRole`, and `DomainRoleFiller` are exactly as drafted
above; `DomainBodyItem` instead reads:
```
DomainBodyItem:
    DomainControllingObj | DomainControlledObj
    | DomainControllingRole | DomainControlledRole | DomainRoleFiller
    | PolicyRef | NormativePolicyRef | Lifecycle
;
```
keeping `DomainControllingObj`/`DomainControlledObj` (§ Problem, above) as
live alternatives rather than removing them.

**Design rationale:**
- Reuses the existing `Role` rule (interface?/isa/description/
  `RoleBodyItem`) rather than inventing a new role type.
- The "X fills role Y" idiom is not new — it generalizes `MemberRef`'s
  existing `('fills' fills=[Role])?` field (currently Community-fills-Role
  for federation membership) to EnterpriseObject-fills-Role for domains.
- `via=[Federation]` is the one genuinely new field: it lets a
  controlled-object filler trace back to whichever federation authorized
  it — needed for domains that aggregate fillers arriving from multiple
  distinct peer federations (the AIVendor N-peer case — see
  `docs/CONCEPTS_INDEX.md`, AIVendor entry, 2026-07-19 update).
- Considered and rejected: a labelled `filler:` keyword. Rejected in
  favour of the bare fills-statement above, to stay consistent with the
  one existing precedent (`MemberRef`) rather than introduce a second,
  differently-shaped idiom for the same underlying concept.

**Migration required (not part of this amendment):**
`referral_scenario.el`'s `PatientDataDomain` needs rewriting under this
grammar once it lands. Per a separate 2026-07-19 design decision logged in
`docs/CONCEPTS_INDEX.md` (Domain entry), `PatientDataDomain` should
actually be split into two overlapping domains
(`PatientDataAuthorshipDomain` and `PatientDataConsentDomain`) rather than
migrated as a single domain — treat that split as a follow-on
scenario-file change after AM-40's grammar lands, not part of this
amendment itself.

**Validator impact — corrected (2026-07-21):** this entry originally
claimed a rule numbered V-NEW-04 already existed, checking "at least one
`controlling_object`, at least one `controlled_object`," and needed
updating. That claim was checked against `toolchain/el_validator.py` at
implementation time and found to be **factually wrong** — no rule under
any name enforced controlling/controlled-object presence on Domain prior
to this session; `V-NEW-04` does not appear anywhere in the file. The
original text was itself part of the proposal, not a description of
current state, and should not have been read as one.

What was actually added: a new rule, `V-NEW-21` (chosen as the next
available number after the existing `V-NEW-19`/`V-NEW-20`, not reused
from the incorrect `V-NEW-04` reference), since none existed before. It
passes a Domain if EITHER at least one `controlling_object` AND at least
one `controlled_object` are declared (old syntax), OR at least one
`controlling_role` AND at least one `controlled_role` are each filled by
a `DomainRoleFiller` resolving to that role (new syntax) — either syntax
alone is sufficient. Role-filler matches are checked by object identity
(`is`) against the domain's own `controlling_roles`/`controlled_roles`,
not by name string or `==`: `role=[Role]` cross-references resolve
globally (no custom `scope_provider`, same as `MemberRef.fills`), and
these dataclasses use default value-based `__eq__`, so either a
name-string or an `in`/`==` check would risk a false positive from a
same-named role declared in a different domain. No cardinality
constraint requiring exactly one controlling-role filler was added — this
remains explicitly unresolved (see Open questions, below) and stays open
rather than silently enforced.

**Open questions, recorded not resolved:**
1. Should `controlling_role`/`controlled_role` embed the full `Role` type
   (interface/isa/description/body items) or would a lighter
   bare-name-only form suffice for current use cases? Full `Role` costs
   nothing extra grammatically; left open for the AIVendor probe to
   stress-test.
2. Controlling-role filler cardinality (one vs many) remains unresolved
   by the standard.

**Implementation notes (2026-07-21) — dual-syntax landing:**
Scope for this pass was deliberately narrow: add the new syntax alongside
the old one, touch nothing else. Specifically out of scope and untouched:
`referral_scenario.el`'s `PatientDataDomain` migration (see "Migration
required," above — still deferred), and removal of the old
`controlling_object`/`controlled_object` syntax (no removal is planned
until migration happens).

- `grammar/v2/el_grammar.tx` — `DomainBodyItem` extended (not replaced;
  see the "Correction" note above); `DomainControllingRole`,
  `DomainControlledRole`, `DomainRoleFiller` added exactly as drafted.
- `toolchain/el_domain.py` — `DomainControllingRole`, `DomainControlledRole`,
  `DomainRoleFiller` domain classes added and registered in
  `DOMAIN_CLASSES`; `Domain` gained `controlling_roles`, `controlled_roles`,
  `role_fillers` fields (populated alongside the existing
  `controlling_objects`/`controlled_objects`, not replacing them). A
  `RoleFillerRef` helper dataclass (`obj`/`role`/`via`) was also added —
  deliberately **not** registered in `DOMAIN_CLASSES`, since it has no
  corresponding grammar rule; textX's `validate_user_classes()` raises
  `TextXSemanticError` for any registered class name not used in the
  grammar, so adding it there would have broken metamodel construction
  entirely, not just been inert.
- `toolchain/el_parser.py` — P8 (`process_domain`) extended with three new
  branches populating `controlling_roles`/`controlled_roles`/`role_fillers`
  (the last as `RoleFillerRef` instances); the existing
  `DomainControllingObj`/`DomainControlledObj` branches are unchanged.
- `toolchain/el_validator.py` — new rule `V-NEW-21` added (see "Validator
  impact," above, for the correction and the rule's actual logic).
- `tests/test_am40_domain_role_syntax.py` — new file, 5 tests: new-syntax
  parsing populates the typed lists correctly; `obj`/`role` resolve by
  identity to the actual declared objects; `via=[Federation]` resolves
  correctly; a fully-filled role-based domain passes `V-NEW-21`; a domain
  with declared-but-unfilled roles fails it. Throwaway minimal fixtures,
  not the referral scenario — `PatientDataDomain` is untouched.
- Full suite: 56 pre-existing tests pass unchanged, plus these 5 new ones
  (61 total).

**Files changed:** `docs/el_grammar_amendments.md` (this entry),
`grammar/v2/el_grammar.tx`, `toolchain/el_domain.py`,
`toolchain/el_parser.py`, `toolchain/el_validator.py`,
`tests/test_am40_domain_role_syntax.py`. `scenarios/referral/
referral_scenario.el` remains untouched — migration is separate follow-on
work (see "Migration required," above).

**Status:** PARTIALLY IMPLEMENTED — grammar/parser/validator support both
syntaxes; PatientDataDomain migration and old-syntax removal still
pending.

---

## AM-41 (2026-07-22) — Widen NormativePolicy from Domain/Federation-only to any Community

**Status:** IMPLEMENTED (2026-07-22) — grammar, parser, and validator
widen `NormativePolicy` to any plain `Community`; V-NEW-20 (the rule that
previously restricted it) is retired.

**Problem:** `NormativePolicy` (AM-28) could only be referenced from
`Domain` or `Federation` body items — validator rule V-NEW-20 rejected any
`normative_policy:` reference on a plain `Community`. This restriction's
own stated justification ("domain policies bind all controlled objects,"
§7.5.1) does not survive scrutiny once Domain IS a Community (settled
2026-06-04, AM-25): §7.3.1 gives an ordinary Community's contract the same
universal-binding property over its members, and Annex B.1.5.3's
e-commerce example cites an external legal agreement directly from a
plain Community's contract, with no Domain or Federation involved. Logged
as an open AM candidate in `docs/CONCEPTS_INDEX.md`'s "NormativePolicy
scope" entry since 2026-07-06.

**Standard reference(s):** §6.5 (Policy concept); §7.3.1 (a plain
community's contract "governs... and constrains the behaviour of its
enterprise object members" — the universal-binding property this
amendment extends NormativePolicy eligibility to match); §7.5.1 ("domain
policies bind all controlled objects" — V-NEW-20's now-superseded original
justification); Annex B.1.5.3 (e-commerceCommunity's contract "refers to a
legal agreement between e.com and its customers" — a plain Community
citing an external source directly, the standard's own precedent for this
widening).

**Blast radius:** `NormativePolicyRef` (the grammar rule for a
`normative_policy:` reference line) appears in exactly three places in
`grammar/v2/el_grammar.tx`: `DomainBodyItem`, `FedBodyItem`, and now
`Community`'s own rule. No other grammar rule references it. In the
toolchain, `normative_policies` is read only by
`_validate_normative_policy_placement` (V-NEW-20, now removed) and is
otherwise inert data carried on the model — zero references in
`el_kripke.py`, `el_engine.py`, `el_reasoner.py`, or `el_api.py`. This is a
grammar + parser + validator change with no runtime/Kripke impact.

**Proposed grammar (`grammar/v2/el_grammar.tx`):** one new line added to
`Community`'s rule body, alongside its other typed lists:
```
Community:
    (contract?='contract')? 'community' name=ID
    ('isa' type_ref=[Community])?
    ('description' ':' description=STRING)?
    '{'
        objective=Objective
        (events+=EventDecl)*
        (invariants+=Invariant)*
        (assignment_policies+=AssignmentPolicy)*
        (join_leave_effects+=JoinLeaveEffect)*
        (roles+=Role)*
        (processes+=Process)*
        (policy_refs+=PolicyRef)*
        (normative_policies+=NormativePolicyRef)*   // AM-41
        (interactions+=CommunityInteraction)*
        (lifecycle=Lifecycle)?
    '}'
;
```
`NormativePolicyRef` and `NormativePolicy` themselves are unchanged —
reused as-is from AM-28.

**Design rationale:**
- Community's grammar rule types every body item directly (no
  `body_items*=CommunityBodyItem` catch-all the way Domain/Federation
  use), so `normative_policies+=NormativePolicyRef` sits alongside
  `policy_refs`, `invariants`, etc. as a plain typed list — consistent
  with the rest of the rule's style, not a new pattern.
- Because it's a direct typed attribute rather than a body-items
  catch-all, textX populates `community.normative_policies` with raw
  `NormativePolicyRef` wrapper objects, not resolved `NormativePolicy`
  instances — unlike `Domain`/`Federation`, which resolve via their P8/P9
  body-items processors. A new object processor, **P11**
  (`process_community`, registered for `'Community'`), was added purely
  to unwrap `ref.policy` for each item, so `Community.normative_policies`
  ends up holding the same kind of resolved list Domain/Federation
  already expose — one line, mirroring the existing
  `domain.normative_policies.append(item.policy)` idiom from P8.
- No double-population risk: `Domain`'s grammar rule
  (`grammar/v2/el_grammar.tx`, `Domain:`) is entirely separate from
  `Community`'s — it has its own `body_items*=DomainBodyItem` and does
  not invoke Community's grammar rule at all (Python class inheritance
  via AM-25 does not imply grammar-rule reuse). textX's
  `register_obj_processors` keys strictly by exact type name, so P11
  (`'Community'`) never fires on `Domain` instances even though `Domain`
  is a Python subclass of `Community`. `Domain.normative_policies` stays
  governed solely by P8, and `Federation.normative_policies` solely by
  P9, both unchanged by this amendment. Verified by a passing regression
  test for each (see "Files changed," below).

**Validator impact:** V-NEW-20 previously flagged any plain-`Community`
element with a non-empty `normative_policies` list. Investigated before
deciding whether to widen its condition or retire it outright: since
`NormativePolicyRef` only ever appears in three grammar locations —
`Community`, `DomainBodyItem`, `FedBodyItem` — and this amendment makes
all three legitimate, **V-NEW-20 can no longer fire on anything the
grammar allows**. There is no remaining case for it to widen into or
narrow around, so it was **removed outright** (function
`_validate_normative_policy_placement`, its dispatch call, and its header
doc-comment line all deleted) rather than kept as a no-op stub, per the
codebase's no-dead-code convention. The rule number `V-NEW-20` is retired
and will not be reused, matching how the incorrect `V-NEW-04` reference
was handled in AM-40 — a rule number, once assigned in this log, is never
recycled even after removal.

**Files changed:** `docs/el_grammar_amendments.md` (this entry),
`docs/CONCEPTS_INDEX.md` ("NormativePolicy scope" entry: table row,
Toolchain status, Open→Closed, new "Future consideration" paragraph on
episodic-level citation staleness — deliberately not built here),
`grammar/v2/el_grammar.tx` (`Community` rule), `toolchain/el_domain.py`
(`Community.normative_policies` field added), `toolchain/el_parser.py`
(`process_community` / P11 added and registered), `toolchain/el_validator.py`
(V-NEW-20 function, dispatch call, and header line removed),
`tests/test_am41_community_normative_policy.py` (new file, 5 tests: plain
Community resolves a NormativePolicy by identity; plain Community passes
validation with no V-NEW-20 error; Domain's existing normative_policy
handling (P8) is unaffected; Federation's existing normative_policy
handling (P9) is unaffected; a Community may cite more than one
NormativePolicy). Full suite: 61 pre-existing tests pass unchanged, plus
these 5 new ones (66 total).

**Status:** IMPLEMENTED — grammar/parser/validator widen NormativePolicy
to any Community; V-NEW-20 retired.

---

## AM-42 (2026-07-22) — Optional enforcement field on NormativePolicy (§7.9.4)

**Status:** IMPLEMENTED (2026-07-22) — `NormativePolicy` gains an optional
`enforcement` field, reusing Policy's own pre-existing `EnforcementMode`
vocabulary by direct reference.

**Problem:** `NormativePolicy` (docs/CONCEPTS_INDEX.md, "NormativePolicy
scope," 2026-07-19 finding) had no way to record whether the norm it cites
is policed and enforced, or unpoliced — ISO/IEC 15414 §7.9.4 ("Policy
enforcement") distinguishes policed-pessimistic (preventative — mechanisms
ensure compliance before the fact; used when trust is low and potential
damage is high) from policed-optimistic (allow the action, detect and
respond to non-compliance after the fact) from unpoliced (no enforcement
specified). This is a policy/regulatory-level property of the cited
source, distinct from `DeonticToken.discharge_mode` (a runtime/Kripke-model
property of a specific token) — the two must not be collapsed or
renamed into one another (see CONCEPTS_INDEX.md finding for the full
argument; unchanged by this amendment).

**Standard reference(s):** §7.9.4 (Policy enforcement — policed
pessimistic/optimistic, or unpoliced); §6.5 (Policy concept, which
`NormativePolicy` specialises, AM-28).

**Blast radius:** `NormativePolicy` has no `body_items` catch-all — every
field is typed directly in its grammar rule (`source`, `kind`, `type`,
etc.), the same style `Community` uses (AM-41). One new optional field,
no changes to any existing field, no changes to `NormativePolicyRef`,
`Domain`, `Federation`, or `Community`'s handling of `normative_policies`.

**Design/implementation history — a real collision, not a clean first
pass:** The first attempt added a brand-new grammar rule, also named
`EnforcementMode`, with literals `'policed_pessimistic' |
'policed_optimistic' | 'unpoliced'` (the exact vocabulary proposed in the
2026-07-19 CONCEPTS_INDEX.md finding). This broke the existing test suite
— `grammar/v2/el_grammar.tx` already has an unrelated, pre-existing
`EnforcementMode` rule (`'optimistic' | 'pessimistic'`, line ~298),
implemented for generic `Policy`'s own `Enforcement` construct
(`Policy.enforcement: Optional[Enforcement]`, `Enforcement` supporting
`'policed' mode=EnforcementMode ('mechanism' ':' ...)?  | unpoliced?='unpoliced'`).
textX did not raise an error at metamodel-build time for the duplicate
rule name; it silently broke parsing of `scenarios/gp_referral/gp_referral_scenario.el`'s
own pre-existing `enforcement policed pessimistic` usage instead
(regression caught by the full suite: `tests/test_revocation_endpoint.py`,
`tests/test_scenario_builders.py[gp_referral]`). The first attempt was
reverted in full (grammar rule and dataclass field) before redesigning.

**Proposed grammar (`grammar/v2/el_grammar.tx`), as actually landed:**
```
NormativePolicy:
    'normative_policy' name=ID '{'
        ('description'       ':' description=STRING)?
        'source'             ':' source=STRING
        'kind'               ':' kind=NormativePolicyKind
        ('enforcement'       ':' enforcement=NormativePolicyEnforcement)?
        ('type'              ':' policy_type=PolicyType)?
        ('initial_value'     ':' initial_value=PolicyValue)?
        ('review_cycle'      ':' review_cycle=Duration)?
        ('policy_setting_behaviour' ':' setting_behaviour=STRING)?
    '}'
;

NormativePolicyEnforcement:
    ('policed' mode=EnforcementMode)
    | (unpoliced?='unpoliced')
;
```
`EnforcementMode` itself (`'optimistic' | 'pessimistic'`) is **reused
as-is** from its pre-existing declaration — no new rule with that name,
no new literal vocabulary. `NormativePolicyEnforcement` is new; it
mirrors `Enforcement`'s two-branch shape (`policed <mode>` vs.
`unpoliced`) but deliberately omits `Enforcement`'s `('mechanism' ':'
STRING)?` sub-field, consistent with `NormativePolicy`'s existing
lightweight design principle (a source, a kind, now optionally an
enforcement mode — not the full policy envelope/value machinery).

**Design rationale:**
- Reusing the existing `EnforcementMode` rule by reference
  (`mode=EnforcementMode`) rather than inventing new literals means
  `NormativePolicy.enforcement` and `Policy.enforcement` now share
  identical enforcement-mode vocabulary by direct reuse, not coincidence
  — `policed pessimistic`/`policed optimistic`/`unpoliced`, not the
  originally-proposed single-token `policed_pessimistic` form.
- `NormativePolicyEnforcement`'s ordered-choice alternation (`('policed'
  mode=EnforcementMode) | (unpoliced?='unpoliced')`) makes `mode`
  non-`None` and `unpoliced=True` mutually exclusive **by grammar
  construction**, not by convention: each branch only ever assigns its
  own field, and PEG ordered choice commits to the first branch that
  matches without attempting the other. Confirmed both by this reasoning
  and by a direct test: `enforcement: policed pessimistic unpoliced` and
  `enforcement: unpoliced pessimistic` are both syntax errors (leftover
  unconsumed token), not silently-accepted values that would set both
  fields (see `tests/test_am42_normative_policy_enforcement.py`,
  `test_enforcement_mode_and_unpoliced_are_mutually_exclusive`).
- No object processor needed for either the plain-scalar case
  (`Policy.enforcement`'s pre-existing `Enforcement` class, confirmed by
  smoke test) or the new `NormativePolicyEnforcement` class — both are
  registered classes matching their own grammar rules, so textX
  instantiates and populates them directly at parse time. In the course
  of this investigation, a stale doc comment was found and corrected:
  `Enforcement`'s docstring claimed "Object processor (P11) sets
  unpoliced=True when mode is absent" — grepped `el_parser.py` and
  confirmed no such processor exists or ever did; `unpoliced?='unpoliced'`
  is a textX boolean match, assigned directly at parse time. (Also
  incidentally the "P11" label in that stale comment collided in name,
  though not in effect, with this session's real P11 — `process_community`,
  AM-41 — an unrelated coincidence worth noting for anyone grepping "P11"
  later.)

**Validator impact:** none. No validator rule reads or checks
`NormativePolicy.enforcement` in this pass — explicitly out of scope.
In particular, no relationship between `NormativePolicy.enforcement` and
`DeonticToken.discharge_mode` is built, checked, or cross-referenced;
CONCEPTS_INDEX.md's "Open question" about an eventual consistency check
between the two remains open, unresolved, exactly as before this
amendment.

**Files changed:** `docs/el_grammar_amendments.md` (this entry),
`docs/CONCEPTS_INDEX.md` ("NormativePolicy scope" entry: Finding
paragraph corrected from "proposed, not yet implemented" to "landed
2026-07-22"; two inline literal-syntax examples elsewhere in the entry
corrected from `policed_pessimistic` to `policed pessimistic` to match
what actually landed; AIVendor section's cross-reference paragraph
likewise corrected), `grammar/v2/el_grammar.tx` (`NormativePolicy` rule,
new `NormativePolicyEnforcement` rule), `toolchain/el_domain.py` (new
`NormativePolicyEnforcement` dataclass, registered in `DOMAIN_CLASSES`;
`NormativePolicy.enforcement` field added; `Enforcement`'s stale
docstring corrected), `scenarios/referral/referral_scenario.el`
(`AuthorshipBasis` and `ConsentRightsBasis` — both added under AM-41 —
now declare `enforcement: policed pessimistic`, since privacy legislation
isn't optional/voluntary), `tests/test_am42_normative_policy_enforcement.py`
(new file, 6 tests: policed-pessimistic resolves; policed-optimistic
resolves; unpoliced resolves; absent defaults to `None`; mode/unpoliced
mutual exclusivity confirmed as a syntax error in both combined-token
orderings; the real referral scenario's `AuthorshipBasis`/
`ConsentRightsBasis` both resolve to `policed pessimistic`). `toolchain/el_parser.py`
required no changes — confirmed by smoke test, not assumed. Full suite:
68 pre-existing tests pass unchanged, plus these 6 new ones (74 total).

**Status:** IMPLEMENTED — `NormativePolicy.enforcement` optional field
landed, reusing Policy's existing `EnforcementMode` vocabulary; no link
to `discharge_mode` built (deliberately out of scope).

## AM-43 (2026-07-28) — Optional url field on NormativePolicy (§6.5 citation identity)

**Status:** IMPLEMENTED (2026-07-28) — `NormativePolicy` gains an optional
`url` field, a plain STRING sub-field alongside `source`.

**Problem:** `NormativePolicy.source` is a plain descriptive string with no
link to the actual instrument it cites. A colleague viewing the board's
citation line (`docs/Board_NormativePolicy_Display_Investigation_2026-07-22.md`,
"combined next-session scope" addendum, item 1) asked "where's the URL?" —
the honest answer was "there isn't one yet." This amendment is item 1 of
that addendum's two paired follow-ups; item 2 (permit/embargo governance
resolution) is separate follow-on work, not touched here.

**Standard reference(s):** §6.5 (Policy concept, which `NormativePolicy`
specialises, AM-28) — no new standard grounding needed; `url` is an
identity/reference detail of the same citation `source` already carries,
not a new concept.

**Blast radius:** one new optional field on `NormativePolicy`'s own grammar
rule, placed directly after `source` (the field it complements). No changes
to `NormativePolicyRef`, `NormativePolicyEnforcement`, `Domain`,
`Federation`, or `Community`'s handling of `normative_policies`.

**Grammar (`grammar/v2/el_grammar.tx`), as landed:**
```
NormativePolicy:
    'normative_policy' name=ID '{'
        ('description'       ':' description=STRING)?
        'source'             ':' source=STRING
        ('url'               ':' url=STRING)?
        'kind'               ':' kind=NormativePolicyKind
        ('enforcement'       ':' enforcement=NormativePolicyEnforcement)?
        ('type'              ':' policy_type=PolicyType)?
        ('initial_value'     ':' initial_value=PolicyValue)?
        ('review_cycle'      ':' review_cycle=Duration)?
        ('policy_setting_behaviour' ':' setting_behaviour=STRING)?
    '}'
;
```

**Design rationale:**
- Plain STRING field, same shape as `source`/`description` — no new
  sub-rule, no new class. Confirmed by smoke test (not assumed, same
  discipline as AM-42): `toolchain/el_parser.py` required no changes; no
  object processor is needed for a plain scalar to populate directly at
  parse time.
- One behavioural note worth recording, not a bug: textX resolves an
  absent optional STRING match to `''` (empty string), not `None` —
  confirmed by smoke test to match `description`'s pre-existing behaviour
  on the same rule. `NormativePolicy.url`'s dataclass default
  (`Optional[str] = None`) is only ever observed if a `NormativePolicy` is
  constructed directly in Python, not via the parser. `''` is falsy in
  both Python and JS, so the frontend's "render `<a href>` when present,
  plain text otherwise" check works correctly regardless of which of the
  two falsy/absent values is in play.

**Validator impact:** none. `url` is not checked by any validator rule —
purely descriptive, like `source`.

**Files changed:** `grammar/v2/el_grammar.tx` (`NormativePolicy` rule, new
`url` field), `toolchain/el_domain.py` (`NormativePolicy.url: Optional[str]
= None`), `toolchain/el_api.py` (`NormativePolicyInfo.url: Optional[str] =
None`; `get_token_governance`'s construction of `NormativePolicyInfo` passes
`url=getattr(p, "url", None)`, matching the existing `description` pattern),
`scenarios/referral/referral_scenario.el` (`AuthorshipBasis`,
`ConsentRightsBasis`, `ReferralEpisodeAccountability` — the three citations
reachable by the board's Obligations panel — each given a real `url`),
`tests/test_am43_normative_policy_url.py` (new file, 3 tests: url present
resolves; url absent resolves to `''`, matching `description`'s existing
behaviour; the three real referral-scenario citations resolve to their real
URLs), `tests/test_token_governance_endpoint.py` (one assertion added to
`test_burden_resolves_to_community_normative_policy`, confirming `url`
passes through the `/tokens/{token_name}/governance` endpoint's
`NormativePolicyInfo` construction). Full suite: 80 pre-existing tests pass
unchanged, plus 3 new (83 total).

**Frontend (computable-governance-ui, separate repo):** not part of this
amendment — `referral-board-view.html`'s `renderObligationCard` rendering
`url` as a real `<a href>` when present (plain text otherwise) is tracked
separately in that repo, per the addendum's step 4.

**Status:** IMPLEMENTED — `NormativePolicy.url` optional field landed;
`AuthorshipBasis`/`ConsentRightsBasis`/`ReferralEpisodeAccountability` in
the referral scenario now carry real URLs. Permit/embargo governance
resolution (item 2 of the paired addendum) remains open, unstarted.

---

## V-17 — Burden/Embargo `for_action` conflict (2026-08-10)

**Status:** IMPLEMENTED (2026-08-10) — `_validate_burden_embargo_conflict`
lands as validator rule `V-17`, registered in `validate_spec`'s dispatcher.

**Motivation:** Follow-on from T5 (Exercise, `el_kripke.py`) — building
T5's Embargo guard surfaced that nothing in the toolchain ever checked
whether a Burden and an Embargo could name the *same* `for_action` at the
specification level. A spec could declare an actor simultaneously
obligated to perform an action (`burden`, §6.4.3) and prohibited from
performing that same action (`embargo`, §6.4.4) — a direct normative
contradiction, not a delegation-chain or discharge-timing question, so it
belongs at Layer 2 (specification validity), not Layer 4 (Kripke
reachability).

**What it checks:** every pair of an `active`-state Burden and an
`active`-state Embargo, both with a non-empty `for_action`. If the two
`for_action` strings match, the rule flags a `[V-17]` error naming both
tokens.

**Why specification-time, not Kripke-time:** this mirrors the
`specification_time_assurance` conflict-resolution strategy already used
at the federation level (§7.9.1 NOTE 3) — a normative conflict this direct
should be rejected when the spec is written, not silently masked or
arbitrated by `el_kripke.py` at model-construction time. T5's Embargo
guard (a Kripke-time mechanism) answers a different question — "is this
specific Permit's exercise blocked right now" — and is actor- and
Action-linkage-scoped; V-17 is unconditional and checked once, at parse
time, independent of any Kripke world.

**Standard reference(s):** §6.4.3 (Burden/obligation), §6.4.4
(Embargo/prohibition), §7.9.1 NOTE 3 (specification-time conflict
resolution, the precedent this rule's timing follows).

**Single-domain-scope limitation:** like T5's Embargo guard, this rule
cannot detect conflicts where the Burden and Embargo belong to different
domains in a federation — `domain_scope` does not exist on bare
`DeonticToken` today. See "Permit/Embargo missing domain scope
(§7.8.8.2/§7.8.8.3 gap)" in `docs/CONCEPTS_INDEX.md`.

**Validator (`toolchain/el_validator.py`), as landed:**
```python
def _validate_burden_embargo_conflict(model) -> List[str]:
    errors: List[str] = []
    burdens = [
        t for t in _collect(model, "DeonticToken")
        if getattr(t, "kind", None) == "burden"
        and getattr(t, "state", None) == "active"
        and getattr(t, "for_action", None)
    ]
    embargoes = [
        t for t in _collect(model, "DeonticToken")
        if getattr(t, "kind", None) == "embargo"
        and getattr(t, "state", None) == "active"
        and getattr(t, "for_action", None)
    ]
    for burden in burdens:
        for embargo in embargoes:
            if burden.for_action == embargo.for_action:
                errors.append(
                    f"[V-17] Burden '{burden.name}' requires action "
                    f"'{burden.for_action}', which Embargo '{embargo.name}' "
                    f"actively prohibits — normative conflict. (§6.4.3, §6.4.4)"
                )
    return errors
```
Registered in `validate_spec`'s dispatcher immediately after V-16b.

**Files changed:** `toolchain/el_validator.py` (`_validate_burden_embargo_conflict`,
new function; module docstring's "Rules implemented" list; dispatcher
registration). `tests/test_v17_burden_embargo_conflict.py` (new file, 2
tests: fires on matching active `for_action`; does not fire when the
Embargo is `pending` or the `for_action` values differ). Full suite: 92
pre-existing tests pass unchanged, plus 2 new (94 total).

---

## AM-49 (2026-08-21) — Enforce `discharge_mode: strict` in the live runtime; `advance_clock()` blocks on an actionable strict Burden

**Status:** IMPLEMENTED (2026-08-21).

**Problem:** closes the `discharge_mode: strict` OPEN FINDING logged in
`docs/CONCEPTS_INDEX.md` (2026-08-20). The paper's central claim
(EDOC26final.tex, reviewer_response.md) is that the runtime blocks time
advancement when a strict obligation is actionable — but `el_engine.py`/
`el_runtime.py` never branched on `discharge_mode` anywhere; the only real
tick-suppression logic lived entirely inside `el_kripke.py`'s Rule T3
(BFS world-expansion), with no connection to a live `WorldState.tick` or
any `advance()`/`advance_clock()` call.

**What changed:** `advance_clock()` (`el_engine.py`) now scans
`state.tokens` directly, before advancing tick, via a new private helper
`_strict_actionable_burdens()`, for any token with `kind=="burden"`,
`discharge_mode=="strict"`, `state=="active"` (never `"pending"` —
§7.8.7's masked/suspended state is a different thing), holder currently
enrolled. If one or more exist, `advance_clock()` returns
`outcome="blocked"` via the same `_blocked()`/`TransitionRecord`
convention `advance()` already uses — it never raises for this case —
and leaves tick completely untouched, not partially advanced by any of
the ticks requested. `reason` names every blocking burden and its
holder, joined by a small serial-comma helper (`_list_and()`) so the
message reads correctly whether one or several burdens are blocking
(e.g. `"strict burden 'x' (held by 'y') is actionable..."` vs.
`"strict burdens 'x' (held by 'y') and 'z' (held by 'w') are
actionable..."`).

**Direct raw-field check, not Kripke/`ObligationState`-coupled:** the
predicate reads `TokenInstance.state`/`.discharge_mode`/`.kind`/`.holder`
directly off the live `WorldState` — no dependency on `el_kripke.py`'s
`ObligationState`/`ActorStatus` types, so Layers 3 and 4 independently
enforce the same rule without either importing the other's types.

**API:** `AdvanceClockResponse` (`el_api.py`) gains `outcome: str` and
`reason: Optional[str] = None`, mirroring `ExecuteActionResponse`'s
existing convention. A blocked call is a normal 200 with `outcome`/
`reason` in the body, not an `HTTPException` — 400 remains reserved for
the pre-existing `ticks < 1` case.

**Standard reference(s):** none new — this closes an enforcement gap on
the existing `discharge_mode: strict` toolchain extension (AM-13); §6.4.3
(Burden), §7.8.7 (token state).

**Empirical verification against the real scenario** (not just the probe
fixtures): fresh `_build_referral_runtime()` → `advance_clock(5)` →
`blocked`, reason `"strict burden 'referralInitiationBurden' (held by
'GPClinician') is actionable and must be discharged before time can
advance"`, tick stays `0`. Then `initiateReferral` discharges
`referralInitiationBurden`. Then `advance_clock(5)` → `ok`, tick == `6`.
Confirms the paper's claim now holds in the running system, not only in
the verifier's model of it.

**Not in scope, deliberately:** `advance()` itself is unaffected — this
closes the gap only for the "let time pass" primitive, since that is the
specific mechanism the paper's claim and reviewer-response commitments
named. Whether `advance()` needs an analogous guard for unrelated
actions while a strict burden sits actionable is a separate question, not
addressed here.

**Known follow-up, not fixed here:** `computable-governance-ui`'s
`referral-board-view.html` `advanceClock()` handler (separate repo)
discards the `/advance-clock` response body entirely
(`await resp.json()`, unused) and unconditionally shows a "time advanced"
success message on any HTTP 200 — confirmed today by direct read, not
yet updated. A blocked call from a cold reset will now show a **false
success message** in the UI. Flagged, deliberately not fixed in this
commit — pending a decision on whether to land it together with this
backend change for a cleaner demo story.

**Files changed:** `toolchain/el_engine.py` (`_strict_actionable_burdens()`,
`_list_and()`, `advance_clock()` blocking branch + updated docstring),
`toolchain/el_api.py` (`AdvanceClockResponse.outcome`/`.reason`,
`advance_clock_endpoint()`, endpoint description text), `tests/test_advance_clock.py`
(two new probes `_STRICT_PROBE`/`_TWO_STRICT_PROBE`; three new tests:
blocks when a strict burden is active and actionable; unblocks once
discharged; reason names every blocking burden with correct plural
wording). Full suite: 156 pre-existing tests pass unchanged, plus 3 new
(159 total).

---

## AM-50 (2026-08-21) — Bridge one-sided `principal_of` standing affiliation into the delegation-chain walk

**Status:** IMPLEMENTED (2026-08-21).

**Problem:** closes Problem 3 of the paused "Delegation holder/chain
resolution" finding (`docs/CONCEPTS_INDEX.md`, 2026-08-19).
`el_reasoner.py`'s `_walk_chain()`/`delegation_graph()` and
`el_kripke.py`'s `_delegation_chain_for_token()` only ever traversed
`Delegation` elements — never `principal_of`. `referral_scenario.el`'s
`GPPractice { principal_of GPClinician }` link is declared as a bare,
deliberately one-sided `principal_of` (no reciprocal `delegated_from` —
see that file's own header comment, lines 41-84: "organisational
affiliation of an independently-accountable party... deliberately NOT
full subordinate agency"). Confirmed by direct empirical re-run before
this fix: `ultimate_accountability(model, "...referralResponseBurden
obligation...")` stopped dead at `GPPractice`, `current_holder ==
"GPPractice"`, despite `gpToSpecialistDelegation` (`GPClinician →
SpecialistClinician`, matching obligation text) existing one hop
further down — structurally unreachable because the walk starts at
`Commitment.actor` ("GPPractice") and the Delegation graph is keyed by
`"GPClinician"`, with no bridge between the two.

**What changed:** a new predicate, `_is_standing_affiliation(principal_name,
agent)` (duplicated in both files — same Layer 3/4 no-cross-import
convention `_find_action_for_burden` already follows), returns `True`
when a `principal_of` entry is **one-sided**: the agent's own
`delegated_from` is absent, or points to a *different* principal than
this one. Only one-sided entries are added as new, unconditionally-
matching ("structural") edges:

- `el_reasoner.py`: `DelegationLink` gains `structural: bool = False`.
  `delegation_graph()` adds a second pass over every `EnterpriseObject`'s
  `principal_of` list, appending a `structural=True` link (empty
  `obligation`, no `sub_delegation_allowed`/`revocable`/etc.) for each
  one-sided entry. `_walk_chain()`'s filter becomes `link.structural or
  obligation.lower() in link.obligation.lower()` — structural edges
  match any obligation being searched for, since they represent a
  standing relationship, not an obligation-specific transfer.
- `el_kripke.py`: `_delegation_chain_for_token()` gets the same second
  pass, adding parent-pointers via `parent.setdefault(agent_name,
  principal_name)` — `setdefault` means any `Delegation`-derived parent
  (the more specific signal, already correctly obligation-scoped by
  `transfers_burden`) always wins if one exists for that node.

**Why paired `principal_of`+`delegated_from` is deliberately NOT
duplicated as a structural edge:** a paired relationship (e.g.
`GPClinician → SpecialistClinician`) is already an explicit `Delegation`
with its own obligation-scoped text (`gpToSpecialistDelegation`).
Duplicating it as an unconditionally-matching structural edge would let
an *unrelated* obligation ride along that hop — confirmed this would
actually happen: `clinicalHandoverBurden` (held by `GPClinician` alone,
never delegated further) would incorrectly extend to
`SpecialistClinician` too, since `GPClinician.principal_of` includes
`SpecialistClinician` regardless of which obligation is being asked
about. Excluding paired entries, and relying on `setdefault` ordering in
the Kripke-side chain, closes this off. Verified directly via
`test_clinical_handover_burden_does_not_over_extend_to_specialist`.

**Standard reference(s):** §7.10.1 alone ("by each such delegation, that
active enterprise object becomes an agent of the parties delegating,
and the parties (collectively) become principal of that object") —
already directly verified against this repo's own citation of the
clause. **§6.6.8 NOTE 3 was considered and rejected** as a citation for
the paired-vs-one-sided discriminator specifically: the only record of
its actual text in this repo (`grammar/v2/el_grammar.tx:112-114`) reads
"A specification may state that, in its initial state, an active
enterprise object is an agent of a party" — it licenses the
`delegated_from` construct itself, but says nothing about pairing with
`principal_of` being required for a "genuine" relationship. That
distinction is this scenario's own documented modelling convention
(`referral_scenario.el`'s header comment), not something the standard's
text draws — worth being explicit about that distinction rather than
overclaiming standard grounding for it.

**Root principal unaffected, chain extended/corrected:** traced against
every `Commitment` in `referral_scenario.el` — `Commitment.actor` is
unchanged in every case (`GPPractice` stays root for
`referralInitiationBurden`/`referralResponseBurden`/`clinicalHandoverBurden`;
`SpecialistPractice` for `assessmentSchedulingBurden`;
`SpecialistClinician` for `aiExaminationBurden`, already correct and
untouched). Only `current_holder`/the discovered chain changes.
**One correction surfaced along the way, not a new one introduced:**
`referralInitiationBurden`'s previously-reported holder (`GPPractice`)
was already wrong against the live runtime — `_build_referral_runtime()`
(`el_api.py`) grants `referralInitiationBurden` to `referring_practitioner`,
which defaults to `"GPClinician"`, not `"GPPractice"`. This fix corrects
that pre-existing inaccuracy as a side effect, bringing the static
reasoner's inferred holder into alignment with the real runtime grant.

**Files changed:** `toolchain/el_reasoner.py` (`DelegationLink.structural`,
`_is_standing_affiliation()`, `delegation_graph()` second pass,
`_walk_chain()` filter), `toolchain/el_kripke.py` (mirrored
`_is_standing_affiliation()`, `_delegation_chain_for_token()` second
pass), `tests/test_am50_accountability_chain_principal_of.py` (new file,
5 tests: `referralResponseBurden` chain now reaches
`SpecialistClinician` via the `GPPractice → GPClinician` bridge;
`referralInitiationBurden` holder corrected to `GPClinician`;
`clinicalHandoverBurden` does NOT over-extend to `SpecialistClinician`
— the discriminator-safety check; `el_kripke._delegation_chain_for_token()`
mirrors `el_reasoner`'s result for the same scenario; a
no-`principal_of`-at-all probe is a pure regression guard). Full suite:
159 pre-existing tests pass unchanged, plus 5 new (164 total).

---

## AM-51 (2026-08-22) — Complete `_delegation_chain_for_token()`'s token_group-membership match; redirect `gpToSpecialistDelegation`; register V-NEW-10

**Status:** IMPLEMENTED (2026-08-22).

**Problem:** closes Problem 1 of the paused "Delegation holder/chain
resolution" finding (`docs/CONCEPTS_INDEX.md`, 2026-08-19) —
`transfers_token_group` conflating two unrelated purposes with no
distinguishing field. `referral_scenario.el`'s `gpToSpecialistDelegation`
declared both `transfers_burden: referralResponseBurden` and
`transfers_token_group: referralBurdenGroup` simultaneously — the latter a
5-member group that also served as the episode objective's
`all_discharged` satisfaction target, with no signal distinguishing "these
burdens transfer together" from "these burdens together satisfy the
objective." This also meant the delegation tripped the (until now,
unregistered) V-NEW-10 mutual-exclusion rule.

**What changed, and why in this order:**

1. **`el_kripke.py::_delegation_chain_for_token()` extended to match a
   Delegation via `token_group` membership, not just a direct `burden`
   reference** (parallel to the existing `.burden` check, same
   `parent[to] = frm` outcome either way). This was done *first*,
   independently, because simply redirecting the group and dropping
   `transfers_burden` would otherwise silently regress AM-50's own fix:
   `_delegation_chain_for_token()` is the sole path by which the
   `GPClinician → SpecialistClinician` hop enters the Kripke-facing chain
   for `referralResponseBurden` (that hop is a *paired*
   `principal_of`+`delegated_from` relationship, deliberately excluded from
   AM-50's structural-edge mechanism — see AM-50's own writeup). Confirmed
   via `tests/test_am50_accountability_chain_principal_of.py::test_delegation_chain_for_token_mirrors_reasoner_for_referral_response`,
   which reads `Delegation.burden` directly and would have silently lost
   the hop had `transfers_burden` been dropped without this extension.
   **Generality check performed first:** grepped every `.el` scenario file
   for a `Delegation` declaring `transfers_token_group` with no
   `transfers_burden` — none exists today (every current
   `transfers_token_group` declaration, in both `referral_scenario.el` and
   `gp_referral_scenario.el`, is paired with a `transfers_burden` that
   already provided a direct match). The gap in the walker was real and
   general — it just hadn't been exercised by any committed scenario until
   this change deliberately exposes it. New isolated test file
   `tests/test_delegation_chain_token_group_match.py` (3 tests, synthetic
   fixture, no real scenario file) confirms the new match path in
   isolation, including a scoping-safety check (a non-member token must not
   be pulled into the chain).

2. **`gpToSpecialistDelegation` redirected**: `transfers_burden:
   referralResponseBurden` removed entirely; `transfers_token_group` now
   points at `specialistBurdenGroup` (a 2-member group — `referralResponseBurden`
   + `assessmentSchedulingBurden` — already declared for this purpose, not
   new). `referralBurdenGroup` (5 members, the episode objective's
   `all_discharged` target) is untouched, resolving the two-purposes
   conflation: the group named on the objective and the group named on the
   delegation are no longer the same object.

3. **V-NEW-10 registered** in `el_validator.py::_validate_delegations()`
   (already dispatched from `validate_spec()` alongside V-07/V-08), message
   text matching the proposed rule in this file verbatim. Confirmed
   `gpToSpecialistDelegation` no longer trips it post-redirect (0 validator
   errors against `referral_scenario.el`). Confirmed, deliberately, that
   `gp_referral_scenario.el`'s own `gpToSpecialistDelegation` — same
   dual-declaration shape, out of scope for this fix — now *would* trip
   V-NEW-10 if validated; traced every `parse(..., validate=True)` call
   against a real scenario file in the test suite and confirmed none target
   `gp_referral_scenario.el` (it is always parsed with `validate=False` in
   `el_api.py`), so nothing in the current suite regresses. Left as a
   known, named gap for `gp_referral_scenario.el` rather than silently
   fixed alongside this one — out of this task's scope.

**Confirmed unaffected:** `_build_obligation_descriptors()`
(`el_engine.py`) output for `referralResponseBurden` and
`assessmentSchedulingBurden` — both already have their own `Commitment`
(`referralResponseCommitment`, `assessmentSchedulingCommitment`), so the
function's `Delegation.token_group` second pass (guarded by `if burden_name
in descriptors: continue`) was already fully inert for this delegation
*before* today's change too, regardless of which group it named. Verified
directly rather than assumed. Separately worth noting for a future reader:
this function's own `holder`/`chain` for `referralResponseBurden`
(`GPPractice`, unextended) differs from `_delegation_chain_for_token()`'s
(`GPPractice → GPClinician → SpecialistClinician`) — a pre-existing,
unrelated discrepancy, since `el_engine.py`'s `walk_chain()` is a separate
implementation (obligation-text matching only, no AM-50 `principal_of`
bridge) that this change does not touch.

**Files changed:** `toolchain/el_kripke.py`
(`_delegation_chain_for_token()`), `scenarios/referral/referral_scenario.el`
(`gpToSpecialistDelegation`), `toolchain/el_validator.py`
(`_validate_delegations()`, V-NEW-10), `tests/test_delegation_chain_token_group_match.py`
(new, 3 tests), `tests/test_v_new_10_delegation_transfer_exclusivity.py`
(new, 2 tests). Full suite: 164 pre-existing tests pass unchanged, plus 5
new (169 total).

**A note on process, for the record:** an earlier pass in this same session
(2026-08-21, in conversation) concluded a narrower version of this fix
(redirect the group only, keep `transfers_burden`) was "confirmed safe" —
but that reasoning was never written into `docs/CONCEPTS_INDEX.md` at the
time, only carried in conversation state. It did not survive a fresh
verification pass in this later session, which found the dual-declaration
tension with V-NEW-10 that the earlier pass had missed. The lesson isn't
the specific miss — it's that a "confirmed safe" conclusion that exists
only in session memory, and not as a written repo record, does not actually
protect the next session (or the next agent) from re-deriving it, or from
missing what it missed. Written the causal story out in full above
specifically so that doesn't recur here.

---

## AM-52 (2026-08-22) — Guard `_delegation_chain_for_token()`'s token_group match against a token's own Commitment root

**Status:** IMPLEMENTED (2026-08-22).

**Problem:** a direct regression AM-51 itself introduced, found the same day
during a ground-truth re-verification of the 2026-08-19 paused finding's
Problem 2 ("no clean discriminator exists over `Commitment.actor`/
`Delegation.delegator`"). That re-verification confirmed Problem 2 itself is
closed (no live code anywhere compares `Commitment.actor` to
`Delegation.delegator`/`.delegate` by equality; it was only ever a
hypothesis tested in investigation, never implemented) — but while
confirming that, it surfaced that AM-51's `token_group`-membership match is
keyed purely on group co-membership, with **no awareness of the token's own
`Commitment` at all**. That's correct when every group member is genuinely
covered by the delegation (`referralResponseBurden` in
`referral_scenario.el`, the case AM-51 was built for), but wrong when a
member has its own, independently-declared `Commitment` root the delegation
has nothing to do with.

**Systematic check performed before fixing (not just the one known case):**
every `token_group` member referenced by a `Delegation`, across every
scenario file with such a delegation (only two exist —
`referral_scenario.el` and `gp_referral_scenario.el`), checked against
whether `ultimate_accountability()`'s forward walk for that member's own
`Commitment.obligation` text actually passes through the delegation's
`(delegator, delegate)` edge. Found **4 conflicts, not 1**:

| Scenario | Token | Commitment.actor | Delegator | Conflict cause |
|---|---|---|---|---|
| referral_scenario.el | `assessmentSchedulingBurden` | `SpecialistPractice` | `GPClinician` | actor unreachable from delegator |
| gp_referral_scenario.el | `assessmentSchedulingBurden` | `SpecialistParty` | `GPPracticeParty` | actor unreachable from delegator |
| gp_referral_scenario.el | `referralInitiationBurden` | `GPPracticeParty` | `GPPracticeParty` | actor == delegator (reachable), but obligation text irrelevant |
| gp_referral_scenario.el | `clinicalHandoverBurden` | `GPPracticeParty` | `GPPracticeParty` | actor == delegator (reachable), but obligation text irrelevant |

The `gp_referral_scenario.el` cases matter for design, not just count: a
bare reachability check (`Commitment.actor` reachable from the delegator)
would have caught only the two `assessmentSchedulingBurden` cases and
missed `referralInitiationBurden`/`clinicalHandoverBurden` entirely, since
their actor trivially equals the delegator. Those two are excluded only by
obligation-text mismatch — the same failure shape Problem 2's original
`actor == delegator` hypothesis produced as a false positive, now
resurfacing through a different mechanism (`gp_referral_scenario.el`'s own
Problem-1 conflation — `gpToSpecialistDelegation` there still points its
`transfers_token_group` at `referralBurdenGroup`, the 4-member
objective-satisfaction group, not a correctly-scoped transfer group — is
already a known, explicitly out-of-scope gap in that file per AM-51's own
write-up; this is a second, independent symptom of that same unfixed root
cause, not a new discovery about the file).

**What changed:** `el_kripke.py::_delegation_chain_for_token()`'s
`token_group`-membership match branch is now guarded. New helper
`_commitment_root_for_token(spec, token_name)` returns the token's own
`(Commitment.actor, Commitment.obligation)` if a `Commitment` exists for
it, mirroring `el_reasoner.py`'s `ultimate_accountability()` root
extraction and `el_engine.py`'s `_build_obligation_descriptors()` — a third
duplicate of the same small pattern, per this codebase's established
Layer 2/3/4 no-cross-import convention (`_find_action_for_burden`,
`_is_standing_affiliation`).

Where a `Commitment` exists, a `token_group` match is trusted only if
**both**:
- **Reachability** — the Delegation's `delegator` equals the Commitment's
  `actor`, or is reachable from it by walking the same one-sided
  `principal_of` structural edges AM-50 already established (the structural
  map is now built *before* the Delegation loop, reordered specifically so
  this check can consult it).
- **Text relevance** — the Commitment's own `obligation` text is a
  substring of the Delegation's `obligation` text, mirroring
  `el_reasoner.py`'s `_walk_chain()` matching (`obligation.lower() in
  link.obligation.lower()`) and `el_engine.py`'s equivalent, so the same
  notion of "this delegation is about this obligation" is applied
  consistently across all three files.

A token with **no** `Commitment` at all (fully delegation-sourced — see
`tests/test_delegation_chain_token_group_match.py`'s `burdenTwo` fixture)
is unaffected — the group match is trusted unconditionally, exactly as
AM-51 left it. **The direct `.burden` match is unconditional and untouched
either way** — an explicit single-token reference is unambiguous, unlike
group co-membership, and nothing found any evidence of it ever being wrong.

**Confirmed against all 4 known conflicts, and the two already-correct
cases, directly (not assumed):**

```
referral_scenario.el
  assessmentSchedulingBurden  -> [SpecialistPractice, SpecialistClinician]   (was: [GPPractice, GPClinician, SpecialistClinician] — now matches ultimate_accountability() and the live runtime holder)
  referralResponseBurden      -> [GPPractice, GPClinician, SpecialistClinician]   (unchanged — the case AM-51 was built for)

gp_referral_scenario.el
  assessmentSchedulingBurden  -> [SpecialistParty, SpecialistClinician]   (now matches its own Commitment root)
  referralInitiationBurden    -> [GPClinician]   (no longer wrongly extends; see note below)
  clinicalHandoverBurden      -> [GPClinician]   (no longer wrongly extends; see note below)
  referralResponseBurden      -> [GPPracticeParty, SpecialistClinician]   (unchanged — direct .burden match, unaffected by this guard)
```

**Reported as found, not forced, per instruction:** `referralInitiationBurden`/
`clinicalHandoverBurden`'s corrected chains do **not** reach
`GPPracticeParty` even though that's their true `Commitment` root — they
stay at the queried holder (`GPClinician`). This is a separate, pre-existing
property of `gp_referral_scenario.el` itself, not introduced by this fix:
`GPPracticeParty { principal_of GPClinician }` there is **paired** with
`GPClinician`'s own `delegated_from GPPracticeParty` — a paired
`principal_of`+`delegated_from` relationship, which AM-50 deliberately
excludes from its structural-edge mechanism (paired relationships are
already a genuine `Delegation`/`Commitment` pairing with their own scoped
text; see AM-50's own write-up and `_is_standing_affiliation()`). With this
guard now correctly refusing the group-derived shortcut, there is simply no
edge left — of any kind — connecting `GPClinician` back to `GPPracticeParty`
for these two specific tokens. Left exactly as found; not this fix's scope
to address.

**Files changed:** `toolchain/el_kripke.py` (`_commitment_root_for_token()`
new; `_delegation_chain_for_token()` reordered and guarded),
`tests/test_am52_token_group_commitment_guard.py` (new, 7 tests: the 4
known conflicts corrected, 2 no-regression checks on the already-correct
cases, 1 synthetic probe isolating text-relevance as an independent
discriminator from reachability). Full suite: 169 pre-existing tests pass
unchanged, plus 7 new (176 total).

**Causal thread, for the record:** AM-51 → committed → this session's
Problem-2 ground-truth re-verification (same day) → surfaced this as a
direct regression AM-51 itself introduced, not an unrelated new finding →
AM-52 closes it. See `docs/CONCEPTS_INDEX.md`'s AM-52 entry for the
narrative version of this same thread.

---

## AM-53 (2026-08-22) — Static-role-anchor fallback in `ultimate_accountability()`

**Status:** IMPLEMENTED (2026-08-22).

**Problem:** standard-conformance gap. ISO/IEC 15414's own library annex
example (§B.2.4) shows a Burden originating purely from filling a role —
"the action of filling a borrower role is therefore a speech act,
resulting in a burden representing the obligation to obey the
regulations" — with no `Commitment` speech act at all, distinct from
§B.2.6.2's borrowing example, which does originate via `Commitment`.
`el_reasoner.py::ultimate_accountability()` previously had exactly two
paths to a root — a matching `Commitment`, or a matching `Delegation`
whose obligation text names the burden — and silently returned `[]` for
everything else. Confirmed live, not theoretical: checked every burden
against every `Commitment` in every scenario file; `ereferral_model.el`
has **zero** `commitment`/`delegation` blocks anywhere — all 4 of its
burdens are conferred purely via `holds` inside a `Role` body.

**What changed:** a new dataclass, `StaticRoleAnchor`, and a new
last-resort path, `_find_role_anchors_for_obligation()`, invoked only when
neither a `Commitment` nor a `Delegation` names the obligation at all.
`ultimate_accountability()`'s return type becomes
`List[Union[AccountabilityChain, StaticRoleAnchor]]` — the two are never
mixed within one call (the fallback only runs when the primary path found
nothing), and an empty list retains its existing meaning: genuinely not
found.

`StaticRoleAnchor` is deliberately **not** a claim about who the standard
says holds the token. `docs/CONCEPTS_INDEX.md`'s "WorldState scope"
finding (2026-08-20) already establishes, citing §6.4.3 directly, that
deontic tokens are held by active enterprise objects filling roles, never
by roles or communities directly — role-filling for an ordinary Community
role is confirmed (grammar + `el_api.py` builder inspection) to be a
runtime-only fact, established via `enroll()`, not expressible anywhere in
the static `.el` spec. `StaticRoleAnchor` reports the nearest static
anchor — the `Role` and its owning `Community` — as far as the static
spec alone can honestly go, structurally distinct from
`AccountabilityChain` (different dataclass, `describe()` not `render()`)
specifically so a caller cannot mistake a non-final answer for a resolved
party without an explicit `isinstance()` check.

**Confirmed against both live triggers, concretely:**
```
ereferral_model.el, all 4 burdens -> StaticRoleAnchor, e.g.
  referralBurden -> StaticRoleAnchor(token_name='referralBurden',
    role_name='referringClinicianRole', community_name='ReferralEpisodeCommunity')

escalationNoticeBurden (referral_scenario.el, gp_referral_scenario.el) -> still []
```
`escalationNoticeBurden` is **not** fixed by this change, deliberately —
its origination is `ViolationResponse.obligates` (a typed, already-
resolved `[EnterpriseObject]` cross-reference — `SpecialistPractice`), not
a `Role.holds` situation at all (confirmed: zero `holds
escalationNoticeBurden` anywhere in either file). That's a different,
still-open gap (`ultimate_accountability()` never reads `ViolationResponse`
at all), already on record as its own open question in
`docs/CONCEPTS_INDEX.md`. Reported honestly as still returning `[]`, not
silently treated as closed by this fix.

**Caller-safety check performed before committing:** grepped every call
site of `ultimate_accountability(` in the repo. `el_api.py`: zero
references, not a caller. `el_reasoner.py`'s own `__main__` CLI block:
updated to `isinstance(result, StaticRoleAnchor)`-branch rather than
duck-type `.render()`. `tests/test_am50_accountability_chain_principal_of.py`:
4 call sites access `AccountabilityChain`-specific fields
(`.root_party`/`.current_holder`/`.chain`) unconditionally, with no
`isinstance()` guard — not structurally safe, but every one of its
queried obligation texts matches an existing `Commitment` in
`referral_scenario.el`, so the new fallback path is never reached for any
of them; confirmed by re-running that file directly (5/5 pass) rather than
inferring safety from the full-suite result alone. No caller required a
diff.

**Files changed:** `toolchain/el_reasoner.py` (`StaticRoleAnchor` new;
`_find_role_anchors_for_obligation()` new;
`ultimate_accountability()`'s early-return wired to it, return type and
docstring updated; `__main__` CLI block updated to branch on type),
`tests/test_am53_static_role_anchor_fallback.py` (new, 8 tests: the 4
`ereferral_model.el` burdens resolving to `StaticRoleAnchor`, `describe()`
content, `escalationNoticeBurden` confirmed still `[]`, a genuinely-
nonexistent-obligation regression guard, a Commitment-rooted no-regression
check). Full suite: 176 pre-existing tests pass unchanged, plus 8 new
(184 total).

**Known, explicitly out-of-scope gaps surfaced by ground-truth checks
during this same work, logged separately (not fixed here):** see
`docs/CONCEPTS_INDEX.md`'s two entries dated 2026-08-22 immediately
following the AM-52 Problem-2 entry — `_find_roots_from_delegations()`
can present a role-conferred root as a resolved `AccountabilityChain`
without ever routing through this fallback (a second, independent code
path this fix doesn't cover), and `_walk_chain()`'s obligation-text
matching does not survive wording drift across multiple delegation hops,
independent of the Commitment-vs-role-conferred question entirely. Both
confirmed real by direct construction, both open.

---

## AM-54 (2026-08-22) — Structural-first matching in `_walk_chain()`/`_find_roots_from_delegations()`; root-grounding check before wrapping in `AccountabilityChain`

**Status:** IMPLEMENTED (2026-08-22).

**Problem:** closes both open findings logged the same day, immediately
above (following the AM-52 Problem-2 entry) — surfaced during
ground-truth re-verification the day AM-53 landed. `el_kripke.py`'s
`_delegation_chain_for_token()` was already fixed (AM-51/52) to match
structurally (`Delegation.burden`/`.token_group`) rather than by free
obligation text; `el_reasoner.py`'s `_walk_chain()`/
`_find_roots_from_delegations()` still relied on obligation-text matching
alone, which is not standard-grounded to begin with — §6.4.7 NOTE 1
describes delegation as literal token transfer, never as matching
descriptive text. This produced two distinct, confirmed-real failure
modes:

1. `_find_roots_from_delegations()` could present a role-conferred root
   (no `Commitment`, held only via a `Role`'s `holds`) as a fully
   resolved `AccountabilityChain`, with only `root_commitment=None` as
   the easy-to-miss signal it wasn't real — AM-53's `StaticRoleAnchor`
   fallback never covered this code path (it only fires when *nothing*
   matches at the top level; this root was found via a matching
   `Delegation`). Confirmed by construction
   (`MultiHopRoleConferredProbe`): a role-conferred burden delegated
   A→B→C came back as `AccountabilityChain(root_party='A', ...)`.
2. `_walk_chain()`'s recursive text match used the *original* query
   string unchanged at every recursion depth, never the current hop's
   own text — so a later hop whose wording drifted from the original
   silently truncated the walk, independent of the Commitment-vs-
   role-conferred question entirely. Confirmed by construction
   (`TextDriftProbe`): a genuinely `Commitment`-backed 2-hop chain
   P→Q→R reported `current_holder='Q'`, silently missing R.

**Ground-truth performed before designing the fix:**
- Checked every `Delegation` in every scenario file (`referral_scenario.el`,
  `gp_referral_scenario.el`, `consent_scenario.el`,
  `federation_consent_scenario.el`, `generated_governance.el`,
  `industrial_procedure_scenario.el`) — every single one already declares
  `transfers_burden` or `transfers_token_group`. Zero exceptions.
  `ereferral_model.el` has no `Delegation` at all. Text-only delegations
  are grammar-legal but do not exist live today — the fallback is kept
  available (per the design), not eliminated.
- Checked the "residual" case this design's own open question named —
  a delegation-chain root neither `Commitment`-backed nor role-`holds`-
  grounded — against the hypothesis that it corresponds to a party
  directly holding the token via `EnterpriseObject.holds_tokens` (the
  same `HoldsToken` rule shared with `Role` bodies, but declared on the
  object directly — no filler ambiguity at all, unlike a `Role`).
  **Result: negative.** Cross-referenced `Commitment`/`Role.holds`/direct
  `EnterpriseObject.holds` for every burden in every scenario file: direct
  holds is used exactly once in the corpus
  (`gp_referral_scenario.el`'s `agent GPClinician { holds
  referralInitiationBurden; holds clinicalHandoverBurden }`), and in that
  one case it is always redundant with an already-existing `Commitment`
  (already on record as dead code — `docs/CONCEPTS_INDEX.md`, 2026-08-13)
  — never the sole grounding for anything. More directly: the residual
  case itself has **zero live occurrences** in the corpus at all — every
  non-`Commitment` burden today is either role-held (AM-53's case) or
  entirely ungrounded and never delegated (`escalationNoticeBurden`,
  which never reaches `_find_roots_from_delegations()` in the first place
  since it's never named by any `Delegation`). No fourth path added —
  writing code for a case with no live or constructed example would be
  designing for a hypothetical, not a confirmed need. The residual case
  keeps its pre-AM-54 `AccountabilityChain`/`root_commitment=None`
  behaviour, explicitly documented as a deliberate simplification.

**What changed:**
- `DelegationLink` gains `burden_name: Optional[str]` and
  `token_group_members: FrozenSet[str]` (plus a `has_structural_ref`
  property), populated in `delegation_graph()` from each `Delegation`'s
  own `.burden`/`.token_group` — field names and semantics deliberately
  mirror `el_kripke.py`'s AM-51/52 fields, duplicated rather than shared,
  per the established Layer 2/4 no-cross-import convention. The two
  functions' matching logic now converges conceptually.
- `_walk_chain()` takes an optional `token_name`. Matching becomes
  structural-first: a link with a structural reference is matched (or
  rejected) by that signal alone, regardless of its own obligation text —
  free-text matching applies only to a link with no structural reference
  at all (inspectable per-hop via `has_structural_ref`, so a text-matched
  hop is never silently indistinguishable from a structural one).
  Structural (AM-50 `principal_of`) links are unaffected, still always
  match.
- `_find_roots_from_delegations()` now returns `{root_name:
  (obligation_text, token_name)}` instead of just text — root-finding
  itself was already purely graph-topological (a set difference over the
  whole model, not text-based, no recursion needed to reach an arbitrarily
  distant true origin); the change is only that the matched delegation's
  own token reference now travels with the root.
- `ultimate_accountability()`: the `Commitment` path derives `token_name`
  directly from `c.burden` (already had it) and passes it into
  `_walk_chain()`. The delegation-only path now checks the inferred
  root's grounding — via `_find_role_anchors_for_obligation()`, reused
  rather than duplicated — before deciding whether to return an
  `AccountabilityChain` or a `StaticRoleAnchor` for that root.
- `StaticRoleAnchor` gains optional `chain: List[DelegationLink]` and
  `current_holder: Optional[str]` (both default empty/`None`, additive —
  AM-53's original `ereferral_model.el` cases, which have no further
  delegation, are unaffected) so a role-conferred root that IS further
  delegated onward doesn't silently lose the onward chain/current holder
  the walk already discovered.

**Confirmed against both constructions directly:**
```
MultiHopRoleConferredProbe (A role-conferred, no Commitment; A→B→C, transfers_burden: burdenX both hops):
  ultimate_accountability(model, "Do the thing") ->
    StaticRoleAnchor(role_name='roleA', community_name='SomeCommunity',
      chain=[A→B, B→C], current_holder='C')
    -- was: AccountabilityChain(root_party='A', root_commitment=None, ...)

TextDriftProbe (P Commitment-backed; P→Q text-matching, Q→R text drifted; transfers_burden: burdenY both hops):
  ultimate_accountability(model, "Deliver the report") ->
    AccountabilityChain(root_party='P', current_holder='R', chain=[P→Q, Q→R])
    -- was: current_holder='Q', R silently missing
```
Text-fallback path re-confirmed still working for a Delegation genuinely
lacking any structural reference (new `NoStructuralRefProbe`), with
`chain[0].has_structural_ref == False` as the inspectable signal.

**Note on test fixtures:** both new probes trip `V-15`
(`el_validator.py`) when parsed with `validate=True` — V-15 requires
every `Delegation`'s obligation to trace back to a `CommitmentDecl` by
text match, which has the same conceptual blind spot as pre-AM-54
`_walk_chain()` (role-conferred roots, drifted text) in a different
layer. Parsed with `validate=False` for these two fixtures instead,
matching the established pattern for probes exercising cases the
validator doesn't support yet. V-15's own gap is not fixed here — logged
separately (see `docs/CONCEPTS_INDEX.md`).

**Files changed:** `toolchain/el_reasoner.py` (`DelegationLink` extended;
`StaticRoleAnchor` extended; `delegation_graph()` populates the new
structural fields; `_walk_chain()` structural-first with `token_name`
parameter; `_find_roots_from_delegations()` returns token_name alongside
each root; `ultimate_accountability()` derives and threads `token_name`
through both paths, checks delegation-only root grounding),
`tests/test_am54_structural_matching_and_root_grounding.py` (new, 4
tests: role-conferred root → `StaticRoleAnchor` not `AccountabilityChain`;
onward chain/holder preserved on that anchor; text-drift survived via
structural match; text-only fallback still works, flagged
lower-confidence). Full suite: 184 pre-existing tests pass unchanged,
plus 4 new (188 total).

**Causal thread, for the record:** AM-53 → committed → this session's
follow-up ground-truth check (same day) asking whether Commitment is the
only possible delegation-chain root → surfaced both findings above →
AM-54 closes them, plus resolves its own open question (residual-case
hypothesis) with a negative, evidence-based result rather than an assumed
fourth path. See `docs/CONCEPTS_INDEX.md` for the narrative version.

---

## AM-55 (2026-08-22) — Structural-first matching for V-15 (`el_validator.py`)

**Status:** IMPLEMENTED (2026-08-22).

**Problem:** the same conceptual gap AM-54 closed in `el_reasoner.py`,
recurring in the validator layer — surfaced as a side effect of writing
AM-54's own test fixtures (both tripped V-15, logged as its own open
finding, `docs/CONCEPTS_INDEX.md`, 2026-08-22) rather than a targeted
investigation. V-15 (`el_validator.py::_validate_obligation_chain()`)
checked every `Delegation`'s own `obligation` text for **exact string
equality** against the flat set of every `Commitment.obligation` in the
whole model — free-text matching alone, no structural option, no
role-conferred-origin awareness, and (worth noting, uncovered while
reading the existing code) weaker than its own docstring claimed: the
docstring described chain-tracing ("mid-chain delegations... valid as
long as the chain root does"), but the code had no such logic — every
delegation's own text needed an exact match, regardless of chain
position.

**Ground-truth performed first:**
1. Read V-15's exact implementation (above) — confirmed it produced the
   exact "obligation 'Do the thing' does not match any CommitmentDecl"
   errors from AM-54's open finding.
2. Confirmed `_validate_obligation_chain()` receives the same parsed
   `Commitment`/`Delegation` domain objects AM-54 worked with — `.burden`/
   `.token_group` directly accessible, `model` available at the call site
   in `validate_spec()` (just needed threading through). `el_validator.py`
   imports nothing from `el_reasoner.py`/`el_kripke.py`/`el_engine.py` —
   same established no-cross-import convention, duplicated logic, not
   shared.
3. Re-ran both of AM-54's probe fixtures with `validate=True` post-fix —
   both now pass cleanly (see below).

**What changed:** `_validate_obligation_chain()` now checks a
`Delegation`'s structural reference first — is at least one referenced
token (via `transfers_burden` or `transfers_token_group`) grounded, by
name, via a `Commitment` naming it or a `Role`'s `holds` naming it
(AM-53-style)? A design simplification worth being explicit about:
"delegation-continuation" (a mid-chain delegation validly passing along
an already-grounded token) needs no separate case — grounding is checked
per **token name**, not per delegation-chain-position, so any delegation
moving an already-grounded token is automatically valid without walking
the chain. Per-token-group-member auditing is already V-16a's job, kept
separate — V-15 only needs *at least one* referenced token grounded to
confirm a `Delegation` isn't wholly obligation-orphaned. A `Delegation`
with no structural reference at all (grammar-legal, zero live examples —
AM-54's own ground-truth finding) falls back to the original exact-text
check, unchanged.

**Confirmed directly:**
```
MultiHopRoleConferredProbe (AM-54's fixture, role-conferred, no Commitment):
  parse_string(..., validate=True) -> OK  (was: 2× V-15 errors)

TextDriftProbe (AM-54's fixture, Commitment-backed, qToR's text reworded):
  parse_string(..., validate=True) -> OK  (was: 1× V-15 error on qToR)

OrphanedTokenProbe (new — burdenOrphan has no Commitment AND no Role holds it):
  parse_string(..., validate=True) -> ["[V-15] Delegation 'xToY': none of
    its referenced token(s) (['burdenOrphan']) has a resolvable origin
    — no Commitment names it and no Role 'holds' it. (§7.10.1)"]
  -- a genuine violation, confirmed still firing.
```

**Follow-on:** `tests/test_am54_structural_matching_and_root_grounding.py`
updated — its two probes now use `validate=True` directly, the
`validate=False` workaround (and the reasoning comment explaining it) no
longer needed.

**Files changed:** `toolchain/el_validator.py`
(`_validate_obligation_chain()` rewritten; `validate_spec()`'s call site
now threads `model` through; module docstring's V-15 description
updated), `tests/test_am55_v15_structural_matching.py` (new, 5 tests:
both AM-54 fixtures now validate cleanly; a genuine structural-orphan
violation still fires; the text-only fallback still works and still
fires on a genuine mismatch), `tests/test_am54_structural_matching_and_root_grounding.py`
(2 `validate=False` → `validate=True`, no logic change). Full suite: 188
pre-existing tests pass unchanged, plus 5 new (193 total).

**Causal thread, for the record:** AM-54 → committed → writing AM-54's
own tests surfaced V-15 tripping on both fixtures → logged as an open
finding the same day → AM-55 closes it, applying the identical
structural-first pattern AM-54 established, one layer over. See
`docs/CONCEPTS_INDEX.md` for the narrative version.

---

## AM-56 (2026-08-22) — `ViolationResponse.creates_burden` as a fourth accountability root in `ultimate_accountability()`

**Problem:** §7.8.6 NOTE 2 ("a rule prescribing types of actions to be
taken... in the event of... violations... is an obligation, which applies
to that object") was already used to justify `violation_response` as a
top-level grammar declaration, specifically so violation-conferred
obligations would participate in accountability-chain reasoning. That
intent was never implemented in `el_reasoner.py`:
`ultimate_accountability()` had exactly three paths to a root (matching
Commitment, matching Delegation, AM-53's role-anchor fallback) and
returned `[]` for a token originating purely from a
`ViolationResponse.creates_burden` field — confirmed live:
`escalationNoticeBurden` (`referral_scenario.el`, `gp_referral_scenario.el`)
is created only this way, and `ultimate_accountability(model,
"escalationNoticeBurden")` returned `[]` even though the specification
already names who's accountable (`obligates: SpecialistPractice` /
`SpecialistParty`). This exact gap was logged as an open finding in
`docs/CONCEPTS_INDEX.md` ("`escalationNoticeBurden` has no
ObligationDescriptor — invisible to Layer 4") for the Layer-4
(`el_kripke.py`) side of the same hole; this amendment closes only the
Layer-2 side.

**Ground-truth performed first:**
1. Confirmed `ViolationResponse`'s grammar shape
   (`grammar/v2/el_grammar.tx:1089-1098`) and that its Python attribute is
   `responding_actor` (el_domain.py:1253) — `obligates` is only the
   grammar keyword. `creates_burden` (el_domain.py:1255) is a plain
   resolved `Optional[DeonticToken]`. No object processor wraps or
   renames either field.
2. Confirmed `escalationNoticeBurden`/`referralNoResponseViolation`'s
   declaration unchanged in both `referral_scenario.el:775-782` and
   `gp_referral_scenario.el:505-512`.
3. Confirmed V-NEW-15/V-NEW-16 (`on_violation_of` must be a burden;
   `escalate_to` must be a party when `response_kind: escalate`) are
   designed (this file, above) but **not registered** in
   `el_validator.py` — same "designed, never implemented" gap as V-NEW-10
   before AM-51. Left unimplemented here, logged for the record only.
4. Checked every scenario file for `violation_response` declarations:
   `ecommerce_scenario.el`'s three blocks use a stale pre-AM-17 body
   syntax (`triggered_by`/`violated_by`/`condition`/...) that doesn't
   match the current grammar at all — consistent with that file's
   already-documented pre-existing syntax error, out of scope.
   `ereferral_model.el`'s three blocks all omit `creates_burden`. So in
   practice this fix affects exactly `escalationNoticeBurden` in the two
   referral scenarios today, though the code is general.

**What changed:** `ultimate_accountability()` gains a fourth, last-resort
matching pass: when neither Commitment/Delegation nor the AM-53
role-anchor fallback finds anything for the queried token, check whether
some `ViolationResponse.creates_burden` names it (`_find_violation_response_roots()`,
new). Matched structurally on `creates_burden`'s own token identity —
never free text, consistent with AM-54's established precedent. Because
`ViolationResponse.responding_actor` is an already-resolved
`[EnterpriseObject]` cross-reference (no filler ambiguity, unlike
`Role.holds`), a match is reported as a genuine `AccountabilityChain`,
not a `StaticRoleAnchor` — there is nothing runtime-only left to flag.
`AccountabilityChain` gains a new `root_violation_response: Optional[str]`
field (mutually exclusive with `root_commitment`), surfaced in `render()`
exactly as `root_commitment` already is.

**Confirmed directly:** `escalationNoticeBurden` now resolves to a real
`AccountabilityChain` rooted at `SpecialistPractice`
(`referral_scenario.el`) / `SpecialistParty` (`gp_referral_scenario.el`),
with `root_violation_response == "referralNoResponseViolation"`. All
existing Commitment/Delegation/Role.holds/AM-53/AM-54 cases unaffected —
the new pass is gated behind both prior fallbacks finding nothing.

**Test-contract update:** `tests/test_am53_static_role_anchor_fallback.py`'s
`test_escalation_notice_burden_not_fixed_by_this_path_still_empty` — which
explicitly asserted this gap stayed open — rewritten (name, docstring,
first assertion) to assert the resolved chain for both scenario files;
its free-text `"notify GP practice"` assertion is unchanged (still `[]`,
matching still structural-only).

**Layer-4 side explicitly not touched:** `el_kripke.py`'s
`_build_obligation_descriptors()` has the identical hole (only iterates
`Commitment`) — `escalationNoticeBurden` remains structurally absent from
`km.obligation_descriptors`, invisible to AF/EF checks and Bellman
planning. Cross-referenced in `docs/CONCEPTS_INDEX.md`'s existing entry
for that finding; not implemented here.

**Files changed:** `toolchain/el_reasoner.py` (`AccountabilityChain`
gains `root_violation_response`; `ultimate_accountability()`'s docstring
and fallback branch; new `_find_violation_response_roots()`),
`tests/test_am53_static_role_anchor_fallback.py` (one test rewritten).

---

## AM-57 (2026-08-23) — Live `any_discharged` sibling supersession in `el_engine.py`, parity with `el_kripke.py`'s P6b

**Problem:** `el_kripke.py` (Layer 4, the verifier) already implements
P6b — when one member of an `any_discharged` `TokenGroup` discharges, its
remaining PENDING/WAITING siblings transition to `SUPERSEDED`, since the
group's objective is already satisfied by that one discharge.
`el_engine.py` (Layer 3, the live runtime) had no equivalent at all —
confirmed by grep: zero references to `SUPERSEDED`/`any_discharged`/
`TokenGroup` anywhere in the file. A live sibling burden in an
`any_discharged` group stayed `active` forever after a peer discharged,
with nothing to stop it later being flagged VIOLATED by
`check_live_violations()` despite the group's purpose already being
fulfilled.

**Ground-truth performed first:** re-read `el_engine.py`'s Step 7a
discharge block (confirmed at the described location, no drift) and
`el_kripke.py`'s `_build_group_index`/`_build_any_discharged_groups`/P6b
block (confirmed at the described location, no drift). Also confirmed:
no currently committed scenario declares `any_discharged` at all
(`referral_scenario.el`/`gp_referral_scenario.el` both use
`all_discharged`; `gp_referral_scenario.el`'s header comment documents an
earlier `any_discharged`→`all_discharged` correction, §13.1b) — so this
change has zero live scenario impact today, confirmed empirically (both
scenario files parse/validate identically before and after; full test
suite unchanged in count beyond the 4 new tests).

**What changed:** `el_engine.py` gains `_build_group_index()` and
`_build_any_discharged_groups()`, ported (duplicated, not imported) from
their `el_kripke.py` namesakes — Layer 3/Layer 4 architectural
independence, per CLAUDE.md. `advance()`'s Step 7a gains a 7a-cont block:
after a burden discharges, any `active`-state sibling in the same
`any_discharged` group (matched across all holders, not just the
discharging actor) transitions to `superseded`, logged in `effects`.
Deliberately scoped to `active` siblings only, not `pending` (masked) —
logged as an open gap in `docs/CONCEPTS_INDEX.md` rather than guessed at,
since no scenario exercises that combination.
`TokenInstance.state`'s comment now flags that `'superseded'` has two
unrelated live meanings (Permit-superseded-by-Embargo via
`revoke_authorization()`, AM-31; and this one) so a future reader isn't
confused. `check_live_violations()` needed no change — confirmed directly
(not assumed): its existing `tok.state != "active"` guard already
excludes `superseded` burdens.

**Confirmed directly**, via a standalone two-actor/two-Commitment minimal
spec (not a change to any real scenario file):
- Actor A discharging `burdenA` supersedes Actor B's `burdenB` sibling;
  `effects` names both.
- The superseded sibling never violates via `check_live_violations()`,
  even 1000 ticks past its deadline.
- A structurally identical `all_discharged` control group is unaffected
  (regression guard: the P6b-equivalent must not fire there).
- A sibling already `discharged` (not `active`) when its peer discharges
  is left alone, not overwritten to `superseded`.

**Files changed:** `toolchain/el_engine.py` (`TokenInstance.state`
comment; new `_build_group_index()`/`_build_any_discharged_groups()`;
`advance()`'s 7a-cont block; `check_live_violations()` confirmation
comment), `tests/test_any_discharged_sibling_supersession.py` (new, 4
tests). Full suite: 193 pre-existing tests pass unchanged, plus 4 new
(197 total). `docs/CONCEPTS_INDEX.md` gains the masked-sibling gap note
and a V-16a/V-16b stale-status correction surfaced during the same
ground-truth pass.

---

## AM-58 (2026-08-22) — `specialist_pool_scenario.el`: first named any_discharged/SUPERSEDED demonstration scenario

**Not a grammar/domain/parser change** — a named scenario + test file,
logged retroactively (2026-09-16) per the same convention later made
explicit by AM-63/AM-75: a scenario-level demonstration that exercises
an existing mechanism under a real name gets its own entry here,
cross-referenced from the scenario file's own header and from
`tests/test_specialist_pool_scenario.py`'s docstring, rather than a
grammar/domain/parser diff.

**What it demonstrates:** `OnCallConsultCommunity` governs two
equally-eligible specialists (`SpecialistA`/`SpecialistB`) over an
`any_discharged(consultResponseGroup)` objective, both members
Commitment-backed (`specialistAResponseCommitment`/
`specialistBResponseCommitment`, satisfying V-16a). First named,
standalone scenario exercising the `any_discharged`/`SUPERSEDED`
collective-obligation mechanism end-to-end — Layer 4 verifier
(`el_kripke.py`'s P6b, since AM-27) and Layer 3 live engine
(`el_engine.py`, since AM-57) — rather than re-testing the mechanism's
own logic (that remains AM-57's job,
`tests/test_any_discharged_sibling_supersession.py`). Two checks match
the scenario file's own header comment: Q1, `EF(objective_satisfied:
OnCallConsultCommunity)` holds — either specialist discharging
satisfies the community objective; Q2, discharging
`specialistAResponseBurden` via the live engine supersedes
`specialistBResponseBurden` (AM-57's mechanism, exercised here under a
real scenario name for the first time).

**Files changed:** `scenarios/specialist_pool/specialist_pool_scenario.el`
(new), `tests/test_specialist_pool_scenario.py` (new, 3 tests).

Commit: `aa26e3a`.

---

## AM-59 (2026-08-23) — `ai_vendor_probe.el`: first named demonstration of AM-40's role-based Domain syntax and the AIVendor two-construct shape

**Not a grammar/domain/parser change** — a named scenario + test file,
logged retroactively (2026-09-16), same convention as AM-58 above.

**What it demonstrates:** first named scenario exercising AM-40's
role-based Domain syntax (`controlling_role`/`controlled_role`/
`DomainRoleFiller` with `via=[Federation]`) and the AIVendor
two-construct shape identified as a gap 2026-07-09
(`docs/CONCEPTS_INDEX.md`): peer contract federations for the
pre-deployment provider duty, one shared subordination domain for the
in-use processor duty. Deliberately structural only — no burdens,
commitments, or Kripke verification, since the AIVendor gap is about
provenance and role correctness, not discharge semantics. Confirms
parse/validate cleanliness (V-NEW-21 passes using only the new
role-based syntax, no `controlling_object`/`controlled_object`) and
that each deployed agent's `via` resolves to the correct, distinct
`Federation` against the real parsed model — the actual N-peer
provenance claim, not just a parse-success check.

**Files changed:** `scenarios/vendor/ai_vendor_probe.el` (new),
`tests/test_ai_vendor_probe_scenario.py` (new, 2 tests),
`docs/CONCEPTS_INDEX.md` (20 lines — AIVendor gap update).

Commit: `53e9ba1`.

---

## AM-60 (2026-08-24) — `Evaluation` structured form + `claimable` `TokenState` (grammar/parser/domain layer)

**Problem:** delegation claiming (DN_003) needs a burden offered to an
`any_discharged` pool to sit in a distinct, authorable "offered, not yet
accepted" state, and needs the holder's accept/reject decision to be a
real, engine-checkable structure rather than free text. Neither existed:
`TokenState` only authored `active`/`pending`, and `Evaluation` (§6.6.7)
was target/result STRING/STRING only — confirmed decorative, with zero
runtime handlers (grep, `el_engine.py`/`el_reasoner.py`).

**What changed:** `grammar/v2/el_grammar.tx` — `TokenState` gains
`claimable` (authorable; the runtime-only outcome state `lapsed`,
AM-61/AM-62, is deliberately NOT added here — outcome states stay
absent from the author-facing enum, matching `discharged`/`violated`/
`superseded`'s existing precedent). `Evaluation` gains a structured
alternative: `of_target` may resolve `EvaluationTarget` to either
`target_token=[DeonticToken]` or the pre-existing `target_text=STRING`;
`result` may resolve `EvaluationResult` to either
`result_code=AcceptabilityResult` (`accept`/`reject`) or the
pre-existing `result_text=STRING`. Backward compatible: the free-text
form still parses and stays fully inert.

`toolchain/el_domain.py`'s `Evaluation` dataclass gains `target_token`/
`result_code` fields alongside the existing flat `target`/`result`
strings. `toolchain/el_parser.py` gains `process_evaluation` (**P12**),
registered in `_build_metamodel`, which flattens the structured match
rules into the flat fields: when the structured form is used,
`target`/`result` are still populated (backward compatibility for any
existing free-text consumer) and `target_token`/`result_code` are set;
when the free-text form is used, `target_token`/`result_code` stay
`None`, which is exactly what the engine's claim logic (AM-62) and the
Kripke layer's claim-evaluation lookup (AM-61) check to distinguish a
live claim decision from an inert credit-rating-style evaluation.

**Confirmed directly:** `erequesting_claiming_scenario.el`'s structured
`evaluation providerAAcceptsReferral { of_target: providerAClaimBurden
result: accept }` resolves to `target_token.name ==
'providerAClaimBurden'` and `result_code == 'accept'`, with `target`/
`result` still populated as flat strings
(`test_evaluation_structured_form_resolves`).

**Files changed:** `grammar/v2/el_grammar.tx`, `toolchain/el_domain.py`,
`toolchain/el_parser.py`. ISO grounding: §6.6.6 (Delegation), §6.6.7
(Evaluation), Annex B.1.9.6 (acceptance-as-evaluation worked example).
Design source: `docs/design_notes/DN_003_delegation_claiming_evaluation.md`.

---

## AM-61 (2026-08-24) — Kripke layer: `CLAIMABLE`/`LAPSED` `ObligationState` and the C1 claim transition

**Problem:** with AM-60's grammar in place, the Layer 4 verifier needed
its own representation of "offered to a pool, not yet claimed" and
"peer claimed first" — distinct from the existing `PENDING`/`WAITING`
(triggered_by-gated) and `SUPERSEDED` (peer discharged first) states —
plus a transition rule for the claim itself.

**What changed:** `toolchain/el_kripke.py` gains
`ObligationState.CLAIMABLE` and `ObligationState.LAPSED`. World
construction: a new `_build_claim_evaluations()` helper maps each
`DeonticToken` name to its structured accept/reject `Evaluation`
objects; an `any_discharged` group's members start `CLAIMABLE` (instead
of `PENDING`/`WAITING`) only if at least one member has an associated
structured Evaluation — ordinary `any_discharged` groups with no
Evaluations (e.g. `specialist_pool_scenario.el`) are unaffected, keeping
this change zero-impact on existing scenarios. `successors()` gains
**Rule C1 (CLAIM)**: for a `CLAIMABLE` obligation held by an `ACTIVE`
actor with a matching accept Evaluation, one edge transitions that
obligation `CLAIMABLE → PENDING` (after which existing T1/P6b logic
applies unchanged) while every other still-`CLAIMABLE` sibling in the
same `any_discharged` group transitions to `LAPSED`. A reject
Evaluation is deliberately not wired into any transition — the
obligation simply has no outgoing C1 edge and stays `CLAIMABLE`.
`CLAIMABLE`/`LAPSED` are both excluded from `utility()`'s numerator/
denominator (not yet in play / non-completion is not a failure,
respectively) and scored neutral (`CLAIMABLE`) or skipped without
setting `any_superseded` (`LAPSED`) in `utility_for_objective()` —
`LAPSED` is deliberately not treated as an objective-achieving
supersession, since the claiming peer's own burden carries that.
`_build_propositions()` emits `claimable:<token>`/`lapsed:<token>`
labels.

**Confirmed directly:** `erequesting_claiming_scenario.el`'s Kripke model —
both pool members start `CLAIMABLE`
(`test_both_pool_members_start_claimable`);
`EF(objective_satisfied:DiagnosticReferralPoolCommunity)` holds (Q1);
`EF(discharged:providerAClaimBurden)` holds — full claim→discharge path
reachable (Qc); `EF(lapsed:providerBClaimBurden)` holds — sibling
correctly lapses when a peer claims first (Ql).

**Files changed:** `toolchain/el_kripke.py`. Design source:
`docs/design_notes/DN_003_delegation_claiming_evaluation.md`.

---

## AM-62 (2026-08-24) — Live engine: `claimable → active` activation and sibling lapse

**Problem:** parity with AM-61 on the live-runtime side, mirroring
AM-57's P6b/live-engine parity pattern. Empirically, the pre-AM-62 live
engine had no `claimable`/`pending → active` activation step at all —
broader than "sibling supersession is skipped" — acting on a burden
that starts masked was a silent, effect-free no-op
(`outcome: "ok"`, `effects: ()`), confirmed directly against
`erequesting_claiming_scenario.el` before this change landed.

**What changed:** `toolchain/el_engine.py`'s `TokenInstance.state`
docstring/comment documents the two new state strings `'claimable'`/
`'lapsed'`, and notes `'lapsed'` is distinct from the two existing
`'superseded'` meanings (AM-31 permit-superseded-by-embargo; AM-57
any_discharged sibling supersession-by-discharge) — a lapsed sibling
made no decision and was overtaken by a peer *claiming* first, not by a
peer *discharging*. `advance()` gains: a claimability check (actor
holds the token, `state == 'claimable'`, `for_action` matches, and a
structured accept Evaluation exists for this actor against this token —
a reject Evaluation or no Evaluation is a no-op, confirmed empirically
leaving the burden `claimable`); **7a-claim**, which transitions a
claimed token `claimable → active` (claiming activates a masked,
pool-offered burden — it does not discharge it; a later `advance()`
call discharges the now-`active` token via the existing 7a discharge
logic, unchanged); and **7a-claim-cont**, which mirrors AM-57's
sibling-supersession pattern but is triggered by CLAIM rather than
DISCHARGE and marks siblings `lapsed` rather than `superseded`.

**Confirmed directly:** claiming `providerAClaimBurden` via
`DiagnosticProviderA`'s accept Evaluation activates it
(`claimable → active`) and lapses `providerBClaimBurden`
(`claimable → lapsed`) in the same `advance()` call, with both effects
named in `record.effects`
(`test_live_claim_activates_holder_and_lapses_sibling`); a second
`advance()` call then discharges the now-active burden normally via the
existing pathway, leaving the lapsed sibling untouched
(`test_live_claimed_burden_then_discharges_normally`); flipping the
Evaluation to `reject` leaves both burdens `claimable`, with
`record.effects == ()` — a deliberate no-op, not an error
(`test_live_reject_evaluation_is_a_no_op`).

**Files changed:** `toolchain/el_engine.py`. Design source:
`docs/design_notes/DN_003_delegation_claiming_evaluation.md`.

---

## AM-63 (2026-08-24) — `erequesting_claiming_scenario.el`: first named pool-claiming demonstration scenario

**Not a grammar/domain/parser change** — a named scenario + test file,
logged per the same convention already established for AM-58
(`specialist_pool_scenario.el`) and AM-59 (`ai_vendor_probe.el`): this
entry documents the scenario's role as the accept-side demonstration of
AM-60–62, cross-referenced from the scenario file's own header and from
`tests/test_erequesting_claiming_scenario.py`'s docstring rather than
requiring a separate log entry format.

**What it demonstrates:** `DiagnosticReferralPoolCommunity` governs two
equally-eligible diagnostic providers (`DiagnosticProviderA`/`B`) over
an `any_discharged(referralClaimGroup)` objective. Both providers'
claim burdens start `claimable`; `DiagnosticProviderA`'s structured
accept `Evaluation` claims `providerAClaimBurden`, activating it and
lapsing `providerBClaimBurden` — the accept-side sibling of
`specialist_pool_scenario.el`'s discharge-side `any_discharged`/
`SUPERSEDED` demonstration (AM-58).

**Files changed:** `scenarios/erequesting_claiming/erequesting_claiming_scenario.el`,
`tests/test_erequesting_claiming_scenario.py` (new, 9 tests: parser
structured-form resolution, both pool members start `CLAIMABLE`, Q1/Qc/Ql
Kripke reachability, live claim+lapse, live claimed-then-discharge, live
reject no-op). Full suite: 203 pre-existing tests pass unchanged, plus 9
new (212 total). Design source:
`docs/design_notes/DN_003_delegation_claiming_evaluation.md`.

---

## AM-73 (2026-08-30) — R38/R38a/R38b: `MedicationRequest` → Commitment + Burden, `MedicationDispense` → fulfilment/discharge (touchpoint 5)

**Status:** CONFIRMED (2026-08-30).

**Problem:** touchpoint 5 (medicines management) of the ConnectedCare
demonstration scenario had no FHIR mapping — pharmacy retrieval of an
ePrescription, eCDS interaction/duplication checks, and dispensing were
unmapped. Needed a `MedicationRequest`/`MedicationDispense` pipeline
mirroring the R05-R08 `ServiceRequest` pipeline and the R37a/R37b
static/live split already established for `Procedure`.

**Design decision — one rule number covers the whole
`MedicationRequest` mapping job**, mirroring the R37a/R37b precedent of
no bare intermediate number for a single resource type's mapping. R38a
= static provenance (mirrors R37a exactly — same `TokenState` grammar
exclusion, `discharged` not authorable). R38b = live bridge (mirrors
R37b exactly — dynamic `burden_name` derivation, no fixed-name
constant, `KeyError` caught inside the handler).

**What changed:**
- `_map_medication_request()` (`toolchain/fhir_mapper.py`) — mirrors
  `_map_service_request()` exactly, including the AM-72 holds-clause
  pattern. `.requester` resolved via
  `_resolve_commitment_accountable_party()` (AM-71) unchanged —
  confirmed against the real AU `au-medicationrequest` profile that its
  target types (`Practitioner|PractitionerRole|Organization|Patient|
  RelatedPerson|Device`) are identical to `ServiceRequest.requester`'s,
  `PractitionerRole` included.
- `handle_medication_dispense_event()` (`toolchain/fhir_event_handler.py`)
  — structurally identical to `handle_procedure_event()`. Confirmed
  against the real `au-medicationdispense` profile: the linking field
  is `.authorizingPrescription`, not `.basedOn`; `medicationdispense-status`
  is its own value set, distinct from `Procedure`'s `event-status` —
  `declined` is this enum's explicit negative.
- `POST /fhir/medication-dispense-events` (`toolchain/el_api.py`) —
  mirrors `procedure_event`.
- No deadline mapping — `dispenseRequest.validityPeriod` is a different
  concept (the repeat-supply authorisation window), not an SLA
  deadline; same accepted gap as R08.

**Standard reference(s):** §6.6 (Commitment), §6.4.3 (Burden) — same as
R05-R08/R37a/R37b; no new grammar construct introduced.

**Empirical verification:** `tests/fixtures/medication_dispense_bundle.json`
plus 3 new test files (mapper/static, handler-probe, endpoint-integration),
including a live `Runtime.build_from_spec()` check confirming a real
`TokenInstance` exists, not just plausible generated text. Full suite:
308/308 passing (288 baseline + 6 mapper + 8 handler + 6 endpoint).

**New open finding logged, not fixed here:** the eCDS
interaction/duplication-check accountability question (who is
responsible for catching a cross-plan medication conflict) —
deliberately deferred as a genuinely novel design question, not a
mechanical mapping. See `docs/CONCEPTS_INDEX.md`, "eCDS
interaction/duplication-check accountability" (OPEN FINDING,
2026-08-30).

**Files changed:** `toolchain/fhir_mapper.py`,
`toolchain/fhir_event_handler.py`, `toolchain/el_api.py`,
`toolchain/fhir_mapping_table.md` (§3.15),
`tests/fixtures/medication_dispense_bundle.json`,
`tests/test_fhir_mapper_r38_medication_request.py`,
`tests/test_fhir_medication_dispense_event_handler.py`,
`tests/test_fhir_medication_dispense_event_endpoint.py`,
`docs/CONCEPTS_INDEX.md`.

Commit: `2db41f9`.

---

## AM-74 (2026-08-30) — R39: `Observation` (progress/PROM score) → Burden + `violation_response` escalation (touchpoint 6)

**Status:** CONFIRMED (2026-08-30).

**Problem:** wires the first real escalation logic into the FHIR
mapper, addressing DN_007's originally-flagged gap ("no escalation
logic appears anywhere, across all six ConnectedCare diagrams"). An
`Observation` representing a progress/PROM score needed to create a
Burden with a genuine clinical-governance deadline and, if unreviewed,
escalate to the GP practice via the existing
`violation_response`/`fire_violation_responses()` mechanism.

**Design decisions:**
- Deadline (`7 days`) is a genuine governance-policy constant, layered
  on top of the data — not derived from any FHIR field (no AU-specific
  `Observation` profile exists; grounded against the base FHIR R4 core
  package, `hl7.fhir.r4.core#4.0.1`, confirmed via a full search of the
  cached AU package directory).
- Holder resolution: `.basedOn` → `ServiceRequest` → that
  `ServiceRequest`'s own already-resolved `Commitment.by` (reused, not
  recomputed) — not `.performer` directly. The base R4 profile confirms
  `.performer`'s target types include `Patient` (a self-reported PROM
  commonly has the patient as performer), which would incorrectly
  obligate the patient to review their own score; `.performer` is used
  only as a fallback when `.basedOn` doesn't resolve.
- `discharge_mode` must stay `eventual`, never `strict` — confirmed via
  `check_live_violations()` that it explicitly skips every `strict`
  burden, which would make a strict review burden permanently
  non-violatable.
- `ViolationResponse`'s shape grounded against the real working example
  already in `referral_scenario.el` (`violation_response
  referralNoResponseViolation`) — `creates_burden` names an ungranted
  burden (no `holds` clause anywhere); the engine grants it dynamically
  only when the violation actually fires.
- One rule number, no static/live split like R37/R38 — no new live
  bridge needed; `check_live_violations()`/`fire_violation_responses()`
  are already-existing, generic engine functions operating over any
  declared burden/`ViolationResponse`.
- `escalate_to` resolves to the accountable party of whichever
  `ServiceRequest` has the earliest `.authoredOn` in the bundle (the
  referral that started the patient's journey), computed once per
  bundle via a new `_find_earliest_referral_accountable_party()`
  helper.

**What changed** (`toolchain/fhir_mapper.py`): `ELViolationResponse`
dataclass, `_map_observation()`, `_find_earliest_referral_accountable_party()`,
`_render_violation_response()`, wired into `_render_el()` after
Declarations (`ViolationResponse` confirmed top-level via
`grammar/v2/el_grammar.tx:73`, sibling to `Commitment`/`Authorization`).

**Standard reference(s):** §6.6 (Commitment), §6.4.3 (Burden),
§6.3.8/§7.8.6/§7.8.6 NOTE 2 (ViolationResponse — see AM-17) — no new
grammar construct introduced.

**Empirical verification:** `tests/fixtures/observation_progress_score_bundle.json`
plus `tests/test_fhir_mapper_r39_observation_review.py` — 8 tests:
`.basedOn` priority over `.performer`, `.performer` fallback, the
degenerate skip case, `violation_response` correctness,
escalation-burden shape, full parse+validate, and the real proof
(advance clock past the 56-tick deadline, `check_live_violations()`
transitions to `violated`, `fire_violation_responses()` grants the
escalation burden and logs the GP notification). Full suite: 321/321
passing (313 baseline + 8 new).

**Edge case discovered, not fixed here:** when neither `.basedOn` nor
`.performer` resolves to anything at all, naively emitting
`commitment.by:` with an empty string would be a textX **parse**
failure (a mandatory grammar cross-reference), not just a validator
warning — a stricter failure mode than AM-71/AM-72's "reference exists
but doesn't resolve" tiers. Guarded via an early-return skipping the
`Observation` entirely in this case. The same latent gap likely exists
in R05/R38 (a `ServiceRequest`/`MedicationRequest` with a completely
absent `.requester`) — not fixed here, logged separately as its own
finding. See `docs/CONCEPTS_INDEX.md`, "An accountable-party reference
resolving to an empty string would crash the parser..." (OPEN FINDING,
2026-08-30).

**Files changed:** `toolchain/fhir_mapper.py`,
`toolchain/fhir_mapping_table.md` (§3.16),
`tests/fixtures/observation_progress_score_bundle.json`,
`tests/test_fhir_mapper_r39_observation_review.py`,
`docs/CONCEPTS_INDEX.md`.

Commit: `2e76380`.

---

## AM-75 (2026-09-03) — reviewNonResponseAndDetermineNextStepsBurden: real §8.4 GP-side notification consumer for escalate_to

**Not a grammar/domain/parser change** — a scenario + builder-level
addition, logged per AM-63's actual format. Note: AM-63's own text
claims this logging convention was "already established for AM-58...
and AM-59" — checked directly (2026-09-16), neither had a dedicated
entry anywhere in this file at the time AM-63 was written, only
passing references inside AM-63's own text. **Fixed as of 2026-09-16:**
both now have dedicated entries above (AM-58, AM-59), and the
AM-73/AM-74 logging gap referenced below has also been closed — see
those entries.

**What it fixes:** `referral_scenario.el`'s `escalate_to: GPPractice`
(on `referralNoResponseViolation`) previously produced only an
informational effects-log line — no state change on `GPPractice`, so it
did not meet X.902 §8.4's own definition of event notification
("receipt of the notification changes the state of objects not
participating in the original action"). This amendment gives
`GPPractice` a real, live consumer: `reviewNonResponseAndDetermineNextStepsBurden`,
granted directly via `effect create ... to gpPracticeOversightRole` on
`notify_gp_of_non_response` (not `emits`/`triggered_by` — that
mechanism was tried first, same day, and reverted: it requires a
pre-existing `pending` token that nothing in the live builder ever
granted). Deliberately cause-agnostic (the model doesn't capture *why*
`referralResponseBurden` was violated) and deliberately NOT a member of
`referralBurdenGroup` (would block ordinary, non-violated episodes from
ever concluding). Single-hop escalation only — no further
`ViolationResponse` chains onto it.

**Two real gaps found and fixed empirically, same day, neither caught
by parse/validate or the full suite alone:**
1. `emits`/`triggered_by` (the first mechanism tried) never actually
   fires in the live builder — reverted in favour of `effect create`.
2. `GPPracticeCommunity`'s new oversight role initially collided in
   name (`practiceOversightRole`) with `SpecialistPracticeCommunity`'s
   existing role of the same name — `effect create ... to <Role>`
   resolves by bare role-name string with no community scoping, so the
   first fix granted the burden to *both* practices. Renamed to
   `gpPracticeOversightRole`; logged as a standing constraint on future
   scenario design (role names used as `effect create` targets must be
   unique across the whole spec, not just within their own community).

**Files changed:** `scenarios/referral/referral_scenario.el` (new
burden, new role, new commitment, action wiring, header comment),
`toolchain/el_api.py` (GPPractice enrolled into
`gpPracticeOversightRole`), `tests/test_referral_event_triggers.py` (2
new tests: structural non-membership in `referralBurdenGroup`, and the
real end-to-end escalation-path proof via genuine
`check_live_violations()`), `tests/test_gp_escalation_notification_chain.py`
(new, general `emits`/`triggered_by` mechanism coverage, decoupled from
this scenario's actual mechanism). Full suite: 325/325 passing. Design/
finding detail in `docs/CONCEPTS_INDEX.md`'s same-day correction and
the `effect create` community-scoping finding.

Commits: `d3899b2` (initial), `7041870` (correction: effect create,
role rename, builder fix).

---

## AM-76 (2026-09-04) — Extend `discharge_mode: strict` live enforcement beyond `advance_clock()` to `advance()`, `revoke_authorization()`, `reinstate_authorization()`, `discharge_burden()`, `fire_event()`

**Status:** IMPLEMENTED (2026-09-04).

**Problem:** closes the remainder of the `discharge_mode: strict`
OPEN FINDING logged in `docs/CONCEPTS_INDEX.md` (2026-08-20), which
AM-49 (2026-08-21) closed only partially. AM-49's own entry scoped
itself deliberately narrowly: *"`advance()` itself is unaffected —
this closes the gap only for the 'let time pass' primitive... Whether
`advance()` needs an analogous guard for unrelated actions while a
strict burden sits actionable is a separate question, not addressed
here."* A direct grep of `el_engine.py` (design note DN_012, chat-level
handoff, 2026-09-04) confirmed five functions advance
`WorldState.tick` unconditionally, with zero branch on
`discharge_mode` anywhere in their bodies: `advance()`,
`revoke_authorization()`, `reinstate_authorization()`,
`discharge_burden()`, `fire_event()`. Net effect: an actor could call
any of these — on an action, authorization, or event completely
unrelated to an outstanding `strict` Burden — repeatedly, while that
Burden sat active and actionable, and nothing blocked it. This was the
exact loophole the 2026-08-20 finding described; AM-49 closed it only
for the explicit `advance_clock()` no-op primitive.
(`check_live_violations()`/`fire_violation_responses()` were checked
and are out of scope — both already exclude `strict` burdens by design
and only advance tick as a side effect of an already-earned consequence
on an `eventual` burden, mirroring Kripke's *unconditional* T2 rule
rather than the gated T3 tick-rule.)

**Design decision — global, not per-actor:** the guard checks
`discharge_mode: strict` Burdens system-wide, exactly like AM-49's
existing `_strict_actionable_burdens()` — not scoped to the calling
actor. This mirrors Kripke Rule T3's own global condition ("NO PENDING
strict obligation has an ACTIVE holder" — not "no PENDING strict
obligation **held by this actor**"). Consequence, confirmed and
accepted: if any `strict` Burden is outstanding anywhere in the
system, no actor can take any action that doesn't discharge it — not
just its holder.

**What changed** (`toolchain/el_engine.py`):
- Two new shared helpers, adjacent to AM-49's existing
  `_strict_actionable_burdens()`/`_list_and()`:
  - `_unaddressed_strict_burdens(state, addressed=None)` —
    `_strict_actionable_burdens(state)` minus any token name in
    `addressed`, i.e. the strict burdens a given call would still
    leave outstanding if it proceeded.
  - `_strict_block_reason(blocking, tail)` — the reason-string builder
    extracted from `advance_clock()`'s AM-49 logic, parameterised by a
    `tail` phrase, so every strict-mode guard reads identically.
- `advance_clock()` refactored to call these two instead of its
  inline duplicate of the same logic. Wording unchanged (tail:
  `"before time can advance"`), so the three existing AM-49 tests in
  `test_advance_clock.py` kept passing unmodified.
- Five new call-site guards, each returning `outcome="blocked"` via
  the existing `_blocked()`/`TransitionRecord` convention (never
  raises for this case):
  - `advance()` — new Step 3.5, inserted after `dischargeable` is
    computed (Step 3) and before Preconditions (Step 4). Exempts any
    burden this same call would discharge (`addressed=set(dischargeable)`),
    since `advance()` on the actionable burden itself is exactly the
    thing that must remain possible. Tail: `"before this action can
    proceed"`.
  - `revoke_authorization()` — guard inserted after the existing
    `KeyError` checks (bad `authorization_name`, missing embargo),
    before any token mutation. Tail: `"before the authorization can be
    revoked"`.
  - `reinstate_authorization()` — same placement/pattern. Tail:
    `"before the authorization can be reinstated"`.
  - `discharge_burden(burden_name)` — guard inserted right after
    `holder` is resolved, before the token-transition logic. Exempts
    the burden being discharged itself (`addressed={burden_name}`) —
    discharging the blocking burden is always allowed. Tail: `"before
    another burden can be discharged"`.
  - `fire_event()` — guard inserted right after `tick = state.tick`,
    before `_activate_triggered_tokens()`. Tail: `"before the event
    can be fired"`.

**Standard reference(s):** none new — same as AM-49: §6.4.3 (Burden),
§7.8.7 (token state).

**Empirical verification:** live spot-check against a fresh
`_build_referral_runtime()` (which carries `referralInitiationBurden`,
`discharge_mode: strict`, held by `GPClinician`, active and
undischarged from construction) confirmed all five guards fire with
the expected reason string, e.g. `advance()` →
`"strict burden 'referralInitiationBurden' (held by 'GPClinician') is
actionable and must be discharged before this action can proceed"`,
and the parallel wording for `revoke_authorization()`,
`reinstate_authorization()`, `fire_event()`; confirmed again against a
fresh `_build_gp_referral_runtime()` for `revoke_authorization()`.

Landing this surfaced that the global-scope decision collides broadly
with the existing regression suite: 17 pre-existing tests across 6
files called `revoke_authorization()`/`reinstate_authorization()`/
`fire_event()` (via `advance()`'s dependency on it too) against
`referral_scenario.el`/`gp_referral_scenario.el` fixtures that start
with `referralInitiationBurden` outstanding — unrelated to what each
test actually exercised, but now correctly blocked by the global
guard. Fixed in two follow-on commits: 9 tests plus a structurally
identical reinstate-endpoint pair (11 total) fixed by discharging
`referralInitiationBurden` in fixture setup before the behaviour under
test (`b0083ac`); `test_fhir_event_handler.py`'s 4 affected tests
fixed the same way, plus one new test,
`test_consent_inactive_revocation_blocked_while_strict_burden_outstanding`,
added to assert the blocked-consent-revocation behaviour as documented
behaviour in its own right rather than leaving it as an incidental
side effect (`870ae0e`). One test,
`test_revocation_endpoint.py::test_revocation_supersedes_only_authorization_permit`
(`gp_referral_scenario.el`, superseded/historical scenario), remains
unfixed as of this entry — tracked separately, fix pending in the same
pass. Full suite as of this entry: 325 passed, 1 failed (that one
known, tracked case).

**Known follow-up, not fixed here:** landing this guard made a
pre-existing latent bug in `fhir_event_handler.py` observable for the
first time — `handle_consent_event()`'s `status == "inactive"` branch
unconditionally sets `action_taken="revoked"` regardless of whether
the underlying `revoke_authorization()` call actually succeeded or was
blocked (invisible before AM-76, since `revoke_authorization()` never
used to block). Logged as its own OPEN FINDING in
`docs/CONCEPTS_INDEX.md` (2026-09-04), cross-referencing this entry,
tentatively **AM-77**. Not fixed in this pass.

**Files changed:** `toolchain/el_engine.py`
(`_unaddressed_strict_burdens()`, `_strict_block_reason()`,
`advance_clock()` refactored to use them, guards added to `advance()`,
`revoke_authorization()`, `reinstate_authorization()`,
`discharge_burden()`, `fire_event()`); `tests/test_referral_ai_examination_permit_gate.py`,
`tests/test_referral_kripke_t6_permit_gate.py`,
`tests/test_hybrid_t5_exercise_embargo_guard.py`,
`tests/test_referral_revocation.py`, `tests/test_reinstate_endpoint.py`,
`tests/test_revocation_endpoint.py`, `tests/test_fhir_event_handler.py`
(fixture-setup fixes across all seven, one new test in the last);
`docs/CONCEPTS_INDEX.md` (AM-77 latent-gap finding).

Commits: `a916e6f` (engine guard), `b0083ac` (Bucket A + reinstate-pair
fixture fixes), `870ae0e` (Bucket B fixture fixes + new test +
CONCEPTS_INDEX entry).

## AM-78 (2026-09-08) — Loosen AM-76's strict-burden guard to T3's actual scope; close `conductAIExamination`'s missing referral-active precondition

**Status:** IMPLEMENTED (2026-09-08).

**Problem:** AM-76 made `advance()`/`discharge_burden()`/
`revoke_authorization()`/`reinstate_authorization()`/`fire_event()`
block whenever *any* `discharge_mode: strict` Burden is outstanding and
the call doesn't discharge *that specific* burden. Confirmed directly
in `build_kripke_from_runtime()`'s BFS loop: T1/T6 discharge-edge
generation has no reference to any strict-burden guard at all — only
the T3 tick-edge ("let time pass, nothing happens") is ever suppressed.
AM-76 was stricter than the verifier it was meant to mirror: T1
discharge edges for *other*, unrelated obligations were always meant to
remain unconditionally available. Concretely, with
`referralInitiationBurden` (strict) outstanding, the live engine
incorrectly blocked `conductAIExamination` from discharging
`aiExaminationBurden` — a real, unrelated discharge, not a no-op — even
though the verifier's own T1/T3 rules say this should be fine. Design
note: DN_013 (chat-level, 2026-09-08).

Loosening the guard alone would have let `conductAIExamination` succeed
immediately after Reset, before any referral exists (no precondition
tied it to referral state) — worse to demo than the pre-AM-78 block. So
this amendment closes that real domain gap in the same pass, at the
grammar layer where it belongs, rather than leaving the loosened guard
to expose it silently.

**Design decision — don't touch the verifier:** `el_kripke.py`'s T1/T3
rules are unchanged; they were always correct. This amendment brings
the live engine back toward their actual scope instead of mirroring
AM-76's over-tight reading into the verifier (rejected: doing so would
make one stuck strict burden in one episode block *all* actions in
every other concurrent episode too, system-wide — the guard has no
community/episode scoping).

**What changed** (`toolchain/el_engine.py`) — Part A:
- **New rule:** a `discharge_mode: strict` Burden blocks a call only
  when that call makes **zero discharge progress at all** — not
  "doesn't address *this specific* strict burden."
- `advance()` — Step 3.5 guard changed from
  `_unaddressed_strict_burdens(state, addressed=set(dischargeable))` to
  a plain emptiness check: `if not dischargeable:` before even
  computing `_strict_actionable_burdens(state)`. Any call that
  discharges *something* — even a burden unrelated to the outstanding
  strict one — now proceeds.
- `discharge_burden(name)` — **AM-76's guard removed entirely.** A
  successful call to this function always discharges the named burden
  by construction, so it can never be a no-progress action; there was
  no scenario where the guard was ever correctly blocking here.
- `revoke_authorization()`, `reinstate_authorization()`, `fire_event()`
  — **unchanged.** These three never discharge anything
  (`discharged=()` always), so unconditional blocking while any strict
  burden is outstanding remains correct — this was the part of AM-76
  that was always right.
- `_strict_actionable_burdens()`, `_unaddressed_strict_burdens()`,
  `_strict_block_reason()` (AM-49/AM-76 helpers) — unchanged; the three
  functions above still call `_unaddressed_strict_burdens(state)` with
  no `addressed` argument, exactly as before.

**What changed** (`scenarios/referral/referral_scenario.el`) — Part B:
- `conductAIExamination` gained a second `precondition:` string,
  `"Referral must be active for AI examination to proceed"`, ahead of
  its existing `"AI agent must hold
  patientRecordAccessPermitByAuthorization"` precondition — matching
  the exact two-precondition pattern already used by
  `scheduleAssessment`/`provideHandover`. `ActionBodyItem`'s
  `items*=ActionBodyItem` already supports multiple `PreconditionDecl`
  per action (no grammar change needed); `advance()`'s Step 4 checks
  each in order and blocks on the first unsatisfied one.

**UI checkbox surface — checked, not generalized (see
`docs/CONCEPTS_INDEX.md`, 2026-09-08 finding):** `el_api.py` does not
expose `Action.preconditions` on any response model, so the
coordination UI's existing per-action precondition checkboxes
(`scheduleAssessment`/`provideHandover`) must already be hardcoded, not
generic. The new `conductAIExamination` precondition is enforced
correctly regardless (it flows through `advance()`'s existing generic
Step 4 fact-lookup) but will need a manual addition to the UI's
hardcoded list in `computable-governance-ui` before it gets a checkbox
there. Logged as a separate, smaller follow-up rather than folded into
this amendment.

**Standard reference(s):** none new — same as AM-49/AM-76: §6.4.3
(Burden), §7.8.7 (token state).

**Empirical verification:** `tests/test_am78_strict_guard_loosening.py`
(new) — `conductAIExamination` now discharges `aiExaminationBurden`
against a fresh `_build_referral_runtime()` with
`referralInitiationBurden` left outstanding and undischarged (previously
blocked under AM-76); `access_patient_clinical_records` (discharges no
burden) remains correctly blocked citing `referralInitiationBurden`;
`discharge_burden("aiExaminationBurden")` now succeeds unconditionally
under the same outstanding-strict-burden condition.
`tests/test_referral_ai_examination_permit_gate.py` — new test
confirms `conductAIExamination` blocks on the new precondition string
when a caller supplies only the pre-AM-78 facts shape, and succeeds
once both precondition facts are supplied. Full suite re-run: 329
passed, 1 xfailed (the pre-existing, unrelated `gp_referral_scenario.el`
xfail) — no regressions; AM-76's own fixture-setup `discharge_burden("
referralInitiationBurden")` calls across the existing suite were left
in place unmodified (now harmless-but-unnecessary in some cases, per
DN_013 §5 — not scope-creeped into cleanup this pass).

**Files changed:** `toolchain/el_engine.py` (`advance()` Step 3.5,
`discharge_burden()` guard removed); `scenarios/referral/referral_scenario.el`
(`conductAIExamination` second precondition); `tests/test_am78_strict_guard_loosening.py`
(new); `tests/test_referral_ai_examination_permit_gate.py` (new test +
`FACTS` updated for the new precondition); `tests/test_referral_event_triggers.py`
(happy-path facts updated for the new precondition); `docs/CONCEPTS_INDEX.md`
(AM-76 cross-reference back-filled with the AM-49→AM-76→AM-78 resolution
chain; new UI-checkbox-hardcoding OPEN FINDING).

## AM-79 (2026-09-09) — Per-world Permit/Embargo state in `World`; new Rules T7 (Authorization Revoke) / T8 (Authorization Reinstate) in `build_kripke_from_runtime()`

**Status:** IMPLEMENTED (2026-09-09).

**Problem:** `World` (the Kripke model's core frozen dataclass) tracked
`obligation_states`, `actor_states`, `occurred_actions`, and `step` —
but Permit and Embargo state were not part of a world's identity at
all. In `build_kripke_from_runtime()` (hybrid mode),
`permit_descriptors` was computed **once**, before BFS expansion even
started, from whatever the live system's permit state happened to be
at that exact moment (filtered `if tok.state != "active": continue`),
then treated as a fixed, global constant for the entire graph. T6's
gate read this static dict, never anything per-world. Live-tested
2026-09-09: with `referralInitiationBurden` discharged and
`patientDataAuthorization` genuinely revoked, the Reachability Path
panel's check for `AI Examination discharged (permit-gated, T6)`
returned `UNREACHABLE`, when the live system genuinely allows a 2-hop
path (re-authorize, then examine). Not a new mistake: hybrid-mode
`PermitDescriptor` was built this way from its own outset, an
active-only-timeless approach correct for the spec-static builder
(`build_kripke_model()`, where a parsed spec never changes mid-
verification) ported directly into hybrid mode without reconsidering
that live permit state, unlike a spec's declared state, can genuinely
change mid-exploration via revoke/reinstate. Design note:
`docs/design_notes/DN_014_kripke_permit_embargo_per_world_state.md`.

Closes the OPEN FINDING logged 2026-08-11 ("R30 Option B design blocked
on a deeper gap: runtime events invisible to both Kripke builders"),
which named exactly this ("extend hybrid mode to read Permit/Embargo
state and generate a T5-equivalent edge from live runtime state") as
Option 1 for closing that gap.

**`T4` is not the mechanism extended here.** `T4 — REVOCATION`
(`build_kripke_model()`'s own docstring) is about *delegation*
revocation (a Burden's holder going `INACTIVE`, obligation reverting to
the delegator) — a different concept from *authorization/permit*
revocation. `T4` stays reserved, unimplemented, untouched.

**Design decision:** same principle already established in this
codebase for Burden/structure — structure extraction is always
spec-derived and mode-agnostic; state is always supplied separately by
whichever mode is running. Extended one step further: who can hold a
permit (`holder`, `for_action`) stays a static, spec-derived fact —
`PermitDescriptor`/structure extraction unchanged. What becomes
per-world is whether that permit is currently active — exactly
mirroring how `ObligationDescriptor` (static) already sits alongside
`obligation_states` (per-world).

**Scope: hybrid mode only (`build_kripke_from_runtime()`), not
`build_kripke_model()`** — matches `T4`'s own precedent exactly; the
static/spec-only builder has no live runtime to revoke against.

**What changed** (`toolchain/el_kripke.py`):
- `World` gained `permit_states`/`embargo_states: FrozenSet[Tuple[str,
  str]]`, both defaulting to `frozenset()` — backward-compatible by
  construction; every existing world that never touches T7/T8 sees an
  empty set, meaning "not tracked here." New accessors `get_permit`/
  `get_embargo`/`permit_dict`/`embargo_dict`, mirroring
  `get_obligation`/`obligation_dict` exactly. `step` gained a `= 0`
  default (a dataclass cannot have non-default fields after defaulted
  ones, and the new fields had to sit before `step` to match T7/T8's
  call shape).
- `_make_world()` takes the same two new params. Normalizes via
  `dict(permit_states).items()` rather than `frozenset(permit_states)`
  directly — a latent bug caught by the Stage 2 test run: `frozenset()`
  on a plain dict iterates its *keys*, silently dropping the state
  values; callers pass either a plain dict (`w0`'s construction) or an
  already-frozen set of pairs (threaded through from a parent world),
  and both must normalize to the same shape.
- `build_kripke_from_runtime()`'s token-processing loop now records
  every permit/embargo token's real current state into
  `init_permit_states`/`init_embargo_states` — active *and*
  superseded/lifted both recorded, nothing filtered out — used to
  seed `w0`. `permit_descriptors` (structure: holder, for_action) is
  now populated for **every** permit regardless of current state, not
  filtered to active-only as before — needed so a permit already
  superseded at build time still has a structural entry for T6's
  holder-match check to succeed once a T8 edge reinstates it
  per-world. (Confirmed necessary empirically, live-testing T7/T8
  against the exact scenario above — not called out explicitly in
  DN_014's own text, which under-scoped this to "populated for every
  permit" without tracing the T6 holder-match consequence.)
- Every existing `_make_world()` call site across the file (not just
  `build_kripke_from_runtime()`'s five BFS rules, but also
  `build_kripke_model()`'s six and the `_run_consent_scenario()` smoke
  script's three) needed touching: the old signature took `step` as
  the 4th positional argument, and the two new params were inserted
  before it — left as positional, `step`'s value would have silently
  landed in the new `permit_states` slot. Sites outside
  `build_kripke_from_runtime()` now pass `step=` as a keyword and
  leave permit/embargo at their `frozenset()` default (correct — those
  builders don't track this); `build_kripke_from_runtime()`'s five
  sites thread `w.permit_states`/`w.embargo_states` through unchanged.
- New shared `_permit_active(w, p)` helper (two-tier: per-world truth
  when tracked, else the old existence-only check via
  `permit_descriptors`) — used by both **T6**'s gate (replacing its
  previous existence-only check) and **T5** (Exercise), which gained
  this guard as a direct, necessary consequence of unfiltering
  `permit_descriptors` above: without it, T5 would start generating
  exercise edges for actions gated by permits that are genuinely
  superseded per-world (not called out in DN_014 either — found the
  same way, via empirical live-fire testing before writing Stage 4
  tests).
- New shared `strict_burden_blocks(w)` helper, factored out of T3's
  existing tick-suppression condition (AM-49/AM-76/AM-78's boolean:
  some `PENDING` `discharge_mode: strict` obligation held by an
  `ACTIVE` actor). Reused by **T7**/**T8**, since
  `revoke_authorization()`/`reinstate_authorization()` never discharge
  anything (`discharged=()` always), so AM-78 correctly left their own
  live guard unconditional whenever this holds — the identical
  condition, not a new one.
- New **T7 — AUTHORIZATION REVOKE** / **T8 — AUTHORIZATION REINSTATE**,
  hybrid-mode only, next free rule numbers after T6 (`T4` stays
  reserved). Mirror `revoke_authorization()`/`reinstate_authorization()`
  (`el_engine.py`) as closely as the model's shape allows: same field
  access (`auth.permit.name` via `_obj_name()`, `on_revocation_embargo`),
  same defensive skip when an Authorization declares no on_revocation
  embargo, same strict-burden guard. Sourced via
  `_collect(spec, "Authorization")` — the same helper
  `_extract_permit_structure()` already uses to walk Authorization
  elements, resolving DN_014 §6's open question empirically rather than
  inventing a new lookup pattern (`_cls(e)` is exactly
  `type(e).__name__`, so this is functionally identical to
  `revoke_authorization()`'s own manual loop). Unlike the live engine,
  T7/T8 do not advance `step` — they are instantaneous actions on a
  world, exactly like T1/T5/T6; only T3 (tick) advances `step`.

**Standard reference(s):** none new — extends the same `T4` precedent
(`build_kripke_model()`'s own docstring) to a distinct concept
(authorization/permit revocation vs. delegation revocation); §6.4.3
(deontic token kinds), §6.6.4/§7.10.2/§7.8.8.4 (Authorization).

**Empirical verification:** full suite re-run after each stage —
Stage 1 (structural `World`/`_make_world()` change alone): 329 passed,
1 xfailed, zero regressions. Stage 2 (T6's two-tier gate): initially 29
failures, all `ValueError: dictionary update sequence element #0 has
length 40` — the `frozenset(dict)` bug above, caught immediately by
the staged test run precisely because it was the first thing to
exercise `w.permit_dict()`; fixed, back to 329 passed, 1 xfailed.
Stage 3 (T7/T8): live-fired the exact scenario above by hand before
writing any test — found and fixed the `permit_descriptors`
unfiltering gap and the resulting T5 guard need (both above); 3 tests
then failed, each asserting the pre-DN_014 bug as correct behavior
(`test_referral_kripke_t6_permit_gate.py::test_ai_examination_burden_ef_false_when_permit_revoked`;
`test_hybrid_t5_exercise_embargo_guard.py`'s revoke/reinstate
whole-graph-label-absence tests) — none are regressions in this
amendment's own code. Stage 4: those three tests updated to assert the
new, correct behavior (one renamed
`test_ai_examination_burden_ef_true_after_revoke_via_reinstate`, with a
new sibling `..._t6_gate_still_blocks_direct_discharge_while_revoked`
guard distinguishing "reachable via reinstate" from "T6's gate went
slack"; the two `test_hybrid_t5_...` tests narrowed from
whole-graph-label-absence to w0's-direct-edges-absence, since T8 makes
the label reachable again further out, by design). New
`tests/test_hybrid_t7_t8_authorization_revoke_reinstate.py` (3 tests):
T7/T8 absent from `w0` while a strict burden is outstanding; T7's
revoke edge present and correct once the strict burden clears; T8's
reinstate edge present and correctly lifts (not merely deactivates)
the embargo. Full suite: 333 passed, 1 xfailed (the pre-existing,
unrelated AM-76 xfail) — zero regressions against the pre-DN_014
baseline.

**Files changed:** `toolchain/el_kripke.py` (`World`, `_make_world()`,
`build_kripke_from_runtime()`'s `w0` construction and BFS loop, T6's
gate, new T5 guard, new T7/T8 rule, new shared `strict_burden_blocks()`/
`_permit_active()` helpers; every other `_make_world()` call site in
the file, keyword-argument-only for `step`); `tests/test_referral_kripke_t6_permit_gate.py`
(one test renamed + rewritten, one new guard test); `tests/test_hybrid_t5_exercise_embargo_guard.py`
(two tests' assertions narrowed to w0's direct edges); `tests/test_hybrid_t7_t8_authorization_revoke_reinstate.py`
(new); `docs/KRIPKE_TRANSITION_RULES.md` (T7/T8 status → Implemented; T6
correction status closed); `docs/CONCEPTS_INDEX.md` (2026-08-11 R30
Option B finding closed out).

## AM-80 (2026-09-09) — Fix `bellman_values()`'s cycle-handling crash

**Status:** IMPLEMENTED (2026-09-09).

**Problem:** live-testing immediately after AM-79 landed, the very
first board-view load of `GET /communities/ReferralEpisodeCommunity/recommended-action`
after a fresh server restart crashed with:

```
File "toolchain/el_kripke.py", line 1088, in <genexpr>
    self.utility(w_prime) + gamma * V[w_prime]
KeyError: World(step=9, [all five referral burdens DISCHARGED])
```

`bellman_values()` ordered worlds via Kahn's algorithm (BFS-based
topological sort) and computed each world's value in a single
reverse-topological pass, assuming every successor's value was already
computed by the time it was needed — correct only for a DAG. Every
transition rule before T7/T8 (AM-79) is monotone (PENDING→
DISCHARGED/VIOLATED/etc, never back), so the world graph was always
acyclic in practice, even though nothing enforced that structurally.
T7 (Authorization Revoke) / T8 (Authorization Reinstate) are the first
genuinely reversible pair: revoke then reinstate, with nothing else
changed in between, returns to a world indistinguishable from a prior
one. Both depend only on permit state and strict-burden status, not on
obligation completion, so this is reachable even from a
fully-discharged terminal world (exactly the crashing world above) —
not limited to mid-episode states. Under Kahn's algorithm, worlds
caught in a cycle never reach in-degree zero, never enter
`topo_order`, and are silently skipped; an already-processed world
looking one up as a successor then raises `KeyError`.

Confirmed not a graph-construction problem:
`build_kripke_from_runtime()`'s BFS already dedupes on `World`
equality, so it correctly builds a finite graph even with cycles in
it — the bug is isolated entirely to `bellman_values()`'s
value-computation step, downstream of a correctly-built graph.
Design note: `docs/design_notes/DN_015_bellman_cycle_fix.md`.

**Design decision:** replace the one-pass topological backward
induction with standard iterative value iteration — the textbook-
correct algorithm for an MDP with cycles and discount factor
`gamma < 1`, not a narrower cycle-avoidance patch. `gamma < 1` makes
the Bellman operator a contraction mapping, so the iteration converges
to the same fixed point regardless of graph structure — matching
backward induction's output exactly on a DAG (verified — see Empirical
verification below) while also being correct on a graph containing
cycles, which backward induction cannot handle at all.

**What changed** (`toolchain/el_kripke.py`, `bellman_values()` only):
- Two new parameters, both with defaults chosen empirically against
  the real referral scenario (see below): `epsilon: float = 1e-6`
  (convergence threshold) and `max_iterations: int = 1000` (safety
  cap). Existing callers (`optimal_path()`; `el_api.py`'s
  `get_recommended_action()`/`get_objective_score()`) all call with
  `gamma=` only (positional or keyword), so both remain fully
  backward-compatible.
- Kahn's-topological-sort block removed entirely. Replaced with:
  initialize `V[w] = 0.0` for every world; repeat up to
  `max_iterations` times computing `new_V[w] = utility(w)` for a
  terminal world (no successors) or
  `max(utility(w') + gamma * V[w'] for w' in successors(w))`
  otherwise, tracking the largest per-world change (`delta`) each
  pass; stop once `delta < epsilon`.
- Performance: `utility(w)` is pure (worlds are immutable) but not
  cheap — it rebuilds a dict and sums over obligations on every call —
  and the naive loop called it `len(worlds) × iterations` times,
  dominating wall-clock time. `successors(w)`/`utility(w)` are now
  precomputed once into plain dicts before the iteration loop (both
  are loop-invariant — neither depends on the evolving `V`), cutting
  wall-clock time by ~2.8× on the graph measured below with no change
  to the algorithm's output.

**What did not need to change:** `optimal_path()` — already has its
own explicit cycle detection while *walking* a path (a `visited` set,
per its own docstring), independent of `bellman_values()`'s internals;
it depends on `bellman_values()` succeeding first, and is unaffected
otherwise (verified — see below). `el_api.py`'s
`get_recommended_action()`/`get_objective_score()` (callers, both call
with `gamma=` only, unmodified). `build_kripke_from_runtime()`'s BFS,
`World`, T7/T8 themselves — all unaffected; this is purely a
value-computation fix downstream of a correctly-built graph. Live
governance/permit enforcement is entirely unaffected — only the
*recommendation* feature (`recommended-action`, `objective-score`,
both of which call `bellman_values()`) was crashing; the live engine's
own permit/precondition checks never touch this code path.

**Empirical verification:**
- Direct reproduction: reimplemented the pre-AM-80 algorithm inline
  (not imported, so it stays a stable regression fixture) and ran it
  against the exact crashing scenario — `_build_referral_runtime()`
  with all five discharge-able referral burdens (`referralInitiationBurden`,
  `clinicalHandoverBurden`, `referralResponseBurden`,
  `assessmentSchedulingBurden`, `aiExaminationBurden`) discharged via
  `discharge_burden()` — confirmed it raises the identical `KeyError`
  found live; confirmed the new algorithm completes on the same
  scenario and returns a value for every world in `km.worlds`,
  including the ones caught in the revoke/reinstate 2-cycle.
- Fixture sanity: confirmed by direct DFS cycle-check (independent of
  `bellman_values()` itself) that this reproduction's graph genuinely
  contains a cycle — not merely a graph the old algorithm happened to
  survive.
- Convergence-equivalence: on a small synthetic DAG (plain-string
  worlds, duck-typed against `KripkeModel.bellman_values` — the real
  referral scenario turned out to have revoke/reinstate cycles
  reachable at modest horizon even from a fresh `w0`, once
  `referralInitiationBurden` clears down some path, so "acyclic real
  subgraph" was not a stable fixture), the new algorithm's output
  matches the reimplemented old algorithm's output exactly (within
  1e-6). On the real cyclic graph, where the old algorithm cannot run
  at all, verified instead that the new algorithm's output satisfies
  the Bellman fixed-point equation for every world.
- Convergence sanity: on the 1352-world graph (referral scenario,
  fresh runtime, `horizon=10`), confirmed convergence within the
  default `epsilon=1e-6` inside `max_iterations=1000` (empirically
  ~133 iterations; `max_iterations` never binds at the default
  `epsilon`) by comparing against a looser `epsilon=1e-3` run — all
  per-world values agree within 1e-2.
- Performance, measured (not assumed) on the referral scenario, fresh
  runtime: `horizon=10` → 1352 worlds / 4632 edges, 2.56s uncached →
  0.91s with the successors/utility caching above; `horizon=15` → 2072
  worlds / 6922 edges, 1.47s. Practical for an interactive API call.
- `optimal_path()` regression: re-ran with the new `bellman_values()`
  on the cyclic scenario — completes, returns a plan, unmodified code
  path.
- Full suite: 339 passed, 1 xfailed (the pre-existing, unrelated
  AM-76 xfail) — zero regressions against the pre-AM-80 baseline (333
  passed, 1 xfailed), the 6 new tests accounting for the difference.

**Files changed:** `toolchain/el_kripke.py` (`bellman_values()` only);
new `tests/test_am80_bellman_cycle_fix.py` (6 tests: cyclic-graph
sanity check, direct-reproduction completeness check, synthetic-DAG
equivalence check, real-graph fixed-point check, epsilon-convergence
regression guard, `optimal_path()` composition check); this file;
`docs/CONCEPTS_INDEX.md` (if not landed in the same sitting — see
that file for current status).

## AM-81 (2026-09-14) — Delegation revocation (T4): `el_engine.revoke_delegation()` + hybrid-mode `Rule T4` in `build_kripke_from_runtime()`

**Status:** IMPLEMENTED (2026-09-14).

**Problem:** `T4 — REVOCATION` had been reserved but unimplemented since
`build_kripke_model()`'s own docstring first named it — genuinely
distinct from `T7`/`T8` (AM-79), which cover *authorization/permit*
revocation, not *delegation* revocation. The docstring's original
sketch ("flip the delegate's `ActorStatus` to `INACTIVE`") was
investigated on 2026-09-12 (docs/CONCEPTS_INDEX.md, T4 investigation
finding) and found to be the wrong shape: `ActorStatus` is a single,
flat, global flag per actor name with no delegation/role/community
scoping anywhere in `el_kripke.py` — revoking one delegation to an
actor would incorrectly flip that actor `INACTIVE` for every other
obligation they separately hold. This amendment implements T4 scoped
per delegation *instance* instead, mirroring how T7/T8 themselves are
correctly scoped per Permit/Embargo instance (`permit_states`/
`embargo_states`) rather than as a blunt per-actor flag — the
investigation's own recommended direction.

**Scope, deliberately narrow, matching T7/T8's own scope exactly:**
single `transfers_burden` Delegations only (`transfers_token_group` is
out of scope — never enters `delegation_index` at all); `.revocable`
enforced as a real precondition (`revoke_authorization()`'s existing
looseness here — it never actually checks `Authorization.revocable` —
is a known, separately-tracked gap, not copied into this new path);
one-way revoke only (no reinstate-delegation edge/function); hybrid
mode only (`build_kripke_from_runtime()`) — `build_kripke_model()` is
untouched, same as T7/T8.

**Layer 3 (`toolchain/el_engine.py`):**
- New `_reassign_holder(tok, new_holder)` helper alongside `_transition()`
  — field-by-field reconstruction with only `holder` changed, modelled
  on the existing inline `transfer` `DeonticEffect` handler's pattern
  (same shape, one field instead of every field).
- New `revoke_delegation(state, spec, delegation_name)`, mirroring
  `revoke_authorization()`'s shape as closely as the different
  construct allows: `KeyError` if undeclared, `KeyError` if not
  `.revocable`, `KeyError` if `.burden` is unset (a
  `transfers_token_group` Delegation), blocked (not raised) via the
  same `_unaddressed_strict_burdens()`/`_strict_block_reason()` guard
  `revoke_authorization()`/`reinstate_authorization()` use, no-op
  (`outcome="ok"`, empty `effects`) if no live TokenInstance for the
  burden is currently held by the delegate — mirroring
  `reinstate_authorization()`'s "already_active" convention — otherwise
  reassigns that token's holder to the delegator, state unchanged.
- **Corrected while implementing, against the spec as originally
  drafted:** the no-op/target lookup matches on `state == "active"`,
  not `"pending"`. No burden anywhere in this codebase is ever granted
  or left `"pending"` while delegated — every burden (including
  `aiExaminationBurden` in `referral_scenario.el`) is declared and
  granted `state: active` and stays `"active"` until discharged/
  violated/superseded; `"pending"` is used *only* for AM-57's unrelated
  TokenGroup `any_discharged` sibling-masking mechanism. Matching on
  `"pending"` as originally specified would have made
  `revoke_delegation()` a permanent no-op against every real scenario
  — confirmed empirically against `referral_scenario.el` before fixing
  it. `"active"` mirrors `_strict_actionable_burdens()`'s own
  convention (`state == "active"`, never `"pending"`, for burden
  actionability).

**Layer 4 (`toolchain/el_kripke.py`):**
- `World` gained `delegation_states: FrozenSet[Tuple[str, str]] =
  frozenset()` — `(delegation_name, "active"|"revoked")` pairs, same
  convention and same backward-compatible empty-default as
  `permit_states`/`embargo_states` (AM-79). New `get_delegation()`/
  `delegation_dict()` accessors, mirroring `get_permit()`/
  `permit_dict()`. `_make_world()` takes the same new param; every
  `_make_world()` call site inside `build_kripke_from_runtime()`'s BFS
  loop (T1's discharge/violate edges, T3's tick, T5's exercise, T6's
  examine, T7's revoke, T8's reinstate) threads
  `delegation_states=w.delegation_states` through unchanged, same
  discipline AM-79 established for `permit_states`/`embargo_states`.
- New `DelegationLink` dataclass (`delegation_name`, `delegator`,
  `delegate`, `revocable`) and `_build_delegation_transfer_index(spec)`,
  keyed by obligation_id (the burden's token name) — mirrors the
  unconditional direct-`.burden`-match branch of
  `_delegation_chain_for_token()` exactly, deliberately excluding that
  function's `token_group` branch (out of scope here).
- New `_effective_holder(w, oid, desc)` helper (closure inside
  `build_kripke_from_runtime()`, alongside `_permit_active()`):
  resolves to the Delegation's delegator when `oid` maps to a tracked
  `DelegationLink` *and* that delegation is flagged `"revoked"` in
  world `w`; otherwise returns `desc.holder` unchanged (every burden
  with no revocable direct-burden Delegation at all — the overwhelming
  majority — is completely unaffected).
- **T1** (Discharge)'s holder-active check and discharge label now read
  through `_effective_holder()` instead of the static `desc.holder` —
  a burden whose delegation was revoked in `w` discharges (and is
  labelled as discharging) against the delegator, not the former
  delegate.
- **`strict_burden_blocks()`** (shared by T3's tick-suppression and
  T7/T8's guard) reads through `_effective_holder()` for the same
  reason: a revoked delegation's still-strict obligation must be judged
  actionable against whoever now actually holds it.
- **T6** (Examine)'s holder-active check *and* its permit-ownership
  match (`permit_descriptors[p].holder == …`) were also switched to
  `_effective_holder()`, extending beyond T1/`strict_burden_blocks()` —
  added after live-verifying against `referral_scenario.el`'s only
  in-scope Delegation (`specialistToAIDelegation`) that its burden,
  `aiExaminationBurden`, is itself permit-gated
  (`conductAIExamination` `requires_permit
  patientRecordAccessPermitByAuthorization`), so T1 alone never governs
  its discharge at all. Confirmed consequence, not a relabeling: post-
  revocation, the effective holder (`SpecialistClinician`) does not
  hold the AI-specific authorization permit `SpecialistAIAgent` was
  granted, so the permit-ownership match fails and the `examine:` edge
  disappears from the reachable model entirely, rather than being
  reattributed. Judged the more correct governance outcome (revoking
  the AI's delegation makes its AI-specific action newly unreachable,
  since the delegator does not inherit the AI's own authorization-
  granted permit) and confirmed with the user before implementing.
- New **T4 — REVOCATION (delegation)** rule block, same position/shape
  as T7/T8 (guarded by the identical `strict_burden_blocks(w)` check —
  `revoke_delegation()` never discharges anything, so it stays
  correctly blocked whenever a strict burden is outstanding and
  actionable, exactly like tick/T7/T8): for each revocable
  `DelegationLink` still `"active"` in `w`, add an edge to a world with
  that delegation flipped to `"revoked"` (obligation/actor/permit/
  embargo state and `step` otherwise unchanged — instantaneous, like
  T1/T5/T6/T7/T8; only T3 advances `step`). Labelled
  `f"revoke_delegation:{deleg_name}"`. One-way only, by design — no
  reinstate branch.
- `build_kripke_model()`'s own docstring (the static/pre-exec builder)
  updated: T4's paragraph now describes the implemented mechanism and
  states explicitly that it is hybrid-mode only, not implemented here —
  same phrasing convention T5's docstring already uses for its own
  Embargo-guard hybrid-only gap.

**Standard reference(s):** §6.6.6/§7.10.1 (Delegation, revocability);
extends the `T4` slot named in `build_kripke_model()`'s own docstring
since before AM-79.

**Empirical verification:** full suite re-run after each stage, no
regressions at any point. Layer 3 alone: 347 passed, 1 xfailed
(baseline unchanged). Layer 4 structural change (`World`/
`_make_world()`/index/helper additions, T1/`strict_burden_blocks()`
substitution): 347 passed, 1 xfailed, unchanged — confirmed via a live
probe against `referral_scenario.el` that a `revoke_delegation:
specialistToAIDelegation` edge is reachable and flips
`delegation_states` correctly. T6 substitution: 347 passed, 1 xfailed,
unchanged — confirmed live that `examine:aiExaminationBurden →
conductAIExamination` is reachable pre-revocation and absent in the
world reached via the T4 edge. New `tests/test_revoke_delegation.py`
(6 tests: happy-path holder reassignment against `referral_scenario.el`,
unknown-delegation `KeyError`, `transfers_token_group`-delegation
`KeyError` — using the scenario's real `gpToSpecialistDelegation` —
blocked-while-strict-burden-outstanding, no-op-once-already-discharged,
and a minimal probe spec for the non-revocable-delegation `KeyError`
case, which has no counterpart in `referral_scenario.el`) and new
`tests/test_hybrid_t4_delegation_revocation.py` (4 tests: T4 absent
from `w0` while a strict burden is outstanding, mirroring T7/T8's own
guard test; T4's edge present and correctly flips
`delegation_states` once the strict burden clears, with a one-way-only
check; the `examine:` edge disappearance above; and a minimal probe
spec with an *ungated* delegated burden isolating T1's own
`discharge:<oid> by <holder>` label rewiring to the delegator — the one
behavior `referral_scenario.el`'s own in-scope Delegation cannot
demonstrate directly, since its burden is permit-gated). Full suite:
357 passed, 1 xfailed — the 10 new tests accounting for the difference
from the 347/1 baseline, zero regressions.

**Files changed:** `toolchain/el_engine.py` (`_reassign_holder()`, new
`revoke_delegation()`); `toolchain/el_kripke.py` (`World`,
`_make_world()`, new `DelegationLink`/
`_build_delegation_transfer_index()`, new `_effective_holder()`
closure, T1/`strict_burden_blocks()`/T6 substitutions, new T4 rule
block, `build_kripke_model()`'s docstring); new
`tests/test_revoke_delegation.py`; new
`tests/test_hybrid_t4_delegation_revocation.py`; this file;
`docs/KRIPKE_TRANSITION_RULES.md` (T4 row); `docs/CONCEPTS_INDEX.md`
(2026-09-12 T4 investigation entry's resolution note).

## AM-82 (2026-09-14) — Burden transfer (T9): hybrid-mode `Rule T9` in `build_kripke_from_runtime()` (Layer 4 only — Layer 3's `transfer` DeonticEffect already existed)

**Status:** IMPLEMENTED (2026-09-14).

**Problem:** the `transfer` `DeonticEffect` (§6.4.7/§7.8.7) has been live
in `el_engine.py` since before this amendment (`elif op == "transfer":`,
reassigning a token's holder when an Action carrying that effect is
performed) but had no Kripke-layer counterpart at all — no rule
existed to model it in either builder, and it went unmentioned even in
`build_kripke_model()`'s own T1–T8 docstring enumeration. There is zero
live usage of it anywhere in `referral_scenario.el` (confirmed:
`grep -n "effect.*transfer"` returns nothing there), so this amendment
also required a new synthetic probe spec (below) to exercise it at all.

**Scope, deliberately narrow, matching T4/T7/T8's own scope:**
Burden-kind tokens only (Permit/Embargo transfers are out of scope —
their per-world state tracks activity, not holder identity);
single-source, single-target only (a `transfer` DeonticEffect is
included only when both `from_role` and `to_role` resolve to exactly
one actor via current role membership — the live engine's
fan-out-to-multiple-holders case is not modelled); a `transfer` with no
`from_role` at all is skipped entirely (no live per-transition acting
actor to fall back on, unlike `el_engine.py`'s own
`eff.from_role or actor_name`); hybrid mode only
(`build_kripke_from_runtime()`) — `build_kripke_model()` is untouched,
same as T4/T7/T8. Layer 3 is untouched this pass — purely additive to
`el_kripke.py`, same spirit as T7/T8's port of already-live engine
behavior (AM-79).

**Known, deliberately unfixed asymmetry (flagged, not copied):**
`el_engine.py`'s own `transfer` handler resolves `to_role` via role
membership (`[a.actor_name for a in state.actors if a.role_name ==
to_role]`) but matches `from_role` directly against
`TokenInstance.holder`, with no role resolution at all — a latent
asymmetry in the live engine, out of scope for this amendment to fix.
`_build_transfer_index()` resolves BOTH `from_role` and `to_role`
through the identical role→actor lookup, which is the semantically
correct behavior for new formal-verification code — not a mirror of
the live engine's current (asymmetric) matching. Fixed by AM-85
(2026-09-14).

**What changed** (`toolchain/el_kripke.py`):
- `World` gained `holder_overrides: FrozenSet[Tuple[str, str]] =
  frozenset()` — `(obligation_id, current_holder_actor_name)` pairs.
  **Deliberately a separate new field from AM-81's `delegation_states`,
  not a merge/refactor of it** — AM-81's already-shipped, tested code
  is untouched. Same accessor pattern (`get_holder_override()`/
  `holder_override_dict()`), same backward-compatible empty default,
  same threading discipline: every `_make_world()` call site inside
  `build_kripke_from_runtime()`'s BFS loop (T1's discharge/violate
  edges, T3's tick, T5's exercise, T6's examine, T7's revoke, T8's
  reinstate, T4's revoke_delegation) now also threads
  `holder_overrides=w.holder_overrides` through unchanged, the same
  discipline AM-79/AM-81 established for `permit_states`/
  `embargo_states`/`delegation_states`.
- `_effective_holder()` (added AM-81) gained one additive `elif`
  branch, not a rewrite: the existing delegation-revocation check runs
  first, unchanged; if it doesn't apply, `w.holder_override_dict()` is
  checked and returned if present; otherwise falls through to
  `desc.holder` as before.
- New `TransferLink` dataclass (`action_name`, `token_name`,
  `from_actor`, `to_actor`) and `_build_transfer_index(spec, actors) ->
  Dict[str, List[TransferLink]]`, keyed by `action_name` — walks
  Community/Domain/Federation → role → action exactly like
  `_build_permit_requirement_index()` does, checking each action's
  `deontic_effects` for `operation == "transfer"` with
  `token.kind == "burden"`. Unlike `delegation_index` (spec-static,
  mode-agnostic), this index needs live runtime actor state to resolve
  `from_role`/`to_role` — built inside `build_kripke_from_runtime()`
  only (from `state.actors`), not shared with the static builder, which
  has no live role membership to resolve against.
- New **T9 — TRANSFER**, same position/shape as T4 (immediately after
  it): for each `TransferLink` where the token's current effective
  holder (via `_effective_holder()`) equals `from_actor` and
  `from_actor` is `ACTIVE`, and the carrying Action hasn't already
  occurred in this world (`w.has_occurred(action_name)` — same idiom T5
  already uses for its own occurred-check, though for a different
  reason there: avoids a redundant self-loop), add an edge to a world
  with `holder_overrides` updated for that obligation and
  `occurred_actions` including the Action (the live engine really does
  mark the action occurred; T9 mirrors that). Gated by the identical
  `strict_burden_blocks(w)` condition as T4/T7/T8 — a transfer doesn't
  discharge anything either. Labelled
  `f"transfer:{token_name} via {action_name} ({from_actor}→{to_actor})"`.
  Instantaneous, no step advance, same convention as every other rule
  here except T3.
- `build_kripke_model()`'s own docstring gained a new T9 paragraph —
  there wasn't one before (this rule didn't exist in that docstring's
  original T1–T5 enumeration at all), added in the same phrasing
  convention T4's paragraph uses for its own hybrid-only-gap note.

**New synthetic probe spec** (`scenarios/probes/transfer_probe.el`,
Probe tier): the first and only live exercise of `effect transfer`
anywhere in this repo's scenarios. One `party`/`Burden`/`Action` happy
path (`performTransfer`: `roleA` → `roleB`) plus one dedicated
Burden/Action pair per T9 skip case in the same file — no `from_role`
at all, `from_role` (`roleC`) filled by two actors (ambiguous),
`to_role` (`roleUnfilled`) filled by nobody (zero actors), and a
Permit-kind token — plus one outstanding `discharge_mode: strict`
Burden to exercise the `strict_burden_blocks()` guard. Role membership
has no grammar construct in this DSL at all (no "fills"/"member"
binding — an Action's `actor: roleX` is descriptive only, per the
grammar's own DOC-03 comment), so role assignment is done in Python via
`el_engine.enroll(state, actor_name, role_name=...)`, the same pattern
`el_api.py`'s own scenario builders already use — not something this
grammar is missing a construct for by mistake.

**Standard reference(s):** §6.4.7/§7.8.7 (DeonticEffect, transfer
operation) — the same clause the already-live `el_engine.py` handler
cites; no new grammar construct.

**Empirical verification:** full suite re-run after each stage, no
regressions at any point. Structural change (`World`/`_make_world()`/
`_effective_holder()` additive branch): 357 passed, 1 xfailed
(baseline unchanged). Index/T9 rule block: 357 passed, 1 xfailed,
unchanged — confirmed live against the new probe that
`_build_transfer_index()` returns exactly one entry (`performTransfer`)
out of five candidate Actions, correctly excluding all four skip cases,
and that the resulting `transfer:` edge's world reassigns
`probeBurden`'s effective holder (confirmed via both
`get_holder_override()` directly and T1's discharge label changing
from `by ActorA` to `by ActorB` afterward). New
`tests/test_hybrid_t9_transfer.py` (8 tests): happy-path edge presence
and holder reassignment, T1 discharge-label rewiring (plus a
no-self-loop check), the four skip cases, and the strict-burden guard
(absent while outstanding, present once cleared). Full suite: 365
passed, 1 xfailed — the 8 new tests accounting for the difference from
the 357/1 baseline, zero regressions.

**Files changed:** `toolchain/el_kripke.py` (`World`, `_make_world()`,
`_effective_holder()`, new `TransferLink`/`_build_transfer_index()`,
new T9 rule block, `build_kripke_model()`'s docstring); new
`scenarios/probes/transfer_probe.el`; new
`tests/test_hybrid_t9_transfer.py`; this file;
`docs/KRIPKE_TRANSITION_RULES.md` (T9 row); `scenarios/README.md` (new
probe catalog entry).

---

## AM-83 (2026-09-14) — JoinLeaveEffect on_join (§7.8.7 NOTE 3): new `el_engine.join_role()` (Layer 3 only — Layer 4 gap logged separately, not closed)

**Status:** IMPLEMENTED (2026-09-14), Layer 3 only.

**Problem:** `JoinLeaveEffect` (`on_join <role> transfer <token>` /
`on_leave <role> revert <token>`) has been a live grammar construct
since AM-21, and is parsed into `Community.join_leave_effects` (also
`Domain`/`Federation`, though neither of those two grammar rules
actually declares a `join_leave_effects` field — see "What changed"
below), but was consulted by **nothing at any layer**. This is a
different failure mode from the T-series items (T4/T6/T7/T8/T9): those
were Layer-3-implemented-Layer-4-missing gaps (an existing live engine
behavior with no Kripke counterpart yet). This one is
declared-and-silently-inert everywhere — `enroll()`, the engine's only
role-membership entry point, has no `spec` parameter and so cannot see
`JoinLeaveEffect` declarations at all; it is not a missing effect
handler inside an existing dispatch, it is a missing capability at the
entry point itself.

`referral_scenario.el` has three live, previously-inert `on_join`
declarations exercised by this amendment: `gpClinicianRole` →
`referralInitiationBurden`, `referringRole` → `clinicalHandoverBurden`,
`referredToRole` → `patientRecordAccessPermitByRole`.

**Scope — deliberately Layer 3 only:** `on_leave`/`revert` is
explicitly OUT of scope, not a deferred nice-to-have: there is no
leave/unenroll primitive anywhere in this engine (only `enroll()`
exists; nothing removes or reassigns an `ActorState`), so there is no
state transition for an `on_leave` handler to hook into yet — a hard
prerequisite blocker. Layer 4/Kripke is explicitly NOT touched this
pass either; see the new dated entry in `docs/CONCEPTS_INDEX.md` for
why that is a structurally different, harder problem than the T-series
additions, not a smaller version of the same one.

**What changed** (`toolchain/el_engine.py`):
- New `join_role(state, spec, actor_name, role_name, community_tag="")
  -> Tuple[WorldState, List[str]]`, placed immediately after `enroll()`.
  `enroll()` itself is completely untouched — same signature, same
  zero-token-effect behavior, confirmed by a dedicated regression test
  below. `join_role()` calls `enroll()` for the base actor-state change,
  then walks `spec.elements` for `Community`/`Domain`/`Federation`,
  collecting each element's `join_leave_effects` (via `getattr(el,
  "join_leave_effects", [])` — defensive, same style as
  `_find_action_for_burden`'s existing traversal — since `Domain`'s
  `DomainBodyItem` and `Federation`'s `FedBodyItem` alternations do not
  actually include `JoinLeaveEffect` at all; only `Community`'s body
  rule does. Confirmed by reading the grammar directly, not assumed.
  Today this means only `Community`-declared `on_join` effects can ever
  fire; the `Domain`/`Federation` walk is forward-compatible, not dead
  code covering a real current gap), filters to `kind == "on_join"` and
  a matching `role_name`, and for each match grants the named token to
  `actor_name` — mirroring the `create` `DeonticEffect` handler's exact
  `TokenInstance` construction (`state="active"`, `discharge_mode` from
  the token's own declared default or `"eventual"`, `priority` default
  `"normal"`, `granted_at_tick=state.tick`) including its idempotency
  guard (skip if `actor_name` already holds a token of that name — same
  guard shape as AM-"double role-enrollment bug" fix, `docs/CONCEPTS_INDEX.md`,
  2026-08-20). Chose create-style construction over literally moving an
  existing live `TokenInstance` from a `from_role` holder (the way the
  separate, pre-existing `transfer` `DeonticEffect` op at
  `el_engine.py:706` does) because the grammar's own `holds <token>`
  declarations inside a role body are spec-level, not live pre-seeded
  `WorldState` instances in general — confirmed against
  `referral_scenario.el` itself: `referringRole` has no `holds
  clinicalHandoverBurden` in its body at all (unlike `gpClinicianRole`
  and `referredToRole`, which do), so a from-role-holder-move semantics
  would have nothing to move for that case. This grant-on-join reading
  is also the one already implied by the pre-existing, still-open
  finding "Permit granted via role-level `holds` is invisible to
  spec-only `permit_descriptors`" (`docs/CONCEPTS_INDEX.md`,
  2026-08-18), checked before implementing this amendment per this
  repo's CLAUDE.md OPEN FINDING gate.

**Standard reference(s):** §7.8.7 NOTE 3 (JoinLeaveEffect / token
transfer on role fill or leave) — no new grammar construct; the grammar
side has existed since AM-21.

**Empirical verification:** new `tests/test_join_role_on_join_effects.py`
(7 tests), run directly against `referral_scenario.el`'s real,
previously-inert `on_join` declarations — no synthetic probe needed:
grant-on-join for each of the three live declarations; idempotency both
when `join_role()` itself is called twice and when the token was
already granted by an unrelated means beforehand; a role with no
matching `JoinLeaveEffect` (`aiExaminationRole`) behaves identically to
bare `enroll()` (zero token effects); and a direct regression check that
bare `enroll()` itself still produces zero token effects, unchanged.
Full suite: 372 passed, 1 xfailed — the 7 new tests accounting for the
difference from the 365/1 baseline, zero regressions.

**Files changed:** `toolchain/el_engine.py` (new `join_role()`); new
`tests/test_join_role_on_join_effects.py`; this file;
`docs/CONCEPTS_INDEX.md` (new dated entry documenting the Layer 4 gap
as unresolved and structurally distinct from the T-series — not a
`KRIPKE_TRANSITION_RULES.md` row, since nothing in that file changed).

---

## AM-84 (2026-09-14) — Delegation reinstatement (T10): `el_engine.reinstate_delegation()` + hybrid-mode `Rule T10` in `build_kripke_from_runtime()` (closes AM-81's deliberate one-way gap, both layers)

**Status:** IMPLEMENTED (2026-09-14).

**Problem:** AM-81 implemented `revoke_delegation()`/`Rule T4`
deliberately one-way — "no reinstate-delegation edge/function" was an
explicit scope decision, not an oversight. This amendment closes that
gap: the reverse direction, both layers, same scope boundaries AM-81
already established. It does not reopen any of AM-81's other scope
decisions (`transfers_token_group` Delegations remain out of scope;
`.revocable` remains a real, enforced precondition; hybrid mode only
at Layer 4).

**Scope — identical to AM-81, just bidirectional now:** single
`transfers_burden` Delegations only; `.revocable` enforced; hybrid
mode only (`build_kripke_from_runtime()`) — `build_kripke_model()` is
untouched.

**Layer 3 (`toolchain/el_engine.py`):**
- New `reinstate_delegation(state, spec, delegation_name)`, placed
  immediately after `revoke_delegation()`. Simpler than
  `reinstate_authorization()`'s mirror of `revoke_authorization()`:
  delegation revocation never creates a new token (no
  embargo-equivalent) — it only moves an existing Burden's holder — so
  there is no first-time-grant branch to handle, just "is it currently
  with the delegator, and if so move it back." Same three `KeyError`
  preconditions as `revoke_delegation()` (undeclared, not `.revocable`,
  no direct `.burden`); same `_unaddressed_strict_burdens()`/
  `_strict_block_reason()` guard (reinstating doesn't discharge
  anything either); no-op (`outcome="ok"`, empty `effects`) if no live
  `"active"` `TokenInstance` for the burden is currently held by the
  **delegator** — already back with the delegate, or discharged/
  violated; otherwise reassigns that token's holder from delegator back
  to delegate via the existing `_reassign_holder()` helper (AM-81) — no
  new helper needed.
- `revoke_delegation()`'s own docstring corrected: the "One-way only:
  there is no reinstate-delegation counterpart" line is no longer true
  and now points to `reinstate_delegation()` instead.

**Layer 4 (`toolchain/el_kripke.py`):**
- Extended the existing T4 rule block rather than writing a new one:
  the block header is renamed "Rule T4/T10: DELEGATION REVOKE /
  REINSTATE" (same naming convention as the T7/T8 header above it), and
  its comment now describes both directions, with the "one-way only"
  line removed (no longer true). The single `for link in
  delegation_index.values(): ... if w.delegation_dict().get(deleg_name,
  "active") != "active": continue` early-exit was restructured into two
  independent `if` branches — `== "active"` (T4, unchanged behavior)
  and `== "revoked"` (new T10) — the same `if`/`if`-shaped pairing T7/T8
  already use for their own revoke/reinstate branches (two independent
  checks, not an `if`/`elif`, since a `continue` would have skipped the
  new branch too). T10 flips `delegation_states[deleg_name]` from
  `"revoked"` back to `"active"` in a new world via the same
  `_make_world()` call shape T4 already uses (`holder_overrides`/
  `permit_states`/`embargo_states` threaded through unchanged). No
  change needed to `_effective_holder()` itself: it already falls
  through to `desc.holder` (the delegate) whenever
  `delegation_dict().get(...)` is anything other than `"revoked"`, so
  flipping the state back to `"active"` alone restores the original
  delegate as the effective holder everywhere T4 redirected it (T1,
  `strict_burden_blocks()`, T6). Labelled
  `f"reinstate_delegation:{deleg_name}"`. Same `strict_burden_blocks(w)`
  guard, same instantaneous/no-step-advance convention as T4.
- `build_kripke_model()`'s own docstring gained a new T10 paragraph
  immediately after T4's (T4's paragraph also lost its own "one-way
  only" line), same hybrid-only-gap phrasing convention T9's paragraph
  already uses.

**Standard reference(s):** §6.6.6/§7.10.1 (Delegation, revocability) —
same clause AM-81 already cites; no new grammar construct.

**Empirical verification:** full suite re-run after each stage, no
regressions at any point. `tests/test_revoke_delegation.py` extended
(not a new file) with 7 tests: `reinstate_delegation()` happy path
against `specialistToAIDelegation` (revoke then reinstate, confirming
the holder ends back with `SpecialistAIAgent`, active state preserved,
a real effect logged), the same three `KeyError` cases (unknown
delegation, `transfers_token_group` delegation via the scenario's real
`gpToSpecialistDelegation`, non-revocable delegation via the existing
probe spec), the strict-burden-blocked case, and the no-op case
(delegation never revoked, so nothing is with the delegator to move
back) — 12 tests total in that file, up from 6. Confirmed the existing
happy-path test's assertion still holds unmodified (revoke's own
behavior is untouched).
`tests/test_hybrid_t4_delegation_revocation.py` extended (not a new
file) with 2 tests: after a `revoke_delegation:specialistToAIDelegation`
edge, a `reinstate_delegation:specialistToAIDelegation` edge is
reachable from that world and the resulting world's `delegation_states`
shows `"active"` again; and confirmed live that
`examine:aiExaminationBurden → conductAIExamination` — absent in the
revoked world (AM-81's own documented consequence) — reappears in the
reinstated world, the mirror image of that finding: the case where the
AI genuinely does get its access back and the obligation stops being
stranded. Also fixed the existing edge-presence test's now-stale
"One-way only — no reinstate-delegation edge back" comment (the
assertion itself — no re-revoke edge from an already-revoked world —
was still correct and needed no change; only the comment was wrong) —
6 tests total in that file, up from 4. Full suite: 380 passed, 1
xfailed — the 8 new tests accounting for the difference from the 372/1
baseline, zero regressions.

**Files changed:** `toolchain/el_engine.py` (new
`reinstate_delegation()`; `revoke_delegation()`'s docstring corrected);
`toolchain/el_kripke.py` (T4 rule block extended into T4/T10,
`build_kripke_model()`'s docstring gained a T10 paragraph);
`tests/test_revoke_delegation.py` (extended); `tests/test_hybrid_t4_delegation_revocation.py`
(extended); this file; `docs/KRIPKE_TRANSITION_RULES.md` (new T10 row,
T4's row retitled and its "one-way only" framing dropped). No
`docs/CONCEPTS_INDEX.md` entry — this closes a documented,
already-logged gap (AM-81's own explicit scope note), it does not
surface a new finding.

---

## AM-85 (2026-09-14) — Fix the live `transfer` DeonticEffect's from_role/to_role resolution asymmetry (`toolchain/el_engine.py`)

**Status:** IMPLEMENTED (2026-09-14).

**Problem:** diagnosed during AM-82 but deliberately left unfixed at the
time (see that entry's "Known, deliberately unfixed asymmetry" note,
and the matching note in `_build_transfer_index()`'s docstring in
`el_kripke.py`, both updated by this amendment with a one-line pointer
here). `el_engine.py`'s live `transfer` `DeonticEffect` handler resolved
`to_role` via role membership, with a graceful literal-name fallback if
nobody currently fills that role:

    to_actors = [a.actor_name for a in state.actors
                 if a.role_name == to_role] or [to_role]

`from_role` got no such resolution at all — `from_role = eff.from_role
or actor_name`, then matched directly against `t.holder`
(`t.holder == from_role`). This only ever worked if `from_role`
happened to literally equal an actor's own name. A genuine role name
passed as `from_role` never matched anything: the transfer silently did
nothing — no error, no log entry indicating why, no distinguishing this
case from "nothing to transfer."

**The fix:** the identical role-resolution-with-fallback pattern
`to_role` already used, applied to `from_role`, but only when
`eff.from_role` was actually given — the `actor_name` fallback (when it
is omitted) is preserved exactly as-is, since `actor_name` at that point
is already a concrete actor, not a role name, and must not be
re-resolved through role lookup or the "whoever is performing this
action" fallback breaks:

    if eff.from_role:
        from_actors = [a.actor_name for a in state.actors
                       if a.role_name == eff.from_role] or [eff.from_role]
    else:
        from_actors = [actor_name]

The match condition changed from `t.holder == from_role` to
`t.holder in from_actors`; the effects-log line now reports the actual
matched `t.holder` (previously equivalent to `from_role` under the old
single-literal-match scheme, no longer equivalent once `from_actors` can
resolve to a role's one current filler).

**Scope:** Layer 3 only (`el_engine.py`). No Kripke-side change needed:
`_build_transfer_index()` (AM-82) already resolved both `from_role` and
`to_role` through the identical role→actor lookup — its own docstring
already noted this was "the semantically correct behavior for new
formal-verification code, not a mirror of the live engine's current
(asymmetric) matching." That mirror gap is now closed from the live-
engine side instead.

**Standard reference(s):** §6.4.7/§7.8.7 (DeonticEffect, transfer
operation) — same clause AM-82 already cites; no grammar change.

**Empirical verification:** new `tests/test_transfer_effect_from_role_resolution.py`
(3 tests) — the first test exercising this handler via live execution
at all (AM-82's own tests are Kripke-side/state-only). Uses a small,
throwaway inline probe spec (`parse_string()`, same pattern as
`tests/test_discharge_burden.py`), distinct from
`scenarios/probes/transfer_probe.el` (AM-82's Kripke-tier probe,
explicitly documented as disposable/not expected to be touched again).
Probe deliberately names the role-filling actor `Holder` and the role
`sourceRole` — different strings — so a passing test could not have
passed against the pre-fix code (`t.holder == from_role` would compare
`"Holder" == "sourceRole"` and never match). Covers: `from_role` given
as a real role name, resolved correctly (also the regression case,
since the holder's name differs from the role name); `from_role`
omitted, confirming the `actor_name` fallback is unchanged; `from_role`
naming a role nobody currently fills, confirming the
`or [eff.from_role]` fallback still attempts a literal match and
degrades gracefully (outcome `"ok"`, empty effects, holder unchanged) —
the same non-crashing shape the pre-fix code already had for any
non-matching `from_role`, only how it gets there changed. Full suite:
383 passed, 1 xfailed — the 3 new tests accounting for the difference
from the 380/1 baseline, zero regressions.

**Files changed:** `toolchain/el_engine.py` (`transfer` `DeonticEffect`
handler); new `tests/test_transfer_effect_from_role_resolution.py`;
this file (new entry, plus a one-line pointer added to AM-82's own
entry); `toolchain/el_kripke.py` (one-line pointer added to
`_build_transfer_index()`'s docstring — the function itself is
unchanged). No `docs/KRIPKE_TRANSITION_RULES.md` change — T9's row
already describes `_build_transfer_index()`'s own (already-correct)
resolution, not the live engine's; no `docs/CONCEPTS_INDEX.md` entry —
this closes a documented, already-logged gap (AM-82's own explicit
note), it does not surface a new finding.

## AM-86 (2026-09-15) — `_build_obligation_descriptors()` gains two new accountability roots: `ViolationResponse.creates_burden` and `Authorization.auth_burden` (`toolchain/el_engine.py`)

**Status:** IMPLEMENTED (2026-09-15).

**Problem:** `_build_obligation_descriptors()` (`toolchain/el_engine.py`)
only ever iterated `Commitment` elements. Any burden created exclusively
through a different root construct was structurally absent from
`km.obligation_descriptors` — invisible not just to AF/EF checks but to
`recommend_action()`/Bellman planning too, since both only ever score
obligations already present in that dict. Two real/candidate cases:

- `ViolationResponse.creates_burden` — real, live case:
  `escalationNoticeBurden` in `scenarios/referral/referral_scenario.el` is
  created only via `violation_response referralNoResponseViolation`, no
  Commitment anywhere in the file creates it. Logged as an open finding
  in `docs/CONCEPTS_INDEX.md` ("`escalationNoticeBurden` has no
  ObligationDescriptor — invisible to Layer 4"), now resolved by this
  amendment. AM-56 already closed the equivalent Layer-2 gap in
  `el_reasoner.ultimate_accountability()`; `el_kripke.py`'s hybrid-mode
  docstring (AM-56's cross-reference note) explicitly flagged the
  Layer-4 side as "unaffected and remains open" — this closes it.
- `Authorization.auth_burden` (grammar keyword
  `creates_burden_on_authority`) — same shape, discovered while grounding
  this fix. Zero live usage anywhere in the corpus (confirmed via grep
  over `scenarios/`); closed proactively before anything depends on it,
  same shape as AM-82/T9. New open finding logged in
  `docs/CONCEPTS_INDEX.md` for the one open question this raises: whether
  `el_reasoner.py`'s Layer-2 accountability resolution has the identical
  blind spot for this specific construct (AM-56 only confirmed covering
  `ViolationResponse.creates_burden`) — flagged there, not answered.

**The fix:** extracted the shared tail logic (chain-walking from a seed
actor, resolving `sub_delegation_allowed`/`revocable` from the delegation
terminating at the holder, extracting `triggered_by`/`fires_event`/
`for_action` from the burden token, constructing the `ObligationDescriptor`
itself) into one nested closure, `_add_descriptor(burden_name, actor_name,
obl_text)`, called once per root construct instead of duplicated per root.
Three roots, in this order:

1. `Commitment` (§6.6.2, §7.10.3) — unchanged from pre-AM-86: `actor_name`
   from `.actor`, `obl_text` from the mandatory `.obligation` STRING.
2. `ViolationResponse` (§6.3.8, §7.8.6 NOTE 2) — only when `.creates_burden`
   is set (optional field, skipped otherwise). `actor_name` from
   `.obligates` (parsed attribute `responding_actor`) — mirrors AM-56's
   Layer-2 precedent directly rather than making a new accountability-root
   decision. `obl_text` from `.description` if present, else falls back to
   `burden_name` — this construct has no `.obligation` field at all.
3. `Authorization` (§6.6.4, §7.10.2, §7.8.8.4) — only when `.auth_burden`
   is set. `actor_name` from `.authority` — "the authority grants a permit
   AND undertakes a burden to facilitate" (the grammar's own comment on
   `Authorization`). Same `.description`-or-`burden_name` fallback as (2).
   Note the grammar keyword/attribute-name split: the keyword is
   `creates_burden_on_authority`, but the parsed attribute is `auth_burden`
   (`grammar/v2/el_grammar.tx:1018`, `el_domain.py:1183`) — same split
   pattern as `on_violation_of` → `violated_burden`.

If the same `burden_name` were ever referenced by more than one of these
three roots (not structurally prevented, but not expected given the
grammar's own separation of concerns), the last root evaluated wins — not
new behavior, the pre-existing Commitment-only loop already had the same
last-write-wins property if two Commitments somehow referenced the same
burden.

Also updated: a stale comment in `build_kripke_from_runtime()`
(`el_kripke.py`, ~line 2849) claiming `spec_descriptors` "only covers
burdens that appear in a Commitment or Delegation.token_group" — corrected
to name all four roots now covered.

**Scope:** both Layer 4 builders (`build_kripke_model()` and
`build_kripke_from_runtime()` both import the same
`_build_obligation_descriptors()`, `el_kripke.py:94`) — confirmed both
pick up the fix, not just one. No grammar change (both fields already
existed, AM-31/AM-17-era); no `el_reasoner.py` change (Layer-2 already
covers `ViolationResponse` via AM-56; the `Authorization.auth_burden`
Layer-2 question is opened, not closed, by this amendment — see the new
`docs/CONCEPTS_INDEX.md` finding).

**Standard reference(s):** §6.3.8/§7.8.6 NOTE 2 (ViolationResponse);
§6.6.4/§7.10.2/§7.8.8.4 (Authorization); §6.6.2/§7.10.3 (Commitment,
unchanged).

**Empirical verification:** new `tests/test_am86_obligation_descriptor_roots.py`
(7 tests). Covers: `escalationNoticeBurden` gets a genuine descriptor in
pre-exec mode (`build_kripke_model()`) with holder resolving to the
degenerate single-element chain `["SpecialistPractice"]` (confirmed by
direct inspection of the file's two delegation blocks, neither of which
originates at `SpecialistPractice` — not assumed); is now reachable via
both `check_obligation()`/AF and `check_permission()`/EF, and appears in a
`recommend_action()` successor world's `obligation_states`; gets a
descriptor in hybrid mode too (`build_kripke_from_runtime()`, live token
granted directly since this burden is never granted at referral-runtime
builder time — same live-granting gap `tests/test_referral_event_triggers.py`
already documents), with `for_action` as the concrete before/after field
(empirically confirmed `None` under git HEAD's pre-AM-86 code on the
identical live-token setup, `"notify_gp_of_non_response"` post-fix); a
throwaway inline probe (`parse_string()`, same convention as
`tests/test_transfer_effect_from_role_resolution.py`/AM-85) for
`Authorization.auth_burden`, both the burden-created and
no-burden-created-when-field-absent cases; and a parametrized regression
test pinning every pre-existing Commitment-backed descriptor's full field
set (both `referral_scenario.el`'s 6 and `consent_scenario.el`'s 2) to
values captured from an empirical `dataclasses.asdict()` diff against git
HEAD's (`dde0e6c`) pre-AM-86 code — all byte-identical, confirming this is
a pure additive change to the existing Commitment path. Full suite: 390
passed, 1 xfailed — the 7 new tests accounting for the difference from the
383/1 baseline, zero regressions.

**Correction (AM-105, 2026-09-26):** "reachable via both
`check_obligation()`/AF" above was a wrong verdict, and the test pinned
it. The static builder placed `escalationNoticeBurden` in w0 as an
ordinary PENDING strict obligation, unlinked to the violation that
creates it, so AF held trivially. Since AM-105 it starts WAITING and is
activated by `referralResponseBurden`'s violation; its verdict is the
bounded response property, "not triggered within horizon" (horizon 10
against a 40-step deadline), with EF false. It is still in the model and
still appears in a recommended successor's `obligation_states`. The text
above is left as it was.

**Files changed:** `toolchain/el_engine.py` (`_build_obligation_descriptors()`
refactor); `toolchain/el_kripke.py` (stale comment correction, no logic
change); new `tests/test_am86_obligation_descriptor_roots.py`; this file
(new entry); `docs/CONCEPTS_INDEX.md` (escalationNoticeBurden finding
marked RESOLVED; new finding logged for the open
`Authorization.auth_burden`/Layer-2 question).

---

## AM-87 (2026-09-16) — `ultimate_accountability()` gains a fifth accountability root: `Authorization.auth_burden` (`toolchain/el_reasoner.py`)

**Status:** IMPLEMENTED (2026-09-16).

**Problem:** answers the open question AM-86 logged in
`docs/CONCEPTS_INDEX.md` ("`Authorization.auth_burden` — same descriptor
blind spot as `escalationNoticeBurden` had, caught proactively; open
question whether `el_reasoner.py` shares it") rather than leaving it
unchecked. Direct inspection confirms it does: `grep -n
"Authorization\|auth_burden" toolchain/el_reasoner.py` returned zero
matches before this fix, and `ultimate_accountability()`'s own docstring
enumerated exactly four root paths — `Commitment`, `Delegation`-only
roots, AM-53's `Role.holds` fallback, and AM-56's
`ViolationResponse.creates_burden` fallback — with nothing for
`Authorization.auth_burden`. A burden created purely via `authorization {
creates_burden_on_authority: ... }` (no Commitment, no Delegation, no
Role.holds, no ViolationResponse) fell through every branch and returned
`[]`, the identical "genuinely not found" symptom AM-53/AM-56 already
fixed for the role-anchor and violation-response cases respectively.

**What changed** (`toolchain/el_reasoner.py`):
- `AccountabilityChain` gains `root_authorization: Optional[str] = None`,
  mirroring AM-56's `root_violation_response` field exactly — mutually
  exclusive with `root_commitment`/`root_violation_response`, never more
  than one set on a given chain. `render()` gains the matching `"Origin
  : authorization '...'"` line.
- New `_find_authorization_roots(model, token_name)`, placed immediately
  after `_find_violation_response_roots()` — structurally identical to
  it, substituting `Authorization`/`auth_burden`/`authority` for
  `ViolationResponse`/`creates_burden`/`responding_actor`. `actor_name`
  resolves from `.authority` (the grammar's own comment on
  `Authorization`: "the authority grants a permit AND undertakes a
  burden to facilitate"), matching AM-86's Layer-4 choice of seed actor
  for the identical construct. Matched structurally on `auth_burden`'s
  own token identity, never free text (AM-54/AM-56 precedent).
- `ultimate_accountability()`'s no-Commitment/no-Delegation branch now
  tries, in order: `_find_role_anchors_for_obligation()` (AM-53), then
  `_find_violation_response_roots()` (AM-56), then
  `_find_authorization_roots()` (AM-87) — each only reached when every
  path before it found nothing. Docstring's numbered algorithm gains a
  step 9 describing this; the `Returns` section's "genuinely not found"
  definition extended to include "no `Authorization.auth_burden` names
  this token either."

**Standard reference(s):** §6.6.4/§7.10.2/§7.8.8.4 (Authorization) — same
clauses cited on the grammar rule itself (AM-31); no new grammar
construct.

**Empirical verification:** zero live usage of
`creates_burden_on_authority`/`auth_burden` anywhere in `scenarios/`
(confirmed via grep, same as AM-86's own finding) — this is a
proactive-closure fix, not a regression fix against a real scenario. New
`tests/test_am87_authorization_accountability_root.py` (3 tests), reusing
AM-86's exact `_AUTH_BURDEN_PROBE` spec (`tests/test_am86_obligation_descriptor_roots.py`)
via `parse_string()` for consistency between the Layer-2 and Layer-4
checks on the identical construct: the probe's `facilitationBurden`
resolves to `root_party == "Authority"`, `root_authorization ==
"probeAuthorization"`, both `root_commitment`/`root_violation_response`
left `None`; the same probe with `creates_burden_on_authority` removed
still returns `[]`; and a regression check that the real
`escalationNoticeBurden` case (AM-56, `referral_scenario.el`) still
resolves via `root_violation_response`, unaffected by the new fallback
sitting after it in the same branch. Full suite: 393 passed, 1 xfailed —
the 3 new tests accounting for the difference from the 390/1 baseline,
zero regressions.

**Files changed:** `toolchain/el_reasoner.py` (`AccountabilityChain.root_authorization`,
`render()`, `_find_authorization_roots()`, `ultimate_accountability()`
docstring + branch wiring); new
`tests/test_am87_authorization_accountability_root.py`; this file (new
entry); `docs/CONCEPTS_INDEX.md` (AM-86's open question marked
RESOLVED).

---

## AM-88a (2026-09-19) — Multi-parent tracing, engine side: `walk_chain()` becomes structural-first and per-token (`toolchain/el_engine.py`)

**Status:** IMPLEMENTED (2026-09-19). Layer 4 counterpart (`el_kripke.py`'s
`_delegation_chain_for_token()`) is AM-88b, tracked separately.

**Problem:** `_build_obligation_descriptors()` has two single-lineage flaws
that only surface when two delegation lineages converge on one agent —
never exercised by any scenario in the corpus today (confirmed by AM-88's
recon ground-truth scan, logged in `docs/CONCEPTS_INDEX.md`), but real bugs
in the code path itself:

1. `walk_chain(start, obl_text)` picked its next hop by testing
   `obl_text.lower() in oblt.lower()` against every outgoing `Delegation`
   from the current node, and took `outgoing[0]` — it never consulted
   which token a `Delegation` structurally transfers via `transfers_burden`/
   `transfers_token_group`. Two Commitments sharing obligation text into
   one delegate, each transferring a *different* burden onward at a further
   hop, could have one token's walk silently continue along the *other*
   token's onward `Delegation`, purely because the text matched.
2. `sub_delegation_allowed`/`revocable` were computed after the walk by
   scanning every `Delegation` in the model for "the last one whose
   `delegate` equals the resolved `holder`" — independent of which token
   was actually being resolved, and dependent on declaration order when
   more than one `Delegation` shares that delegate.

**Repro (see `tests/test_am88a_multi_parent_tracing.py`,
`test_repro1_converging_lineages_resolve_per_token` /
`test_repro2_sub_delegation_allowed_and_revocable_are_order_independent`):**
`FinanceParty`/`LegalParty` each commit an obligation with identical text
("Settle payments") into `SettlementAgent`, which sub-delegates only
`settleBurdenA` (Finance's) onward to `SubAgent`. Pre-fix,
`settleBurdenB`'s (Legal's) chain incorrectly continued onto `SubAgent`
too, and both tokens' `sub_delegation_allowed`/`revocable` took on
whichever of `finDel`/`legDel` was declared last.

**What changed** (`toolchain/el_engine.py`):
- New `_commitment_root_for_token(model, token_name)` — returns
  `(actor_name, obligation_text)` for `token_name`'s own `Commitment`, or
  `None`. Mirrors `el_kripke.py`'s identical function of the same name,
  which keeps its own copy for now (AM-88b switches it to import this one
  instead and deletes that copy — see that amendment for `el_kripke.py`'s
  side; the two are not shared as of AM-88a). Written in `el_engine.py`'s
  own idiom (inline `type(x).__name__` filtering) rather than importing
  `el_kripke.py`'s `_collect()`/`_obj_name()` utilities, which don't exist
  in `el_engine.py` — confirmed exactly equivalent.
- `del_graph`'s per-edge tuple gains `burden_name`/`group_tokens` — the
  structural transfer signals already read off each `Delegation` when the
  graph is built, not re-fetched per candidate.
- `walk_chain()` gains a `token_name` parameter and now returns
  `(chain, sub_delegation_allowed, revocable)` in one call, with the latter
  two taken from whichever `Delegation` produced the walk's *final* hop
  (`False, False` if zero hops occurred) — replacing the separate post-walk
  scan entirely. Matching per hop mirrors `el_kripke.py`'s fallthrough order
  exactly, field by field: neither `transfers_burden` nor
  `transfers_token_group` set → the original free-text substring match
  (AM-54 ground-truth: no scenario in the corpus has a `Delegation` with
  neither field, but the grammar permits it — exercised by a constructed
  probe, `test_free_text_fallback_still_matches_when_delegation_has_no_structural_ref`).
  Otherwise: `transfers_burden` names `token_name` → match. Else (not "or"
  — checked only when the burden field is absent or names a different
  token) `token_name` is a `transfers_token_group` member → match if the
  token has no `Commitment` of its own (e.g. one rooted at
  `ViolationResponse.creates_burden`/`Authorization.auth_burden` instead —
  AM-86/AM-87), otherwise only if the `Commitment`'s own obligation text is
  contained in this `Delegation`'s obligation text (the AM-52 guard, ported
  from `el_kripke.py`). **Correction during review:** an earlier version of
  this fix checked the burden field and, if present, never checked the
  group field regardless of whether it matched `token_name` — reasoning
  that V-NEW-10 makes the two fields mutually exclusive so only one could
  ever be relevant. That reasoning doesn't hold in practice:
  `gp_referral_scenario.el`'s `gpToSpecialistDelegation` violates V-NEW-10
  today (declares both fields; parsed with `validate=False`, so unenforced
  — logged separately, out of scope) and other-group-member matching for
  such a Delegation would have silently broken without the fallthrough.
  Fixed before commit; `test_both_fields_delegation_falls_through_to_group_for_other_member`
  pins it, confirmed to fail against the pre-fallthrough code.
  **No reachability conjunct** (the other half of `el_kripke.py`'s AM-52
  guard) is needed here: `walk_chain()` only ever considers
  `del_graph[current]` — Delegations whose `delegator` *is* the
  already-verified current chain node — so structural continuity from
  `start` is guaranteed by the walk's own construction, not by a separate
  check. Confirmed empirically before deciding this, not assumed: a
  version applying the token_group match unconditionally (no guard at all)
  was prototyped against the full corpus and changed two real descriptors
  in `scenarios/gp_referral/gp_referral_scenario.el`
  (`referralInitiationBurden`/`clinicalHandoverBurden`, which pick up a
  spurious extra hop onto `SpecialistClinician` from incidental
  `referralBurdenGroup` co-membership with `referralResponseBurden`,
  which *is* genuinely transferred by the same `Delegation`) — carrying
  over the text-relevance conjunct (without reachability) gives zero diffs
  across the full corpus and still fixes the repro; this is the version
  implemented. `test_gp_referral_scenario_guard_case_unchanged` pins this
  case directly.
- `outgoing[0]`/now `candidates[0]` is still kept after structural
  filtering — unchanged policy, now documented with a comment: more than
  one structurally-matching outgoing `Delegation` for the same token from
  the same node is ill-formed per §6.4.1/§7.8.7 (a token has exactly one
  active holder) and is currently resolved by declaration order,
  unflagged by the validator. Logged in `docs/CONCEPTS_INDEX.md` as a
  known gap; a validator warning is future work, not part of this
  amendment.

**Standard reference(s):** §6.4.1/§7.8.7 (a `DeonticToken` is held by
exactly one active enterprise object — the reason a single linear chain per
token, not a DAG, is the correct model); §6.6.6/§7.10.1 (Delegation);
V-NEW-10 (`transfers_burden`/`transfers_token_group` mutual exclusion,
which is what makes the `burden_name is not None` branch unconditional).

**`ObligationDescriptor.sub_delegation_allowed`/`.revocable` — stored-data
fix only:** confirmed during AM-88 recon that neither field has any
control-flow consumer today anywhere in `el_engine.py`/`el_kripke.py`
(distinct from `DelegationLink.revocable`, AM-81's separate index, which
*does* gate real T4 revocation and was already correctly per-burden before
this amendment). This fix corrects stored data an agent-facing endpoint
could read in the future; it changes no runtime behaviour today.

**Empirical verification:** byte-identical regression via
`dataclasses.asdict()` against a snapshot of the pre-fix code's output over
every parseable scenario file (`tests/fixtures/am88a_obligation_descriptors_snapshot.json`,
37 descriptors across 14 files at authoring time — `scenarios/ecommerce/ecommerce_scenario.el`
excluded, pre-existing syntax error, unrelated) — zero diffs, confirming
this is a pure bug fix with no behavioural change to any existing scenario.
New `tests/test_am88a_multi_parent_tracing.py` (19 tests: the snapshot
check; Repro 1 and its engine/Kripke parity check, each across all 6
declaration-order permutations of the 3 Delegations involved; Repro 2
across both declaration orders; the free-text fallback probe; the
unconditional-branch probe for a token rooted at `Authorization.auth_burden`
via `transfers_token_group`; the both-fields-Delegation fallthrough probe
(also an engine/Kripke parity check); and the `gp_referral_scenario.el`
guard-case pin). Full suite: 412 passed, 1 xfailed (393/1 baseline + 19
new, zero regressions).

**Portability note (added after a clean-clone failure was reported):** the
37-descriptor gate above included 12 descriptors from four scenario files
under `scenarios/industrial_procedure/` that are untracked/local-only
(excluded via a local `.git/info/exclude` entry, never pushed) — a public
clone only has the 25 descriptors from tracked scenarios. The snapshot
fixture and the test that reads it were fixed to iterate the snapshot's
own file list rather than a local glob, so the pinned gate now covers
exactly those 25 tracked-scenario descriptors regardless of what else
exists in a given checkout; see the follow-up fix commit for detail.

**Files changed:** `toolchain/el_engine.py` (`_commitment_root_for_token()`
new; `del_graph` tuple shape; `walk_chain()` signature and matching logic;
`_add_descriptor()`'s `sub_delegation_allowed`/`revocable` derivation
simplified); new `tests/test_am88a_multi_parent_tracing.py`; new
`tests/fixtures/am88a_obligation_descriptors_snapshot.json`; this file (new
entry); `docs/CONCEPTS_INDEX.md` (new AM-88 findings section).

---

## AM-88b (2026-09-19) — Multi-parent tracing, verifier side: `_delegation_chain_for_token()`'s AM-52 guard becomes a multi-parent search (`toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-19). Completes AM-88 (engine side: AM-88a).

**Problem:** `_delegation_chain_for_token()`'s AM-52 guard — "is this
Delegation's delegator reachable from the token's Commitment actor via
`principal_of` structural edges?" — chased a single pointer through
`structural_parent`, a dict built with `setdefault` (first-declared parent
wins). When one agent had **two** `principal_of` parents, only the
first-declared one was ever considered for the reachability check, so
whether the guard trusted a `transfers_token_group` match at all — and
therefore whether the chain extended past that agent — silently depended
on declaration order.

**Repro (GuardProbe, see `tests/test_am88b_guard_multi_parent_reachability.py`):**
`P1`/`P2` are both `principal_of AgentA`; only `P2` has the `Commitment`
for `burdenT`, transferred onward from `AgentA` to `AgentB` via
`transfers_token_group`. Pre-fix: `_delegation_chain_for_token(model,
"burdenT", "AgentB")` gave `['AgentB']` (guard wrongly rejected the
transfer) when `P1` was declared before `P2`, and the correct
`['P2', 'AgentA', 'AgentB']` when declared the other way round — verified
live in both pre-exec-style direct calls and hybrid mode
(`build_kripke_from_runtime()`).

**What changed** (`toolchain/el_kripke.py`):
- `_commitment_root_for_token()`'s local copy deleted; imports AM-88a's
  version from `el_engine.py` instead (`el_kripke.py`'s import line at the
  top of the file). No behavioural change — the two copies were already
  identical modulo idiom.
- `_is_standing_affiliation()` does **not** move — `el_engine.py` has no
  caller for it (its own `walk_chain()` never crosses `principal_of` edges
  at all; see AM-88a), so relocating unused code buys nothing. It stays in
  `el_kripke.py`, unchanged. `el_reasoner.py`'s independent, pre-existing
  twin of the same name is also untouched — `docs/CONCEPTS_INDEX.md`
  records why unifying it isn't in scope here (nothing in the toolchain
  imports `el_reasoner.py` today except tests, so there's no cycle
  motivating it).
- `_delegation_chain_for_token()` now builds **two** structural-parent
  maps from the same `principal_of` scan, where it previously built one:
  the pre-existing single-valued `structural_parent` (`setdefault`,
  first-declared-wins) is kept **exactly as before**, still driving this
  function's own *final chain-extension* loop at the bottom (deliberately
  out of scope — see below); a new `structural_parents_multi: Dict[str,
  Set[str]]` records **every** `principal_of` parent per agent. The
  guard's local `_reachable()` closure is rewritten from a single-pointer
  chase over `structural_parent` to a BFS over `structural_parents_multi`
  — this is the actual fix.

**Deliberately NOT fixed here, logged instead (`docs/CONCEPTS_INDEX.md`):**
which of an agent's multiple `principal_of` parents the function's
*exported chain* itself continues through (the final
`parent.setdefault(agent_name, principal_name)` loop, using the untouched
single-valued `structural_parent` map) is a separate, narrower,
still-order-dependent question — GuardProbe's own chain is
`['P1', 'AgentA', 'AgentB']` or `['P2', 'AgentA', 'AgentB']` depending on
which party is declared first, even after this fix. What AM-88b fixes is
*whether the transfer is trusted at all* (chain length 3 vs. the wrong,
truncated length-1 `['AgentB']`) — that no longer depends on declaration
order in either case. **Update:** this residual is itself narrowed by
AM-88c below, for the Commitment-rooted case specifically — see that
entry. A token with no Commitment of its own remains genuinely
order-dependent even after AM-88c, by design.

**Standard reference(s):** same as AM-88a — §6.4.1/§7.8.7, §7.10.1
(`principal_of` structural affiliation).

**Empirical verification:** byte-identical regression via
`_delegation_chain_for_token()`'s output for every `(scenario, token)` pair
that has an `ObligationDescriptor`, compared against a pre-fix snapshot
(`tests/fixtures/am88b_delegation_chain_for_token_snapshot.json`, 37 pairs
across 12 files with at least one descriptor) — zero diffs, confirming no
existing scenario exercises the two-`principal_of`-parents case. New
`tests/test_am88b_guard_multi_parent_reachability.py` (6 tests: the
snapshot check; GuardProbe's guard-trust order-independence in both
declaration orders; a direct positive check of the fully correct chain
when the real root is declared first; and the same order-independence
check reached through hybrid mode, `build_kripke_from_runtime()`). Full
suite: 418 passed, 1 xfailed (412/1 AM-88a baseline + 6 new, zero
regressions).

**Files changed:** `toolchain/el_kripke.py` (`_commitment_root_for_token()`
local copy deleted, imported from `el_engine.py` instead;
`_delegation_chain_for_token()` gains `structural_parents_multi` and a BFS
`_reachable()`, `structural_parent`/its final-extension loop unchanged);
new `tests/test_am88b_guard_multi_parent_reachability.py`; new
`tests/fixtures/am88b_delegation_chain_for_token_snapshot.json`; this file
(new entry); `docs/CONCEPTS_INDEX.md` (GuardProbe finding: OPEN →
RESOLVED).

---

## AM-88c (2026-09-19) — `_delegation_chain_for_token()`'s final chain-extension loop prefers the token's own Commitment root over first-declared (`toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-19). Narrows the residual AM-88b left open.

**Problem:** AM-88b fixed the AM-52 guard's *trust* decision (multi-map
BFS reachability), but left the function's separate final chain-extension
loop untouched — it still picked whichever of an agent's multiple
`principal_of` parents was declared first (`structural_parent`,
`setdefault`). For GuardProbe (`P1`/`P2` both `principal_of AgentA`; `P2`
is the real `Commitment` actor for `burdenT`): declaring `P1` first made
the exported chain `['P1', 'AgentA', 'AgentB']` — full length, structurally
plausible-looking, and **wrong**. This is a worse failure mode than
AM-88b's own pre-fix symptom: a visibly truncated `['AgentB']` at least
signals something is missing, where a full-length chain naming the wrong
root gives no signal at all.

**What changed** (`toolchain/el_kripke.py`, `_delegation_chain_for_token()`'s
final extension loop only): when an agent has more than one entry in
`structural_parents_multi` AND the token has its own `Commitment`
(`commitment_root is not None`), the loop now prefers, in order: (1) the
parent that IS the Commitment's actor exactly; (2) failing that, the first
(`sorted()`, for determinism) candidate from which that actor is reachable
via the same BFS `_reachable()` the AM-52 guard already uses. If neither
condition is met, or the token has no `Commitment` at all, the loop falls
back to the pre-existing single-valued `structural_parent` entry
(first-declared-wins) — unchanged. An agent with only one `principal_of`
parent is unaffected either way (there's nothing to choose between).

**Deliberately left open, logged (`docs/CONCEPTS_INDEX.md`):** a token
with NO `Commitment` of its own has no actor to prefer against — for that
case the exported chain genuinely still depends on declaration order,
verified live (`test_no_commitment_multi_parent_token_remains_order_dependent`).
Defaulting to *some* parent there without saying so would be a guess
dressed up as a fix, not a real resolution. Planned resolution: **AM-91**
(not yet scheduled at time of writing) — a `[W-16e]` warning for an agent
with ≥2 `principal_of` parents, naming them (sorted) and noting that the
exported chain for a Commitment-less token among them names only one,
*plus* a sorted-first deterministic fallback in
`_delegation_chain_for_token()` itself (replacing today's first-declared-
wins, so the chosen parent is at least stable rather than order-dependent,
while the warning makes the ambiguity visible rather than silent). Not
scoped to AM-88c.

**Standard reference(s):** same as AM-88a/b — §6.4.1/§7.8.7 (a token's
holder — and, by extension here, its accountability chain — should not be
ambiguous); §7.10.1 (`principal_of` structural affiliation).

**Empirical verification:** byte-identical regression against the AM-88b
snapshot (`tests/fixtures/am88b_delegation_chain_for_token_snapshot.json`,
same 37 pairs) — zero diffs. **Correction (found during AM-91 recon):** an
earlier version of this note claimed no existing scenario has an agent
with more than one `principal_of` parent — imprecise.
`scenarios/consent/federation_consent_scenario.el`'s `SpecialistParty`
does have two standing `principal_of` parents (`GPParty`,
`SpecialistPracticeParty`). The byte-identical regression holds anyway,
for a different reason: `SpecialistParty` (and the file's only other
structural child, `AISpecialistAgent`) is *also* the delegate of a real
`Delegation`, which sets `parent[to] = frm` unconditionally, before this
function's final-extension loop even runs — `parent.setdefault(...)` is
therefore a no-op for both, regardless of which fallback rule the loop
uses. This scenario's chain output has never depended on, and still
doesn't depend on, this fix. New `tests/test_am88c_multi_parent_chain_extension.py` (6 tests: the
snapshot check; GuardProbe's full-chain order-independence, direct and
hybrid, both declaration orders; and the no-Commitment residual, asserted
as still order-dependent by design, not a bug). Full suite: 424 passed, 1
xfailed (418/1 AM-88b baseline + 6 new, zero regressions).

**Files changed:** `toolchain/el_kripke.py`
(`_delegation_chain_for_token()`'s final extension loop only); new
`tests/test_am88c_multi_parent_chain_extension.py`; this file (AM-88b
entry's "Deliberately NOT fixed" note updated to cross-reference this
entry; new AM-88c entry); `docs/CONCEPTS_INDEX.md` (residual: RESOLVED for
Commitment-rooted tokens, OPEN for tokens without one).

---

## AM-89 (2026-09-19) — validator warnings channel: `ParseResult.warnings` (`toolchain/el_parser.py`)

**Status:** IMPLEMENTED (2026-09-19).

**Problem:** `el_validator.validate_spec()` returns one flat `List[str]`
mixing genuine errors (`[V-...]`/`[V-NEW-...]`) and advisory warnings
(`[W-...]` — today, only `[W-16b]`, singleton `SatisfactionCondition`,
AM-29). `el_parser.parse()` extended `ParseResult.errors` with that entire
list, and `ParseResult.ok` was `len(self.errors) == 0` — so a spec
triggering only a warning, with zero genuine errors, still made `.ok`
`False`. Confirmed live: a `Community` whose `Objective` declares
`satisfaction: all_discharged(singleToken)` (no `TokenGroup` needed —
grammar's inline form) produces exactly one `[W-16b]` message and nothing
else; `parse()` on it pre-fix returned `ok=False`, `errors=["[W-16b] ..."]`,
with `.model` still populated (validation happens after `result.model` is
set, so the model itself was never discarded — only `.ok` was wrong).

Every consumer that gates on `.ok` would refuse that spec: 134 test-suite
call sites of the `assert result.ok, result.errors` pattern (115 of the
suite's 158 total `parse()`/`parse_string()` call sites actually run the
validator, explicitly or via the `validate=True` default), plus
`el_reasoner.py`'s and `fhir_mapper.py`'s CLI entry points (both parse with
the default `validate=True`). Recon confirmed no tracked scenario triggers
this today (scanned all 11 tracked `.el` files with `validate=True`, zero
`[W-` output) — the bug was entirely latent, not yet a live regression, but
a future warning-producing rule (a planned multi-parent-authority-join
warning is out of scope for this amendment) would hit it immediately.
`el_api.py` is unaffected either way: all 5 of its `parse()` calls already
pass `validate=False`, so `validate_spec()` never runs there regardless of
this fix — recon confirmed no HTTP endpoint surfaces validation messages
to a caller today either.

**What changed** (`toolchain/el_parser.py`):
- `ParseResult` gains `warnings: List[str] = field(default_factory=list)`.
  Confirmed before adding it: exactly one construction site exists in the
  whole codebase (`el_parser.py`'s own `parse()`, no-arg `ParseResult()`),
  so the new defaulted field breaks nothing.
- `parse()`'s validation step now partitions `validate_spec()`'s return by
  the existing `"[W-"` prefix — `.errors` gets everything else, `.warnings`
  gets the rest. `validate_spec()` itself is **completely unchanged**: same
  signature, same flat `List[str]` return, same ~17 internal rule
  functions, zero edits to `el_validator.py`. `.ok` needed no code change —
  it was already `len(self.errors) == 0`; warnings are simply never placed
  there.
- Routing choice (prefix vs. a structured severity field on every rule
  function's return): prefix, because it keeps `validate_spec()`'s
  contract untouched and matches the convention `el_parser.py` already
  uses for `[SYNTAX]`/`[SEMANTIC]`/`[PARSE ERROR]` — a structured-severity
  refactor would touch every rule function in `el_validator.py` for no
  benefit this amendment needs.

**What changed** (the two CLI entry points that parse with `validate=True`
by default): `el_reasoner.py`'s and `fhir_mapper.py`'s `__main__` blocks
now print `result.warnings` to stderr, unconditionally, before checking
`.ok` — a warning-only spec is both reported and no longer aborted.
`fhir_mapper.py`'s validate-and-report step was extracted into a new
module-level `_print_parse_report(el_path)` function (identical logic,
now callable in isolation) purely so it's unit-testable directly: the
mapper's own generated output never contains a `satisfaction:` clause, so
it can never exercise a `[W-` warning through the normal bundle-mapping
pipeline — testing the fix required parsing a hand-written probe file
directly rather than running the full FHIR pipeline. `el_reasoner.py`
needed no such extraction — its `--policy-conflicts` CLI mode is already a
clean, deterministic subprocess target.

**Standard reference(s):** none — this is tooling/diagnostics
infrastructure, not a grammar or accountability-semantics change; no ISO
clause governs how a toolchain reports its own validation messages.

**Empirical verification:** full suite 433 passed, 1 xfailed (424/1
baseline + 9 new, zero regressions), reproduced identically on a clean
`git worktree add` checkout with the diff applied (not just the normal
working tree — the AM-88 portability lesson). New
`tests/test_am89_warnings_channel.py` (9 tests): a warning-only spec is
`ok` with the warning isolated in `.warnings`; a genuine error alongside
the same warning splits correctly into `.errors`/`.warnings` with no
cross-contamination; `validate_spec()` called directly still returns the
old unsplit flat list (pins that the split is `parse()`-only); a
warning-only spec loads through `Runtime.build_from_spec()` (the actual
`validate=True`-by-default entry point a spec author's tooling goes
through — not an `el_api.py` path, since none of `el_api.py`'s `parse()`
calls validate); the two named, tracked reference scenarios
(`referral_scenario.el`, `consent_scenario.el` — no glob, so this can never
depend on a local-only file) produce zero warnings; both CLI fixes,
verified via subprocess (`el_reasoner.py`) and direct call with `capsys`
(`fhir_mapper.py`'s extracted function) for both the warning-only case
(stderr has the warning, exit/success unaffected) and a genuine-error case
(still reported, still fails, to guard against the fix accidentally
swallowing real errors).

**Files changed:** `toolchain/el_parser.py` (`ParseResult.warnings`,
`parse()`'s partitioning, docstring); `toolchain/el_reasoner.py` (`__main__`
prints warnings); `toolchain/fhir_mapper.py` (`_print_parse_report()`
extracted, prints warnings); new `tests/test_am89_warnings_channel.py`;
this file (new entry); `docs/CONCEPTS_INDEX.md` (new note: warnings channel
exists; no API/UI validation surface exists to update).

---

## AM-90 (2026-09-19) — multi-parent authority join: `[W-16c]`/`[W-16d]` warnings, shared `parents_of()` query (`toolchain/el_reasoner.py`, `toolchain/el_validator.py`)

**Status:** IMPLEMENTED (2026-09-19). Builds on AM-89's warnings channel
(`ParseResult.warnings`, `56939b9`) — both new rules are advisory and never
affect `.ok`.

**Design settled beforehand (not re-litigated here):** multi-parent
authority is legitimate per §7.10.1 ("the parties (collectively) become
principal of that object"); the toolchain enumerates parents and never
stays silent about the structure, but composing overlapping authorities
across parents is application-defined — the toolchain does not do it.
Per §6.4.1/§7.8.7 a token is still held by exactly one active object, so
its own delegation chain stays linear (the AM-88 series); multi-parent is
a property of the *agent*, not the per-token chain.

**New public query** (`toolchain/el_reasoner.py`):
- `ParentRecord` (parent, delegation_name, tokens, sub_delegation_allowed,
  revocable) and `CoGrantedAuthorization` (authorization_name, authority,
  permit) — two small dataclasses.
- `parents_of(model, agent_name) -> (List[ParentRecord], List[CoGrantedAuthorization])`
  — every genuine `Delegation` naming `agent_name` as its `delegate`, plus
  every `Authorization` granting it a permit via `to_agent`. Built entirely
  on `delegation_graph()`'s already-extracted per-`Delegation` fields
  (`burden_name`, `token_group_members`, `sub_delegation_allowed`,
  `revocable`) — no new `getattr(d, "burden"/"token_group")` expansion
  anywhere, so this is not a third copy of that extraction (`el_engine.py`'s
  `walk_chain()` and `el_kripke.py`'s `_delegation_chain_for_token()` each
  already do it once). Deterministic and fully sorted (`ParentRecord`s by
  `(parent, delegation_name)`, each record's own `tokens` sorted,
  `CoGrantedAuthorization`s by `authorization_name`). An unknown
  `agent_name` returns `([], [])`, never raises. Documented out of scope,
  matching the design decision: structural `principal_of` affiliations
  with no `Delegation` of their own (`delegation_graph()`'s
  `link.structural`), and `to_role` Authorizations (no single resolved
  agent to attribute them to).

**Two new validator rules** (`toolchain/el_validator.py`), both built from
`parents_of()`/`delegation_graph()` directly — no independent
re-derivation, so the warning text and the public query can never diverge:

- `[W-16c]` **multi-parent notice** — fires when an agent's *distinct*
  parent count (via `parents_of()`) is ≥2 (delegation count doesn't
  matter: one delegator with two Delegations to the same delegate does
  **not** fire). Message groups by parent (sorted `(parent,
  delegation_name)`), each parent showing every one of its Delegations as
  `delegation -> tokens` joined by `"; "` when a parent has more than one;
  parents joined by `", "`. Co-granted Authorizations render in a
  **separate** sentence, worded as authority *sources*, not principals
  (AM-31 §4.0b: an authorizing party does not thereby become a
  co-principal) — omitted entirely when there are none. Ends with a
  pointer to the query itself. Full shape:

  `[W-16c] Agent 'X' has 2 parents: P1 (d1 -> t1), P2 (d2 -> t2). Principals are collectively responsible (§7.10.1). If these parents' authorities overlap, how they combine is application-defined; the toolchain does not compose them. Permits granted to 'X' (authority sources, not necessarily principals): A1 (P1: p1). See el_reasoner.parents_of(model, 'X').`

- `[W-16d]` **same-token conflict** — one token (burden or a
  `token_group` member, deduped per `Delegation` via the same set-union
  `parents_of()` uses — this is exactly what stops a single `Delegation`
  declaring both `transfers_burden` and a `transfers_token_group`
  containing that same token, a real V-NEW-10 violation
  `gp_referral_scenario.el` has, from flagging itself) transferred by ≥2
  distinct Delegations to the same delegate (double-source), or by the
  same delegator to ≥2 different delegates (fork). Grouping by
  `(token, delegate)` and `(token, delegator)` separately means a
  sequential chain (`P→A`, then `A→B` carrying the same token onward)
  never trips this — each hop's transferred-token set is scoped to its
  own `Delegation`, never conflated across hops.

**Standard reference(s):** §7.10.1 (multi-parent principal accountability
— `[W-16c]`); §6.4.1/§7.8.7 (one holder per token — the reason `[W-16d]`
flags an ambiguous transfer as advisory rather than silently picking one);
AM-31 §4.0b (an authorization's authority is a source, not a principal —
the reason the co-granted-authorizations clause is worded and placed
separately from the principals sentence).

**Import graph:** confirmed cycle-free before writing any code —
`el_reasoner.py` has zero internal toolchain imports at module level (its
two `from el_parser import parse` occurrences are inside
`if __name__ == "__main__":` or a docstring example, never executed on a
normal `import el_reasoner`), and nothing internal imports `el_reasoner.py`
today except tests. `el_validator.py` adding
`from el_reasoner import delegation_graph, parents_of` is therefore a
one-directional edge with no cycle — same shape as the already-established
`el_kripke.py → el_engine.py` edge.

**Empirical verification:** ran both rules' actual trigger conditions
against every tracked `.el` file (`git ls-files scenarios`, `validate=True`)
— zero `[W-16c]`/`[W-16d]` anywhere (`scenarios/ecommerce/ecommerce_scenario.el`
still unparseable, unaffected, same pre-existing syntax error).
Order-invariance verified live across all 6 permutations of a 2-Delegation
probe and, separately, all 24 permutations of a combined
2-Delegation-plus-2-Authorization probe — identical warning string every
time in both cases. New `tests/test_am90_multi_parent_warnings.py` (14
tests): the Repro-1-shaped multi-parent probe (exact message, then
order-invariance across all permutations); single-parent chain and
one-delegator-two-delegations negatives for `[W-16c]`; a `principal_of`-only
negative (documented out-of-scope case); the both-fields-Delegation
self-flag negative for `[W-16d]`; double-source and fork positives for
`[W-16d]`; `parents_of()` on an unknown agent; `parents_of()`'s output
checked to contain every string fragment the `[W-16c]` message uses (no
twin logic); a third-authority-not-a-delegator case (authority-sources
clause only, never counted as a parent); the one-parent-two-delegations
grouping case; the two named tracked reference scenarios (no glob); and
that warnings never affect `.ok`. Full suite: 447 passed, 1 xfailed (433/1
AM-89 baseline + 14 new, zero regressions) — reproduced identically on a
clean `git worktree add` checkout with the diff applied.

**Files changed:** `toolchain/el_reasoner.py` (`ParentRecord`,
`CoGrantedAuthorization`, `parents_of()`, module docstring); `toolchain/el_validator.py`
(`_validate_multi_parent_notice()`, `_validate_same_token_conflict()`,
dispatch wiring, module docstring, `Tuple` import); new
`tests/test_am90_multi_parent_warnings.py`; this file (new entry);
`docs/CONCEPTS_INDEX.md` (new AM-90 note).

---

## AM-91 (2026-09-19) — standing `principal_of` multi-parent: `[W-16e]` warning and a deterministic verifier fallback (`toolchain/el_reasoner.py`, `toolchain/el_validator.py`, `toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-19). Closes the residual AM-88c/AM-90 left
open (`docs/CONCEPTS_INDEX.md`).

**Problem:** AM-90's `[W-16c]` counts only genuine `Delegation`-based
parents; structural `principal_of` affiliations are documented out of
scope there. That left an agent with ≥2 STANDING `principal_of` parents
(a one-sided structural affiliation, not paired with `delegated_from` —
`el_reasoner._is_standing_affiliation()`), where a token among them has no
`Commitment` of its own, BOTH order-dependent (the AM-88c residual —
`el_kripke._delegation_chain_for_token()`'s final chain-extension fell
back to first-declared when no Commitment anchored the choice) AND
unwarned.

**Recon finding, not zero:** scanning all 11 tracked `.el` files for
agents with ≥2 distinct standing structural links found ONE real hit:
`scenarios/consent/federation_consent_scenario.el`'s `SpecialistParty`
(parents `GPParty`, `SpecialistPracticeParty`). Traced empirically, not
assumed: this file's only descriptor (`seekConsentObligation`) is
Commitment-rooted at a third, fully disconnected party
(`GPPracticeParty`), so `_delegation_chain_for_token()`'s walk never
reaches `SpecialistParty` at all — AM-91's fallback change produces zero
diff on this file's `am88b_delegation_chain_for_token_snapshot.json`
entry. Separately, `SpecialistParty` (and the file's only other
structural child, `AISpecialistAgent`) is *also* the delegate of a real
`Delegation`, which sets that agent's `parent[to] = frm` unconditionally
before the fallback loop runs — `parent.setdefault(...)` is therefore a
no-op regardless of which fallback rule is used. Confirmed this is the
*only* multi-standing-parent case anywhere in the tracked corpus, so the
byte-identical snapshot gate holds for the entire corpus, not just this
one file. `[W-16e]` still fires on this file, correctly — its trigger is
independent of chain-reachability; see the new test pinning this exact
case as a true positive.

**What changed** (`toolchain/el_reasoner.py`):
- `standing_parents_of(model, agent_name) -> List[str]` — every standing
  `principal_of` parent of `agent_name`, sorted, built entirely on
  `delegation_graph()`'s existing `link.structural=True` entries (no
  separate `principal_of`/`_is_standing_affiliation` scan — confirmed by
  inspection during recon that this produces the identical parent set
  `el_kripke.py`'s own inline `structural_parents_multi` computes, since
  both share byte-identical `_is_standing_affiliation` bodies and
  identical `EnterpriseObject`/`principal_of` iteration). Returns every
  standing parent found (0, 1, or more) — the ≥2 threshold is the
  caller's decision, matching `parents_of()`'s shape. Unknown `agent_name`
  returns `[]`, never raises.

**What changed** (`toolchain/el_validator.py`):
- `[W-16e]` (`_validate_standing_multi_parent_notice()`) — an agent with
  ≥2 distinct standing `principal_of` parents. Built entirely from
  `standing_parents_of()` — message and query share the same data by
  construction. Advisory (AM-89 channel), never affects `.ok`.
  Independent of `[W-16c]`: an agent can trigger either, both, or
  neither, depending on which kind of parent edge it has (verified by a
  dedicated test constructing an agent with two of each, disjoint).
  Message: `[W-16e] Agent 'X' has N standing principal_of parents: P1,
  P2. For a token with no Commitment of its own, chain-based views name
  one of them (the first alphabetically); the choice is stable but
  arbitrary. Which parent's authority applies is application-defined. See
  el_reasoner.standing_parents_of(model, 'X').`

**What changed** (`toolchain/el_kripke.py`, `_delegation_chain_for_token()`'s
final chain-extension loop): when an agent has >1 `principal_of` parent
and no Commitment-anchored choice exists (no `Commitment` at all, or the
Commitment's actor is neither an exact candidate nor reachable), the
fallback is now `sorted(candidates)[0]` instead of `structural_parent[agent_name]`
(first-declared). Single-parent agents and every Commitment-anchored case
are unaffected — the new branch only replaces the *last-resort* fallback.
**Message/behaviour parity, enforced by test, not just documented:**
`tests/test_am91_standing_parent_warnings.py`'s dedicated parity test
asserts, across every declaration-order permutation, that the fallback's
actual choice equals `sorted(standing_parents_of(model, agent))[0]` — the
exact claim `[W-16e]`'s "first alphabetically" wording makes. This is
what stops the message and the fallback from silently diverging if either
is ever changed independently.

**Correction to an earlier amendment entry (found during this amendment's
own recon):** AM-88c's "no existing scenario has an agent with more than
one `principal_of` parent" framing was imprecise —
`federation_consent_scenario.el` does have one. That entry is corrected
above with the actual reason the byte-identical gate held regardless (the
real-`Delegation`-wins-first argument, not scenario absence). AM-88b's
own, narrower claim (that no scenario *exercises the AM-52 guard* under
two `principal_of` parents) is unaffected by this correction — that guard
only engages for a `transfers_token_group` `Delegation`, and this file has
none.

**Standard reference(s):** §7.10.1 (`principal_of` structural
affiliation, multi-parent collective responsibility — same basis as
`[W-16c]`); §6.4.1/§7.8.7 (one holder per token — the reason an ambiguous
fallback choice is flagged rather than silently trusted).

**Import graph:** confirmed cycle-free before writing any code, same
argument as AM-90 — `el_reasoner.py` still has zero internal toolchain
imports at module level; `el_validator.py` adding `standing_parents_of`
to its existing `from el_reasoner import delegation_graph, parents_of`
line is a one-directional edge with no cycle.

**Empirical verification:** ran the `[W-16e]` trigger condition against
every tracked `.el` file — exactly the one real hit above, nothing else.
Byte-identical regression against `tests/fixtures/am88b_delegation_chain_for_token_snapshot.json`
(25 pairs, current public snapshot) — zero diffs, confirming AM-91's
fallback change is inert for the entire tracked corpus. Order-invariance
verified across all permutations of a 3-party standing-parent probe —
identical `[W-16e]` string every time. New
`tests/test_am91_standing_parent_warnings.py` (13 tests): the `[W-16e]`
message and its order-invariance; the message/behaviour parity test
described above; a single-standing-parent negative; a paired
`principal_of`+`delegated_from` negative (must not count as standing); a
`Delegation`-only negative (`[W-16c]` fires, `[W-16e]` does not); a
both-kinds-at-once positive (both warnings, independently); `standing_parents_of()`
output-matches-message and unknown-agent checks; the two named tracked
reference scenarios (unchanged); the one real corpus hit
(`federation_consent_scenario.el`, exact string pinned); warnings never
affect `.ok`; and `validate_spec()`'s own unsplit-list contract. Also
updated: `tests/test_am88c_multi_parent_chain_extension.py`'s residual
test, renamed from `..._remains_order_dependent` to
`..._is_now_order_independent` and re-asserted (both declaration orders
now give `["P1", "AgentA", "AgentB"]`); `tests/test_am90_multi_parent_warnings.py`'s
principal_of-only test, renamed and narrowed to assert only that `[W-16c]`
does not fire (it no longer asserts zero warnings overall, since
`[W-16e]` now correctly fires on that exact shape). Full suite: 461
passed, 1 xfailed (448/1 AM-90 baseline + 13 new, zero regressions) —
reproduced identically on a clean `git worktree add` checkout with the
diff applied.

**Files changed:** `toolchain/el_reasoner.py` (`standing_parents_of()`,
module docstring); `toolchain/el_validator.py`
(`_validate_standing_multi_parent_notice()`, dispatch wiring, module
docstring); `toolchain/el_kripke.py` (`_delegation_chain_for_token()`'s
final extension loop, `sorted(candidates)[0]` fallback branch); new
`tests/test_am91_standing_parent_warnings.py`; updated
`tests/test_am88c_multi_parent_chain_extension.py` and
`tests/test_am90_multi_parent_warnings.py` (see above); this file (AM-88c
entry corrected, new AM-91 entry); `docs/CONCEPTS_INDEX.md` (residual:
RESOLVED by AM-91; new AM-91 section).

---

## AM-92 (2026-09-19) — V-08 sub-delegation check becomes token-aware and order-independent (`toolchain/el_validator.py`)

**Status:** IMPLEMENTED (2026-09-19). Closes §7 step 3 of DN_017.

**Problem:** V-08 (`_validate_delegations()`) used `_find_parent_delegation()`,
which returned the FIRST `Delegation` in declaration order whose `delegate`
matched the sub-delegating agent — ignoring which token was actually being
passed on, and ignoring every other incoming `Delegation`. With ≥2 distinct
incoming `Delegation`s to one agent, the verdict depended on which was
declared first.

**Repro:** `FinanceParty`/`LegalParty` each commit a burden into
`SettlementAgent` via their own `Commitment` (`finDel` permits
sub-delegation, `legDel` doesn't); `SettlementAgent` sub-delegates only
`FinanceParty`'s burden (`settleBurdenA`) onward via `subDel`. Pre-fix,
declaring `finDel` before `legDel` gave `ok` (correct); swapping the two
gave a false positive naming `legDel` — the WRONG delegation, since
`subDel` never touched `legDel`'s token (`settleBurdenB`) at all. Passing
on `settleBurdenB` instead should error in **both** orders, naming `legDel`.

**What changed:**
- `_validate_delegations()` gains a `model` parameter (its only caller,
  `validate_spec()`, already has it), used to build one
  `el_reasoner.delegation_graph(model)` call shared across every
  `Delegation` in the loop — not a fourth copy of token-extraction logic.
- V-08 itself is extracted into `_validate_sub_delegation()`, called once
  per agent-delegator `Delegation`. Algorithm:
  - **S1 (token-aware):** for each token `d` structurally transfers
    (`transfers_burden`, or its `transfers_token_group`'s members — read
    off `delegation_graph()`'s already-extracted `DelegationLink.burden_name`/
    `.token_group_members`, never re-derived from `getattr(d, "burden"/
    "token_group")` again), find the incoming, genuine (non-structural)
    `Delegation`(s) to `d`'s delegator that structurally name that same
    token. Any of them with `sub_delegation_allowed=false` is a genuine
    violation for that token.
  - **S2 (conservative fallback):** when a token is named by NO incoming
    `Delegation` at all, or `d` has neither `transfers_burden` nor
    `transfers_token_group` set, every incoming `Delegation` to the agent
    must permit sub-delegation, regardless of what it transfers — the
    pre-AM-92 check, kept as the fallback rather than replaced.
  - **S3 (order-independent by construction):** "the incoming Delegations
    to this agent" is a pre-built structural index
    (`incoming_by_agent: Dict[str, List[DelegationLink]]`), not "the
    first" one found by scanning — there is no first, only the set.
  - **Deduplication:** one error per `(d, forbidding parent Delegation)`.
    When one parent forbids several of `d`'s tokens, **all** of them are
    named, sorted and comma-joined, in a single error — not one error per
    token (tweak from the original proposal, which had suggested naming
    only the sorted-first token; rejected in favour of naming all of them).
- `_find_parent_delegation()` deleted — confirmed its only caller was V-08
  itself, and no test referenced it directly.

**Message formats — deliberately different by branch:**
- S1 match: `[V-08] Delegation 'subDel': agent 'SettlementAgent' attempts
  to sub-delegate 'settleBurdenB' but parent delegation 'legDel' has
  sub_delegation_allowed=false. (§7.10.1)` — names the token(s)
  (`'A', 'B'` when several map to the same forbidding parent).
- S2 fallback: `[V-08] Delegation 'X': agent 'Y' attempts to sub-delegate
  but parent delegation 'Z' has sub_delegation_allowed=false. (§7.10.1)`
  — **byte-identical to the pre-AM-92 message**, no token named. For a
  single-parent agent whose token happens to match structurally, S1's
  branch is taken instead and the message *does* gain a token name — a
  deliberate, approved change from the pre-AM-92 wording, since no test
  or consumer depended on V-08's exact string before this amendment
  (confirmed during recon: `_find_parent_delegation` and V-08's message
  text were referenced nowhere except a descriptive "out of scope" note
  in `tests/test_am89_warnings_channel.py`'s docstring).

**Deliberate scope boundary, not an oversight:** an incoming `Delegation`
with NEITHER `transfers_burden` nor `transfers_token_group` set can never
S1-match a specific token — it has no structural token to match against,
so it only ever participates in the S2 fallback. If some OTHER incoming
Delegation structurally matches a token and permits it, a neither-field
incoming Delegation to the same agent does **not** block that token, even
though it itself forbids sub-delegation in general. S2 is reached only
when NO incoming `Delegation` makes any structural claim on the token at
all — this is conservative-on-single-parent by design, matching S2's own
"identical to today's verdict" requirement for that case, not a gap.

**Standard reference(s):** §7.10.1 (sub-delegation requires the parent
delegation's explicit permission — unchanged; only *which* parent is
consulted, and *how many*, changes).

**Empirical verification:** ran the OLD and proposed verdicts side by
side over every tracked `.el` file (`git ls-files scenarios`,
`validate=True`) — **zero differences anywhere**; the tracked corpus has
exactly two real agent-delegator sub-delegation chains
(`consent_scenario.el`'s `specialistToAIDelegation`,
`generated_governance.el`'s `TaskAiAgent001Delegation`), both single-parent
with the sub-delegated token exactly matching the sole incoming
Delegation's own token — so S1 and S2 collapse to the identical check in
both live cases; neither exercises genuine multi-parent disambiguation.
Live repro verified in all 6 declaration-order permutations, both token
choices (`settleBurdenA` → no error anywhere; `settleBurdenB` → identical
`legDel`-naming error everywhere). New `tests/test_am92_v08_token_aware.py`
(14 tests): the repro (both token choices, all permutations); single-parent
forbidden (error, message now names the token) and permitted (ok); an
agent with no incoming Delegation at all (ok); group-transfer-permitted
(ok); the S2 neither-field fallback with one of two parents forbidding,
byte-identical message, both orders; the both-fields dedup case (one
error naming both tokens); party-delegator (never checked); the
deliberate scope-boundary case (a neither-field incoming Delegation does
not block a token another incoming Delegation structurally permits); a
multi-error spec, asserting the SET of `[V-08]` strings is identical
across every declaration-order permutation of all four Delegations
involved; a spot-check that `[W-16c]` (present) and `[W-16d]`/`[W-16e]`
(absent) are unaffected by a spec that also triggers V-08;
`validate_spec()`'s new-signature call still returns a flat list; the two
named tracked reference scenarios (unchanged, no V-08). Full suite: 475
passed, 1 xfailed (461/1 AM-91 baseline + 14 new, zero regressions) —
reproduced identically on a clean `git worktree add` checkout with the
diff applied.

**Files changed:** `toolchain/el_validator.py`
(`_validate_delegations()` gains `model` parameter; `_validate_sub_delegation()`
new, replacing the inline V-08 block; `_find_parent_delegation()` deleted;
module docstring rule list updated); new
`tests/test_am92_v08_token_aware.py`; this file (new entry);
`docs/CONCEPTS_INDEX.md` (new AM-92 note).

---

## AM-93 (2026-09-20) — `delegated_from` as a list (`grammar/v2/el_grammar.tx`, `toolchain/el_parser.py`, `toolchain/el_domain.py`, `toolchain/el_reasoner.py`, `toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-20). Type: AM (grammar). Closes §7 step 5
of DN_017. **Declarative only** — it lets an agent list several delegators;
it adds no composition semantics.

**Problem:** `ObjectBody` allowed at most one `delegated_from`
(`(delegated_from=DelegatedFrom)?`), so a second line was a syntax error,
although §7.10.1 says the parties (collectively) become principal of the
agent they delegate to. Both `_is_standing_affiliation` twins
(`el_reasoner.py`, `el_kripke.py`) read that single value.

**What changed:**
- **Grammar:** `ObjectBody` becomes `(delegated_from+=DelegatedFrom)*`, same
  position (after `holds`, before `principal_of`). The `DelegatedFrom` rule
  itself, including its per-entry optional `duration`, and its
  `delegator=[EnterpriseObject]` typing are unchanged. Every existing spec
  parses exactly as before.
- **Model shape (decided by the maintainer):** `EnterpriseObject.delegated_from`
  is now a `List[DelegatedFrom]` — one record per line, `.delegator` and
  `.duration` kept together. Parser processor P2 keeps the entries
  (`obj.delegated_from = list(obj.body.delegated_from)`), unlike
  `principal_of`, whose wrapper is dissolved to bare refs — the difference
  is deliberate: `DelegatedFrom` has a second field. `delegation_duration`
  is removed (it had no reader anywhere). An absent duration is still `''`
  (the textX default), and an object with no entries now has `[]` where it
  had `None`. Rejected: a parallel durations list (index alignment, a
  second attribute to keep in sync) and a compatibility shim exposing "the
  first entry" (it would reintroduce the single-valued reading this
  amendment removes).
- **Both twins, identically:**
  `return not any(_obj_name(entry.delegator) == principal_name for entry in getattr(agent, "delegated_from", None) or ())`.
  A `principal_of` is standing iff that principal is not among ANY entry's
  delegator. Single entry: same result as before; no entries: standing, as
  before.

**Semantics — set, not sequence:** the twins treat the entries as a set, so
declaration order makes no difference, and **a delegator listed twice in
one object parses and is accepted as written** — no de-duplication, no new
rule, no warning; both entries are kept, each with its own duration.

**Why the twin change is mandatory, not tidy-up:** with a list-valued
attribute and the twins unchanged, `_obj_name(list)` returns `None`, so
`None != principal_name` is true and every paired `principal_of` is
silently classed as standing. Observed in a throwaway prototype: two
false `[W-16e]` warnings, each counting a principal that was paired via
`delegated_from` as if it were standing. Nothing raises; the output is
just wrong. The parity truth-table test and
the all-paired test below pin exactly this.

**Deliberately untouched (out of scope):** how multi-parent structure is
otherwise detected (`parents_of()`, `[W-16c]`/`[W-16d]`/`[W-16e]`, V-08 all
work from Delegations / `principal_of`, not from `delegated_from`); any
child-side "complete parent set" cross-check; composition semantics; the
`[Party]`-typing question for `DelegatedFrom.delegator` (open finding in
`docs/CONCEPTS_INDEX.md`); unifying the two twins (still independent
copies, per the no-cross-import convention); the FHIR mapper (below);
`scenarios/ecommerce/ecommerce_scenario.el` (not edited).

**FHIR mapper — no change needed.** It has its own `ELObject.delegated_from:
Optional[str]` and emits at most one `delegated_from` line, which is valid
under the new grammar. Its first-wins `_set_delegated_from` would drop a
second delegator, but no agent in any spec it produced — 85 captured (all
bundle fixtures plus every spec built inside the mapper-related tests) — is
the delegate of two distinct delegators. Regenerated
`generated_governance.el` is byte-identical (existing golden test).

**Standard reference(s):** §7.10.1 ("the parties (collectively) become
principal of that object"); §6.6.8 NOTE 3 (static initial delegation) —
unchanged, now allowed more than once.

**Verification:** new `tests/test_am93_delegated_from_list.py` (17 tests,
inline specs and named tracked files only): a single entry (model shape,
duration `''` when absent, duration kept, no `delegation_duration`);
objects with no entries (`[]`); two entries with durations on none / first
/ second / both; position between `holds` and `principal_of`;
`principal_of` before `delegated_from` still a syntax error; a duplicated
delegator accepted with both entries kept; a truth table over every
ordered delegator sequence of length 0–3 over {A,B,C} (40 agents) x four
principals, asserting BOTH twins agree with each other and with set
membership (plus agents with no attribute, `None`, `[]`); a `principal_of`
paired with ANY of two delegators non-standing in both declaration orders
(unpaired one standing, no `[W-16e]`); all principals paired → no standing
parent and no warning; unpaired principals standing alongside a paired one
(`[W-16e]` names them); the three named scenarios (`referral_scenario.el`,
`consent_scenario.el`, `federation_consent_scenario.el`) unchanged in
warnings, with their single entries. Two mutation checks in scratch copies
were both caught: a reasoner twin reading only the first entry (4 test
failures) and a verifier twin left on the old single-valued logic (the
parity truth table fails). Errors and warnings of the three named
scenarios are byte-identical before and after. Full suite: 492 passed, 1
xfailed (475/1 baseline + 17 new, zero regressions).

**Ecommerce, recorded as found (no edit):** with this grammar change alone
`scenarios/ecommerce/ecommerce_scenario.el` still does not parse — its
first error moves from the second `delegated_from` to a stale
`sub_delegation_allowed:` line in an object body, and beyond that lie
pre-AM-17 constructs in community, role, permit, embargo and commitment
bodies, `--` comments, and a `delegated_from Customer` that references an
object declared nowhere. See the open item in `docs/CONCEPTS_INDEX.md`.

**Files changed:** `grammar/v2/el_grammar.tx` (`ObjectBody`; `DelegatedFrom`
comment); `toolchain/el_parser.py` (P2); `toolchain/el_domain.py`
(`DelegatedFrom` docstring; `ObjectBody.delegated_from` and
`EnterpriseObject.delegated_from` to `List`; `delegation_duration`
removed); `toolchain/el_reasoner.py` and `toolchain/el_kripke.py`
(`_is_standing_affiliation`, identical bodies; reasoner docstring);
new `tests/test_am93_delegated_from_list.py`; this file (new entry);
`docs/CONCEPTS_INDEX.md` (new AM-93 note and the ecommerce open item).

---

## AM-94 (2026-09-20) — `[W-16f]`: an Action leaves a co-granting authority unconsulted (`toolchain/el_reasoner.py`, `toolchain/el_validator.py`)

**Status:** IMPLEMENTED (2026-09-20). Type: V-NEW (validator warning); no
grammar change. Closes §7 step 6 of DN_017 ("V-J1"). Advisory, never an
error; routed through the AM-89 warnings channel.

**Problem — the substitution failure on the permit side:** an agent (or
role) is authorized by two distinct authorities, each granting its own
permit, and an Action requires only one authority's permit. The other
authority is never consulted, and the Action still runs if that
authority's authorization is revoked. Composition of such authorities is
application-defined; the toolchain only flags the omission.

**What changed:**
- **Three public read-only queries in `el_reasoner.py`** (records:
  `PermitGrant`, `CoGrantedPermitSet`, `ActionPermitRequirement`,
  `OmittedAuthority`, `PermitOmission`):
  - `co_granted_permit_sets(model)` — Authorizations with the same TARGET
    (a `to_agent` name, or a `to_role` name; separate namespaces, so an
    agent and a role with the same name are not conflated) and the same
    NON-EMPTY `domain_scope` (compared trimmed and case-insensitively;
    interior whitespace is not collapsed), from >=2 DISTINCT authorities.
    The set is the permits they grant. Displayed `domain_scope` is the
    smallest trimmed spelling actually declared, so output is
    deterministic.
  - `required_permits_by_action(model)` — every role Action that names
    >=1 `requires_permit`, over Community, Domain and Federation roles.
    `for <role>` is ignored, as engine step 6 and the verifier's index
    ignore it.
  - `permit_omissions(model)` — per (action, set), the required permits
    of the set and the omitted authorities, each with the grants it made
    in the set. Sorted and deterministic.
- **The rule** `_validate_unconsulted_permit_authority()` builds `[W-16f]`
  entirely from `permit_omissions()` (no twin logic). One warning per
  (action, set).
- **Message:** `[W-16f] Action 'X' (role 'R', community 'C') requires 'P1'
  from the permits co-granted to agent 'Ag' in domain_scope 'S' by 2
  distinct authorities (Auth1, Auth2). Not consulted: authority 'Auth2'
  (Authorization 'a2': permit 'P2'). If every listed authority must
  approve this action, add the missing requires_permit; if any one
  suffices, this is intended. How these authorities combine is
  application-defined; the toolchain does not compose them.`

**Decisions:**
- **Authority-based omission, not "any permit missing".** Warn only when
  the Action requires >=1 permit of the set AND at least one distinct
  authority of the set has NONE of its permits (within the set) required
  by the Action. An authority is consulted if the Action names any permit
  it granted. Example: Auth1 grants P1+P2, Auth2 grants P3 — requiring
  P1+P3 is not flagged; requiring only P1, or only P1+P2, names Auth2 and
  P3.
- **ConditionalAction is excluded.** The warning advises "add the missing
  requires_permit", which does nothing on a ConditionalAction:
  `ConditionalAction.requires_permits` is set by the parser and read by
  nothing. Logged as a new open finding in `docs/CONCEPTS_INDEX.md` and
  DN_017 §6 (not fixed).
- **Grouping key** is same target + normalized non-empty `domain_scope`.
  `domain_scope` remains free text (AM-14, typed reference, stays a
  separate improvement), so a typo in one Authorization's scope silently
  splits a set — the documented fail-open.
- **Fourth independent required-permit extraction.** Engine step 6,
  `can_perform`, the verifier's `_build_permit_requirement_index()` and
  `required_permits_by_action()`. A small shared helper was needed
  because the verifier's index is name-keyed (last wins, so same-named
  actions in different roles collide), drops role identity, and importing
  it into the validator would pull `el_engine` into Layer 2. None of the
  others is refactored. A parity test pins this helper to the verifier's
  index (named tracked scenarios, unique action names, plus an inline
  multi-permit case) so the two cannot silently drift.

**Documented out of scope (unchanged):** permits obtained by role `holds`
(not Authorizations, never form a set); an Authorization without a
`domain_scope` (never joins a set — fail-open); Step, Prescription and
Declaration requirements; role-to-agent resolution (the warning is about
the permit set, not about who performs the action, so an Action in a role
unrelated to the set's target can still be flagged — advisory);
delegation/`principal_of` parents (W-16c/W-16e); errors and runtime
enforcement; numeric ceilings; `any_parent`; an explicit group attribute.

**Standard reference(s):** §6.6.4 and §7.10.2 (Authorization), §6.4.6
(permit required by an action) — as cited in the grammar's own comments
on `Authorization` and `DeonticRequirement`.

**Verification:** new `tests/test_am94_partial_permit_requirement.py` (22
tests, inline specs and named tracked files only): exact message wording;
P1-only, P2-only, both, neither; different, missing and blank
`domain_scope`; scope variants differing only in case/whitespace grouped;
one authority granting two permits (not two authorities); `to_role`; an
agent and a role with the same name not conflated; three authorities with
an action requiring two; the authority-based cases above; every grant of
an omitted authority listed; an authority that granted the required permit
too is consulted; ConditionalAction not covered; permit via role `holds`
not covered; same-named actions in different roles stay separate;
order-invariance over all 36 permutations of the authorizations and
actions (identical strings); the query's output equals what the message
lists; the named tracked scenarios (`referral_scenario.el`,
`consent_scenario.el`, `federation_consent_scenario.el`) have no `[W-16f]`
and no co-granted set; parity with the verifier's index. Mutation checks
in scratch copies were caught: a "consulted only if all its permits are
required" rule, agent/role namespaces conflated, no scope normalisation, a
multi-permit extraction drift, and a first-role-only coverage drift.
Corpus: all 11 tracked `.el` files give identical errors and warnings
before and after, zero `[W-16f]`; the tracked corpus has 3 Authorizations
(one each in `generated_governance.el`, `gp_referral_scenario.el`,
`referral_scenario.el`) and no co-granted set. Full suite: 514 passed, 1
xfailed (492/1 AM-93 baseline + 22 new, zero regressions) — reproduced
identically on a clean `git worktree add` checkout with the diff applied.

**Files changed:** `toolchain/el_reasoner.py` (module docstring; the five
records and three queries); `toolchain/el_validator.py` (module docstring
rule list; `_validate_unconsulted_permit_authority()`; wiring in
`validate_spec()`); new `tests/test_am94_partial_permit_requirement.py`;
this file (new entry); `docs/CONCEPTS_INDEX.md` (new AM-94 note and the
ConditionalAction open finding).

---

## AM-95 (2026-09-23) — `[W-16g]`: declared-parent union across all channels (`toolchain/el_reasoner.py`, `toolchain/el_validator.py`)

**Status:** IMPLEMENTED (2026-09-23). Type: V-NEW (validator warning); no
grammar change. Advisory, never an error; routed through the AM-89
warnings channel.

**Problem:** AM-90's `[W-16c]` counts only genuine `Delegation`-based
parents; AM-91's `[W-16e]` counts only standing `principal_of` parents.
Each rule evaluates its own `>=2` threshold independently against its own
channel. An agent with exactly one parent in each of two or three
channels — one via a real `Delegation`, one via a standing
`principal_of`, one via a bare `delegated_from` with neither a matching
`Delegation` nor a matching `principal_of` — triggered NEITHER warning,
even though it has 2 or 3 genuinely distinct declared parents. AM-93's
own amendment entry logged this gap explicitly ("deliberately untouched
... `parents_of()`, `[W-16c]/[W-16d]/[W-16e]`, V-08 all work from
Delegations / `principal_of`, not from `delegated_from`") without closing
it. `delegation_graph()` never emits an edge for a bare `delegated_from`
at all — it is read only by `_is_standing_affiliation()`, to decide
whether a `principal_of` edge is structural, never as a parent-declaring
edge in its own right — so a `delegated_from`-only parent was invisible
not just to the two warnings but to the graph itself.

**Standard basis:** `delegated_from` is itself a self-sufficient static
declaration (§6.6.8 NOTE 3: "a specification may state that, in its
initial state, an active enterprise object is an agent of a party") — it
does not need a matching `Delegation` to be legitimate, so the fix is
NOT "warn when `delegated_from` lacks a backing `Delegation`" (that would
misfire on every correct spec using the construct as designed). The fix
recognises `delegated_from` as a genuine parent-source for VISIBILITY
purposes, and counts total distinct parents as the union across all three
channels, per §7.10.1 ("the parties (collectively) become principal").

**What changed:**
- **`el_reasoner.py`** — two new functions, placed after
  `standing_parents_of()`:
  - `_delegated_from_parents(model, agent_name)` — every delegator named
    in `agent_name`'s own `delegated_from` entries (AM-93's list), as a
    `Set[str]`. Deliberately not built from `delegation_graph()` — see
    Problem, above.
  - `all_declared_parents_of(model, agent_name) -> List[str]` — the
    union of `parents_of()`'s Delegation-based parent names,
    `standing_parents_of()`'s standing parent names, and
    `_delegated_from_parents()`'s names. Sorted, deduplicated by
    construction (Python set union) — a party declared as a parent via
    more than one channel to the same agent counts once, not once per
    channel. Unknown `agent_name` returns `[]`, never raises, matching
    `parents_of()`/`standing_parents_of()`'s own contract.
- **`el_validator.py`** — `_validate_all_channel_multi_parent_notice()`,
  `[W-16g]`, wired into `validate_spec()` after `[W-16f]`. Built entirely
  from the same three primitives `all_declared_parents_of()` composes (no
  twin logic). Iterates every `EnterpriseObject` name in the model (not
  just names already appearing in `delegation_graph()`, since a
  `delegated_from`-only parent has no graph edge at all).
  - **Non-redundancy rule:** fires iff `len(union) >= 2` AND
    `union != delegation_parents` (what `[W-16c]` would name) AND
    `union != standing` (what `[W-16e]` would name) — i.e. only when the
    union states something neither channel's own warning already said in
    full. If a channel's own set already equals the union, that channel's
    warning already names it and a third, redundant warning is
    suppressed. If `[W-16c]` or `[W-16e]` fires for a strict SUBSET of
    the union (a third, distinct parent from another channel), `[W-16g]`
    fires alongside it — verified: a 2-Delegation probe that already
    triggers `[W-16c]` for `{X, Y}`, plus one distinct standing parent
    `C`, triggers `[W-16c]` AND `[W-16g]` (naming all three), not
    `[W-16c]` alone.
  - **Same-name, multiple channels → one entry, multiple tags:** a party
    declared via more than one channel to the same agent (the common
    corpus idiom — a real `Delegation` paired with a matching
    `delegated_from` entry from the same party, per
    `_is_standing_affiliation()`'s own docstring) renders as ONE list
    entry naming every channel it came from
    (`"GPClinician (gpToSpecialistDelegation, delegated_from)"`), never
    as two separate entries for the same name — pinned by an exact-string
    test, not just a set-membership check.
  - **Message:** names every union member with its channel tag(s) —
    the Delegation name(s) for the delegation channel (mirroring
    `[W-16c]`'s own per-parent detail), `"standing principal_of"`, or
    `"delegated_from"` — then the standard §7.10.1 collective-
    responsibility sentence, the §6.6.8 NOTE 3 self-sufficiency note, and
    the SAME hand-off sentence `[W-16c]` uses ("How these authorities
    combine is application-defined; the toolchain does not compose
    them."), then a pointer to `el_reasoner.all_declared_parents_of()`.
  - **`[W-16c]`, `[W-16d]`, `[W-16e]` are unchanged** — same triggers,
    same wording, same existing tests, verified by rerunning the full
    suite with only the AM-95 addition present before writing any new
    tests.

**One real, tracked-corpus hit — a true positive, not modified** (same
pattern as AM-91's `federation_consent_scenario.el` finding):
`scenarios/referral/referral_scenario.el`'s `SpecialistClinician` has two
genuinely distinct declared parents — `GPClinician` (both a real
`Delegation`, `gpToSpecialistDelegation`, AND a paired `delegated_from`
entry — the file's own documented idiom, header lines 780-782, for "a
GENUINE, if temporary, delegated principal-agent relationship") and
`SpecialistPractice` (a standing `principal_of` parent, organisational
affiliation only). Neither channel alone reaches its own `>=2` threshold
(one distinct parent each), so this was previously silent on both
`[W-16c]` and `[W-16e]`. `[W-16g]` now fires exactly once, naming
`GPClinician (gpToSpecialistDelegation, delegated_from), SpecialistPractice
(standing principal_of)` — advisory, and the scenario file itself is
unchanged. `scenarios/consent/federation_consent_scenario.el`'s
`SpecialistParty` (AM-91's own tracked-corpus hit) was also checked: its
union equals its `[W-16e]` standing set exactly, so the non-redundancy
rule correctly keeps `[W-16g]` silent there — confirmed against the real
file, not only a synthetic case. `consent_scenario.el` and every other
tracked, parsing scenario produce no `[W-16g]`. `gp_referral_scenario.el`
still fails to parse on a pre-existing, unrelated `V-NEW-10` error, out of
scope here; `ecommerce_scenario.el` remains the documented non-parsing
open item.

**Standard reference(s):** §7.10.1 ("the parties (collectively) become
principal of that object"); §6.6.8 NOTE 3 (delegated_from is a
self-sufficient static declaration).

**Verification:** new `tests/test_am95_all_channel_multi_parent_warnings.py`
(18 tests): a ThreeChannelProbe (one parent per channel, fires once,
names all three, exact string); each 2-of-3 channel pairing (fires); each
single channel alone (silent); a channel already at `>=2` on its own via
`[W-16c]` (no redundant `[W-16g]`) and the symmetric case via `[W-16e]`;
`[W-16c]` at `>=2` plus one distinct extra parent from another channel
(`[W-16g]` fires alongside it, naming all three); the same-party
two-channel case rendering as one entry with both tags (exact string,
`.count("SameParty") == 1`); order-invariance across every permutation of
a 3-channel probe's declaration order; `all_declared_parents_of()` on an
unknown agent (`[]`) and its parity with the message's content; warnings
never affect `.ok`; the named tracked scenarios
(`referral_scenario.el` pinned to its one true-positive `[W-16g]`,
`consent_scenario.el` and `federation_consent_scenario.el` confirmed to
produce none). Four pre-existing tests in
`tests/test_am89_warnings_channel.py`, `tests/test_am91_standing_parent_warnings.py`,
and `tests/test_am93_delegated_from_list.py` asserted `warnings == []` (or
no-warning) on `referral_scenario.el` or on a synthetic all-paired-parents
probe that is itself a genuine new `[W-16g]` true positive
(`AgentA` with two parents declared via `delegated_from` alone, both
paired with `principal_of` and so correctly NOT standing) — updated to
assert the exact new warning, with an AM-95 note explaining why; `[W-16c]`-
and `[W-16e]`-specific assertions in those same files are untouched. Full
suite: 541 passed, 1 xfailed (523/1 baseline + 18 new, zero regressions),
reproduced identically on a clean `git worktree add` checkout with the
diff applied. The 523 baseline is HEAD at the time of this work
(`3e9d397`), not AM-94's own commit-time count (514, at `995ed66`/`c09abcf`)
— two unrelated, already-committed FHIR-mapper commits (`8b92511`: 514→519;
`3e9d397`: 519→523) landed on `main` between AM-94's DN_017 push and this
amendment, each independently verified by its own gate. Reconciled by
`git stash`-ing this amendment's changes back to a clean HEAD and rerunning
(523 passed, 1 xfailed), then restoring and rerunning (541, 1 xfailed) —
not a typo, a stale carried-over count, or an untracked file.

**Files changed:** `toolchain/el_reasoner.py` (`_delegated_from_parents()`,
`all_declared_parents_of()`); `toolchain/el_validator.py` (module
docstring rule list; `_validate_all_channel_multi_parent_notice()`; wiring
in `validate_spec()`); new
`tests/test_am95_all_channel_multi_parent_warnings.py`;
`tests/test_am89_warnings_channel.py`,
`tests/test_am91_standing_parent_warnings.py`,
`tests/test_am93_delegated_from_list.py` (updated referral_scenario.el /
all-paired-probe assertions); this file (new entry); `docs/CONCEPTS_INDEX.md`
(new AM-95 note).

---

## AM-96 (2026-09-23) — `[W-16h]`: ungrantable permit requirement (`toolchain/el_reasoner.py`, `toolchain/el_validator.py`)

**Status:** IMPLEMENTED (2026-09-23). Type: V-NEW (validator warning); no
grammar change. Advisory, never an error; routed through the AM-89
warnings channel.

**consent_scenario.el's two true-positive hits below — fixed by AM-97.**

**Problem:** an Action's `requires_permit` can name a permit that nothing
in the specification ever grants — no `Authorization`, no `holds` clause,
no action `effect create`. Today this is caught only at runtime
(`el_engine` step 6 / `Runtime.advance()` blocks it correctly, and the
Layer-2 static reasoner `can_perform()` reports it too — both confirmed
live against a probe) — with zero static diagnostic. Distinct from
AM-94's `[W-16f]` (a choice between permits co-granted by >=2 authorities
— a substitution risk): this is a requirement with no path to
satisfaction at all, a dead end, not a composition question.

**What changed:**
- **`el_reasoner.py`** — three new pieces, placed after `permit_omissions()`
  (AM-94), reusing `required_permits_by_action()` rather than adding a
  fifth independent extraction of an action's required permits:
  - `grantable_permit_names(model) -> Set[str]` — the union of every
    token name with at least one static source: `Authorization.
    grants_permit`; `EnterpriseObject.holds_tokens`; `Role.holds_tokens`
    (a Role's own `holds`, distinct from an EnterpriseObject's — included
    on the same basis V-15 and V-16a already use, both already treating
    "a Role `holds` it" as valid static grounding: `_validate_
    obligation_chain()`'s `role_held_token_names`, `_validate_
    token_group_provenance()`'s `backed_by_role_holds`); and an Action's
    own `effect create <token>` (the only `TokenOp` that fabricates a
    brand-new `TokenInstance` from nothing — confirmed by reading
    `el_engine.py`: `transfer`/`clone` both require an existing instance,
    `activate`/`pend`/`destroy` only change state of one). Deliberately
    NOT built from Delegation `transfers_burden`/`transfers_token_group`
    — see the dedicated paragraph below.
  - `delegation_transferred_token_names(model) -> Set[str]` — every token
    name transferred by a genuine Delegation, used only to annotate the
    warning message when an ungrantable permit is also named in one.
  - `ungrantable_permit_requirements(model) -> List[UngrantablePermitRequirement]`
    — every (action, permit) pair from `required_permits_by_action()`
    whose permit is not in `grantable_permit_names()`.
- **`el_validator.py`** — `_validate_ungrantable_permit_requirement()`,
  `[W-16h]`, wired into `validate_spec()` after `[W-16g]`. Built entirely
  from `ungrantable_permit_requirements()` (no twin logic).
  - **Message tone, deliberately different from `[W-16c]`/`[W-16e]`/
    `[W-16f]`/`[W-16g]`'s "application-defined; the toolchain does not
    compose them" closing:** worded as a spec-authoring defect to fix
    ("The requirement can never be satisfied. Add a grant for '<permit>',
    or remove the requirement if it is no longer needed.") — this is not
    a choice between legitimate alternatives, it is a dead end.
  - **Delegation-transfer annotation:** when the ungrantable permit is
    also named in a Delegation transfer, the message appends ", though it
    is named in a Delegation transfer (which presupposes, not creates,
    the token)" before continuing — so a spec author isn't left wondering
    why a permit that is "transferred somewhere" still triggers the rule.
    A distinct, exact-string-pinned wording variant from the plain
    ungranted-anywhere case.

**Delegation-transfer exclusion — decided and confirmed live, not
assumed.** A Delegation transfers an EXISTING token between holders; it
does not create one — §6.4.7 NOTE 1 describes delegation as "literal
token transfer", which presupposes prior existence. Treating "some
Delegation transfers it" as evidence of grantability would reproduce
`_validate_token_group_provenance()`'s (V-16a) own circularity
(`backed_by_delegation` treats TokenGroup membership in a Delegation's
transfer as itself sufficient backing) for the different, stricter
question this rule asks. Confirmed live with a probe: a `TokenGroup` with
one Commitment-grounded member and one otherwise-ungrounded permit,
transferred whole by a real `Delegation`, passes both V-15 (at least one
referenced token is grounded) and V-16a (the permit is "backed_by_
delegation") with zero errors — yet the permit is held nowhere. This
exact shape is `tests/test_am96_ungrantable_permit_warnings.py`'s
`test_delegation_transfer_only_warns_with_transfer_note` — the excluded
channel still produces the warning, with its own wording.

**Two real, tracked-corpus hits — true positives, not modified** (same
pattern as AM-91's `federation_consent_scenario.el` finding and AM-95's
`referral_scenario.el` finding): `scenarios/consent/consent_scenario.el`
— the primary EDOC 2026 demonstration scenario — declares `permit
aiAnalysisPermit` ("Permission to perform AI diagnostic analysis —
requires prior consent"), required by `aiAgentRole`'s `seekConsent` and
`performAnalysis` actions, but never grants it: this file has no
`Authorization` at all, no `holds` clause names it, and no `effect
create` targets it. `[W-16h]` now fires twice, once per action; advisory,
and the scenario file itself is unchanged. Every other tracked, parsing
scenario produces zero `[W-16h]` hits (checked: `referral_scenario.el`,
`federation_consent_scenario.el`, `ereferral_model.el`,
`erequesting_claiming_scenario.el`, `generated_governance.el`,
`transfer_probe.el`, `specialist_pool_scenario.el`, `ai_vendor_probe.el`).
`gp_referral_scenario.el` still fails to parse on the pre-existing,
unrelated `V-NEW-10` error.

**Standard reference(s):** §6.4.6 (conditional action / requires_permit
semantics); §7.10.1 (delegation as literal token transfer, §6.4.7 NOTE 1).

**Verification:** new `tests/test_am96_ungrantable_permit_warnings.py`
(14 tests): a permit granted nowhere (fires, exact message); each grant
channel alone — Authorization, EnterpriseObject `holds`, Role `holds`,
`effect create` — silences it; granted-and-required silent; the
Delegation-transfer-only (`ghostPermit`) case fires with the distinct
transfer-note wording, exact string pinned; order-invariance across every
permutation of a two-permit probe's declaration order;
`grantable_permit_names()`/`ungrantable_permit_requirements()` parity
with the message; warnings never affect `.ok`; the named tracked
scenarios (`consent_scenario.el` pinned to its two true-positive
`[W-16h]`s, `referral_scenario.el` and `federation_consent_scenario.el`
confirmed to produce none). Three pre-existing tests in
`tests/test_am89_warnings_channel.py`, `tests/test_am91_standing_parent_warnings.py`,
and `tests/test_am93_delegated_from_list.py` asserted `warnings == []`
(or an unrelated subset) on `consent_scenario.el` — updated to assert the
exact two new warnings, with an AM-96 note explaining why;
`[W-16c]`/`[W-16d]`/`[W-16e]`/`[W-16f]`/`[W-16g]`-specific assertions in
those same files are untouched. Full suite: 555 passed, 1 xfailed (541/1
baseline + 14 new, zero regressions), reproduced identically on a clean
`git worktree add` checkout at the correct base commit with the tracked
diff applied via `git apply` (not manual copying — the AM-95 lesson).

**Files changed:** `toolchain/el_reasoner.py` (`grantable_permit_names()`,
`delegation_transferred_token_names()`, `UngrantablePermitRequirement`,
`ungrantable_permit_requirements()`); `toolchain/el_validator.py` (module
docstring rule list; `_validate_ungrantable_permit_requirement()`; wiring
in `validate_spec()`); new `tests/test_am96_ungrantable_permit_warnings.py`;
`tests/test_am89_warnings_channel.py`,
`tests/test_am91_standing_parent_warnings.py`,
`tests/test_am93_delegated_from_list.py` (updated consent_scenario.el
assertions); this file (new entry); `docs/CONCEPTS_INDEX.md` (new AM-96
note).

---

## AM-97 (2026-09-23) — reference-scenario content fix: `consent_scenario.el`'s `aiAnalysisPermit` becomes grantable (`scenarios/consent/consent_scenario.el`)

**Status:** IMPLEMENTED (2026-09-23). Type: DOC/content (reference
scenario fix); no grammar, toolchain, or validator-rule change. Prompted
directly by AM-96's own finding — `[W-16h]` working as designed, not a
toolchain bug.

**Problem:** AM-96 found two genuine `[W-16h]` hits in the primary EDOC
2026 demonstration scenario: `permit aiAnalysisPermit` ("Permission to
perform AI diagnostic analysis — requires prior consent"), required by
`aiAgentRole`'s `seekConsent` and `performAnalysis` actions, granted
nowhere. Reading the file's narrative: `seekConsentObligation` flows
GP → Specialist → AI agent via two Delegations (`discharge_mode: strict`
is the file's whole Layer-4 demonstration point); `aiAnalysisPermit` is
clearly meant to represent "the AI agent may now analyse, because
consent was obtained" — a content gap, not an independent, unconnected
static declaration.

**What changed — a 2-line fix to `seekConsent`'s action body:**
```diff
                 action seekConsent {
                     description: "AI agent seeks and records informed patient consent"
                     actor: aiAgentRole
                     precondition: "Patient must be contactable"
-                    requires_permit aiAnalysisPermit for aiAgentRole
+                    effect create aiAnalysisPermit to aiAgentRole
                 }
```
`performAnalysis` is unchanged — it keeps `requires_permit aiAnalysisPermit
for aiAgentRole`, the action the permit should actually gate. Removing
the requirement from `seekConsent` is necessary, not cosmetic: engine
step 6 (permit check) runs before step 7 (effect application), so
`seekConsent` requiring the very permit it is about to create would be a
standing deadlock. `to aiAgentRole` matches this file's own established
style (both existing `effect create` uses in this file always name an
explicit `to <role>`).

**Precedent, confirmed not assumed:** the established idiom for "action X
causes token Y to become available" in this grammar/engine is
`effect create <token>` placed directly in the action that causes it —
NOT a `triggered_by`/`discharged_by`/`emits` chain. `referral_scenario.el`'s
own header comment (lines 128-144) documents that the event-driven
mechanism was tried for an equivalent case and reverted same-day
("it requires a pre-existing pending token that nothing ever granted...
`effect create` matches the precedent `initiateReferral` already uses").
`consent_scenario.el` itself already used this idiom once
(`initiateReferral`'s `effect create seekConsentObligation to
specialistRole`) — AM-97 is the first tracked use of `effect create` for
a **permit** specifically, rather than a burden.

**Important distinction — stated explicitly, not left implicit (per the
maintainer's instruction):** this fix grants `aiAnalysisPermit` as a side
effect of the `seekConsent` ACTION executing, not as a formal consequence
of `seekConsentObligation` being DISCHARGED. No `discharged_by`-style
mechanism exists in this grammar to hang a grant off a burden's discharge
transition — the engine has no such hook (see the cross-referenced open
finding, below). The two would coincide in practice only if
`seekConsentObligation` were also actually discharged by an action named
`seekConsent` performing that role — which, per the finding below, it
currently is not. A future reader should understand this as "grant on
the seeking of consent" (the narrative act `seekConsent` performs),
**not** "grant on discharge of the consent obligation" (a formal engine
event that does not currently occur here).

**Bonus finding, logged as its own open item, NOT fixed here:**
`seekConsentObligation.for_action` is `"seek_patient_consent"`, but no
action named `seekConsent` (or any other) ever matches it — engine step
3's discharge check is a literal string `tok.for_action == action_name`
(`el_engine.py:469`), and `"seek_patient_consent" != "seekConsent"`. No
action in this file currently discharges `seekConsentObligation` via the
engine's automatic mechanism at all. Pre-existing, independent of AM-96/
AM-97's permit issue — confirmed live, not fixed as part of this
amendment (out of scope: touching the file's primary obligation's
discharge wiring is a bigger, separate content decision). Logged as its
own open finding in `docs/CONCEPTS_INDEX.md`.

**Blast radius — every test/fixture pinning `consent_scenario.el`'s exact
output, checked (not assumed) before proposing the fix:**
- `tests/test_am89_warnings_channel.py`, `tests/test_am91_standing_parent_warnings.py`,
  `tests/test_am93_delegated_from_list.py` — each asserted the exact two
  `[W-16h]` strings AM-96 introduced; reverted to `result.warnings == []`.
- `tests/test_am96_ungrantable_permit_warnings.py` —
  `test_consent_scenario_produces_exactly_two_w16h_true_positives`
  renamed to `test_consent_scenario_no_longer_produces_w16h`, now
  asserting `result.warnings == []`, with a docstring explaining the
  AM-97 fix; the rule's own correctness (trigger, exact wording, the
  Delegation-transfer variant) remains fully covered by this file's
  inline probes, independent of the scenario.
- `tests/test_am86_obligation_descriptor_roots.py`'s pinned
  `dataclasses.asdict()` snapshot of `seekConsentObligation`'s and
  `reportingObligation`'s obligation descriptors, and both
  `tests/fixtures/am88a_obligation_descriptors_snapshot.json` /
  `am88b_delegation_chain_for_token_snapshot.json` — confirmed
  unaffected: `_build_obligation_descriptors()` filters `kind == "burden"`
  only, and both JSON fixtures key exclusively on `reportingObligation`/
  `seekConsentObligation`; `aiAnalysisPermit` never appears in either.
  Verified byte-identical before/after in scratch, not assumed. No
  changes needed; re-run as part of the gate.
- `tests/test_am90_multi_parent_warnings.py`, `tests/test_am92_v08_token_aware.py`,
  `tests/test_am94_partial_permit_requirement.py`,
  `tests/test_am95_all_channel_multi_parent_warnings.py` — each filters
  for its own warning code or checks `.ok`/absence of a specific error;
  unaffected either way. No changes needed; re-run as part of the gate.
- `docs/DSL_TOOLCHAIN_REFERENCE.md`'s worked Bellman/AF/EF example (about
  `seekConsentObligation`/`reportingObligation` only) — not a pinned
  test, but confirmed unaffected: Kripke world/edge counts are
  byte-identical before/after (30 worlds / 13 edges both times).

**Verification, in scratch before touching the real file:** built the
exact fix as a scratch copy and ran it through `parse()`,
`co_granted_permit_sets()`/`permit_omissions()` (no new `[W-16f]` risk —
no Authorization is added), `_build_obligation_descriptors()` (both
pinned burden descriptors byte-identical), and `build_kripke_model()`
(AF/EF for `discharged:seekConsentObligation` both `True` before and
after; world/edge counts identical, 30/13). After the real edit: `ok=True,
errors=[], warnings=[]` — both `[W-16h]` hits gone, zero new warnings of
any kind. Full suite: 555 passed, 1 xfailed (same count as AM-96's own
endpoint — a content fix plus reverted assertions, no new tests),
reproduced identically on a clean `git worktree add` checkout at the
correct base commit with the tracked diff applied via `git apply`.

**Standard reference(s):** none new — this is a scenario-content fix, not
a grammar or validator change. The scenario's own accountability chain
remains grounded in §6.6.6/§7.10.1 (Delegation) exactly as before.

**Files changed:** `scenarios/consent/consent_scenario.el` (`seekConsent`
action body, 2 lines); `tests/test_am89_warnings_channel.py`,
`tests/test_am91_standing_parent_warnings.py`,
`tests/test_am93_delegated_from_list.py` (reverted `consent_scenario.el`
assertions to `[]`); `tests/test_am96_ungrantable_permit_warnings.py`
(renamed true-positive test); this file (new entry, and a one-line
forward-pointer added to AM-96's own entry above); `docs/CONCEPTS_INDEX.md`
(new AM-97 note, a forward-pointer on AM-96's entry, and a new open
finding for the `for_action` mismatch).

---

## AM-98 (2026-09-25) — `DurationUnit` lists plurals first so plural units parse (`grammar/v2/el_grammar.tx`)

**Status:** IMPLEMENTED (2026-09-25). Type: AM (grammar bug fix). No
toolchain, domain-class, or validator-rule change.

**Problem:** `DurationUnit` (introduced by AM-23) listed each singular
before its plural — `'minute' | 'minutes' | 'hour' | 'hours' | ...`.
PEG ordered choice commits to the first alternative that matches, so
`'hour'` matched the prefix of `hours` and the enclosing rule then failed
on the trailing `s`. Every plural unit was unparseable wherever `Duration`
is used: `Policy.initial_value` / envelope values (via `PolicyValue`) and
`NormativePolicy.review_cycle`. Reproduced before the fix: `24 hours`,
`3 days` and `12 months` all failed with a `[SYNTAX]` error pointing at
the `s` (`24 hour*s`); the singular forms parsed.

**What changed:** each plural now precedes its singular:
```diff
 DurationUnit:
-    'minute' | 'minutes' | 'hour' | 'hours' | 'day' | 'days'
-    | 'week' | 'weeks' | 'month' | 'months' | 'year' | 'years'
+    'minutes' | 'minute' | 'hours' | 'hour' | 'days' | 'day'
+    | 'weeks' | 'week' | 'months' | 'month' | 'years' | 'year'
 ;
```
plus a two-line comment above the rule explaining why the order matters.
Singular forms are unaffected (`1 hour` still parses to unit `'hour'`).
The `DurationUnit` enum in `toolchain/el_domain.py` already carried both
singular and plural members, so no domain-class change was needed.
`_DEADLINE_UNIT_STEPS` in `toolchain/el_engine.py` operates on free-text
deadline strings, not `Duration`, and is unaffected.

**Scenario workaround reverted:** `scenarios/terms_of_engagement/external_agent_access_scenario.el`'s
`RefusalQuarantinePolicy` used `initial_value: 1 day` only to avoid this
bug; it is now `initial_value: 24 hours`, as intended. The scenario still
validates cleanly before and after (`ok=True, errors=[], warnings=[]`),
and parses the value as `24` / `'hours'`. `RefusalReviewPolicy`'s
`initial_value: 1 day` in the same file is intentional (it matches
`refusalReviewBurden`'s deadline) and is deliberately left unchanged.

**Tests:** new `tests/test_am98_duration_plural_units.py`, four tests,
each asserting the parsed unit string as well as successful parsing, so a
future reorder cannot silently collapse a plural onto its singular:
`Policy.initial_value` `24 hours` → `'hours'` and `1 hour` → `'hour'`;
`NormativePolicy.review_cycle` `12 months` → `'months'` and `1 month` →
`'month'`. **Undo-and-rerun check:** with the grammar change temporarily
stashed, the two plural tests fail and the two singular tests pass —
confirming the tests actually detect this bug rather than passing
vacuously. With the fix restored, all four pass.

**Verification:** full suite (`.venv/bin/python3.13 -m pytest`) — 559
passed, 1 xfailed, against the 555 passed / 1 xfailed baseline at
`2cfe669` (AM-97's endpoint). The +4 are exactly the new AM-98 tests; no
existing test changed outcome. The suite was re-run after each step
(grammar, tests, scenario) with the same result at each point.

**Standard reference(s):** none new — a parser-level fix to AM-23's
typed policy values (§6.5, §7.9 policy concepts), restoring the
intended surface syntax.

**Files changed:** `grammar/v2/el_grammar.tx` (`DurationUnit`
alternative order, plus comment); `tests/test_am98_duration_plural_units.py`
(new); `scenarios/terms_of_engagement/external_agent_access_scenario.el`
(`RefusalQuarantinePolicy.initial_value`); this file (new entry).

---

## AM-99a (2026-09-25) — part 1 of 3: static builder counts deadlines from activation (`toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-25). Type: toolchain fix (Layer 4,
static builder only). No grammar or validator change. Fixes a
**pre-existing** issue in `build_kripke_model()`'s deadline counting for
P6a-activated obligations. It is independent of T11 (AM-99a part 2), and
is landed first so its effect can be checked on its own.

**Problem:** Rule T2 checked `w.step < desc.deadline_steps`, which counts
every obligation's deadline from step 0, including obligations the P6a
cascade only moves from WAITING to PENDING at a later step. An obligation
activated at a step at or past its deadline got a VIOLATED edge in the
same world it became PENDING, so AF could never hold for it however
promptly its holder acted. Found while prototyping AM-99a: once T11 lets
`refusalRecordBurden` (strict; default 5-step deadline) be triggered at
step ≥ 5, its bounded response property is false for this reason alone.

**What changed:**
- New `World.activation_steps` field (frozenset of `(obligation_id,
  step)`, default empty), also accepted by `_make_world()`.
- P6a records `w.step` for every obligation it activates.
- T2 now checks `w.step - activated_at < desc.deadline_steps`, where
  `activated_at` is the recorded step, or 0 if none is recorded.
- Every static-builder rule (T1, C1, T2, T3, T5, T6) passes the field on
  to the successor world.
- Obligations PENDING at w0 are not recorded (implicit step 0), so w0 and
  every existing model are unchanged.
- The hybrid builder (`build_kripke_from_runtime()`) is untouched; its T2
  still checks `w.step >= desc.deadline_steps`.

**Correction to the investigation note (stated explicitly):** the AM-99a
investigation said this fix would match the live engine's
`tick - granted_at_tick`. That is wrong for event-triggered tokens. The
engine activates them through `_transition()` (`el_engine.py:145-155`),
which keeps the original `granted_at_tick`, so `check_live_violations()`
counts an event-triggered token's deadline from **grant**, not
activation. Part 1 therefore **deliberately does not mirror the engine**.
After it, the verifier and the engine disagree for triggered obligations.
Before it, they agreed only because both counted from the wrong point.
Logged as a new open finding in `docs/CONCEPTS_INDEX.md`, "Engine counts
event-triggered deadlines from grant, not activation", which must be
fixed, as its own amendment, before AM-99b.

**Separate open item, not fixed here:** C1-claimed obligations
(CLAIMABLE → PENDING) still count their deadline from step 0 in the
static builder. C1 does not record an activation step. Out of scope for
part 1, which is limited to P6a.

**Blast radius, checked rather than assumed:** static world count, edge
count and AF/EF verdict for every obligation in all 15 parseable
scenarios (`ecommerce_scenario.el` does not parse — see AM-93 note) are
identical before and after, compared as a full text snapshot. No
existing scenario activates an obligation through P6a late enough for
the counting point to matter. No pinned count or verdict moved.

**Tests:** new `tests/test_am99a_deadline_from_activation.py`, 4 tests,
on a minimal fixture: `firstBurden` (1-week deadline) fires `firstDone`
on discharge, and `secondBurden` is `triggered_by: firstDone` with the
default 5-step deadline. The tests check:
- the default deadline is 5 steps;
- an activation at step ≥ 5 has no violation edge in its activation world;
- across every world, a violation edge exists exactly when
  `step - activated_at >= 5`;
- w0 records no activation steps.

**Undo-and-rerun check:** with only T2's old comparison restored (the
field still present, so failures reflect the bug and not a missing
attribute), the two behavioural tests fail. With the fix, all four pass.

**Verification:** full suite (`.venv/bin/python3.13 -m pytest`) — 563
passed, 1 xfailed, against the 559 passed / 1 xfailed baseline at
`8407e5d`. The +4 are exactly the new tests.

**Standard reference(s):** Annex C (Kripke semantics, informative) —
§C.2's deadline-expiry reading of obligation violation. §7.8.7 (token
lifecycle): a token's obligation is in force from activation, not before.

**Files changed:** `toolchain/el_kripke.py`; `tests/test_am99a_deadline_from_activation.py`
(new); `docs/KRIPKE_TRANSITION_RULES.md` (T2 row, last-updated note);
`docs/CONCEPTS_INDEX.md` (new open finding, plus a forward pointer on the
"Engine/Kripke event-model symmetry gap" finding); this file (new entry).

---

## AM-99a (2026-09-25) — part 2 of 3: Rule T11, action-emitted events fire in the static builder (`toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-25). Type: toolchain change (Layer 4,
static builder only; hybrid is AM-99b). No grammar or validator change.

**Problem:** in `build_kripke_model()` a WAITING obligation could only
become PENDING through P6a, i.e. when another obligation's discharge
raised its `triggered_by` event (`fires_event`, from `discharged_by`).
Events raised by an Action's `emits` (AM-22), which the live engine fires
at Step 7c, were invisible to the verifier. In
`scenarios/terms_of_engagement/external_agent_access_scenario.el`,
`refusalRecordBurden` (`triggered_by: accessRefused`, emitted by
`refuseRequest`) and `incidentNotificationBurden`
(`triggered_by: vendorIncidentDetected`, emitted by `detectIncident`)
therefore stayed WAITING. `refusalReviewBurden`, which depends on the
first, stayed WAITING too. The BFS dead-ended at 4 worlds, with AF and EF
false for all three.

**What changed — Rule T11 (EVENT FIRING):**
- New `_build_event_firing_index()` maps each event to the eligible
  actions that emit it. An action is eligible if it:
  - has `emits`;
  - has no `requires_permit` (gated actions never fire through T11);
  - is not a discharging action: not any descriptor's `for_action`, and
    its emitted event is not any descriptor's `discharged_by`.
- For each event with WAITING dependents and each eligible emitter not
  yet occurred on the path, T11 adds an edge in which:
  - every WAITING obligation triggered by the event becomes PENDING;
  - the activation step is recorded (part 1's `World.activation_steps`);
  - the action is added to `occurred_actions`;
  - the step does not advance.
  The edge label is `fire:<event> via <action>`.
- Suppressed while a strict obligation is PENDING with an ACTIVE holder:
  the same condition as T3, mirroring the engine's Step 3.5 guard (AM-78),
  which blocks no-progress actions. A T11 action discharges nothing.
- No actor-activity or embargo check: the static builder has no
  role→actor map, and no static rule changes actor status.
- Embargoes are out of scope. `noCircumventionEmbargo` is also
  `triggered_by: accessRefused`, but T11 activates obligations only, and
  embargo state is fixed in the static builder.

**Why discharging actions are excluded (approved at the investigation
step):** without the exclusion, T11 fires `recordRefusal` (emits
`refusalRecorded`) without discharging `refusalRecordBurden`. That
activates `refusalReviewBurden` with no refusal ever recorded, and marks
the discharging action occurred while its burden is still open. The
prototype confirmed this breaks the strict burden's response property
(21228 worlds, all verdicts false). Discharge-raised events keep firing
through T1/P6a only. The `discharged_by` half of the exclusion extends the
approved `for_action` rule to the other way the engine discharges through
an action (Step 3, `event_discharged`). No current scenario hits it; a
fixture test covers it.

**Not an exact engine mirror, stated explicitly:** the engine emits from
a gated action once its permit is held (Step 6 precedes Step 7c). T11
never fires gated actions. Recorded on the "Engine/Kripke event-model
symmetry gap" finding in `docs/CONCEPTS_INDEX.md` as still open.

**AM-97's idiom is unaffected:** AM-97's `effect create` engine idiom
("action X makes token Y available") is unaffected. T11 is the verifier
counterpart for specifications that use `emits` / `triggered_by` instead,
and does not change how `effect create` is handled anywhere.

**Result on the scenario (horizon 10):** 4 → 2444 worlds (5924 edges). T11
fires exactly `fire:accessRefused via refuseRequest` and
`fire:vendorIncidentDetected via detectIncident`. `refusalReviewBurden` is
activated only by discharging `refusalRecordBurden` (P6a). EF is true for
all three burdens. AF from w0 stays false for all three, because each
waits on an event that may never fire. Part 3 replaces that verdict with
the bounded response property for triggered obligations.

**Blast radius, checked rather than assumed:** full static snapshot (world
count, edge count, AF/EF per obligation) of all 15 parseable scenarios.
Only `external_agent_access_scenario.el` changed. The only other `emits`
in the repo (`referral_scenario.el`, `referralSubmitted`) triggers no
burden, so T11 adds nothing there. Hybrid mode is untouched.

**Tests:** new `tests/test_am99a_t11_event_firing.py`, 9 tests.
- On the scenario:
  - it no longer dead-ends;
  - EF is true for all three burdens;
  - the exact set of T11 edges;
  - `refusalReviewBurden` is activated only by discharge.
- On minimal fixtures:
  - an ungated emitter fires (PENDING, occurred, same step, activation
    step recorded);
  - a gated emitter does not fire;
  - a `for_action` emitter does not fire;
  - an emitter of a `discharged_by` event does not fire;
  - a strict obligation blocks T11 until it is discharged.

**Undo-and-rerun checks,** each component removed on its own and the file
restored afterwards (byte-identical):

| Removed | Tests failing |
|---|---|
| T11 disabled | 6 (every positive test) |
| Gated exclusion | 1 (the gated test) |
| Discharging exclusion | 4 (the two exclusion tests and two scenario tests) |
| Strict guard | 1 (the strict test) |

**Verification:** full suite — 572 passed, 1 xfailed (563 after part 1,
plus 9).

**Standard reference(s):** Annex C (Kripke semantics, informative),
§C.2(b) reachability relation; §7.8.7 (token lifecycle, activation);
event raising per ODP Part 2 §8.4 (EmitsDecl, AM-22).

**Files changed:** `toolchain/el_kripke.py` (`_build_event_firing_index()`,
Rule T11 in `build_kripke_model()`, docstring);
`tests/test_am99a_t11_event_firing.py` (new);
`docs/KRIPKE_TRANSITION_RULES.md` (T11 row, last-updated note);
`docs/CONCEPTS_INDEX.md` (partial-resolution note on the symmetry-gap
finding); `scenarios/README.md` (scenario row); this file (new entry).

---

## AM-99a (2026-09-25) — part 3 of 3: bounded response property for triggered obligations (`toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-25). Type: toolchain change (Layer 4
verdict semantics, static builder only). No grammar or validator change.
Completes AM-99a.

**Problem:** `check_obligation()` reports AF(discharged) from w0. For an
obligation with `triggered_by`, that asks whether it is discharged on
every path, including paths where its trigger never fires. On those paths
the obligation was never in force, so an AF failure there is not a
compliance failure. After part 2, all three burdens in
`external_agent_access_scenario.el` failed AF from w0 for exactly that
reason, including the strict `refusalRecordBurden`, which is discharged
immediately whenever it is actually triggered.

**What changed:**
- **Verdict:** for an obligation with `triggered_by`, in a model whose
  `response_semantics` is set, `check_obligation()` delegates to the new
  `check_response()`. That reports the **bounded response property
  ("within horizon")**: AG(pending:O → AF discharged:O), evaluated from
  every world before the horizon step in which O is PENDING.
- **Operator label:** `modal_operator = RESPONSE_OPERATOR`
  (`"AG(pending→AF)"`).
- **Counterexample:** the shortest path from w0 to the earliest failing
  PENDING world (new `_path_to()`), followed by `_find_AF_counterexample()`
  from there.
- **Two outcomes are never reported as satisfied.** Both set the new
  `ObligationVerdict.status` field with `satisfied=False`:
  - `"not triggered within horizon"`: O is PENDING in no reachable world;
  - `"not resolved within horizon"`: O is PENDING only in horizon-step
    worlds.
  `ObligationVerdict.__post_init__` raises `ValueError` if either status is
  combined with `satisfied=True`, so the rule holds for any future caller,
  not only this one. `render()` shows the status and "NOT satisfied".
- **Horizon-step worlds are excluded from the antecedent** (approved at
  the investigation step). Only tick enqueues a new world at
  `step == horizon`, so a horizon-step world created by any other rule is
  an artificial dead end. Logged as its own open finding in
  `docs/CONCEPTS_INDEX.md`, "Kripke builders expand horizon-step worlds
  only when a tick produces them". That finding includes a scratch check
  of the possible link to the 31-vs-30 consent discrepancy: expanding
  every horizon-step world leaves consent at 30, so this fix in this form
  does not explain it.
- **Unchanged:** obligations without `triggered_by` keep AF from w0.
  `check_permission()` (EF from w0) is unchanged.

**`response_semantics` is TEMPORARY (stated explicitly, as required at
approval):** new `KripkeModel.response_semantics: bool = False`, set
`True` only by `build_kripke_model()` (both of its return sites).
`build_kripke_from_runtime()` leaves it `False`, so hybrid verdicts,
including `el_api.py`'s `/tokens/{name}/status` compelled/detectable
fields, are unchanged. **AM-99b must align hybrid mode with these
semantics and remove the flag**, re-checking `referralInitiationBurden`
under response semantics: it has `triggered_by: encounterConcluded`, and
its hybrid AF is pinned `True` in `tests/test_referral_kripke.py:30`.

**Blast radius, checked rather than assumed:** full static snapshot of all
15 parseable scenarios, including operator and status per obligation.
World and edge counts are unchanged everywhere (part 3 changes no
transitions). Verdict changes:
- `external_agent_access_scenario.el` — the intended ones, below.
- `referral_scenario.el`, static only — `referralInitiationBurden` stays
  `satisfied=False` but is now reported as "not triggered within horizon"
  under the response operator, instead of a plain AF failure. Its trigger
  `encounterConcluded` is fired only from FHIR (`fire_event()`), never by
  a DSL action or discharge. No test pins its static verdict; its pinned
  hybrid verdict is untouched.
No other obligation's verdict, operator or status changed.

**Result on the scenario (horizon 10):**
- `refusalRecordBurden` (strict) — bounded response property **holds**.
- `refusalReviewBurden` and `incidentNotificationBurden` (eventual) —
  bounded response property **fails**, EF **true**: detectable, not
  compelled.

This matches the maintainer's hand-run expectation (tokens starting
active), now reached from the real WAITING initial state. Reaching it
needed parts 1 and 2 as well as this part.

**Tests:** new `tests/test_am99a_bounded_response.py`, 12 tests.
- The three scenario verdicts, and that the counterexample starts at w0.
- Scoping:
  - an untriggered obligation keeps AF (consent `seekConsentObligation`);
  - the static builder sets the flag;
  - the hybrid referral model has the flag off and still reports AF for
    `referralInitiationBurden`.
- "not triggered within horizon" on static referral and on a minimal
  fixture, including `render()` text.
- "not resolved within horizon" on a hand-built model where O is PENDING
  only at the horizon step.
- The `ValueError` guard for both statuses.

**Undo-and-rerun checks,** each component removed on its own and the file
restored afterwards (byte-identical):

| Removed | Tests failing |
|---|---|
| Flag not set by the static builder | 6 |
| Horizon-step exclusion | 2 (strict `refusalRecordBurden`, not-resolved) |
| Not-triggered reported as vacuously satisfied | 2 (both not-triggered tests) |
| Never-satisfied guard | 2 (both guard tests) |

**Verification:** full suite — 584 passed, 1 xfailed (572 after part 2,
plus 12). AM-99a overall: 559 → 584 (+4 part 1, +9 part 2, +12 part 3).

**Standard reference(s):** Annex C (Kripke semantics, informative) —
§C.2's reading of obligation as "behaviour obliged to occur", applied from
the point the obligation is in force (§7.8.7 token lifecycle: a triggered
token is not in force while it waits on its event). The response pattern
AG(p → AF q) is standard CTL, and its bounded form is a consequence of
the finite horizon H of the constructed model (§C.2(b)).

**Files changed:** `toolchain/el_kripke.py` (`RESPONSE_OPERATOR` and
status constants; `KripkeModel.response_semantics`; `check_obligation()`
delegation; new `check_response()` and `_path_to()`;
`ObligationVerdict.status`, `__post_init__` guard, `render()` branch;
flag set at both `build_kripke_model()` return sites);
`tests/test_am99a_bounded_response.py` (new);
`docs/KRIPKE_TRANSITION_RULES.md` (note under "Related, not a transition
rule itself", last-updated note); `docs/CONCEPTS_INDEX.md` (new open
finding on horizon-step enqueueing); `scenarios/README.md` (scenario
row); this file (new entry).

---

## AM-100 (2026-09-25) — engine counts event-triggered deadlines from activation; events activate only pending tokens (`toolchain/el_engine.py`)

**Status:** IMPLEMENTED (2026-09-25), in two parts. Type: toolchain fix
(Layer 3, live engine). No grammar or validator change. The engine-side
counterpart of **AM-99a part 1**, which made the static Kripke builder
count deadlines from activation (`World.activation_steps`). Lands before
AM-99b, which mirrors the engine's event handling in hybrid mode and would
otherwise copy the old behaviour. Resolves the `docs/CONCEPTS_INDEX.md`
finding "Engine counts event-triggered deadlines from grant, not
activation".

### Part 1 — deadlines count from activation

**Problem:** activating a pending token went through `_transition()`,
which copies `granted_at_tick` unchanged, and `check_live_violations()`
computed `elapsed = tick - tok.granted_at_tick`. An event-triggered
burden's deadline therefore ran from its grant (typically enrolment or
build time), not from when its trigger fired. A burden triggered late
enough violated on the first sweep after it became active. After AM-99a
part 1 the engine and the static builder disagreed on this.

**What changed:**
- New `TokenInstance.activated_at_tick: Optional[int] = None`. None
  means "active since grant"; freshly created tokens are unchanged.
  `granted_at_tick` is kept as grant provenance, never reset.
- New `_activate(tok, tick)` (pending → active, stamping the tick) and
  `_activation_tick(tok)` (`activated_at_tick` if set, else
  `granted_at_tick`).
- `_activate_triggered_tokens()` takes a required `tick` and stamps
  activated tokens. Both callers pass it: `advance()` Step 7c and
  `fire_event()`.
- The 7b DeonticEffect `activate` op stamps the tick as well.
- `check_live_violations()` computes `elapsed = tick - _activation_tick(tok)`.
- `_transition()`, `_reassign_holder()` and the transfer/clone handlers
  carry the field through.
- An already-active token is not re-stamped, so a repeated event does not
  restart its deadline.
- **C1 claim (claimable → active) is unchanged:** a claimed token still
  counts from grant. See "Decisions to revisit".

### Part 2 — events activate only pending tokens

**Problem:** `_activate_triggered_tokens()` moved every token whose name
matched the event to `active`, whatever its state. A repeated event
revived `discharged` and `violated` tokens. It also logged "triggered
activation" for every matching name, so `fhir_event_handler` reported
`"fired"` for a repeated Encounter even when nothing was activated.

**What changed:**
- Only tokens in state `pending` are activated. This mirrors the static
  builder's P6a and T11, which activate only WAITING obligations.
- Only tokens actually activated are logged. An event that matches
  nothing pending leaves the effects log empty, and
  `handle_encounter_event()` reports `"fired_no_match"`. Its docstring
  and `fired_no_match` message now name both causes (no matching
  `triggered_by`, or none still pending).
- **Behaviour change beyond discharged and violated, accepted:** a
  `claimable` token with `triggered_by` is no longer activated directly
  by its event; it must be claimed. No scenario combines the two
  (`specialist_pool_scenario.el` deliberately avoids it).
- Checked before changing: with the pending-only guard applied, the full
  suite was unchanged, so no existing test relied on reactivation.

### Blast radius

No pinned verdict or violation timing moved (checked, not assumed):
- `referral_scenario.el`'s only triggered burden,
  `referralInitiationBurden`, is strict, so `check_live_violations()`
  never sweeps it. The escalation test violates `referralResponseBurden`,
  which is pre-seeded, not triggered.
- The FHIR event-handler tests assert states and effects, not timing.
- `test_gp_escalation_notification_chain.py` never sweeps its triggered
  burden. The claim tests never sweep.
- Two tests in `tests/test_referral_event_triggers.py` call
  `_activate_triggered_tokens()` directly and gained `tick=0`; their
  assertions are unchanged.

### Tests

`tests/test_am100_engine_deadline_from_activation.py` (new), 8 tests, on
a minimal fixture where every burden has a 5-step deadline, is granted at
tick 0, and (where triggered) is activated at tick 10.

Part 1 (6 tests):
- A burden activated by `emits`, by `fire_event()`, and by the 7b
  `activate` op each violates at tick 15 and not at 14, keeping
  `granted_at_tick == 0`.
- A token granted at tick 3 counts from 3; `activated_at_tick` stays None.
- A repeated event on a still-active token does not restart its deadline.
- C1: a claim at tick 10 still violates at grant + 20
  (`erequesting_claiming_scenario.el`).

Part 2 (2 tests there, plus 1 in `tests/test_referral_event_triggers.py`):
- A repeated event leaves a discharged token discharged, and a violated
  token violated (both reached through the real action and sweep).
- On the real referral runtime, a second `status=finished` Encounter after
  `referralInitiationBurden` is discharged yields `"fired_no_match"` with
  empty effects.

**Undo-and-rerun checks:**

| Reverted | Tests failing |
|---|---|
| Old `tick - tok.granted_at_tick` comparison | 4 (emits, fire_event, `activate` op, repeated event); fresh-token and C1 tests pass, as intended |
| Part 1 guard (`state != "active"`) instead of `== "pending"` | 2 (both part-2 reactivation tests) |
| Logging every matching name | 1 (the `fired_no_match` test) |

**Verification:** full suite (`pytest -c pytest.ini`) — 590 passed, 1
xfailed after part 1 (584 + 6); 593 passed, 1 xfailed after part 2
(+3).

### Decisions to revisit

Judgement calls made in AM-99a and AM-100, one line each:

- **C1 counts from grant (AM-100):** pool deadlines are worded from the offer ("4 hours from referral delegation"), and both layers already agreed; revisit if a pool deadline is ever worded from the claim.
- **7b `activate` sets `activated_at_tick` (AM-100):** a deadline counts from when the obligation becomes live, whatever the route; Kripke does not model 7b, so no layer mismatch.
- **`tick` is a required parameter of `_activate_triggered_tokens()` (AM-100):** a default would silently stamp the wrong tick for any caller that forgot it.
- **Claimable tokens no longer activated by events (AM-100 part 2):** mirrors P6a/T11 (only WAITING activates) and keeps claim as the only route out of `claimable`; no scenario combines the two.
- **T11 excludes gated actions and discharging actions (AM-99a part 2):** discharging actions because firing one without its discharge activated dependents with no refusal recorded, breaking the strict burden's property. **Gated exclusion resolved by AM-99b part 3:** gated actions fire their events through T5 (exercise) and T6 (gated discharge, which also runs P6a), in both builders, matching the engine's Step 7c after its Step 6 permit check; T11's exclusion is now by design.
- **T11 shares T3's strict guard (AM-99a part 2):** mirrors the engine's Step 3.5 guard (AM-78), which blocks no-progress actions while a strict obligation is actionable.
- **`KripkeModel.response_semantics` flag is temporary (AM-99a part 3):** keeps hybrid verdicts (and `el_api.py`'s compelled/detectable fields) unchanged until AM-99b aligns hybrid mode and removes it. **Removed by AM-99b part 5**; no hybrid verdict changed.
- **Bounded response property excludes horizon-step worlds (AM-99a part 3):** only tick expands a horizon-step world, so any other horizon-step world is an artificial dead end; open finding "Kripke builders expand horizon-step worlds only when a tick produces them".

**Standard reference(s):** §7.8.7 (token lifecycle): a triggered token's
obligation is in force from activation, not before, and a token that has
completed its lifecycle (discharged, violated) is not re-entered by a
later event. Annex C (Kripke semantics, informative), §C.2, for the
matching verifier behaviour (AM-99a part 1; P6a/T11 WAITING-only
activation).

**Files changed:** `toolchain/el_engine.py` (`TokenInstance.activated_at_tick`,
`_activate()`, `_activation_tick()`, `_activate_triggered_tokens()`,
Step 7b `activate`, `check_live_violations()`, field carried through
copies; docstrings); `toolchain/fhir_event_handler.py` (`fired_no_match`
docstring and message); `toolchain/el_api.py` (`/check-violations`
description); `toolchain/el_kripke.py` (`World.activation_steps`
docstring only); `tests/test_am100_engine_deadline_from_activation.py`
(new); `tests/test_referral_event_triggers.py` (`tick=0` on two direct
calls; one new test); `tests/test_am99a_deadline_from_activation.py`
(docstring correction); `docs/KRIPKE_TRANSITION_RULES.md` (T2 row,
last-updated note); `docs/CONCEPTS_INDEX.md` (finding resolved;
symmetry-gap finding updated); this file (new entry).

---

## AM-99b (2026-09-25) — hybrid mode mirrors the engine's event model; T5/T6 fire action events; `response_semantics` flag removed (`toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-25), in six parts (commits `86f5c23`,
`01d4270`, `e462791`, `736f5c2`, `ee12a71` and this docs commit),
preceded by a scenario fix (`8733915`). Type: toolchain change (Layer 4,
Kripke verifier). No grammar or validator change. Extends AM-99a's T11
and bounded response verdict to hybrid mode (`build_kripke_from_runtime()`).
Principle: in hybrid mode, the model mirrors the live engine's own event
handling (Step 7c, AM-100) rather than reusing the static rules
unchanged — the same layer-fidelity approach T9 took. Prerequisite
AM-100 confirmed on origin/main before starting.

### Preceding scenario fix — `noCircumventionEmbargo` blocks only retry-by-other-route (`8733915`)

`external_agent_access_scenario.el` put `inhibited_by_embargo
noCircumventionEmbargo` on `submitServiceRequest` and
`readPatientDemographics`, so a single refusal would have blocked every
legitimate referral permanently; time-bounded quarantine is already
`RefusalQuarantinePolicy`'s job. Removed from both; the embargo's
`for_action` became `"retryByOtherRoute"` (AM-97 literal match), and a
new action `retryByOtherRoute` on `externalRequesterRole` carries the
`inhibited_by_embargo`. The scenario validates; static model unchanged
at 2444 worlds / 5924 edges, same three response verdicts. After a
refusal the engine blocks `retryByOtherRoute` and allows submit and
read, and the verifier's inhibition index names only
`retryByOtherRoute`.

### Part 1 — hybrid w0 seeding and T2 from activation (`86f5c23`)

- An engine `pending` burden with `triggered_by` maps to `WAITING`.
  **A `pending` burden without `triggered_by` stays `PENDING`**
  (masked while delegated, §7.8.7 — ereferral's three masked burdens);
  mapping it to `WAITING` would strand it.
- Every burden `PENDING` at w0 has its engine activation tick
  (`_activation_tick()`: `activated_at_tick`, else `granted_at_tick`)
  seeded into `w0.activation_steps`, in the same absolute-tick unit as
  hybrid `w.step`.
- **T2 defect:** hybrid T2 compared `w.step >= deadline_steps`, with
  `w.step` the absolute runtime tick — counting from neither grant nor
  activation. It now counts `w.step - activated_at`, matching static T2
  and `check_live_violations()`. Probe before the fix: a burden
  activated at tick 8 with an 8-step deadline had violate edges from
  step 9; the engine violates at 16.
- **Separate defect, also fixed:** every hybrid successor world dropped
  `activation_steps` (none of the ten hybrid `_make_world` calls passed
  it), so even a correctly seeded w0 would have lost its seeds after one
  transition. All ten now thread it through.
- The fallback descriptor path (tokens with no Commitment root) now
  reads `triggered_by`/`discharged_by` from the spec token instead of
  hard-coding `None`.

### Part 2 — hybrid T11, P6a and event-activated embargoes (`01d4270`)

- Hybrid T11: same eligibility as static T11
  (`_build_event_firing_index()`), over the live-sourced descriptors;
  taken only if the event activates something in the world. It keeps
  the strict guard (`strict_burden_blocks()`), matching the engine's
  Step 3.5; no step advance.
- `_fire_event()`, the hybrid counterpart of `_activate_triggered_tokens()`:
  `WAITING` obligations become `PENDING` (activation step recorded), and
  every Permit/Embargo named by the engine's own
  `_find_spec_tokens_for_event()` whose per-world state is `pending`
  becomes `active`. This is how `noCircumventionEmbargo` is activated on
  `accessRefused`.
- Hybrid T1 now runs P6a on the burden's `discharged_by` event.
- **Pre-existing defect, fixed:** the hybrid T5/T6 Embargo guards read
  only the w0 state (`embargo_holder_index`), never the per-world
  `embargo_states`, so an embargo activated inside the model never
  blocked anything. It was masked because T7 (the only rule that changed
  embargo state before) also supersedes the permit, so `_permit_active()`
  blocked the exercise anyway. The guards now use `_embargo_active()`,
  two-tier like `_permit_active()`.
- **The verifier checks the embargo's state; the engine enforces the
  blocking.** The verifier does not model `retryByOtherRoute` (no permit,
  no burden, so no rule produces an edge for it), so it cannot show the
  action blocked. What it verifies is that `noCircumventionEmbargo` is
  active in every world reachable after a refusal; the engine test shows
  the embargo blocks the retry and nothing else. Both halves are tested
  together.
- **The every-world embargo property holds because these terms specify
  no lift for `noCircumventionEmbargo`** (no Authorization names it as
  its `on_revocation` embargo, so no T8 lifts it). It is a property of
  this scenario's terms, not a general guarantee.
- **Hybrid P6b is still missing** (open finding "Hybrid T1 has no P6b").

### Part 3 — T5 and T6 fire action events, both builders (`e462791`)

- T5 (exercise) fires the event its `for_action` emits, on the same
  edge: `WAITING` obligations become `PENDING` (hybrid: also `pending`
  Permits/Embargoes). This is how gated actions fire their events, as
  the engine does in Step 7c after its Step 6 permit check; T11 keeps
  excluding them. An event that is some obligation's `discharged_by` is
  not fired by T5 (as T11), since T1/T6 fire those with the discharge.
- T6 (gated discharge) runs P6a on the obligation's `discharged_by`
  event and fires the gated action's own emitted event.
- New helpers `_build_action_emits_index()` and `_activate_waiting()`
  (shared by both builders); `_fire_event()` takes a list of events.
- No scenario has a gated or permit action with `emits`, so no world
  count moved; tests use an inline fixture.
- **Asymmetry found, not fixed:** neither builder's T5 has a strict-mode
  guard, while the engine's Step 3.5 refuses exercise actions while a
  strict burden is actionable — logged as an open finding and planned
  as the next amendment (it moves the referral scenario's pinned counts).
  **Resolved by AM-101**; no test pinned a count, so none moved.

### Part 4 — hybrid horizon counts from the runtime's tick (`736f5c2`)

The hybrid horizon was absolute: w0.step is the runtime's tick and every
endpoint passes `horizon=10`, so a runtime at tick ≥ 10 expanded only w0
(8 worlds on the terms-of-engagement runtime, against 1374 at tick 0).
Worlds now expand up to `state.tick + horizon`; `KripkeModel.horizon`
stays relative in both builders, and `check_response()` counts its
horizon step from `initial.step`. Measured before landing: no pinned
test changed. The horizon-step enqueue asymmetry (open finding) is
unchanged.

### Part 5 — `response_semantics` flag removed (`ee12a71`)

`check_obligation()` now reports the bounded response property for any
obligation with `triggered_by`, in models from both builders.
**No hybrid verdict changed** (all 16 obligations across the four
scenario builders rechecked against the pre-AM-99b values). The only
triggered obligation in any builder, `referralInitiationBurden`, stays
satisfied: the referral builder grants it `active` at tick 0, so it is
`PENDING` at w0. Only its operator changes, from `AF` to
`AG(pending→AF)` (pre-approved). `test_static_model_sets_response_semantics`
was deleted (it asserted the removed field; approved).

### Deferred, logged as open findings

- **CLAIMABLE:** hybrid mode still maps `claimable` to `PENDING`; a
  hybrid C1 mirroring the engine's live `claim()` is its own amendment
  ("Hybrid mode has no C1").
- **Pending tokens without a trigger stay `PENDING`** (Part 1) —
  deliberate, recorded with the C1 finding.
- **Hybrid P6b** ("Hybrid T1 has no P6b").
- **T5 strict guard** — next amendment ("Rule T5 has no strict-mode
  guard"). **Resolved by AM-101.**
- **Engine Step 5 ignores `inhibited_by_embargo`** — the engine side is
  to change ("Engine Step 5 ignores `inhibited_by_embargo`").

### Blast radius

No pinned verdict or world count moved (checked, not assumed): the four
scenario builders keep 998 / 323 / 3992 / 44 hybrid worlds (all at tick
0, no `WAITING` obligation or pending Permit/Embargo at w0); the static
scenarios keep consent 30, referral 280, terms-of-engagement 2444.

### Tests

`tests/test_am99b_hybrid_event_model.py` (new), 23 tests:
- Part 1 (5): no-event runtime matches the static w0; masked `pending`
  stays `PENDING`; activation tick seeded from the engine; seed falls
  back to grant tick; a burden activated at tick N is violated no
  earlier than N + deadline.
- Part 2 (8): after-refusal w0 mirrors the engine; response verdicts
  match static; `noCircumventionEmbargo` active in every reachable
  world; engine blocks only `retryByOtherRoute`; hybrid T11 fires the
  refusal; T11 suppressed while a strict burden is actionable; hybrid
  P6a; an event-activated embargo blocks exercise per world (inline
  fixture).
- Part 3 (8, both builders): triggered burdens start `WAITING`; T5
  fires a gated action's event; T6 fires emits and runs P6a; the
  triggered burdens are reachable.
- Part 4 (2): model shape invariant under a pure clock shift; response
  verdicts past the old absolute horizon match static.

`tests/test_am99a_bounded_response.py`: the pinned hybrid test became
`test_hybrid_model_uses_response_semantics` (operator label only);
`test_static_model_sets_response_semantics` deleted.

**Undo-and-rerun checks:** reverting each part's code fails 4 (part 1),
4 (part 2), 6 (part 3) and 2 (part 4) of that part's tests; the rest
are guards or properties that hold either way (e.g. the every-world
embargo property, the engine-only test).

**Verification:** full suite (`pytest -c pytest.ini`) — 593 → 598 → 606
→ 614 → 616 → 615 passed, 1 xfailed.

**Standard reference(s):** §7.8.7 (token lifecycle: a triggered token is
in force from activation; masked `pending` tokens); §6.4.6 (Embargo;
Action-level inhibition); Annex C (Kripke semantics, informative), §C.2.

**Files changed:** `toolchain/el_kripke.py` (`build_kripke_from_runtime()`
w0 mapping, seeding, T1 P6a, T2, T5/T6 guards and event firing, T11,
relative horizon; static T5/T6 event firing; `_build_action_emits_index()`,
`_activate_waiting()`; `check_obligation()`/`check_response()`;
`response_semantics` removed; docstrings);
`scenarios/terms_of_engagement/external_agent_access_scenario.el`;
`tests/test_am99b_hybrid_event_model.py` (new);
`tests/test_am99a_bounded_response.py`; `docs/KRIPKE_TRANSITION_RULES.md`
(T1, T2, T5, T6, T11 rows; related notes; last-updated note);
`docs/CONCEPTS_INDEX.md` (symmetry-gap, hybrid-`WAITING` and
horizon-enqueue findings updated; four new open findings); this file
(AM-100's "Decisions to revisit" updated; new entry).

---

## AM-101 (2026-09-26) — Rule T5 strict-mode guard, both Kripke builders, mirroring the engine's Step 3.5 (`toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-26), in four parts (commits `17945c0`,
`d536176`, `b3ed020` and this docs commit). Type: toolchain change
(Layer 4, Kripke verifier). No grammar, validator or engine change.
Resolves the CONCEPTS_INDEX finding "Rule T5 has no strict-mode guard;
the engine's Step 3.5 refuses the same actions" (found during AM-99b
part 3).

**Problem.** The engine's Step 3.5 (AM-78, `el_engine.py`) refuses an
action when its Step 3 `dischargeable` list is empty and
`_strict_actionable_burdens()` is not: some `active`,
`discharge_mode: strict` burden whose holder is enrolled. Exercising a
permit discharges nothing unless its action also discharges a burden
the actor holds. T3, T4, T7–T11 already had the equivalent guard; T5 did
not, so the verifier explored exercise edges the engine refuses, and
since AM-99b part 3 such an edge could also fire the action's event.

### Part 1 — static builder (`17945c0`)

T11's `strict_blocks` (PENDING, strict, holder `ACTIVE`: textually the
same condition as T3's `has_strict_pending_dischargeable`) is computed
once above T5 and shared by T5 and T11. T5 skips a permit when
`strict_blocks` holds and `_discharges_any()` is false. New module
helpers: `_build_action_destroys_index()` (action → tokens its `destroy`
effects name; first match per action name, as the engine's
`_find_action()`), and `_discharges_any()`, the verifier's copy of Step
3's `dischargeable`: some PENDING obligation held by the permit holder
that the action destroys, matches by `for_action`, or discharges by
emitting its `discharged_by` event. The static `for_action` comes from
`_build_obligation_descriptors()` (token `for_action`, else
`_find_action_for_burden()`), the same source `token_from_spec()` uses.

### Part 2 — hybrid builder (`d536176`)

Same guard, using `strict_burden_blocks(w)`. Holders are read through
`_effective_holder()` (revoked delegation, T9 override), as
`strict_burden_blocks()` reads them. `for_action` is read from the live
tokens, as the engine's Step 3 does: a hybrid descriptor built without a
spec descriptor has `for_action` None.

**Engine mirror, not a blanket guard.** An exercise whose action
discharges a burden the holder holds is kept, as the engine accepts it;
T1/T6 still draw the discharge as their own edge. No scenario has that
overlap today: the engine-mirroring guard and a blanket guard produce
identical models for every scenario (harness rerun after Part 2).

### Blast radius (horizon 10, measured before landing)

| Scenario | Builder | Worlds | Edges | Exercise edges removed |
|---|---|---|---|---|
| `referral_scenario.el` | static | 280 → 272 | 632 → 604 | `patientRecordAccessPermitByAuthorization` |
| | hybrid (`referral` builder) | 3992 → 3976 | 16350 → 16286 | same |
| `gp_referral_scenario.el` | static, spec-only (`validate=False`) | 67 → 61 | 122 → 105 | same |
| | hybrid (`gp_referral` builder) | 998 → 994 | 3458 → 3446 | same |
| `ereferral_model.el` | hybrid (`ereferral` builder) | 323 → 315 | 659 → 631 | `patientRecordAccessPermit` |
| `external_agent_access_scenario.el` | static | 2444 → 2444 | 5924 → 5840 | `serviceRequestSubmitPermit`, `patientLookupPermit` |
| | hybrid, fresh | 16340 → 16340 | 59176 → 58840 | same |
| | hybrid, after one refusal | 9114 → 9111 | 32066 → 32059 | same |
| `public_data_portal_scenario.el` | static | 2444 → 2444 | 5924 → 5840 | `aggregateQueryPermit`, `publishedDatasetReadPermit` |
| | hybrid, fresh | 16340 → 16340 | 59176 → 58840 | same |
| `fhir/generated_governance.el` | static | 4 → 3 | 4 → 2 | `ConsentAiDiagnostic001Permit` |

Every other scenario is unchanged in both builders (consent stays 30;
`erequesting_claiming` 44 hybrid). In the terms-of-engagement scenarios
the world count holds because the same exercise worlds are still
reached by exercising after `recordRefusal`; only the out-of-order edges
go. **No AF, EF or bounded response verdict changed, no EF witness path
changed, and no `WAITING` obligation lost an activation** (none of the
removed exercise actions emits an event). The terms-of-engagement
reading is unchanged in both scenarios and both builders: recording
refusals compelled (`refusalRecordBurden` holds); review and
notification detectable only (fail, EF true). No test pinned a world or
edge count, so none moved; the CONCEPTS_INDEX finding's expectation
that pinned counts would move was wrong.

### Tests

`tests/test_am101_t5_strict_guard.py` (new), 20 tests:
- Parity, inline fixture (8): a strict burden held by one actor; four
  permits held by another, one per `dischargeable` arm (none, matching
  `for_action`, `destroy` effect, emitted `discharged_by` event). The
  engine refuses only the first; each builder's w0 has exactly the
  engine-accepted exercises; after the strict discharge the refused
  exercise returns (control).
- Parity, terms of engagement (1): after a refusal the engine refuses
  both exercises with the strict reason; hybrid w0 and every static
  world with the same obligation states have no T5 edge.
- Invariant (11): no T5 edge leaves a strict-blocked world, static over
  the six affected scenario files, hybrid over the five affected
  runtimes.

**Undo-and-rerun checks:** against the pre-AM-101 `el_kripke.py`, 13 of
the 20 fail (the static ereferral invariant is vacuous: no permits in
the static model); with `_discharges_any()` forced false (a blanket
guard), the two inline-fixture parity tests fail.

**Verification:** full suite (`pytest -c pytest.ini`) — 620 → 620 → 620
→ 640 passed, 1 xfailed.

### Decisions to revisit

- **Engine "enrolled" vs verifier `ActorStatus.ACTIVE`.** No transition
  rule produces `INACTIVE`, and the static builder has no enrollment:
  every chain member and permit holder is `ACTIVE` in every world. The
  engine has no un-enroll primitive, so enrollment only grows; T9's
  to-actor is resolved from enrolled actors. The two can diverge only
  when a strict burden's holder, or a revoked delegation's delegator, is
  never enrolled (`grant_token()` does not check). The engine then does
  not block and the verifier does. In every curated runtime (the four
  `el_api` builders, both terms-of-engagement runtimes) every strict
  holder and every delegator is enrolled, so **no reachable world
  diverges there**. A static model corresponds to a runtime that
  enrolls every chain member.
- **A kept exercise does not discharge in the model.** When the permit's
  action also discharges a burden, the engine does both in one step;
  the verifier keeps T5 (occurrence) and T1/T6 (discharge) as separate
  edges. Pre-existing split, not introduced here; no scenario exercises
  it.
- **Action-name lookup.** `_build_action_destroys_index()` takes the
  first action of a name (as the engine); `_build_action_emits_index()`
  (AM-99b) takes the last. They can differ only for a duplicated action
  name; no scenario has one.

**Standard reference(s):** §6.4.5 (Permit: a standing grant, not
consumed by exercise); §7.8.7 (token lifecycle, discharge); Annex C
(Kripke semantics, informative), §C.2.

**Files changed:** `toolchain/el_kripke.py` (static and hybrid T5
guard; `_build_action_destroys_index()`, `_discharges_any()`; static
T11 shares the hoisted `strict_blocks`; docstrings);
`tests/test_am101_t5_strict_guard.py` (new);
`docs/KRIPKE_TRANSITION_RULES.md` (T5 row, last-updated note);
`docs/CONCEPTS_INDEX.md` (finding resolved and corrected); this file
(AM-99b's deferred list updated; new entry).

---

## AM-102 (2026-09-26) — one embargo blocking rule for the engine and the verifier; embargo guards on T1, T9, T11; `[W-18]` (`toolchain/el_engine.py`, `el_api.py`, `el_kripke.py`, `el_validator.py`)

**Status:** IMPLEMENTED (2026-09-26), in six parts (commits `2c35c93`,
`98a6bc4`, `996ea32`, `4d62585`, `17506fd` and this docs commit). Type:
toolchain change across Layers 2–4 plus one advisory validator warning.
No grammar change. Resolves the CONCEPTS_INDEX finding "Engine Step 5
ignores `inhibited_by_embargo`; the verifier's guards rely on it". The
earlier decision held: the verifier keeps §6.4.6 (the Action declares
what inhibits it); the engine changed.

**Problem.** The engine's Step 5 blocked an action when an active embargo
held by the actor had that action as its `for_action`, or had none. It
never read `inhibited_by_embargo`. The verifier's T5/T6 guards read only
`inhibited_by_embargo` and never `for_action`, and T1, T9 and T11 had no
embargo guard. On an inline fixture the layers disagreed for every
class: (b) `for_action` set, named by no Action — engine blocks, builders
draw the edge; (c) named by an Action other than its `for_action` — each
layer blocks the other's action; (d) general — engine blocks everything,
builders nothing.

### The rule (`el_engine._embargo_coverage()`)

An action A by actor X is blocked iff X holds an `active` embargo E that
covers A:
1. if any role Action declares `inhibited_by_embargo E`, E covers exactly
   those Actions — `for_action` does not affect blocking;
2. else, if E has a `for_action`, E covers that action (fallback — keeps
   the 16 class (b) embargoes in the tracked scenarios working);
3. else E is general and covers every action of X (the pre-AM-102 engine
   behaviour; covering nothing would silently weaken a prohibition).

The holder must be the actor performing the action, in both layers.
ConditionalAction `inhibited_by` is not read by either layer (open
finding). Top-level embargo tokens only, as `token_from_spec()`.

### Part 1 — engine and API (`2c35c93`)

`_embargo_coverage()` and `_embargo_covers()` in `el_engine.py`. Step 5
reads them (it runs for every action, discharging ones included, and for
action names with no declared Action). `el_api.get_available_actions()`,
which had copied Step 5's old rule, reads them too.

### Part 2 — verifier index, T5/T6 (`98a6bc4`)

`_build_embargo_inhibition_index()` is now built from
`_embargo_coverage()` (named Actions, else `for_action`);
`_build_general_embargoes()` lists rule 3. Each builder has one
`embargo_blocks` closure (static: declared state, `holds` holder; hybrid:
per-world state, w0 token holder) used by T5 and T6. The index's dead
ConditionalAction loop was removed.

### Part 3 — T1, T11, T9 (`996ea32`)

Mirrors the engine's performer for each rule:
- **T1** (both builders): the performer is the burden's (effective)
  holder; suppressed if it holds an embargo covering the `for_action`.
- **T11** (both builders) and **T9** (hybrid): the engine lets any
  enrolled actor perform an ungated action (Step 2 checks only
  enrolment; a transfer's `from_role` resolves the source holder, not
  the performer), and Step 5 refuses only an embargoed one. So the edge
  is suppressed only when every performer holds a covering embargo —
  static: every `ACTIVE` actor; hybrid: every enrolled actor.

### Part 4 — `[W-18]` (`4d62585`)

Advisory, via the AM-89 warnings channel: an embargo named by ≥1 Action
whose `for_action` is outside that set (the `for_action` is ignored under
rule 1). Built from `el_engine._embargo_naming_actions()`, extracted from
`_embargo_coverage()` so the warning and the rule share one map. The
validator imports it lazily, as its other rules import `el_reasoner`;
`el_engine` imports no toolchain module at load time (its only one,
`el_parser`, is in the `__main__` block), so there is no cycle. Fires on
no tracked scenario.

### Inventory (10 scenario files declare embargoes)

| Scenario | Embargo | `for_action` | Named by | Runtime holder | Class |
|---|---|---|---|---|---|
| terms of engagement, public data portal | `noCircumventionEmbargo` | `retryByOtherRoute` | `retryByOtherRoute` | agent (test grant) | a |
| public data portal | `outsideScopeEmbargo` | `accessNonPublicFile` | `accessNonPublicFile` | agent | a |
| terms of engagement | `outsideScopeEmbargo` | `access_unlisted_resource` (undeclared) | — | agent | b |
| referral, gp_referral | `patientRecordAccessEmbargo` | `access_patient_clinical_records` | — | permit holder, via revocation | b |
| fhir generated | `ConsentAiDiagnostic001SubProv2Embargo` | `disclose` (undeclared) | — | permit holder, via revocation | b |
| industrial + 3 SOP variants | 2–4 each | undeclared actions | — | none granted | b |
| ecommerce (does not parse) | `auditorCustomerEmargo` | none | — | none | d |

No class (c) in any tracked scenario (the historical instance was
`external_agent_access_scenario.el` before `8733915`). No scenario uses
ConditionalAction `inhibited_by` or the token-level
`inhibited_by_embargo` string. No embargo is given a holder with `holds`.

### Blast radius

Measured before landing, against the pre-AM-102 code: **engine outcomes
identical** for every enrolled actor × action on 14 runtime states (the
four `el_api` builders; both terms-of-engagement runtimes fresh, after a
refusal, after recording it and after a revocation; referral and
gp_referral after a revocation), including available-actions. **Kripke
counts and verdicts identical** for every static, hybrid and spec-only
model, and for six hybrid models built after revocation or recording;
Part 3 moved nothing either (the only T1 overlap,
`automatedPressureTripEmbargo`, is held by nobody). The
terms-of-engagement reading is unchanged. No existing test failed at any
part.

### Tests

`tests/test_am102_embargo_parity.py` (new), 19 tests: the coverage rule
on the fixture; engine outcome per case (8: classes b, c, d, exercises
and discharges); both builders' w0 exercise/discharge edges equal the
engine-accepted set (2); available-actions; `[W-18]` flags exactly the
class (c) embargoes and no tracked scenario (2); T11 kept while one
actor is not embargoed, suppressed when every performer is, with the
engine (3); T9 likewise (2).

**Undo-and-rerun checks:** against the pre-AM-102 toolchain, 11 of 19
fail (the 8 that pass are cases the old engine already blocked, the
"kept" controls and the scenario-wide `[W-18]` silence); against Part 2
without Part 3, the T1/T11/T9 tests fail (4).

**Verification:** full suite (`pytest -c pytest.ini`) — 640 → 640 → 640
→ 640 → 659 → 659 passed, 1 xfailed.

### Decisions to revisit

- **Rule 3 (general embargoes block every action)** — kept from the
  engine for fail-closed behaviour. Only ecommerce, which does not parse,
  has one.
- **T11/T9 performer set** differs by builder: static has no enrolment,
  so it uses every `ACTIVE` actor (chain members and permit holders);
  hybrid uses enrolled actors, as the engine does.
- **T1 checks `for_action` only.** The engine also discharges through a
  destroy effect or an emitted `discharged_by` event, under that
  action's own name; T1 does not model which action discharged, so an
  embargo covering such an action is not seen by T1.
- **available-actions lists "obligated" entries without an embargo
  check** (pre-existing; only "permitted" entries are filtered).
  **Resolved by AM-103** (`"obligated_blocked"`).

Logged as open findings in CONCEPTS_INDEX (2026-09-26): V-17 compares
`for_action` strings, not coverage; embargo holder resolution (static
`holds` only, one hybrid holder per name, T7-created embargoes without a
holder); `grant_token()` does not check enrolment; Step 3.5 as a
denial-of-service vector; strict mode, model vs deployment.

**Standard reference(s):** §6.4.4 (Embargo), §6.4.6 (conditional action:
the Action declares what inhibits it), §7.8.7 (token lifecycle); Annex C
(Kripke semantics, informative), §C.2.

**Files changed:** `toolchain/el_engine.py` (`_embargo_naming_actions()`,
`_embargo_coverage()`, `_embargo_covers()`; Step 5); `toolchain/el_api.py`
(available-actions); `toolchain/el_kripke.py`
(`_build_embargo_inhibition_index()` rebuilt, `_build_general_embargoes()`;
`embargo_blocks` in both builders; T1, T5, T6, T9, T11 guards;
docstrings); `toolchain/el_validator.py` (`[W-18]`);
`tests/test_am102_embargo_parity.py` (new);
`docs/KRIPKE_TRANSITION_RULES.md` (T1, T5, T6, T9, T11 rows;
last-updated note); `docs/CONCEPTS_INDEX.md` (finding resolved;
ConditionalAction finding updated; OPEN FINDING marker on the V-NEW-10
paragraph; five new open findings); this file (new entry).

---

## AM-103 (2026-09-26) — `[W-19]`/`[W-20]` for strict burdens without a safety net; available-actions `obligated_blocked`; stale strict-mode text retired (`toolchain/el_validator.py`, `el_api.py`, `el_engine.py` docstring)

**Status:** IMPLEMENTED (2026-09-26), in four parts (commits `69a1501`,
`c8a4b13`, `422ea03` and this docs commit). Type: validator warnings
(advisory) plus an API response value. **No semantics change** in the
engine or the verifier. Follows the CONCEPTS_INDEX findings "Step 3.5 as
a denial-of-service vector" and "Strict mode, model vs deployment".

**Design context (2026-09-26, design chat):** a blocking-compelled strict
burden is to get its deployment safety net from an external, authorised
violation declaration (later amendment). That declaration needs a
deadline and a ViolationResponse; this amendment flags strict burdens
that lack them. Also decided: the Step 3.5 freeze is narrowed from
system-wide (candidate: holder scope plus explicit embargoes for
cross-actor blocking, community scope as fallback; tested in the scope
amendment's Phase 1 by remodelling the terms-of-engagement scenarios);
weak fairness accepted either way. Both recorded in CONCEPTS_INDEX.

### Part 1 — `[W-19]`, `[W-20]` (`69a1501`)

Both advisory (AM-89 channel), over top-level DeonticTokens and
role-scoped InlineTokens (`_strict_burdens()`).

- **`[W-19]`** — a strict burden without a deadline carrying an
  elapsed-time magnitude: `el_engine._has_deadline_magnitude()` false,
  the same test `check_live_violations()` uses for a genuine deadline.
  The token's own `deadline` is the only source (Commitment has no
  deadline field). A prose deadline ("clinical session") or a bare
  number only yields `_parse_deadline_steps()`'s default of 5, which does
  not count. Two message variants: no deadline; deadline without
  magnitude.
- **`[W-20]`** — a strict burden that no ViolationResponse names in
  `on_violation_of`. Fires on every such burden, including likely-noise
  cases the validator cannot tell apart; the message names the
  exception: not needed if the enforcement point discharges the burden
  atomically.

Fires on (tracked scenarios): `[W-19]` — 7 burdens (both consent files,
ereferral, fhir generated, transfer probe, both terms-of-engagement
files); `[W-20]` — all 15 strict burdens in the 13 parseable files with
one (no strict burden in any scenario has a ViolationResponse). Likely
noise, kept by decision: the transfer probe and SOP test variants
(fixtures for other rules), `pressureInterlockTrip` (declared an
automatic trip — executing-compelled), `escalationNoticeBurden` (itself
created by a ViolationResponse).

**Existing tests scoped, not re-pinned** (by decision): 11 tests pinned a
scenario's exact warning list. Each now asserts only the codes it is
about — `test_am91` `[W-16e]`, `test_am93` the `[W-16*]` family,
`test_am95` `[W-16g]`, `test_am96` `[W-16h]`; `test_am89`'s clean-scenario
test and the public data portal fixture accept no warnings other than
`[W-19]`/`[W-20]`, with a comment that these are known deployment gaps
pending the violation-declaration amendment. No scenario changed.

### Part 2 — available-actions `obligated_blocked` (`c8a4b13`)

An "obligated" entry whose action is covered by an active embargo the
actor holds (`_embargo_coverage()`, as the engine's Step 5) is kept, with
reason `"obligated_blocked"`, so a stuck obligation stays visible. The
response-model comment and endpoint description list `"obligated" |
"obligated_blocked" | "permitted"`. Consumers checked first: the
coordination simulator ignores `reason` (renders every entry as
executable); the ereferral simulator matches `/obligat|required/i`, so
the new value would show as "Required" and clickable. Neither crashes;
both are updated in a separate `computable-governance-ui` commit
referencing AM-103. The endpoint still ignores Step 3.5 during a strict
freeze — logged under "Step 3.5 as a denial-of-service vector", for the
scope amendment.

### Part 3 — tests (`422ea03`)

`tests/test_am103_strict_safety_net.py` (new), 17 tests: `[W-19]` no
deadline, prose and bare-number deadlines, silence with a magnitude and
for eventual burdens; `[W-19]`/`[W-20]` on an inline strict burden;
`[W-20]` firing, silence when named and for eventual; the consent and
referral scenarios' exact hits; available-actions parity with Step 5
(`obligated_blocked` iff the engine refuses by embargo). **Known open
finding pinned as current behaviour** (6): a strict burden whose
discharging action is embargoed (case A) or whose required permit was
revoked (case B) — engine entry points and both builders' dead end.
Against the pre-AM-103 validator/API, the 7 firing and parity tests fail;
the silence and deadlock tests hold either way.

### Part 4 — docs

- `check_live_violations()` docstring: the exclusion of strict burdens is
  kept, with the true reason (the engine refuses `advance_clock()` and
  non-discharging actions while a strict burden is actionable, so elapsed
  ticks do not measure the holder's delay; violation is to come from an
  external declaration). The old text said nothing suppressed the clock,
  untrue since AM-49/76/78.
- CONCEPTS_INDEX: the 2026-08-20 finding "`discharge_mode: strict` —
  enforcement exists only in the verifier" marked **SUPERSEDED**, pointing
  to the two 2026-09-26 findings; "Strict mode, model vs deployment"
  gains the `refusalRecordBurden` instance (modelled as a separate gateway
  action, so blocking-compelled; deployment needs refuse-and-record to be
  atomic) and the design decisions; "Step 3.5 as a denial-of-service
  vector" gains the freeze-scope decision and the available-actions note;
  new OPEN FINDING "A strict burden whose discharge is itself blocked
  deadlocks" (engine entry-point table, verifier dead end).

**Verification:** full suite (`pytest -c pytest.ini`) — 659 → 659 → 676
→ 676 passed, 1 xfailed.

**Standard reference(s):** §6.4.3 (Burden), §7.8.7 (token lifecycle:
deadlines), §6.3.8 and §7.8.6 (violation and its response), §6.4.4 and
§6.4.6 (Embargo, conditional action — available-actions).

**Files changed:** `toolchain/el_validator.py` (`[W-19]`, `[W-20]`,
`_strict_burdens()`; header); `toolchain/el_api.py` (available-actions);
`toolchain/el_engine.py` (`check_live_violations()` docstring);
`tests/test_am103_strict_safety_net.py` (new); `tests/test_am89_…`,
`test_am91_…`, `test_am93_…`, `test_am95_…`, `test_am96_…`,
`test_public_data_portal_scenario.py` (assertions scoped);
`docs/CONCEPTS_INDEX.md`; this file.

---

## AM-104 (2026-09-26) — violation responses that act: `response_kind` read by the engine; `[W-21]`–`[W-23]`; status endpoint names its property (`toolchain/el_engine.py`, `el_validator.py`, `el_api.py`)

**Status:** IMPLEMENTED (2026-09-26), in five parts (commits `f9d077b`,
`4fac549`, `c1a8cfb`, `25a1ca5` and this docs commit). Type: engine semantics
(Layer 3 only), validator warnings (advisory), API response fields. **No
grammar change; no verifier change.** Resolves the CONCEPTS_INDEX finding
"`response_kind` is read by nothing; only `creates_burden` responses ever
fire" (2026-09-26), including its status-endpoint part.

**Design context (2026-09-26, design chat):** "detectable" must mean
"violation recorded AND answered". This amendment makes responses act;
the violation-declaration and `discharged_by` amendments follow it.

### Part 1 — engine (`f9d077b`)

- **Once-only marker.** `WorldState.responded`: a frozenset of
  (response name, violated token name, holder, granted_at_tick), one per
  violated token instance. `with_tokens()`, `with_tick()` and `enroll()`
  carry it; `with_responded()` sets it. `fire_violation_responses()` fires
  a response once per violated instance whose key is absent, then adds
  the key. A re-granted instance (new granted_at_tick) can fire again.
  The old once-only condition ("obligates does not hold creates_burden
  'active' or 'discharged'") only worked for responses with
  creates_burden; it survives only as a duplicate-grant guard (not
  granted again while obligates holds it 'active'; logged).
  **Edge case:** two instances of the same token granted to the same
  holder in the same tick share a key, so only the first violation of
  the two fires. Not reachable in any tracked scenario.
- **Firing by kind** (§7.8.6). Every kind fires, with or without
  creates_burden. Effects and ledger lines in order: (1) grant
  creates_burden, if set; (2) `escalate_to` ledger line, if set; (3) a
  line naming the response_kind and the violator — first when there is
  no grant line, so the pre-existing grant-first order is unchanged;
  (4) terminate only: revocations. escalate, remediate and penalise do
  nothing beyond 1–3.
- **terminate.** Revokes every Authorization whose `to_agent` is in
  `_violator_chain()` of the violated instance's holder (the holder,
  objects whose `delegated_from` chain leads to it, objects it is
  transitively `principal_of`; static declarations only), that is
  revocable with an `on_revocation` embargo, whose permit is still
  active, and whose `authority` is the response's `obligates`. Any other
  Authorization in the chain gets a `not revoked '…': …` ledger line; the
  response still counts as fired. `to_role` Authorizations are not
  covered (open finding).
- **Strict freeze.** `revoke_authorization()`'s token effects moved into
  `_apply_revocation()` (no guard, no tick, no ledger). The public
  `revoke_authorization()` keeps its strict guard and calls it;
  terminate calls it directly, so a response revokes while a strict
  burden is actionable: a response is an institutional act, not an
  ordinary governed action. Step 3.5 is unchanged for `advance()`.
  (`check_live_violations()` and `fire_violation_responses()` already
  ran unguarded.)
- **Engine-only.** The verifier models no response firing (confirmed in
  Phase 1). A hybrid model built after firing reflects the new state
  (portal scenarios after the 2.10b violation: 28 → 24 worlds, every
  verdict unchanged). The static builder's treatment of response-created
  burdens is wrong and is logged as an open finding.
- Docstrings: `el_runtime.fire_violation_responses()`; the
  `/fire-violation-responses` endpoint description.

### Part 2 — tests (`4fac549`)

`tests/test_am104_violation_responses.py` (7): DN_019 step 2.10b in both
terms-of-engagement scenarios (terminate revokes both Authorizations,
permits superseded, the agent's read blocked, second fire a no-op with
no tick); the missed-review case in both (escalate as a ledger entry
only, no token change, agent unaffected); terminate during a strict
freeze (direct revoke refused, response revokes, Step 3.5 still blocks
the agent); authority mismatch (ledger note, not revoked, still fired);
re-firing on a re-granted instance (and "permit not active" instead of
a second revocation). `tests/test_fire_violation_responses.py` is
unchanged and passes.

### Part 3 — validator (`c1a8cfb`)

All advisory (AM-89 channel).

- **`[W-21]`** — a terminate response that would revoke nothing: no
  Authorization to the violator chain is revocable with an
  `on_revocation` embargo and granted by `obligates`. The holder is the
  one `el_engine._build_obligation_descriptors()` resolves; a burden with
  no descriptor is skipped. Fires on no tracked scenario (both
  terminate responses have two qualifying Authorizations).
- **`[W-22]`** — an escalate response with no creates_burden: "fires as
  a ledger entry only; nobody becomes obligated" (§7.8.6 NOTE 2). Fires
  on 4: ereferral `examinationViolation`, `acknowledgementViolation`; both
  terms-of-engagement `missedReviewResponse`s.
- **`[W-23]`** — the dormant V-NEW-16 (`el_domain.ViolationResponse`'s
  docstring): an escalate response whose `escalate_to` is missing or not
  a party. Added as a warning because no tracked scenario fails it (all
  six escalate responses name a party). Named `[W-23]` so it takes the
  warning channel (`[W-` prefix); the message cites V-NEW-16.

The public data portal fixture now also accepts `[W-22]`, with a
comment (pending the violation-declaration amendment's scenario edits).
New `tests/test_am104_validator_warnings.py` (10).

### Part 4 — status endpoint (`25a1ca5`)

`GET /obligations/{token_name}/status` gains `modal_operator` ("AF", or
"AG(pending→AF)" for a burden with `triggered_by` — the bounded response
property, AM-99a part 3), `status` (None, or "not triggered within
horizon" / "not resolved within horizon") and `horizon`
(`_KRIPKE_HORIZON`, 10). Additive; existing clients unaffected. New
`tests/test_am104_obligation_status_fields.py` (3).

### Part 5 — docs

- CONCEPTS_INDEX: the `response_kind` finding marked **RESOLVED**; new
  OPEN FINDINGS — the static builder places response-created burdens in
  w0 unlinked to the violation (wrong AF verdict for referral's
  `escalationNoticeBurden`); revocation supersedes a permit by name for
  every holder (high priority; touches T7); `to_role` Authorizations not
  covered by terminate. The `missedReviewResponse` oddity (escalates to
  the contact who missed the review) recorded there.
- DN_019: step 2.10b and work item 4 updated to AM-104 behaviour.

**Verification:** full suite (`pytest -c pytest.ini`) — 676 → 676 → 683
→ 693 → 696 passed, 1 xfailed. Phase 1 (temporary patch, reverted)
compared every scenario before and after: only the portal runs that
reach a violation move.

**Standard reference(s):** §6.3.8 and §7.8.6 (violation; the response
rule is an obligation on the responding object, NOTE 2); §6.6.4 and
§7.10 (Authorization, its revocation by the authority); §6.6.8 and
§7.10.1 (delegation, principal); §7.4 (party); Annex C (Kripke
semantics, informative), §C.2.

**Files changed:** `toolchain/el_engine.py` (`WorldState.responded`,
`with_responded()`, `enroll()`, `_apply_revocation()`,
`revoke_authorization()`, `_violator_chain()`,
`_terminate_authorizations()`, `fire_violation_responses()`);
`toolchain/el_runtime.py` (docstring); `toolchain/el_api.py`
(fire-violation-responses description; `ObligationStatusResponse`,
status endpoint); `toolchain/el_validator.py` (`[W-21]`–`[W-23]`;
header); `toolchain/el_domain.py` (docstring);
`tests/test_am104_violation_responses.py`,
`tests/test_am104_validator_warnings.py`,
`tests/test_am104_obligation_status_fields.py` (new);
`tests/test_public_data_portal_scenario.py` (warning allow-list);
`docs/CONCEPTS_INDEX.md`; `docs/design_notes/DN_019_…`; this file.

---

## AM-105 (2026-09-26) — burdens a ViolationResponse creates wait on the violation, in both Kripke builders (`toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-26), in four parts (commits `aab285c`, `63c878e`,
`045c02f` and this docs commit). Type: verifier semantics (Layer 4). **No
grammar, engine or descriptor change.** Resolves the CONCEPTS_INDEX
finding "Static builder: response-created burdens sit in w0, unlinked to
the violation" (2026-09-26, from AM-104). Corrects a wrong verdict:
`escalationNoticeBurden` (referral, gp_referral) was reported AF true
(compelled) by the static model although it exists only after
`referralResponseBurden` is violated.

**Design (decided 2026-09-26):** reuse the `triggered_by` mechanism. A
created burden starts WAITING and the violated burden's T2 edge activates
it, so its verdict is the bounded response property from activation, as
for any triggered burden (AM-99a).

### Part 1 — static builder (`aab285c`)

- **`KripkeModel.violation_activation`**: `{created_burden:
  (violated_burden, ...)}` from `_build_violation_activation_index()`.
  A separate index, not an `ObligationDescriptor` field, so descriptors
  and their three snapshot tests are unchanged. A burden is linked only
  if a ViolationResponse creates it, it has a descriptor, it has **no
  `triggered_by`** of its own, and it has **no other root** (no
  Commitment, no Authorization `auth_burden`, not in any object's or
  role's `holds`) — a burden with another root exists independently of
  the violation and keeps its ordinary initial state. Several responses
  creating one burden list every violated burden.
- **Initial world:** a linked burden starts WAITING.
- **T2:** the edge violating O also makes every linked burden waiting
  on O PENDING, activation step = that step (`_activate_on_violation()`),
  so its deadline counts from there.
- **Violated worlds stay terminal, except** when their T2 edge activated
  a created burden: that world is enqueued (below the horizon, like any
  other). Left terminal, the created burden could never discharge — a
  dead end makes AF false — so the model would report "never
  dischargeable", wrong the other way. Every other violated world stays
  terminal, including one reached after a created burden is activated:
  a later unrelated violation still ends the path, so the created
  burden's bounded response fails on that path (pinned by
  `test_static_other_violations_stay_terminal`).
- **`check_obligation()`** gives a linked burden the bounded response
  verdict (`AG(pending→AF)`), as for `triggered_by`.
- **Why one T2 edge, not a separate "fire" transition.** In the engine,
  `check_live_violations()` and `fire_violation_responses()` are separate
  system calls; the created burden does not exist between them, so no
  ordinary action can affect it. A separate fire edge would only add
  paths where the operator never calls `fire_violation_responses()`,
  making AF fail on a property of how the runtime is operated, not of
  the governance rules. Treating the response as taken is the weak-
  fairness assumption already accepted in AM-103 (an enabled
  institutional act is eventually taken). **One-tick approximation:** the
  engine's firing advances the tick by 1 and grants the burden at the
  firing tick, so the model's activation step can be up to that much
  earlier than the engine's `granted_at_tick`.
- **`test_am86_…::test_escalation_notice_burden_reachable_via_af_ef_and_bellman`**
  pinned the wrong verdict (AF true, EF true); updated in this part (so
  the part is green on its own) to the corrected verdict, with a comment.
  Its name is kept; its Bellman assertion (the burden is present in a
  recommended successor's `obligation_states`) still holds.

### Part 2 — hybrid parity (`63c878e`)

Before AM-105 a created burden not yet granted was absent from the
hybrid model (descriptors come only from live tokens), so a violation in
a future world never produced it — incomplete rather than wrong. Now,
when a burden it waits on is live, the builder seeds it from its spec
descriptor: WAITING, activated by hybrid T2 (same enqueue rule as
static); or PENDING at w0, activated at the runtime's tick, if that
burden is already violated (detected, response not yet fired — firing
treated as taken, as in T2). Once the response has fired, the created
burden is an ordinary live token: not seeded, not indexed.
`tests/test_kripke_witness_endpoint.py`'s referral witness now also
shows `escalationNoticeBurden: WAITING`; updated.

### Part 3 — tests (`045c02f`)

New `tests/test_am105_violation_activation.py` (10): the pinned verdict
for `escalationNoticeBurden` in both referral scenarios, static and
hybrid (the same: bounded response, "not triggered within horizon", EF
false, WAITING at w0); a granted created burden is not indexed in
hybrid; a short-deadline probe — T2 activates the created burden on the
violating edge and the world continues, bounded response true in both
builders; hybrid seeds PENDING when already violated; an unrelated
violation stays terminal (dead-end counterexample); the index links only
response-only, untriggered burdens and lists every violated burden for a
burden two responses create.

### Part 4 — docs

AM-104's static-builder finding marked **RESOLVED**; correction notes
(not rewrites) on AM-86's "Empirical verification" and on the
CONCEPTS_INDEX entry "`escalationNoticeBurden` has no ObligationDescriptor
… RESOLVED (2026-09-15)"; new OPEN FINDINGS: hybrid never violates
permit-gated burdens (high priority); a burden created by several
responses; a created burden that is also `triggered_by`.

### Results

| Model | Worlds | Edges | Verdict change |
|---|---|---|---|
| static referral | 272 → 264 | 604 → 584 | `escalationNoticeBurden`: AF true, EF true → bounded response false, "not triggered within horizon", EF false |
| static gp_referral | 61 → 57 | 105 → 97 | same |
| hybrid referral, gp_referral | unchanged | unchanged | `escalationNoticeBurden` now present, WAITING: same verdict as static |
| every other scenario, both builders | unchanged | unchanged | none |

**"Not triggered within horizon" here reflects horizon 10 against
`referralResponseBurden`'s 40-step deadline** ("5 working days"): the
violation that creates the escalation is out of reach, so nothing can
be said about the escalation within the horizon. It is not a claim that
the escalation is never needed or never discharged. In hybrid mode it is
also unreachable for another reason: `referralResponseBurden` is
permit-gated, and hybrid T2 never violates a gated burden (open finding).
The worlds removed from the static models are the branches the strict
escalation used to force at w0 (T3 suppressed until it was discharged).

**Verification:** full suite (`pytest -c pytest.ini`) — 696 → 696 → 696
→ 706 → 706 passed, 1 xfailed.

**Standard reference(s):** §6.3.8 and §7.8.6 NOTE 2 (violation; the
response rule is an obligation on the responding object); §7.8.7 (token
lifecycle: activation, deadlines); Annex C (Kripke semantics,
informative), §C.2.

**Files changed:** `toolchain/el_kripke.py` (`KripkeModel.violation_activation`,
`_build_violation_activation_index()`, `_activate_on_violation()`,
`check_obligation()`, `build_kripke_model()` initial world and T2,
`build_kripke_from_runtime()` seeding and T2);
`tests/test_am86_obligation_descriptor_roots.py` (pinned verdict
corrected); `tests/test_kripke_witness_endpoint.py`;
`tests/test_am105_violation_activation.py` (new); `docs/CONCEPTS_INDEX.md`;
this file.

---

## AM-106 (2026-09-26) — hybrid T2 applies to permit-gated burdens; the hybrid fallback descriptor uses the token's `for_action` and static deadline parsing (`toolchain/el_kripke.py`)

**Status:** IMPLEMENTED (2026-09-26), in four parts (commits `a8ad4a7`, `f1e1fb7`,
`4e6ba94` and this docs commit). Type: verifier semantics (Layer 4, hybrid
builder only). **No grammar, engine or static-builder change.** Resolves
the CONCEPTS_INDEX findings "Hybrid mode never violates a permit-gated
burden" (high priority, from AM-105) and the smaller fallback gap logged
in it.

### Part 1 — hybrid T2 as its own loop (`a8ad4a7`)

Hybrid T2 sat inside the T1 loop, after `if desc.for_action in
permit_requirement_index: continue`, so a burden whose discharging action
requires a permit was never VIOLATED in a hybrid model, and a
ViolationResponse on it could never fire there (AM-105's
`escalationNoticeBurden` waits on the gated `referralResponseBurden`).
T2 is now its own loop over every PENDING obligation, mirroring static T2
exactly: same deadline test counted from activation, same AM-105
activation and enqueue rule, no holder-status check (as static). The
permit gate stays on T1 only. The hybrid label stays `violate:<oid>`.

Before/after, every hybrid model the suite builds (132 models in 122
tests, recorded by a scratch pytest plugin): 60 move, all through the
same change — **"eventually violated" (`EF violated:<oid>`) false → true
for a gated burden** (referral's `aiExaminationBurden`, 3976 → 4768
worlds, and its variants, e.g. 2832 → 3552, 4104 → 5040; probe burdens
`noteBurden`, `examineBurden`, `gatedBurden`). **No AF, EF or bounded
response verdict moves** — including the five gated burdens listed in
the finding, all AF false before and after. gp_referral, erequesting,
and the terms-of-engagement runtimes do not move (deadlines beyond the
horizon, or nothing gated).

**Caveat on the main visible effect:** referral's `aiExaminationBurden`
has `deadline: "referral episode"` — no elapsed-time magnitude — so its
5 steps are `_parse_deadline_steps()`'s default, and the engine never
clock-violates it (`_has_deadline_magnitude()`). Its newly reachable
hybrid violation is therefore an instance of the verifier-wide
no-magnitude mismatch (see "Not done here" under Part 2), not a real
deadline. It now matches the static builder, which already violated it.
**Update (AM-108):** no longer — T2 skips a deadline without a
magnitude. `aiExaminationBurden` is now violated only by T2b, when the
rest of its opted-in episode has concluded, exactly as the engine does.

### Part 2 — the fallback descriptor (`f1e1fb7`)

A live burden with no spec descriptor (no Commitment, response or
Authorization root) gets a fallback descriptor. It now takes:

- **`for_action` from the live token** (was `None`, so neither T1's
  permit gate nor its embargo check could apply — AM-101 had worked
  around this for the strict guard only). ereferral's
  `aiExaminationBurden` becomes gated: T6 discharges it (`examine:… →
  conductAIExamination`, needing the agent's active
  `patientRecordAccessPermit`) instead of T1, and T6's embargo guard
  applies. Moves the two ereferral models: 315 → 316 worlds, 631 → 628
  edges; no verdict change.
- **the deadline parsed as `_build_obligation_descriptors()` parses it**
  (`_parse_deadline_steps()`), instead of `int(dl)` first. A bare number
  "10" gave 10 steps here but 5 in static. Moves nothing in the suite (no
  descriptor-less live token has a bare-number deadline); pinned by
  `test_fallback_deadline_parsed_as_static`.

**Not done here — bare numbers still violate, as in static.** Parsing "as
static" means the default of 5 steps for a deadline with no elapsed-time
magnitude, so the verifier still violates such a burden, while the
engine never does (`_has_deadline_magnitude()`, 2026-08-29 mitigation;
`[W-19]`'s message says the same). That mismatch is verifier-wide
(static, and hybrid for every burden with a spec descriptor), not
specific to the fallback; see CONCEPTS_INDEX "`deadline: "referral
episode"` has no valid tick-count" (underlying gap still OPEN). Fixing it
(no T2 without a magnitude, in both builders) would, for example, remove
`violate:clinicalHandoverBurden` and `violate:aiExaminationBurden` (both
"referral episode") from the referral models; a separate amendment.
**Update (AM-108):** done — T2 skips a deadline without a magnitude in
both builders, and T2b adds the engine's episode-conclusion violation;
see the AM-108 entry.

### Part 3 — tests (`4e6ba94`)

New `tests/test_am106_hybrid_gated_t2.py` (5; all fail on the pre-AM-106
code): a short-deadline probe where a gated burden is violated in hybrid
and its response-created burden activates on that edge (bounded response
true), hybrid matching static on the same probe; referral's
`aiExaminationBurden` violable in hybrid with AF/EF unchanged; the
fallback's `for_action` (ereferral: `examine` edge, no T1 `discharge`);
the fallback's deadline parsing.

### Part 4 — docs

CONCEPTS_INDEX: the permit-gated finding and its fallback gap marked
**RESOLVED**; a note on "Strict mode, model vs deployment".
`docs/KRIPKE_TRANSITION_RULES.md`: T2 row (AM-105 and AM-106) and the
last-updated note — AM-105 had not updated it.

### First case of the terminal rule under-reporting in practice

With `referralResponseBurden` now violable in hybrid, a runtime near its
deadline activates `escalationNoticeBurden` within the horizon: referral
or gp_referral with `referralInitiationBurden` discharged and the clock
advanced to tick 36 (15336 and 2916 worlds). The escalation is PENDING
in 1800 / 342 worlds, EF true (before AM-106: "not triggered within
horizon", EF false). Its **bounded response is false**, counterexample
`violate:referralResponseBurden` → `violate:clinicalHandoverBurden` →
dead end: the unrelated violation ends the path while the escalation is
pending. With violated worlds left non-terminal (throwaway check) it is
**true** in both scenarios (17982 / 2997 worlds). So this false comes
only from the terminal rule — the first place it under-reports in
practice. See CONCEPTS_INDEX "\"Violated worlds are terminal\" conflicts
with violation responses" (`7695d1f`). **The terminal-rule amendment
follows immediately.** (`clinicalHandoverBurden`'s deadline, "referral
episode", has no magnitude — the engine would never violate it; see the
bare-number note in Part 2.)

### Strict burdens: model vs engine

Neither builder's T2 excludes `discharge_mode: strict` burdens, while
the engine never clock-violates one (`check_live_violations()` skips
them, AM-103). In the model this rarely shows, because T3 (tick) is
suppressed while a strict burden is actionable, but a strict burden
whose holder is not ACTIVE can age and be violated in the model. See
CONCEPTS_INDEX "Strict mode, model vs deployment". Unchanged here.

**Verification:** full suite (`pytest -c pytest.ini`) — 706 → 706 → 706
→ 711 → 711 passed, 1 xfailed.

**Standard reference(s):** §6.4.3 (Burden), §6.4.6 (conditional action:
permit requirement), §7.8.7 (token lifecycle: deadlines); §6.3.8 and
§7.8.6 (violation and its response); Annex C (Kripke semantics,
informative), §C.2.

**Files changed:** `toolchain/el_kripke.py` (`build_kripke_from_runtime()`:
T2 loop, fallback descriptor); `tests/test_am106_hybrid_gated_t2.py`
(new); `docs/CONCEPTS_INDEX.md`; `docs/KRIPKE_TRANSITION_RULES.md`; this
file.

---

## AM-107 (2026-09-26) — horizon-honest AF, genuine counterexamples, deterministic ties (`toolchain/el_kripke.py`, `el_api.py`)

**Status:** IMPLEMENTED (2026-09-26), in five parts (commits `0f1bdd7`, `aa87e6a`,
`9b036cd`, `2fcdc3c` and this docs commit). Type: verifier semantics (Layer 4) and
API output. **No grammar, engine or transition-rule change.** Opens and
resolves the CONCEPTS_INDEX finding "AF reported true only because the
horizon stopped time"; resolves "Recommendation ties depend on hash
order".

**Reorder (decided 2026-09-26).** AM-107 was first scoped as "the
verifier does not violate a burden whose deadline has no elapsed-time
magnitude". Its Phase 1 found that removing those violations would
expose a pre-existing horizon bug (below) and report more eventual
burdens as compelled only because time stops at the horizon. So the
horizon fix comes first, as AM-107. The no-magnitude T2 skip, together
with a T2b mirroring the engine's episode-conclusion violation (DN_010
option b) and a validator warning `[W-24]`, becomes **AM-108**; the
terminal-violated-world rule (CONCEPTS_INDEX, `7695d1f`) becomes
**AM-109**.

### The bug

At the horizon step there is no tick (T3), but other edges — notably a
discharge — remain. An eventual obligation that is never violated within
the horizon therefore has, at the horizon, only the discharge left, and
AF(discharged) came out **true ("compelled") only because time stopped**.
Live on HEAD in both builders: erequesting_claiming's
`providerAClaimBurden` (static, hybrid) and `providerBClaimBurden`
(hybrid) — deadline "4 hours" = 20 steps, horizon 10. A one-burden probe
with deadline "1 week" (12 steps) is AF true in both builders. No strict
verdict depended on it.

### Part 1 — three-valued AF (`0f1bdd7`)

`KripkeModel._AF_bounded()` evaluates AF with the horizon explicit: a
world satisfying the obligation's `violated:` proposition fails (it can
never be discharged afterwards); a world at the horizon step that is
neither discharged nor violated is where the path was cut off, and counts
as a pass or a failure depending on the reading; such a world is not
expanded. `_AF3()` combines the two readings:

- **holds** — AF holds even with cut-off paths counted as failures;
- **fails** — AF fails even with them counted as passes (a violation, a
  dead end below the horizon, or a cycle): counterexample given;
- **not resolved within horizon** — otherwise: `satisfied` False,
  `status` = `NOT_RESOLVED_WITHIN_HORIZON`, no counterexample.

`check_obligation()`'s AF path and `check_response()` (per pending world;
any genuine failure fails the property, else any unresolved world leaves
it unresolved) both use it. Memos are shared across pending worlds. The
API keeps `compelled` = `satisfied` (false when not resolved), with the
AM-104 `status` field.

Before/after (every static model, API runtime, and the 137 hybrid models
the suite builds): **5 verdicts true → "not resolved within horizon"**,
all eventual — the three erequesting_claiming ones and two probe burdens
in `test_am102_embargo_parity.py` (`carryBurden` AF, `handleBurden`
bounded response). **17 already-false verdicts** (all in suite probes)
change from "fails with counterexample" to "not resolved": their only
counterexample was a path that ticked to the horizon. **No strict verdict
moves. World counts, edges, Bellman values and recommendations
unchanged** — nothing else reads AF (Bellman, `recommend_action()`, the
witness endpoint, the UI pages' "Compelled" badges, which are hardcoded
or fixed by `discharge_mode: strict`). No existing test failed.

### Part 2 — genuine counterexamples (`aa87e6a`)

`_find_AF_counterexample()` follows only successors from which AF fails
even with cut-off paths counted as passes, so the path always ends at a
genuine failure, never at a horizon cut-off. New terminal label
`✗ violated — obligation can no longer be discharged` alongside
`✗ dead-end` and `↺ cycle`. Across the scenarios all 30 failing verdicts
now end genuinely (13 violated, 10 dead end below the horizon, 7 cycle).
The five that used to end at the horizon: static referral and gp_referral
`referralResponseBurden`, `assessmentSchedulingBurden` — now a tick, an
unrelated violation, dead end at step 9 (genuine under today's rules, but
it rests on the terminal rule, AM-109, and on the no-magnitude default,
AM-108); hybrid referral `referralResponseBurden` — a
`revoke`/`reinstate` cycle on `patientDataAuthorization`.

### Part 3 — deterministic tie-breaking (`9b036cd`)

Successor sets were iterated in hash order wherever one of several equals
was picked, so results depended on `PYTHONHASHSEED`: the top
recommendation (among equal utilities), the Bellman policy walk, the API's
recommended action (among equal Q-values), `rank_worlds_by_utility()`,
and the shortest witness / `_path_to()` path among equal lengths. New
`World.sort_key()` (a total order over every field; `__repr__` shows only
step and obligation states) and `KripkeModel.ordered_successors()`
(label, then `sort_key()`); every such site iterates it. The API's
candidate sort is `(-q, label)`.

Changes, every one a tie at equal value: before, the hybrid suite models
differed between two seeds in 17 of 137, the static/API models in 3 of
20; after, in none, with identical verdicts. 22 suite-model and 5
static/API recommendations change to the label-first choice — e.g.
ereferral `discharge:examinationBurden` → `discharge:acknowledgementBurden`
(0.6864 both), erequesting_claiming A/B now always A, specialist_pool
now always A, static referral always `discharge:clinicalHandoverBurden`.
The API's `/recommended-action` for ereferral and erequesting_claiming
varied with the seed at HEAD (the UI could show a different
recommendation after an API restart); now fixed. Matters for audit
replay.

### Part 4 — tests (`2fcdc3c`)

New `tests/test_am107_horizon_honest_af.py` (17; 14 fail on the
pre-AM-107 code — the two "holds" cases are unchanged by design, and the
hybrid cycle case was hash-order dependent before): the three
erequesting_claiming verdicts; one probe per outcome in both builders
(strict holds; 1 hour fails with a `✗ violated` counterexample; 1 week
not resolved — AF true before); bounded response not resolved; genuine
counterexamples for the five referral-family cases; the status endpoint;
the same recommendations and witness across two processes with
`PYTHONHASHSEED` 0 and 1.

### Part 5 — docs

This entry; CONCEPTS_INDEX: the horizon finding opened and resolved, the
tie-order finding resolved, a new OPEN FINDING on horizon sizing; the
API `status` field comment and endpoint description (`el_api.py`).

**Verification:** full suite (`pytest -c pytest.ini`) — 711 → 711 → 711
→ 711 → 728 → 728 passed, 1 xfailed.

**Standard reference(s):** Annex C (Kripke semantics, informative), §C.2
(AF, obligation), §C.4 (utility, recommendation); §6.4.3 (Burden), §7.8.7
(deadlines).

**Files changed:** `toolchain/el_kripke.py` (`World.sort_key()`,
`KripkeModel.ordered_successors()`, `_AF_bounded()`, `_AF3()`,
`check_obligation()`, `check_response()`, `_find_AF_counterexample()`,
`_path_to()`, `_find_EF_witness()`, `rank_worlds_by_utility()`,
`recommend_action()`, the Bellman policy walk); `toolchain/el_api.py`
(recommended-action and execute-action candidate order; status field
description); `tests/test_am107_horizon_honest_af.py` (new);
`docs/CONCEPTS_INDEX.md`; this file.

---

## AM-108 (2026-09-26) — no-magnitude deadlines: T2 skip plus episode-conclusion violation (T2b); `[W-24]` (`toolchain/el_kripke.py`, `el_validator.py`)

**Status:** IMPLEMENTED (2026-09-26), in four parts (commits `498dcda`, `dfaa10b`,
`a5757ac` and this docs commit). Type: verifier semantics (Layer 4), validator
warning (advisory). **No grammar or engine change; descriptors
unchanged.** Resolves the verifier/engine "no-magnitude" mismatch
recorded in AM-106 (its caveat and "Not done here") and in CONCEPTS_INDEX
(the permit-gated entry's caveat; the verifier side of "`deadline:
"referral episode"` has no valid tick-count"). Scoped in AM-107's reorder.

**The mismatch.** A burden whose deadline has no elapsed-time magnitude —
prose ("referral episode", "end of session"), a bare number, or none —
gets `_parse_deadline_steps()`'s default of 5 in its descriptor, and both
builders' T2 violated it at 5 steps. The engine never clock-violates one
(`check_live_violations()` requires `_has_deadline_magnitude()`), but it
*can* violate an eventual one through DN_010 option (b): when every other
member of an opted-in satisfaction group (`terminating {
on_objective_achieved: true }`) is DISCHARGED or SUPERSEDED
(`all_discharged`), or one is (`any_discharged`). 18 of 35 burdens in the
tracked scenarios have no magnitude. AM-107's horizon-honest AF made
removing the fictional violations safe: a burden that can no longer be
violated is reported "not resolved within horizon", not compelled.

### Part 1 — T2 skip and T2b, both builders (`498dcda`)

One part: the skip alone would also drop the violations the engine can
produce by conclusion; T2b alone is meaningless while T2 still violates
the same burdens at 5 steps.

- **T2 skip.** `_build_enforceable_deadlines()` (top-level and
  role-scoped burdens with a magnitude) is kept on
  `KripkeModel.enforceable_deadlines` (`None` in a hand-built model =
  every deadline enforceable). T2 applies only to those. A live burden
  with no spec token has no deadline and is not enforceable, as in the
  engine. `render_summary()` prints `deadline=none` for the others.
- **T2b — episode conclusion.** For a PENDING, eventual obligation with
  no enforceable deadline: if an opted-in group has concluded around it
  (`_build_conclusion_index()`, `_episode_concluded()`, the world-state
  mirror of `el_engine._owning_group_concluded()`: the obligation itself
  excluded; a member absent from the world counts as unresolved), an
  edge to VIOLATED at the same step, labelled `violate:<O> (episode
  concluded)`. Strict burdens: never (the engine excludes them). Same
  AM-105 activation and terminal rule as T2. The engine's and the
  verifier's satisfaction-group builders (duplicated per AM-57) agree on
  every tracked scenario.
- T2b can reach four burdens: referral `clinicalHandoverBurden`,
  `aiExaminationBurden`; ereferral `examinationBurden`,
  `aiExaminationBurden`. In hybrid referral it produces 189 + 189 edges,
  in ereferral 42 + 42. In the static referral model the rest of the
  episode does not conclude within horizon 10, so there are none.
- Three existing tests updated in this part (so it is green on its own):
  `test_am107_…::test_counterexample_is_genuine`'s four static cases now
  pin "not resolved within horizon" (their counterexample was an
  unrelated no-magnitude burden violated at the default 5, then a dead
  end); `test_am99a_deadline_from_activation`'s second burden gets
  `deadline: "1 hour"` (it relied on the default 5); and
  `test_am86_…::test_escalation_notice_burden_descriptor_in_hybrid_mode`
  pins the flip below.

**Before/after** (every static model, API runtime, and 147 suite-built
hybrid models, recorded with a scratch pytest plugin; deterministic
since AM-107):

- "Eventually violated" true → false for every no-magnitude burden
  without a conclusion path; unchanged (via T2b) for the four with one.
- "Fails" → "not resolved within horizon" wherever the only
  counterexample rested on a fictional violation: static referral
  `referralResponseBurden`, `assessmentSchedulingBurden`,
  `reviewNonResponseAndDetermineNextStepsBurden`, the same in
  gp_referral, consent `reportingObligation`, the transfer probes, the
  FHIR mapper's `Id402`/`Id403`/`Id702`/`Id703`, and other probes.
- World counts shrink (hybrid referral 4768 → 3562, ereferral 316 → 268,
  gp_referral 994 → 796; static referral 264 → 176, consent 30 → 24,
  transfer_probe 384 → 192). Expected utilities rise where fictional
  violation branches disappear; in referral-family models the top
  action moves from `examine:aiExaminationBurden` to
  `examine:referralResponseBurden` (e.g. 0.7601 → 0.8095).
- No verdict becomes true merely because a violation disappeared and
  AM-107 would otherwise report "not resolved": the only false → true is
  the tick-36 escalation below, which holds honestly.

**`escalationNoticeBurden` flip — terminal rule plus T2b.** Granted
directly in the referral runtime (two tests), its AF goes true → false.
Counterexample: the other episode members are discharged at step 0, T2b
violates `aiExaminationBurden` ("episode concluded"), and that violated
world is terminal with the strict escalation still PENDING — a dead end.
The engine allows the sequence (others' discharging actions and
`check_live_violations()` are not blocked by the strict freeze). With
violated worlds non-terminal (throwaway check) AF holds again. So the
false is the terminal rule's, a conservative under-report; before
AM-108 `aiExaminationBurden` was only violated by T2's default 5 steps,
which the strict freeze never let elapse. **AM-109 (the terminal rule)
is next.**

**Tick-36 escalation case (AM-106).** The dead-end counterexample
(violate `referralResponseBurden` → violate `clinicalHandoverBurden` →
dead end) disappears: `clinicalHandoverBurden`'s violation was the
fictional default, and T2b cannot fire there (`referralResponseBurden`
is violated, not resolved). The escalation's bounded response is now
true in referral (8370 worlds) and gp_referral (1998).

### Part 2 — `[W-24]` (`dfaa10b`)

An eventual burden (top-level or role-scoped) whose deadline has no
elapsed-time magnitude and that is in no opted-in satisfaction group
together with another member: "Eventual burden 'X' has no enforceable
deadline ('…') and no episode-conclusion path: it is never violated, at
runtime or in the verifier. Give it a deadline with a time unit, or put
it in a satisfaction group whose community opts in with
on_objective_achieved. (§6.4.3, §7.8.7)". Uses the engine's helpers, as
`[W-18]`/`[W-19]` do. Strict burdens are `[W-19]`'s. Fires on 7: consent
`reportingObligation`; ereferral `acknowledgementBurden`; gp_referral
`clinicalHandoverBurden` (only in `ReferralFederation`'s group, which does
not opt in); the four eventual transfer-probe burdens. Existing tests:
the `[W-16b]` probes in `test_am89_warnings_channel.py` and a
`test_am90` probe get a `"1 hour"` deadline (neutral to what they test);
`test_am89`'s tracked-scenario test excludes `[W-24]` alongside
`[W-19]`/`[W-20]` (consent's `reportingObligation`, a known scenario gap).

### Part 3 — tests (`a5757ac`)

New `tests/test_am108_no_magnitude_deadlines.py` (19; 16 fail on the
pre-AM-108 code — the three that pass are the engine parity check and
the two scenarios where `[W-24]` must stay silent): prose and bare-number
deadlines never clock-violated, in both builders, with the descriptor
unchanged and `deadline=none` in the summary; a magnitude deadline still
violated; T2b fires only once the group has concluded, never on the
strict member, and matches the engine's `check_live_violations()` step
by step; referral's two "referral episode" burdens violated only by T2b
(hybrid) and not at all (static); gp_referral `clinicalHandoverBurden`
never violated; `[W-24]` per tracked scenario and its message; **the
consent scenario's recommended order and values pinned** (static model,
horizon 10, γ 0.9): `recommend_action(w0)` — seek consent immediate 0.86
/ expected future 0.93, report 0.44 / 0.72; Bellman Q (API formula) —
6.4975 / 2.15.

### Part 4 — docs

This entry; CONCEPTS_INDEX: the no-magnitude mismatch resolved (notes on
the "referral episode" entry and the permit-gated entry's caveat), the
escalation flip added to the terminal-rule finding; the AM-106 entry's
caveat and "Not done here" updated; `docs/KRIPKE_TRANSITION_RULES.md`:
T2 row, new T2b row, last-updated note.

### EDOC 2026 Q-values

The EDOC 2026 paper's consent figures (+0.980 for
`seekConsentObligation`, +0.920 for `reportingObligation`) cannot be
reproduced at HEAD, before or after AM-108 — neither as Bellman Q-values
(6.4975 / 2.15) nor as `recommend_action` expected future utility (0.8593
/ 0.72 before, 0.93 / 0.72 after, horizon 10), nor at horizons 3–15 — and
the values appear nowhere in the repository's history (`git log -S` over
all branches). **The recommended order they illustrate (seek consent
first) holds before and after AM-108.** AM-108 changes only
`seekConsentObligation`'s expected future utility (0.8593 → 0.93, now
the same at every horizon); the Bellman Q-values are unchanged. The
figures now have a reproducible source: the consent test in Part 3.

**Verification:** full suite (`pytest -c pytest.ini`) — 728 → 728 → 728
→ 747 → 747 passed, 1 xfailed.

**Standard reference(s):** §6.4.3 (Burden), §7.8.7 (token lifecycle:
deadlines), §6.2 and §7.7 (community objective, satisfaction), §7.6
(community lifecycle: termination); Annex C (Kripke semantics,
informative), §C.2, §C.4.

**Files changed:** `toolchain/el_kripke.py`
(`KripkeModel.enforceable_deadlines`, `render_summary()`,
`_build_enforceable_deadlines()`, `_build_conclusion_index()`,
`_episode_concluded()`, T2/T2b in both builders, builder docstring);
`toolchain/el_validator.py` (`[W-24]`, header);
`tests/test_am108_no_magnitude_deadlines.py` (new);
`tests/test_am107_horizon_honest_af.py`,
`tests/test_am86_obligation_descriptor_roots.py`,
`tests/test_am99a_deadline_from_activation.py`,
`tests/test_am89_warnings_channel.py`,
`tests/test_am90_multi_parent_warnings.py`; `docs/CONCEPTS_INDEX.md`;
`docs/KRIPKE_TRANSITION_RULES.md`; this file.
