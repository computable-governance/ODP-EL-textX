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
| CommunityObject | Implemented (AM-26); 2026-07-28 correction on record — community object, not community, is the role filler; MemberRef emphasis open question |
| Objective rules | Implemented |
| Policy / policy envelope | Grammar exists — deliberately excluded from reference scenarios |
| NormativePolicy scope | Implemented (AM-28); widened to any Community (AM-41, 2026-07-22); enforcement-mode field landed (AM-42); optional url field landed (AM-43, 2026-07-28) |
| Establishing behaviour | Implemented (AM-33) — demonstrated in `referral_scenario.el` |
| Creation-style / episodic community | Settled 2026-07-07: created COMMUNITY, not federation (corrected from a 2026-07-06 conclusion) — demonstrated in `referral_scenario.el` |
| Implicit creation / standing communities | Implemented |
| Party vs agent for clinicians | Fixed in `referral_scenario.el` (2026-07-07); `gp_referral_scenario.el` asymmetry remains until superseded |
| Authorization ≠ delegation | Implemented + documented |
| Permit split by grant mechanism | Implemented (AM-31b) |
| Accountability chain composition | Insight captured, no formal treatment |
| Compelled vs detectable (AF/EF) | Implemented + API-exposed |
| Standing accountability: principal_of/delegated_from vs. Domain | Both implemented; documented as deliberate choice |
| Traceability between standing federation and episodic instances | Open question, deliberately not resolved |
| Naming conventions (Annex B precedent) | Settled 2026-07-07 |
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

**Demonstrated in:** `federation_consent_scenario.el` (probe, 2026-06-06),
for the now-retired organizational-structure usage.
`referral_scenario.el`'s `PatientDataDomain` (2026-07-07) is the first
demonstration of the genuine cross-cutting case this entry reserves
`domain` for — one controlling authority (`GPPractice`) reaching across
three controlled objects (`GPClinician`, `SpecialistClinician`,
`SpecialistAIAgent`) for data-governance purposes specifically, cutting
across both practice communities and the episode alike.

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

