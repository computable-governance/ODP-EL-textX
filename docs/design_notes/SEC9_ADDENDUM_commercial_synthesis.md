# Addendum for §9 (Closing — Newsletter and Commercial Framing)

*Drop-in addition to `fhir_governed_autonomy_analysis.md` §9. Synthesises
the Magentus/AU eRequesting commercial read (grounded in public material)
from the session's earlier discussion with a privacy-preserving
accountability pattern surfaced while designing DN_003 (delegation
claiming). The R1/Magentus material below is public; the claim/transfer
mechanism is described generically, at the pattern level, since its
publication status is uncertain — no specific operation names, parameters,
or verbatim text are reproduced, consistent with DN_003's provenance note.
Kept to a pointed observation, not a strategy — deeper commercial
development belongs in the separate Commercial project, per this session's
own scope.*

---

## §9a. A sharper commercial hook than "sits alongside, doesn't compete"

Two findings from this session, taken together, narrow "Governed Autonomy
doesn't compete with FHIR" into something more specific and more durable:

**Magentus is not a generic vendor target — it is the de facto reference
implementation of AU eRequesting itself**, having supplied ~90% of the
published R1 design, and it already runs live cross-provider portability
(the "Digital Patient Choice" work moving pathology requests between
Sonic Healthcare, Australian Clinical Labs, and Healius, with radiology
extension underway). R2 scope is still being defined, with an explicit
upcoming workstream on exactly the group-status/ownership problem
`any_discharged`/SUPERSEDED already solves. This gives a credible,
standards-engagement entry point (a contribution to open R2 scope) that
doesn't require displacing anything Magentus has built.

**Session discussion of the emerging claim/transfer pattern surfaced
something more durable than a scope gap: a deliberate, permanent privacy
boundary between competing fillers.** The pattern discussed is designed so
that neither the original filler nor the claiming filler can identify the
other. This is not an oversight a future release might close later — it is
a competitive/privacy decision, and no future FHIR revision will remove it,
because the barrier is commercial, not technical. Two organisations
racing for the same referral traffic are not going to agree to expose that

relationship to each other, regardless of how the standard evolves.

**This reframes the value proposition from "fills a scope gap" to "holds
something the FHIR layer is structurally forbidden from holding."** A
Governed Autonomy mediator sitting above multiple competing fillers' FHIR
servers can maintain the full accountability chain — which party
originally held a request, when and under what authority it moved, who is
accountable now — without either FHIR-facing party ever seeing the other's
identity. The governance layer's knowledge and the FHIR-level exchange's
deliberate opacity are not in tension; they serve different audiences (a
regulator, an auditor, a neutral cross-vendor layer) than the two
competing operational systems do.

**Why this specifically strengthens the neutral-third-party position
argued earlier in §9's original framing:** a governance layer's value here
depends on it being trusted by *both* competing fillers precisely because
it is neither of them. A layer built or owned by one vendor (including
Magentus, despite its central position) would recreate exactly the
disclosure problem the fillers are avoiding. The credible shape of this
offering is therefore a vendor-neutral accountability layer spanning
multiple providers' FHIR deployments — not a feature embedded in any single
vendor's platform, and not something the standard itself can absorb.

**One line for the newsletter/deck, if useful:** *"Two competing labs can
refuse to tell each other who picked up a referral. They can't refuse to
be accountable for it. Something has to hold that — and it can't be
either of them."*

---

*Further commercial development — go-to-market shape, specific
conversations with Magentus or others, positioning against the AI code of
conduct — belongs in the Commercial project, not this analysis document.*
