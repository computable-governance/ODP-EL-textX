# DSL-EL Toolchain — Technical Reference
## Validator, Reasoner, and Architecture Overview

This document describes what each component of the DSL-EL toolchain does,
how they relate to each other, and where they sit in the four-layer
ComputableGovernance stack. Intended as project context for future sessions.

---

## Component Overview

```
el_grammar.tx     — textX grammar defining the DSL syntax
el_parser.py      — loads grammar, parses .el files, invokes validator
el_validator.py   — 71 rules (45 errors, 26 warnings) checked at specification time
el_reasoner.py    — governance queries over the static model
el_kripke.py      — Layer 4 Kripke semantics (modal obligation verification)
example.el        — payment processing scenario exercising all constructs
```

---

## The Validator (`el_validator.py`)

### What it does

Runs at **specification time**, before any execution. Takes a parsed DSL-EL
model and checks it against 71 rules: 45 errors and 26 warnings (tags
beginning `[W-`). Each rule in the table below is traced to a clause of
ISO/IEC 15414:2015; the rules added in 2.1.0 and 2.2.0 end "(clause to be
confirmed)". Analogous to a compiler's semantic phase — the grammar
checks syntax, the validator checks meaning.

`validate_spec()` returns one list of messages; `parse()` splits it into
`errors` and `warnings`, and a specification with no errors is `ok`.
Does not execute anything; reasons over the static model only.

### Rules

The original 15 rules:

| Rule | Clause | What it checks |
|------|--------|----------------|
| V-01 | §7.7   | Every community has exactly one objective |
| V-02 | §7.8.5 | Every process has at least one step |
| V-03 | §7.8.5 | Every step has at least one actor |
| V-04 | §7.8.5 | Process declares initiation and termination |
| V-05 | §7.8.2 | Assignment policy references an existing role |
| V-06 | §7.7   | Sub-objective assigned_to references existing role or process |
| V-07 | §7.10.1| Delegation from/to must be party or agent kind |
| V-08 | §7.10.1| Sub-delegation only if parent has sub_delegation_allowed: true |
| V-09 | §6.4.1 | A deontic token held by exactly one active enterprise object |
| V-10 | §6.6.2 | Commitment actor must be party or agent |
| V-11 | §7.10.5| Prescription actor must be party/agent or hold a permit |
| V-12 | §7.5.2 | Federation members reference declared communities |
| V-13 | §7.9.4 | Pessimistic enforcement must declare a mechanism |
| V-14 | §7.9.1 | PolicyRef target exists in community scope |
| V-15 | §7.10.1| Delegation obligation traces back to a CommitmentDecl |

Added before v2.0.0 (33; v2.0.0 has 48 rules in all):
- Errors: `V-17` (a burden whose action an embargo prohibits);
  `V-NEW-10`, `V-NEW-19`, `V-NEW-21` to `V-NEW-25`; five Authorization
  checks (the authority is a party; a revocable authorization names an
  `on_revocation` embargo; exactly one of `to_agent` and `to_role`;
  `grants_permit` names a permit; `on_revocation` names a declared
  embargo); `E-16a` (a token-group member with no backing commitment or
  delegation).
- Warnings: `[W-16b]` to `[W-16h]`, `[W-18]` to `[W-29]`.