**Gap found 2026-07-19:** `PatientDataDomain`'s `controlling_object:
GPPractice` has no documented rationale anywhere in this file or
`el_grammar_amendments.md` — checked both, zero hits. This predates a
needed split (see below) and should not be read as settled design intent.

**Settled 2026-07-19 — PatientDataDomain splits into two overlapping
domains.** Rather than one domain with multiple controlling roles,
`PatientDataDomain` should become two domains with different
characterizing relationships and different controlling objects:
- `PatientDataAuthorshipDomain` — characterizing relationship: authorship/
  ownership of the clinical record (copyright-like). Controlling object
  `GPPractice` (for `GPClinician`) and `SpecialistPractice` (for
  `SpecialistClinician`/`SpecialistAIAgent`) — assuming, for now, both
  clinicians are employees (not independent contractors) of their
  respective practices.
- `PatientDataConsentDomain` — characterizing relationship: consent-governed
  use of the record. Controlling object `Patient`.

Grounded directly in the standard, not inferred: X.902 §10.3 note 2 states
domains can be disjoint or overlapping; the Annex B.1.5.9 worked example
shows the same object set governed by multiple overlapping policy domains
with different controlling objects and no hierarchy implied between them.
An object subject to more than one domain must conform to all of their
policies concurrently (§7.4 NOTE, objects governed by multiple communities'
policies at once).

**OPEN FINDING** — The employee/contractor fork is deliberately deferred, not resolved. If
later revisited: contractor status shifts data ownership from practice to
clinician per general agency-law default (employee records generally owned
by employer; independent contractor generally owns their own patients'
records as part of their own business) — this would need per-clinician or
even per-record granularity rather than a single static `controlling_object`
per domain, and a lifecycle-triggered succession/transfer mechanism (Domain
already has `lifecycle` from AM-33) for what happens to authorship-domain
membership when a contractor's engagement ends. Not being built now —
logged so it isn't rediscovered from scratch later.

**OPEN FINDING** — **AM-40 syntax direction (2026-07-19, still pending):** Domain's
`controlling_object`/`controlled_object` are currently bare object
references with no role machinery at all — §7.5.1 explicitly says "roles
of controlled objects... role of controlling object," so these should
become genuine roles. The role-filling statement should NOT introduce a
new `filler:` keyword — it should reuse the `fills` idiom already
established by `MemberRef` (`community fills role`), applied to
`EnterpriseObject` instead of `Community`, as a bare, unlabelled
`DomainBodyItem`:

    obj=[EnterpriseObject] 'fills' role=[Role] ('via' via=[Federation])?

`via` is genuinely new vocabulary — nothing existing lets a domain
role-filling trace back to the federation that authorized it. `fills` is
not new; it's `MemberRef`'s existing pattern generalized.

**OPEN FINDING** — **Open (2026-07-19):** controlling-role cardinality — can more than one
object fill a controlling role in a single domain? — remains genuinely
unresolved by the standard, and is NOT settled by the
`PatientDataAuthorshipDomain`/`SpecialistPractice` case above, since that
case is resolved via two overlapping single-controller domains rather than
by one domain needing multiple controlling fillers. Logged as still open
for any future case that might need it.

**Landed (2026-07-22) — migration carried out.** The split described
above is implemented in `referral_scenario.el`: `PatientDataDomain` is
replaced by `PatientDataAuthorshipDomain` (controlling objects
`GPPractice`, `SpecialistPractice`) and `PatientDataConsentDomain`
(controlling object `Patient`), each still using the existing
`controlling_object`/`controlled_object` syntax (the AM-40 role-based
syntax direction above remains separately pending — not part of this
migration) and each now carrying its own `NormativePolicy`
(`AuthorshipBasis`, `ConsentRightsBasis` respectively), made possible by
AM-41 widening NormativePolicy to any Domain/Community/Federation. The
"Gap found 2026-07-19" note above (undocumented `controlling_object:
GPPractice` rationale) is resolved by this split — each domain's
characterizing relationship and controlling object now has an explicit,
documented rationale. `authorization patientDataAuthorization`'s
`domain_scope` (a plain STRING, not a cross-reference — nothing
validates it) was updated from `"PatientDataDomain"` to
`"PatientDataConsentDomain"`, matching its actual consent/revocation
semantics. See `tests/test_referral_kripke.py`
(`test_patient_data_authorship_domain_structure`,
`test_patient_data_consent_domain_structure`) for the regression tests.

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
- **2026-07-07 — CORRECTION to the 2026-07-06 "created federation" entry
  above.** Checking `ereferral_model.el`'s actual worked design (not just
  the abstract library annex example) showed its episode-equivalent
  (`ReferralEpisodeCommunity`) has roles filled by INDIVIDUAL clinicians/
  agents, not whole communities — by the modelling test above, that is a
  plain community, not a federation. Confirmed as a hard grammar
  constraint, not just a style choice: `MemberRef` is typed
  `community=[Community]` (grammar/v2/el_grammar.tx) — individual parties/
  agents cannot be federation members at all. Directly confirmed against
  the standard itself (§7.5.2: "a community of a number of pre-existing
  communities") — not merely an artifact of this toolchain's grammar.
  `ReferralNetworkFederation` (standing, never created — the durable
  inter-practice relationship) and `ReferralEpisodeCommunity` (created,
  per-referral, a plain community — see Creation-style entry) are
  therefore two separate constructs, not one. `Federation`'s new
  `Lifecycle` support (this entry, above) remains implemented but
  unexercised in any real scenario — `referral_scenario.el`'s
  `ReferralNetworkFederation` has no lifecycle block at all (standing,
  implicit existence); only `Domain`'s `Lifecycle` support and
  `Establishing.established_by` are actually exercised there (see those
  entries).

**Open:** Federation's `Lifecycle` support (this entry) is implemented
and verified (throwaway test, AM-33) but not yet exercised in any real
scenario. Nothing currently blocking; simply hasn't come up.

---

### AIVendor — regulatory-overlay gap (identified 2026-07-09, not yet modelled)

**OPEN FINDING**

**Status:** AM-40's grammar/parser/validator prerequisite landed 2026-07-21 (dual-syntax, unit-tested). The two-construct shape is now demonstrated in `scenarios/vendor/ai_vendor_probe.el` (AM-59) — see update below.

**The gap:** The scenario currently conflates "the AI vendor" with "the deployed AI agent" —
only `SpecialistAIAgent` exists as a party/agent. Privacy and AI regulation treats these as
legally distinct: EU AI Act's provider/deployer split, GDPR's controller/processor split,
HIPAA's covered-entity/business-associate split all separate "the company that built/supplies
the system" from "the system as deployed/operated."

**Proposed shape, if modelled** (requires a probe scenario, not a Reference-scenario edit):
- **Peer layer** — `AIVendor` ↔ `GPPractice`, a negotiated standing relationship: `contract
  federation` (or `contract community`), same pattern as `ReferralNetworkFederation`. Carries
  the *pre-deployment* provider duty (conformance/risk documentation).
- **Subordination layer** — `AIVendor` (or `SpecialistAIAgent` as its deployed instance)
  as a `controlled_object` under `GPPractice`'s `controlling_object` authority: plain `domain`,
  same pattern as `PatientDataDomain`. Carries the *in-use* processor duty (safe operation
  under the practice's instructions).
- These are two different ODP constructs because the obligations are legally different in
  kind (pre-deployment vs. in-use), not just different lifecycle stages of one relationship.

**Correction on record:** there is no standalone `Contract` construct in the grammar —
`contract` is only an optional keyword modifier on `community`/`federation`
(`(contract?='contract')? 'community' name=ID`). Modelling `AIVendor`'s peer relationship
therefore requires a full community/federation declaration with roles and an assignment
policy — comparable weight to `GPPracticeCommunity` — not a lightweight bolt-on.

**Why deferred:** not required for R23–R31 FHIR mapping work (which targets structures
already in the Reference scenario); genuinely new design, candidate/probe-tier work per
`scenarios/README.md`'s maturity model, not a Reference-scenario edit.

**Next step, when prioritised:** a probe scenario (e.g. `vendor/ai_vendor_probe.el`)
validating the two-construct shape in isolation, following the same lifecycle
`federation_consent_scenario.el` and `ereferral_model.el` took before absorption.

**Update 2026-07-14 — three independent motivating cases now on record.**

The peer/subordination shape proposed above (originally scoped to EU AI
Act/GDPR/HIPAA provider-vs-deployer) has since come up unprompted in two
further, unrelated contexts — raising confidence this is a general
governance primitive, not an artifact of one regulatory framing:

1. **Health-AI regulation** (original case) — `AIVendor` ↔ `GPPractice`
   peer federation (pre-deployment conformance duty) vs. `SpecialistAIAgent`
   as controlled object under `GPPractice` domain authority (in-use
   processor duty). 1:1 — one vendor, one deployed instance.

2. **Copyright/collective-licensing** (2026-07-14, Australian TDM-exception
   brainstorm) — `CollectingSociety` ↔ `FrontierAiCompany` peer contract
   federation (pre-training royalty/licence-terms commitment) vs. a
   subordination domain carrying in-use attribution/audit obligation once
   training is running. Also 1:1.

3. **Industrial multi-agent operations** (Pieter van Schalkwyk, "Agents Are
   Context Hungry," LinkedIn, 2026-07-10) — describes the identical two-gate
   structure independently: a context layer performing ingest-time
   data/meaning checks (Information-viewpoint concern, not deontic), and an
   agent harness governing "what the agent is allowed to conclude, what it
   is allowed to do, the operating envelope... the point where authority
   reverts to a person, and the signed record it leaves behind" (the
   subordination domain, in our vocabulary). Explicitly **N peers into one
   domain**: a single plant runs an OEM's agent, a third party's agent, and
   the operator's own agent concurrently, each governed by one shared
   harness/domain regardless of which peer federation it came from.

**Consequence for the proposed shape:** case 3 shows the probe scenario
needs to test N-peer-federations → one-subordination-domain from the
outset (multiple controlled objects, each traceable to a distinct peer
federation, one controlling object/domain binding all of them to a common
envelope) — not just the 1:1 shape cases 1 and 2 alone would have
suggested. Building a 1:1 version first and discovering the N-peer
requirement afterward would have meant redoing the domain-membership
design.

**Priority note:** still probe/candidate-tier, not required for R23–R31
FHIR mapping, still outside the current commercial-focus window. Ordered
just ahead of #7 (Board UI polish), #8 (concurrent multi-episode), #9
(LLM-to-DSL) once that window closes, given three independent cases now
outweigh those items' single-domain motivation.

**Secondary cross-reference, lower priority:** Pieter's context/harness
split is also an independent, external, industry-practitioner
confirmation of the Enterprise-vs-Information viewpoint boundary in
`five_viewpoint_dsl_position_note.tex` — worth a citation there if that
paper thread is revisited, not urgent.

**Update 2026-07-19 — consolidated N-peer probe design.**

Three peer contract federations — `OEMVendorFederation`,
`ThirdPartyVendorFederation`, `OperatorVendorFederation` — each pairing a
`PlantCommunity`/`PlantObj` with one vendor's own `Community`/
`CommunityObject`, each carrying its own `NormativePolicy` representing a
pre-deployment provider duty. One shared `PlantGovernanceDomain` with
`controlling_role` `plantAuthority` (filled by `Plant`) and
`controlled_role` `deployedAgent` (filled by three agent instances, each
`via=[Federation]` tracing back to whichever peer federation admitted it),
carrying its own `NormativePolicy` representing the in-use/deployer safety
duty.

Deliberate modelling choice: AI agents get no intrinsic provider/deployer
type marker — that character emerges purely from which federation/domain
the agent is a member of (ODP-faithful: type membership emerging from
role-filling, not an intrinsic label).

Three motivating cases this mechanism is meant to generalize across, with
`NormativePolicy.kind` varying per case:
- Health/FHIR EU AI Act — `kind: legislation` on both the federation and
  the domain side.
- AU copyright/TDM — `kind: legislation` for the copyright-act
  absence-of-TDM-exception side; `kind: contractual` for the
  licensing-terms side.
- Pieter van Schalkwyk's industrial N-peer case — `kind: contractual` for
  vendor conformance agreements; `kind: standard`/`legislation` for in-use
  machinery-safety obligations.

**Update 2026-08-23 — probe scenario built, AM-40 loop closed.**

`scenarios/vendor/ai_vendor_probe.el` demonstrates the full two-construct
shape: two independent peer contract federations (AIVendorAlphaSupplyFederation,
AIVendorBetaSupplyFederation) each carrying the pre-deployment provider
duty, feeding into one shared subordination domain
(AIVendorGovernanceDomain) using AM-40's role-based syntax exclusively.
Each deployed agent's `via=[Federation]` correctly traces back to its
originating vendor federation, confirmed against the real parsed model
(not just a parse-success check) in `tests/test_ai_vendor_probe_scenario.py`.

Deliberately structural only (no burdens/commitments/Kripke) — the gap
was always about provenance and role correctness, not discharge
semantics. `PatientDataAuthorshipDomain`/`PatientDataConsentDomain`'s
migration to the new syntax remains separately deferred, unaffected by
this probe.

**Cross-reference (2026-07-19):** each peer federation's pre-deployment
`NormativePolicy` and the shared domain's in-use `NormativePolicy` are
exactly the kind of policy pair the enforcement-mode finding below is
about — see the NormativePolicy scope entry's "Finding (2026-07-19)"
paragraph for the `enforcement: policed pessimistic | policed optimistic
| unpoliced` field (landed 2026-07-22, AM-42) and why it stays distinct
from `discharge_mode`.

---

## Concurrent multi-episode runtime

**OPEN FINDING**

Toolchain currently runs a single module-level `_runtime` instance per scenario;
every endpoint (`get_available_actions`, `execute_action`, `/debug/tokens`,
`/reset`, etc.) implicitly assumes one active episode at a time. Genuine
multi-instance support — "episode 1 vs. episode 2," each independently
addressable — requires redesigning state storage (dict of `Runtime` objects
keyed by episode ID, likely derived from `Encounter.episodeOfCare`) and
touching every endpoint accordingly. Deliberately out of scope for R26–R29;
builds on Encounter-extraction work from that item. Own multi-session project;
treat as a production-readiness milestone, not a routine feature. Not started.

---

## LLM-to-DSL translation pipeline (Mode 2)

Research direction, not yet implemented as a pipeline — components exist
(CLAUDE.md as in-context grammar spec, `.el` examples as few-shot, validator
as automated check, API for reasoner execution) but no structured prompt
template, no automated validator-feedback loop, no translatability scorer,
no repeatable worked example. Core research question: can an LLM correctly
classify natural-language obligations as compelled (AF/strict) vs. detectable
(EF/eventual) — the same distinction driving the toolchain's central formal
finding. Translatability varies by document type (~60–70% for consent
directives, ~25–30% for strategic governance documents like the National
Model for Clinical Governance). Prerequisite: confirm `_build_obligation_descriptors()`
fix has landed — flagged as non-negotiable before this work starts, since a
validator that's already wrong makes LLM-output failures unattributable.
Not started.

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

**Correction (2026-07-28) — it is the community OBJECT, not the community
itself, that fills a federation role.** Direct standard citations: §7.3.2,
"a community object fulfils one or more roles in other communities"; §6.2.2,
a community object "is a composite enterprise object that represents a
community" whose "components... are objects of the community represented."
The community is what is being represented; the CommunityObject is the
actual, interaction-capable filler of the role. This corrects informal
language used in recent design discussion (the AIVendor probe sketches
above; this index's own existing entries describing `MemberRef`, e.g. the
Domain entry's "`community fills role`" phrasing and the Federation entry's
"whole communities" phrasing) that said or implied the community itself
fills the federation role, with the community object as a secondary/
optional detail. Per the standard, it is the reverse: the community object
is the primary filler; the community is what it represents. Those existing
informal phrasings are not being rewritten as part of this correction — only
flagged here as informal, pending any future editing pass.

**OPEN FINDING** — **Open question, recorded not resolved (2026-07-28):** `MemberRef`'s
current grammar (`grammar/v2/el_grammar.tx`) reads

    member: community=[Community] ('represented_by' represented_by=[CommunityObject])?
        ('fills' fills=[Role])?

with `fills` attached to the `community` field and `represented_by` marked
optional. Given the standard's own wording above, this may have the
emphasis backwards — if the community object is what actually does the
filling, a `MemberRef` with `fills` present but no `represented_by` would
be asserting a role-filling with no object capable of performing it. This
needs a careful check against the actual grammar file (done — quoted above)
and against whatever existing tests/scenarios use `MemberRef` before any
change is proposed. Recording the question here, not proposing a fix.

**OPEN FINDING** — **Finding 1 (2026-07-28) — `DelegatedFrom.delegator` should be typed
`[Party]`, not `[EnterpriseObject]`.** Per ISO/IEC 15414's Figure A.5
(class diagram; confirmed via a secondary source describing the figure
directly — Sepanosian's thesis, cited here only for its factual
description of the standard's own diagram structure, not as a design
authority, per this project's standing "do not cite Sepanosian as a
design reference" note): "Principal and Agent... are specialisations of
Party and ActiveEO respectively." That is, Principal is required to be a
Party specifically (narrower type); Agent may be any active enterprise
object (broader type, not restricted to Party). Confirmed against the
current grammar (`grammar/v2/el_grammar.tx`):

    DelegatedFrom:
        'delegated_from' delegator=[EnterpriseObject]
        ('duration' ':' duration=STRING)?
    ;

`delegator` is typed `[EnterpriseObject]`, not `[Party]` — this does not
enforce the Figure A.5 restriction. Also confirmed: no validator rule
enforces this either. V-07 (`DelegationDecl`, a separate, different
construct — the speech-act version, §7.10.1) requires both delegator and
delegate to be party OR agent (symmetric), which is a different rule from
the Figure A.5 restriction and doesn't substitute for it. AM-31-V1
(`Authorization.authority` must be a party) is also a different, adjacent
relationship, not this one. This is a confirmed gap, not yet fixed —
flagged for careful implementation in a future session, given the need to
check whether any existing scenario currently declares a `delegated_from`
pointing at something other than a Party before tightening this type.

**Investigation 1 results (2026-07-28) — blast radius, before any grammar
change.** Every `delegated_from:` declaration in `scenarios/**/*.el` was
searched and its delegator traced back to its `ObjectKind` declaration.
16 real declarations found; 10 are already `party` (no-op if tightened):
`referral_scenario.el:178` (`GPClinician`), `referral_scenario.el:190`
(`SpecialistClinician`), `ecommerce_scenario.el:55` (`ECom`),
`ecommerce_scenario.el:57` (`CFO`), `consent_scenario.el:46`
(`GPPracticeParty`), `ereferral_model.el:20` (`GPPractice`),
`generated_governance.el:32` (`GpPractice001`),
`federation_consent_scenario.el:22` (`SpecialistParty`),
`gp_referral_scenario.el:76` (`GPPracticeParty`),
`gp_referral_scenario.el:92` (`SpecialistClinician`).

**5 are declared `agent`** and would fail to validate if `delegator` were
tightened to require party kind:
- `ecommerce_scenario.el:67,75,82` — `eSystem` (declared `agent` at line
  52, described as "automated agent handling orders, payments, and
  catalogue"), delegating to `pricingService`, `shippingSubsystem`,
  `purchasingSubsystem` respectively.
- `consent_scenario.el:54` — `SpecialistAgent` (declared `agent` at line
  43), delegating to `AIDiagnosticAgent`.
- `generated_governance.el:39` — `SpecialistDrOkonkwo` (declared `agent`
  at line 29), delegating to `AiDiagnosticAgent001`.

Of these three files, only `generated_governance.el` is exercised by a
currently-passing test — `tests/test_fhir_mapper_golden.py::test_fhir_mapper_output_parses_and_validates`
parses and validates it with `validate=True` and asserts `result.ok`.
Tightening the type would break this test, and would additionally require
new kind-aware logic in `toolchain/fhir_mapper.py` (`_set_delegated_from`/
`_infer_delegation_structure`), which currently sets `delegated_from` from
FHIR-derived data with no kind check at all. `ecommerce_scenario.el` and
`consent_scenario.el` are not loaded by any test by path, so no test would
fail for those two, but the files themselves would stop validating.
(A separate, pre-existing, unrelated issue surfaced incidentally:
`ecommerce_scenario.el:89` references `Customer` as a delegator, but
`Customer` is never declared with any `ObjectKind` anywhere in that file —
a latent dangling reference, not a consequence of this finding.)

No test in `tests/` constructs or asserts on `DelegatedFrom`/
`ObjectBody.delegated_from` directly. The two `.delegator` assertions
found in `tests/test_referral_kripke.py:130,133` turned out to be on the
unrelated `Delegation` speech-act construct (`from:`/`to:`, §7.10.1), not
`DelegatedFrom` — same attribute name, structurally different rule/class
(`el_domain.py`: `Delegation` vs. `DelegatedFrom`).

**Structural finding:** there is no `[Party]` grammar rule to retype to.
`party` is only one enum value of `EnterpriseObject.ObjectKind`
(`grammar/v2/el_grammar.tx:90-99`), not a distinct subtype/rule — there is
no `Party` class the way there is a `Domain`/`Community` class pair.
"Tightening to Party" therefore cannot be a same-shape grammar retype; it
would need either a new grammar-level Party subtype, or a validator-level
kind check layered on top of the existing loose `[EnterpriseObject]`
reference — the same pattern AM-31-V1 already uses for
`Authorization.authority` (enforced in `el_validator.py`, not in the
grammar). Choosing between those two mechanisms is a separate design
decision, not resolved by this investigation.

**OPEN FINDING** — **Open conceptual question, not an engineering one — recorded, not
resolved:** §6.6.8 NOTE 2 states "the delegation may have been direct, by
a party, or indirect, by an agent of the party having authorization from
the party to so delegate." The three `agent`-declared delegators above
(`eSystem`, `SpecialistAgent`, `SpecialistDrOkonkwo`) may be legitimate
instances of exactly this indirect/sub-delegation case, rather than
modelling errors. Before any validator rule is written enforcing a
Party-only restriction, this needs settling against the standard's own
text: does an agent sub-delegating in this way formally become a
Principal in Figure A.5's strict Party-only sense (in which case these
three would genuinely need to be reclassified, or the delegation
re-expressed some other way), or does the standard model indirect
delegation through some different mechanism that doesn't reuse the
Principal class at all (in which case tightening `delegator` to
`[Party]` unconditionally would be the wrong fix, and a Party-OR-agent-
with-authorization rule would be needed instead, mirroring how V-07
already treats `DelegationDecl`)? Not resolved here — this is the
question that has to be settled before Finding 1 can be scoped for
implementation.

**OPEN FINDING** — **Finding 2 (2026-07-28) — CommunityObject should satisfy
EnterpriseObject/ActiveEO typing (Figure A.2).** Per §6.2.2 and Figure
A.2, CommunityObject is itself an active enterprise object (a composite
one, representing a community). Confirmed earlier this week: in the
current grammar/domain-class implementation, CommunityObject is its own
separate top-level rule/dataclass, NOT typed as a subtype of
EnterpriseObject — meaning a CommunityObject currently cannot fill
anywhere an EnterpriseObject is expected: not a Domain's `controlled_role`
(AM-40), and, per Finding 1 above, potentially not `PrincipalOf.agent` or
`DelegatedFrom.delegator` either, despite the standard treating it as
exactly the kind of thing that should qualify. This is the same gap
already noted in the "Correction (2026-07-28)" entry above regarding
`MemberRef`'s `fills`/`represented_by` emphasis, now confirmed to be part
of a broader pattern: CommunityObject's standing as a full ActiveEO is not
currently reflected anywhere in this toolchain's type system. Flagged as a
confirmed, real gap requiring a proper grammar/domain-layer fix — not a
quick patch, since it likely requires either a shared parent class between
CommunityObject and EnterpriseObject in the Python domain layer, or
restructuring how cross-reference matching works for these types. Not yet
investigated for blast radius or implemented.

**Investigation 2 results (2026-07-28) — class hierarchy, metamodel risk,
and cross-reference site inventory.** Confirmed directly in
`toolchain/el_domain.py`: `EnterpriseObject` and `CommunityObject` are
pure Python siblings — neither inherits the other, and nothing else in
the file inherits from `EnterpriseObject` at all. The one existing
inheritance relationship in the whole domain-class file is
`class Domain(Community)` (AM-25).

The toolchain's entire semantic layer — `el_validator.py`,
`el_reasoner.py`, `el_runtime.py`, `el_kripke.py` — is driven purely by
`type(x).__name__` string comparisons (e.g. `_collect(model, "EnterpriseObject")`,
`if type(el).__name__ != "EnterpriseObject": continue`). Zero `isinstance()`
calls against any domain class were found anywhere in those four modules.
This matters directly: even if `CommunityObject` were made a Python
subclass of `EnterpriseObject`, every one of these exact-name-string
checks would keep evaluating false for a `CommunityObject` instance (its
`__name__` stays `"CommunityObject"`, unaffected by inheritance) — so
inheritance alone would fix nothing at the semantic-validation/runtime
layer. That would be a second, separate required fix, touching every
`_collect`/`type(...).__name__` site currently keyed on
`"EnterpriseObject"`.

Separately, textX's own cross-reference resolution (`textx_isinstance`,
used by the default `PlainName` scope provider for every un-annotated
`[ClassName]` reference in this grammar) checks Python `isinstance()`
first. This is exactly the mechanism that already lets `Domain` satisfy
`[Community]` cross-references today, per `Domain`'s own docstring in
`el_domain.py` citing AM-25 for that purpose — a direct, working
precedent for the grammar-level effect this finding is asking about.

**Metamodel-construction risk, corrected citation.** The prior note
mislabeling the `DOMAIN_CLASSES`/`validate_user_classes()` incident as
"AM-41" is corrected here: the incident is documented under **AM-40**
(`docs/el_grammar_amendments.md`, "Implementation notes (2026-07-21) —
dual-syntax landing"), not AM-41 (which is the unrelated NormativePolicy-
widening entry — see the NormativePolicy scope entry above).
`validate_user_classes()` raises `TextXSemanticError` when a registered
class's `__name__` was never matched against a grammar rule name during
parsing — a name-string/registration mismatch, unrelated to Python class
hierarchy; it never inspects `__mro__` or base classes. Since
`CommunityObject`'s grammar rule and its `DOMAIN_CLASSES` registration
would both be left untouched by an inheritance-only change, this specific
failure mode looks low-risk for that change in isolation — the AM-40 risk
comes from *accompanying* changes (e.g. introducing a new unregistered
helper class), not from the inheritance edge itself.

**Full `[EnterpriseObject]` cross-reference inventory** (18 occurrences
across 13 fields in `grammar/v2/el_grammar.tx`): `EnterpriseObject.type_ref`
(`isa`), `DelegatedFrom.delegator`, `PrincipalOf.agent`,
`DomainControllingObj.obj`, `DomainControlledObj.obj`,
`DomainRoleFiller.obj` (AM-40), `Commitment.actor`, `Commitment.principals`,
`Delegation.delegator`, `Delegation.delegate`, `Authorization.authority`,
`Authorization.authorized_agent`, `Prescription.actor`,
`Declaration.actor`, `Evaluation.evaluator`,
`ViolationResponse.responding_actor`, `ViolationResponse.escalate_to`.

Several of these already carry a kind-based validator check layered on
top of the raw `[EnterpriseObject]` cross-reference type — `Commitment.actor`/
`principals` (V-10), `Authorization.authority` (AM-31-V1, requires party),
`ViolationResponse.escalate_to` (V-NEW-16, requires party if
`response_kind == escalate`), `Delegation.delegator`/`delegate` (V-07,
requires party or agent) — every one of which reads `obj.kind`, a field
`CommunityObject` does not have at all (confirmed against its class
definition: only `name`, `description`, `abstracts`). So even for slots
where letting a `CommunityObject` fill them seems plausible per §6.2.2/
Figure A.2's characterization of a community object as a composite active
EO, each kind-checked site would need its validator logic reconciled
(giving `CommunityObject` a synthetic `kind`, or special-casing it in each
rule) before the fix would work end-to-end — a grammar-level typing
change and a toolchain-semantics change are two separate pieces of work,
not one.

**Status for both findings above:** both findings fully investigated
(blast radius, metamodel risk, and full cross-reference-site inventory
complete). Neither is scoped for implementation yet, and neither is
scheduled.

Finding 1 needs the sub-delegation conceptual question above (§6.6.8 NOTE
2, direct vs. indirect delegation) resolved before any validator rule can
be written — this is a standard-interpretation question, not an
engineering one.

Finding 2 is a multi-step fix — the `CommunityObject`/`EnterpriseObject`
inheritance change itself, plus updating every name-string check across
`el_validator.py`/`el_reasoner.py`/`el_runtime.py`/`el_kripke.py` that
currently excludes `CommunityObject` by construction, plus resolving
`CommunityObject`'s missing `.kind` field against the several kind-based
validator rules cataloged above — warranting its own dedicated future
session, at least comparable in size to today's AM-40 through AM-43 work
combined.

(See also the still-open `MemberRef` `fills`/`represented_by` question
logged earlier today, which is closely related to Finding 2.)

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

**Toolchain status:** Implemented (AM-28); widened to any plain Community
by AM-41 (2026-07-22). Validator rule V-NEW-20, which previously
restricted NormativePolicy to Domain/Federation body items only, is
retired — once Community's own grammar rule could carry a
NormativePolicyRef too, V-NEW-20 could no longer fire on anything the
grammar allows, so it was removed rather than widened. Community's rule
gained `(normative_policies+=NormativePolicyRef)*` alongside its other
typed lists; a new object processor P11 (`process_community`) resolves
each reference to its `NormativePolicy`, matching the resolution
convention P8/P9 already use for Domain/Federation.

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

**Closed (2026-07-22) — AM-41 drafted and implemented.** Grammar, parser,
and validator now permit `NormativePolicy` on any `Community`, `Domain`,
or `Federation` — no distinction remains between them for this purpose.
See `docs/el_grammar_amendments.md`, AM-41, for the full change record.

**Finding (2026-07-19) — standard grounding for an enforcement-mode field
on NormativePolicy.** ISO/IEC 15414 §7.9.4 ("Policy enforcement") states
policies can be specified as policed and enforced, or unpoliced. If
policed, enforcement is either pessimistic (preventative — mechanisms
ensure obligated actions occur, prohibited actions don't, authorized
actions aren't blocked; used when trust is low and potential damage is
high) or optimistic (allow the action, detect and respond to
non-compliance after the fact).

**Landed 2026-07-22 (AM-42).** Implemented as:

    enforcement: policed pessimistic | policed optimistic | unpoliced

This reuses Policy's own pre-existing `Enforcement`/`EnforcementMode`
construct (§7.9.4, already implemented in `grammar/v2/el_grammar.tx` for
generic `Policy`) by direct reference to the same `EnforcementMode` rule
— not a coincidence of vocabulary — rather than the differently-shaped
single-enum `policed_pessimistic | policed_optimistic | unpoliced` form
originally proposed here. That original proposal turned out to collide
by rule name with the pre-existing `EnforcementMode` and was reverted and
redesigned mid-session; see `docs/el_grammar_amendments.md`, AM-42, for
the full account. `NormativePolicy.enforcement` deliberately omits
`Policy.Enforcement`'s `mechanism` sub-field, consistent with
NormativePolicy's lightweight design (a source, a kind, now optionally
an enforcement mode — not the full policy envelope/value machinery).

Explicitly NOT the same concept as `discharge_mode` (strict/monitored) on
DeonticToken, and should NOT be renamed or merged with it, despite the
conceptual overlap. `discharge_mode` is a runtime/Kripke-model property of
a specific token (is violation reachable by construction, or only
observable after the fact) — already established, reader-facing
vocabulary threaded through the arXiv paper, board UI, and figures,
deliberately kept in plain language ("detectable" → "monitored", per an
earlier revision). `NormativePolicy.enforcement` would instead be a
policy/regulatory-level property, grounded in the cited source, of
whether and how that obligation is meant to be enforced at all. The
relationship: a policy's declared enforcement mode is the regulatory
justification for a token's `discharge_mode` choice — e.g. a
NormativePolicy citing the EU AI Act's conformity-assessment requirement
would declare `enforcement: policed pessimistic`, which is the reason a
token it governs should get `discharge_mode: strict`. Keep the two
concepts and their vocabulary distinct; do not collapse them.

**Worked-example grounding.** ISO/IEC 15414 Annex B has exactly two
worked examples: B.1 (e-commerce system) and B.2 (Templeman Library,
University of Kent). B.2's borrowing regulations show a concrete
enforcement/consequence chain: late return creates a financial charge
(new obligation triggered by violation); continued non-payment escalates
to suspension of borrowing privileges by the Librarian (identified
authority revoking a permit). This is structurally identical to the
already-implemented `patientDataAuthorization` /
`patientRecordAccessEmbargo` pattern (revoke → embargo) — log that no new
grammar construct is needed for the consequence chain itself, only the
enforcement-mode label on NormativePolicy. The existing
token/embargo/lifecycle machinery already covers "what happens on
violation"; enforcement mode only needs to state the regulatory posture
that machinery is satisfying.

**OPEN FINDING** — **Open question, recorded not resolved:** should there eventually be a
validator check for consistency between a NormativePolicy's declared
enforcement mode and the `discharge_mode` of the tokens it governs (e.g.
flagging a `policed pessimistic` policy governing a `monitored`-mode
token as a mismatch worth surfacing)? Not building this now — logged so
it isn't lost.

**Positioning link:** this sharpens the AU AI-regulation positioning note
(2026-07-19, `AU_AI_Regulation_NormativePolicy_Positioning_Note.md`) —
NAIC's Guidance for AI Adoption would be `kind: guideline`,
`enforcement: unpoliced`; the EU AI Act would be `kind: legislation`,
`enforcement: policed_pessimistic`. Not just a different citation, a
different enforcement posture.

**Landed 2026-07-28 (AM-43).** `NormativePolicy` gains an optional `url`
field, a plain STRING alongside `source` — a link to the cited instrument,
where `source` only ever carried descriptive text. Motivated by
`docs/Board_NormativePolicy_Display_Investigation_2026-07-22.md`'s
combined next-session scope addendum (item 1): a colleague viewing the
board's citation line asked "where's the URL?" The referral scenario's
three board-reachable citations (`AuthorshipBasis`, `ConsentRightsBasis`,
`ReferralEpisodeAccountability`) now carry real URLs. See
`docs/el_grammar_amendments.md`, AM-43, for the full change record.

**Landed 2026-07-28 (item 2 of the same addendum, no AM number).**
`el_kripke.find_normative_policies_for_token` gains a second, fallback
resolution path — `find_governing_element_via_authorization` — for a token
that is the `grants_permit` or `on_revocation_embargo` target of some
`Authorization` declaration, resolved via that `Authorization`'s
`domain_scope` (a plain, unvalidated STRING name-matched against
`model.elements`; still not the typed `[DomainDecl]` cross-reference the
tentative `AM-14` amendment proposes). This is deliberately narrower than
"permit/embargo resolution" in general: a permit/embargo referenced only
via a role action's `requires_permit`/`inhibited_by_embargo` — never via
any `Authorization` — still doesn't resolve, e.g.
`patientRecordAccessPermitByRole`. What it does newly reach:
`patientRecordAccessPermitByAuthorization` and
`patientRecordAccessEmbargo`, both granted/revoked by
`patientDataAuthorization`, now resolve to `PatientDataConsentDomain` and
its `ConsentRightsBasis` citation — the citation most narratively relevant
to patient consent, per the investigation note. No AM entry: pure
toolchain logic (`el_kripke.py`), no grammar or validator change,
consistent with `find_normative_policies_for_token` itself (commit
`a2b92a6`) also having no AM entry. Tests:
`tests/test_permit_embargo_governance_resolution.py` (new — direct
`el_kripke` calls, including a throwaway-fixture case confirming a
`domain_scope` matching no real element degrades to `(None, [])` rather
than erroring) and additions to `tests/test_token_governance_endpoint.py`.
Frontend (`renderConsent` wiring, computable-governance-ui) is separate
follow-on work, not done here.

**Confirmed 2026-07-22 — episodic communities already support this via
AM-41, no new grammar required.** Investigated directly: the
"Creation-style / episodic community" pattern (see that entry) is not a
distinct grammar construct — `ReferralEpisodeCommunity` in
`referral_scenario.el` parses as `type(el).__name__ == 'Community'`,
the exact same rule AM-41 modified. "Episodic" is purely a usage pattern
(established via `lifecycle { establishing { established_by: <event> } }`,
AM-33, with the triggering event emitted from a separate, standing
community) layered on top of the ordinary `Community` rule — nothing
distinguishes it from a standing community at the grammar or type level.
A throwaway fixture mirroring `ReferralEpisodeCommunity`'s real creation
pattern, additionally carrying a `normative_policy:` reference, parsed,
validated, and resolved by identity with zero grammar changes; now a
permanent regression test (`tests/test_am41_community_normative_policy.py`,
`test_episodic_community_normative_policy_resolves`).

The genuinely open matter here is not a toolchain gap — it's a
modelling/process question for whoever writes the `.el` file: how a
citation stays correctly pinned to whichever specific reform (e.g. an
AISI targeted reform) actually governed a particular past deployment
instance, versus a standing citation that may drift out of sync as
guidance evolves over time. That's a usage-discipline concern, not
something the grammar needs to solve.

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
  (the only option with a real, implemented precedent:
  `DeonticToken.triggered_by`/`discharged_by` (AM-22) and `Action.emits`
  establish exactly this pattern — "state changes when a named event
  fires" — though checked directly 2026-07-06 and confirmed to have
  zero actual usage in any scenario, the same implemented-but-unexercised
  status as Process/Step below, not "actively exercised" as first
  assessed). **Chosen: `established_by: [EventDecl]`**,
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

**Open:** None. Implemented as AM-33 (`el_grammar_amendments.md`,
`el_grammar.tx`, `el_domain.py`, `el_parser.py`), verified end-to-end via
a throwaway test (2026-07-06), and now genuinely exercised in a real
scenario — `referral_scenario.el`'s `ReferralEpisodeCommunity` (a plain
Community, not the Federation first assumed — see Creation-style entry
correction below) uses `established_by: referralSubmitted`, resolved
against an event emitted by `GPPracticeCommunity`'s `initiateReferral`
action.

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
- 2026-07-06 (Zoran) — Initially concluded: the referral episode is a
  created federation, not a plain community — reasoning from the
  library annex example alone (Federation entry, above).
- **2026-07-07 — CORRECTED.** Checking `ereferral_model.el`'s own actual
  worked design (rather than reasoning from the abstract annex example
  alone) showed its `ReferralEpisodeCommunity` has roles filled by
  INDIVIDUAL clinicians/agents, not whole communities — by the
  Federation entry's own modelling test, that makes it a plain
  community, not a federation. Confirmed as a hard grammar constraint
  (`MemberRef` typed to `[Community]`; individuals cannot be federation
  members at all — §7.5.2) and independently confirmed against the
  standard directly, not merely this toolchain's grammar.
- 2026-07-07 — Circularity found and fixed while building
  `referral_scenario.el`: the action that creates the episode
  (`initiateReferral`, emitting the trigger event) cannot live inside
  the episode community it creates. Moved to `GPPracticeCommunity` (the
  *creating* community) — matching the Annex B pattern ("creation
  behaviour lives in the creating community's specification") concretely
  for the first time, not just as a stated principle.
- 2026-07-07 (Zoran) — **SETTLED: the referral episode is a created
  plain COMMUNITY** (`ReferralEpisodeCommunity`), separate from the
  standing `ReferralNetworkFederation` (which federates the two
  pre-existing practice communities and never itself gets created). Two
  constructs, not one — see Federation entry.

**Open:** None on the modelling question — settled as created community,
demonstrated in `referral_scenario.el` (parse/validate verified,
2026-07-07). Kripke/runtime impact remains separately deferred (see next
entry).

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

**OPEN FINDING**

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

**Open:** None. Fixed in `referral_scenario.el` (2026-07-07) —
`GPClinician` is now `party`, matching `SpecialistClinician`. Extended
further than originally scoped: the accountability chain itself was also
corrected to clinician-to-clinician (`GPClinician` → `SpecialistClinician`,
"Option B"), not practice-to-practice, with layered `principal_of`/
`delegated_from` distinguishing standing organisational affiliation from
genuine episode-scoped delegation — see "Standing accountability" and
"Accountability chain composition" entries. `gp_referral_scenario.el`'s
asymmetry remains as-is until it is superseded.

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
- 2026-07-07 — Concrete modelling realization in `referral_scenario.el`:
  a genuine two-hop delegation chain (`GPClinician` → `SpecialistClinician`
  → `SpecialistAIAgent`, "Option B", clinician-to-clinician not
  practice-to-practice) with a principled distinction now applied
  consistently — `principal_of` ALONE marks standing organisational
  affiliation of an independently-accountable party; `principal_of`
  PAIRED WITH a reciprocal `delegated_from` marks genuine, if
  episode-scoped, delegated principal-agent accountability. See
  "Standing accountability" entry. This resolves the `principal_of`
  semantic-looseness concern more precisely than the caveat-comment
  originally proposed for it.

**OPEN FINDING** — **Open:** Formal written treatment (paper/design-note) not started;
concrete modelling pattern now exists and is demonstrated.

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

**OPEN FINDING** — **Open:** Candidate for a dedicated future refactor session. Today's
pragmatic fix (adding `lifecycle=Lifecycle` directly to `FedBodyItem` and
`DomainBodyItem`) proceeds in the meantime as the additive, low-risk
option.

---

## Standing accountability: principal_of/delegated_from vs. Domain

**Definition:** Two structurally distinct grammar mechanisms can both
express the same underlying fact of standing internal accountability —
one object being accountable for/controlling another. `principal_of`/
`delegated_from` (ObjectBody, on Party/Agent declarations) is local and
lightweight, declared inline where the relationship lives. `Domain`
(§7.5.1, controlling_object/controlled_object) is a separate top-level
community-type element, naturally suited to one controlling authority
reaching across several controlled objects at once.

A further, more precise distinction found while building
`referral_scenario.el`: `principal_of` ALONE (no reciprocal
`delegated_from`) marks standing organisational affiliation of an
independently-accountable party (`GPPractice`↔`GPClinician`,
`SpecialistPractice`↔`SpecialistClinician` — deliberately not full
subordinate agency). `principal_of` PAIRED WITH a reciprocal
`delegated_from` marks a genuine, if possibly episode-scoped, delegated
principal-agent relationship (`GPClinician`↔`SpecialistClinician`,
`SpecialistClinician`↔`SpecialistAIAgent`). The same construct, used two
different ways depending on whether it's paired.

**Standard:** §7.5.1; §6.6.8-9

**Toolchain status:** Both implemented; neither supersedes the other.

**Demonstrated in:** `referral_scenario.el` uses principal_of/delegated_from
(asymmetric form) for `GPPractice`↔`GPClinician` and
`SpecialistPractice`↔`SpecialistClinician` (single practice-clinician
pairs, standing); the paired form for the two genuine delegation hops;
and the same file's `PatientDataDomain` uses the Domain form for a
genuinely multi-object controlling relationship (see Domain entry).

**Decisions:** 2026-07-07 (Zoran) — noted as a deliberate choice for this
scenario (economy of expression for single pairs), not a semantic
necessity — either mechanism could express either relationship. The
asymmetric-vs-paired distinction for `principal_of` specifically was
identified the same day, resolving the earlier-flagged semantic
looseness (see "Party vs agent for clinicians" entry) more precisely
than the caveat-comment first proposed.

**Key learnings (2026-07-19):** `principal_of`/`delegated_from` (§6.6.8,
formal agency) is a distinct question from data ownership. `GPPractice`'s
existing `principal_of` `GPClinician` (with no reciprocal
`delegated_from`) signals organisational affiliation without full
agency, because `GPClinician` retains independent professional
accountability — and this reasoning holds whether `GPClinician` is an
employee or a contractor, i.e. neither engagement type should get
`delegated_from`. Data ownership is a separate fact, properly
represented via a `NormativePolicy` (`kind: contractual`, source citing
the employment/engagement agreement or relevant legal default) attached
to the authorship domain (see `PatientDataAuthorshipDomain`, Domain
entry) — not via `principal_of`/`delegated_from`. **OPEN FINDING** — Also logged: there is
currently no grammar construct for recording a clinician's engagement
type (employee vs. contractor) as a checkable fact — it can only live as
prose in a `NormativePolicy.source` string today. Flagged as a future
gap, not something to build now.

---

## Traceability between standing federation and episodic instances

**Definition:** `ReferralNetworkFederation` (standing, pre-existing) and
`ReferralEpisodeCommunity` (created, per-referral) are connected only
indirectly in `referral_scenario.el` — through `GPPracticeCommunity`, a
federation member whose own action emits the event that triggers the
episode's establishment. Nothing in either declaration references the
other directly.

**OPEN FINDING** — **Open question (Zoran, 2026-07-07):** federated networks of this kind
exist to reflect digital health business and regulatory arrangements
between providers — but there may need to be explicit traceability and
provenance between that static, standing arrangement and each dynamic,
episodic instance of it. A further question this raises: should an
episodic community be required to comply with the rules (invariants,
normative policies) of the standing federation — or even a single
standing community — it traces back to? Likely yes, but not certain, and
not something to force an answer to now. Zoran separately asked whether
this same question arises for a single pre-existing community (not a
federation) creating an episodic community — i.e., does
`justInTimeCommunity` need to comply with `e-commerceCommunity`'s own
rules?

**Standard:** Partial evidence, not a direct answer. §7.9.2 ("Policies
for federation") explicitly requires layered compliance for the
federation/domain case: "An enterprise object in the `<X>` federation
community shall conform both to the policies of the `<X>` domain
community to which it belongs and to the policies of the `<X>` federation
community" — and NOTE 1 there confirms standing and episodic layers can
run on separate lifecycles ("the policies for each domain community and
for the federation community may have separate life cycles"). This is
suggestive support for the general principle, but it is NOT stated for
the narrower single-community-creates-community case Zoran also asked
about — neither §7.3.2 nor the `justInTimeCommunity`/open-registry annex
examples (B.1.5.6-8) state whether the created community must comply
with its creator's own rules. Not found, not asserted by stretching
§7.9.2 to cover it.

**Toolchain status:** No mechanism exists for this today, structurally
or in the grammar, for either the federation case or the single-community
case.

**Decisions:** Logged for future consideration, deliberately not
resolved or built now — 2026-07-07.

---

## Naming conventions (Annex B precedent)

**Definition:** Both Annex B worked examples (e-commerce, library) follow
one consistent naming pattern, with no exceptions found: enterprise
objects/parties get plain, natural names (`e.com`, `e-system`, `customer`,
`supplier`); every community, without exception, carries a distinguishing
community-word (`e-commerceCommunity`, `purchasingCommunity`,
`shippingCommunity`, `warehouseCommunity`, `justInTimeCommunity`,
`ratingServiceCommunity`). Role names describe the FUNCTION a role plays,
not the class of thing filling it (`customer`, `supplier`, `auditor`,
`manager`, `catalogueServer`, `orderTaker` — never something like
"customerPersonRole").

**Standard:** Annex B.1.5.1-9 (e-commerce example); library example
(Case 5 and surrounding text).

**Toolchain status:** Adopted as house convention, 2026-07-07.

**Demonstrated in:** `referral_scenario.el` — three separate naming
decisions this session, each independently confirmed against this
precedent before being applied: (1) dropping the `Party` suffix
(`GPPracticeParty`→`GPPractice`, `SpecialistParty`→`SpecialistPractice`,
`PatientParty`→`Patient`) — matching the standard's own bare-object-name
convention; (2) keeping/adding the `Community` suffix consistently
(`GPPracticeCommunity`, `SpecialistPracticeCommunity` — the latter
corrected from `SpecialistCommunity` for symmetry) — matching the
standard's universal community-suffix convention; (3) shortening
`referringClinicianRole`/`referredToSpecialistRole` to `referringRole`/
`referredToRole` — matching the standard's function-not-filler role
naming. Note (2) required care: `GPPractice`/`SpecialistPractice` (party,
bare per rule 1) and `GPPracticeCommunity`/`SpecialistPracticeCommunity`
(community, suffixed per rule 2) necessarily have different names for
the same real-world organisation, since the grammar cannot merge a
`Community` and a `[EnterpriseObject]`-typed party into one declaration —
confirmed as a genuine, not cosmetic, naming collision avoided by the
convention, not created by it.

**Decisions:** Settled 2026-07-07, checked against the standard directly
rather than decided by feel — see the underlying discussion for each of
the three specific renames.

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

---

## Toolchain implementation priority sequencing (confirmed 2026-07-15)

Current confirmed order for remaining toolchain work, consolidating the
FHIR-mapping critical path with the AIVendor gap and later-stage items:

1. Encounter.status-driven token-state seeding (needs design pass: status→state
   mapping table, edge cases for `cancelled`/`entered-in-error`, explicit boundary
   against R30 Option B)

   **OPEN FINDING** — **Update 2026-07-15:** A probe-tier implementation now exists — see AM-39
   (commit `7699baa`). This wires the mechanism end-to-end for
   referralInitiationBurden specifically (Encounter.status=finished fires an
   event via the new Runtime.fire_event(), activating the burden), but does
   NOT implement the full status→state mapping design described above (all
   nine FHIR Encounter statuses, deadline computation, etc.). That full design
   remains outstanding under this item.
2. **OPEN FINDING** — R30 Option B (live grant/reinstate) — optional, deferred unless a demo
   narrative needs it
3. `FHIRConsentMapper` flat-community gap — fix shape undecided
4. EDOC24 Mediator write-back direction — larger scope
5. Kripke verifier `conditional_action` gap — captured in arXiv Limitations,
   not implemented
6. Board UI polish
7. **AIVendor gap** — three independent motivating cases now confirmed (health/FHIR
   EU AI Act provider/deployer split; Australian copyright/TDM policy; Pieter van
   Schalkwyk's N-peer-federation industrial case, commit `7a6484f`). Priority:
   just ahead of #8/#9, behind items 1–6 above.
8. Concurrent multi-episode runtime — production-readiness milestone, last in
   sequence among these
9. LLM-to-DSL translation pipeline Mode 2 — prerequisite: confirm
   `_build_obligation_descriptors()` fix has landed

---

## Event-triggered activation (Step 7c) — implemented but untested

**OPEN FINDING**

`el_engine.py`'s `advance()` Step 7c (AM-22, commit `18b243dd`, 2026-06-05)
performs real event-triggered token activation: when an Action's `emits`
matches a token's `triggered_by`, that token transitions to `active`.
The companion event-driven discharge path (Step 3's `event_discharged`,
same commit) is equally real. Both are original, untouched since authorship,
and confirmed still present via `git blame`. However: zero scenarios in
the repo currently pair a token's `triggered_by`/`discharged_by` with a
matching `emits` in a way that exercises either path with non-empty data
(the one `emits:` usage, `referral_scenario.el:392`, has no matching
`discharged_by`), and zero tests in `tests/` reference `triggered_by` or
`discharged_by` at all. Confirmed via direct grep + full test suite run
(45/45 passing, none touching this code). If future work builds on this
mechanism (e.g. item #1's Encounter.status gating), first tests for Step 3/7c
should be added as part of that work, not assumed correct from authorship alone.

**Status: PARTIALLY RESOLVED 2026-08-23.** The `triggered_by`/Step 7c side
is now resolved: AM-39 gave it a real scenario pairing
(`encounterConcluded` → `referralInitiationBurden` in
`referral_scenario.el`) and `tests/test_referral_event_triggers.py` now
covers it directly (10 tests: token activation on a matching event and
no-op on a non-matching one, `Runtime.fire_event()` transitioning a
pending burden to active plus its no-match case, Step 7c activation via
an action's `emits`, and four `handle_encounter_event()` cases covering
the finished-status activation path and its error/no-match branches).
The `discharged_by`/`event_discharged` side (Step 3) remains genuinely
untested — confirmed via grep, 2026-08-23: `discharged_by` appears only
in `grammar/v2/el_grammar.tx`, `toolchain/el_domain.py`,
`toolchain/el_parser.py`, `toolchain/el_engine.py`, and
`toolchain/el_kripke.py` — all grammar/engine/verifier code, zero
scenario files and zero tests anywhere in the repo. Do not treat this
finding as closed — half of it still needs the same treatment
`triggered_by` just got, whenever `discharged_by`/`event_discharged` work
is next picked up.

## Engine/Kripke event-model symmetry gap — undocumented, not deliberately designed

**OPEN FINDING**

`el_engine.py`'s event-triggered activation (Step 7c, AM-22, 2026-06-05) and
`el_kripke.py`'s `WAITING`/P6 cascade (commit `894afdbd`, 2026-06-13, logged
under AM-26/27 but the P6/WAITING logic itself was never given its own
amendment entry) both implement the same idea — a token/obligation waiting on
a named event before becoming live — using the same grammar fields
(`triggered_by`/`discharged_by`) but independent state models (`TokenInstance.state`
string vs. `ObligationState` enum) and independent code, built 8 days apart.
Neither amendment references the other. This is not confirmed as a deliberate
design choice — no commit message or amendments-log entry asserts intended
symmetry or explains the discrepancy. Worth keeping in mind for any future
work that touches either side: changes to one do not automatically apply to
the other, and there is currently no shared abstraction between them.

## Engine/Kripke unification — what a shared design would and wouldn't merge

Following up on the symmetry gap above: the operational/modal split itself
is legitimate and shouldn't be merged — `el_engine.py` models one concrete
`WorldState` advancing step by step (what actually happened); `el_kripke.py`
explores a branching reachability graph via BFS (what could happen, per
AF/EF). Collapsing those would blur the compelled-vs-detectable distinction
that's the paper's central finding.

What *did* diverge unnecessarily, and could be factored out without
threatening that split:

1. **A single canonical state vocabulary.** `TokenInstance.state` (plain
   string) and `ObligationState` (typed enum) are two independent
   representations of the same idea, bridged only by a hand-written
   ternary in `build_kripke_from_runtime()` — exactly the kind of seam
   where a case can silently go missing (see open question below on
   whether `WAITING` is ever actually reachable from that function).
2. **A single event-matching function.** `_activate_triggered_tokens()`
   (engine) and the Kripke P6a cascade both answer "given an event name,
   which tokens does it activate?" via two independently written
   implementations — one over live tokens, one over hypothetical
   `ObligationDescriptor`s. If the matching logic itself lived in one
   shared function, both layers could call into it and could not
   disagree about which tokens relate to which events; only how each
   layer *processes* that shared fact (commit vs. explore) would differ.

A from-scratch version might look like a shared module owning the state
enum and the trigger-matching function, with `advance()`/`fire_event()` and
the Kripke BFS step both built as thin layers over it — one committing to
a single transition per call, one exploring all reachable ones. The
anchoring function (`build_kripke_from_runtime()`) would then be closer to
a formality than a hand-maintained classification with room to drift.

**OPEN FINDING** — **Open question, not yet confirmed:** does `build_kripke_from_runtime()`
(the hybrid mode, anchored to a live runtime) ever produce
`ObligationState.WAITING`, or is `WAITING` only reachable from a separate,
pure spec-only world-builder that doesn't involve a runtime at all? If
the hybrid mode never produces `WAITING`, a pending→active transition via
`Runtime.fire_event()` would be invisible to that proof mode's output —
worth a targeted recon before relying on `Runtime.fire_event()` as any kind
of bridge between the two layers, which it currently is not.

Not scheduled — this is a forward-looking design note, useful the next
time either layer is touched, not urgent work.

## TokenGroup/any_discharged coordination semantics — Kripke-only, not enacted by operational engine

**OPEN FINDING**

Confirmed via direct grep (2026-07-16): `el_engine.py` contains zero
references to `TokenGroup`, `any_discharged`, or `SUPERSEDED` — and zero
imports of `el_kripke.py`/`el_domain.py` at all (stdlib-only dependencies
confirmed). The `TokenGroup`/`any_discharged`/`SUPERSEDED` coordination
semantics (AM-26/27, commit `894afdbd`, explicitly titled "coordination
semantics in Layer 4 Kripke verifier") exist only in the Kripke/
verification layer and the grammar — never in the live operational engine
that `coordination-simulator.html` actually calls (`get_available_actions`/
`execute_action` via `Runtime`).

**Practical implication:** if a `.el` scenario declares an `any_discharged`
`TokenGroup`, the Kripke layer can prove that one sibling's discharge
suppresses the others (SUPERSEDED) — but the live engine has no code path
that ever produces this suppression. A real running instance would let
every sibling burden sit independently dischargeable, indefinitely,
contradicting what the construct's name and the Kripke-side proof imply.

**Not yet checked:** whether any current `.el` scenario (referral,
ecommerce, consent, etc.) actually declares an `any_discharged`
`TokenGroup` — if one does, its live-demo behavior is currently silently
non-functional for this specific coordination guarantee.

**Relation to other findings this session:** a sharper, more consequential
instance of the operational/verification divergence documented in
"Engine/Kripke event-model symmetry gap" and
`docs/OPERATIONAL_VS_VERIFICATION_SEMANTICS.md` (commit `9b48284`) — not a
shared-but-inconsistent implementation (like triggered_by/Step 7c vs
WAITING/P6), but a construct implemented on only one side at all.

**Paper relevance:** directly relevant to the arXiv revision already
committed to reviewers (`reviewer_response.md`) distinguishing
specification-level verification from runtime-level enforcement — a
concrete, checkable example supporting exactly that qualification.
Candidate addition to the Limitations section. The already-submitted
workshop paper (`soea4ee26.tex`) makes no claims referencing
`TokenGroup`/`any_discharged`/coordination — confirmed via grep, zero
matches — so this finding does not affect its correctness.

Not scheduled for implementation — logging only. Checking current
scenarios for actual `any_discharged` usage is a reasonable next step
before any implementation decision.

**Status: RESOLVED 2026-08-23.** The core gap — the live engine having
zero `any_discharged`/`SUPERSEDED` handling — is resolved by AM-57
(`docs/el_grammar_amendments.md`): `el_engine.py` gained
`_build_group_index()`/`_build_any_discharged_groups()` (ported from
`el_kripke.py`) and a 7a-cont block in `advance()` that supersedes
`active`-state siblings in an `any_discharged` group when one member
discharges. Confirmed via grep, 2026-08-23: `el_engine.py` now contains
extensive `TokenGroup`/`any_discharged`/`superseded` references (group
indexing, the 7a-cont supersession block, and a `check_live_violations()`
comment confirming superseded burdens are already excluded).

This finding's own "Not yet checked" question — whether any current
`.el` scenario actually declares an `any_discharged` `TokenGroup` — is
now directly answered: `scenarios/specialist_pool/specialist_pool_scenario.el`
(commit `aa26e3a`, "AM-58"; not a grammar/domain/parser change, so
correctly absent from `docs/el_grammar_amendments.md` itself — documented
instead in `tests/test_specialist_pool_scenario.py`'s docstring) is
exactly that scenario, and its live-demo behavior is confirmed correct,
not "silently non-functional" as this finding originally warned it would
be. Independently re-verified against the real parsed model this
session, both checks passing: Q1, `EF(objective_satisfied:
OnCallConsultCommunity)` holds at the Kripke layer
(`test_ef_objective_satisfied_holds`); Q2, live discharge of
`specialistAResponseBurden` via the engine correctly transitions
`specialistBResponseBurden` to `superseded`, never violating
(`test_live_discharge_of_specialist_a_supersedes_specialist_b`).

**Paper relevance note carried forward, not resolved:** the "Paper
relevance" paragraph above proposed this gap as a candidate Limitations-
section addition to the arXiv revision. That gap is now closed, so the
proposed addition may need revisiting — flagging this for Zoran's
judgment, not editing `reviewer_response.md` or any paper file as part of
this doc-cleanup fix.

**Checked 2026-09-03 (design-chat session, against paper-draft files —
not part of this repository, so not independently re-verifiable from
here):** `reviewer_response.md`, `EDOC26_revision_notes.md`,
`EDOC26_revision_notes_consolidated_2026-06-26.md`,
`five_viewpoint_dsl_position_note.tex`, and `EDOC26final.tex` were
grepped for `any_discharged`/`SUPERSEDED`/`TokenGroup`/"collective
obligation" — zero matches in all five. The proposed Limitations-
section addition was never actually drafted into any paper file; it
existed only as an idea in this note. Since the underlying gap is
resolved (AM-57, `specialist_pool_scenario.el`), there is nothing stale
to correct. No paper file requires editing. (If those paper files are
ever brought into this repo, this claim should be re-verified with a
local grep rather than trusted from this note alone.)

---

## Amendments-log gap — AM-34 through AM-37 missing; dangling AM-34 reference

**RESOLVED 2026-08-23**

`docs/el_grammar_amendments.md` had no entries for AM-34 through AM-37 —
AM-33 was the last logged entry before AM-38 (which, per its own commit
96b7795, only ever touched `toolchain/fhir_mapping_table.md` and was never
meant to be logged here) and AM-39 (commit `7699baa`). Per CLAUDE.md's
Key Invariant #3 (every grammar amendment must be logged in
`docs/el_grammar_amendments.md`), this was a real, pre-existing gap.

Resolved by (a) merging AM-34 through AM-37's full content, verbatim,
from `docs/fhir_toolchain_amendments.md` into `docs/el_grammar_amendments.md`,
inserted in chronological order between AM-33 and AM-39; the companion
file is retained as a FHIR-toolchain-scoped index, not the sole source,
with a note added at its top pointing to the merge. And (b) re-checking
the dangling docstring reference this finding originally flagged in
`fhir_event_handler.py`: it turned out to already be fixed
independently — the docstring currently reads "Scope (rule numbers per
FHIR_ODP_EL_Positioning_Notes):" with zero AM-34 references (confirmed
via `grep -n "AM-34" toolchain/fhir_event_handler.py`, zero matches).

---

## `ObligationState.EXPIRED` — declared and priced but unreachable

**OPEN FINDING**: `ObligationState.EXPIRED` is declared in `el_kripke.py` and priced in the utility function (0.0, neutral) and world-labelling function ("expired"), but is never produced by any transition rule in the current Kripke world-construction code — it is a reserved-but-unreachable state. Comment at declaration site says "context no longer applies (actor left community etc.)", suggesting it's intended for future revocation/context-loss handling (connects to deferred R30 Option B — live Consent revocation via FHIR). Until wired into an actual transition, any paper/reviewer-facing description of the reachable state space for this scenario should state {PENDING, DISCHARGED, VIOLATED} as reachable and EXPIRED as reserved, not omit it or claim it's fully implemented.

---

## Layer 4 discharge has no negative preconditions; strict-mode AF may be structurally guaranteed

**OPEN FINDING**

Surfaced while adding a declared-vs-verified `discharge_mode` classifier to
a local verification-report script, using a probe scenario combining a
`strict` `Burden` with an `Embargo` on the same `for_action`, plus a
deadline-shrink test. The classifier expected two of its six branches —
`declaration_mismatch_not_compelled` and `declaration_mismatch_unreachable`
— to fire when a `strict` obligation doesn't actually verify as compelled.
Constructing a scenario to exercise them surfaced the following.

**CONFIRMED (verified by code read + empirical test):**

- Rule T1 (DISCHARGE) in `build_kripke_model()` is unconditional whenever an
  obligation is `PENDING` and its holder is `ACTIVE` — no `Permit`,
  `Embargo`, or other precondition gates it. Confirmed by code read (the
  transition-guard code at `el_kripke.py` lines ~1733–1783 checks only
  obligation state and holder `ActorStatus`; `requires_permit` and
  `inhibited_by_embargo` appear elsewhere in the file only in comments about
  an unrelated Authorization-resolution function,
  `find_governing_element_via_authorization`, never in transition-guard
  code) and by an empirical test: declaring an `Embargo` on the same
  `for_action` as a `strict` `Burden` had zero effect on the AF/EF result or
  on `worlds_explored`.

- Rule T3 (TICK) is blocked globally whenever any `strict`-mode obligation
  is `PENDING` with an `ACTIVE` holder (`el_kripke.py` lines ~1823–1828,
  `has_strict_pending_dischargeable`). Confirmed by code read and by an
  empirical test: shrinking a `strict` obligation's deadline to the
  parser's minimum (`_parse_deadline_steps`, 2 steps via `"1 second"`) had
  zero effect on the result — `w.step` cannot advance past `0` while such
  an obligation is outstanding, so Rule T2's deadline guard
  (`w.step >= desc.deadline_steps`) can never fire before T1 does,
  regardless of the declared deadline's value.

- `ActorStatus.INACTIVE` is declared as an enum member but never assigned
  to any world's `actor_states`, anywhere in the toolchain. Confirmed by a
  repo-wide grep for `ActorStatus`/`INACTIVE` across every `toolchain/*.py`
  module — the only file where either symbol appears at all is
  `el_kripke.py`. All three model-construction paths in that file
  (`build_kripke_model()`, the hybrid-mode `build_kripke_from_runtime()`,
  and the synthetic demo functions `_run_consent_scenario()` /
  `_run_hybrid_smoke_test()`) initialize every actor to `ACTIVE` and
  contain no transition rule that ever writes `INACTIVE`. The only other
  reference is a docstring block on `build_kripke_model()` describing a
  planned **"Rule T4 — REVOCATION"** (delegation revocation → holder
  `INACTIVE`, obligation reverts to the delegator), explicitly marked
  `(Not yet implemented — placeholder for hybrid mode.)`. Delegation
  revocation and Community-leave/`JoinLeaveEffect` grammar constructs are
  parsed elsewhere in the domain model but are not consulted by
  `el_kripke.py`'s actor-state handling.

**OPEN QUESTION (hypothesis, not a proven universal claim):**

Combined, these facts suggest that for any obligation with a
validator-passing `Commitment`, AF may be structurally guaranteed to hold
once declared `strict`, regardless of the obligation's actual structure —
which would mean the three "declaration mismatch" / "unreachable"
classification branches added to the verification-report script this
session are currently unreachable for any well-formed scenario. This has
NOT been exhaustively tested against every possible scenario shape (e.g.
multiple competing strict obligations, unusual Delegation/Community
structures) — flagged here as a hypothesis worth further investigation,
not a settled fact. Rule T4 (revocation), once implemented, would be the
most direct route to making the holder-inactive path — and therefore the
`declaration_mismatch_*`/`unreachable_obligation` branches — actually
reachable.

---

## `referralResponseBurden`'s accountability chain does not reach SpecialistClinician

**OPEN FINDING**

Surfaced while checking whether `referralResponseBurden`'s computed holder
resolves through the GP-to-specialist delegation chain
(`GPClinician` → `SpecialistClinician`) the way `referral_scenario.el`'s own
comments (lines 708–714) describe it. Verified by running
`build_kripke_model()` directly against `referral_scenario.el` and printing
`km.obligation_descriptors`.

**CONFIRMED FACT (verified by running `build_kripke_model` against
`referral_scenario.el` directly):**

- `referralResponseCommitment.by` = `GPPractice` (line 681).
- `gpToSpecialistDelegation.from` = `GPClinician` (line 716).
- `walk_chain()` starts from the Commitment's actor and only follows
  Delegation edges whose `from` exactly matches that name. Since
  `GPPractice != GPClinician`, the walk terminates at `GPPractice` — it
  never reaches `gpToSpecialistDelegation` at all. Confirmed by the printed
  descriptor: `referralResponseBurden` holder = `GPPractice`, chain =
  `['GPPractice']`.
- By contrast, `aiExaminationBurden` resolves correctly:
  `aiExaminationCommitment.by` = `SpecialistClinician` matches
  `specialistToAIDelegation.from` = `SpecialistClinician` exactly, and the
  printed descriptor shows the full two-hop chain: holder =
  `SpecialistAIAgent`, chain = `['SpecialistClinician',
  'SpecialistAIAgent']`. This confirms the chain-walk mechanism itself
  works correctly when actor names align — the gap is specific to the
  `GPPractice`/`GPClinician` naming mismatch, not a general defect in
  `walk_chain()`.

**OPEN QUESTION (not a prescribed fix):**

Which side is actually wrong is undecided:

- Should `referralResponseCommitment.by` name `GPClinician` instead of
  `GPPractice`?
- Should `gpToSpecialistDelegation.from` name `GPPractice` instead of
  `GPClinician`?
- Or is there a missing link between `GPPractice` and `GPClinician` that
  the model should represent explicitly (e.g. the practice standing behind
  its clinician), and both names are individually correct but
  disconnected?

The scenario's own comments at lines 708–714 describe
`gpToSpecialistDelegation` as "the TRUE referral delegation... GP
clinician delegates referral response and scheduling obligations to
specialist clinician — clinician-to-clinician, not
institution-to-institution." As things stand, that specific claim is not
backed by what the model actually computes: the burden this delegation is
meant to transfer (`referralResponseBurden`) is held by a Commitment naming
the institution (`GPPractice`), so the "clinician-to-clinician" framing is
narrative intent, not verified chain-walk behaviour.

---

## `escalationNoticeBurden` has no ObligationDescriptor — invisible to Layer 4

**OPEN FINDING**

Surfaced while checking whether every declared burden in
`referral_scenario.el` has a corresponding `ObligationDescriptor` in
`km.obligation_descriptors`, given that `_build_obligation_descriptors()`
was known to iterate `Commitment` elements only. Verified by running
`build_kripke_model()` directly against `referral_scenario.el` and
comparing the full set of declared burdens against
`km.obligation_descriptors.keys()`.

**CONFIRMED FACT (verified by running `build_kripke_model` against
`referral_scenario.el` and inspecting `km.obligation_descriptors`
directly):**

- `escalationNoticeBurden` is created only via `violation_response`
  `referralNoResponseViolation`'s `creates_burden` field (line 769) — no
  `Commitment` anywhere in the file creates it.
- `_build_obligation_descriptors()` (`el_kripke.py`) only ever iterates
  `Commitment` elements (`for c in _collect(model, "Commitment")`) — it
  never reads `ViolationResponse` at all.
- Confirmed empirically: `km.obligation_descriptors` has entries for all
  five Commitment-backed burdens (`referralInitiationBurden`,
  `referralResponseBurden`, `clinicalHandoverBurden`,
  `assessmentSchedulingBurden`, `aiExaminationBurden`) but NOT for
  `escalationNoticeBurden`.
- Practical consequence: `escalationNoticeBurden` is parsed and validates
  cleanly per the grammar, but is structurally absent from the Kripke
  model — invisible not just to AF/EF checks, but also to `utility()` and
  Bellman planning, since both only ever score obligations already
  present in `obligation_descriptors`. A burden created via a violation
  response can therefore never appear in an "optimal path" recommendation
  at all, not merely be scored low.

**OPEN QUESTION (not a prescribed fix — this is narrower than "who is
accountable," since the specification already answers that):**

The specification is not actually silent on who is accountable here:
`referralNoResponseViolation` already names `obligates: SpecialistPractice`
directly (line 767). So the open question isn't "who is this allocated
to" — the file already answers that — it's narrower:

- Should `ViolationResponse.obligates` + `.creates_burden` be treated as a
  second valid root by `_build_obligation_descriptors()`, functionally
  equivalent to a `Commitment`, without requiring any duplicated
  authoring?
- Or does genuine accountability grounding require a separate, explicit
  `Commitment` authored alongside every `ViolationResponse` that creates a
  burden — treating `ViolationResponse.obligates` alone as insufficient,
  even though it already names an actor?
- This may generalise beyond this one case: check whether any other
  grammar construct has a `creates_burden`-shaped field outside
  `Commitment` and `ViolationResponse`, since each would have the same
  blind spot.

**Cross-reference (2026-08-22):** AM-56 closes the Layer-2 side of this
same gap — `el_reasoner.py`'s `ultimate_accountability()` now treats
`ViolationResponse.creates_burden` as a fourth accountability root,
resolving `escalationNoticeBurden` to a real `AccountabilityChain` rooted
at `SpecialistPractice`/`SpecialistParty`. The Layer-4 gap described
above (`_build_obligation_descriptors()` in `el_kripke.py`, still only
iterating `Commitment`) is **unaffected and remains open** —
`escalationNoticeBurden` is still structurally absent from
`km.obligation_descriptors`, still invisible to AF/EF checks and Bellman
planning. `el_kripke.py` was deliberately not touched by AM-56. See
`docs/el_grammar_amendments.md`'s AM-56 entry.

---

## Governance-engine builder accountability gap

**OPEN FINDING (2026-08-10)**

No entry currently exists for who is accountable if the deployed
*governance engine itself* has a bug or bypass path — distinct from
whether the AI agent being governed was correctly specified/supplied.
Arguably more consequential than the AIVendor gap (see "AIVendor —
regulatory-overlay gap" entry, 2026-07-09/2026-07-14), since it concerns
trustworthiness of the verifier, not just the governed party.

At least two distinct failure modes, likely needing different remedies —
keep separate rather than collapsing into one "engine trust" line:

- **Verifier-logic failure**: a bug in Kripke transition
  construction/reasoning (`el_kripke.py`) produces an incorrect
  governance verdict despite correct scenario input.
- **Bypass-path failure**: the engine is logically correct but something
  in deployment (misconfiguration, an unenforced construct, an
  integration gap) allows an action to proceed without passing through
  governance at all.

**Status:** candidate/probe-tier, no design work started. Surfaced from
FTI Consulting conversation (2026-08-10, Sabine Bennett / Nicki Doyle)
discussion context, not FTI-specific in substance.

---

## Permit/Embargo missing domain scope (§7.8.8.2/§7.8.8.3 gap)

**OPEN FINDING (2026-08-10)**

Per ISO 15414 §7.8.8.2 and §7.8.8.3, Permission and Prohibition are each
*defined* as starting with "an authorization domain that prescribes the
[permission/prohibition]" — domain scope is intrinsic to what a Permit or
Embargo token *is*, not something borrowed from a wrapping construct.

Current grammar (`el_grammar.tx`) does not reflect this: `domain_scope`
exists only on `Authorization`, not on bare `DeonticToken` (which covers
burden/permit/embargo via shared fields). Permit and Embargo tokens
declared outside an `Authorization` wrapper currently carry no domain
scope at all.

This matters concretely, not just formally: §7.8.8.4 states plainly that
"Authorizations will not necessarily be effective outside the domain
controlling them. In federations, the effect of authorizations is
determined by the contract of the federation." Domain scope actively
gates whether a Permit/Embargo has force at all once a federation
boundary is crossed — it is not just descriptive metadata.

**Distinct from, and complementary to, `inhibited_by_embargo` /
`requires_permit_for` / `favoured_by_burden`:** those fields answer
"is this token blocked by another specific token" (grounded in
§7.8.8.4's "other restrictions that might prevent use of the permit").
`domain_scope` answers "is this token authoritative in the domain where
the action is being attempted" — a different question, currently
unaddressed for permit/embargo.

**Immediate practical consequence:** the T5 (Permit-occurrence) rule and
its Embargo guard, as currently scoped for `el_kripke.py`, use
`inhibited_by_embargo` token-to-token linkage and hold correctly only
*within a single domain*. They do not yet know what to do if a Permit
and the Embargo that would block it belong to different domains in a
federation — per §7.8.8.4, that case is federation-contract-determined,
and no federation-level authorization-conflict resolution exists in the
toolchain yet. T5 should be built and documented as single-domain-scoped
for now, not silently assumed to generalize.

**Status:** candidate/probe-tier, no grammar change proposed yet. Surfaced
during T5/Embargo-guard design discussion (2026-08-10), in the context of
the pre-existing federation domain-scope concern raised with Pieter's
industrial multi-agent case.

---

## Recommended vs. Compelled — undefined relationship (framing only)

**OPEN FINDING (2026-08-10)**

Surfaced during the FTI Consulting conversation (Sabine Bennett, Nicki
Doyle) while demoing the coordination-simulator's Bellman planner: there
is no formal statement of how the planner's "Recommended" action
(advisory, Q-value-based) relates to Compelled obligations
(`discharge_mode: strict`, architecturally enforced via T3-tick
suppression).

Two sub-questions, deliberately kept separate rather than treated as one:

1. **Does the planner even operate over Compelled obligations, or only
   Monitored ones?** A Compelled obligation isn't really a "choice" in
   the sense the planner is built to evaluate — `discharge_mode: strict`
   already forces action at first opportunity by construction, so a
   Q-value ranking over "whether/when to discharge" may not apply to it
   at all.

2. **If the planner does weigh in on a Compelled obligation, what is it
   actually ranking?** Candidate framing (untested, not yet designed):
   "Recommended" may simply be "the Q-value-optimal action *within* the
   already-constrained compliant action space" — i.e. Recommended and
   Compelled aren't competing categories where one might override the
   other; Recommended could be a refinement operating strictly inside
   Compelled's boundary. This framing avoids ever implying a Compelled
   obligation could be "recommended against."

**Status:** framing only, no design work started. This is distinct from
T5 (Exercise) and V-17, landed the same session — those gave Permit/
Embargo real Kripke semantics (EF/AG) but did not touch the planner's
relationship to `discharge_mode`. Flagged as highest-priority remaining
item from the 2026-08-10 FTI conversation, deferred to next session for
proper design treatment (chat, not CC) rather than rushed same-day.

---

## Recommended vs. Compelled — RESOLVED (2026-08-11)

Follow-up to the 2026-08-10 framing note above. Ground truth established
by reading `el_kripke.py` directly, not inferred.

**Finding 1 — `discharge_mode` doesn't affect valuation.** `utility()`
(el_kripke.py:649-708) and `bellman_values()` (900-966) never read
`discharge_mode`. A `strict` (Compelled) obligation is scored identically
to an `eventual` one at every state (+1.0 discharged / +0.3 pending /
-1.0 violated, weighted by `priority_weight`). `discharge_mode: strict`
only affects graph topology — it suppresses the T3 (Tick) edge, narrowing
`max(successors)` in the Bellman recursion to fewer candidates. There is
no certainty bonus, no special-cased reward — the "compulsion" is
structural (fewer branches), not a distinct value the planner assigns.

**Finding 2 — Permit-exercise (T5) is entirely utility-neutral.**
Confirmed by grep and by reading T5's world construction directly: T5
edges leave `obligation_states` unchanged (only `occurred_actions`
differs), and `utility()` is a pure function of `obligation_states`. So
`utility(w') == utility(w)` always, for any T5 edge. Nothing downstream
(T1's discharge guard) reads `occurred_actions` either, so a Permit's
exercise cannot even indirectly influence value via later obligation
outcomes, under the current implementation.

**Conclusion — the planner's silence on Permission is correct, not a
gap.** Burden and Permit answer different kinds of question:
- **Burden asks "ought this happen?"** — the planner has an opinion
  because deontic obligation semantics give it one to have. Compelled
  obligations participate in this ranking on identical terms to Monitored
  ones, just with a narrower choice set.
- **Permit asks "may this happen?"** — a modal possibility question
  (§7.8.8.2: "allowed to occur"), never an "ought." There is no normative
  pressure toward exercising a mere permission, so a value function with
  no opinion on it is faithful to what Permission actually means, not an
  oversight.

It is obligations — not permissions — that are the active drivers of
behaviour toward a community's objectives; permission and prohibition are
gates on what obligations may use to discharge, not independent sources
of directedness. This is the resting design position: **"Recommended" is
a Burden-only concept.** There is no competing category to reconcile it
against — the original framing question ("does a Compelled obligation's
discharge action always have to be the Recommended one," "does the
planner even weigh in on Compelled obligations") is dissolved rather than
answered by a new rule, once it's clear Compelled obligations were never
excluded from valuation in the first place.

**Left deliberately open, not a gap:** if a future scenario needs the
planner to have an opinion about *exercising* a Permit (e.g., "merely
permitted but strategically valuable to do now"), that would be a
genuine new extension — `utility()` would need to read `occurred_actions`,
which it structurally does not today — not a bug fix to this finding.
No such case identified yet (checked against the industrial/XMPro
context and IT-governance framing; neither surfaced one).

**Status:** resolved by direct code inspection, 2026-08-11. No
implementation change made or required — this closes the framing
question, it does not open new work.

---

## IT-governance demo — live consent-grant path required (R30 Option B), deferred for proper design

**OPEN FINDING (2026-08-11)**

Investigating what the IT-governance demo (originally motivated by the
2026-08-10 FTI conversation) would need to show surfaced three findings,
verified empirically against the live codebase and UI, not assumed:

1. **No live consent-grant path exists today.** The board UI's consent
   panel has only revocation buttons (`btn-revoke`, `btn-revoke-fhir`).
   `fhir_event_handler.py`'s R30 handling of `Consent.status: active` is
   explicitly bootstrap-only ("Option A") — a live `active` event received
   after runtime construction is a documented no-op
   (`fhir_event_handler.py:182-197`). No grant/activate endpoint exists in
   `el_api.py`. "Live grant/reinstate (Option B)" — already listed as
   deferred FHIR work — is the actual gap.

2. **Consequence: T5 already fires silently at `w0` in both live
   scenarios.** `patientRecordAccessPermitByAuthorization` is declared
   `state: active` statically in both `referral_scenario.el` and
   `gp_referral_scenario.el`, with `for_action` set and holder resolvable
   via `Authorization.to_agent`. Confirmed by building the Kripke model:
   `exercise:patientRecordAccessPermitByAuthorization →
   access_patient_clinical_records` is present in `w0`'s successors in
   both scenarios, since parse time — not something a demo or UI action
   triggers, it's simply always true today. Not a regression from T5's
   build (2026-08-10) — just the first time anyone looked.

3. **"6 iterations" paper claim is safe.** Comes from
   `_run_consent_scenario()`, a hand-rolled synthetic demo structurally
   incapable of ever touching T5 (never parses a real `.el` file, no
   Permits). Confirmed unchanged: still 6 iterations, 15 worlds. The
   pre-existing 30-vs-31-worlds discrepancy (see CONCEPTS_INDEX §13.2)
   is against `build_kripke_model()` on the real consent scenario — a
   different, already-tracked item, unrelated to and untouched by T5.

4. **No UI surface for `occurred_actions` exists anywhere** — confirmed
   by grep across both repos and by tracing `execute-action`'s response
   shape (`step`/`obligations`/`actors` only). Nothing to extend; this
   would be built from scratch.

**Decision (2026-08-11):** the IT-governance demo deserves the "live
grant → T5 fires → occurrence becomes reachable" story, not just a
static display of what's already true at `w0` — the transition is the
compelling part, especially for the FTI audience. That means R30 Option
B (live grant/reinstate) needs to be built first, as its own properly
scoped design item — same discipline as T5 (design in chat, precise spec
to CC, diff-by-diff review), not folded in as a rushed side effect of
"just build the demo."

**Not started.** Scope for the eventual design session should cover, at
minimum: the live grant endpoint (`el_api.py`), the `fhir_event_handler.py`
change to make a post-bootstrap `active` event a real transition rather
than a no-op, and the UI button/flow to trigger it — plus, separately,
the `occurred_actions` display surface needed regardless of which demo
shape is chosen.

**Priority:** next IT-governance-adjacent design session, whenever that
naturally falls — not blocking on FTI's calendar, since this is buildable
independent of any specific meeting date.

**Status update (2026-08-23):** item 4's "no UI surface... exists
anywhere" is no longer accurate. A witness-path panel was added to
computable-governance-ui's `coordination-simulator.html` (commit
`5782595`) — dropdown of propositions, chain rendering of the witness
path (worlds + edge labels), explicit UNREACHABLE state, consuming
`GET /kripke/witness`. This repo's own docs were never positioned to
track that repo's completion, which is why this went unflagged for a
while — noting it here since the finding's own wording made a
whole-system claim, not a this-repo-only one. Items 1-3, the "Decision,"
and the R30 Option B live-grant work below remain unaffected and still
open — this update is scoped to item 4 only.

---

## R30 Option B design blocked on a deeper gap: runtime events invisible to both Kripke builders

**OPEN FINDING (2026-08-11)**

Traced R31 (consent revocation) end to end before designing its mirror
(R30 Option B, live grant). The trace surfaced a structural gap larger
than "grant doesn't exist yet" — the desired demo narrative ("live event
→ T5 fires → occurrence becomes reachable," already flagged in the
2026-08-11 IT-governance-demo finding) is **not currently possible for
either grant or revoke**, under either Kripke build mode.

**R31 (revocation) itself works correctly, but only at the runtime/ledger
level.** `revoke_authorization()` (`el_engine.py:490-557`) correctly
mutates `Runtime._state` (permit → superseded, embargo → active,
copy-on-write via `with_tokens()`) and appends to `Runtime._ledger`.
Auditable via `GET /debug/tokens` and the FHIR-provenance side-dict in
`el_api.py`. AM-34's 6 tests (6/6 passing, confirmed just now) all assert
against `WorldState`/`TokenInstance` state or API response fields
directly — none of them build a Kripke model, import `el_kripke`, or
check an AF/EF verdict. This was never noticed before because nothing
had a reason to build a Kripke model right after a revocation and check
it.

**Why: neither Kripke builder can see a runtime event.**
- `build_kripke_model()` (spec-only mode, where T5 lives) reads
  `DeonticToken.state` off the *static parsed model* only
  (`_build_permit_descriptors`/`_build_embargo_holder_index`,
  `el_kripke.py:291,403`). Nothing writes runtime mutations back into
  the parsed `EnterpriseSpec` — confirmed no re-serialize/re-parse step
  exists anywhere in the codebase.
- `build_kripke_from_runtime()` (hybrid mode, the one that *does* read
  `runtime.current_state()`) only processes `kind == "burden"` tokens
  (`el_kripke.py:2304`). It never calls the permit/embargo descriptor
  builders and has no T5 — its own docstring documents Revocation as
  "Not yet implemented — placeholder for hybrid mode"
  (`el_kripke.py:1852-1856`).

So revocation (and by extension, any future grant) is real and correctly
enforced at the runtime layer, but currently unverifiable — AF/EF/
EF(occurred:...) cannot reflect it, in either build mode.

**Three options identified for closing this, not yet decided between:**
1. **Extend hybrid mode** to read Permit/Embargo state and generate a
   T5-equivalent edge from live runtime state — real new work, same
   category of effort as T5 itself (2026-08-10), deserves the same
   design-first treatment before implementation.
2. **Add a re-parse/re-serialize bridge** — translate live runtime state
   back into something `build_kripke_model()` can consume fresh after
   each event. No such step exists today; unclear yet whether this is
   simpler or harder than option 1.
3. **Rescope the demo** to two static before/after model builds rather
   than a live-response narrative — buildable without touching the
   runtime/Kripke bridge at all, but loses the "watch it respond in real
   time" story that was the compelling part of the IT-governance framing
   (2026-08-11 finding).

**Status:** not decided. This blocks R30 Option B from being scoped
precisely, since the right shape for "grant" depends on which of the
three paths above is chosen. Needs a proper design session (chat-first,
same discipline as T5), not a quick decision — deferred pending
availability of a longer working block.

**Related:** the `ObligationState.EXPIRED` "reserved but unreachable"
finding, already noting this general territory (runtime events not
wired into obligation-state handling) was anticipated but left unbuilt.

**Status: RESOLVED (2026-08-13).** Option 1 (extend hybrid mode) was chosen
and implemented as R30 Option B: live grant/reinstate, wired end-to-end
through Kripke verification — `reinstate_authorization()` (`el_engine.py`)
mirrors `revoke_authorization()` in reverse, `handle_consent_event()` routes
post-bootstrap `Consent.status: active` events to it instead of the old
no-op, and `build_kripke_from_runtime()`'s hybrid-mode T5 (from the
concurrent Stage 2 work) makes both grant and revoke verifiable via
AF/EF/`EF(occurred:...)`, closing the gap this finding raised. Full details
and the four-diff implementation record: `docs/session_summaries/2026-08-13_r30_option_b_and_cleanup.md`
(commit `7471d91`). 102/102 tests passing at landing time.

Confirmed live-verified against the running API on 2026-08-14: a stale
server process (running since 28 Jul, pre-dating this fix) was found still
serving the old bootstrap-only no-op behavior for `status: "active"` —
restarting it to pick up current code resolved this; `POST
/fhir/consent-events` with `status: "active"` now correctly returns
`action_taken: "reinstated"` (or `"already_active"`, idempotently) end to
end. Same session added a direct, non-FHIR counterpart,
`POST /authorizations/{authorization_name}/reinstate`, mirroring
`POST /authorizations/{authorization_name}/revoke`'s exact response shape
(`ReinstateAuthorizationResponse`, no `action_taken` discriminator — the
URL fixes the semantic, and empty-vs-non-empty `effects` carries the
already-active-vs-reinstated distinction, same as revoke's `effects` list
already does) — giving the board UI's consent panel genuine two-button
(direct + FHIR-event) symmetry for grant/reinstate, matching the existing
revoke pattern. Tests: `tests/test_reinstate_endpoint.py` (4 new: happy
path, idempotent already-active, 404 unknown authorization, 400 no
on_revocation embargo via throwaway fixture — the last of these also
closes out the pre-existing gap that `revoke_authorization_endpoint`'s own
400 branch had no test coverage anywhere in the suite, noticed while
mirroring it). 106/106 passing after this addition.

**Still open, unrelated to this finding:** the T5 label-collision finding
(logged the same day, immediately below) and the `occurred_actions` UI
display surface (2026-08-11 finding, above) are both real remaining gaps,
but neither blocks R30 Option B itself — this finding's blocking condition
is resolved.

---

## T5's edge labels silently collide when two Permits share a for_action

**OPEN FINDING (2026-08-13)**

Surfaced while writing Diff 4's revoke_authorization end-to-end test for
Stage 2 (hybrid-mode T5, building on the 2026-08-11 finding above).
Verified empirically against the real referral scenario, not inferred.

**Mechanism.** `patientRecordAccessPermitByRole` (held by
`SpecialistClinician`) and `patientRecordAccessPermitByAuthorization`
(held by `SpecialistAIAgent`) both declare the same
`for_action: "access_patient_clinical_records"`. `World` identity
(`el_kripke.py`'s `World` dataclass) is computed purely from the
resulting `(obligation_states, actor_states, occurred_actions, step)`
tuple — it carries no notion of *which* Permit caused a transition. So
from `w0`, both Permits independently compute the exact same successor
world `w'` (same resulting `occurred = {access_patient_clinical_records}`).
`edges[w0]` is a `Set[World]`, so the duplicate successor collapses
harmlessly — but `labels[(w, w')]` is a plain `Dict[Tuple[World, World],
str]` keyed only on the `(w, w')` pair, so the second Permit processed in
T5's loop (dict iteration order, which follows `state.tokens`/
`permit_descriptors` insertion order) silently **overwrites** the first
Permit's label. Confirmed directly: before revoking
`patientDataAuthorization`, only
`"exercise:patientRecordAccessPermitByAuthorization → ..."` survives in
`labels`, even though `patientRecordAccessPermitByRole`'s edge is
present and real in `edges` — its specific attribution is silently
dropped.

**Not a Diff 3 (hybrid-mode T5 port) bug.** The same `labels[(w, w')] =
label` pattern, with the same collision property, already exists
unchanged in `build_kripke_model()`'s (pre-exec) original T5 (2026-08-10)
— Diff 3 copied it verbatim, correctly. This is a pre-existing property
of T5's design in both build modes; it was never exercised by a test
before because no prior test had two Permits sharing a `for_action` from
the same reachable world. The referral scenario's real content happens
to have exactly that shape.

**Consequence.** `EF(occurred:<action>)` at the action level remains
correct regardless (it only asks "does the action ever occur on any
path," which doesn't depend on `labels`) — this is not an AF/EF
correctness bug. But anything that reads `labels` for
explainability/audit purposes (a witness-path display, an API surface
showing "which Permit satisfied this") could report the wrong Permit as
having enabled an action-occurrence, or fail to show that a second,
independent Permit also grants the same access. For a governance
toolchain whose value proposition rests on explainability, that's a real
(if narrow) gap, not cosmetic.

**Not fixed.** Logged only; Diff 4's revoke_authorization test works
around it by asserting on the specific `exercise:` label string rather
than a blanket `EF` query. A real fix would need `labels` (or an
equivalent structure) to support multiple attributions per edge — e.g.
`Dict[Tuple[World, World], List[str]]` — which touches every call site
that reads `labels[(w, w')]` as a single string (witness-path
construction, `_serialize_path` in `el_api.py`, etc.), so it's a
real-sized change, not a one-line fix.

**Priority:** low urgency — doesn't affect any AF/EF verdict, only
label/attribution fidelity when multiple Permits share a `for_action`.
Worth fixing before any UI surface is built that displays *which*
Permit/action-occurrence pairing satisfied a query (ties into the
"`occurred_actions` display surface" gap already noted in the 2026-08-11
finding above) — not before then.

---

## `Runtime.build_from_spec()` reads wrong attribute for `holds`-declared tokens

**OPEN FINDING (2026-08-13)**

`Runtime.build_from_spec()` (`el_runtime.py`) reads
`getattr(el, "tokens", [])` to auto-grant tokens declared via `holds` on
an `EnterpriseObject`/`party`, but the actual grammar/domain attribute is
`holds_tokens` — confirmed against `grammar/v2/el_grammar.tx:102` and
`el_domain.py:321`. Since `"tokens"` is never a real attribute on any
parsed element, `getattr(..., "tokens", [])` always returns the default
empty list, silently.

**Consequence:** `build_from_spec()` grants **zero** tokens for any spec
that declares them via `holds`, with no error, warning, or exception —
the resulting `state.tokens` is simply empty where it should contain
every statically-declared grant. A spec like:

```
party Operator {
    holds accessPermit
}
```

produces a `Runtime` whose `current_state().tokens` does not include
`accessPermit` at all.

**Discovered:** 2026-08-13, while building Stage 2's hybrid-mode T5 test
fixtures (`tests/test_hybrid_t5_exercise_embargo_guard.py`), mirroring
pre-exec T5's original minimal `_T5_FIRE`-style spec. The symptom was an
unexpectedly empty `state.tokens` and an `EF(occurred:...)` result of
`False` where `True` was expected for a trivially simple case.

**Workaround used, not a fix:** `el_kripke.py`'s own
`_run_hybrid_smoke_test()` already established the pattern — grant tokens
manually after construction via `grant_token(state,
token_from_spec(model, token_name, holder_name))`. Stage 2's tests reuse
this same pattern rather than fixing `build_from_spec()` itself, which
was out of scope for that work.

**Impact beyond Stage 2:** this affects any hybrid-mode scenario —
existing or future — that relies on `holds` for static token-granting via
`build_from_spec()`, not just test fixtures. Worth checking whether any
of the three registered scenario builders (`gp_referral`, `referral`,
`ereferral`) are also silently affected, or whether they all happen to
grant tokens through a different path (e.g. directly in Python, as
`ereferral`'s builder is already known to do for Burdens — see the
2026-08-11 ereferral coverage-gap finding) and so never hit this bug in
practice.

**Status:** RESOLVED (2026-08-13). Fixed as a one-line correction
(`"tokens"` → `"holds_tokens"`, `el_runtime.py`:104) once confirmed safe:
none of the three registered scenario builders (`gp_referral`, `referral`,
`ereferral`) route through `build_from_spec()` at all — each constructs
its `Runtime` directly (`Runtime(state, spec)`, `el_api.py:127,171,266`)
and grants tokens by hand in Python — so the fix cannot double-grant
anything in production. The one real dependency found was Diff 4's own
three minimal-fixture tests, which called `build_from_spec()` and then
unconditionally re-granted the same tokens as a workaround; confirmed via
direct simulation that landing the fix without touching them would have
produced duplicate `TokenInstance` entries. Those three tests were
updated in the same change to drop the now-redundant manual
`grant_token()` calls and rely on the corrected auto-grant directly. Full
suite green afterward (98/98, identical test set to before the fix).

---

## `holds` declarations on `EnterpriseObject` are dead code in `gp_referral`/`referral` scenarios

**OPEN FINDING (2026-08-13)**

Discovered while verifying the `build_from_spec()` fix (see the
`tokens`/`holds_tokens` finding above, RESOLVED same day): both
`gp_referral_scenario.el` and `referral_scenario.el` declare tokens via
`holds` directly on `EnterpriseObject`s — e.g. `agent GPClinician { holds
referralInitiationBurden; holds clinicalHandoverBurden }` — but these
declarations are currently **never honored**. `_build_gp_referral_runtime()`
and `_build_referral_runtime()` (`el_api.py:127,171`) each construct their
`Runtime` directly (`Runtime(state, spec)`) and grant every token by hand
in Python, never calling `build_from_spec()` — the only function that
would actually read these `holds` declarations.

**Consequence:** the `.el` file's `holds` declaration and the Python
builder's manual grant are two independent, currently-redundant sources
of truth for the same fact — token X is held by actor Y — and only the
Python one is live today. If someone edits a scenario's `holds`
declaration expecting it to change runtime behavior (a reasonable
assumption, since it's declarative and reads as authoritative), nothing
will happen; the Python builder's hand-written grant is what actually
governs. This is easy to miss silently, since both currently agree in
content even though only one is causally active.

**Not a bug in the sense of incorrect behavior today** — both sources
happen to agree, so nothing is currently wrong. It's a maintainability
trap: a latent inconsistency risk for whoever next edits either the `.el`
file or the Python builder without knowing the other exists.

**Relevant if:** a future scenario builder is written to call
`build_from_spec()` directly instead of hand-rolling grants (now that
`build_from_spec()` correctly reads `holds_tokens` per the same-day fix)
— at that point these `.el` declarations would suddenly become live,
which could either be the desired simplification or a surprise, depending
on whether the Python-side manual grants are removed at the same time.

**Status:** logged, no action planned. Worth revisiting only if/when a
scenario builder is refactored to rely on `build_from_spec()`.

---

## `conductAIExamination` has no enforced link to data-access authorization

**PARTIALLY RESOLVED — Layer 3 FIXED (2026-08-18); Layer 4 gap remains open**

Investigating a medico-legal question about patient data authorization
realism (see `docs/patient_authorization_and_obligation_delegation.md`,
"Patient Authorization and Clinical Obligation: Two Independent
Governance Mechanisms") surfaced that `aiExaminationBurden`'s discharge
action, `conductAIExamination`, is not actually coupled to
`patientRecordAccessPermitByAuthorization` at the engine or Kripke layer,
despite the natural real-world assumption that examining a record
requires having accessed it.

**Confirmed, by direct code read (`referral_scenario.el:635-641`,
`el_engine.py`, `el_kripke.py`):**

- `conductAIExamination`'s `precondition` field ("AI agent must hold
  patientRecordAccessPermitByAuthorization") is checked only as an
  exact-string match against a caller-supplied facts dict — self-asserted
  by whoever calls the API, not derived from the Permit's actual live
  state.
- The Action's `artefact: patientRecord` reference is parsed and stored
  but never read anywhere in `el_engine.py` — no record is fetched, no
  data is touched, nothing simulates accessing or analyzing content.
- `aiExaminationBurden` does not set `requires_permit_for` (confirmed
  dead code across the codebase, same as the `inhibited_by_embargo`
  finding earlier this week).
- At the Kripke layer, `conductAIExamination` can never appear in
  `occurred_actions` under any current rule — T5 only fires for action
  names that are some Permit's `for_action`, and `conductAIExamination`
  isn't one. `EF(occurred:conductAIExamination)` is not just unproven,
  it's structurally unreachable.

**Practical consequence:** today, revoking
`patientRecordAccessPermitByAuthorization` does not prevent
`conductAIExamination` from being called and successfully discharging
`aiExaminationBurden` — nothing in the engine checks live Permit state
against this precondition. "Reports findings back to the accountable
clinician," per the Action's description text, has no grammar construct
behind it at all (no `emits`, no `DeonticEffect`, no finding/report
object) — discharging the burden is, mechanically, just a token flipping
`PENDING`→`DISCHARGED`, gated by a self-asserted boolean.

**Why this matters beyond correctness:** this is the exact
clinical-safety-relevant coupling ("don't examine without
authorization") that a governance demo would most want to guarantee, and
it's currently unenforced — a materially more consequential gap than
some of today's other findings, since it touches the scenario's central
governance claim.

**Status:** Layer 3 (engine enforcement) FIXED 2026-08-18. Added
`requires_permit patientRecordAccessPermitByAuthorization for
aiExaminationRole` to `conductAIExamination` in
`scenarios/referral/referral_scenario.el`, mirroring the sibling action
`access_patient_clinical_records` in the same role — the typed
`[DeonticToken]` cross-reference mechanism, not a revival of the dead
`requires_permit_for` field. Activates `advance()`'s existing Step 6
check (`_actor_holds_permit`, `el_engine.py`); no engine or grammar
change was needed. `scenarios/ereferral/ereferral_model.el` was checked
separately and found to already have the equivalent
`requires_permit patientRecordAccessPermit` clause — a confirmation
comment was added there, no functional change.

The original candidate fix direction — routing through "whatever
mechanism `el_reasoner.can_perform()` already uses" — was superseded
before implementation once ground-truth checks (2026-08-18) confirmed
`can_perform()` reads static spec-level `holds_tokens`, not live
`WorldState`; see the `can_perform()` finding immediately below.

Verified by direct `advance()` calls against fresh, throwaway
`_build_referral_runtime()` instances (no state mutation left behind):
with the permit `active`, `conductAIExamination` succeeds and
discharges `aiExaminationBurden`; after `revoke_authorization`
supersedes the permit, the same call returns `outcome='blocked'`,
`reason="required permit 'patientRecordAccessPermitByAuthorization'
not held by actor"`, and the burden stays `active` (undischarged);
after `reinstate_authorization`, the call succeeds again. New
regression test: `tests/test_referral_ai_examination_permit_gate.py`
(3 tests) encodes all three cases. Full suite: 106 → 109 passed, zero
failures.

**Layer 4 gap remains open and is unaffected by this fix** — the
Permit token's own `for_action` is still `access_patient_clinical_records`,
not `conductAIExamination`, so T5 still cannot make
`conductAIExamination` appear in `occurred_actions`;
`EF(occurred:conductAIExamination)` remains structurally unreachable.
This finding is partially resolved, not closed.

**Correction (2026-08-19):** the "structurally unreachable" claim above
(both at the first bullet, "At the Kripke layer, `conductAIExamination`
can never appear in `occurred_actions`...", and again in "Layer 4 gap
remains open") was accurate at the time it was written — 2026-08-18,
before T6 existed. It is now stale: T6 landed later the same day, and
its discharge edge fuses the obligation-state change and the
action-occurrence into a single atomic transition —
`occurred:conductAIExamination` is now true on the exact same world,
via the exact same edge, as `discharged:aiExaminationBurden`. It is
reachable after all. Not rewritten in place, to preserve the historical
record of what was true at authorship — see "T6 fuses
`discharged:<burden>` and `occurred:<action>` onto the same edge —
confirmed 2026-08-19" (below) for the full finding.

---

## `can_perform()` has no live-facing caller — CONFIRMED NOT A GAP (2026-08-18)

Follow-up check prompted by the `conductAIExamination` finding above,
whose original candidate-fix direction assumed `el_reasoner.can_perform()`
was (or could stand in for) a live-Permit-state check. Ground truth
established by grep and direct code read, not inferred.

**Finding — `can_perform()` has zero real callers.** Grepped the whole
repo outside `el_reasoner.py`'s own definition: no code calls it. The
only references are documentation-provenance comments — three in
`el_kripke.py` (391, 394, 429, 2110) noting that T5's Kripke Embargo
guard was *built to mirror* `can_perform()`'s `held_token_names`
traversal, and one docstring line in
`tests/test_t5_exercise_embargo_guard.py:9-10` citing it by line number
to explain why that guard is actor-scoped. Neither imports or invokes
`el_reasoner`.

**Finding — the actual live-facing surface (`GET
/actors/{actor_name}/available-actions`, `el_api.py:492`,
`get_available_actions()`) does not call `can_perform()` either.** It is
a separate, independent implementation that reads
`_runtime.current_state()` directly — live `state.tokens`, filtered on
`tok.state == "active"` — and its own docstring says so explicitly:
"Reads directly from the current Layer 3 runtime state — no Kripke
model is needed for this endpoint." Its embargo handling mirrors
`el_engine.py` Step 5's logic against the same live token set, per its
own inline comment (lines 505-506).

**Conclusion — `can_perform()`'s static/spec-level scope is correct, not
a gap, because nothing live-facing depends on it.** Its own docstring
already self-discloses the scope ("static check against declared token
holdings... Runtime token state changes... are not modelled here — this
is structural, not operational") — that was documented accurately at
authorship; `get_available_actions()` was simply built as its own thing
afterward rather than layered on top of it. This is the inverse
situation from `conductAIExamination`: there, a live-facing action
lacked any live-state check; here, the one mechanism lacking a
live-state check has no live-facing consumer to expose it through.

**Status:** resolved by direct code inspection, 2026-08-18. No
implementation change made or required. Corrects the candidate-fix
pointer in the `conductAIExamination` finding above, which had assumed
`can_perform()` was reusable for a live check — it is not; the correct
reusable mechanism for that fix is `el_engine.py`'s `_actor_holds_permit()`
(reads `WorldState`, already exercised at Step 6), not `can_perform()`.

---

## T1 is blind to `requires_permit` — affects three Burdens, not one (pre-existing, latent since 2026-06-16)

**OPEN FINDING (2026-08-18)**

Full inventory across all three registered scenarios confirms T1
discharges any Burden unconditionally, with zero awareness of whether
that Burden's discharge Action carries a `requires_permit` clause. This
affects `referralResponseBurden`, `assessmentSchedulingBurden`, and
`aiExaminationBurden` — not just the `conductAIExamination` case fixed
today. Two of the three were already correctly gated at Layer 3
(engine, `advance()` Step 6) since these scenarios were first authored
(`gp_referral_scenario.el`, 2026-06-16); only the Kripke/Layer 4 side
(T1) has always been blind to it. Not introduced by today's fix — a
pre-existing gap this work surfaced while scoping the T6 design.

**Consequence for T6's design:** T6 must be a general rule (detect "does
this Burden's Action have a `requires_permit` link" as a property), not
a `conductAIExamination`-specific carve-out. T1 must correspondingly
exclude any Burden whose Action carries this link, deferring those
cases to T6 — otherwise the ungated T1 edge remains reachable in the
Kripke model regardless of what T6 adds.

Full inventory table: `docs/kripke_transition_rules_reference.md`,
"Known gap" section.

**Status:** T6 implemented 2026-08-18, across four diffs:
`_build_permit_requirement_index()`, T1's exclusion check, T6 itself in
`build_kripke_model()` (spec-only), and T6 ported to
`build_kripke_from_runtime()` (hybrid). Verified via exact `AF`/`EF`
values (full pytest suite, 109/109 passing) and a 7-case regression
check confirming the five ungated actions are unaffected.

**Correction (2026-08-18):** the verification plan predicted world/edge
counts would *increase* once T6 landed ("T6 adds new reachable
worlds"). Measured against a true pre-diff baseline (scratch mirror of
the last committed `el_kripke.py`), counts *decreased* in every
scenario/mode checked instead — e.g. `referral_scenario.el` hybrid mode
went from 639/1515 worlds/edges to 472/1340.

**Retraction (2026-08-18):** this note originally claimed the decrease
"does not affect correctness," citing exact `AF`/`EF` values, the full
pytest suite, and the ungated-action regression check as independent
confirmation. **That claim is withdrawn — it was checked only against
`referral_scenario.el`, the one scenario today's tests exercise in
hybrid mode, and does not hold in general.** A same-day follow-up
investigation found two real problems the original note missed
entirely:

1. `ereferral_model.el`'s "unchanged" world/edge count is not evidence
   for the interleaving-fusion hypothesis below — T6 is completely
   inert in that scenario (confirmed via a byte-identical before/after
   graph hash), so nothing was fused or removed. See "T6/T1-exclusion
   silently inert for scenarios without Commitment/Delegation-backed
   burdens" below.
2. `gp_referral_scenario.el`'s larger reduction is not explained by
   interleaving-removal alone — one of its two gated Burdens
   (`assessmentSchedulingBurden`) is now genuinely unreachable
   (`EF` flipped `True`→`False`), a real regression this note
   incorrectly characterized as harmless. See "T6's same-holder
   requirement causes a genuine unreachability regression" below.

The interleaving-fusion hypothesis (fusing discharge and occurrence
into one atomic T6 transition removes a combinatorial ordering degree
of freedom the old two-step path allowed) may still be *part* of the
explanation for `referral_scenario.el`'s reduction — still not traced
or proven — but it is not the complete, or even primary, explanation
across the three scenarios, and "correctness independently confirmed"
should be read as applying only to `referral_scenario.el`, the one
scenario where it was actually checked.

---

## Permit granted via role-level `holds` is invisible to spec-only `permit_descriptors` (pre-existing, exposed by T6)

**OPEN FINDING (2026-08-18)**

Discovered while verifying Diff 3 (T6) against `verify_gp_referral.py`
(targets `gp_referral_scenario.el` via `build_kripke_model()`, spec-only
mode): Q2/Q3/Q4 `EF` checks remained `FAIL` even after T6 landed. Traced
to the root cause — not a T6 bug.

`patientRecordAccessPermitByRole` is granted via `holds
patientRecordAccessPermitByRole` **inside `role specialistRole`'s
body** (`gp_referral_scenario.el:354`), transferred at community join
via `on_join specialistRole transfer patientRecordAccessPermitByRole`
(line 348) — not via an `EnterpriseObject.holds_tokens` declaration,
and not via any `Authorization`. `_extract_permit_structure()` (which
`build_kripke_model()`'s `permit_descriptors` is built from) has only
two holder-resolution tiers — `EnterpriseObject.holds_tokens` and
`Authorization.to_agent` — neither of which covers a permit granted
structurally to a *Role* and transferred on join. So this permit never
appears in `permit_descriptors` in spec-only mode at all; T6's
`all_active` check correctly (given the data available to it) reads
that as "not active" and refuses to fire.

**Pre-existing, not introduced by T6:** this has always affected T5 too
in spec-only mode — T5 has never been able to generate a spec-only
occurrence edge for `access_patient_clinical_records` via
`patientRecordAccessPermitByRole`. It was invisible until now because
nothing needed to query `permit_descriptors` for this permit before T6
existed; T1's old unconditional discharge never consulted
`permit_descriptors` at all.

**Does not affect hybrid mode:** `build_kripke_from_runtime()`'s
`permit_descriptors` reads directly from live `state.tokens`, bypassing
`_extract_permit_structure()`'s tiered resolution entirely.
`el_api.py`'s `_build_referral_runtime()` (line 260) and
`_build_gp_referral_runtime()` (line 122) both explicitly grant
`patientRecordAccessPermitByRole` to `SpecialistClinician` at runtime
construction — so hybrid-mode T6 consumers should not hit this gap
(prediction as of logging; Diff 4 will confirm directly).

**Status:** logged, not fixed. Out of scope for the current T1/T5/T6
diff sequence. A future fix would need a third resolution tier in
`_extract_permit_structure()` — role-level `holds` +
`on_join ... transfer`, mirroring the existing
`EnterpriseObject.holds_tokens`/`Authorization.to_agent` tiers — or an
explicit decision that spec-only mode doesn't need to support this
permit-granting mechanism at all.

---

## T6/T1-exclusion silently inert for scenarios without Commitment/Delegation-backed burdens (`ereferral_model.el`, confirmed 2026-08-18)

**OPEN FINDING (2026-08-18)**

Root cause: `_build_obligation_descriptors()` only builds an
`ObligationDescriptor` for a Burden that appears in at least one
`Commitment` or `Delegation` (per its own docstring).
`ereferral_model.el` has zero `commitment`/`delegation` declarations
anywhere in the file — confirmed by grep. So
`_build_obligation_descriptors()` returns an empty dict for this entire
scenario. In `build_kripke_from_runtime()`'s per-token loop
(`el_kripke.py` ~line 2467-2477), when
`spec_descriptors.get(tok.token_name)` is `None`, the fallback branch
sets `for_action = None` unconditionally, regardless of what the
Action's grammar declaration actually says.

Consequence: T1's exclusion check (`if desc.for_action and
desc.for_action in permit_requirement_index`) never triggers when
`for_action` is `None` — every Burden in this scenario, including
`aiExaminationBurden` (which IS gated by `requires_permit
patientRecordAccessPermit`), still discharges unconditionally via T1,
exactly as before any of today's T6 work. T6's own guard (`if not
desc.for_action or ...`) skips for the same reason — T6 never fires
here either.

Confirmed empirically, not inferred: `km.labels.values()` contains zero
`examine:` edges for `ereferral_model.el`'s hybrid-mode Kripke model;
`discharge:aiExaminationBurden by SpecialistAIAgent` is still present.
The before/after graphs (pre-diff scratch mirror vs. current) are
byte-identical — same sorted label multiset, same SHA-256 hash
(`36cb86d486e4a1a0`) — confirming zero behavioral change, not "T6
correctly found nothing to change."

**Open design question:** should hybrid mode's `for_action` resolution
be loosened to not depend on `_build_obligation_descriptors()`'s
Commitment/Delegation-only scoping? That function's narrow scope is
deliberate for the fields it was originally built to serve (deadline,
discharge_mode, chain, etc. — all genuinely tied to accountability-chain
structure), but `for_action` is a different kind of fact (which Action
discharges this Burden, per `favoured_by_burden`) that doesn't obviously
need the same Commitment/Delegation gate. A Burden activated via a
different mechanism (e.g. `effect activate`, as `ereferral_model.el`
uses for `aiExaminationBurden`) can still have a perfectly
well-defined `for_action` via the structural `favoured_by_burden`
search (`_find_action_for_burden`) — hybrid mode just never calls it in
the fallback branch today. Not scoped or designed here.

**Status:** logged, not fixed. Any future scenario built without
Commitment/Delegation declarations (as a matter of style, not error)
will silently bypass T6 the same way.

---

## T6's same-holder requirement causes a genuine unreachability regression: `assessmentSchedulingBurden` in `gp_referral_scenario.el` (EF True→False, confirmed 2026-08-18)

**OPEN FINDING (2026-08-18)**

Confirmed by direct comparison: in `gp_referral_scenario.el`'s live
runtime (`_build_gp_referral_runtime()`), `assessmentSchedulingBurden`
is held by `SpecialistParty` (per its `Commitment`: `by: SpecialistParty
... creates_burden: assessmentSchedulingBurden`), while the Permit its
discharge Action requires, `patientRecordAccessPermitByRole`, is held
by `SpecialistClinician` (per the live grant in
`_build_gp_referral_runtime()`). Different actors.

T6's `all_active` check requires `permit_descriptors[p].holder ==
desc.holder` — an exact same-actor match, mirroring T5's actor-scoped
Embargo guard precedent. Given the mismatch above, T6 correctly (per
its own stated logic) refuses to fire for this Burden. But T1 is now
excluded from handling it too (`for_action` correctly resolves to
`'scheduleAssessment'`, correctly found in `permit_requirement_index`)
— so **no rule can discharge this Burden at all**. Confirmed directly:
`check_permission("assessmentSchedulingBurden").satisfied` is now
`False`, where before today's T6 work it was `True` (T1 discharged it
unconditionally, with no permit check at all). This is a genuine
regression in provable governance behavior, not a neutral side effect.

**Why this wasn't caught today:**
`tests/test_referral_kripke_t6_permit_gate.py` and
`tests/test_referral_kripke.py` both build only `referral_scenario.el`
in hybrid mode — where the equivalent Burden
(`assessmentSchedulingBurden`, held by `SpecialistClinician`, matching
its Permit's holder exactly) correctly retains `EF=True`.
`gp_referral_scenario.el`'s hybrid-mode `AF`/`EF` values were never
independently asserted by any test added today; `verify_gp_referral.py`
(the only existing check against this scenario) runs in spec-only mode,
which has its own, separately-logged permit-resolution gap and was
already known-failing before this was found — masking this second,
distinct problem from view.

**Open design question:** should T6 allow "held by anyone in the Burden
holder's principal/delegate chain" (e.g. `SpecialistParty` as principal
of `SpecialistClinician`, matching how `principal_of`/`delegated_from`
already model this relationship elsewhere in the grammar), rather than
requiring the exact same actor? Or is the exact-match requirement
correct, and `assessmentSchedulingBurden`'s Commitment actor
(`SpecialistParty`) is itself the thing that should change (e.g. the
Commitment or a Delegation should transfer accountability down to
`SpecialistClinician`, matching how `referralResponseBurden` is
explicitly delegated in this same scenario)? Not resolved here — a real
modeling question, not just an engine bug.

**Status:** logged, not fixed. Confirmed regression, not yet decided
whether the fix belongs in T6's guard logic or in the scenario's own
Commitment/holder structure.

---

## Delegation holder/chain resolution is a coincidental text-match, not a real design — affects up to nine Burden/scenario rows (2026-08-18)

**OPEN FINDING (2026-08-18)**

Follow-up to the `assessmentSchedulingBurden` regression above, tracing
the mechanism before scoping a fix. Finding, confirmed by reading the
actual code rather than assumed: **the delegation-holder resolution
that appears to work for `referralResponseBurden` is not a real
delegation-following design at all — it is a coincidental text-match.**

`_build_obligation_descriptors()`'s first pass (`el_kripke.py:1601-1653`)
resolves a Burden's holder via `walk_chain()`, which extends the chain
from a Commitment's actor only when a Delegation's `obligation:` text
substring-matches (`obl_text.lower() in oblt.lower()`) the walk's
current text. It never reads `transfers_burden` or
`transfers_token_group` at all — confirmed by grep, zero references to
either field anywhere in `el_kripke.py`. `referralResponseBurden`'s
chain extends correctly only because `referralResponseCommitment`'s
`obligation:` string happens to exactly equal
`gpToSpecialistDelegation`'s `obligation:` string. Hybrid mode's
equivalent function, `_delegation_chain_for_token()`
(`el_kripke.py:2388-2403`), is a real back-link walk (not text
matching) but checks only `d.burden` (the `transfers_burden` field) —
never `d.token_group` — so any Burden reachable only via
`transfers_token_group` (not individually named by `transfers_burden`
on any Delegation) never gets chain-extended there either. Both
functions have the same blind spot for group-transferred Burdens, by
two different routes.

**Scope, checked directly, not assumed:** every Burden in both
`referral_scenario.el` and `gp_referral_scenario.el` is named in
`gpToSpecialistDelegation`'s `transfers_token_group`, and every one of
them already has its own `Commitment` — meaning the "may not have a
Commitment" fallback path documented on
`_build_obligation_descriptors()`'s second pass never actually runs for
any Burden in either scenario. Spec-only resolved holders, full table:

| Scenario | Burden | Spec-only holder | Live/intended holder | Match? |
|---|---|---|---|---|
| `referral_scenario.el` | `referralInitiationBurden` | `GPPractice` | `GPClinician` | no |
| `referral_scenario.el` | `clinicalHandoverBurden` | `GPPractice` | `GPClinician` | no |
| `referral_scenario.el` | `referralResponseBurden` | `GPPractice` | `SpecialistClinician` | no |
| `referral_scenario.el` | `assessmentSchedulingBurden` | `SpecialistPractice` | `SpecialistClinician` | no |
| `referral_scenario.el` | `aiExaminationBurden` | `SpecialistAIAgent` | `SpecialistAIAgent` | yes |
| `gp_referral_scenario.el` | `referralInitiationBurden` | `GPPracticeParty` | `GPClinician` | no |
| `gp_referral_scenario.el` | `clinicalHandoverBurden` | `GPPracticeParty` | `GPClinician` | no |
| `gp_referral_scenario.el` | `referralResponseBurden` | `SpecialistClinician` | `SpecialistClinician` | yes |
| `gp_referral_scenario.el` | `assessmentSchedulingBurden` | `SpecialistParty` | `SpecialistParty` | yes |

7 of 9 rows mismatch between spec-only resolution and the live/intended
holder — the text-match mechanism is broadly unreliable, not a
narrow problem specific to `assessmentSchedulingBurden`.

**Checked directly: a naive fix (always override with the Delegation's
`delegate`) would be actively wrong, not just incomplete.** In
`gp_referral_scenario.el`, `gpToSpecialistDelegation`'s sole `delegate`
is `SpecialistClinician` — a naive "second pass always wins" fix would
reassign `referralInitiationBurden` and `clinicalHandoverBurden` to
`SpecialistClinician`, when their correct, live-granted holder is
`GPClinician` — these two Burdens were never meant to be delegated at
all; the GP keeps them. In `referral_scenario.el`, this problem is
worse than "pick the wrong actor": the scenario has **multiple
delegates** across its delegation structure (at least
`SpecialistClinician` and `SpecialistAIAgent` found), so "the naive
override target" isn't even a single well-defined actor without first
correctly matching each Burden to the specific Delegation whose
`token_group` actually names it — a naive fix has no unambiguous target
to fall back on in that file at all.

**Status:** logged, not fixed. **A proper fix needs its own design
session — not something to attempt in the current session.** It needs
per-Burden correctness, not a blanket guard removal or unconditional
override: which Delegation (when more than one exists) governs which
Burden, and confirmation that Burdens with no governing Delegation at
all (`referralInitiationBurden`, `clinicalHandoverBurden`) are left
untouched. Candidate fix shapes were sketched in the investigation that
led to this finding (extend `_delegation_chain_for_token()` to also
check `token_group` membership; loosen T6's exact-holder match to
chain-membership) but are not decided or scoped here.

---

## T6 (Examine) has no Embargo guard — discharges a gated Burden even while a same-actor Embargo blocks the action — RESOLVED (2026-08-19)

**OPEN FINDING (2026-08-19), RESOLVED same day**

T5's Exercise rule has an actor-scoped Embargo guard (via
`embargo_inhibition_index`/`embargo_holder_index`, verified against
`el_reasoner.can_perform()`, 2026-08-18). T6 (Examine) — introduced
2026-08-18 alongside T1's exclusion — never inherited this guard. Its
`all_active` check was limited to `permit_descriptors.get(p) is not None
and permit_descriptors[p].holder == desc.holder`; no call to either
embargo index anywhere in T6's block, in either build mode.

**Confirmed via a minimal running test, not inferred:** a fixture where
an actor holds both an `active` Permit and an `active` Embargo blocking
the same action (`inhibited_by_embargo` on the Action, same actor) —
T6 discharged the gated Burden anyway. Witness path:
`examine:testBurden → doTheThing` fired in the world where the Embargo
was active.

**Fix:** ported T5's existing actor-scoped Embargo guard verbatim into
T6's block, in both `build_kripke_model()` and `build_kripke_from_runtime()`
— same `embargo_inhibition_index.get(desc.for_action, [])` /
`embargo_holder_index` lookup, same-holder/`active`-state check, `blocked`
→ `continue` before the discharge edge is created. No new mechanism;
reused the indexes T5 already builds and that were already in scope.

**Regression tests added:** `tests/test_t6_examine_embargo_guard.py`
(pre-exec, `build_kripke_model()`) and
`tests/test_hybrid_t6_examine_embargo_guard.py` (hybrid,
`build_kripke_from_runtime()`), each with the same-holder-suppresses /
different-holder-does-not-suppress pair mirroring
`test_t5_exercise_embargo_guard.py`'s pattern.

Building the hybrid-mode fixture surfaced a second, narrower thing worth
recording: `build_kripke_from_runtime()` sources its obligation
descriptors by iterating `runtime.current_state().tokens` (live
WorldState), not the spec's `Commitment`s directly. A Burden declared
only via `commitment ... creates_burden:` with no `holds` clause on any
`EnterpriseObject` never reaches `state.tokens` via
`Runtime.build_from_spec()`'s auto-grant, and is silently invisible to
hybrid mode — `obligation_descriptors` comes back empty for it, and any
EF/AF query against it reads `False` for the wrong reason (no obligation
exists), not because a guard fired. Caught before it produced a
vacuously-passing test: the first version of the hybrid fixture (without
`holds gatedBurden`) passed the same-holder case and failed the
different-holder case, both for this reason rather than the guard.
Fixed in the test fixtures by adding `holds gatedBurden`, not in
`el_kripke.py` — this is a pre-existing hybrid-mode/`Runtime.build_from_
spec()` characteristic, not part of the Embargo-guard bug, and out of
scope for this fix. Worth knowing before building any other hybrid-mode
Burden fixture from a bare `Commitment`.

Full suite: 117 passed (113 pre-existing + 4 new), zero regressions.

---

## Delegation holder/chain resolution — Option B investigation reveals three compounding problems, not one (paused, 2026-08-19)

**OPEN FINDING (2026-08-19)**

Follow-up to last night's finding ("Delegation holder/chain resolution
is a coincidental text-match"). Attempted Option B (extend, don't
replace, the resolution mechanism) — investigation revealed the problem
is deeper than the original design anticipated. Pausing here; the fix
needs its own dedicated design session, not continued same-day work.

**Three separate, compounding problems found, each independently
confirmed:**

1. **`transfers_token_group` conflates two unrelated purposes with no
   distinguishing field.** `referralBurdenGroup` is simultaneously (a)
   the community objective's `all_discharged` satisfaction target and
   (b) (per Delegation's `transfers_token_group` field) an apparent
   delegation-transfer group — but its actual membership serves purpose
   (a) only in practice; nothing in the grammar or data distinguishes
   "these Burdens are delegated together" from "these Burdens together
   satisfy the episode objective." Both files' `referralBurdenGroup`
   includes `referralInitiationBurden`/`clinicalHandoverBurden` — the
   two Burdens that must never be reassigned — alongside the Burdens
   that should be.

2. **No discriminator over `Commitment.actor`/`Delegation.delegator`
   cleanly separates "should extend" from "must not reassign."** Tested
   `actor == delegator` directly against both scenario files: fails in
   *opposite* directions. In `gp_referral_scenario.el`, it's a false
   positive (fires true for the two Burdens that must not move, since
   `GPPracticeParty` both commits and delegates directly — no
   institution/individual split in this file). In `referral_scenario.el`,
   it's a false negative on the one Burden it most needs to catch
   (`referralResponseBurden` — which has an explicit, unambiguous
   `transfers_burden` link, no group-membership involved at all — because
   the Commitment is made by `GPPractice`, the delegation is from
   `GPClinician`, and no other discriminator was found that bridges
   this correctly across both files' differing accountability shapes).

3. **`walk_chain()` only ever follows `Delegation` elements — never
   `principal_of`.** `referral_scenario.el`'s `GPPractice → GPClinician`
   link is declared as a bare `principal_of` relationship (by design —
   `party GPPractice { principal_of GPClinician }`, with an explicit
   scenario comment noting there is deliberately no reciprocal
   `delegated_from`, since `GPClinician` is independently accountable).
   `walk_chain()` structurally cannot cross this link at all, regardless
   of text-matching, `transfers_burden`, or `transfers_token_group` —
   confirmed directly: the walk never reaches `del_graph["GPClinician"]`
   starting from `GPPractice`. This means `referralResponseBurden` in
   `referral_scenario.el` cannot be fixed by anything discussed so far
   (Parts 1/2 of the Option B design, or any discriminator over
   Commitment/Delegation fields) — a `principal_of`-bridging mechanism
   would be needed, which is a separate, larger design decision (should
   `principal_of` be walkable at all? If so, under what conditions,
   given it's explicitly *not* meant to imply the same accountability
   transfer a `Delegation` does?).

**Two scenario files also confirmed to have genuinely different
accountability shapes**, not just different data: `referral_scenario.el`
has an institution/individual split (`GPPractice` commits,
`GPClinician` delegates, connected only by `principal_of`);
`gp_referral_scenario.el` collapses these into one actor
(`GPPracticeParty` both commits and delegates directly). Any single
discriminator has to work correctly across both shapes, which is part
of why every attempt so far has failed in opposite directions per file.

**What was confirmed safe and unaffected, before pausing:**
`dataclasses.replace()` compatibility for `ObligationDescriptor` (plain
dataclass, no blockers) — this remains valid groundwork for whichever
fix direction is eventually chosen. Part 1 of the original Option B
design (`_delegation_chain_for_token()`'s `token_group` extension, hybrid
mode) was confirmed mechanically safe against current data — but only
because the walk is holder-anchored and one-directional, not because
group membership itself was ever a safe signal, per the original
design's now-disproven safety claim. Not implemented — held pending the
same design session as everything else here, since implementing Part 1
alone while Parts 2/3 remain unresolved would leave the two build modes
asymmetric.

**Also noted, from the same-day discussion that led to pausing here:**
a Kripke-model/delegation-chain visualizer (graphical trace of worlds,
transitions, and accountability links) was independently identified as
a priority two separate times this week (2026-08-18 during T6's
world-count investigation, 2026-08-19 during this investigation) —
both times, the actual debugging work was done through dense
grep/table-output archaeology that a visual graph would likely have
shortened substantially. Not scoped here; noted as motivation for
prioritizing it.

**Status:** paused, not fixed. Needs its own dedicated design session
covering, at minimum: (a) whether `principal_of` should be walkable by
`walk_chain()`/`_delegation_chain_for_token()` and under what
conditions; (b) how to disambiguate `transfers_token_group`'s dual
purpose (objective-satisfaction vs. delegation-transfer), likely
requiring a grammar-level or convention-level fix, not just an engine
change; (c) whether the fix needs to handle `referral_scenario.el` and
`gp_referral_scenario.el`'s differing accountability shapes via one
unified mechanism or scenario-aware logic. `assessmentSchedulingBurden`
in `gp_referral_scenario.el` (yesterday's original regression) remains
unfixed.

---

## T6 fuses `discharged:<burden>` and `occurred:<action>` onto the same edge — confirmed 2026-08-19

**FINDING (2026-08-19)**

T6's `_make_world` call atomically transitions both the obligation state
(`PENDING` → `DISCHARGED`) and `occurred_actions` (adding the gated
action) in one edge — not two separate edges the way pre-T6 discharge
and T5 exercise were. Consequence: for any T6-gated Burden/action pair
(e.g. `aiExaminationBurden`/`conductAIExamination`), the two
propositions `discharged:aiExaminationBurden` and
`occurred:conductAIExamination` become true on the exact same world,
reached via the exact same edge — they are not independently
reachable/unreachable; checking either one via `EF` yields the same
witness path.

**Confirmed 2026-08-19** by reading T6's code directly and running it
(`extract_witness_path`/`GET /kripke/witness`), not something previously
recorded as a verified claim — worth being explicit about that
provenance, since it corrects a claim made earlier the same day (see
correction below).

See the correction appended to the `conductAIExamination` finding
(above) for where the original "structurally unreachable" claim was
made and corrected.

**Practical consequence:** either proposition string can be used
interchangeably to query T6-gated reachability going forward, though
`discharged:<burden>` is the one with prior test coverage
(`tests/test_referral_kripke_t6_permit_gate.py`) and should remain the
default choice absent a reason to prefer `occurred:<action>` specifically.

---

## T1 lacks Embargo-awareness — a Burden gated only by `inhibited_by_embargo` (no `requires_permit`) would discharge unconditionally

**OPEN FINDING (2026-08-19)**

T1's exclusion check (`if desc.for_action and desc.for_action in
permit_requirement_index: continue`) only excludes a Burden if its
Action has a `requires_permit` clause. It does not check
`embargo_inhibition_index` at all. T6's own entry condition uses the
same `permit_requirement_index` key, so an Action gated *only* by
`inhibited_by_embargo` (no `requires_permit`) would be excluded by
neither T1 nor T6 — nothing guards it, and T1 would discharge the
Burden unconditionally, ignoring an active, same-holder Embargo
entirely.

**Structurally identical to the gap fixed this morning** (T6 missing an
Embargo guard T5 already had) — same underlying pattern, third instance:
Permit/Embargo-awareness has had to be added piecemeal to T5, then T6,
and now T1 is confirmed to have the analogous hole.

**Confirmed real via direct empirical test**, not just inferred from
reading the code: a minimal probe (Burden → Action with
`inhibited_by_embargo` only, active same-holder Embargo, no
`requires_permit`) shows T1 firing unconditionally in both build modes —
`EF(discharged:gatedBurden) = True` despite the active Embargo.

**Currently latent, not live:** zero Actions in any registered scenario
use `inhibited_by_embargo` at all — confirmed via repo-wide grep. This
also means, worth noting separately: **the Embargo-guard machinery built
this week (T5's guard, this morning's T6 port) has never actually fired
against real scenario data** — every test exercising it uses a
throwaway probe spec, not `referral_scenario.el`/`gp_referral_scenario.el`/
`ereferral_model.el`. `patientRecordAccessEmbargo` exists in real
scenarios only as a token materialized via `on_revocation`, never wired
to any Action's `inhibited_by_embargo` clause.

**Status:** logged, not fixed — no live instance to break yet. Candidate
fix, once needed: extend T1's exclusion to also check
`embargo_inhibition_index` (mirroring the `permit_requirement_index`
check), and extend T6's entry condition similarly, so an
embargo-only-gated Action is correctly excluded from T1 and picked up by
some future embargo-aware rule (T6 itself, if generalized, or a new
rule) rather than falling through unguarded to either.

---

## Double role-enrollment bug (GET /actors/SpecialistClinician/available-actions) — actually a double-grant, root cause traced to yesterday's paused delegation finding, fixed 2026-08-20

**OPEN FINDING (2026-08-20), RESOLVED same day**

Coordination simulator showed duplicate `scheduleAssessment` cards for
`SpecialistClinician`. Investigation (not `enroll()` called twice, not a
role assigned twice — `SpecialistClinician` filling two roles
concurrently, `specialistRole` + `referredToRole`, is by design and
confirmed harmless since `get_available_actions()` derives entirely from
`state.tokens`, never role names) traced the real cause to **two
independent mechanisms both granting `referralResponseBurden`/
`assessmentSchedulingBurden` to the same holder**:

1. `_build_referral_runtime()` (`el_api.py`) pre-seeds both burdens to
   `SpecialistClinician` directly at tick 0.
2. `initiateReferral`'s grammar `effect create ... to referredToRole`
   (`referral_scenario.el:425-426`) unconditionally grants a second,
   field-for-field identical `TokenInstance` when the action fires
   (`el_engine.py`'s `create` op, Step 7b).

Confirmed both `acknowledgeReferral` and `scheduleAssessment` duplicated
identically (same root cause, same effect block, same pre-seed loop) —
not just the one action visible in the screenshot. Confirmed the
duplication is Layer-3/API-only: `build_kripke_from_runtime()` builds
its `descriptors` dict keyed by `tok.token_name` (`el_kripke.py:2608`),
so duplicate raw tokens collapse before any world/edge is constructed —
world/edge counts were never affected.

**Why the pre-seed exists — traced, not assumed:** it is the *only*
mechanism that gets `SpecialistClinician` recorded as these two burdens'
holder in the Kripke hybrid-mode layer. `_build_obligation_descriptors()`
itself reads only the parsed spec (`Commitment`/`Delegation`/
`DeonticToken`), never `WorldState.tokens` — but `build_kripke_from_runtime()`
never falls back to it for a burden absent from live `state.tokens`;
that spec-only path was tested directly and resolves the holder to
**`GPPractice`**/**`SpecialistPractice`** respectively, not
`SpecialistClinician` — because `walk_chain()` can't cross the
`GPPractice`→`GPClinician` `principal_of` link and has no
`Delegation.obligation` text match for `assessmentSchedulingBurden` at
all. This is the identical gap logged and paused yesterday in
"Delegation holder/chain resolution — Option B investigation reveals
three compounding problems, not one (paused, 2026-08-19)" (problem 3,
the `principal_of`-walkability question). The pre-seed in
`_build_referral_runtime()` is a working-around-the-gap necessity, not
redundant leftover code — removing it was tested directly and confirmed
to break `tests/test_referral_kripke.py::test_referral_response_is_detectable_not_compelled`,
`test_assessment_scheduling_is_detectable_not_compelled`, and
`tests/test_referral_kripke_t6_permit_gate.py`'s `referralResponseBurden`
permission check (all three currently pass; removal was not applied).

