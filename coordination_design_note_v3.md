# Coordination field of application — design note (v3)

**Status:** working design note, reflecting implementation state as of
commits 894afdb (P1-P6), a87720c (AM-27 log), 2913d48 (validator fixes),
b52be43 (validator amendments log), a9c8449 (CLAUDE.md public),
ebefde7 (el_reasoner.py AM-18 fix), 4b25855 (GP-referral scenario +
verification). The GP-referral scenario is now built and verified —
see §13.1 (Milestones) for results.

## 1. Framing: a second field of application

ISO/IEC 15414:2015 §6.1.2/§8.3 define *field of application* as the
properties the environment of a specification's use shall have for that
specification to be applicable — framed around reuse: "is this
specification for me?" (see `field_of_application_note.md` for the full
terminological discussion).

The same DSL-EL specification fragment (community/role structure, deontic
tokens, accountability chains, the four-layer toolchain) admits at least
two fields of application:

- **Governance** — environment: regulated deployments (e.g. clinical AI
  under consent/accountability requirements). Audience: governance
  officers, boards, auditors. Question: retrospective/structural — is
  the governance structure consistent, who is accountable, was each
  action compliant?
- **Coordination** — environment: multi-agent systems where hand-coded
  orchestration between agents becomes brittle as obligations accumulate
  and change. Audience: heads of AI/automation, enterprise architects.
  Question: prospective/operational — given an agent's current token
  state, can it act, and if not, what unblocks it and who is responsible?

The formal axis distinguishing the two is **AF vs. EF** over the same
Kripke model:

- **AF ("Assured")** — governance: "across all paths, will the objective
  be satisfied?" A design-time guarantee; `discharge_mode: strict` prunes
  the branching tree so the property holds by construction.
- **EF ("Feasible")** — coordination: "does there exist a path from here
  to a world where the objective is satisfied?" A run-time query, asked
  by an agent to navigate within the space governance has already pruned
  to be safe.

Same `el_kripke.py`, same Kripke model M = (W, R, V, w₀) — different
CTL formulas, different consumers, different temporal direction (design-time
vs. run-time).

The *choice of query* — AF or EF — is what determines the field of
application, not the specification itself. Governance asks AF because its
purpose is to certify a property holds unconditionally across all possible
futures (enabling enforcement and audit); coordination asks EF because its
purpose is to navigate toward an objective at runtime, where the existence
of at least one feasible path is sufficient for an agent to act. Both
queries operate over exactly the same Kripke model built from the same
DSL-EL specification.

## 2. The core idea: topology allocates the deontic web

A community is specified as a topology of community roles and the
relationships between them:

- **Principal-agent** (Party/Agent/ActiveEO, Annex A Fig. A.5) —
  Party carries legal/accountability weight (buck stops here); Agent
  is an ActiveEO (human or AI) acting on behalf of a principal.
  Determines where accountability lands when an agent acts.
- **Controlling-controlled** (domain structure) — determines who has
  authority to grant/revoke permits. The controlling-controlled
  relationship in an organisational domain is essentially an implicit
  authorisation speech act executed at domain establishment.

This topology *allocates the deontic web*: which permissions,
prohibitions, and obligations attach to which roles, and — critically —
how the consequence of one role's action propagates to another role's
deontic state (via `emit`/`triggered_by`, AM-22), because that
propagation follows the relationship-topology.

Enterprise objects fill roles and act according to their role's
current deontic state (permitted/obligated/embargoed), at their own
initiative. Many valid traces result from one topology — the trace
is *generated* by repeatedly applying "an action requires tokens that
another action's consequences create," not separately specified.

**Analogy:** a soccer team. Roles (positions) have permissions/obligations
("rules of the game"); which player fills which role can vary; the trace
of play (who passes to whom, in what order) is not specified — it emerges
from players acting on the current state of play in service of the team's
objective. Describing coordination as a sequence (A→B→C) is the wrong
description style even for the steady-state case — the same way
"player 1 passes to player 2 passes to player 3" is the wrong way to
describe how a soccer team plays, even when that is exactly what happened
in one match.

## 3. Why this suits agentic communities specifically

