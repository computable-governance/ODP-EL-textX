# Concept Index

Purpose: before treating any concept as new, missing, or unresolved, check
this document first — at the start of any design/implementation/demo
session, and again at the moment of asserting "there is no X" or "this
hasn't been decided." Maintained with the same rigor as
el_grammar_amendments.md. Not in Project Knowledge — fetch fresh each
session (raw.githubusercontent.com or via Claude Code), per the file
freshness protocol.

Companion: scenarios/README.md (catalog of scenario files and their
maturity status).

## Directory

| Concept | Status |
|---|---|
| Community | Implemented |
| Domain (community type) | Settled 2026-07-06: retired for organizational structure; reserved for cross-cutting characterizing relationships |
| Federation (community type) | Implemented |
| CommunityObject | Implemented (AM-26) |
| Objective rules | Implemented |
| Policy / policy envelope | Grammar exists — deliberately excluded from reference scenarios |
| NormativePolicy scope | Implemented (AM-28), restriction under review — proposed widening to any Community (2026-07-06) |
| Establishing behaviour | Mechanism decided 2026-07-06 (established_by: [EventDecl]) — amendment not yet implemented |
| Creation-style / episodic community | Settled 2026-07-06: created federation, not plain community |
| Implicit creation / standing communities | Implemented |
| Party vs agent for clinicians | Inconsistent across scenarios |
| Authorization ≠ delegation | Implemented + documented |
| Permit split by grant mechanism | Implemented (AM-31b) |
| Accountability chain composition | Insight captured, no formal treatment |
| Compelled vs detectable (AF/EF) | Implemented + API-exposed |
| Kripke/runtime impact of community lifecycle | Not implemented — deferred, most consequential and least-tested planned work |
| Process / Step (behaviour structuring) | Grammar exists, zero usage — deliberate architectural alternative, not an oversight |
| Community/Domain/Federation grammar sharing | Not implemented — consciously deferred structural refactor |
| Scenario maturity language | Proposed |

---

## Community

**Definition:** A configuration of enterprise objects formed to meet an
objective, subject to an agreement (contract) governing collective
behaviour, with actions assigned via roles.

**Standard:** §7.3

**Toolchain status:** Implemented — core construct since the v2 grammar.

**Demonstrated in:** all reference/probe scenarios.

**Decisions:** none pending.

---

## Domain (community type)

**Definition:** Per §7.5.1, a domain IS a community — one whose defining
structure is a single controlling object and a set of controlled objects,
related by a characterizing relationship. Controlling/controlled are
community roles, subject to assignment policy (§7.6.2, including late/
dynamic assignment) and the full community machinery (lifecycle,
objective, contract) by inheritance from community.

**Standard:** §7.5.1; Part 2 §10.3; Annex B.1.5.9

**Toolchain status:** Implemented as a reduced grammar rule
(`DomainBodyItem` = `DomainControllingObj | DomainControlledObj | PolicyRef
| NormativePolicyRef` only) — no roles, no assignment policy, no
lifecycle, no objective. Substantially narrower than the standard's
domain-as-community.

**Demonstrated in:** `federation_consent_scenario.el` (probe, 2026-06-06).

**Decisions:**
- 2026-06-04 — Domain IS a community; `DomainDecl` not resolvable as
  `[Community]` was a modelling error, corrected by AM-25.
- 2026-07-06 — Annex B.1.5.9 evidence: the standard's own e-commerce
  example uses communities for organizational structure and reserves
  domains for cross-cutting characterizing relationships (security,
  naming, audit, policy-setting) — not for org units.
- 2026-07-06 — Confirmed `DomainBodyItem` also lacks `lifecycle` entirely
  (same gap independently found in Federation — see that entry and the
  new "Community/Domain/Federation grammar sharing" entry for root cause).
  Decision: add `(lifecycle=Lifecycle)?` to `DomainBodyItem`, for
  consistency with the same fix applied to Federation, and because a
  future cross-cutting domain (e.g. a data-governance authority spanning
  both practices) plausibly needs establishment/termination triggers too
  (e.g. established when a cross-practice data-sharing agreement is
  signed, terminated when it lapses).