Added in 2.1.0 (20):
- Errors: `policy-value-type`, `calendar-date`, `instant-valid`,
  `range-ends`, `currency-code` (see "Typed policy values");
  `comparison-type`, `fact-key-clash`, `comparison-in-step`,
  `envelope-currency`, `envelope-membership` (see "Comparisons");
  `standing-fields`, `standing-in-group`, `term-end-type` (see "Standing
  duties").
- Warnings: `[W-deadline-date-not-measured]`, `[W-deadline-date-invalid]`,
  `[W-deadline-several-durations]` (see "Deadlines");
  `[W-strict-precondition]` (see "Comparisons"); `[W-standing-no-end]`,
  `[W-standing-shared-fact]`, `[W-standing-not-modelled]` (see "Standing
  duties").

Added in 2.2.0 (3):
- Errors: `deadline-policy-type` (see "Deadlines"); `option-duplicate`,
  `option-set-name` (see "Typed policy values", options sets).

### Usage

```python
from el_validator import validate_spec
errors = validate_spec(model)   # returns list[str]
```

Or via the parser (validation is on by default):

```python
from el_parser import parse
result = parse("my_spec.el")
if result.ok:
    print("Valid")
else:
    for err in result.errors:
        print(err)
```

---

## Typed policy values (2.1.0)

### Scope of values

- The DSL types the values a specification states (policy values) and the
  values a comparison reads. It is not a general type system or an
  expression language.
- Value kinds: string, boolean, integer, exact decimal (`number` is an
  alias of `decimal`), percentage, amount (a number and a currency code),
  date, instant (a date and time with a UTC offset), and duration (written
  as in 2.0.0). A policy value may also be an integer interval (`7..10`)
  or an option of a user-defined type; from 2.2.0 an `options` set
  declares the options a type allows.
- A comparison has one reported fact, one of `>=`, `<=`, `>`, `<`, `==`,
  `!=` (`==` and `!=` from 2.2.0), and one limit: a number, percentage,
  amount, date, instant or duration literal, or a policy of one of those
  types (date, instant and duration from 2.2.0), or, from 2.2.0, a policy
  of an options type with `==` and `!=` only. There is no `and` or `or`,
  no arithmetic and no functions (`and` and `+` are syntax errors; no
  "date plus 30 days"), and a date is never compared with an instant. An
  action may carry several preconditions: all must
  hold, and a refused act gives the reason of the first one that fails (a
  false comparison is reported before one not established). A standing
  duty's `keeps` is one comparison.
- Types are checked where a value meets a limit. At specification time, a
  policy value is checked against its type keyword or, from 2.2.0, its
  declared options set (`policy-value-type`) and its envelope (`envelope-membership`, `envelope-currency`), and a
  comparison's limit against the comparable kinds (`comparison-type`). At
  run time, a reported value is checked against the kind of its limit:
  another kind, another currency or another notation is not established.
  A fact's name is free text and the specification declares no type for
  it; reading one fact in two ways is an error (`fact-key-clash`).
- Amounts are compared only within one currency and are never converted.
  A share, ratio or total is computed by the adapter and reported as a
  percentage or an amount.
- Notation follows existing standards where one exists: ISO 8601 for dates
  and instants, and the ISO 4217 three-letter form for currency codes (the
  code list itself is not checked); the source clauses are to be
  confirmed. Durations are written `60 days`, not ISO 8601 `P60D`, which
  is refused. Where a domain has its own standard, a domain extension
  should adopt it rather than invent a notation (for example, FHIR
  quantities with UCUM units for clinical values; these source standards
  are to be confirmed).
- The set of value kinds is deliberately small and general. A domain that
  needs more, such as quantities with units, may add its own kinds as an
  extension to the language. An extension adopts that domain's own
  standard notation, says so, and keeps the same rules: values are
  compared, never computed. No such extension exists yet. Computation,
  structured data and rule languages stay outside the DSL, behind the
  adapter that reports the facts.

### Types and literals

A Policy's `initial_value`, its envelope values and the ends of a
`range of [a to b]` envelope rule are typed literals. A NormativePolicy's
`initial_value` uses the same literals.

The value types are adopted from existing standards rather than invented
here. Where the source has not yet been checked against the standard's
text, the table says so.

| Type keyword | Literal form | Example | Held as | Source standard |
|---|---|---|---|---|
| `integer` | ASCII digits, optional leading `-` | `3`, `-5` | `int` | source standard to be confirmed |
| `decimal` | digits `.` digits, optional leading `-` | `0.75`, `4.50` | `decimal.Decimal`, as written | source standard to be confirmed |
| `number` | alias of `decimal` | `4`, `4.5` | as `decimal` | source standard to be confirmed |
| `percentage` | a number followed by `%` | `4.25%`, `6%` | `Percentage`; the number as written (4.25, not 0.0425) | source standard to be confirmed |
| `amount` | a number, then a three-letter currency code | `250.00 AUD` | `Amount` (number and code as written) | currency code: ISO 4217 alphabetic code form (edition to be confirmed); number: as `decimal` |
| `string` | a quoted string | `"standard"` | `str` | — |
| `boolean` | `true` or `false` | `true` | `bool` | — |
| `duration` | a whole number and a unit (unchanged from 2.0.0) | `60 days`, `1 year` | `Duration` | none: DSL notation (recorded deviation, see below) |
| `date` | `YYYY-MM-DD` | `2026-11-30` | `Date`, as written | ISO 8601 extended calendar date (part and edition to be confirmed) |
| `instant` | `YYYY-MM-DDTHH:MM[:SS]` then `Z` or `±HH:MM` | `2026-11-30T17:00+10:00`, `2026-11-30T07:00Z` | `Instant`, as written | ISO 8601 extended date and time with a UTC offset (part and edition to be confirmed); strict profile |

Other value forms: an integer interval `7..10` (accepted for `integer`,
`decimal` and `number`), and a bare name (an option of a user-defined
type such as `policy Tier : TierOptions`).

**Options sets (2.2.0).** `options <Name> [<option>, ...]` declares the
options a user-defined type allows (source standard to be confirmed):

```
options ApprovalStates [pending, approved, rejected]

policy RequiredState : ApprovalStates {
    initial_value: approved
    envelope { one of [approved, rejected] }
}
```

- An options set is a top-level element. Its options are plain names,
  comma-separated, at least one; they are not cross-references.
- A policy whose type names a declared options set takes one of its
  options: its `initial_value`, envelope values and range ends are checked
  (`policy-value-type`). A quoted string and a bare name both read as
  text, so `"approved"` is the option `approved`.
- A type that names no options set is not checked, as in 2.1.0:
  `policy Tier : TierOptions { initial_value: gold }` with no `options
  TierOptions` validates with no message.
- An option listed twice is the error `option-duplicate`. An options set
  named like a type keyword (`options date [...]`) is the error
  `option-set-name`: `policy P : date` is a date policy and never takes
  the options. A name that only begins with a keyword (`dateWindows`) is
  accepted.
- `true` and `false` parse as booleans, so an option with either name is
  never matched by a value. If two options sets share a name, the first
  declared is read.
- A comparison may use a policy of an options type as its limit, with
  `==` and `!=` only (see "Comparisons").

**Principles.**
- The DSL compares typed values. It does not compute with them: there is
  no arithmetic and there are no expressions.
- Amounts are compared only within one currency. They are never converted.
- Durations go down to minutes (the units are minute, hour, day, week,
  month and year, singular or plural). For comparison a month is 30 days
  and a year is 365 days, the engine's existing deadline unit table, in
  which one step is one minute.
- Instants are compared by the moment they denote: `17:00+10:00` equals
  `07:00Z`. An instant needs a UTC offset. Seconds may only be `:00`.
  Fractional seconds and zone names are not accepted.
- The duration notation `60 days` is not ISO 8601 (which writes `P60D`).
  This is a recorded deviation from the principle of adopted notations,
  kept so that 2.0.0 specifications still parse.

**Number forms.** Digits are ASCII only. A plain number has no leading
`+`, no exponent (`1e3`), no `5.` or `.5` form and no digit grouping
(`1,000`). `-0` and `-0.0` are accepted.

**What 2.1.0 tightens in 2.0.0.**
- An integer literal now parses as an integer. In 2.0.0 `5` became the
  float `5.0`.
- A decimal literal is an exact `Decimal`, not a binary float.
- The number forms are stricter. `1e3`, `+5`, `5.`, `.5` and non-ASCII
  digits parsed in 2.0.0 and are now syntax errors. Write `1000`, `5`,
  `5.0` and `0.5`.
- `0` and `1` are integers, not booleans. A `boolean` policy needs `true`
  or `false`.
- `decimal`, `percentage`, `amount`, `date` and `instant` are new reserved
  type words. They are matched as whole words, so a user-defined type may
  begin with one (`integerCodes`, `dateWindows`).

**Validator rules.** Each message ends "(clause to be confirmed)".

| Rule | What it checks |
|---|---|
| `policy-value-type` | A value matches its policy's type keyword. An integer is accepted for `decimal`/`number`, an interval for `integer`/`decimal`/`number`. A user-defined (ID) type is not checked, unless (2.2.0) it names a declared options set: then each value is one of its options. |
| `calendar-date` | A date, or an instant's date part, is a real calendar date. |
| `instant-valid` | An instant's hour is at most 23, minute at most 59, seconds only `00`; its offset hours at most 23 and minutes at most 59; `-00:00` is refused. |
| `range-ends` | A range's ends are of one kind (number, percentage, amount, duration, date or instant), amounts are in one currency, and the low end is not above the high end. An end already reported by `calendar-date` or `instant-valid` is not reported again. |
| `currency-code` | An amount's code is three upper-case letters A–Z (the ISO 4217 form; membership in the code list is not checked). A code that abbreviates a duration unit (`5 min`, `5 hrs`) is told how to write the duration. |
| `option-duplicate` (2.2.0) | An options set lists each option once. |
| `option-set-name` (2.2.0) | An options set is not named like a policy type keyword. |

**Runtime.** `WorldState.policy_values` holds each top-level Policy's value
as plain text, `(name, text)` pairs sorted by name (decimals never in
exponent form). It is seeded read-only by `initial_state(spec)`,
`Runtime.build_from_spec`, `Runtime.build_from_federation` and the API's
scenario builders. `state.policy_value(name)` reads one value.

Shared examples, one valid file and one invalid file per rule, are in
`tests/examples/typed_values/`.

---

## Deadlines (2.1.0)

A burden's `deadline` is a string or, from 2.2.0, the name of a duration
policy (below). A string is read in one of two ways, on two different
clocks.

**A duration from activation.** `deadline: "21 days"` is one duration
counted from the burden's activation: the first firing of its
`triggered_by` event, an `activate` effect, or else the grant. It is
measured on the engine's step clock, `WorldState.tick`, where one step is
one minute (units: second, rounded up to a whole minute, minute, hour,
day, week, month (30 days), year (365 days); "working" or "business" days
count as 7/5 of a day and business hours as 168/40 of an hour, so "5
working days" and "40 business hours" are both 7 days). For "N days after
event E", write a burden with `state: pending`, `triggered_by: E` and
`deadline: "N days"`. `check_live_violations()` violates an eventual burden
when the tick minus its activation tick reaches the duration. This is
unchanged from v2.0.0.

**A duration policy (2.2.0).** The deadline may name a Policy of type
duration instead of quoting the duration (source standard to be
confirmed):

```
policy NoticePeriod : duration { initial_value: 24 hours }

burden notice {
    for_action: "giveNotice"
    state: active
    deadline: NoticePeriod
}
```

- The deadline is the policy's declared `initial_value`, read-only, and
  is then counted exactly as the same duration written as a literal
  (`deadline: "24 hours"`). Top-level and role-scoped tokens.
- One resolver, `el_engine.deadline_text()`, gives every reader the
  deadline text: the engine, both verifier builders and the validator's
  deadline warnings. `TokenInstance.deadline` holds the resolved text
  (`"24 hours"`).
- Violation lines name the policy: `violated 'notice' held by 'Supplier'
  (elapsed 1440 >= deadline 1440 steps) (policy NoticePeriod = 24 hours)`,
  and the same suffix on a declared violation.
- A policy of another type, or with a negative value (`-5 days`), gives
  no measurable deadline and is the error `deadline-policy-type`
  (`deadline NoticePeriod is a policy of type 'date'; it must be of type
  duration`). An undeclared name is a reference error at parse time.
- The verifier reads the same declared value from the specification,
  never `WorldState.policy_values` (`docs/ENGINE_VERIFIER_PARITY.md`, rows
  R10 and R19). A standing duty takes no deadline (`standing-fields`).

**A date.** A deadline that is a date alone, `"by 2026-11-30"`, or a date
and time with a UTC offset, `"2026-11-30T17:00+10:00"` or
`"2026-11-30T07:00Z"`, is a fixed moment. It is written in the notation of
the 2.1.0 Date and Instant policy values (ISO 8601 extended format; `T` and
`Z` in upper case; seconds only `:00`). A date alone is due at 00:00 on the
next day in the clock's offset, so the whole day counts; a date and time is
due at that moment. It does not depend on activation.

A date deadline is judged only against a wall-clock time the caller
supplies, `as_at`, never against the tick, and only with a clock:

```python
from datetime import datetime, timedelta, timezone
from el_engine import DeadlineClock
from el_runtime import Runtime

rt = Runtime.build_from_spec(spec, clock=DeadlineClock(utc_offset=timezone(timedelta(hours=10))))
rt.check_live_violations(as_at=datetime(2026, 12, 1, 0, 0, tzinfo=timezone(timedelta(hours=10))))
```

- `DeadlineClock(utc_offset=..., epoch=None)` is keyword-only. The offset is
  one fixed UTC offset for the run. `epoch` (the wall-clock time of tick 0)
  is optional and not yet used.
- An eventual date burden is violated when `as_at` is at or after its due
  moment. The effect reads `violated 'X' held by 'H' (due <iso>; as_at
  <iso>; activated at tick N)`.
- Without a clock, without an `as_at`, or for a date that is not measured,
  it is **not judged**. The effects gain `not judged 'X' held by 'H':
  <reason>` (`date deadline, no clock`, `date deadline, no as_at`, `a date
  with other numbers is not measured`, `date not in the 2.1.0 notation`,
  `invalid date`). A burden not judged is never violated and never
  reported as met. `el_engine.not_judged_date_burdens()` returns the same
  list as data.
- A date burden is never violated by episode conclusion.
- `as_at` must carry a UTC offset (a naive value raises `ValueError`). It may
  not go backwards within one runtime: an earlier `as_at` than the last one
  accepted raises `ValueError` and nothing is ledgered; an equal one is
  accepted.
- Text containing a date is never read as a duration.

**Warnings.** Burdens only, top-level and role-scoped:

| Warning | When |
|---|---|
| `[W-deadline-date-not-measured]` | The deadline contains a date that is never judged: a date with other numbers or a second date, or a date not in the 2.1.0 notation (`"2026-11-30 17:00"`, `"2026-11-30T17:00"` without an offset). |
| `[W-deadline-date-invalid]` | A date in the 2.1.0 notation is not a valid date or time, with the reason: not a calendar date, not a time of day, not a whole minute, not a UTC offset. |
| `[W-deadline-several-durations]` | More than one duration (`"2 weeks and 3 days"`): only the first is measured, so the burden is violated earlier than stated. |

`[W-24]` no longer warns on an eventual burden whose deadline is a measured
date, and `[W-25]` no longer warns on any deadline containing a date.
`[W-19]` still warns on a strict burden with a date deadline: strict date
burdens are not judged in 2.1.0.

**API.** `POST /check-violations?as_at=<ISO 8601 with offset>` passes
`as_at` to the sweep. In a query string `+` must be sent as `%2B`
(`as_at=2026-12-01T00:00%2B10:00`); an unencoded `+` arrives as a space and
is refused. A trailing `Z` is accepted. 422 for a value that cannot be
parsed, has no offset, or is earlier than the last accepted one (nothing is
ledgered). The response adds `as_at` (echoed, or null) and `not_judged:
[{token, holder, reason}]`. Each scenario's clock is in
`el_api._SCENARIO_CLOCK`. No shipped scenario has a clock, and no burden
in a shipped scenario has a date deadline (one permit in
`scenarios/fhir/generated_governance.el` has `deadline: "by 2026-05-20"`;
`check_live_violations()` judges burdens only, so it is never judged, as
in v2.0.0).

**Verifier.** The verifier does not model date deadlines
(`docs/ENGINE_VERIFIER_PARITY.md`, rows R5 to R7): it never proves anything
about a date deadline, and an eventual date burden is never reported
compelled while it is pending.

---

## Comparisons (2.1.0)

An action's precondition may compare a value the caller reports on the act
with a limit. The DSL compares typed values; it does not compute: there is
no arithmetic and no expression ("10% of a policy" cannot be written).

**Syntax.**

```
policy MinimumCover : amount { initial_value: 20000000 AUD }

action assess {
    actor: assessorRole
    precondition: "insurance cover" >= MinimumCover
    precondition: "subcontract share" <= 10%
}
```

- `precondition: "<fact>" <op> <limit>`. The fact is the key of a value the
  caller reports with the act; a plain `precondition: "<fact>"` is read as
  before.
- Operators: `>=`, `<=`, `>`, `<`, and from 2.2.0 `==`, `!=` (source
  standard to be confirmed). `==` and `!=` are exact equality of the
  values, not of the text: `"2.0" == 2` and `"20000000.00 AUD" ==
  20000000 AUD` hold, and `"10.00%" != 10%` fails. An amount in another
  currency is not established, as for the other operators.
- The limit is a number (`5`, `2.5`), a percentage (`10%`), an amount
  (`20000000 AUD`, written without digit grouping), or a Policy of type
  integer, decimal, number, percentage or amount, at its value (its
  `initial_value`; policy values are read-only).
- From 2.2.0 the limit may also be a date (`2027-06-30`), an instant
  (`2027-06-30T17:00+10:00`, `2027-06-30T07:00Z`) or a duration (`24
  hours`, `60 days`), or a Policy of type date, instant or duration.
  Dates compare by calendar day; instants by moment (`17:00+10:00` equals
  `07:00Z`); durations in minutes, through the deadline unit table (a
  30-day month, a 365-day year), so `1 day <= 24 hours` holds and `1
  month <= 24 hours` fails. A duration limit is a whole number and a unit,
  never signed (`+60 days` and `-60 days` are syntax errors in a
  comparison; a policy's duration value still accepts `+5 days`, as in
  2.1.0). `60 sec` is not a duration (sec is not a unit): it reads as an
  amount and is refused by `comparison-type`.
- From 2.2.0 the limit may also be a Policy of an options type (see
  "Typed policy values", options sets), with `==` and `!=` only. The
  reported text must be one of the options, exactly; it equals the limit
  when it is the policy's option. An ordering operator (`>=`, `<=`, `>`,
  `<`) is refused by `comparison-type` and, if judged, not established:
  options have no order.

```
options ApprovalStates [pending, approved, rejected]
policy RequiredState : ApprovalStates { initial_value: approved }

action release {
    actor: clerkRole
    precondition: "approval" == RequiredState
}
```

With `{"approval": "pending"}` the act is refused: `precondition not
satisfied: 'approval' pending == approved (RequiredState)`. With
`{"approval": "maybe"}`: `precondition not established: 'approval'
reported maybe: not one of the options [pending, approved, rejected]`.

```
policy NoticePeriod : duration { initial_value: 24 hours }

action renew {
    actor: assessorRole
    precondition: "certificate expiry" >= 2027-06-30
    precondition: "notified at" <= 2027-06-30T17:00+10:00
    precondition: "notice given within" <= NoticePeriod
}
```

With `{"certificate expiry": "2027-07-01", "notified at":
"2027-06-30T07:00Z", "notice given within": "25 hours"}` the act is
refused: `precondition not satisfied: 'notice given within' 25 hours <= 24
hours (NoticePeriod)`. A date reported where an instant is the limit, or
the reverse, is not established (`reported 2027-07-01T09:00+10:00: not a
date value`).
- Only on actions. Step preconditions are not enforced by any engine path,
  so a comparison in a step is the error `comparison-in-step`.

```
action countersign {
    actor: assessorRole
    precondition: "approvals" == 2
    precondition: "insurance cover" != MinimumCover
}
```

With `{"approvals": "3", ...}` the act is refused with `precondition not
satisfied: 'approvals' 3 == 2`; with `{"approvals": "2", "insurance
cover": "25000000.00 AUD"}` both hold.

**The reported value.** The caller passes it in the act's facts, as text,
in the notation of the 2.1.0 values (source standard to be confirmed):

| Limit | Reported text | Example |
|---|---|---|
| number | `-?digits` or `-?digits.digits`, ASCII | `"25000000"`, `"5.50"` |
| percentage | the number then `%`, no space | `"8.5%"` |
| amount | the number, one space, three upper-case letters | `"25000000.00 AUD"` |
| date (2.2.0) | `YYYY-MM-DD`, a calendar date | `"2027-06-30"` |
| instant (2.2.0) | the 2.1.0 Instant notation, with a UTC offset | `"2027-06-30T17:00+10:00"`, `"2027-06-30T07:00Z"` |
| duration (2.2.0) | a whole number, one space, a unit (minute to year, singular or plural) | `"24 hours"`, `"1440 minutes"` |
| an options type (2.2.0) | one of the options, exactly | `"approved"` |

At most 100 characters. A number limit accepts a decimal report
(`"5.50" >= 5`). Amounts are compared only within one currency, never
converted.

**Outcomes.** A comparison that holds lets the act proceed. Otherwise the
act is refused (outcome `blocked`), never violated:

| Situation | Refusal reason |
|---|---|
| The comparison fails | `precondition not satisfied: 'insurance cover' 15000000 AUD >= 20000000 AUD (MinimumCover)` |
| The fact is missing, null or `"unknown"` | `precondition not established: 'insurance cover' not reported` |
| The fact is not text | `precondition not established: 'insurance cover' reported a value of type int, not text; send text, e.g. "25000000.00 AUD"` |
| Wrong kind or notation | `precondition not established: 'insurance cover' reported 25000000: not an amount value` |
| Another currency | `precondition not established: 'insurance cover' reported 25000000 NZD: currency NZD, not AUD; amounts are compared only within one currency` |
| Not one of the options (2.2.0) | `precondition not established: 'approval' reported maybe: not one of the options [pending, approved, rejected]` |
| An ordering operator with an options limit (2.2.0) | `precondition not established: 'approval': limit approved (RequiredState) is an option; options are compared with == and != only` |

A false precondition is reported before one not established, each in
declared order. `advance()` and `declare_violation()` share the check.

**The ledger line.** When the act is applied, each comparison that held
adds a line to the record's effects, before the other effects:
`precondition satisfied: 'insurance cover' 25000000.00 AUD >= 20000000 AUD (MinimumCover)`.
Plain preconditions add none.

**The JSON-number trap.** Through the API, facts are JSON. Send the value as
a string: `{"insurance cover": "25000000.00 AUD"}`. A JSON number
(`25000000`) is refused as not established, never read, because a JSON
number can be a binary float.

**Adapter pattern for a share of the contract value.** The DSL never
computes a share. The adapter that knows the subcontract value and the
contract value computes it and reports the result as a percentage, for
example `{"subcontract share": "8.5%"}`; the precondition compares it with
`10%` or with a percentage policy. The adapter, not the DSL, is
responsible for the computation and its rounding.

**Plain preconditions.** Unchanged from v2.0.0: a plain precondition holds
when its fact is truthy in Python, so the strings `"false"`, `"no"` and
`"0"` pass, and `False`, `0` and `""` do not. Send real booleans.

**Validator.** Errors: `comparison-type` (the limit is a number,
percentage, amount, date, instant or duration, an amount code in ISO 4217
form, or a policy of a comparable type; `"x" <= 60 sec` is refused, with
"a duration's unit is minute, hour, day, week, month or year"; from 2.2.0
`"x" <= 60 day` is a duration; from 2.2.0 a policy of an options type
with `==` or `!=`, and an ordering operator against one is refused),
`calendar-date` and `instant-valid` (from
2.2.0 also on a comparison's date or instant limit), `fact-key-clash` (one fact
read two ways), `comparison-in-step`, `envelope-currency` (an amount
initial value with envelope amounts in another currency) and
`envelope-membership` (the initial value inside every envelope rule). The
warning `[W-strict-precondition]` flags a strict burden whose discharging
action has a precondition, plain or a comparison.

**Verifier.** The verifier assumes every precondition holds
(`docs/ENGINE_VERIFIER_PARITY.md`, R11). For a strict burden whose
discharging action has a precondition, `GET /obligations/{token}/status`
may report `compelled: true` while the engine refuses the discharge; its
field `assumes_preconditions` lists the assumed preconditions as
`<action>: <precondition>`.

---

## Standing duties (2.1.0)

A standing duty is a burden kept for a term: for example, "the supplier
keeps insurance cover of at least 20000000 AUD for the life of the
contract". It is judged against values the caller reports; the DSL
compares, it does not compute.

**Syntax.** `standing` and `keeps` (a comparison, see "Comparisons
(2.1.0)") come first in the burden's body, optionally followed by
`ends_at` and `ended_by`:

```
enterprise specification CoverForTheTermOk

policy MinimumCover : amount { initial_value: 20000000 AUD }
policy MaximumShare : percentage { initial_value: 10% }
policy ContractEnd : instant { initial_value: 2027-06-30T17:00+10:00 }

party Supplier {
    holds keepCover
    holds keepShare
}

burden keepCover {
    standing
    keeps: "insurance cover" >= MinimumCover
    ends_at: ContractEnd
    ended_by: contractTerminated
    state: pending
    triggered_by: contractSigned
}

burden keepShare {
    standing
    keeps: "subcontract share" <= MaximumShare
    ends_at: ContractEnd
    ended_by: contractTerminated
    state: pending
    triggered_by: contractSigned
}

community Contract {
    objective: "the supplier keeps cover and limits subcontracting for the term"
    event contractSigned
    event contractTerminated
    Supplier fills supplierRole
    role supplierRole {
        action sign { actor: supplierRole emits: contractSigned }
        action terminate { actor: supplierRole emits: contractTerminated }
    }
}
```

(This is `tests/examples/standing/ok_cover_for_the_term.el`; it parses and
validates with no error.)

**The term.** It starts at the duty's activation: its grant, or the first
firing of `triggered_by`. It ends at `ends_at` (a date or instant, or a
date or instant Policy shared by several duties) or when the `ended_by`
event fires, whichever comes first.

- A date alone ends at the end of that day in the clock's offset; an
  instant at that moment. A term end by date is judged only with a clock
  (`DeadlineClock`, see "Deadlines (2.1.0)") and an `as_at`.
- An `ended_by` event ends the term when it fires: an action that emits it,
  or `fire_event()`.
- An `ended_by` event that fires while the duty is still pending is not
  remembered: a duty that starts later is never ended by it.

**Judged only at a check.** `keeps` is judged when the caller runs a
check, with the time (`as_at`) and the facts the adapter reports:

```python
from datetime import datetime, timedelta, timezone
from el_engine import DeadlineClock
from el_runtime import Runtime

rt = Runtime.build_from_spec(spec, clock=DeadlineClock(utc_offset=timezone(timedelta(hours=10))))
rt.fire_event("contractSigned")
record = rt.check_live_violations(
    as_at=datetime(2027, 1, 15, 9, 0, tzinfo=timezone(timedelta(hours=10))),
    facts={"insurance cover": "25000000.00 AUD", "subcontract share": "8.5%"},
)
```

Through the API: `POST /check-violations?as_at=2027-01-15T09:00%2B10:00`
with the body `{"facts": {"insurance cover": "25000000.00 AUD",
"subcontract share": "8.5%"}}`. The response lists each duty under
`standing` as `{token, holder, verdict, text}`.

**Verdicts.**

| Verdict | When | Effect |
|---|---|---|
| kept | the reported value satisfies the comparison | none; the ledger line `kept '<duty>' held by '<holder>': <comparison> at as_at <time>` |
| breached | the reported value fails the comparison | the duty is violated: once, and final (a later good report does not undo it) |
| met | `as_at` is at or after `ends_at`, or `ended_by` has fired | the duty is discharged; `keeps` is not judged at or after the end |
| not judged | nothing reported, not text, wrong kind, another currency, no `as_at`, or a term end that cannot be judged (no clock) | no change; a duty is never "kept" without a value that holds |

Kept means kept at the moments checked: a lapse between two checks is not
seen, and nothing runs a check on its own.

**Nothing else ends it.** A standing duty is not discharged by an action,
a `destroy` effect, an event other than its `ended_by`, or
`discharge_burden()` (refused); a declaration of its breach is refused; no
deadline or episode conclusion violates it.

**Rules.**
- `standing-fields` (error): a standing duty is an eventual burden, active
  or pending, with no `deadline`, `discharged_by` or `for_action`. It cannot
  be strict: a strict burden blocks the clock while it can be acted on,
  and the verifier would report it compelled by a discharge the engine
  never makes.
- `standing-in-group` (error), `term-end-type` (error); `comparison-type`
  and `fact-key-clash` also read `keeps`.
- `[W-standing-no-end]`: neither `ends_at` nor `ended_by`, so it is never
  met.
- `[W-standing-shared-fact]`: the facts of one check are global, one value
  per key, so standing duties of different holders that read the same fact
  key are all judged by one report. Use one fact key per holder.
- `[W-standing-not-modelled]`: on every standing duty (see Verifier).

**Verifier.** The verifier does not model standing duties: it treats one
as an ordinary obligation that its holder could discharge at any step, and
has no breach or term-end step (`docs/ENGINE_VERIFIER_PARITY.md`, R13 to
R18). The toolchain withholds its claims about them:
- `GET /obligations/{token}/status` answers `status: "standing duty: not
  modelled"`, `standing: true`, `compelled: null`, `detectable: null`, and
  no path;
- `GET /kripke/witness` refuses (422) `discharged:<duty>`, `violated:<duty>`
  and `all_discharged` while the model tracks a standing duty;
- the recommended action (its route, and the one execute-action returns)
  never proposes discharging a standing duty, and its Q-values are computed
  on the model without those discharge edges (2.1.0-23). When the only
  other edge is the tick, the recommendation is `tick`.

Other routes are unaffected: the objective score and reachability read
satisfaction groups, which never contain a standing duty; available
actions list obligations by their `for_action`, which a standing duty
cannot have. The `updated_world`/`current_world` maps still show a
standing duty's state in the model (PENDING while active).

**The two rules, with an adapter.**
- Cover at least 20000000 AUD: `keeps: "insurance cover" >=
  MinimumCover`. The adapter reports the current cover as text, for
  example `"25000000.00 AUD"`.
- Exposure at most 10% of contract value: `keeps: "subcontract share" <=
  10%` (or a percentage policy). The adapter computes the share from the
  subcontract and contract values and reports it, for example `"8.5%"`; the
  DSL never computes it.

Send each value as text: a JSON number is not established, and the reason
says to send text (`e.g. "25000000.00 AUD"`).

**Adapter checklist.**
- Send every value as text in the exact notation: `"25000000.00 AUD"`,
  `"8.5%"`. Any other form (`"8.5"`, `"0.085"`, `"10 %"`, `"25000000"`
  with no currency) is not established in a precondition and "not judged"
  in a standing duty, never a breach.
- Before passing an act on, run a check under a clock with the current
  time as `as_at`: an act carries no time, so a late act made before the
  next check counts as on time.
- Treat the first breach as final and keep it: later checks do not report
  it again.
- Fire a term-ending event only after the duty is active: one that fires
  earlier is forgotten.
- Compute shares in the adapter and send them as percentages; the DSL
  compares, it does not compute.

**Not supported.** A term given as a duration; declaring a breach; ending a
term by community conclusion; currency conversion; arithmetic; proof of
where a reported value came from.

---

## Token events in the ledger (unreleased)

Each `TransitionRecord` lists, in `token_events`, every change its act made
to a token instance, as `TokenEvent` records. The effect lines, reasons,
outcomes and token states are unchanged; the events describe them in data.

**A `TokenEvent`** has:

| field | meaning |
|---|---|
| `event` | `granted` (a new instance), `removed` (the instance left its holder: a transfer or a delegation reassignment, followed by a `granted` for the new holder), or the new state (`active`, `pending`, `discharged`, `violated`, `superseded`, `lifted`, `lapsed`, ...) |
| `token_name`, `token_kind`, `holder`, `granted_at_tick` | the instance |
| `from_state`, `to_state` | the state before and after (`None` before a grant, after a removal) |
| `tick` | the record's tick |
| `by` | the record's actor: the performer, the authority, the declarer, the `fire_event()` source, `system` for sweeps and responses, `model` for the build record |
| `cause`, `cause_ref` | why, and the name it refers to (below) |

**Causes.** The `cause` says why the instance changed, and `cause_ref`
names what it refers to:

| cause | cause_ref | the change |
|---|---|---|
| `initial` | — | a grant in the build record |
| `action` | the action | what `advance()` does by default: a create effect, a discharge by a destroy effect or by `for_action`, pend, activate, transfer, clone, claim |
| `event` | the event | a discharge by `discharged_by`, an activation by `triggered_by`, a standing duty's term ended by `ended_by`; from an emitting action or `fire_event()` |
| `sibling` | the sibling discharged or claimed | a burden superseded in an `any_discharged` group, or lapsed when a sibling is claimed |
| `deadline` | — | a duration deadline elapsed (`check_live_violations()`) |
| `date_due` | — | a date deadline judged due |
| `episode_concluded` | — | a deadline with no magnitude, its episode concluded |
| `standing_breach` | — | a standing duty's keeps judged false |
| `term_end` | — | a standing duty's term ended by its date |
| `declaration` | the declaring action | `declare_violation()` |
| `revocation` | the Authorization | `revoke_authorization()`, or a response's revocation |
| `reinstatement` | the Authorization | `reinstate_authorization()` |
| `response` | the ViolationResponse | a burden a response grants |
| `delegation_revoked`, `delegation_reinstated` | the Delegation | `revoke_delegation()`, `reinstate_delegation()` |
| `discharge_call` | — | `discharge_burden()` |

When one act changes an instance twice, the event shows the final state and
the cause of the last change.

**The build record and `Runtime.history()`.** A `Runtime` records the
tokens it starts from in `Runtime.build_record`: `actor_name` `model`,
`action_name` `build`, outcome `ok`, at the starting tick, with one `granted`
event (by `model`, cause `initial`) per token, in its starting state (a
`pending` token is granted `pending`). It is made when the `Runtime` is
constructed, so it covers `build_from_spec()`, `build_from_federation()` and
a `Runtime(state, spec)` built from a granted state. It is not in the ledger:
the ledger records acts, and the hybrid verifier reads it unchanged.
`Runtime.history()` returns the build record, then the ledger, in order.

**Was a token in force? `Runtime.in_force_at(token_name, holder, tick)`.**
It answers whether `holder` held `token_name` active when an act at `tick`
was judged: `True` or `False`, or `None` when that is unknown.
`Runtime.token_states_at(token_name, holder, tick)` gives the states behind
the answer, one per instance the holder had, by grant tick (`()` if none).
Both read only the token events of `history()`, never the effect text.

- **Ticks, not wall-clock time.** `tick` is the engine's tick
  (`WorldState.tick`; a record's `tick` is the tick its act was judged
  at). The state at `tick` is the build record's grants followed by the
  events of every record with a lower tick: every act that changes a token
  advances the tick, so an act and its events never share a tick with a
  later act. A date or `as_at` is not a tick; to ask about a wall-clock
  moment, find the record judged at it first.
- **In force** means `active`, for a permit, an embargo or a burden. A
  holder with several instances is in force if any of them is.
- **Never held**, with a complete history: `False` (and `()`).
- **`None` when the history is missing or does not reproduce the current
  state:** a `tick` before the build record's tick or after the current
  tick; or, for that token and holder, folding every event of `history()`
  does not give the holder's current instances, because something changed
  them outside the runtime's methods (for example `grant_token()` on its
  state, or `revoke_delegation()`, which the runtime does not wrap). The
  check is per token and holder: other tokens are still answered.
- The history is in memory only, for the life of the `Runtime`.

**Completeness.** The events are found by comparing the token instances
before and after the act, so every change made by an engine function is
listed, whatever made it. A change made outside the engine functions (for
example `grant_token()` on a runtime's state) is not.

**Known limit: the instance is inferred.** A `TokenInstance` has no id. An
instance is identified by token name, kind, holder and `granted_at_tick`;
two instances with the same four values (a token cloned to a holder who
already holds it from the same tick) are matched in list order.

**Open findings now visible in the events.** A revocation supersedes every
instance of the Authorization's permit, whoever holds it, and a
reinstatement lifts every instance of its embargo (see
`docs/CONCEPTS_INDEX.md`, "Revocation supersedes a permit by name for every
holder"). The events record this as it happens: a revocation lists a
`superseded` event for each holder of the permit, including holders the
Authorization does not name.

A response's revocation of an embargo that is already active produces no
event, although its effect line still says "activated embargo" (in both
terms-of-engagement scenarios, `outsideScopeEmbargo` is active from the
start). The text is unchanged; low priority.

---

## The Reasoner (`el_reasoner.py`)

### What it does

Also runs over the **static model**, but asks governance queries rather than
checking rules. Three queries are implemented. The reasoner does not execute
or simulate — it reasons over the declared structure.

### Query 1 — `ultimate_accountability()` (primary query)

**The question:** "Which party is ultimately accountable for obligation O
through the delegation chain?"

**Algorithm:**
1. Find all CommitmentDecls whose obligation text matches the query
2. Build a directed delegation graph: delegator → delegate
3. Walk the chain forward from the committing party to the current holder
4. Return an AccountabilityChain with root party, origin commitment,
   ordered delegation hops, and current holder

**Returns:** `List[AccountabilityChain]`

Each `AccountabilityChain` has:
- `obligation`: the obligation text
- `root_party`: the ultimately accountable party (root of chain)
- `root_commitment`: name of the CommitmentDecl that created the obligation
- `chain`: ordered list of `DelegationLink` objects (each hop)
- `current_holder`: who currently holds the obligation

Each `DelegationLink` records: delegation name, from/to names, obligation,
sub_delegation_allowed flag, revocable flag, duration, conditions,
creates_reporting_burden flag.

**Example output:**
```
Obligation : 'Process all customer payments within SLA'
Root party : MerchantParty  ← ULTIMATELY ACCOUNTABLE
Origin     : commitment 'merchantSLACommitment'
Chain      :
  [merchantToGatewayDelegation] MerchantParty ──► PaymentGatewayParty
                                 (12 months)  [sub-delegation allowed]  [reporting burden]
    [gatewayToProcessorDelegation] PaymentGatewayParty ──► PaymentProcessorAgent
                                   (6 months)  [reporting burden]
Holder now : PaymentProcessorAgent
```

**Usage:**
```python
from el_reasoner import ultimate_accountability
chains = ultimate_accountability(spec, "Process all customer payments within SLA")
for chain in chains:
    print(chain.render())
```

---

### Query 2 — `can_perform()` (deontic capability check)

**The question:** "Can actor X perform action Y given their current token holdings?"

Implements §6.4.6 conditional action semantics:
- Actor must hold required permits (requires_permit declarations)
- Actor must NOT hold active embargos for the action (inhibited_by_embargo)
- Burdens do not block but favouring burdens are noted

**Important limitation:** This is a *static* check against declared token
holdings in ObjectDecl bodies. Runtime token state changes (via speech acts)
are not modelled — this is structural, not operational. The runtime engine
handles the dynamic/operational version.

**Returns:** `CanPerformResult` with:
- `permitted`: bool
- `blocking_embargos`: list of embargo names preventing action
- `missing_permits`: list of permit names required but not held
- `explanation`: human-readable reason

**Usage:**
```python
from el_reasoner import can_perform
result = can_perform(spec, "PaymentGatewayParty", "authoriseTransaction")
print(result.render())
```

---

### Query 3 — `policy_conflicts()` (cross-community conflict detection)

**The question:** "Are there conflicting policies across communities?"

Scans all communities and their policy references. Detects cases where one
community's policy creates an `obligation` on a target while another creates
a `prohibition` on the same target.

**Returns:** `List[PolicyConflict]`, each with community_a, community_b,
obligation text, and description.

**Usage:**
```python
from el_reasoner import policy_conflicts
conflicts = policy_conflicts(spec)
if conflicts:
    for c in conflicts:
        print(c.description)
```

---

## Relationship Between Components

```
Specification (.el file)
        │
        ▼
   el_parser.py  ──► el_validator.py (71 rules)
        │                    │
        │            errors and warnings
        │
        ▼
   parsed model
        │
        ├──► el_reasoner.py  ──► ultimate_accountability()
        │                    ──► can_perform()
        │                    ──► policy_conflicts()
        │
        ├──► el_kripke.py    ──► build_kripke_model()
        │                    ──► check_obligation()   [AF φ]
        │                    ──► check_permission()   [EF φ]
        │                    ──► ranked_reachable()   [utility §C.3/C.4]
        │
        └──► Runtime engine (el_engine.py / el_runtime.py)
             ──► WorldState transitions
             ──► Deontic enforcement at runtime
             ──► Append-only ledger
             ──► (optional: ledger anchors el_kripke.py initial world)
```

**Key distinction:**
- Validator: *Is this specification internally consistent?*
- Reasoner: *Given consistency, what can we conclude about accountability?*
- Kripke (el_kripke.py): *Across all possible futures, will obligation O inevitably discharge?*
- Runtime engine: *Given a valid specification, what happened when executed?*

---

## Position in the Four-Layer Stack

```
Layer 1 — computable-governance grammar (Igor Dejanovic)
          Core ODP-EL concepts: community, role, deontic token, policy
          Q: What is the governance structure?

Layer 2 — THIS TOOLCHAIN (el_grammar.tx + el_validator.py + el_reasoner.py)
          Structural governance and accountability tracing
          Q: Who is accountable for obligation O through the chain?

Layer 3 — Runtime engine
          Operational execution: WorldState, transitions, ledger
          Q: What happened, and was each step permitted?

Layer 4 — el_kripke.py (implemented May 2026)
          Kripke semantics (Annex C of ISO/IEC 15414:2015)
          AF φ (obligation), EF φ (permission), AG φ (invariant), utility §C.3/C.4
          Q: Across all possible futures, will obligation O
             eventually be discharged?
```

---

## The Kripke Verifier (`el_kripke.py`)

### What it does

Implements **all four sections of Annex C of ISO/IEC 15414:2015** as Layer 4
of the ComputableGovernance stack. Builds a finite Kripke model M = (W, R, V, w₀)
from a parsed DSL-EL spec and provides verification, utility scoring, and
action recommendation over it.

This is believed to be the first complete implementation of Annex C in a
working toolchain connected to a real ODP-EL grammar and parser.

### Reachability relation R

R is built **from the DSL-EL delegation structure alone** — obligations,
deadlines, and actor assignments generate the full branching tree of possible
futures. Three transition rules expand the model from the initial world:
- **T1 DISCHARGE** — active holder performs the obligated action → DISCHARGED
- **T2 VIOLATION** — deadline steps elapsed, obligation still PENDING → VIOLATED
- **T3 TICK**      — time passes (suppressed if any strict obligation is pending
                     and its holder is active)

An optional **hybrid mode** (implemented as `build_kripke_from_runtime` in `el_kripke.py`) allows the Layer 3
ledger to anchor the initial world and prune unreachable branches.

### Modal operators (§C.2)

| Operator | CTL | Meaning | Used for |
|----------|-----|---------|----------|
| `AF φ` | Along all paths, Finally φ | φ on every possible future eventually | Obligation verification |
| `EF φ` | there Exists a path, Finally φ | φ on some possible future | Permission verification |
| `AG φ` | Along all paths, Generally φ | φ in every reachable world | Invariant checking |

### Utility function (§C.3)

`utility(world)` is a **priority-weighted average** over obligation outcomes:

```
utility(w) = Σ(score_i × weight_i) / Σ(weight_i)
```

Outcome scores: DISCHARGED=+1.0, PENDING=+0.3, EXPIRED=0.0, VIOLATED=-1.0.

Priority weights from AM-15 `PriorityLevel` on `DeonticTokenDecl`:
- `critical`=1.00, `high`=0.75, `normal`=0.50 (default), `low`=0.25

Result normalised to [-1, +1]. Priority weighting means a violated critical
obligation dominates even when all low-priority obligations are discharged.

### BDI recommender (§C.4)

`expected_future_utility(world)` — mean utility over all worlds reachable
from w; captures long-run quality of a choice, not just the immediate outcome.

`recommend_action(world)` — ranks all available transitions by expected future
utility. Rank 1 is the advised action. This is the BDI connection:
- Beliefs  = current world
- Desires  = priority-weighted utility function
- Intention = rank-1 recommended action

`walk_recommended_path()` / `render_recommended_path()` — follows the greedy
best-action sequence from the initial world, showing alternatives at each step.

### DSL grammar additions (AM-13, AM-15)

```
burden seekConsentObligation {
    state: active
    deadline: "clinical session"
    discharge_mode: strict     ← AM-13: AF holds by construction
    priority: critical         ← AM-15: feeds weighted utility
}
```

### Key finding (consent scenario — two obligations)

```
[seekConsentObligation]  priority=critical  mode=strict    AF=✓  EF=✓
[reportingObligation]    priority=low       mode=eventual  AF=✗  EF=✓
```

Recommender output from initial world:
```
Step 1: ★ discharge:seekConsentObligation by AIDiagnosticAgent  (EFU=+0.870)
        Alternative: discharge:reportingObligation by GPPracticeParty (EFU=+0.720)
Step 2: ★ discharge:reportingObligation by GPPracticeParty  (EFU=+1.000)
Final:  both discharged, utility=+1.000
```

The recommender derived "consent first" from the DSL structure and priority
weights alone — not from any hard-coded ordering rule.

### Usage

```python
from el_parser import parse
from el_kripke import build_kripke_model

result = parse("consent_scenario.el")
km     = build_kripke_model(result.model, horizon=10)

print(km.render_summary())

# §C.2 — modal verification
print(km.check_obligation("seekConsentObligation").render())
print(km.check_permission("seekConsentObligation").render())

# §C.3 — utility-ranked worlds
for world, score in km.ranked_reachable(km.initial):
    print(f"  utility={score:+.3f}  {world.obligation_dict()}")

# §C.4 — BDI action recommendation
print(km.render_recommended_path())
```

### Standalone test (no parser required)

```bash
python el_kripke.py    # runs synthetic consent scenario (§C.2 only)
```

---

## Known Limitations and Open Issues

**Validator:**
- V-03 uses items*=StepBodyItem structure; checks ActorRef in items list
- V-15 checks obligation text against CommitmentDecl only (not mid-chain);
  this is intentional but means obligations that enter only via delegation
  (no explicit commitment) will trigger the rule

**Reasoner:**
- `can_perform()` is static only — does not model runtime token changes
- Delegation chain walk is depth-first, follows first matching link;
  multiple parallel chains are each returned as separate AccountabilityChain
- `policy_conflicts()` uses simple obligation/prohibition text matching;
  does not handle semantic equivalence of differently-worded rules

**Runtime engine:**
- Claiming (2.0.0): a burden offered to a pool is claimable, and the
  holder who made the accept Evaluation claims it by performing its action
  or calling `claim()`; an accept alone changes nothing and a reject is a
  no-op. The engine enforces this. The static verifier does so only for
  members of an `any_discharged` group that has a structured Evaluation; a
  burden declared `state: claimable` outside such a group starts pending
  and is discharged without a claim. The hybrid verifier has no claim
  step: it treats claimable as pending, so it can discharge a burden
  nobody claimed
- `setting_behaviour` and `community_object` (2.0.0): both are parsed, and
  `community_object` is validated (its `abstracts` community must be
  declared), but nothing reads either at runtime or in the verifier.
  `member: C fills R` and `represented_by` have no effect. A federation
  `role` with `X fills R` does take effect

**Typed policy values (2.1.0):**
- `-0` reads as the integer `0` (the sign is lost); `-0.0` keeps its sign
- Leading zeros are accepted (`007` is `7`)
- Durations and integer intervals still accept a leading `+` (`+5 days`,
  `+1..3`) as policy values; plain numbers do not, and neither does a
  duration limit in a comparison (2.2.0)
- Envelopes are checked by the validator only: an `initial_value` outside
  its envelope is an error (`envelope-membership`), and so is an amount in
  another currency than the envelope's (`envelope-currency`). No engine or
  verifier rule reads an envelope
- `5 sec` gets no "if you meant a duration" hint: there is no seconds
  unit to suggest
- Policy values are read-only. The engine reads a policy's typed
  `initial_value` from the specification as a comparison limit, as a
  standing duty's `ends_at` and, 2.2.0, as a policy-fed deadline; the
  verifier reads a policy's declared value only as a policy-fed deadline
  (R19), never `WorldState.policy_values`.
  The text copy seeded into `WorldState.policy_values` is read by nothing
  in the toolchain. The superseded gp_referral API builder does not seed it
- A NormativePolicy's value is checked but not seeded
- Currency codes are not looked up in the ISO 4217 list; options of a
  user-defined type are not checked unless (2.2.0) the type names a
  declared options set
- A quoted string and a bare name both read as text and cannot be told
  apart

**Deadlines (2.1.0):**
- `as_at` is asserted by the caller, and nothing checks it against real
  time. A future `as_at` violates a date burden early, and a violation
  cannot be undone; the only guard is that `as_at` cannot go backwards
  within one runtime. (v2.0.0 never judged a deadline by its date.)
- One fixed UTC offset per run: no daylight saving, no holidays.
- Two clocks in one ledger: durations are judged on the tick, dates on
  `as_at`, so the ledger order is not wall-clock order.
- Durations run on the step clock, where every applied act also costs one
  minute: five acts inside a "5 minutes" window violate it with no time
  passing (as in v2.0.0).
- Strict burdens with a date deadline are not judged: the clock never
  violates a strict burden, and `declare_violation()` refuses any deadline
  containing a date. (v2.0.0 refused a date with no unit word, but
  accepted `"by 2026-11-30 end of day"` as 30 days after activation.)
- The verifier does not model date deadlines.
- An episode that concludes before the date leaves a date burden open: it
  is never violated by episode conclusion. (In v2.0.0 a date deadline with
  no unit word, in an opted-in group, was violated when its episode
  concluded.)
- `as_at` appears in the ledger only in a violation's effect: a check that
  violates nothing leaves no record of the `as_at` it used.
- A date mixed with other numbers is not measured (v2.0.0 enforced
  `"within 5 days of 2026-11-30"` as 5 days and `"by 2026-11-30 end of
  day"` as 30 days after activation).
- A deadline with several durations is measured by its first one only, as
  in v2.0.0 (`"2 weeks and 3 days"` is 2 weeks); 2.1.0 warns.

**Comparisons (2.1.0):**
- Reported values are asserted by the caller and trusted as given; the
  toolchain records the text it compared, not where it came from. (v2.0.0
  had no comparison: `precondition: "x" >= 5` did not parse.)
- The verifier assumes every precondition holds. For a strict burden whose
  discharging action has a precondition, `compelled` can be true while the
  engine refuses the discharge. This is so in v2.0.0 for plain
  preconditions; 2.1.0 states it (`[W-strict-precondition]`,
  `assumes_preconditions`) and does not close it.
- Step preconditions are not enforced: in v2.0.0 a step with a failing
  plain precondition, or with its fact missing, proceeds; 2.1.0 is the
  same, and refuses a comparison in a step (`comparison-in-step`).
- A plain precondition passes on any truthy fact, including the strings
  `"false"`, `"no"` and `"0"`, as in v2.0.0.
- Envelopes: v2.0.0 accepted an initial value outside its envelope, or of
  another kind, unchecked; 2.1.0 refuses it (`envelope-membership`).
  Amounts did not parse in v2.0.0.
- 2.2.0 adds `==` and `!=`, and date, instant and duration limits (2.1.0
  had neither). A policy limit is its initial value (values are
  read-only). Options have no order: a policy of an options type is
  compared with `==` and `!=` only, and there is no option literal. There
  are no string or boolean limits.
- Facts must be text; a JSON number is refused as not established.

**Standing duties (2.1.0):**
- v2.0.0 cannot express a standing duty: `standing keeps: …` is a syntax
  error. A duty "for the term of the contract" could be written only as a
  burden with a prose deadline, which the v2.0.0 engine never violates
  (`[W-24]` warns), which `discharge_burden()` ends, and whose discharge the
  verifier offers at any step. 2.1.0 adds standing duties, and withholds
  the verifier's claims about them instead of modelling them.
- Reported values are asserted by the caller; kept means kept at the
  moments checked, and nothing runs a check on its own.
- A term end by date needs a clock; one fixed UTC offset.
- Not supported: a term given as a duration, declaring a breach, ending a
  term by community conclusion.

**Found by running contract clauses (v2.0.0 and 2.1.0):**

Procurement and contract clauses (a Contractor, a Principal) were written
as small specifications and played through the Runtime on v2.0.0 and on
2.1.0. Each code block below is an excerpt from a specification that
parsed and validated with its scaffolding (parties, role fillers, the
community); it is not a complete specification. Where a result is the
same on both versions, it says so. Re-run on 2.2.0, every clause gives the
same results as on 2.1.0.

- **`effect destroy` acts on burdens only.** v2.0.0 and 2.1.0, the same:
  aimed at a permit or an embargo, the action returns ok, the token stays
  active, the ledger has no effect line and the validator gives no
  warning. After `endSiteAccess` the permit's action still runs; after
  `liftRemovalEmbargo` the embargo still blocks. Aimed at a burden, it ends
  it, but the ledger reads `discharged burden 'siteCleanupBurden'`, as if
  the work had been done.

  ```
  action endSiteAccess { actor: contractorRole effect destroy siteAccessPermit }
  action liftRemovalEmbargo { actor: contractorRole effect destroy equipmentRemovalEmbargo }
  action cancelCleanup { actor: contractorRole effect destroy siteCleanupBurden }
  ```

- **`effect create` grants the token active.** v2.0.0 and 2.1.0, the same:
  whatever state the token was declared with, it is created active and its
  trigger is ignored, so its deadline counts from creation. Below, with the
  defect never reported, `fixDefect` was violated two hours after the work
  order (`elapsed 122 >= deadline 120 steps`). Reported 61 minutes after
  the work order, it was violated at minute 123 (`elapsed 123 >= deadline
  120 steps`), only 62 minutes after the report. A token that must wait for
  an event has to be held by its party from the start of the run.

  ```
  burden fixDefect {
      for_action: "repairDefect"
      state: pending
      deadline: "2 hours"
      triggered_by: defectReported
  }

  action issueWorkOrder { actor: principalRole effect create fixDefect to contractorRole }
  ```

  2.1.0 only: a standing duty created this way is active and judged from
  creation, so a check before its trigger can breach it. Its `ends_at` and
  `ended_by` still end it.

  ```
  action issueWorkOrder { actor: principalRole effect create keepLiabilityCover to contractorRole }
  ```

- **`for <role>` is not checked.** v2.0.0 and 2.1.0, the same: in
  `requires_permit p for r` the `for r` part is parsed and stored, but the
  engine checks the performer's own permit. With the permit held by the
  Principal, the Contractor's action below is refused (`required permit
  'subcontractApproval' not held by actor`); held by the Contractor, it
  runs. An undeclared role name is accepted without warning.
  `inhibited_by_embargo e for r` parses through the same rule; only the
  `requires_permit` form was run.

  ```
  action subcontractWork {
      actor: contractorRole
      requires_permit subcontractApproval for principalRole
  }
  ```

- **The contents of a `conditional_action` are not read.** v2.0.0 and
  2.1.0, the same: it is parsed and its token names are resolved, but
  nothing reads it (engine, validator, Kripke model, reasoner). It sits in
  a role beside actions, not inside one. Below, the ordinary action
  `subcontractWork` (declared beside it with no `requires_permit`) runs
  without the permit, and `subcontractWithApproval` can itself be
  performed as an undeclared, unrestricted action. Write the rule as an
  ordinary action with `requires_permit`.

  ```
  conditional_action subcontractWithApproval {
      actor: contractorRole
      requires_permit subcontractApproval
  }
  ```

- **An act carries no time.** v2.0.0 never judged a deadline by its date.
  2.1.0 judges a date deadline only at a check, against its `as_at`; an act
  carries no wall-clock time. A delivery made after the due moment but
  before the next check is recorded as `discharged burden
  'deliverReport'`, and the later check reports nothing: the late act
  counts as on time.

  ```
  deadline: "by 2027-06-30"
  ```

- **A standing duty's breach is reported once.** v2.0.0 cannot express a
  standing duty. In 2.1.0 the first breach makes the duty violated; later
  checks, with a bad or a good value, add nothing, and the API's
  `standing` list no longer includes it (`standing=[]`).

  ```
  burden keepLiabilityCover {
      standing
      keeps: "public liability cover" >= MinimumLiabilityCover
      ends_at: ContractEnd
      ended_by: contractCompleted
      state: pending
      triggered_by: contractAwarded
  }
  ```

- **A term-ending event that fires before the duty starts is forgotten.**
  v2.0.0 cannot express a standing duty. In 2.1.0, with the duty above,
  `contractCompleted` fired before `contractAwarded` changes nothing; at
  the award the duty becomes active, and a later check with a low value
  breaches it although the contract was already completed.

- **Values must be in the exact notation.** v2.0.0 has no comparison
  (`precondition: "x" >= 5` does not parse). In 2.1.0 a value written in
  any other form is never compared. In a precondition the act is refused
  as not established: `"25000000"` gives `precondition not established:
  'public liability cover' reported 25000000: not an amount value`, and
  `"25000000 NZD"` is refused for its currency. In a standing duty the
  check gives "not judged", never a breach: `"8.5"`, `"0.085"` and `"10 %"`
  each give `'subcontract share' reported <value>: not a percentage
  value`.

  ```
  precondition: "public liability cover" >= MinimumLiabilityCover
  keeps: "subcontract share" <= MaximumSubcontractShare
  ```

- **A date written in words is not enforced.** v2.0.0 and 2.1.0, the same:
  the deadline below is accepted with two warnings and is never violated
  (the step clock was run to 100000 minutes on both; on 2.1.0 a check with
  an `as_at` in July also reports nothing, not even "not judged"). The
  2.1.0 date warnings do not fire, because the text has no `YYYY-MM-DD`
  date. Write `"by 2027-06-30"`.

  ```
  deadline: "by 30 June 2027"
  ```

  The two warnings, on both versions:
  - `[W-24] Eventual burden 'deliverReport' has no enforceable deadline
    ('by 30 June 2027') and no episode-conclusion path: it is never
    violated, at runtime or in the verifier. Give it a deadline with a
    time unit, or put it in a satisfaction group whose community opts in
    with on_objective_achieved. (§6.4.3, §7.8.7)`
  - `[W-25] Burden 'deliverReport' has deadline 'by 30 June 2027': it
    contains a number but no recognised time unit (second, minute, hour,
    day, week, month, year), so the number is ignored and the deadline is
    never measured, at runtime or in the verifier. Write the unit out,
    e.g. "2 hours". (§6.4.3, §7.8.7)`

- **The suggested deadline scale misses a burden granted by `holds`.**
  v2.0.0 and 2.1.0, the same: for the burden below, held by the Contractor
  through `holds`, `el_kripke.suggest_deadline_scale(spec, 10)` returns 1,
  because the suggestion reads only spec-level obligation descriptors and
  this burden has none. At k = 1, after the incident,
  `GET /obligations/notifySafetyIncident/status` gives `compelled: false`,
  `detectable: true` and `status: "not resolved within horizon"`. With
  `deadline_scale=160` set by hand, it gives a counterexample that ends
  with the burden violated.

  ```
  burden notifySafetyIncident {
      for_action: "notifyIncident"
      state: pending
      deadline: "24 hours"
      triggered_by: safetyIncident
      discharge_mode: eventual
  }
  ```

**Grammar (known textX/arpeggio issues):**
- FederationDecl uses per-line `member:` declarations (not comma list)
  due to arpeggio cross-reference list resolution bug
- DomainDecl uses `controlled_object:` per line for same reason
- Boolean flags use `key: true` style (absence = false); `key: false`
  is not valid syntax — simply omit the flag

---

## CLI Quick Reference

```bash
# Parse and validate a specification
python el_parser.py my_spec.el

# Trace accountability chain
python el_reasoner.py my_spec.el "obligation text here"

# Detect policy conflicts
python el_reasoner.py my_spec.el --policy-conflicts

# Run Kripke modal verification (Layer 4 — full Annex C)
python el_kripke.py                        # synthetic consent scenario (standalone)

# In Python — full Layer 4 pipeline
# from el_parser import parse
# from el_kripke import build_kripke_model
# km = build_kripke_model(parse("consent_scenario.el").model)
# km.check_obligation("seekConsentObligation").render()   # §C.2 AF
# km.ranked_reachable(km.initial)                         # §C.3 utility
# km.render_recommended_path()                            # §C.4 BDI planner

# Run the worked example
python el_parser.py example.el
python el_reasoner.py example.el "Process all customer payments within SLA"
```

---

## Dependencies

```bash
pip install textX   # version 4.3.0 confirmed working
```

No other dependencies beyond the Python standard library.