Other agents cannot access an agent's intent — only its observable,
token-relevant behaviour (discharged burdens, emitted events, exercised
permits). The deontic web is the observable coordination interface
through which agents coordinate without needing to model each other's
(possibly opaque, LLM-internal) reasoning.

`GPParty` doesn't need to know *why* `AISpecialistAgent` attempted an
action — only that the attempt emitted an event, which is the
behaviourally-observable fact that triggers `GPParty`'s burden. Intent
operates within the space the deontic web leaves open (which of several
permitted actions an agent chooses) but propagates to other agents only
via observable behaviour, never directly. This is well-matched to agentic
communities where agents' internal reasoning is often genuinely opaque
even to their designers.

## 4. Community lifecycle: Creation vs. Introduction

X.902 §9.18/§9.19 distinguish two kinds of community instantiation:

- **Introduction (§9.19)** — the community simply exists at the start of
  the specification; no in-model act creates it. This is how existing
  scenarios work (`build_from_federation()` enrolls actors statically from
  the parsed AST).
- **Creation (§9.18)** — instantiation achieved by an action of objects
  in the model. ODP-EL §7.6.1 ("establishing behaviour... may be
  implicit or explicit") directly supports this. For the GP-referral
  scenario, the GP's commitment speech act is a Creation-style
  kick-off: one act both instantiates the community and seeds the first
  burden, from outside the deontic web it then sets in motion.

ODP-EL §7.4 gives the corresponding membership-origin cases: "by design"
(Introduction), "at the time of creation" (Creation), "dynamic changes
during lifetime" (§7.6.3, `fill_role`/`leave_role` — flagged as future
work).

## 5. Token groups, clones, and collective obligations

§7.8.7 NOTE 6: a deontic token may be declared once at community
level; when a role is filled, the token is cloned to the filler.
For multiple simultaneous fillers, multiple clones derive from one
community-level original. `TokenGroup` = the active clone-set.

Three distinct clone-lifecycle endings (all distinct, not one generic
mechanism):

- **Voluntary role-leaving (NOTE 3)** — `leave_role` speech act, clone
  reverts to community. `JoinLeaveEffect` declarative structure exists in
  grammar but no runtime speech act yet — flagged future work.
- **Failure (NOTE 5)** — specifier-declared exception, consequence (e.g.
  reactivation) is stated per-delegation, not automatic.
- **SUPERSEDED (our proposal, standard-silent)** — a sibling clone
  discharged first; this clone's purpose is fulfilled. Implemented in
  `el_kripke.py` (P3/P6). SUPERSEDED obligations are excluded from
  `utility()` entirely (not scored — genuinely excluded from both
  numerator and denominator of the weighted average).

