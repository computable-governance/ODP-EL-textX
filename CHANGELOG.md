# ODP-EL-textX changelog

All _notable_ changes to this project will be documented in this file.

The format is based on _[Keep a Changelog][keepachangelog]_, and this project
adheres to _[Semantic Versioning][semver]_.

## [2.5.1] - 2026-11-13

### Changed

- The message of the validator error `[response-permit-authority]` now ends
  "(clause to be confirmed)" instead of citing §6.6.4 and §7.8.6, since no
  clause says that only the grantor may suspend or end a permit. V-NEW-23
  keeps its own citation.
- The advice of `[W-breach-response-duty]` now ends "or a revokes, suspends or
  expires line".
- `[W-21]` no longer fires on a terminate response with a `suspends:` or
  `expires:` line, since those lines act when the response fires.

None of the published specifications gets any of these messages, so their
results are unchanged.

## [2.5.0] - 2026-11-06

Permit time limits and violation responses that act on a permit (2.5.0-1 and
2.5.0-2). A permit's `deadline` is now enforced, and a permit whose time is up
moves to a new state, `expired`. A violation response can now suspend or
expire the permit an Authorization grants. No verifier code changed. Details
are in [docs/el_grammar_amendments.md](docs/el_grammar_amendments.md) (entries
2.5.0-1 and 2.5.0-2) and in "Permit time limits (2.5.0)" and "Violation
responses that suspend or expire a permit (2.5.0)" in
[docs/DSL_TOOLCHAIN_REFERENCE.md](docs/DSL_TOOLCHAIN_REFERENCE.md).

### Added

- **A permit's time limit is enforced.** A permit's `deadline` (a duration, a
  date or instant, or a duration policy) is now a time limit. A duration limit
  is checked at use and at the sweep (`check_live_violations()`), counted in
  steps from the instance's first activation. A date or instant limit is
  checked at the sweep only, against the caller's `as_at`, and only when the
  runtime has a `DeadlineClock`.
- **New permit state `expired`.** The sweep moves a permit whose time is up to
  `expired`, with the line `expired permit 'P' held by 'H' (...)` and one
  token event with cause `deadline`. `expired` is final for that instance:
  only a new grant (a new instance) brings the permit back. It is not
  `lapsed`, which is a claimable token whose sibling was claimed.
- **Validator warning `[W-authorization-duration]`.** An Authorization's
  `duration` is recorded and not enforced, so it does not limit the permit it
  grants. It fires 7 times on the published specifications; the
  published-specs golden records them.
- **Validator warning `[W-strict-timed-permit]`.** A strict burden whose
  discharge needs a permit with a time limit can get stuck once the time is
  up. It fires on none of the published specifications.
- **A violation response can suspend or expire a permit.** Two new optional
  clauses on a ViolationResponse, `suspends:` and `expires:`, each name one
  Authorization per line and are written after `revokes:`. When the response
  fires, `suspends:` moves the permit that Authorization grants from active to
  pending, and `expires:` moves it from active or pending to `expired`. They
  act on the Authorization's `to_agent`, or on each actor filling its
  `to_role`, and never on another holder's instance. An instance in any other
  state does not change and gets note lines, for example `suspend 'P' had no
  effect: 'H' holds it expired`. No embargo is touched, and the Authorization
  need not be revocable. A response's `expires:` is a second way into
  `expired`, beside the sweep; `expired` stays final for that instance.
- **Validator error `[response-permit-authority]`.** Each Authorization a
  response names in `suspends:` or `expires:` must be granted by the
  response's `obligates`. The engine repeats the check when the response
  fires. It fires on none of the published specifications. The validator now
  has 82 rules: 47 errors and 35 warnings.

### Changed

- **A use past the limit is refused.** This changes behaviour. The act is
  `blocked` with the reason `required permit 'P' time has elapsed for actor`,
  and the permit's state is unchanged (it stays `active` until the sweep).
