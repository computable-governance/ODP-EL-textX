# Coordination field of application — design note (v3)

**Status:** working design note, reflecting implementation state as of
commits 894afdb (P1-P6), a87720c (AM-27 log), 2913d48 (validator fixes),
b52be43 (validator amendments log), a9c8449 (CLAUDE.md public),
ebefde7 (el_reasoner.py AM-18 fix + GP-referral scenario, initial build),
1802c70 (P6b SUPERSEDED suppression limited to any_discharged groups),
4b25855 (GP-referral Commitment fix + verify_gp_referral.py). The
GP-referral scenario is now built and verified — see §13.1 (Milestones)
for results.

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

### 5.1 SUPERSEDED — plain-language definition and worked example

**SUPERSEDED, in one sentence:** an obligation becomes moot because a
sibling obligation in the same collective-responsibility group already
discharged it — not a failure, just no-longer-needed.

**Worked example.** Three role-fillers (Role A, Role B, Role C) share one
collective obligation via an `any_discharged` `TokenGroup` — any one of
them discharging satisfies the group's purpose. All three start PENDING.
Role A discharges first. At that moment, P6b looks at the other members
of the same group: Role B and Role C are both still PENDING, so both
transition to SUPERSEDED. The group's purpose (at least one member
discharged) is satisfied; B and C's individual burdens are not violations
— they simply never needed to be acted on, because A already covered the
collective responsibility.

**What this means in practice for B and C:** their burden disappears from
having any further bearing on the objective. It is not scored as a
partial success or a partial failure — `utility_for_objective()` (§12.2)
excludes SUPERSEDED members from scoring entirely, and `all_discharged`
counts SUPERSEDED the same as DISCHARGED for satisfaction purposes (§6).
SUPERSEDED is a *resolution*, not an outcome on its own terms.

**Open edge case (unresolved, not yet decided):** the example above
assumes B and C are still PENDING (or WAITING) at the moment A discharges.
P6b only acts on siblings that are PENDING or WAITING when it runs — it
does not retroactively revisit a sibling that independently became
VIOLATED (deadline elapsed) or EXPIRED (context removed) *before* A
discharged. So a group could end up with one member DISCHARGED, one
member independently VIOLATED, and only the remaining member SUPERSEDED.
`any_discharged` is still satisfied in that case (one member did
discharge), but whether the already-VIOLATED sibling's record should be
retroactively reinterpreted, left as-is, or flagged some other way is not
addressed anywhere in the design note or the implementation as currently
specified. Worth a decision if/when a scenario actually produces this
ordering — not yet exercised by either the consent or GP-referral
scenarios.



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

### 6.1 Provenance and scope of `TokenGroup` relative to `Objective` (revised 2026-06-17)

**Status: design clarification, supersedes the original AM-29 framing
below in spirit — kept here as a record of how the thinking developed,
see the revised position at the end of this subsection.**

It is worth being precise about three distinct historical layers that
get easily conflated, because the standard, the 2011 collective-obligation
paper, and the EDOC26 toolchain each contribute something different, in
a specific order:

**Layer 1 — the standard's own `Objective` concept.** ISO/IEC 15414:2015
defines `objective (of an <X>)` deliberately broadly and entity-agnostically:
"practical advantage or intended effect, expressed as preferences about
future states" (applicable to a Party, an AI agent, or a community alike).
For communities specifically, §7.7 and the contract clauses say the
objective is *stated* in the contract, which *governs* structure/behaviour/
policies and *constrains* member behaviour in service of it — but the
standard does not specify any formal satisfaction relation between the
objective and individual deontic tokens. There is no `TokenGroup`-equivalent
concept anywhere in the standard's metamodel (see Annex A Figure A.2:
`DeonticToken`/`Burden`/`Embargo`/`Permit` are all owned by individual
`ActiveEO`s; nothing groups them). The link from objective to token is
simply not addressed at the standard level.