Collective obligation resolution (Linington & Milosevic 2011 — "if
an obligation is on a community of equal members, who acts?"): model as
one `TokenGroup` with one token per role-filler, `any_discharged`
semantics. Redundant capacity is built into the specification — "did
anyone" (observable) rather than "who must" (unresolvable from outside).
SUPERSEDED handles the siblings once one discharges.

## 6. Objective satisfaction

`Objective` gains a machine-checkable `satisfaction:` clause (AM-27):

```
odpel
token_group ReferralObjectiveTokens {
    member: seekConsentObligation
    member: aiAnalysisPermit
    member: reportReturnedObligation
}

community ReferralCommunity {
    objective: "Patient receives consented specialist assessment"
        satisfaction: all_discharged(ReferralObjectiveTokens)
    ...
}
```

Operators:

- `all_discharged(group)` — every member DISCHARGED or SUPERSEDED
- `any_discharged(group)` — at least one member DISCHARGED

This gives AF and EF a single named target proposition
`objective_satisfied:<community>` (emitted by `_build_propositions()`,
P5) — the community's objective *as a whole*, not individual obligations.

Epoch end:

- **Objective satisfied** — `epoch_end_condition` becomes true via T1
  transitions. Community fulfilled.
- **Abandoned** — community-level deadline elapsed while condition still
  false (T2-equivalent at the community level).

**Note (validated by GP-referral scenario, see §13.1):** a `TokenGroup`
member used in an `all_discharged`/`any_discharged` satisfaction
condition only enters the Kripke world-state if it *also* has a backing
`Commitment` — `_build_obligation_descriptors()` in `el_kripke.py` only
tracks burdens reachable via `Commitment.burden`. A `TokenGroup` member
without one is silently untracked, and the satisfaction condition can
become unsatisfiable without any obvious error. See §13.2, item 7 for
the proposed validator fix.

## 7. Runtime execution sequence

This is what actually drives coordination behaviour at runtime:

```
commitment (kick-off — Creation-style instantiation, §7.6.1)
    → el_engine processes speech act
    → ledger updated (append-only record, el_runtime.py)
    → w₀ established (initial world: triggered_by obligations start
      WAITING, others start PENDING, per P6)

        → agent attempts action
            → el_engine checks permits/embargoes (step 6)
                → if embargoed or missing permit: action blocked
                → if permitted:
                    → action executed
                    → events emitted (EmitsDecl, step 3, AM-22)
                    → DeonticEffect fan-out to role fillers (step 7b)
                    → triggered_by tokens activated (step 7c)
                    → ledger record appended

                        → other agents' deontic states change
                            → they attempt their actions
                                → ... (repeats)

    → epoch ends when:
        objective_satisfied:<community> becomes true
        (all_discharged or any_discharged over TokenGroup)
        OR community-level deadline elapsed (abandoned)
```

Key point: the engine *is* the coordination mechanism at runtime — not
a separate orchestrator. Each agent checks its own current token state and
acts when permitted/obligated. The deontic web's topology determines which
agent's action affects which other agents' states; the engine enforces it
action by action.

Layer 4 (Kripke/`el_kripke.py`) does not drive execution — it *reasons
about* the space of possible executions (all reachable worlds from the
current state), answering AF/EF queries. The distinction:

- **Layer 3** (`el_engine.py`): "can this specific action be performed right
  now, and what are its immediate consequences?" — deterministic, per-action
- **Layer 4** (`el_kripke.py`): "across all possible futures from here, will
  the objective be satisfied?" — modal, over the whole reachable world-set

The Layer 3 `triggered_by` mechanism (step 7c) and the Layer 4 T1 cascade
(P6) are the same mechanism at different levels: Layer 3 executes it
action-by-action at runtime; Layer 4 models it as world-transitions for
reasoning. They must stay consistent — any `triggered_by` semantics added
to the grammar must be reflected in both.

## 8. The ledger — field-of-application-agnostic Layer 3 infrastructure

`el_runtime.py`'s append-only ledger was designed as part of the
governance architecture — recording speech acts and action submissions
as the audit trail for Layer 3 compliance checking, and as the state anchor
for Layer 4 Kripke reasoning via `build_kripke_from_runtime()` (which reads
the ledger to establish the current w₀).

The ledger carries through to the coordination field of application
*unchanged*: it records what happened; which CTL query (AF/governance
or EF/coordination) is run against that record determines what the
recording *means* for the current purpose. No redesign was needed — the
ledger is stable Layer 3 infrastructure used transparently by both fields
of application.

The ledger is field-of-application-agnostic because it records speech acts
and their token-state consequences — facts that are the same regardless of
whether the purpose of querying them is "prove compliance" (governance)
or "navigate toward the objective" (coordination).

Note: Thomas Sepanosian's thesis (2026) also used an append-only ledger
concept, arrived at independently via a Pydantic-based architecture. The
convergence on the same data structure reflects the naturalness of
"immutable history of speech acts" as the right representation for deontic
token state changes — not a shared design.

## 9. Key component summary (as of 2026-06-16)

**`el_parser.py`** — Grammar loading + object processors (P1-P10)
Loads `el_grammar.tx` via textX; object processors (P1-P10) post-process
raw parsed objects into clean domain objects.

- P10 (AM-26, new): unwraps `TokenGroupMember` wrappers into
  `group.tokens`; clears `group.members`.

**`el_domain.py`** — Domain class definitions (~68 dataclasses)

- `TokenGroupMember` (new, AM-26): thin wrapper for `member: <token>`
  declarations; cleared by P10.
- `SatisfactionCondition` (new, AM-27): operator + group →
  `TokenGroup` ref.
- `Objective`: gains `satisfaction: Optional[SatisfactionCondition]`.

**`el_validator.py`** — Layer 2 static validation (V-01 through V-15)
15 semantic rules. Now genuinely operational after AM-18 class-name fixes
(all `_collect()` calls use correct post-AM-18 names). Key recent fixes:

- AM-18 fix: 8 stale `_collect()` class names corrected.
- V-05 fix: AM-21 contract dissolution — reads `assignment_policies`
  directly from community.
- V-09 fix: P2 body dissolution — reads `holds_tokens` directly from
  object.
- Federation/Domain coverage (AM-25): V-01 extended to Federation;
  `all_communities` extended to include Domain for V-12. Domain does
  NOT receive V-01 (grammar has no `objective` field on Domain — Python
  inheritance artifact only).
- **Open question (2026-06-16, surfaced by GP-referral scenario):** possible
  new rule (provisionally V-16) flagging `TokenGroup` members with no
  backing `Commitment` — see §13.2 item 7.

**`el_reasoner.py`** — Layer 2 accountability queries (governance)
Fixed 2026-06-15 (commit ebefde7): same AM-18 stale-class-name bug as
`el_kripke.py`/`el_validator.py` made all `_collect()` calls return empty
lists, so this file was a silent no-op at runtime — every query against
a real parsed model returned trivially empty results. Now genuinely
operational; verified end-to-end by the GP-referral scenario (§13.1).
Four functions:

- `ultimate_accountability(model, oid)`: walks delegation chain → root
  accountable party.
- `can_perform(model, actor, action)`: static permit/embargo check.
- `policy_conflicts(model)`: cross-community consistency.
- `delegation_graph(model)`: builds `{delegator_name: [(delegate_name,
  obligation_text, sub_delegation_allowed, revocable), ...]}` — maps "who
  has delegated what to whom" across the whole spec. Used by
  `ultimate_accountability()` to walk backward from current obligation
  holder to root principal. The structure of this graph *is* the topology
  of accountability relationships — in the GP-referral scenario,
  `GPPracticeParty` appears as a key (delegating `referralResponseBurden`
  to `SpecialistClinicianAgent` across the community boundary). Reusable
  by the coordination layer for "who is upstream of me in the
  accountability chain?" queries without needing to re-traverse the full
  spec.

**`el_engine.py`** — Layer 3 stateless governance engine
Evaluates individual action attempts against current WorldState.
Unchanged. Key steps:

- Step 3: `EmitsDecl` fires events from action (AM-22).
- Step 6: permit/embargo check — blocks if embargoed or missing permit.
- Step 7b: `DeonticEffect` fan-out to all actors in a role.
- Step 7c: `_find_spec_tokens_for_event` — activates `triggered_by`
  tokens on event emission. This is the Layer 3 runtime equivalent of
  P6's T1 cascade in Layer 4 — same mechanism, different layer.

**`el_runtime.py`** — Layer 3 stateful runtime + ledger
Wraps `el_engine.py` with state. Unchanged in logic.

- `Runtime.submit_action(...)`: runs engine step, appends ledger record.
- `Runtime.current_state()`: returns current WorldState.
- `build_from_federation(runtime, spec)`: auto-enrolls actors from Domain
  structure; auto-grants burden to terminal delegate via
  commitment→delegation chain walk. Closest existing equivalent to
  §7.6.1 establishing behaviour (Introduction-style).

**`el_kripke.py`** — Layer 4 Kripke verification
Most changed file (P1-P6, AM-18 fix). Key additions:

New obligation states:

- `SUPERSEDED`: sibling in same TokenGroup discharged first; purpose
  fulfilled, not a failure. Excluded from `utility()` entirely.
- `WAITING`: `triggered_by` event has not yet fired; not eligible for T1
  discharge or T2 violation. Starts WAITING if `triggered_by` is set,
  transitions to PENDING when trigger fires (P6a cascade).

New `ObligationDescriptor` fields:

- `triggered_by`: event name whose firing moves WAITING → PENDING.
- `fires_event`: event name emitted when this obligation discharges
  (bidirectional — the discharge event that cascades to others).

New helpers:

- `_build_group_index(model)`: `{group_name: [oid,...]}` from `TokenGroup`
  declarations. Used by T1/P6b for SUPERSEDED sibling lookup.
- `_build_satisfaction_conditions(model)`: `{community_name: (operator, [member_ids])}` from `Objective.satisfaction` clauses. Used by
  `_build_propositions()` to emit `objective_satisfied:<community>`.

New `KripkeModel` fields:

- `group_index`: populated by both builders.
- `satisfaction_conditions`: populated by both builders.

Extended `_build_propositions(world, satisfaction_conditions)`:

- Emits `superseded:<id>`, `waiting:<id>`, `any_waiting` (new).
- Emits `objective_satisfied:<community>` when satisfaction condition
  holds (P5).

Combined T1 pass (P6):

- P6a (cascade): discharge of A with `fires_event=E` → any obligation
  with `triggered_by=E` currently WAITING → PENDING.
- P6b (SUPERSEDED suppression): any PENDING/WAITING sibling in same
  TokenGroup → SUPERSEDED. P6b runs second and overrides P6a for
  same-group tiebreak cases.

**AM-18 bug fix (critical):** Five `_collect()` calls used pre-AM-18
class names (`DeonticTokenDecl`, `CommitmentDecl`, `DelegationDecl`).
Fixed to `DeonticToken`, `Commitment`, `Delegation`. Effect: `build_kripke_model(parsed_model)` now produces real multi-world models
from actual `.el` files for the first time. The EF≠AF finding from
EDOC26 is now reproducible from the parsed spec (30 worlds, AF=True for
consent obligation, AF=False/EF=True for reporting obligation).

**Tracking gap (surfaced by GP-referral scenario, see §13.1/§13.2 item 7):**
`_build_obligation_descriptors()` only tracks burdens reachable via
`Commitment.burden` — a `TokenGroup` member without a backing `Commitment`
is silently absent from the world-state, which can make a satisfaction
condition unsatisfiable with no direct diagnostic.

## 10. Boundary: transactional vs. dispositional norms

The deontic web specifies the *transactional* layer completely —
burdens, permits, embargoes; specific, discharge-able/violable, held by
specific roles. Given that an outcome-event occurs, the community's
reaction is fully governed.

*Dispositional/character norms* — e.g. "a conscientious agent would
notice and surface things outside its assigned task" — are NOT reducible
to a missing token. Whether an agent notices and chooses to emit an
outcome-event at all (e.g. an incidental finding outside its assigned
scope) depends on the agent's own reasoning/alignment, not on community
structure. The specification can incentivise (utility functions) but
cannot mandate this the way a burden mandates discharge.

This is an honest, stated limit — not a gap to engineer away.

## 12. Community objective vs. collective obligations — and the role of utility + Bellman

These are related but distinct concepts operating at different levels, and
the distinction matters for how Kripke + utility + Bellman link them.

### 12.1 The distinction

- **Community objective** (`Objective` on `CommunityBehaviour`, Annex A) —
  the community-as-a-whole's goal: "patient receives consented specialist
  assessment," "referral is completed." Captured in the toolchain as the
  `objective_satisfied:<community>` proposition (P5), which becomes true when
  the community's TokenGroup satisfaction condition (`all_discharged` /
  `any_discharged`) holds in a world. This is a specification-level
  declaration of what the community exists to achieve.
