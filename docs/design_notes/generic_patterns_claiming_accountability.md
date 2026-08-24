# Generic Patterns Note — Distributed-Systems Grounding for Claiming and Accountability

*Raw material for the EDOC journal-version future-work section, and/or a
standalone LinkedIn post. Deliberately written in independent
computer-science terms with no reference to any specific FHIR IG, vendor,
or non-public specification — these are established distributed-systems
patterns that Governed Autonomy's claiming/accountability work happens to
instance, not concepts derived from any particular deployment.*

---

## 1. Optimistic concurrency / compare-and-swap claiming

**The generic pattern:** when multiple actors may attempt to acquire the
same resource concurrently, a common and long-established approach is
*optimistic concurrency control* — attempt the state transition directly,
without locking in advance, and let the underlying store report back
whether it succeeded. This is the same principle behind compare-and-swap
(CAS) instructions at the CPU level, optimistic locking in relational
databases (check a version number hasn't changed before committing an
update), and conditional writes in distributed key-value stores.

The defining shape:
- An actor attempts to transition a shared resource to a new state.
- The system either confirms success, or returns a precise structural
  reason it did not (the resource was already claimed, a version conflict
  occurred, a concurrent attempt is in progress).
- Critically, "you already hold this" is treated as a **successful no-op**,
  not an error — the operation is *idempotent* with respect to an actor
  re-attempting a claim they already own.

**Why this matters for Governed Autonomy:** a delegated burden offered to
a pool of eligible holders (the `any_discharged`/collective-obligation
model) is exactly this shape when the acquisition is *declarative* rather
than judged — no actor weighs whether to accept, the claim either succeeds
structurally or it doesn't. This gives the toolchain a genuine, formally
stateable safety property that a verifier could check: **mutual exclusion
over active claims** — no two members of a claiming pool are ever
simultaneously in an active-holder state for the same burden. That's a
concrete, citable target for the Kripke-layer verification story,
independent of any particular domain's claiming mechanism.

## 2. Idempotent acknowledgment and tombstoning

**The generic pattern:** distributed message-passing systems must handle
duplicate delivery — retries after a lost acknowledgment, at-least-once
delivery semantics, network partitions healing and re-syncing stale state.
Two well-established techniques address this:

- **Idempotent acknowledgment (ack/nack):** a consumer processes a message
  once, then separately acknowledges it so the sender or queue knows not
  to redeliver. If the ack itself is lost and the message *is* redelivered,
  a correctly designed consumer recognises the duplicate and treats it as
  a no-op rather than reprocessing.
- **Tombstoning:** rather than simply deleting a record (which a stale
  reader might then interpret as "never existed" and recreate), a
  tombstone marker is left in its place — "this existed, and is now
  deliberately dead" — so that eventual-consistency re-syncs, late-arriving
  writes, or re-scans don't silently resurrect superseded state.

Together, these produce a **two-phase lapse**: mark-as-superseded, then a
separate, later acknowledgment step that prevents the superseded item from
being rediscovered as if it were still live or still pending.

**Why this matters for Governed Autonomy:** the existing `SUPERSEDED`
obligation state (already implemented, verified in the Kripke layer and
partially in the live engine) is a token-level instance of tombstoning —
a peer's obligation is marked dead once collectively fulfilled, precisely
so it isn't mistaken for still-outstanding. Extending this to a genuine
two-phase handshake (mark superseded → later, separately acknowledged)
for pool-claiming's "lost the race" case is a direct, well-precedented
generalisation of a pattern the toolchain already partially implements —
not a new invention.

## 3. The blind/anonymous intermediary pattern

**The generic pattern:** in some markets and protocols, two parties
transact through a trusted third party who can see both sides of the
transaction while the parties themselves cannot see each other. This is a
recognised architectural pattern with independent lineage across several
domains:

- **Dark pools in financial markets** — private trading venues where buy
  and sell orders are matched by an intermediary without revealing either
  party's identity or order details to the other, specifically to prevent
  competitors from inferring trading strategy from counterparty
  information.
- **Blind bidding / sealed-bid brokering** — an auctioneer or broker
  matches bids to offers without disclosing bidder identity to competing
  bidders, common in procurement and some forms of ad-exchange matching.
- **Some ride-hailing and marketplace matching architectures** — a
  platform matches supply and demand and can identify both parties
  internally for accountability/dispute purposes, while deliberately
  withholding certain identifying details from each party about the other
  until (or unless) a match is confirmed.

The structural feature common to all three: **the intermediary's knowledge
is a strict superset of what either party discloses to the other** — and
this is not an oversight or a limitation to be engineered away, it is
often the *entire point* of the architecture, because the parties have
independent (often competitive) reasons for wanting exactly that boundary
to exist.

**Why this matters for Governed Autonomy, and why this is the strongest of
the three for the accountability thesis specifically:** a governance
mediator that sits between two parties who each have legitimate reasons
not to disclose their involvement with each other to one another is not a
compromise on the accountability-chain principle — it is a textbook
instance of a pattern *designed* to combine full intermediary-level
accountability with partial mutual anonymity. This reframes what
Governed Autonomy's ledger is for in exactly these settings: not to
enable the two parties to negotiate more transparently with each other
(they've deliberately chosen not to), but to be the trusted party that
*can* be held accountable — by a regulator, an auditor, or the ultimate
principal — precisely because it holds the full picture that the two
operational parties structurally cannot exchange between themselves.

**Suggested framing line (independent of any source material):**
*"Some systems are built so the two parties on either side of a
transaction can't see each other by design. That doesn't remove
accountability — it just means something else has to hold it. That's
the role a governance layer is built for."*

---

## Where this could go

- **EDOC journal-version future work:** pattern 1 (CAS/optimistic
  concurrency) pairs naturally with the existing "Can AI govern AI?"
  recursive-verification thread — mutual exclusion over claims is a
  concrete, formally verifiable property in the same family as the
  free-rider risk already noted for `any_discharged`.
- **LinkedIn Post 3/4 (AIVendor / "Can AI govern AI?" angle):** pattern 3
  (blind intermediary) is a strong standalone post on its own — it doesn't
  need the AIVendor framing at all, and could run independently as a piece
  on why governance and privacy aren't in tension.
- **Design-note cross-reference:** patterns 1 and 2 could be added as a
  short "prior art" paragraph in DN_003 once it's revisited for
  implementation, giving the pool-claiming/lapse design an independent
  citable grounding beyond the ISO 15414 clauses already used there.
