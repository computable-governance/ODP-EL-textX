# Deontic Notes — Permission, Prohibition, and Obligation — 2026-07-28

Captured from a design discussion during the permit/embargo governance-resolution work
(see `SESSION_SUMMARY_2026-07-28.md`). Conceptual/theoretical, not an implementation record —
candidate material for the paper's conceptual framing or future-work section.

## The starting claim (Standard Deontic Logic)

The classical von Wright-tradition reduction:

    P(A) ≡ ¬O(¬A)

A permission that A occurs is equivalent to there being no obligation that A *not* occur. This is
usually called **weak permission** — A is permitted by default, purely by the absence of a
countervailing obligation. No positive act is required for weak permission to hold; it's simply
the ambient state where nothing prohibits A.

## The permission/prohibition duality

Confirming the counterpart to the claim above: a prohibition is equivalent to there being an
obligation for the behaviour *not* to occur —

    F(A) ≡ O(¬A)

Prohibition and (weak) permission are exact negations of each other:

    F(A) ≡ ¬P(A)

A is prohibited if and only if A is *not* permitted. This gives a clean, standard deontic
triangle — obligation, permission, and prohibition are all inter-definable via negation, not
three independent primitives.

## The distinction that matters for this toolchain: weak vs. strong permission

ODP-EL's `permit` token does not model weak permission. It models **strong permission**: an
explicit, granted, revocable authorization (`Authorization.grants_permit`) — something an
authority actively confers on an agent, not merely the absence of a prohibition. Weak permission
is a logical default state; a `permit` token is a first-class, grantable, holdable thing.

The two aren't in conflict, though — strong permission's *effect*, once granted, is exactly to
produce the weak-permission state for a specific agent: granting a permit is the act of ensuring
`¬O(¬A)` holds where it otherwise might not, rather than the agent simply relying on the general
ambient default.

## Burden, embargo, and permit as three configurations of obligation

This gives a tight, unifying account of the toolchain's existing three-token vocabulary, all
reducible to obligation on action:

- **Burden** = `O(A)` — an obligation that A occurs.
- **Embargo** = `O(¬A)` — an obligation that A does *not* occur (a prohibition).
- **Permit** = the explicit act of establishing `¬O(¬A)` for a specific agent — i.e., actively
  ensuring no embargo applies, rather than that agent simply falling under the general default.

So permission and prohibition are not a separate, fourth deontic primitive alongside obligation —
they're both expressible *as* obligation (or its explicit negation-of-negation), which is exactly
consistent with the toolchain's own design: `Authorization`, `DeonticToken`, and the
burden/permit/embargo triad all sit within a single unifying obligation-based vocabulary rather
than requiring separate primitive constructs for each deontic modality.

## Consent as a species of authorization

Separately, but related: consent is best understood as authorization reflecting the *grantor's
own preferences* over their own data/interests — not a distinct mechanism from authorization in
general. `Authorization` (authority grants a permit to an agent, revocable) is the general
construct; consent is simply the case where the authority granting it is the data subject
themselves, and the "preference" being enacted is personal rather than organisational or
regulatory. Worth being precise about this distinction if it appears in the paper: consent is a
*use* of authorization, not authorization *defined in terms of* consent.

## Open question, not resolved here

Whether this formal reduction (permit as an explicit act producing a weak-permission state) is
worth stating formally in the paper, or is better left as background motivation for why the
toolchain's three-token vocabulary is complete (covers all the deontic modalities that matter)
without needing a fourth primitive construct.
