# DN_017 — Multi-parent authority join: tracing, signalling, and the
hand-off to application-level composition (AM-88 series)

**Status:** AM-88a, AM-88b, AM-88c and AM-89 through AM-93 implemented,
committed, and pushed. AM-94 implemented and committed locally, pending
push at time of writing. §7 steps 1 through 7 done.
**Relates to:** `toolchain/el_engine.py` (`_build_obligation_descriptors()`,
`walk_chain()`), `toolchain/el_kripke.py` (`_delegation_chain_for_token()`
— fallback, AM-91), `toolchain/el_validator.py` (V-08 — token-aware,
AM-92; W-16c, W-16d — AM-90; W-16e — AM-91; W-16f, the V-J1 permit-side
warning — AM-94),
`toolchain/el_parser.py` (`ParseResult` — `.warnings`, AM-89),
`toolchain/el_reasoner.py` (`parents_of()` — AM-90; `standing_parents_of()`
— AM-91; `permit_omissions()` — AM-94; `delegation_graph()` — reused by
AM-92), grammar rules
`EnterpriseObject`, `DelegatedFrom`, `Delegation`, `Authorization`.
**Found:** design session 2026-09-19, prompted by an external enquiry about
delegation graphs in which one child has more than one incoming parent.
**DN number is provisional** — confirm the next free number before logging.

---

## 1. Scope and non-goals

**In scope:** making the toolchain never silently follow a single lineage
when an agent has more than one parent; signalling that situation to the
spec author; and defining the hand-off to whatever composes scopes above
the toolchain.

**Non-goals (decided, see §4):** composing scopes or ceilings; adding scope,
ceiling or quantity constructs to the grammar; using policy envelopes for
ceilings; an `any_parent` (OR) composition mode; signature, key or
freshness evidence.

## 2. The problem: checks that follow one lineage

Two or more parents delegating to one child is a normal, legitimate
configuration. The failure is a check or trace that follows one lineage and
never consults the others, so its answer depends on which lineage it happened
to follow — often declaration order. Instances found by reading the code and
by live probes:

| # | Where | Behaviour | Status |
|---|---|---|---|
| 1 | engine `walk_chain()` | matched edges by obligation text and took `outgoing[0]`; one token's chain leaked onto another's onward delegation | fixed, AM-88a |
| 2 | engine descriptor `sub_delegation_allowed` / `revocable` | taken from the last-declared delegation targeting the holder, regardless of token | fixed, AM-88a (stored data only) |
| 3 | verifier AM-52 guard reachability | chased one `principal_of` pointer; verdict depended on party declaration order | fixed, AM-88b |
| 4 | verifier final chain extension | continued through the first-declared `principal_of` parent, giving a full-length chain with the wrong root | fixed for Commitment-rooted tokens, AM-88c |
| 5 | validator V-08 `_find_parent_delegation()` | checked only the first delegation targeting an agent; verdict flipped with declaration order | fixed, AM-92 |
| 6 | grammar `delegated_from` | single-valued; a second declaration is a syntax error | fixed, AM-93 |
| 7 | validator warnings | as the code read, `[W-…]` diagnostics shared the error list, so `ParseResult.ok` was false whenever one was emitted | fixed, AM-89 |

## 3. Standard basis (ISO/IEC 15414:2015)

- **One token, one holder (§6.4.1, §7.8.7).** A deontic token is held by
  exactly one active enterprise object. Therefore one linear chain per token
  is correct, and a chain-type change (a DAG per token) is not needed.
  Multi-parent is a property of the *agent*, not of the token.
- **Collective principals (§7.10.1).** Delegating parties collectively become
  principal of the agent, and a principal is responsible for the acts of its
  agent. This is the basis for multiple simultaneous parents.
- **Annex B.1.9.5 is not a precedent for simultaneous principals.** It models
  delegation by cloning tokens, and presents the agent as acting for one
  principal in one specification and for another "in a different enterprise
  specification" — alternatives, not both at once. A scenario declaring both
  merges the two.
- **The standard states neither attenuation nor a composition rule.** Any such
  rule is a design choice consistent with the standard, not required by it.
  Policy envelopes (§7.9.1) were considered as a home for ceilings; they are
  parsed but not consulted by the validator, engine or verifier today.

## 4. Decisions

