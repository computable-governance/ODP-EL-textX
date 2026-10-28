# Engine and verifier parity

Each row sets a runtime engine rule (Layer 3, `toolchain/el_engine.py`,
`toolchain/el_runtime.py`) beside the Kripke rule that models it (Layer 4,
`toolchain/el_kripke.py`), and says whether the verifier mirrors it,
abstracts it or leaves it out. **Update this table in the same commit as
any change to an engine rule or a Kripke rule**, so that it does not drift
from the code. Started in 2.1.0-5 with the rows about deadlines, the clock
and policy values; preconditions added in 2.1.0-12, standing duties in
2.1.0-17, policy-fed deadlines in 2.2.0-8, token events (unreleased). Other parts of the engine are not yet listed.

**Conventions**
- *Static* is `build_kripke_model()` (before execution). *Hybrid* is
  `build_kripke_from_runtime()` (anchored to the current runtime state).
- **Over** (over-approximation): the verifier admits behaviour the engine
  refuses. Extra paths: EF may be falsely true, AF falsely false.
- **Under** (under-approximation): the verifier omits behaviour the engine
  allows. Missing paths: AF may be falsely true, EF falsely false.
- **When the verifier must change.** A verifier change is needed only if
  leaving a row absent or abstracted makes the verifier wrong in the unsafe
  direction for a claim users rely on. The main such claim is `compelled`
  (AF: the burden discharges on every path) on `GET
  /obligations/{token}/status`. An eventual burden is never reported
  compelled while it is pending, because a path on which it stays pending
  always exists, so a missing violation path cannot make that claim
  falsely true.