**Fix applied** (the reverse of removing the pre-seed): an idempotency
guard in `el_engine.py`'s `create` effect handler — skip granting if the
target already holds a `TokenInstance` of that name, per-target, scoped
inside `op == "create"` only (the separate `clone` op, which
intentionally adds a second copy, is untouched). Checked against every
`effect create` site in the repo (5 total, across `consent_scenario.el`,
`referral_scenario.el`, `gp_referral_scenario.el`) — confirmed the guard
only ever fires for the two sites that actually had a pre-existing
duplicate-grant conflict; the other three are unaffected since nothing
else pre-seeds those tokens. Also fixed the same bug in
`gp_referral_scenario.el`'s `referralResponseBurden` (identical shape,
`specialistRole` resolves to `SpecialistClinician`, same as the pre-seed
holder).

**Left deliberately unfixed, a distinct bug surfaced by this
investigation:** `gp_referral_scenario.el`'s `assessmentSchedulingBurden`
does *not* get deduped by this guard — its pre-seed holder
(`SpecialistParty`, `_build_gp_referral_runtime()`) differs from the
`create` effect's resolved holder (`SpecialistClinician`, via
`specialistRole`). These are two genuinely different-holder token
instances, not a duplicate, so the idempotency guard correctly leaves
both in place. This is a wrong-pre-seed-holder bug, not a duplication
bug — worth its own investigation, not addressed here.

