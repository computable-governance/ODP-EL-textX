# ODP-EL-textX changelog

All _notable_ changes to this project will be documented in this file.

The format is based on _[Keep a Changelog][keepachangelog]_, and this project
adheres to _[Semantic Versioning][semver]_.

## [Unreleased]

### Added

- **Token events in the ledger.** Each `TransitionRecord` has
  `token_events`: one `TokenEvent` per change its act made to a token
  instance (granted, removed, or a new state), with the tick, who made it
  and a cause. A `Runtime` has a `build_record` listing the tokens it
  starts from (by `model`), outside the ledger, and `history()`, the build
  record then the ledger. No effect line, reason, outcome or state
  changed. See "Token events in the ledger" in
  [docs/DSL_TOOLCHAIN_REFERENCE.md](docs/DSL_TOOLCHAIN_REFERENCE.md) and
  row R20 of [docs/ENGINE_VERIFIER_PARITY.md](docs/ENGINE_VERIFIER_PARITY.md).

## [2.2.0] - 2026-10-18

Equality in comparisons, date, instant and duration limits, deadlines that
name a duration policy, and options sets. Details per sub-change are in
[docs/el_grammar_amendments.md](docs/el_grammar_amendments.md) (entries
2.2.0-1 to 2.2.0-13); the rules are in
[docs/DSL_TOOLCHAIN_REFERENCE.md](docs/DSL_TOOLCHAIN_REFERENCE.md),
"Typed policy values (2.1.0)" (options sets), "Deadlines (2.1.0)" (a
duration policy) and "Comparisons (2.1.0)".

No 2.1.0 judging text changed: for what 2.1.0 accepts, the engine gives
the same verdicts, reasons and ledger lines. The 29 published specifications (the
13 shipped scenarios and the 16 examples in `tests/examples/`) give the
same parse results, errors, warnings and seeded policy values as in 2.1.0,
except one reworded message on one example (below, under "Changed").
Kripke world and edge counts and AF/EF verdicts are unchanged.

### Added

- **2.2.0-2, 2.2.0-3 `==` and `!=` in comparisons.** `precondition:
  "approvals" == 2`, `precondition: "insurance cover" != MinimumCover`, and
  the same in a standing duty's `keeps`. Exact equality of the values
  (`"2.0" == 2` holds); an amount in another currency is not established.
  `=>` stays a syntax error.
- **2.2.0-4 to 2.2.0-6 Date, instant and duration limits in comparisons.**
  `precondition: "certificate expiry" >= 2027-06-30`, `"notified at" <=
  2027-06-30T17:00+10:00`, `"notice given within" <= 24 hours`, or a policy
  of type date, instant or duration. Dates by calendar day, instants by
  moment, durations in minutes; a date is never compared with an instant.
  A duration limit is never signed (`+60 days` is a syntax error in a
  comparison; policy values still accept it). Invalid date or instant
  limits are reported by `calendar-date` and `instant-valid`.
- **2.2.0-7 to 2.2.0-9 `deadline: <Policy>`.** A token's deadline may name
  a Policy of type duration (`deadline: NoticePeriod`): the deadline is
  the policy's declared value, read-only, through one resolver
  (`el_engine.deadline_text()`) in the engine, both verifier builders and
  the validator's deadline warnings. Violation lines name the policy
  (`(policy NoticePeriod = 24 hours)`). New error `deadline-policy-type`.
  Parity row R19 added.
- **2.2.0-10 to 2.2.0-12 Options sets.** `options ApprovalStates [pending,
  approved, rejected]` declares the options of a user-defined policy type.
  A policy whose type names a declared options set takes one of its
  options (`policy-value-type` checks its initial value and envelope
  values); a type that names no options set stays unchecked and silent, as
  in 2.1.0. New errors `option-duplicate` and `option-set-name`. A
  comparison may use a policy of an options type as its limit, with `==`
  and `!=` only (`precondition: "approval" == RequiredState`); an ordering
  operator is a `comparison-type` error. Parity rows R12 and R17 reworded.
- **2.2.0-1 Golden test.** `tests/test_published_specs_unchanged.py` pins
  what the toolchain reports for the 29 published specifications.
- **2.2.0-13** The API reports version 2.2.0.

### Changed

