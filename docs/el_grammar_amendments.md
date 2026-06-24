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
