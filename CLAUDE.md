# CLAUDE.md — ODP-EL-textX Repository Context

This file gives Claude Code persistent context for working on this repository.
Read it at the start of every session before touching any code or grammar file.

---

## 1. What This Repository Is

A Python DSL implementation of the **ODP Enterprise Language (ODP-EL)**,
standardised as ISO/IEC 15414:2015 (≡ ITU-T X.911).

The DSL is the specification layer for **computable governance of agentic AI
systems**: it lets governance rules, accountability chains, deontic obligations,
and delegation structures be written in a human-readable formal language and
then parsed, validated, reasoned over, and executed by a Python toolchain.

The canonical repository is:
  https://github.com/computable-governance/ODP-EL-textX
(a fork of the now-archived igordejanovic/ODP-EL-textX; that repo's README
explicitly points here as the continuation.)

---

## 2. The Four-Layer Architecture

Defined in the EDOC 2026 paper (§3.5). This is the canonical framing — use
these layer numbers and descriptions consistently in code comments and docs.

```
Layer 1 — FHIR R4 (domain-specific data layer)
          Clinical (or other domain) data.
          Governance semantics extracted by toolchain/fhir_mapper.py.
          Q: What is the domain data saying, and what governance obligations
             does it imply?

Layer 2 — DSL-EL specification and accountability reasoning
          grammar/v2/el_grammar.tx → parsed by textX → domain objects
          toolchain/el_validator.py (15 rules, ISO-clause traced;
            AM-18 class-name bug fixed 2026-06-14; Federation/Domain
            community-type coverage added 2026-06-14)
          toolchain/el_reasoner.py (ultimate_accountability, can_perform,
                                    policy_conflicts)
          Q: Is this governance structure consistent, and who is ultimately
             accountable?

Layer 3 — Runtime enforcement
          Thomas Sepanosian's pyodpel engine.
          https://github.com/thomas-sepanosian/pyodpel
          WorldState + stateless engine + append-only ledger.
          Q: Did each action comply with the governance rules at execution time?

Layer 4 — Kripke verification (Annex C of ISO/IEC 15414:2015)
          toolchain/el_kripke.py — pre-execution mode complete.
          CTL operators: AF (obligation), EF (permission), AG (invariant).
          Bellman planner for optimal action selection.
          AM-26/27 (2026-06-13): TokenGroup satisfaction conditions wired into
            _build_propositions(); objective_satisfied:<community> propositions
            emitted; coordination semantics P3–P6 implemented.
          Q: Across all possible futures, will obligation O inevitably
             be discharged?
```

**Important:** Layers 2, 3, and 4 are **domain-independent governance layers**.
Layer 1 is the domain-specific integration point. FHIR is the demonstration
case for clinical AI; the governance layers apply to any domain.

**Central formal finding (EDOC 2026):** EF ≠ AF — delegation creates permission
(EF: there exists a path on which the obligation discharges) but not obligation
(AF: on every possible path, the obligation discharges). The `discharge_mode:
strict` grammar construct restores AF at specification time, by suppressing the
tick transition whenever a strict obligation is actionable.

---

## 3. The Standard — ISO/IEC 15414:2015

Every grammar rule and validator check must be traceable to a standard clause.

| Section | Topic |
|---------|-------|
| §6.1    | System concepts — EnterpriseSpec |
| §6.2    | Community concepts — Community, Objective |
| §6.3    | Behaviour concepts — Role, Action, Step, Process |
| §6.4    | Deontic concepts — DeonticToken (burden/permit/embargo), ConditionalAction |
| §6.5    | Policy concepts — Policy |
| §6.6    | Accountability concepts — Commitment, Delegation, Authorization, Prescription, Declaration, Evaluation |
| §7.3    | Community structuring — CommunityInteraction |
| §7.4    | Enterprise objects — EnterpriseObject (party/agent/active_object/artefact_object/resource_object) |
| §7.5    | Common types — Domain (§7.5.1), Federation (§7.5.2) |
| §7.6    | Community lifecycle — Lifecycle |
| §7.7    | Objective rules — Objective, SubObjective |
| §7.8    | Behaviour rules — Role, Process, Step, DeonticToken lifecycle |
| §7.9    | Policy rules — Policy, Enforcement |
| §7.10   | Accountability rules — Delegation, Authorization, Commitment, etc. |
| §11     | Viewpoint correspondences — Correspondence |
| Annex B | Reference scenario — Kent library (B.2) — Thomas's regression baseline |
| Annex C | Kripke semantics (informative) — implemented in el_kripke.py |