**Settled (2026-07-06):** Retiring bare `domain` for organizational
structure. `GPPracticeDomain`/`SpecialistPracticeDomain` are organizational
units (practices) — per Annex B.1.5.9's own test, a domain is not an
organizational unit but a single controlling relationship that CUTS
ACROSS community boundaries regardless of org structure (e.g. the
standard's securityDomain spans objects from two different communities,
purchasingCommunity and shippingCommunity). The practices will be modelled
as communities, represented by CommunityObjects for federation
participation (AM-26). `domain` is reserved for genuine future
cross-cutting cases — not used in the unified referral scenario.

---

## Federation (community type)

**Definition:** Per §7.5.2, a community of pre-existing communities
cooperating toward a shared objective. **Correction (2026-07-06):** the
"pre-existing" constraint applies to the *member* communities, not to the
federation itself — the federation community can be created in response
to an event, time-limited, and dissolved on objective achievement.
Confirmed directly by the standard's own text: "Federation establishment
is an example of [community-creating-community] behaviour" (Annex B,
library Case 5).

**Standard:** §7.5.2; Annex B library Case 5

**Toolchain status:** Implemented (AM-25) — `contract federation`,
objective, member, invariant, conflict_resolution. **Gap found
2026-07-06:** `FedBodyItem` (`FedSharedObjective | EventDecl | Role |
MemberRef | PolicyRef | NormativePolicyRef | Invariant |
WithdrawalBehaviour | ConflictResolution`) has NO lifecycle support at
all — no `Establishing`, no `Terminating`. Its only lifecycle-adjacent
item, `WithdrawalBehaviour`, is a free-text description string, weaker
even than Community's already-partial `Terminating` (which at least has a
structured `on_objective_achieved` trigger).

**Demonstrated in:** `federation_consent_scenario.el` (probe, 2026-06-06),
`ereferral_model.el`, `gp_referral_scenario.el` (all as standing
federations, not event-created — consistent with the grammar currently
having no way to create one).

