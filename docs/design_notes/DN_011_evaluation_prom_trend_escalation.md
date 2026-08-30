# DN_011 — Evaluation-Gated PROM Trend Escalation

**Status:** Design note, not yet scoped for implementation.
**Date:** 2026-08-30.
**Follows on from:** R39 (AM-74, touchpoint 6 escalation logic) and the
DN_007 finding that no escalation logic appears anywhere across the six
ConnectedCare diagrams.

## 1. The gap R39 leaves open

R39, as built, creates a "must review within 7 days" Burden for EVERY
Observation unconditionally, escalating to the GP only if that review
never happens. This is a real, working compliance-SLA mechanism -- but
it is not "escalate if deteriorating," which is what DN_007's original
finding actually named. A PROM (Patient-Reported Outcome Measure --
a standardised instrument where the patient self-reports functional
status, symptoms, or quality of life as a score) that stays perfectly
stable still generates the identical review burden as one showing sharp
decline. The blanket approach is a reasonable, low-risk first step, not
a wrong one -- but it doesn't yet capture the trend-conditional
semantics the real diagram implies.

## 2. Standards grounding: §6.6.7 Evaluation

"evaluation: An action that assesses the value of something... For
example, the action by which an ODP system assigns a relative status to
a thing, according to estimation by the system... Other examples of
automated evaluation are credit scores and insurance underwriting
ratings." (§6.6.7)

The standard's own single worked example (Annex B.1.9.6, e-commerce bid
evaluation) is structurally identical to a PROM trend assessment: raw
data in (bid price, delivery terms, supplier history), a graded
automated judgment out (a relative status/score). This is the standard
reaching for exactly the "improving/stable/deteriorating" shape a PROM
trend needs -- not an accept/reject binary.

Checked and confirmed: the library annex (B.2) has NO Evaluation example
at all -- its own accountability section explicitly enumerates only four
illustrated action types (commitment, declaration, delegation,
prescription). The e-commerce example is the standard's only worked
illustration of this concept across both annexes. This doesn't weaken
the reading above; it just means there's no second annex example to
cross-check against.

## 3. The gap between the standard and the current grammar

grammar/v2/el_grammar.tx's Evaluation construct (confirmed via grep):

    Evaluation:
        'evaluation' name=ID '{'
            'by'          ':' evaluator=[EnterpriseObject]
            'of_target'   ':' target=EvaluationTarget
            'result'      ':' result=EvaluationResult
        '}'
    EvaluationResult:
        result_code=AcceptabilityResult | result_text=STRING
    AcceptabilityResult:
        'accept' | 'reject'

This was purpose-built for a narrower, different use case -- claim
evaluation (accept/reject a claim on a token, tied to the engine's
AM-60-63 claiming logic). Its own docstring comment confirms this
origin. The result_text: STRING fallback COULD hold "deteriorating" as
free text, and of_target's free-text fallback could describe the PROM
informally -- but using it this way stretches a construct built and
tested for a different, more specific purpose, rather than a clean fit.

## 4. Two design paths, not yet decided

**Path A -- stretch the existing construct.** Use result_text: STRING
for the graded judgment ("deteriorating"), of_target: STRING for a
description of what's being assessed. Zero grammar change. Risk:
conflates two different concerns (claim-acceptance and trend-judgment)
under one construct; the AcceptabilityResult enum becomes misleading
noise for this use case (why does a trend-evaluation object expose
accept|reject as an option when it will never use it?).

**Path B -- extend the grammar with a genuine, minimal addition.** A new
EvaluationResult alternative, e.g. a TrendResult enum
(improving|stable|deteriorating), alongside the existing
AcceptabilityResult -- both remaining valid EvaluationResult shapes for
different Evaluation instances. Small, deliberate, backward-compatible
(existing claim-evaluation usage untouched) -- but it IS a grammar
change, with everything that entails (validator updates, a fresh
amendment log entry, re-checking every place EvaluationResult is
pattern-matched).

No recommendation made here -- this is exactly the kind of decision
that should be made deliberately, with the person, not defaulted to
whichever is less code (same discipline as the R37b import-vs-duplicate
decision, AM-68).

## 4a. A third option: Path C -- no grammar or engine change at all

accept/reject (AM-60) was purpose-built for exactly one use case,
DN_003's delegation-claiming problem -- confirmed directly from the
amendment log, not assumed. Before AM-60, Evaluation was pure free text
(STRING/STRING), "confirmed decorative, with zero runtime handlers" --
AM-60 added a second, STRUCTURED alternative alongside the original
free-text form; it did not replace or narrow it. The grammar's own
comment: "the original free-text credit-rating-style use... is untouched
and continues to have no engine effect, exactly as before."

This means the free-text path has always been exactly general enough
for a PROM trend judgment -- it is closer to Evaluation's ORIGINAL
purpose than the accept/reject form is, not a stretch of it.