**Deontic token types (§6.4.3–6.4.5):**
- `burden` — obligation; holder must perform the associated action
- `permit` — permission; holder is allowed to perform the associated action
- `embargo` — prohibition; holder must not perform the associated action

**Token states (§7.8.7):**
- `active` — token is in force
- `pending` — token is masked/suspended (e.g. while delegated)

---

## 4. Repository Structure (verified June 2026)

```
ODP-EL-textX/
│
├── grammar/
│   ├── v1/                     Igor Dejanovic original grammar (SoSyM 2025)
│   │   ├── odpel.tx            Core deontic perspective grammar
│   │   ├── odppolicy.tx        Change/policy perspective grammar
│   │   ├── odpel.pu / .png     PlantUML diagrams
│   │   ├── __init__.py
│   │   ├── Makefile
│   │   └── README.md
│   └── v2/                     Extended unified grammar (EDOC 2026)
│       ├── el_grammar.tx       ← PRIMARY GRAMMAR — single source of truth
│       └── README.md
│
├── toolchain/
│   ├── el_parser.py            textX metamodel construction and parsing
│   ├── el_validator.py         15-rule semantic validator (ISO-clause traced)
│   ├── el_reasoner.py          Accountability chain reasoner (Layer 2)
│   ├── el_kripke.py            Kripke verifier + Bellman planner (Layer 4)
│   ├── fhir_mapper.py          FHIR R4 → DSL-EL mapping, 22 rules (Layer 1)
│   ├── fhir_mapping_table.md   Mapping table documentation
│   ├── ai_diagnostic_bundle.json  FHIR bundle for consent scenario
│   └── README.md
│
├── scenarios/
│   ├── consent/
│   │   ├── consent_scenario.el   Clinical AI consent (v2 grammar)
│   │   └── consent.odpl          v1 grammar version
│   ├── ecommerce/
│   │   └── ecommerce_scenario.el (pre-existing syntax error at line 57)
│   ├── fhir/
│   │   └── generated_governance.el  Output of FHIR mapper pipeline
│   └── README.md
│
├── docs/
│   ├── DSL_DESIGN_NOTES.md
│   ├── DSL_TOOLCHAIN_REFERENCE.md
│   └── el_grammar_amendments.md
│
├── README.md
├── CHANGELOG.md
├── requirements.txt
├── setup.py / setup.cfg
├── runtests.sh / install-dev.sh / install-test.sh
├── PULL_REQUEST_TEMPLATE.md
└── LICENSE
```

**Grammar convention:** `.tx` is the textX file extension. Always refer to the
v2 grammar as `grammar/v2/el_grammar.tx`.

**Root scaffolding files** (`setup.py`, `setup.cfg`, `runtests.sh`, etc.) are
inherited from Igor Dejanovic's original fork and belong at root. Do not move
or remove them.

**v1 grammar** (`grammar/v1/`) covers approximately 60–70% of ISO/IEC 15414
concepts, using a partitioned two-file design (`odpel.tx` + `odppolicy.tx`).
It is stable — do not modify it. It is the grammar described in the SoSyM 2025
and EDOC 2024 papers.

**v2 grammar** (`grammar/v2/el_grammar.tx`) covers approximately 95% of
ISO/IEC 15414 concepts in a single unified file. It is the grammar described
in the EDOC 2026 paper and is the active development target.

---

## 5. Grammar Structure (grammar/v2/el_grammar.tx)

### 5.1 Top-level structure
```
EnterpriseSpec → elements*=SpecElement
SpecElement    → Domain | Federation | Community | EnterpriseObject
               | DeonticToken | TokenGroup | Policy
               | Commitment | Delegation | Authorization
               | Prescription | Declaration | Evaluation
               | ViolationResponse | Correspondence
```

Order in `SpecElement` is significant (PEG matching; more-specific before
more-general where keywords overlap).

### 5.2 Order-independent bodies
`RoleBodyItem`, `ActionBodyItem`, `StepBodyItem`, `FedBodyItem`,
`DomainBodyItem` all use unified alternation rules so body items may appear
in any order. This was a deliberate design choice to avoid arpeggio PEG bugs
with cross-reference lists.