- **Reworded `comparison-type` messages (2.2.0-4, 2.2.0-6), on invalid
  specifications only.**
  - An amount limit whose code is not in ISO 4217 form now ends "; a
    duration's unit is minute, hour, day, week, month or year" (was "; a
    duration cannot be compared").
  - A limit of another kind: "is not a number, percentage, amount, date,
    instant or duration" (was "is not a number, percentage or amount").
  - A policy limit of another type: "a comparison takes a policy of type
    integer, decimal, number, percentage, amount, date, instant or
    duration" (was "integer, decimal, number, percentage or amount").
  - The published example
    `tests/examples/comparisons/invalid_comparison_type.el` uses `60 sec`
    instead of `60 day`, which is now a valid duration; its message is the
    one reworded message among the published specifications.
- **New error `deadline-policy-type` (2.2.0-9).** A deadline that names a
  policy not of type duration, or a duration policy whose value is
  negative (`initial_value: -5 days`), is an error: `deadline NoticePeriod
  has value -5 days, not a usable duration (a whole number of a unit, not
  negative)`. Such a deadline is never measured, as for a token with no
  deadline. In 2.1.0 a deadline could not name a policy at all.
- **New keyword `options` (2.2.0-10)**, at the start of a top-level
  element. It is not reserved: a party, policy, role, option or
  specification named `options`, and references to it, parse as in 2.1.0.
  A syntax error at the position of a top-level element now lists
  `'options'` among the expected words.

### Limits

- Options are compared with `==` and `!=` only; they have no order. A
  comparison names a policy of the options type as its limit; there is no
  option literal (`"approval" == approved` names a Policy `approved`).
  Options sets are top-level; a second set with the same name is ignored,
  with no message. No string or boolean limits.
- A policy-fed deadline is the policy's declared `initial_value`; policy
  values stay read-only, and the verifier never reads
  `WorldState.policy_values`. A standing duty takes no deadline, and its
  term cannot be given as a duration (`term-end-type`).
- Values are compared, never computed: no arithmetic and no "date plus 30
  days". A month is 30 days and a year 365 for comparison.

## [2.1.0] - 2026-10-17

Typed policy values, date deadlines, comparisons and standing duties.
Details per sub-change are in
[docs/el_grammar_amendments.md](docs/el_grammar_amendments.md) (entries
2.1.0-1 to 2.1.0-25); the rules are in
[docs/DSL_TOOLCHAIN_REFERENCE.md](docs/DSL_TOOLCHAIN_REFERENCE.md),
"Typed policy values (2.1.0)", "Deadlines (2.1.0)", "Comparisons (2.1.0)"
and "Standing duties (2.1.0)".

### Added

- **2.1.0-1 Typed policy literals.** Policy values may be dates
  (`2026-11-30`), instants (`2026-11-30T17:00+10:00`), percentages
  (`4.25%`), amounts (`250.00 AUD`), integers and exact decimals. New type
  words `decimal`, `percentage`, `amount`, `date`, `instant`. An envelope
  may state a range: `range of [a to b]`.
- **2.1.0-2 Typed value checks.** Five validator rules:
  `policy-value-type`, `calendar-date`, `instant-valid`, `range-ends`,
  `currency-code`.
- **2.1.0-3 Read-only policy value seeding.** `WorldState.policy_values`
  and `WorldState.policy_value(name)`, seeded from each Policy's
  `initial_value` by `initial_state(spec)` and the Runtime builders.
- **2.1.0-4 Docs and examples.** The type table, shared examples in
  `tests/examples/typed_values/`, and seeding in the API scenario builders
  (except the superseded gp_referral).
- **2.1.0-5 Parity matrix.** `docs/ENGINE_VERIFIER_PARITY.md` records,
  row by row, where the verifier mirrors, abstracts or leaves out an engine
  rule about deadlines, the clock and policy values.
- **2.1.0-7 Date deadlines.** `DeadlineClock(utc_offset=...)` on
  `Runtime.build_from_spec()`/`build_from_federation()`, and
  `check_live_violations(as_at=...)`: a deadline that is a date alone
  (`"by 2026-11-30"`) or a date and time with an offset
  (`"2026-11-30T17:00+10:00"`) is judged against the caller's `as_at`.
  Without a clock or an `as_at` it is reported "not judged".
  `el_engine.not_judged_date_burdens()`.
- **2.1.0-8 Date-deadline warnings.** `[W-deadline-date-not-measured]`,
  `[W-deadline-date-invalid]`, `[W-deadline-several-durations]`.
- **2.1.0-9 `as_at` on `POST /check-violations`.** The response adds
  `as_at` and `not_judged`.
- **2.1.0-11 Comparison preconditions.** `precondition: "insurance cover"
  >= MinimumCover`: a reported value against a number, percentage or
  amount literal, or a policy; operators `>= <= > <`.