A display-layer dedupe (by action name, first-occurrence-wins) was also
added to `get_available_actions()` in `el_api.py` as defense in depth,
before the root cause was traced — confirmed lossless (the two entries
were byte-for-byte identical on every field `AvailableAction` exposes)
and left in place after the engine-level fix, since it's a harmless
safety net for any future create-effect/pre-seed overlap of this shape.

Full suite: 121 passed, zero regressions, after both fixes.

---

## Live violation triggering — detection mechanism exists and is tested; wiring to `on_violation_of` effects is the actual gap

**OPEN FINDING (2026-08-20)**

Investigating the "blocked until violation" label on the Escalation
Notice witness-path option (yesterday's finding: `escalationNoticeBurden`
permanently unreachable, no code path fires a violation) surfaced a more
precise picture than originally assumed.

**What already exists and works, confirmed by direct trace:**
`_violation_entry()` (`el_engine.py`) is a real, tested deadline-check —
compares an obligation's declared deadline against current time, flags
`VIOLATED` when passed. Exercised by existing tests. This is not
missing.

**What's actually missing:** nothing currently *consumes* a detected
violation to fire the corresponding `on_violation_of` effect.
`referralNoResponseViolation`'s effect (creating `escalationNoticeBurden`
when `referralResponseBurden` is violated) is declared in the grammar
but never wired to `_violation_entry()`'s output — detection and
effect-firing are disconnected. This is a narrower gap than "build
violation detection from scratch": the hard part already exists and is
tested; the missing piece is the wiring step, structurally similar to
how `create` effects already fire from actions.