- **Collective obligation** (Linington & Milosevic 2011 — "who acts, why not
  leave it to another?") — an obligation placed on a group of role-fillers,
  where any one of them could discharge it. Captured as a `TokenGroup` with
  one token per filler and `any_discharged` semantics; SUPERSEDED handles
  siblings once one discharges (P3/P6). This is a deontic-level construct:
  *which* individual role-filler, among several equally-capable actors, actually
  discharges the burden.

The two are linked — discharging collective obligations is typically *how*
the community objective gets reached — but they are not the same: the
community objective is *what the community is for*; collective obligations
are *how individual role-fillers contribute to it*.

### 12.2 Three levels of reasoning over the same Kripke model

The distinction motivates three progressively richer queries, all over the
same `KripkeModel` built from the same DSL-EL specification:

**Level 1 — Kripke + AF/EF** (already implemented, now verified across a
federation boundary — see §13.1):
Binary existence query. "Will/can the community objective be reached?"
`check_obligation()` (AF/"Assured") and `check_permission()` (EF/"Feasible")
check whether `objective_satisfied:<community>` inevitably or feasibly holds.
Sufficient for yes/no compliance/feasibility questions.

**Level 2 — Kripke + utility** (partially implemented, small extension needed):
Graded quality of a world. `utility(world)` currently scores all active
obligations globally (priority-weighted). For community-objective reasoning,
this needs scoping: `utility_for_objective(community_name, world)` =
priority-weighted score over just the members of that community's
satisfaction TokenGroup. This differentiates within the space of "objective
satisfied" worlds — a world where the high-priority burden is DISCHARGED and
the low-priority one is SUPERSEDED scores differently from the reverse. The
`satisfaction_conditions` dict (P5) + `ObligationDescriptor` priority weights
already provide everything needed; this is a small contained extension
(~10-15 lines, new method on `KripkeModel`).

**Level 3 — Kripke + Bellman value iteration** (future work):
Optimal path to the objective. Rather than just "is there a feasible path?"
(EF), Bellman asks "what is the *optimal sequence* of role-filler actions —
the one maximising expected utility across all steps, not just at the
endpoint?" This is Annex C §C.4's explicit motivation: "judging a course of
action on the basis of the desirability of its outcome overlooks the fact
that there may be intermediate states on the path to the desired outcome
which are themselves of very low desirability." Bellman value iteration over
the world-graph (discount factor γ, value function V(w) initialised from
`utility(world)`, backward induction over edges) addresses this directly.
The world-graph already exists; this is a ~50-100 line addition to
`el_kripke.py`. Currently `EDOC26_revision_notes.md` item 25, LOW priority.

### 12.3 Implementation order

- **Level 1** is implemented and now verified by the GP-referral scenario
  (EF: "is there a path where the referral objective is satisfied?", AF:
  "is it guaranteed given `discharge_mode: strict`?") — see §13.1.
- **Level 2** (scoped utility) is small enough to add during further scenario
  work, now that real priority-weighted TokenGroup members exist in the
  GP-referral spec.
- **Level 3** (Bellman) is best deferred until a scenario concretely
  motivates "which role-filler action sequence maximises utility toward
  the referral objective?"

Conclusion: Level 1 is done and verified; Level 2 follows naturally
during further scenario work; Level 3 follows as a subsequent session
once a scenario motivates it.

## 13. Milestones

### 13.1 First end-to-end accountability chain resolution from a parsed spec, and GP-referral scenario verified (2026-06-15/16)

Prior to the AM-18 fix in `el_reasoner.py` (commit ebefde7),
`ultimate_accountability()`, `can_perform()`, and `policy_conflicts()` were
silent no-ops — all `_collect()` calls returned empty lists, so no chains
were ever built from parsed `.el` files. The GP-referral scenario is the
first scenario where Layer 2 governance reasoning is genuinely operational
end-to-end, and the first full build-and-verify pass of the scenario
itself:

- `ultimate_accountability('referralResponseBurden')` correctly traces
  `GPPracticeParty → SpecialistClinicianAgent` — the cross-community
  delegation chain, with `GPPracticeParty` confirmed as root accountable
  party per §7.10.1/NOTE 5.
- `ultimate_accountability('referralInitiationBurden')` correctly traces
  to `GPPracticeParty` directly (no delegation).
- `can_perform('SpecialistClinicianAgent', 'acknowledgeReferral')`
  correctly blocks (permit not pre-declared in object body — granted at
  runtime via Authorization, as designed).
- Consent scenario regression passes: two-hop chain
  (GPPracticeParty → SpecialistAgent → AIDiagnosticAgent) resolves
  correctly.
- `policy_conflicts()` returns empty (no conflicts) for both scenarios.
- `delegation_graph()` confirms `GPPracticeParty` as delegator with
  `SpecialistClinicianAgent` as delegate for `referralResponseBurden` —
  matching the designed topology, and validating the §9 description of
  `delegation_graph()`.

Scenario built at `scenarios/gp_referral/gp_referral_scenario.el`,
verified via `scenarios/gp_referral/verify_gp_referral.py`. All four
Layer 4 verification questions (Q1–Q4) PASS against expected values:

- Q1: `AF(discharged:referralInitiationBurden)` → YES (strict)
- Q2: `AF(discharged:referralResponseBurden)` → NO; `EF` → YES (eventual)
- Q3: `objective_satisfied:ReferralFederation` (`all_discharged`) → EF only
- Q4: `objective_satisfied:SpecialistCommunity` (`any_discharged`) → EF only

Kripke model: 102 worlds (grew from an initial 27 once two
previously-untracked `TokenGroup` members were given backing
`Commitment`s — see §13.2 item 7). This is the first scenario to
exercise both AM-27 `SatisfactionCondition` operators (`all_discharged`,
`any_discharged`) together, and the first to confirm the EF≠AF finding
holds across a federation boundary via cross-community delegation
(`GPPracticeParty → SpecialistClinicianAgent`), not just within a
single community as in the consent scenario.

Full details: `SESSION_SUMMARY_2026_06_16.md`.

### 13.2 Open items arising from the GP-referral session (2026-06-16)

7. **Possible new validator rule (provisionally V-16) for unbacked
   `TokenGroup` members.** The GP-referral verification run surfaced a real
   authoring gap: a `TokenGroup` member used in an `all_discharged`/
   `any_discharged` satisfaction condition has no Kripke world-state entry
   — and the satisfaction condition is silently unsatisfiable — unless
   that token also has a backing `Commitment`
   (`_build_obligation_descriptors()` in `el_kripke.py` only tracks burdens
   reachable via `Commitment.burden`). This was caught only at Layer 4
   verification time, as an unexpected `EF` result, and required manual
   root-cause tracing to diagnose. Open question: should `el_validator.py`
   gain a rule that flags `TokenGroup` members lacking a backing
   `Commitment` at Layer 2 (static validation) instead, where the error
   message can name the token directly? Needs a decision on hard error vs.
   warning — a `TokenGroup` member might legitimately acquire its token via
   `Delegation` or `Authorization` rather than `Commitment` in some
   modelling patterns; needs checking against the grammar's full set of
   token-creating constructs before deciding rule severity.
8. **World-count scaling data point.** The growth from 27 to 102 worlds
   when going from 2 to 4 tracked obligations is a concrete data point on
   how state-space size scales with concurrent obligation count — relevant
   context for the EDOC26 31-vs-30-worlds discrepancy (§13.3 item below)
   and for any future scalability remarks in the safety paper.

### 13.3 Other open items (carried forward, unchanged this session)

- **EDOC26 31-vs-30-worlds discrepancy** — paper claims 31 worlds;
  fixed `build_kripke_model()` on parsed spec produces 30. AF/EF
  finding itself is solid. World count needs reconciling before
  submission.
- **Domain objective grammar amendment** — §7.5.1 says domain is a
  community type and should have an objective. Current Domain grammar
  rule has no `objective` field. Future AM entry needed (AM-28 or next
  available); until then V-01 correctly excludes Domain.
- **fill_role / leave_role speech acts** — declarative `JoinLeaveEffect`
  exists in grammar but no runtime speech act. Future work; not blocking
  further scenario development.
- **CommunityObject** — Annex A concept, absent from grammar. Relevant
  to federation-membership-of-communities and "community-level original"
  token ownership (NOTE 6). Not needed for current scope.
- **Agent-facing query surface** — three REST endpoints needed for
  agents to query their own token state, permitted/obligated actions,
  and community objective feasibility. Small-to-medium task (~1-2 days).
  See `el_api.py` for existing REST bridge pattern. **Now unblocked** —
  the GP-referral scenario is built and verified, so this can proceed.
