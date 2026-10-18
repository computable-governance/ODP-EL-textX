# ODP-EL Grammar — Version 2

This directory contains the extended, unified textX-based implementation
of the ODP Enterprise Language (ISO/IEC 15414:2015), developed by
Zoran Milosevic (Deontik) as the basis for the EDOC 2026 paper.

## Files

- `el_grammar.tx` — unified ODP-EL grammar with greatly extended coverage
  of ISO/IEC 15414 concepts (estimated ~95%) in a single file

## Coverage

Version 2 provides greatly extended coverage of ISO/IEC 15414 concepts
(estimated ~95%). Key advances over v1:

- Unified single-file grammar (no partitioning required)
- Top-level speech act declarations (commitment, delegation, authorization,
  declaration) as first-class constructs
- Order-independent body items within enterprise specifications
- Complete deontic token lifecycle (burden, permit, embargo)
- Delegation chains with sub-delegation control and discharge modes
- Federation constructs for multi-community governance
- Policy envelope and policy value integrated into the unified grammar
- Cross-reference resolution across all construct types

## 2.1.0 additions

Full text in `docs/DSL_TOOLCHAIN_REFERENCE.md`; each change is logged as
2.1.0-1 to 2.1.0-25 in `docs/el_grammar_amendments.md`.

- **Typed policy values.** `integer`, `decimal` (`number` is an alias),
  `percentage` (`4.25%`), `amount` (`250.00 AUD`), `date` (`2026-11-30`),
  `instant` (`2026-11-30T17:00+10:00`, a UTC offset required), `string`,
  `boolean` and `duration`. An integer literal is an integer and a decimal
  is exact (in 2.0.0 every number was a float); `1e3`, `+5`, `5.` and `.5`
  are syntax errors.
- **Durations.** Written as a whole number and a unit, `60 days`, as in
  2.0.0. This is a recorded deviation: ISO 8601 writes `P60D`, which is
  not accepted.
- **Date deadlines.** A `deadline` string that is a date or an instant
  (`"by 2026-11-30"`, `"2026-11-30T17:00+10:00"`) is judged against a
  wall-clock time supplied at check time, under a clock; a duration
  deadline (`"21 days"`) is counted from activation, as in 2.0.0.
- **Comparisons in preconditions.** `precondition: "<fact>" >= <limit>`
  (also `<=`, `>`, `<`, and from 2.2.0 `==`, `!=`), the limit a number,
  percentage, amount or policy, and from 2.2.0 a date, instant or duration
  literal or policy, or a policy of an options type (`==` and `!=` only).
  There is no arithmetic.
- **Options sets (2.2.0).** `options ApprovalStates [pending, approved,
  rejected]` declares the options a user-defined policy type allows; a
  policy of that type takes one of them. A type that names no options set
  is not checked, as in 2.1.0.
- **Policy-fed deadlines (2.2.0).** `deadline: NoticePeriod` names a
  Policy of type duration instead of quoting the duration; the deadline
  is the policy's declared value, read-only, counted as the same literal
  duration would be.
- **Standing duties.** `burden X { standing keeps: <comparison>
  ends_at: <date, instant or policy> ended_by: <event> ... }`: a burden
  kept for a term and judged at each check.

The source standards and ISO/IEC 15414 clauses of these additions are to
be confirmed; each new validator message ends "(clause to be confirmed)".

## Known Gaps

The remaining gaps are semantic precision items rather than missing
concepts; see `docs/el_grammar_amendments.md` and the Known Limitations
in `docs/DSL_TOOLCHAIN_REFERENCE.md`.

## Reference

This grammar is described in:

> Milosevic, Z. (2026). *Computable Governance for Autonomous Agents.*
> EDOC 2026. *(in preparation)*

## Relationship to v1

Version 2 is not a direct extension of v1 — it is an independent
reimplementation that addresses the open design questions documented
during v1 development, particularly around token lifecycle, delegation
semantics, and the integration of policy constructs. Both versions are
MIT licensed and can be used independently.