- **The sweep moves the tick when it expires a permit.** A sweep that only
  expires permits moves the tick once; its outcome stays `ok`.
- **Revoke and reinstate on an expired permit.** This changes behaviour. A
  reinstate of an Authorization whose permit instances are all expired is
  refused (outcome `blocked`, reason `permit 'P' has expired; only a new grant
  restores it`). A revoke of one changes nothing: outcome `ok`, a note line
  `revoke 'P' had no effect: 'H' holds it expired`, no embargo, no tick.
  Beside other instances, revoke and reinstate skip the expired ones.
- **The status route withholds `compelled` for a strict burden gated on a
  timed permit.** `GET /obligations/{token_name}/status` answers `compelled:
  null` with status `permit time limit: not modelled`, in both modes, for a
  strict burden any of whose discharging actions requires a permit with a
  time limit (parity row R28): the model has no permit time, so it can offer
  a discharge the engine refuses. Other strict burdens are unchanged by this
  rule; a permit that a violation response suspends or expires is withheld
  too (below).
- **The status route withholds `compelled` for a permit a response suspends
  or expires.** `GET /obligations/{token_name}/status` answers `compelled:
  null` with status `permit suspension or expiry by a response: not
  modelled`, in both modes and whether or not the response has fired, for a
  strict burden any of whose discharging actions requires a permit granted by
  an Authorization that a response names in `suspends:` or `expires:` (parity
  row R31). The verifier reads neither clause. Only `compelled` is withheld;
  `detectable` and the paths stay as computed. A time limit takes precedence.
  After a firing, the hybrid model's correct `false` is withheld too. A
  permit named only by `revokes:` is not covered.
- **`[W-breach-response-duty]` no longer fires on a response with
  `suspends:` or `expires:`.** Its printed advice is unchanged.

### Fixed

- **The FHIR consent handler reports a refused event as refused.** Before, it
  never read the engine's outcome, so a refused event was reported as
  `already_active` (status active) or `revoked` (status inactive). Now a
  refusal reports the new label `blocked`, with the engine's reason in the
  message, and an inactive event on a permit whose instances are all expired
  reports the new label `already_expired`. `POST /fhir/consent-events` stamps
  provenance on a token for neither label.

### Known limits

- No route re-grants a permit; a clone or a transfer keeps the old start tick.
- A strict burden gated on a timed permit can get stuck once the time is up
  (the validator warns), and a limit with no measurable magnitude (for example
  `"thirty days"`) never elapses.
- A reinstate of an Authorization with no `on_revocation` embargo raises an
  error, so a permit suspended under such an Authorization comes back only by
  `effect activate` or by its triggering event.
- A restore acts by permit name across holders, so with several holders a
  suspended instance can stay pending after a reinstate.
- A terminate response with `suspends:` or `expires:` and no `revokes:` can
  still get the warning that it "would fire and do nothing" although the
  clauses act.
- A response's `suspends:` or `expires:` on the permit a strict burden's
  discharge needs can leave the burden stuck, as an expired permit can; the
  status route withholds `compelled` for it.

### Documentation

- New Reference sections "Permit time limits (2.5.0)" and "Violation
  responses that suspend or expire a permit (2.5.0)" in
  [docs/DSL_TOOLCHAIN_REFERENCE.md](docs/DSL_TOOLCHAIN_REFERENCE.md); parity
  rows R26, R28, R29, R30 and R31 in
  [docs/ENGINE_VERIFIER_PARITY.md](docs/ENGINE_VERIFIER_PARITY.md); the
  Concepts Index and `CLAUDE.md` updated; an explainer page,
  [docs/explainers/permit_time_limits.html](docs/explainers/permit_time_limits.html).

No verifier code changed in 2.5.0-1 or 2.5.0-2. None of the published
specifications uses `suspends:` or `expires:`, so 2.5.0-2 changes none of
their parse results, errors, warnings or status-route answers.

## [2.4.1] - 2026-11-05

### Fixed