The real distinguishing question is not "which form is semantically
broad enough" -- both are -- but "does this decision need real engine
significance at runtime." accept/reject matters to the ENGINE because
claim-acceptance is a genuine live, unpredictable-timing decision made
by a real actor while the system is running (AM-61/AM-62 have to react
to it as it happens). A PROM trend judgment is different in kind: it is
knowable entirely from FHIR data already present, AT MAP TIME --
comparing two Observations and computing "deteriorating" is the same
KIND of decision fhir_mapper.py already makes constantly (R38's holder
resolution, R39's .basedOn-vs-.performer choice) -- resolved once, in
Python, before any .el text is generated. It does not need a live actor
deciding anything at runtime the way claim-acceptance genuinely does.

Path C: the trend-gating decision lives ENTIRELY in mapper-side Python
-- no grammar change, no new engine logic. The mapper computes the
trend (comparing sorted Observations for the same patient/instrument)
and decides whether to emit the review-burden + violation_response,
exactly like every other conditional-emission decision in
fhir_mapper.py today. A free-text Evaluation could still be emitted
purely for AUDIT TRACEABILITY (recording why the mapper made that call,
human-readable, in the generated .el) -- but it would carry no engine
significance whatsoever, matching its original, pre-AM-60 purpose
exactly.

Two-layer shape, worth stating explicitly: (1) SENSE -- each Observation
gets assigned a domain value (a score or graded status) -- this is
purely §6.6.7's evaluation concept; (2) ACT -- a trend function over a
SEQUENCE of those values decides whether to create the Burden -- a
discrete governance decision, not a continuous computation. Trend is a
second-order comparison over prior Evaluation.result values, not a
delta computed directly over raw clinical data -- this keeps "value"
doing real work at each individual measurement, with "trend" a
genuinely separate, higher-order operation on top of it.

No recommendation between Path A/B and Path C made here either -- same
discipline as §4's existing A-vs-B framing.

## 4b. "Value" (§6.6.7) is not the same concept as this toolchain's
    utility/Bellman machinery -- important to keep separate

This toolchain already has a formal, working notion of "utility" --
el_kripke.py's utility_for_objective(), used by the Bellman planner to
reason about which future actions best advance obligation-discharge. It
would be a real design mistake to conflate this with §6.6.7's "value"
just because the vocabulary overlaps.

§6.6.7's value ("usefulness, importance, preference, acceptability") is
a domain-specific judgment an evaluator assigns to some EXTERNAL thing
(a bid's quality, a credit score, a patient's functional status) -- an
INPUT to the governance model. The Kripke layer's utility is a measure
of how well the OBLIGATION/TOKEN STATE SPACE is progressing toward a
declared objective -- computed over possible worlds of deontic token
states, not clinical measurements. Different mathematical objects,
different domains, sharing a word by coincidence, not by design.

Concretely: do not feed a PROM score into utility_for_objective()'s
formula. The two-layer sense-then-act pattern in §4a mirrors reward->
policy structure only conceptually (assess a signal, then act on it) --
it is not, and should not become, a literal Bellman formulation.

**Explicitly deferred, flagged but not part of this design's near-term
scope:** a much bigger, more speculative question -- could a community's
stated OBJECTIVE itself ever explicitly include something like patient
wellbeing (not just formal obligation-discharge), such that clinical
"value" and governance "utility" become genuinely the same mathematical
quantity, feeding one unified Bellman formulation? A real, interesting
research question, possibly paper-relevant -- but a much bigger,
separate idea than solving the escalation problem here, and conflating
the two now would make a simple, working mechanism unnecessarily
complicated. Logged here as a flagged future thought, not scoped, not
to be picked up alongside Path A/B/C.

## 5. The harder, separate problem: baseline comparison

Determining "deteriorating" requires comparing AT LEAST TWO Observations
for the same patient + same instrument/code, ordered by
effectiveDateTime -- there is no FHIR field expressing "the trend" or
"the baseline" directly. This is a genuinely different kind of mapping
problem from everything built today: every rule so far (R05-R39) reasons
over ONE resource (or one resource plus its single linked counterpart,
like MedicationDispense.authorizingPrescription) at a time. A trend
evaluation needs to reason across a SET of same-type resources for the
same subject, sorted and compared -- new territory for fhir_mapper.py's
architecture, not just a new resource-type rule.

Sub-questions this raises, unresolved:
- What counts as "the same instrument"? Observation.code matching
  exactly, or something looser?
- How many prior Observations constitute a valid baseline -- the single
  most recent prior one, or a trend across several?
- What threshold or rule determines "deteriorating" vs "stable" vs
  "improving" -- a fixed numeric delta? Any decrease at all? This is a
  genuine clinical-judgment question, not a technical one -- the kind of
  thing that likely needs input from actual clinical guidance, not
  invented by the mapper's author.

## 6. Relationship to the eCDS accountability gap (logged 2026-08-30,
   touchpoint 5)

Structurally similar shape: both are "should the system have caught
something, and who's accountable if it didn't" questions, arising from
data the toolchain sees but doesn't yet reason over meaningfully. Worth
treating as siblings when this area gets picked up -- solving one may
suggest a shared pattern for the other (an Evaluation-gated Burden
creation mechanism), rather than solving them independently.

## 7. Explicitly out of scope for whenever this gets built

- Real clinical scoring algorithms or thresholds -- this project models
  the GOVERNANCE layer (who's obligated to act, and what happens if they
  don't), not clinical decision support itself. The evaluation's actual
  judgment logic is assumed to come from elsewhere (a real eCDS/scoring
  system) -- the design question here is how the toolchain represents
  and reacts to that judgment once made, not how the judgment gets
  computed.
- Modelling every possible PROM instrument type generically -- start
  narrow (one instrument shape, matching R39's existing fixture) and
  generalise only if a second real instrument shape is actually needed.

## 8. Recommended next step, whenever this is picked up

Decide between Path A, Path B, and Path C first (a genuine design
conversation, not something to default), THEN scope the baseline-
comparison mapper logic separately (relevant regardless of which path is
chosen for the gating decision itself) -- these are two different
decisions and shouldn't be bundled into one CC prompt.