**Decisions:**
- 2026-07-06 — Corrected an earlier misreading in this project ("federation
  is not the episodic construct") — the standard's own worked example
  says otherwise.
- 2026-07-06 — Modelling test for community-vs-federation membership
  (derived from comparing all three Annex B creation examples): a
  federation's members are pre-existing COMMUNITIES with their own
  persisting internal governance to be preserved (library trading
  community — each library keeps its own roles/policies while
  cooperating); a plain created community's members are individual
  OBJECTS with no internal structure to preserve (justInTimeCommunity,
  open-registry community — both cross-organizational, both plain
  communities, not federations). Org-boundary alone is NOT the
  distinguishing test — two of the three examples are cross-org and use
  plain community.
- 2026-07-06 (Zoran) — **Settled: the referral episode is a created
  federation**, not a plain community. GPPracticeCommunity and
  SpecialistPracticeCommunity are themselves real communities with
  persisting roles (gpClinicianRole, specialistRole) and assignment
  policies that exist independently of any given referral — matching the
  library pattern, not the supplier/registry pattern.
- 2026-07-06 (Zoran) — "Federation as a special kind of Community should
  inherit all properties of the community, including its lifecycle."
  Decision: add `(lifecycle=Lifecycle)?` to `FedBodyItem`, reusing the
  existing `Lifecycle` rule rather than inventing a parallel mechanism.
  Applied the same fix to Domain for consistency (see that entry).

**Open:** None — mechanism settled. Awaiting implementation (see
Establishing behaviour entry for the trigger mechanism, and the pragmatic
amendment now being drafted).

---

## CommunityObject

**Definition:** A community represented as an object, able to fulfil a
role in another community — the mechanism for community hierarchy and
for a community to participate in a federation.

**Standard:** §6.2.2, §7.4

**Toolchain status:** Implemented (AM-26).

**Demonstrated in:** `ereferral_model.el` (`GPPracticeObj`,
`SpecialistPracticeObj`).

**Decisions:**
- 2026-07-06 — §7.7 consistency rule identified: when a CommunityObject
  fulfils a role in another community, the represented community's own
  objective must be consistent with the sub-objective assigned to that
  role. Candidate validator rule, not yet implemented.
- **Missed in 2026-07-05 analysis** — the incident that motivated this
  index. The fact was already in project memory; not cross-checked
  before reasoning about community/federation structure.

---

## Objective rules

**Definition:** Every community has exactly one objective, expressible in
a contract; may be decomposed into sub-objectives assigned to roles or
processes, each defining the *state* in which the sub-objective is met.

**Standard:** §7.7

**Toolchain status:** Implemented — V-01 (exactly one objective);
`objective_satisfied:{community}` as a Kripke proposition.

**Demonstrated in:** all reference/probe scenarios; `/communities/{name}/
objective-reachable` and `objective-score` endpoints.

**Decisions:**
- 2026-07-06 — §7.7 defines sub-objectives as termination *states* — i.e.,
  sets of worlds. The existing `objective_satisfied` proposition is
  therefore §7.7-grounded, not only Annex-C-grounded — a stronger and
  previously unstated basis for the Kripke layer's objective semantics.

---

## Policy / policy envelope

**Definition:** A formal mechanism (policy value, policy envelope) for
constraining and evolving community behaviour flexibly while keeping the
objective achievable.

**Standard:** §6.5, §7.7, §7.9

**Toolchain status:** Grammar support exists (`SettingBehaviour`, AM-27).
**Deliberately excluded from board/clinical reference scenarios.**

**Demonstrated in:** no reference scenario.

**Decisions:**
- 2026-07-06 (Zoran) — Policy/envelope is a powerful evolution and
  flexibility mechanism, but judged likely to confuse board audiences and
  inexperienced architects. Deliberately kept out of reference scenarios.
  This is a scoping decision, not an oversight — recorded here so it
  isn't rediscovered as a gap later.
- 2026-07-06 (research thread, not a scenario feature) — §7.7: "the policy
  value in force is always within the policy envelope, which is chosen so
  that the objective is always achievable" formalizes the envelope as an
  **EF(objective_satisfied) invariant** — a policy-setting action that
  falsifies this has left the envelope by definition. Checkable with
  existing Kripke machinery. Candidate paper contribution; explicitly not
  a scenario/widget feature per the scoping decision above.
- 2026-07-06 — Clarification: this exclusion covers the full policy
  envelope/value/setting-behaviour machinery only. NormativePolicy (see
  next entry) is a separate, much lighter-weight concept and is NOT
  covered by this exclusion.

---

## NormativePolicy scope

**Definition:** NormativePolicy (AM-28) models externally-sourced norms
(legislation, regulation, standard, guideline, contractual) as a named,
citable policy object — distinct from the full policy envelope/value
machinery (§7.9), which is deliberately excluded from reference scenarios
(see Policy / policy envelope entry above). This is deliberately
lightweight: a source, a kind, and a description — not a dynamic,
evolvable policy value.

**Standard:** §6.5; §7.5.1 ("domain policies bind all controlled
objects" — cited as V-NEW-20's original justification); §7.3.1 (a plain
community's contract "governs... and constrains the behaviour of its
enterprise object members" — the same universal-binding property);
Annex B.1.5.3 (e-commerceCommunity's contract "refers to a legal
agreement between e.com and its customers" — a plain Community, not a
Domain or Federation, citing an external source directly)

**Toolchain status:** Implemented (AM-28), but restricted by validator
rule V-NEW-20 to Domain and Federation body items only — not permitted on
plain Community.

**Demonstrated in:** `ereferral_model.el` — `MyHealthRecordsAct`,
`NationalClinicalGovernance`, both referenced from `ReferralNetworkFederation`
(a Federation), not from either Domain block. Neither `GPPracticeDomain`
nor `SpecialistPracticeDomain` references NormativePolicy in the current
file — current usage is Federation-only in practice, even though the
validator also permits Domain.

**Decisions:**
- 2026-07-06 — V-NEW-20's Domain/Federation-only restriction rests on
  "domain policies bind all controlled objects" as its stated
  justification — but §7.3.1 gives an ordinary Community's contract the
  same universal-binding property over its members. Once Domain IS a
  Community (settled 2026-06-04), the distinction V-NEW-20 draws does not
  survive scrutiny. Annex B.1.5.3 independently shows the standard's own
  e-commerce example citing an external legal agreement directly from a
  plain Community's contract, with no Domain or Federation involved.
- 2026-07-06 (Zoran) — Motivated directly by the Domain-retirement
  decision above: once the practices are plain communities, either should
  be able to cite a practice-specific regulation without requiring
  federation-wide scope.

**Open:** AM candidate — relax V-NEW-20 to permit NormativePolicy on any
Community. Not yet drafted or implemented.

---

## Establishing behaviour

**Definition:** The behaviour by which a community's contract is put in
place. Per Part 2 §13.2.1: explicit (resulting from interactions of the
objects that will take part in the contract, requiring instantiation of
the contract's template) or implicit (performed by an external agency, or
having occurred in a previous epoch).

**Standard:** §7.6.1; Part 2 §13.2.1; Annex B.1.5.6, B.1.5.8

**Toolchain status:** Partial. `Establishing` grammar rule supports only
`implicit: true` and free-text `commitment by <actor>: "<description>"` —
no trigger/event field, no cross-reference to anything, no conditional
guard.

**Demonstrated in:** `ereferral_model.el` (`ReferralEpisodeCommunity`,
prose-only trigger).

**Decisions:**
- 2026-07-05 — Asymmetry identified: `Terminating` has a structured
  trigger (`on_objective_achieved`); `Establishing` does not.
- 2026-07-06 — Both Annex B examples demonstrate created communities with
  explicit establishing behaviour requiring template instantiation
  (Part 2 §13.2.1 Note 3): `justInTimeCommunity`, the open-registry
  community. Three convergent grounds (library, e-commerce ×2) for a
  grammar amendment.
- **2026-07-06 — Mechanism decided.** Considered three options for the
  trigger's cross-reference target: `[Action]` (unprecedented — `for_action`
  on tokens is deliberately a plain string per DOC-03, not a cross-
  reference; AM-01's typed upgrade was proposed but never built),
  `[Step]` (also unprecedented — `Process`/`Step` has zero usage anywhere
  in any scenario and zero handling in `el_engine.py`/`el_kripke.py`/
  `el_runtime.py`; see the new Process/Step entry), or `[EventDecl]`
  (already proven: `DeonticToken.triggered_by`/`discharged_by` (AM-22)
  and `Action.emits` establish exactly this pattern — "state changes
  when a named event fires" — and it is actively exercised in the
  current toolchain). **Chosen: `established_by: [EventDecl]`**,
  mirroring `DeonticToken.triggered_by` exactly. The full chain: an
  Action `emits` an event → `Establishing.established_by` references
  that same event → the community/federation comes into existence.
- 2026-07-06 — Confirmed no custom scope provider is registered for
  `EventDecl` anywhere in `el_domain.py`/`el_parser.py`, and `Community`
  itself already declares `events+=EventDecl` natively. Cross-reference
  resolution therefore uses textX's default global name-based matching —
  an event emitted by an action inside one community is resolvable from
  `established_by` anywhere else in the model, with no nesting
  requirement. No scoping blocker for the amendment.

**Open:** Amendment not yet drafted in `el_grammar_amendments.md` /
implemented in `el_grammar.tx`. Next concrete step.

---

## Creation-style / episodic community

**Definition:** A community created by another community's behaviour
(§7.3.2: "a community may include behaviour for creating new
communities"), as opposed to standing/pre-existing.

**Standard:** Part 2 creation vs. introduction distinction; §7.3.2 NOTE 3;
Annex B library Case 5, B.1.5.6, B.1.5.8

**Toolchain status:** Not formally expressible — prose-only, riding on
`Establishing`'s free-text commitment field, pending the amendment above.

**Demonstrated in:** `ereferral_model.el` (`ReferralEpisodeCommunity`, as
a plain community — see below for why the unified scenario will differ).

**Decisions:**
- 2026-06-24 — Option A (plain community, prose trigger, expressible now)
  vs. Option B (proper federation-based construct with lifecycle
  extension) — B deferred as "implementation track, not this week."
- 2026-07-06 — Naming: **"Creation-style community"** is the technical
  term (covers all three annex examples). **"Episodic community"** is the
  domain-facing term for the clinical instantiation specifically —
  deliberately chosen to resonate with the established clinical/FHIR
  concept "episode of care." Two-register naming, same pattern as
  compelled/detectable vs. AF/EF.
- 2026-07-06 — Creation behaviour lives in the *creating* community's
  specification, not the created community's own establishing block
  (confirmed by the Annex B pattern).
- **2026-07-06 (Zoran) — SETTLED: the referral episode is a created
  federation**, not a plain community. See the Federation entry for the
  full modelling test (members-are-communities vs. members-are-objects)
  and rationale. This was Option B from 2026-06-24, now activated rather
  than deferred, because Federation's lifecycle gap is being fixed as
  part of the same amendment (see Federation entry).

**Open:** None on the modelling question — settled as created federation.
Remaining: implement the `established_by`/`FedBodyItem` amendment (see
Establishing and Federation entries); Kripke/runtime impact remains
separately deferred (see next entry).

---

## Implicit creation / standing communities

**Definition:** A specification may cover only a period during which a
community already exists — "their existence forms part of the initial
state of the specification, creation being implicit" (§7.3.1).

**Standard:** §7.3.1

**Toolchain status:** Implemented — this is how `gp_referral_scenario.el`
models both practice communities today.

**Demonstrated in:** `gp_referral_scenario.el`.

**Decisions:**
- 2026-07-06 — Confirmed fully conformant, not deficient. The episodic/
  Creation-style community is an *enrichment* for the unified scenario,
  not a correction of an error in the current one.

---

## Kripke/runtime impact of community lifecycle

**Definition:** Extending the Kripke world model so community existence
is itself a modelled, checkable dimension — not assumed from world 0.

**Standard:** n/a (toolchain-internal; grounded in the Establishing/
Terminating entries above)

**Toolchain status:** Not implemented. Identified as the most consequential
and least-tested layer of planned work.

**Demonstrated in:** n/a.

**Decisions:**
- 2026-07-05/06 — Scoped: requires a `community_states` dimension in
  `World`, alongside existing `obligation_states`/`actor_states`. An
  `established_by` transition is the symmetric counterpart to the existing
  `on_objective_achieved` termination transition.
- 2026-07-06 — Explicitly deferred as its own future phase, separate from
  the grammar amendment and the unified scenario design — acknowledged as
  touching the least-tested part of the toolchain (see Layer 3, tests/
  README.md).
- 2026-07-06 — Design constraint for this future work, confirmed by
  direct inspection of `el_kripke.py`: it already treats `Community`,
  `Domain`, and `Federation` fully generically (three separate
  `type(el).__name__ not in ("Community", "Federation", "Domain")` checks,
  no special-casing between them) wherever it collects objectives/
  satisfaction conditions. The `community_states` extension should
  preserve this genericity — check only "does this element have a
  lifecycle with established_by/on_objective_achieved," never branch on
  which of the three type names it is. Today's grammar amendment (adding
  `Lifecycle` to `FedBodyItem`/`DomainBodyItem`) makes this genericity
  easier to sustain, since all three are now symmetric for this purpose.

---

## Party vs agent for clinicians

**Definition:** Whether individual clinicians are modelled as parties
(independently accountable) or agents (accountable via a principal).

**Standard:** §6.6.8-9; A.5 UML (Party is a specialization of active
enterprise object — party-hood and role-filling are not exclusive)

**Toolchain status:** Inconsistent across scenarios.

**Demonstrated in:** `federation_consent_scenario.el` (`GPParty` and
`SpecialistParty` both declared `party`); `gp_referral_scenario.el`
(`GPClinician` = `agent` of `GPPracticeParty`; `SpecialistClinician` =
`party`, "HPI-I registered, accountable in own right").

**Decisions:**
- 2026-06-06 — Both clinicians modelled as parties in
  `federation_consent_scenario.el`.
- 2026-07-05 — HPI-I argument (Zoran): Australian registered clinicians
  bear personal legal/professional accountability regardless of practice
  affiliation — both `GPClinician` and `SpecialistClinician` should be
  parties. The June 6 decision was correct and directly applicable;
  it was not consulted when `gp_referral_scenario.el` was built ten days
  later, producing the asymmetry.

**Open:** Fix `GPClinician` agent→party in the unified scenario.

---

## Authorization ≠ delegation

**Definition:** `AuthorizationDecl` (§6.6.4) is an empowerment — it does
not, by itself, establish principal/agent accountability. That requires
a `DelegationDecl` act (§6.6.6, §7.10.1).

**Standard:** §6.6.4, §6.6.6, §7.10.1

**Toolchain status:** Implemented and documented.

**Demonstrated in:** AM-31 design note §4.0b; `gp_referral_scenario.el`
(`PatientParty` authorizing `SpecialistAIAgent` does not make the patient
a co-principal; `SpecialistClinician` remains sole principal).

**Decisions:** Settled 2026-07-02 (§4.0b).

---

## Permit split by grant mechanism

**Definition:** A single permission split into role-based and
authorization-based grants, so revocation of one doesn't collaterally
affect the other.

**Standard:** §6.6.4 (permit as deontic token; grant mechanism)

**Toolchain status:** Implemented (AM-31b).

**Demonstrated in:** `gp_referral_scenario.el`
(`patientRecordAccessPermitByRole` / `...ByAuthorization`); locked in by
`tests/test_revocation_endpoint.py`.

**Decisions:** Settled 2026-07-02; verified live and test-locked
2026-07-05.

---

## Accountability chain composition

**Definition:** The full accountability chain for an obligation is the
composition of its delegation chain *and* the domain controlling-controlled
relationships along the way — neither alone is sufficient.

**Standard:** §7.10 (delegation, authorization, commitment, declaration,
prescription rule-sets)

**Toolchain status:** Insight captured; no formal treatment yet.

**Demonstrated in:** June 4 session notes; `EDOC26_revision_notes`
items 17-18.

**Decisions:**
- 2026-06-04 — Establishing a domain is itself an implicit authorization
  speech act: the controlling object is the authority, the controlled
  object the authorized party.
- 2026-07-06 — §7.10's five rule-sets proposed as the organizing frame
  for a formal accountability treatment (likely a paper section or
  design-note chapter, not new grammar).

**Open:** Not started as a written treatment.

---

## Compelled vs detectable (AF/EF)

**Definition:** Board-facing vocabulary for Annex C's AF (architecturally
guaranteed) and EF (possible but not guaranteed) modal operators.

**Standard:** Annex C §C.2

**Toolchain status:** Implemented and API-exposed.

**Demonstrated in:** `el_kripke.py`; `GET /obligations/{name}/status`;
`POST /authorizations/{name}/revoke`.

**Decisions:** Vocabulary settled 2026-07-04 — never AF/EF in board-facing
material.

---

## Process / Step (behaviour structuring)

**Definition:** `Process`/`Step` (§7.8.5) models community behaviour as
an authored sequence — a process with ordered, refinable steps, each
carrying its own actors/artefacts/deontic items. The traditional
workflow-style way of specifying "what happens in what order."

**Standard:** §7.8.5

**Toolchain status:** Grammar fully implemented. **Zero usage anywhere:**
no scenario file declares a `process` or `step`; no `refines` usage
anywhere; zero handling in `el_engine.py`, `el_kripke.py`, or
`el_runtime.py` (checked directly 2026-07-06).

**Demonstrated in:** nowhere.

**Decisions:**
- 2026-07-06 — This is a deliberate architectural choice, not an
  oversight, and is distinct from the Policy exclusion (which was an
  explicit scoping decision made once, in the open). Process/Step was
  simply never reached for, because the coordination engine's
  `recommend_action`/Bellman machinery (§C.4) achieves the same
  "what happens next" question through a fundamentally different,
  more flexible mechanism: it iterates over `successors(world)` —
  every world reachable via ANY currently-legal action, determined
  purely by that action's own standalone preconditions and the current
  token state — with no reference to a pre-authored sequence anywhere in
  the logic. Legal *and* optimal orderings emerge from search over the
  reachability graph rather than being declared upfront. Confirmed by
  direct inspection of `recommend_action`'s implementation: it contains
  no reference to Process or Step at all.
- 2026-07-06 — Recorded explicitly so a future session doesn't either (a)
  rediscover this as a "gap" and start authoring Process/Step scenarios
  that the runtime can't execute, or (b) build new runtime machinery
  assuming Process/Step already has support that it doesn't.

**Open:** No action needed unless a future scenario genuinely requires
authored sequencing that the declarative/search-based approach can't
express — not currently anticipated.

---

## Community/Domain/Federation grammar sharing

**Definition:** Whether `Domain` and `Federation` should syntactically
inherit `Community`'s body items (roles, lifecycle, assignment policies,
etc.) via a shared grammar structure, rather than each maintaining its
own independent, manually-synchronized item list.