**Layer 2 — the EDOC26 paper's pre-existing, general-purpose link.** Before
`TokenGroup` existed in this toolchain at all, the paper had *already*
solved "how do individual deontic tokens relate to community-level
outcomes" — via AF/EF over individually-owned obligations (§C.2) and the
priority-weighted utility function (§C.3), demonstrated on
`seekConsentObligation` and `reportingObligation` as two entirely separate,
individually-held tokens, with no grouping construct needed anywhere. This
*is* the general-purpose mechanism connecting individual deontic constraints
to community-level judgment that the standard's broad `Objective` concept
calls for — it predates and does not depend on `TokenGroup`.

**Layer 3 — `TokenGroup`, from Linington & Milosevic (2011).** This is a
narrower, separate problem: "if an obligation is on a community of equal
members, who acts, and why not leave it to another?" — i.e. collective
obligation among role-fillers, not the general objective-to-token link.
`TokenGroup` + `any_discharged` + SUPERSEDED (P3/P6) is this toolchain's
answer to that 2011 problem, and it is a good answer to it — but it is an
answer to a different, narrower question than Layer 2 already solved.

**Where AM-27 introduced an unintended coupling.** When `Objective.satisfaction`
was specified (AM-27) as `operator(TokenGroup)` — i.e. *every* satisfaction
condition routes through the Layer 3 mechanism — this implicitly made the
narrow collective-obligation construct carry the weight of the standard's
general `Objective` concept, even though Layer 2's individual-obligation
AF/EF/utility machinery already provided that general link, and predates
`TokenGroup`'s introduction. The original framing of this subsection
(below the line, kept for record) treated this as a usability/boilerplate
problem solvable by adding a `discharged(<token>)` shorthand alongside the
group operators. On reflection that undersells the issue: the concern is
not merely that singleton groups are verbose, but that promoting
`TokenGroup` to the *sole* sanctioned mechanism risks implying the standard's
`Objective` concept is intrinsically collective-obligation-shaped, which it
is not — the standard never says this, and the paper's own pre-`TokenGroup`
machinery shows it isn't necessary.