**Two open design questions, not yet decided:**
1. **Trigger mechanism** — should violation-checking fire automatically
   on every `/advance` call, or require an explicit action/endpoint
   (e.g., a "check deadlines" control)? The coordination simulator has
   no time-advancement UI today, so an explicit trigger may be the more
   demoable and honest-to-the-model choice — makes visible *when* the
   check happens, rather than silently occurring on unrelated calls.
2. **Escalation semantics** — should the escalation Burden's creation be
   fully automatic the moment a violation fires, or should it become a
   new available action on the escalation target's role (something the
   actor must discover and then act on)? Real semantic choice about
   what "escalation" means in this model, not just an implementation
   detail.

**Status:** logged, not designed or implemented. Deliberately sequenced
after this session's holder-resolution/double-grant fix, and — per
2026-08-20 discussion — prioritized *ahead of* the cosmetic UI pass
(Escalation Notice wording, usage instructions), since the wording fix
depends on knowing whether this becomes real or stays permanently
unreachable by design.

**Correction (2026-08-20, same day) — the "already exists and is tested"
claim above is wrong; retracted.** Before starting the wiring design,
a ground-truth check was run against this finding's own claim.
`_violation_entry()` does not exist anywhere in the codebase — confirmed
by direct grep across every file in `toolchain/`, zero matches. There is
no function by that name, and no equivalent under another name either:

- `el_engine.py` documents its own absence of this feature, rather than
  omitting it by oversight — Step 1's docstring (module header, lines
  8-9) reads *"identify tokens past deadline (informational; real clock
  requires caller to manage tick-to-deadline mapping)"*, and the Step 1
  comment in `advance()` (line 212) reads *"caller to inspect but does
  not auto-violate here."*
- Grepped every assignment of `"violated"`/`'violated'` across
  `toolchain/*.py`: the only two hits are the field comment declaring
  `TokenInstance.state`'s valid enum values (`el_engine.py:38`, never
  assigned to) and `el_kripke.py:2574`, which only *reads*
  `tok.state == "violated"` if a caller had already set it — nothing
  upstream ever does.
- Grepped `outcome="violation"` / `outcome='violation'`: zero hits in
  `el_engine.py`. `TransitionRecord.outcome` is documented as
  `'ok' | 'blocked' | 'violation'`, but `'violation'` is never actually
  produced by any live code path — the same declared-but-dead-enum-value
  pattern as `TokenInstance.state == 'violated'`.

**What actually exists:** deadline→VIOLATED logic is real, but lives
entirely inside `el_kripke.py`'s Kripke world-expansion BFS (roughly
lines 2016-2185 and 2658-2659), e.g. `if w.step >= desc.deadline_steps:
... ObligationState.VIOLATED`. This walks the *model checker's own*
internal `step` counter within a bounded horizon, generating a
hypothetical future world where an obligation goes VIOLATED if not
discharged in time — built for AF/EF verification (is there a path /
are all paths eventually violating), not for observing the actual live
`WorldState`. It has no tick-to-wall-clock mapping and no connection to
the live `Runtime` or ledger. **Live violation detection against the
running system does not exist at all.**