- **2.1.0-12 Comparison judging.** The reported text is read strictly
  (`"25000000.00 AUD"`, `"8.5%"`, `"5"`) and compared; a failing or
  unestablished comparison refuses the act with a reason, and a passed one
  adds `precondition satisfied: ...` to the act's effects.
- **2.1.0-13 Comparison and envelope validation.** Errors
  `comparison-type`, `fact-key-clash`, `comparison-in-step`,
  `envelope-currency`, `envelope-membership`.
- **2.1.0-14 Strict precondition guard.** Warning `[W-strict-precondition]`
  and the `assumes_preconditions` field on `GET /obligations/{token}/status`.
- **2.1.0-16 to 2.1.0-19 Standing duties.** `standing keeps: <comparison>
  [ends_at: …] [ended_by: …]`: a burden kept for a term, judged at each
  check against the reported facts (kept, breached, met, not judged); its
  term ends at a date or instant, or when an event fires. Errors
  `standing-fields`, `standing-in-group`, `term-end-type`; warnings
  `[W-standing-no-end]`, `[W-standing-shared-fact]`.
- **2.1.0-20 Standing duty guard.** `[W-standing-not-modelled]`; the status
  route answers "standing duty: not modelled" with `standing: true` and null
  `compelled`/`detectable`; the witness route refuses propositions that
  depend on a standing duty; recommendations never discharge one.
- **2.1.0-21 Facts on `POST /check-violations`.** Optional body `{"facts":
  {...}}`; the response adds `standing: [{token, holder, verdict, text}]`.
- **2.1.0-23** The recommended action's Q-values (its route and
  execute-action's `new_q_value`) are computed without the edges that
  discharge a standing duty; with only those edges and the tick, the
  recommendation is `tick`.

### Changed

- **2.1.0-1** An integer literal parses as `int` (in 2.0.0 it was a float)
  and a decimal as an exact `decimal.Decimal`. `1e3`, `+5`, `5.`, `.5` and
  non-ASCII digits are now syntax errors; durations and intervals are
  unchanged. A type name beginning with a type word (`integerCodes`) now
  parses.
- **2.1.0-2** A policy whose value does not match its type keyword is now
  an error.
- **2.1.0-6** A deadline containing a calendar date is never read as a
  duration. In v2.0.0 `"by 2026-11-30 end of day"` was enforced as 30 days
  after activation and `"within 5 days of 2026-11-30"` as 5 days, by the
  engine and the verifier, with no warning. They are no longer enforced by
  the clock.
- **2.1.0-7** A burden whose deadline contains a date is never violated by
  episode conclusion. In v2.0.0 `"by 2026-11-30"` was never enforced by
  time, but in an opted-in group it was violated when its episode
  concluded. Now it is judged only against `as_at`, under a clock.
  `check_live_violations()` effects may gain "not judged" lines for date
  burdens.
- **2.1.0-13** An initial value outside its envelope, of another kind, or
  in another currency than the envelope is now an error. In v2.0.0
  envelopes were not checked (`initial_value: 5` with `one of [1, 2, 3]`,
  or with `one of [1 day, 2 day]`, was accepted).
- **2.1.0-14** `gp_referral` and `referral` each gain one warning,
  `[W-strict-precondition]` on `referralInitiationBurden`; the scenarios
  are unchanged. The warning reports a verifier gap present since v2.0.0.
- **2.1.0-19** `[W-24]` no longer reports a standing duty.
- **2.1.0-20** `GET /obligations/{token}/status`: `compelled` and
  `detectable` may be null (only for a standing duty), and the response
  has a new field `standing` (false for every other burden).
- **2.1.0-8** `[W-25]` no longer fires on a deadline containing a date (in
  v2.0.0 `"by 2026-11-30"` drew a "no recognised time unit" warning), and
  `[W-24]` no longer fires on a measured date. A deadline with several
  durations (`"2 weeks and 3 days"`, enforced as its first part, as in
  v2.0.0) now warns.

### Limits

- Values are compared, never computed. Amounts are never converted
  between currencies. Durations go down to minutes; a month is 30 days and
  a year 365 for comparison. `60 days` is DSL notation, not ISO 8601.
- Policy values are read-only. The engine reads a policy's value only as
  a comparison limit or a standing duty's `ends_at`; the verifier does not
  read policy values. Envelopes are checked by the validator only.
- `as_at` is asserted by the caller: a future `as_at` violates a date
  burden early and irreversibly. One fixed UTC offset, no daylight saving
  or holidays. Durations stay on the step clock, dates on `as_at`, in one
  ledger. Strict date burdens are not judged. The verifier does not model
  date deadlines. No shipped scenario has a clock, and no shipped burden
  has a date deadline.
