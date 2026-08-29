# DN_010 — Episode-Conclusion-Based Deadline Checking (Option (b), Properly Scoped)

*Design note, written same-day per direct instruction not to postpone.
Directly follows CC's 2026-08-29 investigation and mitigation
(`CONCEPTS_INDEX.md`'s "referral episode" finding). Grounded in the
actual `referral_scenario.el` and `el_engine.py` source, verified by
grep — not speculation.*

---

## 0. The headline finding — this reframes option (b) considerably

CC's investigation stated: *"nothing in `WorldState`/`TokenInstance`
currently represents 'has this episode concluded' as a checkable
condition."* **That's only half true, and the missing half changes the
whole scope of this problem.**

The concept of "episode concluded" **already exists, declared
explicitly**, in `ReferralEpisodeCommunity` itself:

```
community ReferralEpisodeCommunity
    description: "... dissolved on objective achievement"
    {
        objective: "Complete specialist assessment for the referred patient"
            satisfaction: all_discharged(referralBurdenGroup)
```

This is not an invented framing — it's the scenario's own stated
lifecycle. **What's missing is not the concept. It's that the live
engine never implements it.** Confirmed by grep across `el_engine.py`:
zero references to community dissolution or objective-achievement-
triggered termination anywhere. The grammar declares it; nothing checks
it at runtime. This is the same "declare vs verify" gap DN_004 already
names as this project's recurring pattern — found again, one layer up,
at the community-lifecycle level rather than the FHIR-Obligations level.

## 1. What this means for option (b)'s actual scope

Not "invent a new WorldState concept from nothing," as the prior
investigation's phrasing implied. **Two concrete, sequenced pieces:**

**(b-1) Implement live community-conclusion tracking.** When a
community's declared objective satisfaction condition
(`all_discharged(referralBurdenGroup)`, or whatever a given community
declares) becomes true, the engine should record that community as
concluded — likely a field on `WorldState` or a parallel structure,
checked/updated wherever the engine already evaluates objective
satisfaction (the same machinery already powering the live
`objective-score`/`objective-reachable` endpoints this whole session has
used).

**(b-2) Wire episode-scoped (no-magnitude) deadline checking to it.**
`check_live_violations()`, for any burden whose deadline has no genuine
magnitude (per yesterday's `_has_deadline_magnitude()`), should check:
*has the owning community concluded?* If yes, and the burden is still
undischarged, **that** is the violation condition — not elapsed ticks at
all. If the community hasn't concluded, the burden stays exactly as
today's mitigation already leaves it: never tick-violating.

## 2. Compatibility with today's shipped mitigation — confirmed, not just assumed

(b) does not require undoing (a). Today's fix means "never violate via
elapsed ticks" for no-magnitude deadlines — a correct default in the
*absence* of conclusion-tracking. (b) adds a **second**, conclusion-based
trigger on top, for when conclusion-tracking exists. No conflict; (b) is
a strict extension of (a), not a replacement.

## 3. One honest, unresolved sub-question — don't let this get silently decided

`all_discharged(referralBurdenGroup)` captures the **successful**
conclusion path. An episode could plausibly end **unsuccessfully** too —
patient withdrawal, an abandoned/escalated referral — and nothing in
this design as scoped so far covers that second path. Recommend treating
successful-conclusion tracking (b-1/b-2 above) as the first, smaller
increment, and explicitly deferring the unsuccessful-conclusion question
rather than trying to solve both at once.

## 4. Group membership — checked, confirmed, not left open

Confirmed by direct inspection of `referral_scenario.el`:

```
token_group referralBurdenGroup {
    member: referralInitiationBurden
    member: clinicalHandoverBurden
    member: referralResponseBurden
    member: assessmentSchedulingBurden
    member: aiExaminationBurden
}
```

Both `clinicalHandoverBurden` and `aiExaminationBurden` — the two
affected episode-scoped burdens — **are** members of the exact group
`ReferralEpisodeCommunity`'s objective depends on. No separate or
additional group needs defining; (b-2) can reference
`referralBurdenGroup`'s own `all_discharged` condition directly.

## 5. What this note deliberately does not do

No code proposed. No decision made on whether to implement this now or
sequence it after the FHIR mapping work already in progress
(`DN_009`/`R33`) — that's yours to decide, informed by this scoping
rather than left vague.