**New open design question this surfaces, not yet decided:** should
live violation detection be **tick-based** (reusing/extending the
Kripke model's own `step` counter and `deadline_steps` semantics — the
existing verification-layer vocabulary) or **wall-clock-based**
(matching how deadlines are actually written in scenario text, e.g.
`referralResponseBurden`'s `"5 working days from referral receipt"`,
`escalationNoticeBurden`'s `"48 hours from violation detection"`)?
These are materially different designs — tick-based reuses existing
machinery but has no real-world time meaning outside the verifier;
wall-clock-based matches the scenario authors' intent but requires
building a deadline-string-to-real-time parser that doesn't exist
today (`_parse_deadline_steps()` in `el_kripke.py` parses these same
strings into an abstract step count for the Kripke horizon only, not
into any real-world duration).

**Consequence for the `ViolationResponse` wiring work logged in this
same finding:** that work is now blocked on this being designed and
built first, not merely on a wiring step on top of an existing
detector. **Deferred, same category as** "Delegation holder/chain
resolution — Option B investigation reveals three compounding
problems, not one (paused, 2026-08-19)" — a real gap surfaced mid-design,
needing its own dedicated session, not continued same-day work.

**Resolved (2026-08-20):** `check_live_violations()` implemented in
`el_engine.py`, wrapped by `Runtime.check_live_violations()` in
`el_runtime.py`, exposed via `POST /check-violations` in `el_api.py`.
Resolves both open questions from this finding: tick-based (not
wall-clock), explicit trigger (not automatic on `advance()`). Reuses the
relocated `_build_obligation_descriptors()`/`_parse_deadline_steps()`
two-tier deadline lookup (see relocation note below) — the same logic
`build_kripke_from_runtime()` already used, not reinvented. Scope:
`discharge_mode: eventual` burdens only; `discharge_mode: strict` burdens
are explicitly excluded, since treating them as violatable on elapsed
time would fabricate an enforcement guarantee that does not exist live
(see the separate, still-open `discharge_mode: strict` finding). This is
the first live code path to produce `TransitionRecord.outcome ==
"violation"` — previously a documented but never-produced value.

Tick advance on this endpoint is conditional, not unconditional like
other engine mutations — a deliberate exception so repeated no-op polling
during a demo doesn't silently erode other Burdens' deadlines. See
`check_live_violations()`'s docstring for the full reasoning.

**Relocation performed as part of this work:** `ObligationDescriptor`,
`_parse_deadline_steps()`, and `_build_obligation_descriptors()` moved
from `el_kripke.py` (Layer 4) into `el_engine.py` (Layer 3);
`el_kripke.py` now imports all three back. Corrects the layering
direction (Layer 4 depending on Layer 3, matching how it conceptually
already worked) rather than duplicating deadline-bucket logic or
inverting the dependency. Confirmed no circular import. 29/29
`el_kripke.py`-specific tests passed on the relocation alone, before
`check_live_violations()` was added.

**9 new tests** (5 engine-level in `tests/test_check_live_violations.py`,
4 endpoint-level in `tests/test_check_violations_endpoint.py`). Full
suite: 135/135, zero regressions (baseline 126/126).

**Still open, deliberately out of scope for this work:** `discharge_mode:
strict` live enforcement (separate finding, unaffected); wiring detected
violations to `ViolationResponse`/`on_violation_of` effects
(`referralNoResponseViolation` grammar already confirmed correct — see
the design spec above — this is the next step, not done here).

---

## `discharge_mode: strict` — enforcement exists only in the verifier, not the live runtime — OPEN FINDING (2026-08-20)

**Status: OPEN, not fixed. Surfaced as a side effect of the violation-detection
ground-truth check, not the original target of that check.**

The paper's central formal claim (EDOC26final.tex, reviewer_response.md) is
that `discharge_mode: strict` is a **runtime enforcement mechanism**: "the
runtime governance engine enforces this by blocking time advancement when a
strict obligation is actionable — a constraint on actual agent behaviour...
not a modelling stipulation." This language was written specifically to
answer a reviewer's concern that strict mode might merely stipulate the
desired conclusion at the modelling layer rather than constrain real
behaviour.

**Confirmed today, by direct grep of `el_engine.py` and `el_runtime.py`
(not inferred): this claim does not hold in the current implementation.**

- `discharge_mode` is read and copied through unchanged in every code path
  (e.g. `_transition()`, `el_engine.py:112-119`) — never branched on.
  Zero conditional logic anywhere in `el_engine.py`/`el_runtime.py` checks
  `discharge_mode == "strict"`.
- `WorldState.tick` advances unconditionally at the end of every `advance()`
  call (`el_engine.py:406`) and identically in `revoke_authorization()` /
  `reinstate_authorization()` (lines 558, 654, 687) — no check anywhere for
  a pending strict obligation on an active holder before advancing.
- The only real tick-suppression logic lives entirely inside
  `el_kripke.py`'s BFS world-expansion (~line 2196-2218): it governs whether
  a tick-edge is added between *hypothetical* worlds during AF/EF
  verification. It has no connection to live `WorldState.tick` or any
  `advance()` call.

**Net effect:** today, an actor can call unrelated `advance()` actions
repeatedly while a `strict` burden sits PENDING and actionable on them, and
nothing in the live system stops it or flags it — `discharge_mode: strict`
currently only guarantees AF holds inside the *verifier's model* of the
system, not in the deployed system itself.

**Same architectural shape as two other findings this week** (today's
double-grant bug; the live-violation-detection gap) — verifier-only logic
assumed, without checking, to also govern live runtime behaviour. This one
is more consequential than either: it is the mechanism the paper's central
formal contribution and the reviewer-response commitments rest on.

**Scope note:** does not affect `referralResponseBurden` /
`assessmentSchedulingBurden` specifically (both confirmed `discharge_mode:
eventual` — see the separate live-violation-detection finding), since
strict-suppression wouldn't apply to them even if live-enforced. This
finding is about the `strict` mechanism generally, wherever it's declared
across any scenario.

**Not fixed today — deliberately deferred**, pending an explicit decision
on urgency (implement live tick-suppression in `el_engine.py` before this
is visible to any external audience, vs. log precisely and schedule
separately). Cross-reference: this finding is independent of and does not
block the in-progress eventual-mode live-violation-detection/
`ViolationResponse`-wiring design work.

**Urgency resolved (2026-08-20):** does not change urgency for
`EDOC26final.tex` / `reviewer_response.md` — both still drafting, not yet
submitted. The reviewer-response document's existing prepared language
("Full operational assurance additionally requires that the governance
engine is faithfully deployed, which is an important open problem we
acknowledge as future work") already anticipates this exact gap; fold this
finding in as a concrete instance of that caveat when finalizing
`reviewer_response.md`.

**Convergence with live-violation-detection design (2026-08-20) — bucket-collision RESOLVED 2026-08-29, see below:**
attempting to design the trigger mechanism for live violation detection on
`referralResponseBurden`/`assessmentSchedulingBurden` (both `discharge_mode:
eventual`) surfaced that this finding's tick-vs-wall-clock ambiguity is not
abstract — it is the actual, concrete blocker.

Confirmed empirically: there is currently no way, by any method, to
determine how much time has elapsed since a specific burden was granted.
`TokenInstance` (`el_engine.py:32-43`) has no "granted at" tick/timestamp
field. `WorldState.tick` is a single global counter with no per-token
reference point. `build_kripke_from_runtime()` is structurally
forward-looking (`w0.step` is always 0 regardless of live `WorldState.tick`
— `el_kripke.py:2102`), so it can answer "would this violate N hypothetical
ticks from now" but not "has this already violated, given real elapsed
time." `_parse_deadline_steps()`'s own docstring
(`el_kripke.py:1441-1457`) confirms its step-bucket mapping is
"necessarily approximate," intended only to preserve relative ordering for
verification — not to represent real elapsed time. Confirmed concretely:
`referralResponseBurden` (5-day deadline) and `assessmentSchedulingBurden`
(14-day deadline) both map to the identical bucket value (8), despite
having different real deadlines.

**This is a missing data model, not an implementation-detail choice
between two working options.** Two open questions must be decided together,
in one dedicated design session — not piecemeal:
1. Does `TokenInstance`/`WorldState` need a real "granted at" reference
   field before any live elapsed-time comparison is possible?
2. Is that reference tick-based (count of `advance()` calls since grant —
   consistent with the paper's own tick-based formal model, T1/T2/T3, and
   with how `discharge_mode: strict`'s AF guarantee is already proven in
   tick-steps) or wall-clock-based (would require a real duration parser,
   which does not exist today — `_parse_deadline_steps()` is a coarse
   verification-time bucket mapping, not a duration parser)?

**RESOLVED (2026-08-29) — the identical-bucket-value claim, specifically.**
Questions 1 and 2 above were already settled by later, separately-logged
work under "Live violation triggering..." earlier in this same
`discharge_mode: strict` section's timeline: `check_live_violations()`
(`el_engine.py`) is tick-based and `TokenInstance` does now carry a real
`granted_at_tick` field — this doc entry had simply not been updated to
say so. What remained genuinely unresolved after that work was exactly the
sentence above: the *bucket-collision* itself, empirically confirmed live
via a CC investigation (`CC_INVESTIGATION_premature_violation.md`,
2026-08-29) that reproduced the referral-board-view.html "Assessment
Scheduling violates at the same tick as Referral Response" symptom against
the running server and root-caused it to `_parse_deadline_steps()`
matching only the unit word, never the leading magnitude.

Fixed the same day in `_parse_deadline_steps()` (`toolchain/el_engine.py`):
now extracts the leading number adjacent to the unit word and multiplies
it by that unit's existing per-unit step value, instead of using the flat
per-unit bucket unconditionally. `referralResponseBurden` ("5 working
days") → 40 steps; `assessmentSchedulingBurden` ("14 days") → 112 steps —
proportional to the real 14/5 = 2.8x ratio, no longer identical. A
magnitude-less deadline string (e.g. a word-form magnitude, or a bare unit
word with no digit) still falls back to the original flat bucket,
unchanged.

Regression-checked, not just diffed: full suite was 213/213 before this
change; added 10 new tests locking in the fix
(`tests/test_parse_deadline_steps.py`, including the magnitude-1 case
matching the original flat-bucket value exactly, so the two existing
`check_live_violations()`/endpoint tests that hardcode `deadline_steps ==
5` for `"1 hour"` stay correct); 223/223 after, zero regressions. Then
re-verified live against the running `referral` scenario server (not just
unit-tested): Reset → `initiateReferral` → repeated `/advance-clock` →
`/check-violations` now shows `referralResponseBurden` violating at tick
41 ("elapsed 41 >= deadline 40 steps") while `assessmentSchedulingBurden`
stays PENDING until tick 113 ("elapsed 113 >= deadline 112 steps") — the
two burdens no longer violate together.

Known, disclosed (not hidden) consequence of the fix: `deadline_steps`
also gates the Kripke verifier's Rule T2 (`el_kripke.py`, `w.step >=
desc.deadline_steps`) within the default horizon (10,
`el_api.py:_KRIPKE_HORIZON`). A large multi-day `deadline_steps` (e.g.
112) now exceeds that horizon, so the verifier can no longer witness a
`"violate:<burden>"` transition for such a burden within the default
horizon-bounded search — it could before this fix, at the old flat value
of 8. Checked directly: no test in the suite asserts EF/AF over a
`"violate:"` proposition (grepped), and discharge reachability (Rule T1)
is unaffected since it fires independently of `deadline_steps` at any
step — so this doesn't regress anything today, but a future scenario
wanting "eventually witnessed as violated within N steps" for a
long-deadline eventual Burden would need a larger horizon, not a further
change to this function.

**Companion, smaller decision surfaced in the same session:** wiring a
proper `Action` declaration for `notify_gp_of_non_response` (held by
`SpecialistPractice`) is separately blocked — `Action` only exists in the
grammar as a `RoleBodyItem` nested inside `Role`
(`grammar/v2/el_grammar.tx:543-593`), and `SpecialistPractice` is declared
as a bare `party` that fills no `Role` anywhere in `referral_scenario.el`
(confirmed by grep). A scenario-authoring decision — which `Role`, in
which community — is needed before this Action can be declared. Should be
resolved alongside the grant-tick design session, since both block the
same feature (live violation detection + response wiring for the referral
scenario).

**Resolved (predates this note's own "Status: deferred" line, never
back-filled):** commit `5572b69` (AM-46) added `practiceOversightRole`
to `SpecialistPracticeCommunity` specifically so `SpecialistPractice`
fills a `Role` and `notify_gp_of_non_response` could be declared as a
real `Action` — the exact blocker this paragraph describes. Confirmed
via `git log -S`. This paragraph's premise is stale; left in place for
history, not as an open item.

**Status: deferred, not decided piecemeal under today's momentum.** No
code written for any of the four items in today's design spec. Next
dedicated session should resolve both the grant-tick mechanism and the
`SpecialistPractice` Role placement together, then the original four-item
spec (Action declaration, live-detection trigger, `ViolationResponse`
firing, tests) can proceed against settled ground truth.

---

## WorldState scope — episode-community vs. standing federation communities (2026-08-20)

`WorldState` is a toolchain implementation concept, not something ISO/IEC
15414 defines directly — the standard only defines *state (of an object)*
(§3.1.1, imported from X.902); it never posits a global snapshot construct.
The toolchain's `WorldState` is a reasonable, sensible engineering choice
for enabling replay/comparison/testing (per the paper's own framing), not
a modelled ODP-EL entity — worth stating explicitly in any positioning
writeup, same treatment as the existing FHIR Contract caveat ("designed to
align with," not "modelled using").

In `referral_scenario.el`, there is exactly **one** `WorldState`, scoped
to `ReferralEpisodeCommunity` — the dynamic, per-episode community whose
roles are filled by acting parties (`GPClinician`, `SpecialistClinician`,
`SpecialistAIAgent`, etc.). This is the only community `WorldState` tracks
live token state for, consistent with §6.4.3 (deontic tokens are held by
active enterprise objects filling roles, not by roles or communities
directly) and §7.8.2 (a role is a placeholder; at most one object fulfils
it at a time).

`GPPractice` and `SpecialistPractice` are two separate **static/standing
community objects** (§6.2.2 — a community object is itself a composite
enterprise object representing a community, which is what allows it to be
used to build community hierarchies or fill member roles in a larger
federation). They relate to each other via `Contract.signer`/
`Contract.term` (the federation layer — see AM-35,
`extract_federation_from_contract()`) — a **peer/federation relationship,
not a shared enclosing community**. Neither practice holds live
per-episode token state, and `WorldState` does not track them the way it
tracks episode role-fillers; they are context/backdrop that licenses and
constrains the episode (via the standing contract), not participants
whose internal state `WorldState` represents directly.

Relevant for: any future work extending the federation/hierarchy pattern
(IPS cross-border scenario, AIVendor gap, further R23+R24-style Contract
extraction) — the episode-vs-standing-community distinction should hold
regardless of how many practices/organizations are involved.

---

## Conformance check — behaviour/actions attach to enterprise objects only via roles (verified against both ISO 15414 Annex B examples, 2026-08-20)

**Question checked:** does the grammar's decision to nest `Action` only inside
`RoleDecl` (i.e. an enterprise object/party can only have declared behaviour by
filling a community role) faithfully reflect ISO/IEC 15414, or is it more
restrictive than the standard requires?

**Method:** direct end-to-end read of BOTH running examples in the standard's
own Annex B — the e-commerce example (§B.1, pages 37–43) and the library
example (§B.2 Templeman Library, pages 43–49) — plus the normative prose
(§6.3, §7.4, §7.8.1–7.8.6) and the authoritative Linington/Miyazaki/Vallecillo
paper "Obligations and Delegation in the ODP Enterprise Language" (the paper by
the standard's own co-author describing the deontic-token extension as it went
into ISO 15414; its Figure 2 became Annex A's community-concepts diagram).

**Note:** the standard DOES contain a library example (§B.2, Templeman Library
at Kent) — this is distinct from and should not be confused with Thomas
Sepanosian's thesis / pyodpel library scenario, which is not a credible design
reference. The §B.2 example is normative-annex material and citable.

**Finding — the grammar's choice is fully standard-conformant, not merely
defensible:** in both worked examples, every action attributes participation to
enterprise objects *via roles*, with zero instances of an object or party
having behaviour/action attributed to it outside role-filling:
- E-commerce §B.1.5.4: "In the action of a customer buying a purple widget,
  e-system object and the customer object are actors, the object representing a
  purple widget is an artefact, and shippingSubsystem is both an actor and a
  resource" — participants named by their roles; "customer object" is explicitly
  defined as "an object fulfilling the role, customer."
- Library §B.2.3.3: "In the libraryCommunity, borrowers and librarians are
  actors in all actions specified for that community. Items are resources.
  Calendar is an artefact..." — participation stated in terms of role-fillers.
- Deontic attachment is role-mediated too: §B.1.7.1 "the e-system object needs
  to hold a permit deontic token before it can participate in the action in the
  role of orderTaker"; §B.1.7.2 "an auditor object (that is, a party fulfilling
  the role, auditor)".
- The obligation-conferring mechanism is role-filling itself: library §B.2.4
  "the action of filling a borrower role is therefore a speech act, resulting in
  a burden representing the obligation to obey the [regulations]." An object
  bears an obligation *because* it fills a role.

**Consequence for the grammar:** nesting `Action` inside `RoleDecl` is faithful
to the standard's own modelling, confirmed against normative prose + both annex
examples + Linington. A party (e.g. `SpecialistPractice`) that needs a declared
action MUST fill a community role — this is the standard-conformant requirement,
not a toolchain restriction to work around. Multi-role filling is explicitly
permitted throughout (§B.1.5.4 customer + e.comManager; §B.2.2.5/§B.2.2.7
librarian + borrower), so giving a standing party a role does not conflict with
its other modelled aspects.

**Supersedes an earlier over-correction in this session:** a mid-session hedge
suggested the grammar might be "more restrictive than the standard requires."
That is retracted — the standard's own examples never once model behaviour
attaching to an object outside a role. Usable as support for a defensible
"grammar respects ISO 15414" conformance claim in the position paper.

**`emits` considered and deliberately not added to `notify_gp_of_non_response` (2026-08-20):** X.902 §8.4 defines event notification as a communication to objects *not participating* in the action — which is conceptually exactly the "notify GP practice" (`escalate_to`) signal. However, this toolchain's `emits` construct (`grammar/v2/el_grammar.tx` `EmitsDecl`) does NOT implement §8.4 outbound notification — it implements intra-spec token choreography: an emitted event makes a burden dischargeable (`discharged_by` match, `el_engine.py` `advance()` Step 3) or transitions a `triggered_by` token WAITING→active (Step 7c; mirrored in `el_kripke.py`'s P6a cascade). No token today has `discharged_by`/`triggered_by` pointing at a notification event from this action, so adding `emits` would declare an inert `EventDecl` with no consumer — the opposite of `favoured_by_burden`, whose governance-lookup consumer genuinely exists. The genuine §8.4 GP-practice notification belongs on the `escalate_to` side of the still-open `ViolationResponse` wiring task; revisit `emits` there only if/when a GP-side waiting-token or notification-consumer actually exists. (Grammar v1 confirmed inert: `el_parser.py` hardcodes `grammar/v2/el_grammar.tx`, zero functional v1 references. `setup.cfg`/`setup.py` reference a dead nonexistent `odpel` package — documented cleanup, not blocking.)

**Correction, same day:** the above was resolved via `emits`/
`triggered_by`, but that mechanism turned out to be non-functional in
the live builder — `triggered_by` requires a pre-existing `pending`
token that nothing ever granted, and `GPPractice` was never enrolled
into the new `gpPracticeOversightRole` either, so nothing could attach
to it. Neither gap was caught by parse/validate or the full suite, only
by a test that actually tried to exercise the live chain end-to-end.
Re-resolved same day using `effect create
reviewNonResponseAndDetermineNextStepsBurden to gpPracticeOversightRole`
on `notify_gp_of_non_response` instead — self-contained, no pre-grant
needed, matches the precedent `initiateReferral` already uses for
cross-community reactive burden creation. `emits`/`event
gpNotifiedOfNonResponse` removed as no longer used.

---

## Delegation holder/chain resolution, Problem 1 — RESOLVED (2026-08-22, AM-51)

**FINDING (2026-08-22), closes Problem 1 of the 2026-08-19 paused finding above.**

`transfers_token_group`'s two-purposes conflation (objective-satisfaction
target vs. delegation-transfer signal, no distinguishing field — Problem 1
above) is fixed. `referral_scenario.el`'s `gpToSpecialistDelegation` no
longer declares `transfers_burden: referralResponseBurden` alongside
`transfers_token_group: referralBurdenGroup`; it now declares only
`transfers_token_group: specialistBurdenGroup` (a 2-member group already
declared for this purpose). `referralBurdenGroup` (5 members) is untouched
and remains solely the episode objective's `all_discharged` target — the
two groups are no longer the same object, so the conflation this Problem
named no longer exists for this delegation.

**This surfaced, and required fixing first, a real but latent gap in
AM-50's own walker:** `el_kripke.py::_delegation_chain_for_token()`
(the function AM-50 extended to bridge `principal_of`) only ever matched a
Delegation via a direct `.burden` reference — never via `token_group`
membership. Dropping `transfers_burden` from `gpToSpecialistDelegation`
without fixing this first would have silently broken AM-50's own
regression test (`test_delegation_chain_for_token_mirrors_reasoner_for_referral_response`):
the `GPClinician → SpecialistClinician` hop for `referralResponseBurden` is
a *paired* `principal_of`+`delegated_from` relationship, deliberately
excluded from AM-50's structural-edge mechanism, so `.burden`/`token_group`
matching on the `Delegation` itself is the *only* way that hop enters this
function's chain. Checked whether the gap was general before fixing it:
grepped every scenario file for a `Delegation` declaring
`transfers_token_group` with no `transfers_burden` — none existed anywhere
in the repo until this change deliberately created one. The gap was real
and general, just never previously exercised.

V-NEW-10 (documented, previously unregistered — mutual exclusion of
`transfers_burden`/`transfers_token_group`) is now registered in
`el_validator.py`. `gp_referral_scenario.el`'s own `gpToSpecialistDelegation`
still declares both fields (same conflation, out of scope for this fix) —
confirmed this doesn't regress anything today only because that file is
always parsed with `validate=False` in `el_api.py`, and no test in the
suite validates it directly. **Left as a known, named gap, not silently
fixed** — worth returning to.

Full detail, including the exact order fixes had to land in and why:
`docs/el_grammar_amendments.md`, AM-51.

**Process note, for the record:** a same-session pass the day before
(2026-08-21, in conversation, not written down) concluded a narrower
version of this fix — redirect the group only, keep `transfers_burden` —
was "confirmed safe." That conclusion never made it into this file; it
existed only in that session's conversation state. It did not survive a
fresh verification pass the next session, which is what actually found the
V-NEW-10 dual-declaration tension and the `_delegation_chain_for_token()`
gap above — both missed by the earlier, unwritten reasoning. Recording this
plainly because the failure mode is generic and worth naming: a
"confirmed safe" conclusion that lives only in a conversation, not in a
written repo record, gives the next session nothing to build on or check
against — it has to be re-derived from scratch, and there's no guarantee
the re-derivation catches what the original pass missed (this time, it
happened to; that's luck, not process). Findings that will matter to a
later session belong here, not just in the transcript that produced them.

---

## Delegation holder/chain resolution, Problem 2 — RESOLVED (2026-08-22, ground-truth check); surfaced a real AM-51 regression, closed as AM-52

**FINDING (2026-08-22), closes Problem 2 of the 2026-08-19 paused finding above, same causal thread as the Problem-1/AM-51 entry directly above.**

Asked, as a read-only ground-truth check: is Problem 2 ("no clean
discriminator exists over `Commitment.actor`/`Delegation.delegator` — a
naive `actor == delegator` test fails in opposite directions against the
two scenario files") closed as a side effect of AM-50/AM-51, or still open?

**Problem 2 itself: confirmed closed.** Grepped `el_reasoner.py`,
`el_kripke.py`, `el_engine.py`, `el_validator.py` for any direct
`Commitment.actor`/`Delegation.delegator` (or `.delegate`) equality
comparison — none exists anywhere. Re-ran the original failing test case
directly against both files and reproduced the exact opposite-direction
failure the 2026-08-19 write-up described — confirming it was accurately
recorded — but confirmed this comparison was never implemented as code,
only explored as a hypothesis in investigation. `ultimate_accountability()`/
`_walk_chain()`/`_delegation_chain_for_token()` resolve every burden in
`referral_scenario.el` end-to-end via pure graph traversal (`Delegation`
edges, `principal_of` structural edges, `token_group` membership) — no
equality shortcut needed anywhere.

**But that same check surfaced a real, distinct problem: a regression
AM-51 itself introduced**, closed same-day as **AM-52** (full detail:
`docs/el_grammar_amendments.md`). `_delegation_chain_for_token()`'s
`token_group`-membership match (added by AM-51) had no awareness of a
token's own `Commitment` at all — so a token sharing a `token_group` with a
genuinely-delegated token, but with its own independent `Commitment` root,
got silently misattributed to the wrong delegation. Checked systematically,
not just the one case already known: **4 conflicts found**, across both
`referral_scenario.el` (`assessmentSchedulingBurden`) and
`gp_referral_scenario.el` (`assessmentSchedulingBurden`,
`referralInitiationBurden`, `clinicalHandoverBurden` — the latter two
excluded only by obligation-text mismatch, not reachability, since their
`Commitment.actor` trivially equals the delegator; a reachability-only fix
would have missed them). AM-52 guards the `token_group` match with both a
reachability check (delegator reachable from the Commitment's actor via
AM-50's structural edges) and a text-relevance check (Commitment obligation
text consistent with the Delegation's own text, mirroring
`el_reasoner.py`'s own matching) — closing the full risk class, confirmed
against all 4 conflicts plus the 2 already-correct cases (including
`referralResponseBurden`, the case AM-51 was built for — no regression).

**Worth naming plainly:** this is the second time in two days a fix in this
delegation-chain area has needed its own follow-up fix the same session
(AM-51 needed the token_group-match extension before its own redirect could
land safely; AM-52 needed guarding the very extension AM-51 just added).
Both times the follow-up was caught by deliberately re-verifying against
the full scenario set rather than trusting the one case already in view —
worth continuing to check systematically (every scenario file, every group
member) rather than only the specific instance a task names, since that's
exactly what caught 3 of these 4 conflicts.

---

## `ultimate_accountability()`'s delegation-fallback path can present a role-conferred root as a resolved party — RESOLVED (2026-08-22, AM-54)

**FINDING (2026-08-22), RESOLVED same day**

Surfaced asking whether `Commitment` is the only possible root of a
delegation chain — it isn't, structurally. `_find_roots_from_delegations()`
(`el_reasoner.py`) is the path `ultimate_accountability()` uses when no
`Commitment` matches the query but some `Delegation`'s obligation text
does: it treats any delegator absent from `all_delegates` (the set of
every `Delegation.delegate` in the whole model) as an authoritative root,
and always wraps the result in a plain `AccountabilityChain` —
**it never checks whether that inferred root actually has any grounding
at all** (a `Commitment`, or, since AM-53, a role-conferred
`StaticRoleAnchor`). AM-53's fallback only fires from
`ultimate_accountability()`'s top-level `if not matching_commitments and
not matching_delegations` branch — it is never consulted from inside
`_find_roots_from_delegations()`'s own branch, which fires whenever *any*
delegation text matches, independent of whether its root is grounded.

**Confirmed by construction** (`MultiHopRoleConferredProbe`, no matching
scenario file exercises this today): `role roleA { holds burdenX }` (no
`Commitment` anywhere) in some community; `A →(aToB, obligation="Do the
thing")→ B →(bToC, obligation="Do the thing")→ C`. The multi-hop *walk*
itself is correct — it does reach back to `A` and forward to `C`, no
under- or over-walking:

```
ultimate_accountability(model, "Do the thing") ->
  AccountabilityChain(obligation='Do the thing', root_party='A',
    root_commitment=None, chain=[A→B, B→C], current_holder='C')
```

`root_party='A'` is presented exactly the way a genuine Commitment-backed
party would be — the only signal that `A` isn't actually resolved is
`root_commitment=None`, a field nothing forces a caller to check. This is
precisely the §6.4.3 conflation AM-53 exists to prevent (deontic tokens
are held by active enterprise objects filling roles, never by roles or
communities directly — a role-conferred root is not a resolved party any
more than a role-conferred leaf burden is), reoccurring through a second,
independent code path AM-53 doesn't cover.

**Status:** RESOLVED (2026-08-22, AM-54). `ultimate_accountability()`'s
delegation-only path now checks the inferred root's grounding via
`_find_role_anchors_for_obligation()` (reused, not duplicated) before
deciding whether to return an `AccountabilityChain` or a
`StaticRoleAnchor` — a role-conferred root now correctly returns a
`StaticRoleAnchor` with the onward delegation chain/current holder
preserved (extended with two new optional fields for exactly this case).
Confirmed directly against `MultiHopRoleConferredProbe` (with a realistic
`transfers_burden` field added, per AM-54's own ground-truth finding that
every live scenario always declares one):
`StaticRoleAnchor(role_name='roleA', community_name='SomeCommunity',
chain=[A→B, B→C], current_holder='C')`, no longer a bare
`AccountabilityChain`. Full detail: `docs/el_grammar_amendments.md`,
AM-54.

---

## `_walk_chain()`'s obligation-text matching does not survive text drift across multiple delegation hops — RESOLVED (2026-08-22, AM-54)

**FINDING (2026-08-22), RESOLVED same day**

Checked separately, since it's independent of the finding above: does
`_walk_chain()`'s recursive obligation-text matching reliably survive
being passed through two or more delegation hops at all, even in an
all-`Commitment`, no-role-conferred scenario? It does not.
`_walk_chain()` matches each hop against the *original* top-level query
string, unchanged at every recursion depth (`obligation.lower() in
link.obligation.lower()`, `obligation` never updated to the current hop's
own text) — so as soon as one hop's own obligation text stops containing
that original substring, the walk stops there, silently, with full-
confidence output and no error.

**Confirmed by construction** (`TextDriftProbe`, no matching scenario file
exercises this today — checked: `referral_scenario.el`'s and
`consent_scenario.el`'s existing multi-delegation chains all use
*different* obligation text per burden, never the same burden delegated
twice with drifting wording, so this has never actually been hit by a
committed scenario): `P` has a real `Commitment` (`obligation="Deliver
the report"`); `P →(pToQ, obligation="Deliver the report")→ Q
→(qToR, obligation="Q hands off report duties to R entirely")→ R`.

```
ultimate_accountability(model, "Deliver the report") ->
  AccountabilityChain(root_party='P', current_holder='Q', chain=[P→Q])
```

`R` is silently missing — the true current holder is `R` (`qToR` is a
genuine, existing `Delegation`), but the second hop's wording doesn't
contain the original query substring, so the walk never reaches it.
Affects both `ultimate_accountability()`'s entry paths equally (the
`Commitment` branch and the delegation-fallback branch above both call
this same `_walk_chain()`).

**Status:** RESOLVED (2026-08-22, AM-54). `_walk_chain()` now matches
structurally first — a hop that declares `transfers_burden`/
`transfers_token_group` is matched (or rejected) by that signal alone,
regardless of its own obligation wording; free-text matching applies only
to a hop with no structural reference at all, exactly the "matching via a
structural signal" direction sketched here, mirroring how AM-51/52 moved
`_delegation_chain_for_token()` off pure text-matching. Confirmed directly
against `TextDriftProbe` (with realistic `transfers_burden` fields added):
`current_holder='R'`, chain `[P→Q, Q→R]` — no longer silently stopping at
`Q`. Full detail: `docs/el_grammar_amendments.md`, AM-54.

---

## V-15's obligation-text matching has the same conceptual gap as pre-AM-54 `_walk_chain()` — RESOLVED (2026-08-22, AM-55)

**FINDING (2026-08-22), RESOLVED same day**

Surfaced as a side effect of writing AM-54's test fixtures, not a
targeted investigation — worth recording rather than letting it disappear
into a test-file comment. `el_validator.py`'s V-15 ("DelegationDecl.obligation
text must match the obligation of a CommitmentDecl or a prior
DelegationDecl — chain continuity check") rejected both of AM-54's new
probe fixtures (`MultiHopRoleConferredProbe`, a role-conferred delegation
root with no `Commitment` at all; `TextDriftProbe`, a later hop's
obligation text deliberately reworded) when parsed with `validate=True`:

```
[V-15] Delegation 'aToB': obligation 'Do the thing' does not match any CommitmentDecl. Delegation chain has no commitment root. (§7.10.1)
[V-15] Delegation 'qToR': obligation 'Q hands off report duties to R entirely' does not match any CommitmentDecl. Delegation chain has no commitment root. (§7.10.1)
```

This is the same conceptual gap AM-54 just closed in `el_reasoner.py`,
recurring in a different layer: V-15 also assumes every genuine
delegation chain traces back to a `Commitment` via text matching, with no
awareness of role-conferred origins (§B.2.4) and no structural
(`transfers_burden`/`transfers_token_group`) matching option at all —
just a stricter validator-time version of the same text-matching
assumption. Not exercised by any live scenario today (both fixtures were
parsed with `validate=False` specifically to route around this, per
AM-54's own test file), so no committed scenario is currently
misvalidated by it — but the same class of false-positive/false-negative
risk AM-54 found in `_walk_chain()` likely applies here too, unverified.

**Status:** RESOLVED (2026-08-22, AM-55), applying AM-54's exact pattern
one layer over. V-15 now checks a `Delegation`'s structural reference
first (`transfers_burden`/`transfers_token_group`) — at least one
referenced token grounded via a `Commitment` naming it or a `Role`
`holds`-ing it (AM-53-style) — falling back to the original exact-text
check only for a `Delegation` with no structural reference at all.
"Delegation-continuation" needed no separate case: grounding by token
name, not chain position, covers it for free. Confirmed directly: both
fixtures above now validate cleanly (`validate=True`, no more
`validate=False` workaround needed — `tests/test_am54_structural_matching_and_root_grounding.py`
updated accordingly); a genuine orphaned-token violation
(`OrphanedTokenProbe` — no Commitment, no Role holds it) still correctly
fires. Full detail: `docs/el_grammar_amendments.md`, AM-55.

---

### V-16a/V-16b status correction (2026-08-23)

Prior notes (including a same-day session brief) described V-16
("TokenGroup members should have a backing Commitment") as still deferred
and unregistered. Ground-truth check of `el_validator.py` on `main` shows
this is stale: **V-16a and V-16b are both implemented and registered**,
confirmed CONFIRMED in `el_grammar_amendments.md`:

- V-16a (`_validate_token_group_provenance`) — every `TokenGroup` member
  must be backed by a top-level `Commitment`, a `Delegation.transfers_token_group`,
  or a role `holds` — dispatched in `validate_spec` immediately before V-16b.
- V-16b (`_validate_satisfaction_singleton`) — warns when a
  `SatisfactionCondition` has only one effective member.

No action needed. Recorded here so this doesn't get re-flagged as open in
a future session.

---

### Masked (`pending`) sibling gap in `any_discharged` supersession (AM-57)

AM-57's live sibling-supersession in `el_engine.py` is scoped to
`active`-state siblings only — not `pending`. This matters more than a
remote edge case: `pending` is dual-purpose at the engine level (NOTE
5/6 delegation-retention masking, AND the live representation of a
`triggered_by`-gated burden before its event fires). `referral_scenario.el`'s
`referralInitiationBurden` (`triggered_by: encounterConcluded`, line 216)
is a real, committed example of the latter mechanism — though the
scenario declares it `state: active` by default; `test_referral_event_triggers.py`'s
`_with_pending_referral_burden()` helper is what actually exercises its
`pending`→`active` transition, by overriding that default. `el_kripke.py`'s
P6b supersedes both PENDING and WAITING siblings (WAITING = Kripke's term
for the not-yet-triggered case); the live engine currently only covers
the PENDING-equivalent (`active`).

Net effect: if an `any_discharged` group member is a `triggered_by`-gated
burden currently sitting `pending`, and its sibling discharges first,
Kripke would supersede it but the live engine won't — it stays inert and
could later resurface as a live obligation once triggered, with no
memory that the group's objective was already met.

**Constraint on future `any_discharged` scenario design** (not just a
documentation note): until this is built, any `any_discharged`
`TokenGroup`'s members should avoid `triggered_by`/`state: pending`
declarations — including the standalone two-peer demo scenario planned
next. Revisit building the full mechanism only if a real scenario needs
a triggered_by-gated peer inside an any_discharged group.

**Update (2026-08-24): `claimable` (AM-60–63) is deliberately outside
the scope of this constraint — recorded explicitly, not left implicit.**
`erequesting_claiming_scenario.el` is a new `any_discharged` scenario and
sits adjacent to this exact area, so the relationship must not be
assumed obvious: `claimable` is a new author-facing `TokenState`,
introduced specifically so pool-claiming does NOT fall inside this
constraint. AM-61's C1 (claim) transition and AM-62's 7a-claim-cont
lapse mechanism operate on `CLAIMABLE`-state siblings — entirely
separate from P6b's `PENDING`/`WAITING`-sibling supersession logic that
this finding leaves incomplete. **Claiming (AM-60–63) does not close
this gap and does not depend on it being closed — they are parallel
mechanisms over different states, not sequential.** The constraint
above (avoid `triggered_by`/`state: pending` siblings in an
`any_discharged` group) still stands, unchanged, for any future
scenario that is not using the claiming mechanism.

---

## Delegation claiming (AM-60–63) — scope, distinctions, and open design options

Design source: `docs/design_notes/DN_003_delegation_claiming_evaluation.md`.
Implementation landed 2026-08-24: AM-60 (grammar/parser/domain), AM-61
(Kripke), AM-62 (live engine), AM-63 (`erequesting_claiming_scenario.el`,
the accept-side sibling of AM-58's `specialist_pool_scenario.el`).

**1. Claiming = evaluative pool-accept, distinct from declarative/atomic
transfer — only the evaluative shape is implemented.** DN_003 §5.0
establishes two speech-act shapes for delegation claiming: an
*evaluative* one (a structured `Evaluation` gates the transition, as
built here) and a *declarative/atomic transfer* one (DN_003 §5.4). Only
the evaluative path is implemented by AM-60–63.

**OPEN FINDING** — The declarative/atomic transfer path (DN_003 §5.4) is
explicitly NOT implemented and is not scheduled — flagged here so no
future session assumes `claimable`/`Evaluation` covers it. If a scenario
later needs one-shot, non-evaluated transfer semantics, that is new
design work, not a variant of AM-60–63.

**2. `lapsed` vs `superseded` are distinct and must not be conflated.**
`lapsed` (AM-61 C1 / AM-62 7a-claim-cont) marks a sibling whose claim
opportunity was overtaken because a peer *claimed* first — no decision
was made, the obligation was never live. `superseded` (AM-57, P6b) marks
a sibling relieved because a peer *discharged* first — the group's
purpose was already fulfilled by a completed obligation. Same shape
(peer-driven, non-failure exclusion from utility scoring) but different
triggers and different standing: a `lapsed` obligation's holder never
had the chance to act; a `superseded` obligation's holder's action was
simply no longer needed.

**3. The masked-sibling gap finding (immediately above) is now resolved
on the accept side, but the underlying empirical finding was broader
than DN_003's original framing.** AM-62's ground-truth check (performed
before implementation, recorded in `erequesting_claiming_scenario.el`'s
scenario header and in AM-62's amendments-log entry) found that the
pre-AM-62 live engine had **no `pending`/`claimable` → `active`
activation step at all** — not merely an absent sibling-supersession
step. Acting on a masked burden was a silent, effect-free no-op
(`outcome: "ok"`, `effects: ()`). Separately: **the Kripke layer never
had this gap.** `el_kripke.py`'s initial-world construction does not
read the DSL's declared `state:` field at all — every non-`triggered_by`
obligation starts `PENDING` regardless of whether the author wrote
`state: pending` or `state: active`, so P6b already covered PENDING/
WAITING siblings symmetrically before AM-61. AM-61 only needed to add
the new `CLAIMABLE`/`LAPSED` states and the C1 rule, not fix an
existing Kripke gap.

**4. `CommunityObject`-as-`Delegation`-target is a live, standards-
grounded design option not yet acted on — logged as an option, not a
commitment.** Per §6.2.2/§7.4, a `CommunityObject` (composite ActiveEO
representing a community) is the standards-correct target for
"delegated to the pool as a whole," which would let a single
`Delegation` name the pool rather than requiring one `Commitment` per
member (as `erequesting_claiming_scenario.el` currently does). The grammar
currently types `Delegation.delegator`/`.delegate` as
`[EnterpriseObject]` only (CLAUDE.md §5.4) and would need extending
to accept `[CommunityObject]` — see also the existing open finding
"Finding 2" above (`CommunityObject` should satisfy `EnterpriseObject`'s
interface) which this option would depend on. Not scheduled; revisit if
a future pool-delegation scenario needs single-target delegation syntax.

---

## `Composition`-based document bundles have no mapping rule in `fhir_mapper.py` — OPEN FINDING (2026-08-28)

**Status: OPEN, not scheduled.** Full write-up: `docs/design_notes/DN_008_composition_mapping_gap.md`.
Fixture: `tests/fixtures/aups_referral_example/` (`Composition-roberts-fred-summary.json`,
`ServiceRequest-referral-endocrinology.json`).

Confirmed empirically, not assumed: a minimal but genuinely valid AU
Patient Summary referral (`ServiceRequest.supportingInfo` → `Composition`,
matching AU PS's own "Referral to Specialist and Allied Health" use case)
run through the real `FHIRConsentMapper.map_bundle()` maps the
`ServiceRequest` correctly (R05 `Commitment`, R07 `Burden`) and produces
**zero** references to the `Composition` anywhere in the output or
provenance table. Confirmed by direct inspection of `fhir_mapper.py`:
there is no mapping rule for `Composition` today. Reproduced independently
against the committed repo state (not just the sandbox that produced the
original finding).

**Direct connection to DN_004:** the `au-ps-composition` `StructureDefinition`
carries real, structured FHIR Obligation extensions per element
(`SHALL:populate` for the producer actor, `SHALL:handle`/`SHOULD:display`
for the consumer actor). None of this is visible to governance today —
a concrete, data-backed instance of the "declare vs verify" gap DN_004
already argues about in the abstract: FHIR Obligations declare what an
actor must do with an element but don't express whether that handling
actually happened, or what follows if it didn't.

DN_008 §5 sketches two implementation options (attach `Composition` as
evidence on the existing `ServiceRequest` burden, vs. a new construct
mapping the `Composition`'s own per-section obligations onto the
receiving clinician) but commits to neither. Not scheduled; revisit when
a future session picks up `Composition` mapping.

---

## `deadline: "referral episode"` has no valid tick-count — falls through to the bare default, now the fastest-violating deadline in the scenario — MITIGATED (2026-08-29), underlying gap still OPEN

**Status: MITIGATED same day it was logged.** Burdens with a no-magnitude
deadline no longer falsely tick-violate (direction 1 below, implemented) —
see "Mitigated (2026-08-29)" at the end of this entry. **The underlying
modelling gap remains OPEN and unscheduled, but is now properly scoped,
not undesigned**: `DN_010_episode_conclusion_deadline_checking.md`
(2026-08-29, same day) corrects the framing this finding originally used
— the concept of "episode concluded" already exists, declared explicitly
in `ReferralEpisodeCommunity`'s own `objective: ... satisfaction:
all_discharged(referralBurdenGroup)` and its description ("dissolved on
objective achievement"); what's missing is that the live engine never
implements it (confirmed by grep, zero references to community
dissolution/termination anywhere in `el_engine.py` — the same
declare-vs-verify gap `DN_004` already names, one layer up). DN_010
scopes direction 2 below into two concrete pieces (live
community-conclusion tracking, then wiring episode-scoped deadline
checking to it) and flags one deliberately deferred sub-question
(successful vs. unsuccessful episode conclusion). No code written; not
scheduled. Distinct from, and older than, the separately-resolved
bucket-collision finding (2026-08-20, resolved 2026-08-29 — see the
`discharge_mode: strict` section's "Convergence with live-violation-
detection design" entry above). That fix corrected magnitude handling for
numeric deadlines; this finding is about a deadline string that carries
no numeric magnitude to correct in the first place.

`clinicalHandoverBurden` and `aiExaminationBurden` (both
`discharge_mode: eventual`, `referral_scenario.el`) declare
`deadline: "referral episode"` — no digit, no unit keyword
(`second`/`minute`/`hour`/`day`/`week`/`month`). Confirmed directly against
`_parse_deadline_steps()` (`toolchain/el_engine.py:704`): neither the
magnitude-matching branch nor the unit-keyword fallback loop fires, so it
falls straight through to the function's own bare `default` parameter,
`5`. Both burdens reach this via Tier 1 (`_build_obligation_descriptors()`,
`el_engine.py:914-927` — each has a real Commitment,
`clinicalHandoverCommitment`/`aiExaminationCommitment`), which calls
`_parse_deadline_steps(deadline_str)` with no explicit default override,
landing on the same bare `5`.

**Confirmed pre-existing, not a side effect of `5b21dc9`.** Extracted the
exact pre-fix function body (`git show 5b21dc9^:toolchain/el_engine.py`) and
traced it by hand against `"referral episode"`: same six substring checks,
same "none match," same `return default` (`5` at that call site too, then
as now). `5b21dc9` only added a magnitude-aware branch ahead of the
existing fallback loop — it never touched what happens when neither a
digit+unit pair nor a bare unit keyword is found. This string hits neither,
before or after.

**Made materially worse by `5b21dc9`, though not caused by it.** Before the
fix, every day-based deadline flattened to the same bucket (8), so the
episode-scoped burdens' `5` was merely the *tightest* among several
similar values. After the fix, numeric deadlines now get their own
proportional values (`referralResponseBurden` → 40,
`assessmentSchedulingBurden` → 112), while the episode-scoped burdens'
value is untouched at `5` — now the *lowest* `deadline_steps` of any
eventual burden in the scenario. Confirmed live: reset →
`initiateReferral` → advance 4 ticks → `/check-violations` at elapsed
tick 5 violates both `clinicalHandoverBurden` and `aiExaminationBurden`
("elapsed 5 >= deadline 5 steps") — before `referralResponseBurden` (needs
40) or `assessmentSchedulingBurden` (needs 112) are anywhere close to
violating. The two vaguest, most open-ended deadlines in the system —
"sometime during this episode" — are currently the *fastest* to falsely
violate, the inverse of their intended meaning.

`check_live_violations()` (`el_engine.py:1140-1251`) applies zero
special-casing here: it sweeps every `discharge_mode: eventual` active
burden with one uniform check, `elapsed = tick - granted_at_tick >=
deadline_steps`, regardless of what the deadline string conceptually
means. There is no code path anywhere that distinguishes an elapsed-time
deadline from an episode-scoped one.

**Root cause is a genuine modelling gap, not a parsing bug.** A deadline
like "5 working days" has a literal tick-equivalent to parse toward.
"Referral episode" does not — it means "bounded by this episode's own
conclusion," and nothing in `WorldState`/`TokenInstance` today represents
"has this episode concluded" as a checkable condition. No fixed
tick-count can ever be conceptually correct here: too tight (today's `5`)
or too loose (any larger chosen default), arbitrarily, because the
underlying question isn't "how many ticks have elapsed" at all.

**Two possible directions, neither decided:**
1. Exclude episode-scoped deadline strings from
   `check_live_violations()`'s sweep entirely — burdens tagged this way
   simply never tick-violate — until genuine episode-conclusion tracking
   exists.
2. A structurally different check tied to episode state (e.g. some future
   "has `ReferralEpisodeCommunity` concluded" condition) rather than
   elapsed ticks. **Now scoped, not just gestured at** — see
   `DN_010_episode_conclusion_deadline_checking.md`: the "episode
   concluded" condition is `ReferralEpisodeCommunity`'s own declared
   `objective: ... satisfaction: all_discharged(referralBurdenGroup)`,
   which both affected burdens (`clinicalHandoverBurden`,
   `aiExaminationBurden`) are already members of — no new group needed.
   Two concrete pieces: (b-1) live community-conclusion tracking in the
   engine (declared in the grammar, never implemented at runtime —
   confirmed by grep, zero hits for dissolution/termination in
   `el_engine.py`), then (b-2) wiring `check_live_violations()`'s
   no-magnitude-deadline burdens to it. DN_010 also flags successful vs.
   unsuccessful episode conclusion as a deliberately deferred
   sub-question, not yet folded into this scoping.

Both require a design decision (what does "episode concluded" even mean
operationally — a Community lifecycle transition? every member burden
discharged? an explicit close action?), not a one-line patch. Not
scheduled; revisit when live violation detection for episode-scoped
deadlines is prioritised.

**Mitigated (2026-08-29), same day — direction 1 above, implemented
generally, not as a narrow string match.** Grepped every `deadline:`
string across every `.el` scenario file in the repo (not just
`referral_scenario.el`) before scoping the fix: seven deadline strings
repo-wide carry no digit at all — `"referral episode"`
(`referral_scenario.el` ×2, `gp_referral_scenario.el` ×1),
`"invoice due date"`, `"agreed delivery date"`, `"reorder point"`,
`"thirty days from cancellation"` (all `ecommerce_scenario.el` — itself
currently unparseable, pre-existing syntax error, so moot in practice
today), and `"clinical session"`/`"end of session"` (`consent_scenario.el`
— `seekConsentObligation`'s `"clinical session"` is `discharge_mode:
strict`, already excluded from `check_live_violations()` regardless;
`reportingObligation`'s `"end of session"` is `eventual` and was affected).
None of `erequesting_claiming_scenario.el`, `specialist_pool_scenario.el`,
or `industrial_procedure_scenario.el` have a no-digit deadline.

New function `_has_deadline_magnitude()` (`toolchain/el_engine.py`,
alongside `_parse_deadline_steps()`) answers "does this deadline string
carry a real, computable elapsed-time magnitude" as a `bool`, distinctly
from `_parse_deadline_steps()`'s `int`-only return, which cannot tell "we
computed 5 because the deadline genuinely means 5" from "we returned the
bare default because there was nothing to compute." `check_live_violations()`
now calls it before resolving `deadline_steps` for each active `eventual`
burden (both Tier 1/Commitment-derived and Tier 2/bare-token paths — the
raw deadline string lookup is now shared between them) and `continue`s
(never touches, never transitions) when it returns `False` — a general
condition based on whether `_DEADLINE_MAGNITUDE_RE` actually matched, not
a literal check against the string `"referral episode"`, so it also
correctly covers `"during the episode"`, `"throughout treatment"`, or any
similarly-shaped deadline a future scenario author writes, without a
separate fix each time.

One deliberate refinement beyond the literal "no digit at all" framing:
the condition is "no digit *adjacent to a recognised unit word*", not "no
digit character anywhere in the string" — `scenarios/fhir/
generated_governance.el`'s `"by 2026-05-20"` contains digits but no usable
elapsed-time magnitude (an absolute calendar date, structurally as
unusable as no digit at all); treating "has digits somewhere" as
sufficient would have left that shape of deadline exploitable by the same
bug. Confirmed this makes no behavioural difference across any deadline
declared today — `"by 2026-05-20"` is declared on a `permit`, not a
`burden`, so `check_live_violations()` (which only ever sweeps burdens)
was never going to touch it regardless — but the function is written to
get the general case right rather than the case that happens not to
matter yet.

Kripke verifier (`el_kripke.py`) behaviour is unchanged — this fix is
scoped to `check_live_violations()`'s live tick-sweep only, per its own
request; `ObligationDescriptor.deadline_steps` and Rule T2 still compute
and use the plain `int` value (`5`, unchanged) exactly as before for these
burdens, since nothing about the verifier's bounded-horizon model was
asked to change here.

10 new tests (2 integration-level in
`tests/test_check_live_violations.py`, exercising both Tier 1 and Tier 2;
8 unit-level in `tests/test_parse_deadline_steps.py` covering
`_has_deadline_magnitude()` directly, including every no-digit deadline
string found in the repo-wide grep above and the `"by 2026-05-20"` edge
case). Full suite: 223/223 before this change (the `5b21dc9` baseline),
231/231 after, zero regressions. Re-verified live: reset →
`initiateReferral` → `/advance-clock` past tick 10,000 → `/check-violations`
— `clinicalHandoverBurden`/`aiExaminationBurden` remain `PENDING`
throughout (never violate, at any tick tested), while
`referralResponseBurden`/`assessmentSchedulingBurden` violate exactly as
`5b21dc9` already established (elapsed ≥ 40 / ≥ 112 respectively).

---

## Mapper-generated burdens are declared but never granted (no live TokenInstance) — RESOLVED (2026-08-30)

**OPEN FINDING (2026-08-30), RESOLVED same day**

**Fix, scoped to R05-R08 specifically (the ServiceRequest → Commitment +
Burden path):** `_map_service_request` now grants the burden directly to
the same accountable party already resolved for `commitment.by` (via
`_resolve_commitment_accountable_party`, AM-71) — but only when that
el_id actually names a declared `ELObject` (checked at map time, since
demographics are always mapped before `ServiceRequest`s). `ELToken`
gains a `holder_el_id` field; `_render_object` emits a `holds <burden>`
clause inside the holder's body (grammar `ObjectBody` order: `holds`,
then `delegated_from`, then `principal_of`). When the holder can't be
resolved (the same dangling-reference risk AM-71's tier (c) already
accepted), the burden stays ungranted — never fabricate a holder the
bundle doesn't support — with an `[R06] UNRESOLVED holder` tag on its
description instead of a silent gap. `Runtime.build_from_spec()` now
produces a real live `TokenInstance` for these burdens — verified against
`scenarios/fhir/generated_governance.el` (regenerated) and
`tests/test_fhir_mapper_holds_clause.py`.

**Confirmed NOT fixed, deliberately out of scope:** R16/R17 (`Consent` →
`permit`/`embargo` via `Authorization`) has the identical underlying
gap — checked, not assumed: even the hand-authored `referral_scenario.el`
cannot use a `holds` clause for an `Authorization`-granted permit at all
(`el_api.py`'s scenario builders hand-maintain a hardcoded
`grant_token()` list instead, entirely bypassing both `holds` and
`Runtime.build_from_spec()`'s generic mechanism). Left for a future pass.

**Found:** 2026-08-30, during R37b test-writing (`fhir_event_handler.py`).

`fhir_mapper.py`'s generated community blocks declare every burden R05
through R37a create (as `DeonticToken` elements), but never emit a
`holds` clause anywhere. Consequence: when a mapper-generated `.el` spec
is parsed and run live via `Runtime.build_from_spec()`, zero live
`TokenInstance`s exist for any mapper-generated burden — they're
declared in the spec, but held by nobody.

This means no mapper-generated output has ever actually been runnable in
the sense of having a real, discharge-able/violate-able token in
`state.tokens`. It's why `tests/test_fhir_procedure_event_endpoint.py`
had to manually grant a token before it could exercise R37b's real
(non-idempotent) discharge path against mapper output — the mapper's own
generated community provides no live instance to test against as-is.

~~Not yet scoped as a fix — flagging as a genuine, previously-undiscovered
gap in the mapper's output, separate from R37a/R37b, affecting every
mapper-generated burden across every rule (R05–R37a), not just
Procedure-related ones. Whoever picks this up next should check whether
party declarations in the generated output are even meant to `holds`
the burdens they're accountable for, and if so, design the mapper-side
fix (likely a `holds` clause emission alongside each `ELToken`, wired
into whichever party/agent object the burden's holder resolves to).~~
Resolved same day for the R05-R08 path via the fix noted at the top of
this entry — R16/R17 confirmed to have the same gap and remains open,
see the note above.

---

## PractitionerRole-as-requester crashes validation entirely (ServiceRequest.requester) — RESOLVED (2026-08-30)

**OPEN FINDING (2026-08-30), RESOLVED same day**

**Fix:** a new PractitionerRole-direct branch in
`_resolve_commitment_accountable_party` (`fhir_mapper.py`), resolving
via a direct `by_ref` lookup in three tiers — `.organization` found
(clean resolution), no `.organization` (falls back to the
PractitionerRole's own `.practitioner` reference, with a warning), or
the PractitionerRole not found in the bundle at all / has neither field
(falls back to the raw reference, with a warning). Verified against the
real touchpoint-3 data that originally surfaced this finding — see
`tests/test_fhir_mapper_practitioner_role_requester.py`.

**Found:** 2026-08-30, while investigating the holds-clause gap against
real ConnectedCare touchpoint 3+4 data.

_resolve_commitment_accountable_party (fhir_mapper.py:307) silently
mis-handles a ServiceRequest.requester reference pointing at a
PractitionerRole resource. Its docstring's "requester does not reference
a Practitioner" case assumes the reference is already resolved (e.g. an
Organization) -- but a PractitionerRole reference is NOT already
resolved this way, and no _map_* function ever turns a PractitionerRole
resource into a declared ELObject. Result: the generated commitment.by
names an object that was never declared, causing a hard validator
failure -- [SEMANTIC] Unknown object "<Name>" of class "EnterpriseObject"
-- before the pipeline ever completes.

This is more severe than a silent gap: PractitionerRole-as-requester is
standard AU Core practice, not an edge case, so ANY real ConnectedCare
(or other AU-shaped) bundle authored this way currently fails validation
entirely. Every existing test fixture in this repo happens to use
requester: {"reference": "Practitioner/..."} directly, which is why this
was never caught until real touchpoint data was run through the pipeline
(2026-08-30 investigation, confirmed via in-memory workaround -- rewrote
requester to reference Practitioner/ directly, no source file modified).

Higher priority than the sibling holds-clause finding logged the same
day: that one is a silent no-op affecting live-runtime behaviour; this
one is a hard parse/validate failure blocking the static pipeline
outright for realistic input shapes.

~~Not yet scoped as a fix -- whoever picks this up should design a
_map_practitioner_role (or equivalent) resolving a PractitionerRole
reference to its underlying Practitioner (and/or declaring the
PractitionerRole itself as an ELObject, matching however Organization
references are already handled), then wire it into
_resolve_commitment_accountable_party's requester-resolution logic.~~
Resolved same day via the fix noted at the top of this entry — no
separate `_map_practitioner_role`/ELObject declaration turned out to be
needed; direct-lookup accountability resolution was sufficient (see the
follow-on design note below on whether role-fulfilment itself is worth
modelling explicitly).

---

## PractitionerRole/Organization mapping could model role-fulfilment explicitly, not just resolve accountability — OPEN FINDING (2026-08-30)

**Found:** 2026-08-30, while grounding the PractitionerRole-as-requester
fix against ISO/IEC 15414.

The standard's own concepts map cleanly onto this FHIR structure:
Practitioner ~ Party/active enterprise object (§6.2 — "parties can have
intentions and are accountable for their actions"); Organization ~
Community, with its own contract/objective/roles (matches the standard's
own library worked example, B.2.2.4-B.2.2.7 — "the libraryCommunity is
composed of objects fulfilling the roles identified above"); PractitionerRole
is NOT itself a party or active enterprise object at all — it's FHIR's
literal encoding of a role-fulfilment relationship, matching §7.8.2's own
definition almost word for word ("an enterprise object fulfilling the
role, <X>").

This validates the just-fixed accountability-resolution logic
(PractitionerRole -> Organization) as conceptually correct, not merely a
workaround — the community genuinely is where organisational
accountability sits per §7.6.2's assignment-policy concept.

But it also surfaces a bigger, separate opportunity: the mapper's
generated role blocks currently render as empty {} bodies (confirmed
during both R34 and R35's grounding work) — zero real content. A richer
future mapping could actually DECLARE the role-fulfilment structure the
standard describes: a real role element on the Organization-community
(e.g. role generalPractitionerRole), with the Practitioner represented as
the enterprise object currently assigned to fulfil it (§7.6.2's
assignment policy, made concrete), rather than flattening PractitionerRole
into a one-off accountability lookup and discarding the rest.

Not scoped as a fix — this is a design-depth question (does the mapper
ever need to model role-assignment explicitly, or is accountability
resolution alone sufficient for the toolchain's purposes?), not a bug.
Separate from, and lower priority than, anything currently in flight.

---

## eCDS interaction/duplication-check accountability — who is responsible for catching a cross-plan medication conflict? — OPEN FINDING (2026-08-30)

**Found:** 2026-08-30, scoping R38 (`MedicationRequest`/`MedicationDispense`,
touchpoint 5, medicines management). Deliberately deferred rather than
built — flagged here per that pass's own scoping decision, not attempted
as new machinery.

Touchpoint 5's real workflow (ConnectedCare) has the pharmacy retrieve an
ePrescription, run eCDS (electronic Clinical Decision Support)
interaction/duplication checks against the patient's existing medication
list, then dispense. R38/R38a/R38b map the mechanical shape of this —
`MedicationRequest` → `Commitment` + `Burden`, `MedicationDispense` →
fulfilment/discharge — but say nothing about the eCDS check itself: who
is accountable for actually running it, what happens governance-wise if
it's skipped, and who bears responsibility if a real interaction is
missed because two different prescribers (on two different care plans,
neither aware of the other) both wrote overlapping medications.

This is the same "declare vs verify" gap `DN_004` already names in the
abstract, but a genuinely new instance of it, not a mechanical mapping
this project's existing patterns (R33a/R34/R36/R37a/R38a-style
provenance tagging) can just be pointed at. A `Burden`/`Permit` pair
requiring the eCDS check before dispense is the obvious first sketch,
but: which enterprise object holds that burden (the dispensing pharmacy?
the ePrescription Exchange, mapped as a plain `Organization` for R38 —
see the sibling entry above? something not yet modelled at all)? What
FHIR-side signal, if any, indicates the check actually ran (no field
identified yet — `MedicationRequest`/`MedicationDispense` carry no
eCDS-outcome element in the AU profiles grounded for R38)? Is a missed
cross-plan interaction even detectable from the FHIR data alone, or does
it require information (the *other* plan's medication list) that may
not be in any single bundle this toolchain ever sees?

Not scoped as a fix, not scoped as a design note yet either — this needs
its own design pass, not an extension of R38's mechanical mapping.
Whoever picks this up next should start by checking whether any AU
profile (au-medicationrequest, au-medicationdispense, or a
CDS-Hooks-adjacent resource) actually carries a structured field for
"interaction check performed" before assuming one needs to be invented.

---

## An accountable-party reference resolving to an empty string would crash the parser, not just fail validation (R05/R38 share this latent gap; guarded only in R39) — OPEN FINDING (2026-08-30)

**Found:** 2026-08-30, implementing R39 (`Observation` → `Burden` +
`violation_response` escalation, `fhir_mapper.py`).

`Commitment.by` is a mandatory, non-optional `[EnterpriseObject]`
cross-reference in the grammar — there is no way to declare a
`Commitment` without one. `_map_observation` (R39) initially hit this
directly: when neither `.basedOn` nor `.performer` resolves to anything
at all, the accountable-party el_id comes back as `""`, and naively
emitting `commitment.by: ` with nothing after it is a textX **parse**
failure, not a `[SEMANTIC]` validator warning — a strictly worse failure
mode than AM-71/AM-72's already-accepted "reference exists but doesn't
resolve to a declared object" risk tier (that case still produces a
syntactically valid, non-empty identifier). R39 guards against this with
an early `return` — skip creating anything for that `Observation`
entirely rather than emit unparseable text.

**Not fixed here, and confirmed present, not merely suspected:**
`_map_service_request` (R05) and `_map_medication_request` (R38) both
call `_resolve_commitment_accountable_party(sr.get("requester"), by_ref)`
unconditionally and pass the result straight into `ELCommitment(by=...)`
with no non-empty check at all. If `.requester` is completely absent
from a `ServiceRequest`/`MedicationRequest` (not just unresolvable —
literally missing the field), `_resolve_commitment_accountable_party`
falls through its own case 1 to `_ref_id(None)`, which returns `""`, and
the same blank-`by:` parse crash follows. Every real fixture and every
real touchpoint bundle used so far has always carried some `.requester`
value, however unresolvable, so this has never actually fired in
practice — it is a genuine gap, not a hypothetical one, just not yet
observed against real data.

Not scoped as a fix — narrower than it looks: the correct guard (skip
creating the `Commitment`/`Burden` entirely when the accountable-party
el_id is empty, mirroring R39's own early-return) is a one-line change
in each of two functions, but making that change without a session
explicitly scoping it would be exactly the kind of unrequested fix this
project's working pattern deliberately avoids. Whoever picks this up
next should add the same empty-string guard to `_map_service_request`
and `_map_medication_request` that R39 already has, plus a regression
fixture (a `ServiceRequest`/`MedicationRequest` with no `.requester`
field at all) to prove it.

---

## `effect create ... to <Role>` target resolution has no community scoping — role names must be unique across communities when used as effect-create targets

**Found and fixed same day (2026-09-03), during AM-75's escalation-chain
work.** `el_engine.py`'s `effect create` target resolution matches by
bare role-name string across every enrolled actor in the whole
`WorldState` — it does not scope by which community declares the role.
`GPPracticeCommunity` and `SpecialistPracticeCommunity` both declaring a
role named `practiceOversightRole` caused a single `effect create ...
to practiceOversightRole` to grant the token to *both* practices'
actors, not just the intended one — confirmed empirically (two `created`
effects, two live tokens, one per practice).

Fixed by renaming the newly-added `GPPracticeCommunity` role to
`gpPracticeOversightRole` — a naming-collision avoidance, not an engine
change. No other two communities in the current scenario set share an
action-bearing role name, so this was the only live instance.

**Constraint on future scenario design:** role names used as `effect
create ... to <Role>` targets must be unique across the whole spec, not
just within their own community — `el_engine.py` does not (and,
per this finding, currently cannot) disambiguate by community. Worth
checking for name collisions before adding any new `effect create`
target role, the same way `any_discharged`/`triggered_by` scenarios
must check for the masked-sibling constraint. Not scheduled as an
engine fix (community-scoped target resolution) unless a real scenario
need for reusing a role name across communities actually arises.

---