| # | Engine rule | Verifier | Status | Direction |
|---|---|---|---|---|
| R1 | A duration deadline is violated when the tick minus the activation tick reaches its steps (eventual burdens; `check_live_violations()`). The duration is a literal or, 2.2.0-7, a duration policy's declared value (`deadline: <Policy>`, read through `deadline_text()`) | T2 from activation, both builders; the deadline read through the same `deadline_text()` (2.2.0-8, R19) | Mirrored | — |
| R2 | Activation by a `triggered_by` event (its first firing starts the deadline) | Hybrid: events activate every waiting token; static: obligations only | Hybrid mirrored; static abstracted | Under (static: event-activated permits and embargoes) |
| R3 | Activation by an `activate` effect | none | Absent | Under (an obligation activated by an effect never activates in the model) |
| R4 | Every applied act advances the tick by one; the model's acts take no time | Only the tick rule (T3) advances a step | Abstracted | Over (discharge before a deadline is easier in the model) and under (while a strict burden blocks the tick, the model cannot step) |
| R5 | A deadline containing a calendar date has no duration magnitude, whatever follows the date (2.1.0-6; before, `"by 2026-11-30 end of day"` was read as 30 days) | The same predicate (`_has_deadline_magnitude()`) | Mirrored | — |
| R6 | A date deadline on an eventual burden (a date alone, or a date and time with an offset) is judged against a caller-supplied `as_at` under a `DeadlineClock`: violated when `as_at` is at or after the due instant; without a clock or an `as_at` it is not judged (2.1.0-7) | none: a date deadline is not enforceable in the model | Absent | Under (no date violation path). It never makes `compelled` true: an eventual date burden is never reported compelled while it is pending (`tests/test_date_deadlines.py`) |
| R7 | A burden whose deadline contains a date is never violated by episode conclusion, judged or not (2.1.0-7) | T2b is still offered for it (it has no magnitude) | Abstracted | Over (a conclusion violation the engine never makes); the safe direction for `compelled` |
| R8 | A strict burden is violated only by a declaration (`declare_violation()`, duration deadlines) | No declaration edge; a strict burden blocks the tick | Absent | **Under. `compelled` may be true for a strict burden while a declaration can violate it** |
| R9 | A deadline with no magnitude and no date, eventual, in an opted-in group, is violated when its episode concludes | T2b | Mirrored | — |
| R10 | Policy values are seeded read-only into `WorldState.policy_values` | Not read. A policy-fed deadline (R19) is read from the specification (the policy's declared value), never from `WorldState.policy_values` | Not used | — (checked by `tests/test_policy_values_invisible_to_verifier.py` and `tests/test_policy_deadline.py`) |
| R11 | An action's preconditions, plain (the reported fact is truthy) or a comparison (a reported value against a literal or a policy, 2.1.0-12; operators `>= <= > < == !=`, 2.2.0-2; a number, percentage, amount, or, 2.2.0-5, date, instant or duration limit), are checked when the act is performed, by `advance()` and `declare_violation()`; false or not established refuses the act | none: every precondition is assumed to hold (T1 discharges by the holder without naming an action) | Absent | Over (paths the engine refuses). **Unsafe for `compelled` on a strict burden whose discharging action has a precondition**: the model's discharge edge replaces what is a dead end in the engine, so `compelled` may be true while the engine refuses the discharge. The gap exists since v2.0.0 for plain preconditions. Stated, not closed (2.1.0-14): the warning `[W-strict-precondition]` flags such a burden at specification time, and `GET /obligations/{token}/status` lists the assumed preconditions under `assumes_preconditions`. Pinned by `tests/test_strict_precondition_guard.py` |
| R12 | A comparison reads a policy limit at its value: the policy's typed `initial_value` (policy values are read-only), of type integer, decimal, number, percentage, amount, or, 2.2.0-5, date, instant or duration, or, 2.2.0-12, an options type (its option, compared with `==` and `!=` only; an ordering operator is not established) | Not read | Not used | — (preconditions as a whole are R11) |
| R13 | A standing duty (2.1.0-17) is never ended by an action (its for_action), a destroy effect, an event other than its ended_by, discharge_burden() or a declaration, and never violated by a deadline or episode conclusion | T1 discharges it at any step like any obligation (and T5, T6, T11 would, given a for_action or discharged_by, which the validator refuses) | Absent | Over: `detectable`, witness paths, `all_discharged` and the planner may show it discharged by its holder. Safe for `compelled` only because a standing duty cannot be strict (validator). Pinned by `tests/test_standing_exclusions.py`. Claims withheld (2.1.0-20): `[W-standing-not-modelled]`; `GET /obligations/{token}/status` gives "standing duty: not modelled" with `standing: true` and null `compelled`/`detectable`; `GET /kripke/witness` refuses `discharged:`/`violated:` of the duty and `all_discharged` (422); the recommended action leaves out its discharge, and its Q-values are computed without the discharge edges (2.1.0-23) |
| R14 | Breach (2.1.0-18): at a check with `as_at`, a standing duty whose keeps comparison (`>= <= > < == !=`, 2.2.0-2; a date, instant or duration limit too, 2.2.0-5) is false against the reported facts is violated, once | none | Absent | Under: `violated:` and `any_violated` unreachable for it. Safe for `compelled` |
| R15 | Term end by date or instant (2.1.0-18): with a clock and an `as_at` at or after `ends_at` (a date alone: the end of that day in the clock's offset), the duty is met (discharged) and its keeps is not judged | none (dates are not modelled, R6) | Absent | Under: the real end is missing; the discharged state is reachable only through R13's holder discharge |
| R16 | Term end by event (2.1.0-18): when its `ended_by` event fires (an emitting action or `fire_event()`), an active standing duty is met | none | Absent | Under |
| R17 | Not judged (2.1.0-18): nothing reported, not text, wrong kind (2.2.0-5: not a date, instant or duration value, so a date reported against an instant limit, or an instant against a date; 2.2.0-12: not one of the options of an options-typed policy limit, or an ordering operator against one), another currency, no `as_at`, or a term end that cannot be judged: no verdict, never "kept" | not applicable | — | — (covered by R14) |
| R18 | A standing duty is not a satisfaction-group member (2.1.0-19: the validator error `standing-in-group`), so it neither concludes nor blocks an episode or objective | not a member either (the groups are read from the same declarations) | Mirrored (by exclusion) | — |
| R19 | A policy-fed deadline (`deadline: <Policy>`, 2.2.0-7) is the policy's declared duration (`initial_value`), read through `deadline_text()`; a policy not of type duration or with no usable value gives no measurable deadline | Both builders read the same declared value through `deadline_text()` at build time (2.2.0-8): enforceable deadlines and the hybrid fallback steps | Mirrored | — while policy values are read-only. If policy values ever change at run time, this row becomes both directions until the verifier reads the same value |
| R20 | Each record lists its token events (`token_events`: a grant, a state change or a removal of one instance, with who made it and why), found by comparing the instances before and after the act; a runtime's build record lists the initial grants. No engine rule reads them, and they change no other field of a record or state | Not read: the hybrid builder reads only `discharged` from the ledger, and the build record is not in the ledger | Not used | — (pinned by `tests/test_ledger_token_events.py`: with events switched off, every record and state is the same) |