- **`effect activate` no longer re-opens a closed burden.** This changes
  behaviour. The effect now acts only on pending instances. Before, a violated
  or discharged burden went back to active with a new activation tick and a
  restarted deadline. Now its state, tick and deadline stay unchanged, the act
  still returns ok, and a note line says so: `activate 'X' had no effect: 'H'
  holds it violated`.
- **`effect pend` moves only active instances.** This changes behaviour. Before,
  a pend moved an instance in any state to pending, so a closed burden could be
  pended and then activated. Now an instance in any other state is unchanged,
  and the line `pended 'X'` is written only when an instance moved.
- **The ereferral scenario shows the difference.** Repeating
  `acknowledgeReferral` after `submitReferral`, `acknowledgeReferral` and
  `scheduleAssessment` used to re-open the discharged `examinationBurden`
  (state active, activation tick moved from 1 to 3). Now the burden stays
  discharged and the act writes the note line.

No verifier code changed. Verifier results are identical to 2.4.0 on the 30
published specifications (29 static models built; `ecommerce_scenario.el` does
not parse at either) and on the six API scenarios.

## [2.4.0] - 2026-11-04

An action that fills a role (`effect fill`), a validator warning for a burden
with no root, and the procurement tender rewritten around a contractor role.
An act with no fill line behaves as in 2.3.0, record and state alike. Apart
from the tender, the 30 published specifications (the 14 shipped scenarios and
the 16 examples in `tests/examples/`) give the same parse results, errors,
warnings and seeded policy values as 2.3.0, except for the added warning. That
warning fires on 5 of the 30 (8 warnings), one of them on the tender, which also
parses with no errors and keeps its policy values; its other warnings change
(see Added). No verifier code
changed, and Kripke world and edge counts are unchanged on all 23 builds
measured (static models of the tracked scenarios that parse, and hybrid models
of the six API scenarios and the referral scenario at its deadline scale).
Details per sub-change are in
[docs/el_grammar_amendments.md](docs/el_grammar_amendments.md) (entries
2.4.0-1 to 2.4.0-6).

Thanks to Andy Bond for the procurement tender scenario
(`scenarios/procurement_tender/`, PR 2).

### Added

- **Validator warning `[W-burden-not-modelled]`.** A burden with no root:
  no Commitment, ViolationResponse `creates_burden`, Authorization
  `creates_burden_on_authority` or Delegation `transfers_token_group`
  creates it for a holder, so the pre-execution model has no obligation for
  it and the verifier gives no verdict on it. The specification still
  validates (`.ok` unchanged). It fires on 5 of the 30 published
  specifications (8 warnings): the ereferral model (4), the two
  terms_of_engagement scenarios (1 each), one standing-duty example (1)
  and, since 2.4.0-5, the procurement tender (1, on
  `incidentNotificationBurden`); the published-specs golden records them. Kripke world and edge counts
  are unchanged. See "Burdens the
  verifier does not model" in
  [docs/DSL_TOOLCHAIN_REFERENCE.md](docs/DSL_TOOLCHAIN_REFERENCE.md) and
  entry 2.4.0-1 in
  [docs/el_grammar_amendments.md](docs/el_grammar_amendments.md).
- **An action fills a role: `effect fill <Role> with <Object>`.** A new
  action-body line (action bodies only, one fill per line): when the
  action is performed, the object comes to fill the role (§7.6.2, §7.6.3,
  §7.8.2). The engine checks every fill after the permit check (Step 6b):
  the role is declared in exactly one community, at most one object fills
  it and a filled role is not refilled, and `excludes_role` applies both
  ways; a refusal blocks the whole act, with state and tick unchanged.
  Then the filler is enrolled and the role's `on_join` tokens are granted
  in their declared state at the act's tick (token events cause
  `on_join`). A claim of a burden whose action fills a role fills it too.
  No leave or refill; `requires_capability`, `requires_token` and
  `requires_relation` are not judged; build-time `fills` stay unchecked;
  the verifier does not model the fill (row R27 of
  [docs/ENGINE_VERIFIER_PARITY.md](docs/ENGINE_VERIFIER_PARITY.md)). See
  "Filling a role by an action" in
  [docs/DSL_TOOLCHAIN_REFERENCE.md](docs/DSL_TOOLCHAIN_REFERENCE.md),
  which also lists the design decisions that are ours and not the
  standard's, and entries 2.4.0-2 to 2.4.0-6 in
  [docs/el_grammar_amendments.md](docs/el_grammar_amendments.md).