### 5.3 Cross-reference bug workaround
A confirmed arpeggio/textX bug: a comma-separated `[Rule]*` list causes
subsequent sub-rule matches to fail (textX continues consuming tokens as
cross-reference candidates). **Fix already applied**: `Federation` uses
one `member: <name>` statement per community (`MemberRef` rule) rather than
a comma-separated list. Apply the same pattern for any new multi-reference list.

### 5.4 Key cross-references (typed, not plain ID)
```
Delegation.delegator      → [EnterpriseObject]
Delegation.delegate       → [EnterpriseObject]
Delegation.burden         → [DeonticToken]
Commitment.actor          → [EnterpriseObject]
Commitment.burden         → [DeonticToken]
Authorization.authority   → [EnterpriseObject]
Authorization.permit      → [DeonticToken]
DelegatedFrom.delegator   → [EnterpriseObject]
MemberRef.community       → [Community]   (Domain satisfies this via Python inheritance)
SubObjectiveRef.objective → [SubObjective]
SatisfactionCondition.group → [TokenGroup]  (AM-27)
```

Plain `ID` fields are a known design smell. Prefer scoped cross-references
where the referenced object is declared in the same specification.

### 5.5 Layer 4 grammar constructs (EDOC 2026 additions)
Three optional attributes on `DeonticToken` bridge the DSL to the Kripke
verifier:

- `discharge_mode: strict | eventual` — `strict` suppresses the T3 (tick)
  transition when the obligation is pending and its holder is active, forcing
  immediate action so AF holds by construction. `eventual` (default) preserves
  tick; EF may hold but AF may not.
- `priority: critical | high | normal | low` — maps to weights 1.0, 0.75, 0.5,
  0.25 in the Bellman planner's utility function (Annex C.3).

`Objective` carries an optional `SatisfactionCondition` (AM-27):
- `satisfaction: all_discharged(GroupName)` — objective satisfied when every
  member of `GroupName` is DISCHARGED or SUPERSEDED.
- `satisfaction: any_discharged(GroupName)` — objective satisfied when at least
  one member is DISCHARGED.
- The Kripke verifier emits `objective_satisfied:<community>` propositions by
  evaluating these conditions against world state.

### 5.6 Grammar amendments log
`docs/el_grammar_amendments.md` tracks all confirmed and tentative amendments:
- `AM-xx` — grammar change
- `V-NEW-xx` — new validator rule (traceable to ISO clause)
- `DOC-xx` — documentation note

Consult before proposing grammar changes. Do not create duplicate amendments.
Most-recent confirmed amendments: AM-18 (Decl suffix removal), AM-19
(JoinLeaveEffect kind capture), AM-21 (contract dissolution), AM-22 (EventDecl),
AM-23 (typed PolicyValue), AM-24 (InlineToken), AM-25 (Federation/Domain as
community types), AM-26 (TokenGroup arpeggio fix), AM-27 (SatisfactionCondition).

---

## 6. The textX Custom Classes Architecture

### 6.1 The problem solved
Thomas Sepanosian's pyodpel runtime used a two-step pipeline:

```
.odpel file → textX parser → generic AST → separate compilation step
           → typed Pydantic domain objects → Specification → engine
```

This created two parallel representations of the standard that had to be kept
in sync manually — the "hydration problem" identified by Igor Dejanovic.

### 6.2 The solution: grammar as schema
textX supports **custom classes**: Python classes registered against grammar
rules; textX instantiates them during parsing rather than creating generic
objects. This eliminates the separate compilation step:

```
.el file → textX parser (custom classes registered via classes= parameter)
        → typed domain objects instantiated directly
        → WorldState → engine
```

The grammar (`grammar/v2/el_grammar.tx`) is the single source of truth.
Domain objects derive from the grammar, not from UML diagrams independently.

### 6.3 Implementation pattern
```python
# In toolchain/el_parser.py
from el_domain import DOMAIN_CLASSES

mm = metamodel_from_file('grammar/v2/el_grammar.tx', classes=DOMAIN_CLASSES)
model = mm.model_from_file('scenarios/consent/consent_scenario.el')
# model.elements now contains typed domain objects, not generic textX objects
```

