# Engine and verifier parity

Each row sets a runtime engine rule (Layer 3, `toolchain/el_engine.py`,
`toolchain/el_runtime.py`) beside the Kripke rule that models it (Layer 4,
`toolchain/el_kripke.py`), and says whether the verifier mirrors it,
abstracts it or leaves it out. **Update this table in the same commit as
any change to an engine rule or a Kripke rule**, so that it does not drift
from the code. Started in 2.1.0-5 with the rows about deadlines, the clock
and policy values; other parts of the engine are not yet listed.

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
| R1 | A duration deadline is violated when the tick minus the activation tick reaches its steps (eventual burdens; `check_live_violations()`) | T2 from activation, both builders | Mirrored | — |
| R2 | Activation by a `triggered_by` event (its first firing starts the deadline) | Hybrid: events activate every waiting token; static: obligations only | Hybrid mirrored; static abstracted | Under (static: event-activated permits and embargoes) |
| R3 | Activation by an `activate` effect | none | Absent | Under (an obligation activated by an effect never activates in the model) |
| R4 | Every applied act advances the tick by one; the model's acts take no time | Only the tick rule (T3) advances a step | Abstracted | Over (discharge before a deadline is easier in the model) and under (while a strict burden blocks the tick, the model cannot step) |
| R5 | A deadline containing a calendar date has no duration magnitude, whatever follows the date (2.1.0-6; before, `"by 2026-11-30 end of day"` was read as 30 days) | The same predicate (`_has_deadline_magnitude()`) | Mirrored | — |
| R6 | A date deadline on an eventual burden (a date alone, or a date and time with an offset) is judged against a caller-supplied `as_at` under a `DeadlineClock`: violated when `as_at` is at or after the due instant; without a clock or an `as_at` it is not judged (2.1.0-7) | none: a date deadline is not enforceable in the model | Absent | Under (no date violation path). It never makes `compelled` true: an eventual date burden is never reported compelled while it is pending (`tests/test_date_deadlines.py`) |
| R7 | A burden whose deadline contains a date is never violated by episode conclusion, judged or not (2.1.0-7) | T2b is still offered for it (it has no magnitude) | Abstracted | Over (a conclusion violation the engine never makes); the safe direction for `compelled` |
| R8 | A strict burden is violated only by a declaration (`declare_violation()`, duration deadlines) | No declaration edge; a strict burden blocks the tick | Absent | **Under. `compelled` may be true for a strict burden while a declaration can violate it** |
| R9 | A deadline with no magnitude and no date, eventual, in an opted-in group, is violated when its episode concludes | T2b | Mirrored | — |
| R10 | Policy values are seeded read-only into `WorldState.policy_values` | Not read | Not used | — (checked by `tests/test_policy_values_invisible_to_verifier.py`) |