1. **Per-token chains stay linear.** No change to `ObligationDescriptor.chain`.
2. **Composition semantics are a business rule, not part of the delegation
   pattern.** The toolchain does not compute minimums, intersections or any
   other combination of scopes across parents, and the grammar gains no
   ceiling or quantity construct. Where several permits are required, the spec
   author already chooses conjunction by listing each `requires_permit`; the
   engine, reasoner and verifier all gate on all of them.
3. **The toolchain's guarantee is enumeration and non-silence.** Every parent
   is traced, none is silently dropped or chosen, and a multi-parent child is
   surfaced to the spec author as a warning (§8).
4. **Revocation is absorbing.** Revoking one parent's grant must block, not
   widen: composition is over the declared parent set and a revoked parent
   contributes nothing. Already true for permit conjunction in the engine and
   verifier; verified by probe.
5. **Diagnostics are order-invariant.** The same facts must yield the same
   output regardless of declaration order. Where a choice is unavoidable it is
   made deterministically (sorted), or surfaced, never left to declaration
   order silently.
6. **Fixes match structure, not text.** Descriptor tracing matches
   delegations by the token they transfer (with the AM-52 guard for group
   transfers), not by obligation-text substring.
7. **`any_parent` (OR) composition is deferred** until it can be implemented
   at every layer; grammar surface with no semantics behind it is the
   parsed-but-inert pattern already seen with `JoinLeaveEffect`.
8. **Warnings are advisory and never affect `.ok`.** `[W-…]` diagnostics are
   routed to a separate `ParseResult.warnings` list by prefix, not mixed
   into `.errors` — `validate_spec()` itself is untouched (AM-89). This is
   what makes decision 3's "surfaced as a warning" actually true rather
   than aborting the load.

## 5. Implemented

| Amendment | Layer | Change | Gate |
|---|---|---|---|
| AM-88a (`7b309ef`, docstring `0f876c4`) | engine | structural, per-token `walk_chain()`; per-token `sub_delegation_allowed`/`revocable`; `_commitment_root_for_token()` added | descriptors byte-identical on 37 descriptors / 14 files; suite 393 → 412 |
| AM-88b (`e5c55e5`) | verifier | multi-map BFS reachability in the AM-52 guard; imports the engine's `_commitment_root_for_token()` | 37 chain pairs identical; suite 418 |
| AM-88c (`e9fa28b`) | verifier | final extension prefers the token's own Commitment actor | 37 chain pairs identical; suite 424 |
| AM-89 (`56939b9`) | parser | `ParseResult.warnings` added; `parse()` splits `[W-…]` by prefix; `validate_spec()` untouched; both CLIs (`el_reasoner.py`, `fhir_mapper.py`) print warnings, unaffected exit status | suite 424 → 433 |
| AM-90 (`51416f8`) | reasoner + validator | `el_reasoner.parents_of()` (shared query); `[W-16c]` multi-parent notice, `[W-16d]` same-token conflict, both built from it | zero hits on tracked corpus; order-invariant across all permutations; suite 433 → 447 |
| AM-91 (`f445ae3`) | reasoner + validator + verifier | `el_reasoner.standing_parents_of()` (shared query); `[W-16e]` standing-`principal_of` multi-parent notice; `_delegation_chain_for_token()`'s no-Commitment fallback becomes `sorted(candidates)[0]` | one real corpus hit (`federation_consent_scenario.el`, true positive, pinned); byte-identical on the 25-pair public snapshot; order-invariant and message/behaviour-parity tested; suite 448 → 461 |
| AM-92 (`85c3de2`) | validator | V-08 becomes token-aware (S1) with an order-independent conservative fallback (S2); `_find_parent_delegation()` deleted | zero diffs on tracked corpus (old vs. new); order-invariant across all permutations of a multi-error spec; suite 461 → 475 |
| AM-93 (`ae01801`) | grammar + parser + reasoner + verifier | `ObjectBody` takes `(delegated_from+=DelegatedFrom)*`; the model keeps a `List[DelegatedFrom]`; both `_is_standing_affiliation` twins use set membership (order-independent, duplicates accepted) | errors/warnings of the three named scenarios byte-identical; twins parity-tested over a 40-agent truth table, plus two mutation checks; FHIR mapper output byte-identical (golden test); suite 475 → 492 |
| AM-94 (`995ed66`) | reasoner + validator | `[W-16f]`: an Action requires part of a permit set co-granted to one target (normalized non-empty `domain_scope`, >=2 distinct authorities) and leaves an authority unconsulted (authority-based); three read-only `el_reasoner` queries, message built from `permit_omissions()`; role Action bodies only (ConditionalAction excluded, §6) | corpus byte-identical, zero hits (3 Authorizations, no co-granted set); order-invariant across all permutations; query/message equality and verifier-index parity tested; suite 492 → 514 |

