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