- **Validator rules for role fills.** Error `[fill-one-filler]` (one
  action fills a role twice); warnings `[W-fill-role-filled]` (the role is
  already filled by a `fills` statement), `[W-fill-excluded-role]` (an
  `excludes_role` makes the fill always refused) and
  `[W-fill-not-modelled]` (once per role an action fills). `[W-27]`,
  `[W-28]` and `[W-29]` count an effect fill as a possible filler, and
  `[W-burden-not-modelled]` gives an on_join hint.
- **The procurement tender rewritten with a contractor role.** The award
  fills `contractorRole`, whose `on_join` tokens carry the contractor's
  duties, written once (534 → 432 lines). README limit 2 is rewritten (a
  role is filled once and not left; the verifier does not model the
  fill); limit 4 no longer needs a workaround, because on_join grants in
  the declared state. Three expected warnings.
- Kripke world and edge counts unchanged on all builds; the tender's
  static model has 4 fewer obligations. The validator has 79 rules (46
  errors, 33 warnings).

### Fixed

- **The procurement tender's cover duty ended at acceptance.** Accepting
  the award (`claim()`) runs the bid's action, which emitted the
  completion event and so ended the public liability cover duty at once.
  The completion event now comes from a buyer act, `certifyCompletion`.

## [2.3.0] - 2026-10-30

Token events in the ledger, violation records for permits and embargoes,
refused attempts recorded as violations, and the verifier's check of every
permit an action requires. No 2.2.0 verdict, reason or ledger line changed
for what 2.2.0 accepts. The 30 published specifications (the 14 shipped
scenarios and the 16 examples in `tests/examples/`) give the same parse
results, errors, warnings and seeded policy values; the new warnings fire on
none of them. Kripke world and edge counts and AF/EF verdicts are unchanged
for the shipped scenarios (measured: static and hybrid models of the six API
scenarios and the consent scenario); the T5 fix below changes the model
only for an action that requires more than one permit, which none of them
has. Details per sub-change are in
[docs/el_grammar_amendments.md](docs/el_grammar_amendments.md) (entries
2.3.0-1 to 2.3.0-12).

Thanks to Andy Bond for the procurement tender scenario
(`scenarios/procurement_tender/`, PR 2).

### Added

- **Token events in the ledger.** Each `TransitionRecord` has
  `token_events`: one `TokenEvent` per change its act made to a token
  instance (granted, removed, or a new state), with the tick, who made it
  and a cause. A `Runtime` has a `build_record` listing the tokens it
  starts from (by `model`), outside the ledger, and `history()`, the build
  record then the ledger. `Runtime.in_force_at(token, holder, tick)` and
  `Runtime.token_states_at(...)` answer from those events whether a token
  was in force when an act at a tick was judged (`None` when the history
  does not reproduce the current state). No effect line, reason, outcome
  or state changed. See "Token events in the ledger" in
  [docs/DSL_TOOLCHAIN_REFERENCE.md](docs/DSL_TOOLCHAIN_REFERENCE.md) and
  row R20 of [docs/ENGINE_VERIFIER_PARITY.md](docs/ENGINE_VERIFIER_PARITY.md).
- **The token that refused an act.** A blocked record's `blocked_by`
  (`TokenRef`) names the embargo (Step 5) or the required permit (Step 6)
  that refused it, in `advance()` and `declare_violation()`; other
  refusals leave it `None`. The reason text is unchanged. Same section of
  the reference, and row R21 of
  [docs/ENGINE_VERIFIER_PARITY.md](docs/ENGINE_VERIFIER_PARITY.md).