Tests: `tests/test_am88a_multi_parent_tracing.py`,
`tests/test_am88b_guard_multi_parent_reachability.py`,
`tests/test_am88c_multi_parent_chain_extension.py`,
`tests/test_am89_warnings_channel.py`,
`tests/test_am90_multi_parent_warnings.py`,
`tests/test_am91_standing_parent_warnings.py`,
`tests/test_am92_v08_token_aware.py`,
`tests/test_am93_delegated_from_list.py`,
`tests/test_am94_partial_permit_requirement.py`, plus two snapshot fixtures
in `tests/fixtures/`. Full detail: `docs/el_grammar_amendments.md`,
`docs/CONCEPTS_INDEX.md`.

Portability note: the gate above ran over 37 descriptors/chain pairs
including 12 from four local-only `scenarios/industrial_procedure/` files
(untracked, excluded via local `.git/info/exclude`); the pinned public
snapshot fixtures cover the 25 from tracked scenarios, and the tests
iterate the snapshot's own file list rather than a local glob so the gate
holds identically on a clean clone (`760f99c`).

## 6. Logged, not fixed

- More than one structurally matching delegation for one token from one node
  is ill-formed (§6.4.1/§7.8.7) and is silently resolved by declaration order
  in both `walk_chain()` and `_delegation_chain_for_token()`.
- ~~A multi-principal token with **no Commitment** still has an
  order-dependent exported chain, and AM-90's `[W-16c]` doesn't cover a
  purely `principal_of`-based multi-parent structure.~~ **Resolved by
  AM-91**: the fallback is now `sorted(candidates)[0]` (deterministic),
  and `[W-16e]` names the agent's standing parents. See §10.