**Standard:** n/a — toolchain grammar architecture.

**Toolchain status:** Not implemented. `Community`'s body is written as
fixed, individually-named fields (`objective=Objective`,
`lifecycle=Lifecycle`, `roles+=Role`, ...); `Domain`/`Federation` each use
their own separate generic alternation list (`DomainBodyItem`,
`FedBodyItem`). The three rules are structurally different styles, not
variations of one shared rule.

**Demonstrated in:** n/a.

**Decisions:**
- 2026-07-06 — Root-caused: likely historical — `Community` was the
  original, foundational construct; `Domain` (§7.5.1) and `Federation`
  (§7.5.2) were added later as independent rules implementing "special
  community types," each hand-written rather than derived from
  `Community`'s structure. AM-25 fixed Python-level cross-reference type
  resolution (a `Domain`/`Federation` can satisfy a `[Community]`
  reference) but never touched grammar-level syntax sharing — these are
  different mechanisms, and fixing one does not fix the other.
- 2026-07-06 — This is now a confirmed RECURRING cost, not a one-off: the
  identical category of gap has been found three times this week (Domain
  missing roles/assignment-policy/lifecycle; Federation missing
  lifecycle; the Establishing/Terminating asymmetry within Community
  itself). Each time, the fix has been a manual, local patch rather than
  a structural one — meaning a fourth "special community type" amendment
  in the future would need to remember to repeat the same propagation by
  hand.