- **Violation records for permits and embargoes.** A violation of an
  embargo (its holder performed an action it covers), of a permit (a third
  party prevented the holder's permitted action) or of a permit
  requirement (the actor acted without the permit the action requires) is
  declared with `Runtime.declare_breach()` and recorded as a
  `ViolationRecord`, in the record's `violation_records` and in
  `WorldState.violation_records`; no token changes state and the tick does
  not advance. The declarer passes the checks a burden's declaration
  applies and may not be the violator; whether each token was in force at
  the occurrence is read from the token events (unknown history: accepted
  with a warning); a prevention justified by an embargo on the permit's
  holder is refused (Annex B.1.7.4); one occurrence is recorded once.
  ViolationResponses on a permit or embargo fire once per occurrence; the
  new optional `also_on_refused_attempts: true` extends that to refused
  attempts. Kripke: absent (rows R22 to R25). See
  "Violation records" in
  [docs/DSL_TOOLCHAIN_REFERENCE.md](docs/DSL_TOOLCHAIN_REFERENCE.md);
  entries 2.3.0-1 to 2.3.0-9 in
  [docs/el_grammar_amendments.md](docs/el_grammar_amendments.md).
- **Refused attempts recorded as violations.** A refusal by
  `Runtime.advance()` at Step 5 (an active embargo) or Step 6 (a required
  permit not held) is also recorded as a `ViolationRecord` with source
  `refused_attempt`, declared by `system`, at the current step; the
  reason, `blocked_by`, tokens and tick are unchanged, and one effect line
  is added. A repeat at the same step adds no record. The keyword
  `record_refused_attempts` of `el_engine.advance()` is off by default, so
  engine calls and dry runs record nothing; `claim()`, `decline()` and
  declarers' refusals are never recorded. This is a design extension that
  follows the definition of violation (§6.3.8), not something the
  standard states.
- **Validator warnings** `[W-breach-response-duty]`,
  `[W-refused-attempts-burden]` and `[W-breach-undeclarable]`; 74 rules
  (45 errors, 29 warnings).

### Changed

- **V-NEW-24** accepts a permit or an embargo as the target of
  `declares_violation_of`; the error "only a burden can be violated" is
  removed. A burden target must still be strict, and the declaring Action
  must still require a permit.
- `advance()` and `declare_violation()` share one embargo and permit
  check; no reason text changed.
- A violation record's identity holds its source
  (`ViolationRecord.identity`; `ViolationRecord.occurrence` is the
  occurrence alone). A declaration of an occurrence recorded as a refused
  attempt is accepted as a second record, with the line `confirms the
  refused attempt recorded at step N`; a response fires once per
  occurrence (deliberately, not once per record).

### Fixed

- **Kripke T5 requires every permit the action requires.** Before, T5
  (exercise) checked only the permit being exercised, while T6 (examine)
  and the engine checked them all, so the model could let an act through
  that the engine refuses (`EF` falsely true, `AF` falsely false). Both
  builders now check every `requires_permit`, each held by the exercising
  permit's holder (and active, in hybrid mode). Row R26 of
  [docs/ENGINE_VERIFIER_PARITY.md](docs/ENGINE_VERIFIER_PARITY.md)
  (Mirrored; one case under: a permit name held by two actors is read as
  held by one). Entries 2.3.0-10 and 2.3.0-11 of
  [docs/el_grammar_amendments.md](docs/el_grammar_amendments.md); the
  reference gains a "Conditional actions" note and a table of the
  verifier's transition rules.

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


[2.5.1]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.5.1
[2.5.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.5.0
[2.4.1]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.4.1
[2.4.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.4.0
[2.3.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.3.0
[2.2.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.2.0
[2.1.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.1.0
[2.0.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.0.0


[keepachangelog]: https://keepachangelog.com/
[semver]: https://semver.org/spec/v2.0.0.html