Class attribute names align exactly with grammar rule attribute names.
Object processors (post-parse hooks, P1–P10) handle post-parse work:
dissolving body wrappers, splitting unified item lists into typed sublists,
injecting enum defaults, unwrapping thin grammar artefacts.

### 6.4 Implementation roadmap — all steps complete as of 2026-06-06

| Step | Status | Task |
|------|--------|------|
| Prep | ✓ | Create CLAUDE.md |
| 1 | ✓ | Grammar audit: rule → class mapping table (STEP1_grammar_audit.md) |
| 2 | ✓ | Write `toolchain/el_domain.py`: 64+ typed domain classes |
| 3 | ✓ | Modify `el_parser.py`: register classes via `classes=`, AM-18 grammar renames, _ELNode fix |
| 4 | ✓ | Implement object processors P1–P10 in `el_parser.py` |
| 5 | ✓ | Adapt engine to run over grammar-derived domain classes (`el_engine.py`) |
| 6 | ✓ | Kripke hybrid mode: anchor initial Kripke world to current WorldState |
| 7 | ✓ | Federation extension: cross-community interactions, multi-party delegation |
| 8 | ✓ | Federation scenario, community_tag actor state, build_from_federation |

**Post-step-8 work (2026-06-13/14):**
- AM-26: TokenGroup arpeggio fix + TokenGroupMember rule
- AM-27: SatisfactionCondition on Objective; Kripke propositions extended
- Kripke P3–P6 coordination semantics implemented
- el_validator.py: AM-18 class-name bug fixed; V-05 (AM-21 contract) and V-09
  (P2 body dissolution) structural bugs fixed; V-01 extended to Federation;
  V-12 extended to include Domain in all_communities index

**Next task:** GP-referral scenario (see §9 and §13).

---

## 7. Thomas Sepanosian's Runtime Engine (Layer 3)

Repository: https://github.com/thomas-sepanosian/pyodpel (public, MIT licence)
Thesis: "Design and Evaluation of an ODP-EL Toolchain for Executable
Accountability", University of Twente, April 2026.

### 7.1 Architecture
- **Stateless engine** — `(WorldState, Action) → (WorldState, TransitionRecord)`
- **Immutable WorldState** — frozen Pydantic objects, copy-on-write
- **Append-only ledger** — accountability tracing over TransitionRecords
- **Specification abstraction** — clean boundary between static model and execution
- **Seven-step execution pipeline** — expiry → initiator → discharge key →
  preconditions → embargo sweep → permit check → effect application

### 7.2 What to retain
- WorldState, ledger design, Specification abstraction: **retain fully**
- Test suite (11 scenarios against Annex B.2): **retain as regression baseline**
- Execution semantic decisions (lifecycle, discharge, delegation): **retain fully**
- Domain model classes: **regrounded** — derived from grammar, not Thomas's
  independent UML translation

### 7.3 Known issues to be aware of
1. **Fail-open guard** — `eval()` against a facts dict; missing fact silently
   passes. Serious correctness gap for governance-critical scenarios.
2. **No persistence** — WorldState in memory only.
3. **Single-community scope** — no federation, no cross-community delegation.
4. **Thin speech act layer** — Authorization, Declaration not typed runtime
   constructs.

### 7.4 ODP-EL subset operationalized
Fully active: DeonticToken lifecycle, Burden/Permit/Embargo, ActionTemplate,
Policy/PolicyEnvelope, Rule (preconditions/effects), Violation materialisation,
two-party delegation.

Not implemented: Federation, naming contexts, cross-community interactions,
multi-party authorization chains, full speech act taxonomy, Calendar EO.

---

## 8. FHIR Integration (Layer 1)

`toolchain/fhir_mapper.py` implements 22 formal mapping rules from FHIR R4
resources to DSL-EL governance constructs. Domain-specific to clinical AI.

Key files:
- `toolchain/ai_diagnostic_bundle.json` — FHIR R4 bundle for the consent scenario
- `toolchain/fhir_mapping_table.md` — full 22-rule mapping table
- `scenarios/fhir/generated_governance.el` — output of the mapper pipeline

The consent scenario demonstrates that the delegation chain
GPPracticeParty → SpecialistAgent → AIDiagnosticAgent without
`discharge_mode: strict` satisfies EF but not AF for `seekConsentObligation`.