- Reported values in comparisons are trusted as given. The verifier
  assumes preconditions hold, so a strict burden's `compelled` can be true
  while the engine refuses its discharge (as in v2.0.0; now stated). Step
  preconditions are not enforced (as in v2.0.0). A plain precondition
  passes on any truthy fact, including the string "false" (as in v2.0.0).
- Standing duties are judged only at checks the caller runs, against
  values the caller reports; the verifier does not model them (its claims
  are withheld). In v2.0.0 a standing duty could not be written:
  `standing keeps:` is a syntax error, and a prose "for the term" deadline
  is never violated.

## [2.0.0] - 2026-09-28

First reference release of the ODP Enterprise Language (ISO/IEC 15414:2015,
ITU-T X.911) as a textX DSL for computable governance. The detailed,
per-amendment record (AM-1 to AM-115, with V-NEW validator rules and DOC
notes) is [docs/el_grammar_amendments.md](docs/el_grammar_amendments.md).

### Added

- **Grammar v2** (`grammar/v2/el_grammar.tx`): a single unified grammar
  covering communities, federations and domains, enterprise objects, roles
  and role fulfilment, deontic tokens (burden, permit, embargo) and token
  groups, policies, the accountability concepts (commitment, delegation,
  authorization, prescription, declaration, evaluation), violation responses
  and correspondences. Parsed straight into typed domain classes
  (`toolchain/el_domain.py`, `toolchain/el_parser.py`); the grammar is the
  schema.
- **Validator** (`toolchain/el_validator.py`): semantic checks, each traced
  to an ISO/IEC 15414 clause.
- **Reasoner** (`toolchain/el_reasoner.py`): ultimate accountability,
  can-perform and policy-conflict queries.
- **Runtime engine** (`toolchain/el_engine.py`, `toolchain/el_runtime.py`):
  stateless engine over an immutable WorldState with an append-only ledger;
  role-restricted actions (AM-114) and authorised violation declaration
  (AM-115).
- **Verifiers** (`toolchain/el_kripke.py`): Kripke verification after
  Annex C, in static (pre-execution) and hybrid (anchored to the current
  WorldState) modes; AF/EF/AG checks, `discharge_mode: strict`, and a Bellman
  planner.
- **Agent-facing API** (`toolchain/el_api.py`): REST endpoints for available
  actions, objective reachability and score, recommended action, action
  execution and reset.
- **FHIR R4 mapper** (`toolchain/fhir_mapper.py`): Layer 1 adapter from FHIR
  bundles to DSL-EL specifications.
- **Scenarios** (`scenarios/`, status per `scenarios/README.md`):
  - Reference: `consent/consent_scenario.el`, `referral/referral_scenario.el`.
  - Demo: `terms_of_engagement/external_agent_access_scenario.el`,
    `terms_of_engagement/public_data_portal_scenario.el`.
  - Probe: `consent/federation_consent_scenario.el`,
    `ereferral/ereferral_model.el`, `specialist_pool/specialist_pool_scenario.el`,
    `vendor/ai_vendor_probe.el`,
    `erequesting_claiming/erequesting_claiming_scenario.el`,
    `probes/transfer_probe.el`.
  - Generated: `fhir/generated_governance.el`.
  - Superseded: `gp_referral/gp_referral_scenario.el`.
  - Historical: `consent/consent.odpl` (v1 grammar),
    `ecommerce/ecommerce_scenario.el` (does not parse).
- Grammar v1 (`grammar/v1/`) is kept unchanged as published.

### Known limitations

- Install from source; packaging to follow.
- Hybrid-mode verification of "detectable" obligations: the verdict is correct,
  but the counterexample reported for AF and bounded-response checks is a
  revoke/reinstate cycle, not the deadline violation. The "detectable, not
  compelled" reading is shown in full only in static mode; in hybrid mode it
  appears through EF(violated). A fix is expected with the fairness work
  (weak fairness rules these cycles out).
- No watchdog runs: deadline violations are declared only by an explicit
  call to `declare_violation`; nothing in the toolchain monitors deadlines
  or invokes it automatically.
- Permits and embargoes declared outside an Authorization have no domain
  scope, and the `domain_scope` field on an Authorization is not checked.


[2.2.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.2.0
[2.1.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.1.0
[2.0.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.0.0


[keepachangelog]: https://keepachangelog.com/
[semver]: https://semver.org/spec/v2.0.0.html