- 2026-07-06 (Zoran + Claude) — **Consciously deferred, not because it
  isn't worth doing, but because of blast radius.** `Community` is the
  most heavily used construct in the entire toolchain; unifying it with
  Domain/Federation's syntax likely means changing how `community.roles`,
  `community.lifecycle`, etc. are exposed as Python attributes (from
  direct named fields to something derived from a body-items list),
  cascading into `el_domain.py`, `el_engine.py`, `el_kripke.py`, and
  every existing scenario and test. This needs its own careful,
  unhurried session with full re-verification — the same discipline
  already applied to the deferred Kripke/community-lifecycle work — not
  something to fold into the current pragmatic amendment, which is
  additive-only and touches nothing existing.

**Open:** Candidate for a dedicated future refactor session. Today's
pragmatic fix (adding `lifecycle=Lifecycle` directly to `FedBodyItem` and
`DomainBodyItem`) proceeds in the meantime as the additive, low-risk
option.

---

## Scenario maturity language

**Definition:** A vocabulary for what a scenario file is for: **probe**
(disposable, validates one construct or decision), **candidate reference
scenario** (under active construction, not yet verified/promoted),
**reference scenario** (settled, maintained, carries tests), **demo**
(audience-packaged, derived from a reference scenario, may simplify but
must not contradict it), **superseded** (was reference/probe, replaced,
kept for record).

**Standard:** n/a — house convention.

**Toolchain status:** Proposed 2026-07-06; extended 2026-07-06 with
candidate/superseded tiers. Applied in `scenarios/README.md`.

**Demonstrated in:** `scenarios/README.md`.

**Decisions:** Proposed 2026-07-06, motivated directly by the confusion
around `federation_consent_scenario.el`'s unratified status. Extended the
same day when naming the not-yet-built unified referral scenario exposed
a missing tier between "probe" and "reference scenario."
