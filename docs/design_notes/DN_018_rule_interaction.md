# Normative and rule-set interaction: why this series keeps finding gaps

**Reflection, logged 2026-09-23.** Prompted by the AM-88 through AM-97
series; not itself a code finding, but recorded because it explains a
pattern that will recur.

Three structurally different things have been happening under one label
("we keep finding new rules"), not two — the original framing conflated
two of them.

---

### A. Correctness bugs (AM-88a/b/c, AM-92, AM-93)

The standard already mandates or permits the behaviour; the toolchain
simply hadn't implemented it. Nothing conceptually new — implementation
catching up to specification.

### B. New heuristics, object level — feature interaction proper (W-16c/e/f/g)

The standard is genuinely silent on whether a *legitimate* construct
should be flagged as risky. Its own scope statement (§1) says it defines
a language "to a level of detail sufficient to enable the determination
of compliance" — it is a grammar and semantics, not an authoring-
assistance or lint specification. It has nothing to say, and by its own
stated scope could not have anything to say, about whether a valid
sentence is a bad idea.

The standard does name a closely related category — worth reading
precisely, not loosely. §7.9.1: "the policies of the two communities
that apply to that object might conflict... the enterprise specification
shall ensure that policy conflicts do not exist, or specify how policy
conflicts are to be prevented or discovered and resolved, or state that
policy conflicts are allowed to cause failures." §7.9.2 NOTE 3 gives
four handling strategies (specification-time assurance, run-time
prevention, run-time discovery-and-resolution, failure handling); §7.7's
NOTE and §7.8.2 name the same root cause for objectives and for an
object fulfilling several roles at once. This is the *direct*-conflict
case — an object cannot satisfy both constraints — already covered in
this toolchain by V-17. §7.9.2 NOTE 2 is the load-bearing line for this
whole category: conflict-management "may be supported by the
specification language or the runtime environment... and may thus not
necessarily be visible explicitly in the enterprise specification." The
standard licenses exactly this shape of tool-level mechanism; it does
not design one.

At this level the pattern is genuinely classic-shape feature interaction,
not a looser analogy: independently-legitimate constructs compose to
produce a real, WRONG runtime outcome, not merely an absence. `[W-16f]`
(`docs/el_grammar_amendments.md`, AM-94) is the pattern this rule exists
to catch: an agent authorized by two distinct authorities, an action's
`requires_permit` naming only one of the granted permits — the other
authority is never consulted, and the action still runs if that
authority's authorization is revoked. Two independently-correct
`Authorization` declarations, composed, produce a real risk neither
declaration states on its own. The telecom "feature interaction problem"
(Bowen et al. 1989 onward; the IOS Press workshop series 1994–1998) is
the direct ancestor of this pattern: independently-correct features
producing unintended emergent behaviour only when composed, worsening
combinatorially as features accumulate. Notably, ISO/IEC 15414 is
jointly ITU-T Recommendation X.911 — the same standards family that
produced the intelligent-network work where feature interaction was
first formally named. The generalisation beyond telephony has already
been made by the feature-interaction community itself: a 2003 FIW panel
abstract (Dini) states that policy-based management systems have "their
own feature interaction problems."

### B′. New heuristics, meta level — detector-coverage gap, not feature interaction (AM-95)

AM-95 is a different, second-order species, not covered by category B
despite the surface resemblance. W-16c and W-16e were each independently
correct, each fully tested in isolation. Composed on an agent with
exactly one parent per channel, they produced silence — a gap neither
rule's own author could see, because neither rule was written knowing
the other existed.

This is NOT feature interaction in category B's sense: no wrong output
was ever produced by either rule, individually or in combination — only
an absence. It is not two norms contradicting (category B's territory
either); it is two *correct detectors* whose union has a coverage gap
neither one's own soundness guarantees against. The precise term is a
detector-coverage/completeness gap, not a behavioral interaction, and
the distinction matters: "feature interaction" carries a strong
connotation of wrong emergent BEHAVIOUR, which is not what happened
here.

The multi-agent-systems "normative conflict" literature
(Vázquez-Salceda et al., normative conflict resolution in multi-agent
systems; the defeasible-deontic-logic line of work, including
Governatori's) is close in spirit but almost entirely addresses the
*direct* case (simultaneously obliged and prohibited) — category B's
territory, not this one. One paper on norm-conflict detection (2018) is
the better match specifically for THIS meta-level case: it explicitly
notes conflicts "that can only be detected when we analyze several norms
together" — a detection-completeness framing, not a behavioral one,
which is exactly AM-95's shape one level removed (here: several
*validator rules*, not several norms in the spec itself).

**No existing work was found connecting RM-ODP / ISO/IEC 15414 / the
enterprise language specifically to feature interaction**, at either
level — object (category B) or meta (category B′). As far as this
search could determine, that connection — particularly the second-order
instance AM-95 surfaced — has not been published elsewhere.

### C. Structural unsatisfiability — a different kind of check, standards-agnostic (W-16h)

W-16h does not belong in category A (the standard never mandates warning
about this) or category B (an ungrantable `requires_permit` is not a
legitimate-but-risky construct — it has zero satisfying execution in ANY
composition, not a composition-dependent risk). It is closer to
dead-code detection in static analysis generally: a requirement that can
never be discharged is exactly analogous to an unreachable branch or an
assignment never read. Nothing in ISO/IEC 15414 needs to be silent,
ambiguous, or even relevant for this category to exist — the same check
would apply to any language with a "this requires a grant" construct,
regardless of domain. Worth keeping distinct from B/B′ precisely because
it needs no standards-silence argument at all to justify itself.

### Practical consequence for future amendments

Recon for a new warning rule should include running its trigger
condition in composition with every *existing* warning rule's trigger on
the same probes, not only checking the new rule in isolation. This is
not a hypothetical recommendation: the check was already performed
informally, twice, before being proposed as a formal step — AM-96's
recon explicitly checked composition against W-16c/e/g before proposing
(confirmed no new W-16f, no change to the others), and AM-97's blast-
radius check did the same across the full rule set before touching the
scenario. AM-95 would have been visible at AM-91's time, in principle,
though this is not a fair complaint against AM-91 in hindsight — it only
becomes visible with a third data point. Formalizing this as an explicit
recon step now, rather than relying on it being remembered informally,
is the point of writing it down.

---

**Status:** REFLECTION. No code change. Informs future recon discipline
(see above) and is a candidate basis for a future paper/post section,
separate from the day-to-day amendment log.