- `_is_standing_affiliation()` exists as independent twins in the verifier and
  reasoner. ~~Both read the single-valued `delegated_from`.~~ **Changed by
  AM-93**: both now read the list with set semantics (a principal is
  standing iff it is not among ANY entry's delegator). They remain
  independent copies — unifying them is out of scope — pinned together by a
  parity truth-table test.
- `scenarios/ecommerce/ecommerce_scenario.el` does not parse, before or
  after AM-93. Its second `delegated_from` (the originally reported error)
  is now grammatical, but the file has further pre-AM-17 stale constructs
  and an undeclared `Customer`; it is not a corpus member for any check in
  this series and no test loads it. Archive-vs-rewrite is an open item in
  `docs/CONCEPTS_INDEX.md`.
- `ConditionalAction.requires_permits` is set by the parser and read by
  nothing, so a `requires_permit` on a ConditionalAction gates nothing.
  The three loops that would consume ConditionalAction data
  (`el_engine.py:898`, `el_kripke.py:503`, `el_kripke.py:1603`) iterate
  `action.conditional_actions`, a field that exists only on `Role`, so they
  never run (and would read `favoured_by`/`inhibited_by`, not
  `requires_permits`, if they did). `[W-16f]` (AM-94) therefore covers role
  Action bodies only: advising "add the missing requires_permit" would
  change nothing on a ConditionalAction. Logged, not fixed; open finding in
  `docs/CONCEPTS_INDEX.md`.
- Pre-exec and hybrid verifier modes differ on `principal_of`-rooted tokens
  (the engine does not extend through `principal_of`); pre-existing.
- Descriptor `sub_delegation_allowed`/`revocable` have no control-flow
  consumer today; the AM-88a fix corrects stored data only.
- No API/UI validation surface exists. `el_api.py` never calls
  `validate_spec()` at all (every one of its `parse()` calls uses
  `validate=False`), and no HTTP endpoint returns validation messages to a
  caller. A spec author reaches `[W-16c]`/`[W-16d]`/`[W-16e]`/`[W-16f]` (or `[W-16b]`)
  only via `ParseResult.warnings` directly, or via `el_reasoner.py`'s and
  `fhir_mapper.py`'s CLIs, which print them to stderr.

## 7. Proposed next steps (in order)

1. **Warnings channel — done (AM-89).** Confirmed live that a `[W-…]`
   diagnostic made `ParseResult.ok` false; `ParseResult.warnings` added,
   `[W-…]` strings routed there by `parse()` (prefix split, `validate_spec()`
   itself untouched), `ok` now ignores them. Prerequisite for step 2, which
   remains open. Full detail: `docs/el_grammar_amendments.md`, AM-89.
2. **W-16c and W-16d — done (AM-90).** W-16c triggers on ≥2 DISTINCT parents
   (not delegation count — one delegator with two Delegations to the same
   delegate does not trigger), lists every parent (sorted) with each of its
   delegations and tokens, and adds a separate permit-line clause for
   co-granted Authorizations (worded as authority sources, not principals —
   AM-31 §4.0b). Structural `principal_of` parents and `to_role`
   Authorizations are documented out of scope, not counted. W-16d: the same
   token transferred to one delegate by ≥2 distinct Delegations, or by one
   delegator to ≥2 different delegates (sequential chains excluded by
   construction). Zero hits on the tracked corpus, confirmed live.
3. **V-08 — done (AM-92).** The sub-delegation check is now token-aware
   (checks only the incoming Delegation(s) that structurally transfer the
   same token being sub-delegated) with a conservative, order-independent
   fallback (every incoming Delegation must permit) when no incoming
   Delegation makes any structural claim on the token at all.
   `_find_parent_delegation()` deleted. Zero diffs against the pre-AM-92
   verdict on the tracked corpus.
4. **Parents query — done (AM-90).** `el_reasoner.parents_of(model,
   agent_name)` returns every incoming Delegation (parent, delegation name,
   tokens, `sub_delegation_allowed`, `revocable`) plus co-granted
   Authorizations, deterministic and sorted; the W-16c/W-16d warnings are
   built from this exact query, so message and API cannot diverge.
5. **`delegated_from` as a list — done (AM-93).**
   `(delegated_from+=DelegatedFrom)*`, declarative only. The model keeps a
   `List[DelegatedFrom]` (`.delegator` + `.duration` together;
   `delegation_duration` dropped). A four-file ripple, not five: parser P2,
   the reasoner and verifier `_is_standing_affiliation` twins (identical
   set-membership bodies; a delegator listed twice is accepted, no
   de-duplication), and the domain dataclasses. The FHIR mapper needed no
   change (its own single-valued model, valid output, no generated agent is
   the delegate of two distinct delegators). A reader that still assumed
   one value would silently class every paired `principal_of` as standing,
   which is why the twin change was mandatory. The child-side
   complete-parent-set check floated here was **not** done — out of scope
   for AM-93 and still open after a corpus check (`delegated_from` is not
   always paired). Full detail: `docs/el_grammar_amendments.md`, AM-93.
6. **V-J1 — done (AM-94, as `[W-16f]`).** Warns when an Action requires >=1
   permit of a set co-granted to one target (`to_agent` or `to_role`,
   separate namespaces) in one normalized non-empty `domain_scope` by >=2
   distinct authorities, and some authority of the set has none of its
   permits required (authority-based: an authority whose permit the Action
   names is consulted). Built from a new `el_reasoner.permit_omissions()`
   query, so message and query cannot diverge. Role Action bodies only —
   ConditionalAction is excluded (§6). Zero hits on the tracked corpus
   (3 Authorizations, no co-granted set). Full detail:
   `docs/el_grammar_amendments.md`, AM-94.
7. **Standing `principal_of` multi-parent — done (AM-91).** `[W-16e]` warns
   on an agent with ≥2 standing `principal_of` parents (not covered by
   W-16c, which only counts genuine `Delegation`-based parents), built
   from a new `el_reasoner.standing_parents_of()` query. Paired with a
   deterministic `sorted(candidates)[0]` fallback in
   `_delegation_chain_for_token()`, replacing first-declared-wins for the
   no-Commitment case — closes the AM-88c residual (§6). One real hit on
   the tracked corpus (`federation_consent_scenario.el`), a true positive,
   scenario unmodified. Full detail: `docs/el_grammar_amendments.md`, AM-91.

## 8. The hand-off contract

**The toolchain guarantees:** every parent of a child is traced; declaration
order does not change the output for Commitment-rooted tokens; a multi-parent
child produces a warning listing all parents; a revoked or missing permit
blocks an action that requires it.

**The toolchain does not:** compose, compare or bound scopes across parents;
decide whether a child's scope "fits" its parents; or pick a composition rule
(minimum, intersection, union, quorum, separation of duty).

**The application must:** enumerate the parents, apply its own composition
rule, and encode any per-parent condition (for example a numeric limit) as a
per-parent permit or precondition supplied as facts. Two ways in, kept in
sync by construction (AM-90 — same underlying query, no twin logic):
- **Read warnings from `ParseResult.warnings`** (AM-89) — `[W-16c]`/`[W-16d]`
  are advisory, never affect `.ok`, and are printed by `el_reasoner.py`'s
  and `fhir_mapper.py`'s CLIs; anyone calling `parse()`/`parse_string()`
  directly reads them off the returned `ParseResult`.
- **Call `el_reasoner.parents_of(model, agent_name)`** directly for a
  structured, deterministic, sorted answer (parent, delegation name,
  tokens, `sub_delegation_allowed`, `revocable`, plus co-granted
  Authorizations) — the same data the warning text is built from.

Actual `[W-16c]` wording (AM-90; supersedes the draft this section
originally sketched):
`[W-16c] Agent 'X' has 2 parents: P1 (d1 -> t1), P2 (d2 -> t2). Principals
are collectively responsible (§7.10.1). If these parents' authorities
overlap, how they combine is application-defined; the toolchain does not
compose them. Permits granted to 'X' (authority sources, not necessarily
principals): A1 (P1: p1). See el_reasoner.parents_of(model, 'X').`

## 9. Verification discipline

Recon first, read-only. Each amendment gated by a byte-identical snapshot
over the whole scenario corpus, declaration-order permutation tests, and
engine/verifier parity tests limited to intended-equal cases. A predicate
prototyped against the corpus before implementation caught one wrong premise
(an unguarded group match changed two descriptors in the superseded
referral scenario), and a probe caught one more (the verifier's own guard was
order-dependent). Keep external names, papers and figures out of code,
comments, docs, tests and commit messages; use "multi-parent authority join".

**Clean-worktree lesson (from a reported failure on a public clone):** a
byte-identical snapshot test that globs `scenarios/**/*.el` passes locally
but fails on a clean clone if the local checkout has additional,
untracked scenario files a public clone never has — some local checkouts
carry extra scenarios under `.git/info/exclude`, which is itself never
shared. The fix: a snapshot-gated test must iterate the **snapshot
fixture's own file list**, not a glob, and no tracked fixture may ever
contain entries from a local-only scenario. Every AM-88/89/90 gate since
has additionally been run in a clean `git worktree add` checkout with the
diff applied (not committed) before commit, specifically to catch this
class of bug before it reaches a public clone.

## 10. Open decisions for the maintainer

- **No-Commitment fallback — resolved: AM-91.** AM-90's `[W-16c]` does not
  count structural `principal_of` parents (documented scope — it only
  covers genuine `Delegation`-based parents), so an agent whose only
  multi-parent structure was ≥2 `principal_of` parents, where a token
  among them has no `Commitment` of its own, used to be BOTH
  order-dependent AND unwarned. AM-91 closed both: `[W-16e]` names an
  agent's ≥2 standing `principal_of` parents (sorted), noting that the
  exported chain for a Commitment-less token among them names only one of
  them; `_delegation_chain_for_token()`'s fallback for that same case is
  now `sorted(candidates)[0]`, replacing first-declared-wins. A dedicated
  parity test ties the two together so they cannot silently diverge.
- **W-16d severity — decided: warning.** Implemented as advisory (AM-90),
  consistent with W-16c and the AM-89 warnings channel.
- **Grouping key for V-J1 — decided: AM-94.** Same target (`to_agent` or
  `to_role`, separate namespaces) plus a trimmed, case-insensitive
  non-empty `domain_scope`, from >=2 distinct authorities. `domain_scope`
  stays free text, so a typo silently splits a set (documented fail-open);
  AM-14 (typed cross-reference) remains a separate improvement, not a
  prerequisite.
- **Parents query.** Shape and home — decided and implemented:
  `el_reasoner.parents_of(model, agent_name)` (AM-90).
- **Push timing.** AM-88a/b/c and AM-89 through AM-93 pushed. AM-94
  was pending push at time of writing (committed locally as its own
  individually-gated commit); the external reply that tracing is fixed is
  the maintainer's own next action, not part of this series' scope.