FHIR integration is domain-specific. The governance layers (2–4) must remain
domain-independent. Never let clinical or FHIR concepts leak into
`el_validator.py`, `el_reasoner.py`, or `el_kripke.py`.

---

## 9. Governance Scenarios

| Scenario | Path | Purpose | Status |
|----------|------|---------|--------|
| Clinical AI consent (v2) | `scenarios/consent/consent_scenario.el` | EDOC 2026 primary demonstration; Layer 4 validation | ✓ Complete |
| Clinical AI consent (v1) | `scenarios/consent/consent.odpl` | v1 grammar version of same scenario | ✓ Stable |
| E-commerce | `scenarios/ecommerce/ecommerce_scenario.el` | Secondary validation scenario | Pre-existing syntax error line 57 |
| FHIR-generated | `scenarios/fhir/generated_governance.el` | Output of FHIR mapper pipeline | ✓ Complete |
| Kent Library | Annex B.2 of X.911 | Thomas's regression baseline (in pyodpel test suite) | ✓ Stable |
| GP-referral | `scenarios/gp_referral/` (planned) | Multi-party delegation across primary/specialist care; federation scenario | **Not yet built** |

---

## 10. Key Invariants — Never Break These

1. **Grammar is the schema.** Domain objects must derive from
   `grammar/v2/el_grammar.tx`. If grammar and domain classes diverge,
   grammar wins.

2. **Every validator rule must cite an ISO clause.** Format:
   `# §X.Y: description`. Do not add rules without a standard reference.

3. **Every grammar amendment must be logged in `docs/el_grammar_amendments.md`**
   with type (AM/V-NEW/DOC), rationale, and confirmed/tentative status.

4. **The arpeggio cross-reference list bug is real.** Never introduce a
   comma-separated `[Rule]*` list in a body rule. Use the per-line declaration
   pattern (one `keyword: <ref>` per line, collected in a `*=` list).

5. **Thomas's test suite is the regression baseline.** Any engine change that
   breaks Annex B.2 scenario behaviour is a regression.

6. **Layer 4 pre-execution mode is complete.** The hybrid mode (anchoring
   initial Kripke world to current WorldState from ledger) is implemented.
   Do not conflate pre-execution and hybrid modes in comments or tests.

7. **Layers 2–4 must remain domain-independent.** Domain-specific logic
   belongs in Layer 1 adapters (`fhir_mapper.py` and equivalents). Never
   let FHIR or clinical concepts leak into `el_validator.py`,
   `el_reasoner.py`, or `el_kripke.py`.

8. **Do not modify `grammar/v1/`.** It is stable, published, and referenced
   by SoSyM 2025 and EDOC 2024 papers.

9. **Domain does not get V-01.** The Domain grammar rule has no
   `objective=Objective` field. Domain's `.objective` is always `None` at
   runtime (Python inheritance from Community does not imply grammar
   enforcement). Applying V-01 to Domain would produce a false error on
   every domain. See open item in §13.

---

## 11. What NOT to Do

- Do not invent grammar constructs without tracing them to a standard section.
- Do not use `eval()` for guard expression evaluation (fail-open — see §7.3).
- Do not create a separate domain model independent of the grammar.
- Do not introduce comma-separated cross-reference lists in body rules.
- Do not modify Thomas's test scenarios without documenting the deviation.
- Do not modify `grammar/v1/` — it is frozen.
- Do not let domain-specific concerns propagate into Layers 2–4 modules.
- Do not apply V-01 to Domain elements (grammar has no objective on Domain).

---

## 12. Collaborators

- **Zoran Milosevic** — project lead, ODP-EL domain expert,
  computable-governance organisation co-founder. Brisbane, Australia.
  Corresponding author on EDOC 2026 paper.

- **Igor Dejanovic** — textX creator, computable-governance organisation
  co-founder. Confirmed the textX custom classes architecture direction
  (June 3, 2026).

- **Thomas Sepanosian** — pyodpel runtime implementer, University of Twente
  MSc. Does not yet know about the computable-governance organisation.
  Plan: invite post-examination; pyodpel belongs here as the Layer 3 component.

- **Peter Linington** — co-author of Linington/Milosevic/Dejanovic/Tanaka
  SSM 2025 paper; foundational ODP-EL work acknowledged in EDOC 2026 paper.