**Revised position:** `Objective.satisfaction` should be understood as
*primarily* expressed through the individual-obligation machinery the
paper already has (AF/EF reachability and utility scoring over the
obligations a community's contract constrains) — this is the general,
standard-aligned link. `TokenGroup`/`any_discharged`/SUPERSEDED should be
treated as an optional, named *refinement*, reached for specifically when
an objective's satisfaction genuinely depends on a collective-responsibility
relationship among several equally-capable role-fillers — not as a
mandatory wrapper that every objective, collective or not, must be
expressed through. Singleton `TokenGroup` usage (per the original AM-29
text below) is one *legitimate* way to wire a single obligation to an
objective under the current grammar, but it should not be read as the only
correct or intended way, and a future grammar revision should make the
non-collective case expressible without implying a collective relationship
that isn't actually present in the domain. This is a positioning/emphasis
question for documentation and future grammar work, not a correctness bug
in what is already implemented and verified (§13.1).

---

**Original framing (2026-06-16), kept for record:**

As currently specified, `TokenGroup` is the *only* mechanism linking
`Objective.satisfaction` to the token layer — `all_discharged`/
`any_discharged` both take a `TokenGroup` reference, and there is no
grammar form for "the objective is satisfied when this one specific
token discharges" that doesn't route through a TokenGroup wrapper. In
practice this means an objective backed by a single, individually-owned
obligation — the common case, not the exception; see e.g.
`referralInitiationBurden` in the GP-referral scenario, which has no
collective-responsibility semantics at all — still requires declaring a
`token_group` block containing exactly one `member:` line purely to
satisfy the grammar, not because anything in the domain is actually
collective.

A singleton `TokenGroup` (one member, `any_discharged` or
`all_discharged` — equivalent when there is only one member) currently
serves as objective-to-token linkage by borrowing the syntax built for
collective obligation. This works, and is not a bug, but — per the
revised position above — should not be read as evidence that the
standard's `Objective` concept is itself collective in nature; it's an
artefact of `TokenGroup` currently being the only available wiring,
not a reflection of what `Objective.satisfaction` is supposed to mean
in general.

A possible future grammar form, *not currently planned as a required
change*, would extend `satisfaction:` to also accept a direct
single-token reference (e.g. `satisfaction: discharged(referralInitiationBurden)`)
for the non-collective case, leaving `all_discharged`/`any_discharged`
over an explicit `TokenGroup` reserved for cases that are genuinely
collective. Whether this is worth implementing, versus simply documenting
clearly that singleton groups are a legitimate non-collective idiom under
the current grammar, is an open question — see §13.2 item 9.



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
Fixed 2026-06-15/16 (commit ebefde7): same AM-18 stale-class-name bug as
`el_kripke.py`/`el_validator.py` — the third file affected by the same
historical renaming gap. Seven stale pre-AM-18 class names corrected
across the file's functions:

- `DelegationDecl` → `Delegation` (`delegation_graph`,
  `ultimate_accountability` ×2)
- `CommitmentDecl` → `Commitment` (`ultimate_accountability`)
- `ObjectDecl` → `EnterpriseObject` (`can_perform`)
- `CommunityDecl` → `Community` (`can_perform`, `policy_conflicts`)
- `ActionDecl` → `Action` (`can_perform`)

Two further structural fixes were needed, reflecting object-processor
dissolutions (P2, P3) that had changed the shape of parsed objects since
these functions were last correct:

- `can_perform`: `actor_obj.body.holds_tokens` (pre-P2 path) →
  `actor_obj.holds_tokens` (flat `DeonticToken` list after P2 dissolved
  the `body` wrapper).
- `can_perform`: `role.behaviour_items`/`ActionDecl` check (pre-P3 path)
  → `role.actions` (typed list after P3).

Prior to this fix, all `_collect()` calls returned empty lists, so the
file was a silent no-op at runtime — every query against a real parsed
model returned trivially empty results. Now genuinely operational;
verified end-to-end by the GP-referral scenario (§13.1), including for
the first time across a federation boundary, not just within a single
community. Four functions:

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

**`el_api.py`** — Agent-facing query API (new, 2026-06-17)
FastAPI application providing the first of three planned read-only
coordination-query endpoints (see §13.1c, `agent_query_api_spec.md`).
Did not exist prior to this session — the "FastAPI/uvicorn — REST bridge"
referenced elsewhere in this document and in CLAUDE.md's "Tools &
resources" was aspirational/planned, not actually built, until now.

- `GET /actors/{actor_name}/available-actions`: implemented. Reads Layer 3
  runtime state directly (no Kripke model) — synthesises an actor's
  current obligated/permitted actions from active burdens and unembargoed
  permits. 404 for an unenrolled actor name.
- `GET /communities/{community_name}/objective-reachable`: planned, not
  yet implemented.
- `GET /communities/{community_name}/objective-score`: planned, not yet
  implemented.

Initializes a single global `Runtime` from the GP-referral scenario via
explicit enrollment (not `build_from_federation()` — see §13.1c for why)
with explicit `role_name` parameters, since the scenario has no static
role-filling declaration (§13.2 item 12).

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

**Level 2 — Kripke + utility, a.k.a. "scoped utility"** (implemented and
verified 2026-06-17 against the GP-referral scenario):
A priority-weighted score per world, rather than a binary yes/no, computed
by the same formula either way: `Σ(score × priority weight) / Σ(priority
weight)`, summed over some set of obligations. The two functions differ
only in *which obligations get included in that sum* — nothing else
changes.
`utility(world)` ("global utility") sums over every obligation
`_build_obligation_descriptors()` tracked when the model was built — for
GP-referral, that's all four obligations across both communities, no
matter which community's question is actually being asked.
`utility_for_objective(community_name, world)` ("scoped utility") sums
over a deliberately smaller set: just the obligation IDs listed in
`community_name`'s own `satisfaction_conditions` entry — for
`SpecialistCommunity`, that's only `referralResponseBurden` and
`assessmentSchedulingBurden`, excluding the two obligations on the GP
side entirely. "Scoped" names this — which obligations are summed over —
not a different formula, weighting scheme, or per-obligation scoring
rule, all of which stay identical between the two functions. SUPERSEDED
members are excluded entirely from either sum, and WAITING members score
0.0 (neutral, distinct from PENDING's +0.3).
Implemented as a new method on `KripkeModel` in `el_kripke.py`; reads
`self.satisfaction_conditions` (populated by `_build_satisfaction_conditions()`
at build time, AM-27) directly for the member-ID list — no separate
`group_index` lookup needed, since `satisfaction_conditions` already stores
`(operator, [member_ids])` rather than `(operator, group_name)`.

**"Global" does not mean "federation-only."** Worth stating immediately,
since the word invites that assumption: `utility(world)` has no concept
of communities or federations at all — it just sums over whatever flat
set of obligations `_build_obligation_descriptors()` happened to track
for the model in front of it. That set could be two obligations from a
single-community spec with no federation involved whatsoever (the
consent scenario — `seekConsentObligation` + `reportingObligation`, the
source of the paper's worked `u=+0.60` example), or four obligations
spanning two communities in a federation (GP-referral). Federation makes
the global/scoped distinction more visible and more useful — since
federating is exactly what bundles multiple communities' obligations
into one model, creating the dilution risk scoped utility exists to
avoid — but federation is not what *causes* the distinction to exist.
The distinction exists the moment a model tracks more than one objective's
worth of obligations, federation or not.

**Verified values, GP-referral scenario, corrected 2026-06-17** (scenario
fix applied same day, see §13.1b — `specialistBurdenGroup` now uses
`all_discharged`, not `any_discharged`; both burdens genuinely required,
not interchangeable. Members: `referralResponseBurden` priority weight
0.75, discharge_mode eventual; `assessmentSchedulingBurden` priority
weight 0.5, discharge_mode eventual; model: 144 worlds — grew from 102
once P6b SUPERSEDED suppression no longer applies to this group, since
that mechanism is scoped to `any_discharged` groups only (commit
`1802c70`) and both burdens now expand independently):

- **Real world, step=9** — `referralResponseBurden` and
  `assessmentSchedulingBurden` both DISCHARGED (the canonical satisfied
  witness world for `all_discharged`, replacing the SUPERSEDED-based
  witness that existed under the old, incorrect `any_discharged` operator):
  `utility_for_objective('SpecialistCommunity', w)` = **+1.0000**
  (both members DISCHARGED, both score +1.0, weighted average +1.0)
- **Real world** — both `referralResponseBurden` and
  `assessmentSchedulingBurden` PENDING:
  `utility_for_objective('SpecialistCommunity', w)` = **+0.3000**
  (both members score +0.3; when every scored member shares the same
  per-state score, the weighted average collapses to that score
  regardless of relative weights) — unchanged from the pre-fix run; the
  scoring arithmetic doesn't depend on the group operator, only on which
  worlds exist
- **Synthetic world** (WAITING does not occur naturally in this scenario —
  neither specialist burden has a `triggered_by`) — `referralResponseBurden`
  VIOLATED, `assessmentSchedulingBurden` WAITING:
  `utility_for_objective('SpecialistCommunity', w)` = **−0.6000**
  versus global `utility(w)` = **−0.1333** for the same world — unchanged
  from the pre-fix run. This is the concrete illustration of the point
  above: the global figure is diluted toward neutral by
  `referralInitiationBurden` (PENDING, weight 1.0) and
  `clinicalHandoverBurden` (PENDING, weight 0.5) sitting alongside the two
  specialist obligations in the same model — nothing to do with
  federation per se, just two extra obligations being averaged in.
- **Synthetic edge case** — both specialist burdens SUPERSEDED (a state
  that can no longer arise naturally for this group under `all_discharged`,
  but the method's logic is exercised here regardless via a hand-built
  world, since the method itself doesn't know or care which operator a
  group uses):
  `utility_for_objective('SpecialistCommunity', w)` = **+1.0000**
  (the `any_superseded` branch correctly distinguishes "every trackable
  member resolved via sibling discharge — objective achieved" from "no
  member was trackable at all," which the original spec sketch's
  `any_member_seen` logic could not distinguish; caught and fixed during
  implementation, not present in the original `utility_for_objective_spec.md`)
- **Edge case** — unknown community name: **+0.0000** (defensive default)

Note: the originally-reported "Example 1" (a real world with
`assessmentSchedulingBurden`=DISCHARGED, `referralResponseBurden`=
SUPERSEDED) no longer exists in the corrected model — expected and
correct, since P6b's SUPERSEDED-suppression mechanism only fires for
`any_discharged` groups (commit `1802c70`), and this group is no longer
one. This is not a regression; it's confirmation the fix took effect.

All values manually re-verified against the priority-weighted formula
before being recorded here; see also `EDOC26_revision_notes.md` item 15/19
for the confirmed PENDING=+0.3 scoring convention this method follows.

**Note on per-state scores:** the EDOC26 paper's §4.4/Equation (1) text
states PENDING=0, but the actual implementation
(`el_kripke.py`, confirmed by Kripke output) uses PENDING=+0.3 — this is a
known paper/implementation discrepancy, already tracked in
`EDOC26_revision_notes.md` item 15, with the implementation judged correct
and the paper's stated table needing correction before submission.
`utility_for_objective()` uses the same +0.3 value for consistency,
confirmed in the verified values above.

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
- **Level 2** (scoped utility) is implemented and verified — see the
  GP-referral values recorded above (§12.2). Real worlds from the model
  show the scoped/global divergence directly (+1.0 on sibling discharge
  via SUPERSEDED exclusion; the −0.6 vs. −0.1333 split demonstrating
  dilution in the global figure).
- **Level 3** (Bellman) is best deferred until a scenario concretely
  motivates "which role-filler action sequence maximises utility toward
  the referral objective?"

Conclusion: Levels 1 and 2 are done and verified; Level 3 follows as a
subsequent session once a scenario motivates it.

## 13. Milestones

### 13.1c Agent-facing query API, first endpoint: `available-actions` (2026-06-17)

**Implemented:** `GET /actors/{actor_name}/available-actions` in the new
`toolchain/el_api.py`, the first of three planned endpoints from
`agent_query_api_spec.md`. Reads Layer 3 runtime state directly — no
Kripke model involved, since "what's available right now" is a
present-tense, deterministic question about current token holdings, not
a question about possible futures. Synthesises an actor's currently
available actions from their active burdens (tagged `"obligated"`) and
unembargoed permits (tagged `"permitted"`), returning a 404 with a clear
message for an actor not enrolled in the runtime.

Runtime initialisation required explicit enrollment rather than
`build_from_federation()` or `build_from_spec()`: `ReferralFederation`'s
members are `Community`-typed, not `Domain`-typed, so the federation
factory's actor-collection step (which only looks at `Domain` members)
produces nothing for this scenario. Enrollment also required an explicit
`role_name` parameter on `enroll()` for `GPClinician`
(`role_name="gpClinicianRole"`) and `SpecialistClinicianAgent`
(`role_name="specialistRole"`) — without it, `el_engine.py`'s
effect-targeting (step 7b) falls back to treating the literal string
`"specialistRole"` as a phantom actor name, since nothing in the scenario
declares who actually *fills* either role (no `fills_role`/equivalent
construct exists anywhere in the file — only `assignment_policy` and
`on_join`/`on_leave` effects, which describe requirements and
consequences of role-filling, not the act of filling itself). This is
related to, but distinct from, the already-tracked `fill_role`/`leave_role`
*dynamic* speech-act gap (§13.3): that gap is about changing role-fillers
*at runtime*; this is the more basic absence of any *static* role-filling
declaration at all.

**Verified, real output against the GP-referral runtime:**
`SpecialistClinicianAgent` — obligated to `acknowledgeReferral`, permitted
`access_patient_clinical_records`. `GPClinician` — obligated to
`initiateReferral` and `provideHandover`. `GPPracticeParty` — zero
available actions (correct: a principal holding no tokens directly,
distinct from the next case). A deliberately nonexistent name,
`"UnknownActor"` — not an entity from the scenario, a synthetic negative
test case used only to confirm the 404 path — correctly returns HTTP 404
rather than an empty list, which matters: an empty list and "this actor
doesn't exist" are different facts a caller needs to distinguish.

**Two more `for_action` mismatches found and fixed, surfacing only
because this was the first time the scenario was exercised through
Layer 3 rather than just Layer 4:** `referralInitiationBurden.for_action`
(`"initiate_specialist_referral"` → `"initiateReferral"`) and
`clinicalHandoverBurden.for_action` (`"provide_clinical_handover"` →
`"provideHandover"`) — same bug class as the two specialist-side fixes
in §13.1b, bringing the total to **four** corrected `for_action` linkage
bugs in this one scenario file. Re-verified after the fix: Q1–Q4 truth
values and world count (144) unchanged, all `utility_for_objective`
values unchanged — expected, since `for_action` linkage is a Layer 3
concern the Kripke layer's results never depended on.

**Two further gaps found during the full sweep, deliberately left
unfixed this session:** `escalationNoticeBurden` and
`patientRecordAccessPermit` both have a `for_action` value with *no*
corresponding action declared anywhere in the file at all — not a wrong
string, an absent one. Neither affects current results
(`escalationNoticeBurden` only activates on violation, not part of the
initial token grant; `patientRecordAccessPermit`'s missing action
doesn't affect whether the API surfaces it as a permitted action). Open
question, not yet resolved: is it legitimate for a token to exist purely
as state with no consuming action ever declared, or does every token
need a matching action body, making this a deeper instance of the same
authoring-gap class as the four already-fixed mismatches? See §13.2 for
tracking.


not by any toolchain failure: does it make sense for the specialist side
to satisfy its objective by *responding to* the referral without ever
*scheduling* the assessment (or vice versa)? No — these are two genuinely
necessary steps toward the objective, not interchangeable ways of
discharging one shared responsibility, unlike the three-equal-role-fillers
collective-obligation case in §5.1. The scenario had used `any_discharged`
for this pair, which is the wrong operator for this relationship.

Checking the actual scenario file surfaced a second, independent issue:
neither `referralResponseBurden` nor `assessmentSchedulingBurden` could
actually be discharged via their associated actions at Layer 3 at all.
`referralResponseBurden.for_action` was `"acknowledge_and_respond_to_referral"`
but the action is named `acknowledgeReferral`; `assessmentSchedulingBurden.for_action`
was `"schedule_specialist_assessment"` but the action is named
`scheduleAssessment`. Neither string matched, so the engine's step-3b
`for_action` discharge path would never fire for either burden — a
defect entirely independent of the operator question, found only because
the operator question prompted a closer read of the action declarations.
(A claimed precondition — "Referral must be acknowledged" on
`scheduleAssessment` — also turned out to be an unenforced prose string,
not a token-state check; not fixed in this pass, noted for future
attention.)

Three fixes applied: both `for_action` strings corrected to match their
actual action names; `specialistBurdenGroup`'s satisfaction operator
changed from `any_discharged` to `all_discharged`. Re-verified in full
(commit-pending; not yet committed to git as of this writing):

- World count: 102 → 144. Removing P6b SUPERSEDED suppression from this
  group (P6b only fires for `any_discharged` groups, commit `1802c70`)
  means both specialist burdens now expand independently in the
  branching tree, widening it.
- Q1–Q3 unchanged (none of these depend on `specialistBurdenGroup`'s
  operator specifically).
- Q4 (`objective_satisfied:SpecialistCommunity`): AF still NO, EF still
  YES — but EF now witnesses a strictly harder condition (*both* burdens
  discharging on some path, not just one), and a witness still exists.
  This is a meaningfully stronger result than before, not merely an
  unchanged one.
- `utility_for_objective` re-verified against the corrected model — see
  §12.2 for full updated values. The previous SUPERSEDED-driven witness
  example no longer exists (expected); a new canonical both-DISCHARGED
  witness world (step=9, score +1.0) replaces it as the satisfied-objective
  example.

This is recorded as a finding, not swept past: the scenario was
*mechanically verifiable* (Q1–Q4 ran, produced results, looked internally
consistent) while modelling clinically incorrect semantics and having two
non-functional action linkages, for some period of time, without either
being caught by parsing, validation, or the verification script — all of
which were checking that the *mechanism* worked, not that the *scenario
content* was correct. Worth keeping in mind for any future scenario
review: passing verification is not the same as being right.

### 13.1a Level 2 (`utility_for_objective`) implemented and verified (2026-06-17)

Implemented per the `utility_for_objective_spec.md` handoff, with two
corrections caught during implementation rather than blindly following
the spec sketch: (1) `satisfaction_conditions[community_name]` unpacks
directly to `(operator, [member_ids])` — no separate `group_index` lookup
needed, contrary to the spec's assumption; (2) the all-SUPERSEDED edge
case needed an explicit `any_superseded` flag to distinguish "every
trackable member resolved via sibling discharge" (→ +1.0) from "no member
was trackable at all" (→ 0.0), which the spec's `any_member_seen` logic
could not distinguish. Initially verified against five cases drawn from
the real GP-referral Kripke model as it existed before the §13.1b fix
(102 worlds); re-verified after §13.1b's correction (144 worlds) — see
§12.2 for the current, corrected verified values. All values manually
re-checked against the priority-weighted formula both times.

### 13.1 First end-to-end accountability chain resolution from a parsed spec, and GP-referral scenario verified (2026-06-15/16)

**Note (2026-06-17): the Q4/any_discharged details below describe the
scenario's state *as it existed at the time this milestone was first
written* — kept as an accurate historical record of that session, not
deleted. The `specialistBurdenGroup` operator was subsequently corrected
from `any_discharged` to `all_discharged`, and two `for_action` linkage
bugs were fixed — see §13.1b for the full account and §12.2 for the
current, corrected verified values. The world count (102, below) is also
historical; the corrected model has 144 worlds.**

Prior to the AM-18 fix in `el_reasoner.py` (commit ebefde7, see §9 for
the full list of seven stale class names and two structural fixes
involved), `ultimate_accountability()`, `can_perform()`, and
`policy_conflicts()` were silent no-ops — all `_collect()` calls returned
empty lists, so no chains were ever built from parsed `.el` files. The
GP-referral scenario is the first scenario where Layer 2 governance
reasoning is genuinely operational end-to-end, and the first full
build-and-verify pass of the scenario itself:

- `ultimate_accountability('referralResponseBurden')` correctly traces
  `GPPracticeParty → SpecialistClinicianAgent` — the cross-community
  delegation chain (`gpToSpecialistDelegation`), with `GPPracticeParty`
  confirmed as root accountable party per §7.10.1/NOTE 5.
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

Scenario built at `scenarios/gp_referral/gp_referral_scenario.el`
(commit ebefde7, initial build), verified via
`scenarios/gp_referral/verify_gp_referral.py` (commit 4b25855). First
run was 6/7 PASS — Q3 EF failed because two `TokenGroup` members
(`clinicalHandoverBurden`, `assessmentSchedulingBurden`) had no backing
`Commitment` and so had no Kripke world-state entry, making the
federation objective vacuously unsatisfiable rather than genuinely false
(see §13.2 item 7 for the full root cause). After adding the two missing
`Commitment` declarations (commit 4b25855), **7/7 PASS**:

- Q1: `AF(discharged:referralInitiationBurden)` → YES (strict)
- Q2: `AF(discharged:referralResponseBurden)` → NO (eventual,
  counterexample: tick→tick→violate); `EF` → YES (witness: direct
  discharge at step 0)
- Q3: `AF(objective_satisfied:ReferralFederation)` → NO (blocked by
  eventual `referralResponseBurden`); `EF` → YES (all four group members
  now tracked; satisfiable on one path)
- Q4: `AF(objective_satisfied:SpecialistCommunity)` → NO (both specialist
  burdens eventual; no guarantee either fires); `EF` → YES
  (`any_discharged` satisfied when `referralResponseBurden` discharges)

Kripke model: 102 worlds (grew from an initial 27 once the two
previously-untracked `TokenGroup` members were given backing
`Commitment`s — see §13.2 item 8). This is the first scenario to
exercise both AM-27 `SatisfactionCondition` operators (`all_discharged`,
`any_discharged`) together, and the first to confirm the EF≠AF finding
holds across a federation boundary via cross-community delegation
(`GPPracticeParty → SpecialistClinicianAgent`), not just within a
single community as in the consent scenario.

A side effect observed in the Q2 AF counterexample also serves as
corroborating evidence for an earlier fix made the same day (commit
`1802c70`, "P6b SUPERSEDED suppression limited to `any_discharged`
groups only"): in that path, `assessmentSchedulingBurden` discharges
first, causing sibling `referralResponseBurden` (both members of the
`any_discharged` group `specialistBurdenGroup`) to transition to
SUPERSEDED rather than being left dangling — the first time that fix
has been exercised by a real multi-burden `any_discharged` group in an
actual verification run, behaving as intended.

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
9. **Revised (2026-06-17, was "Proposed AM-29"): position `TokenGroup`
   as an optional collective-responsibility refinement, not the sole
   sanctioned link between `Objective` and tokens.** Originally raised
   2026-06-16 as a usability concern (singleton `TokenGroup` declarations
   as boilerplate); revised after tracing the provenance more carefully —
   see §6.1 for the full discussion. The standard's own `Objective`
   concept (broad, entity-agnostic, §7.7) does not specify any
   token-level satisfaction mechanism at all; the EDOC26 paper's
   individual-obligation AF/EF/utility machinery already provides a
   general-purpose link from tokens to community-level judgment,
   predating `TokenGroup`; `TokenGroup` itself answers a narrower,
   separate question from Linington & Milosevic (2011) — collective
   responsibility among role-fillers, not general objective-to-token
   linkage. AM-27's `satisfaction: operator(TokenGroup)` form is not
   wrong or blocking, but should not be read as implying every objective
   is intrinsically collective in nature. Whether a future grammar
   revision should add a non-collective `discharged(<token>)` form
   (the original AM-29 idea, kept as one option) or simply document
   singleton-`TokenGroup` as a legitimate non-collective idiom under the
   current grammar is still open — worth scheduling alongside the V-16
   validator decision (item 7), since both touch how `TokenGroup` usage
   should be interpreted/validated.
10. **Unresolved: SUPERSEDED vs. a sibling already VIOLATED/EXPIRED
    before group resolution.** Surfaced 2026-06-16 while drafting a
    plain-language SUPERSEDED example (§5.1). P6b only flips siblings
    that are PENDING or WAITING at the moment one member discharges — it
    does not retroactively revisit a sibling that already independently
    became VIOLATED or EXPIRED beforehand. `any_discharged` is still
    satisfied either way, but whether an already-VIOLATED sibling's
    record should be reinterpreted, left as-is, or flagged is undecided
    and not addressed in either the design note or the implementation.
    Not yet exercised by any existing scenario — worth a decision before
    (or if) one does.
11. **Unresolved: tokens with a `for_action` value but no corresponding
    action declared anywhere in the scenario.** Surfaced 2026-06-17
    during the full `for_action` sweep that found the two GP-side
    mismatches (§13.1c). `escalationNoticeBurden` and
    `patientRecordAccessPermit` both have this property — not a wrong
    `for_action` string (the bug class already found and fixed four
    times in this scenario), but a *missing* action body to match
    against at all. Neither currently affects results
    (`escalationNoticeBurden` only activates on violation, outside the
    initial token grant; the permit's missing action doesn't affect
    whether the API surfaces it). Open question: is a token legitimately
    allowed to exist as pure state with no consuming action ever
    declared, or should this be flagged the same way V-16 (item 7) would
    flag an unbacked `TokenGroup` member — i.e. is this a fifth instance
    of the authoring-gap class, just with a different symptom (absent
    rather than mismatched)? Deliberately left unfixed pending this
    decision.
12. **No static role-filling declaration mechanism exists in the
    grammar.** Surfaced 2026-06-17 while building the `available-actions`
    endpoint's runtime initialisation. The GP-referral scenario declares
    `assignment_policy` (requirements for who *may* fill a role) and
    `on_join`/`on_leave` effects (consequences of filling/leaving a
    role), but nothing that actually states *who fills* `specialistRole`
    or `gpClinicianRole` — no `fills_role` construct or equivalent
    exists anywhere in the grammar. This is distinct from the
    already-tracked `fill_role`/`leave_role` *speech act* gap (next
    item, carried forward from earlier sessions): that gap is about
    changing role-fillers dynamically at runtime; this is the more basic
    absence of any way to declare role-filling *statically* at all.
    Worked around for this session via an explicit `role_name` parameter
    on `enroll()` rather than reading it from the spec, since nothing in
    the spec states it. Worth a grammar amendment if more of the toolchain
    needs to resolve role-fillers from the spec going forward, rather
    than continuing to hand-wire it per scenario.

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