---

## 13. Open Items (as of 2026-06-18)

These are known gaps or deferred decisions. Address them before EDOC 2026
submission or when the relevant scenario demands it.

### 13.1 GP-referral scenario — built and verified (2026-06-16)

**What:** Built and verified per coordination_design_note_v3.md §13.1.
Spans GPPracticeCommunity and SpecialistCommunity via Federation,
exercising cross-community Delegation (GPPracticeParty →
SpecialistClinicianAgent), TokenGroup with both `all_discharged` and
`any_discharged` satisfaction conditions, and Kripke EF/AF verification.
Kripke model: 144 worlds, 270 edges. 7/7 PASS on the four verification
questions (Q1-Q4), reached after fixing two scenario-authoring bugs
(missing Commitment declarations for two TokenGroup members;
any_discharged SUPERSEDED-suppression scoping — see design note §13.2
items 7-9 for what those bugs surfaced).

**Next action:** none outstanding for the scenario itself. See design
note §13.4 for the TokenGroup/V-16 follow-on item this build surfaced.

### 13.2 EDOC 2026 — 31-vs-30-worlds Kripke discrepancy
**What:** The paper states 31 Kripke worlds for the consent scenario under
`discharge_mode: eventual`; the verifier currently produces 30. The off-by-one
must be resolved and the paper figure reconciled before submission.
**Next action:** Trace world construction in `el_kripke.py`; identify the
missing world and decide whether it reflects a paper error or a verifier bug.

### 13.3 Domain objective — future grammar amendment
**What:** §7.5.1 states that a domain IS a community type and should have an
objective. The current Domain grammar rule has no `objective=Objective` field,
so V-01 cannot be applied to Domain without producing false errors. A future
amendment should add `objective=Objective` to Domain (making it mandatory as
in Community and Federation) and extend V-01 accordingly.
**Next action:** Open a new AM entry (AM-28 or next available) when the Domain
objective grammar change is ready to implement; update V-01 at the same time.

### 13.4 fill_role / leave_role speech acts — future work
**What:** ODP-EL includes `fill_role` and `leave_role` as speech acts that
govern when an enterprise object enters or exits a community role. These are
not yet modelled as first-class grammar constructs or runtime operations.
The current `JoinLeaveEffect` in ContractDecl is a grammar convenience with
no standard grounding (see AM-11 — agreed to remove). The standard-compliant
replacement requires explicit `ActionDecl` with `DeonticEffect` for role entry/exit.
**Next action:** Defer until Layer 3 engine integration work resumes; then
model as `Action` within a `Role` body with appropriate `DeonticEffect` entries.

### 13.5 Agent-facing REST query surface — complete (2026-06-19)

**What was built:** Four endpoints in `toolchain/el_api.py` (419 lines,
commit d0dcab6) forming the agent-facing query surface over the Kripke
model:

- `GET /actors/{actor_name}/available-actions` — what can this agent do
  right now given its current token state (Layer 2, EF reachability)
- `GET /communities/{community_name}/objective-reachable` — is the
  community objective still reachable from the current world (Layer 4,
  EF query)
- `GET /communities/{community_name}/objective-score` — priority-weighted
  utility of the current world (Layer 4, §C.3 utility function)
- `GET /communities/{community_name}/recommended-action` — Bellman-optimal
  next action with Q-value and ranked alternatives (Layer 4, §C.4 Bellman
  value iteration, single `bellman_values()` call, greedy argmax)

All four query endpoints share the same `_runtime` singleton and
`build_kripke_from_runtime` pattern with `_KRIPKE_HORIZON = 10`.

Two additional endpoints added (commit 7dcefcf):

- `POST /actors/{actor_name}/execute-action` — advance runtime state
  by executing an action; returns TransitionRecord fields plus updated
  world state, new recommended action, new objective score, and EF
  reachability. Uses `utility_for_objective` consistent with endpoint 3.
  Blocked outcome returns reason string (fail-safe precondition guard, §7.3).
- `POST /reset` — reloads `_build_gp_referral_runtime()` from scratch,
  resetting all token states to initial PENDING.

**Next action:** Coordination UI widget in computable-governance-ui
(port 8001, GP-referral scenario, role-selector + recommended-action
panel + execute button). See coordination_design_note_v3.md §13.3.
