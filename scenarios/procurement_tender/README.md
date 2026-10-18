# Procurement tender scenario

`procurement_tender_scenario.el` models a public-sector tender with two bidders, from close of bids to the first post-award clauses. All parties and values are illustrative.

Contributed by Andy Bond, BIDLOGIQ Pty Ltd.

Tested against `main` at `34fabd5` (2.2.0) on Python 3.14. It parses and validates with no errors. It has two warnings, both expected: `[W-standing-not-modelled]` on each cover duty (see limit 1). `tests/test_procurement_tender_scenario.py` has 18 tests, which check the live engine (Layer 3).

## What it models

| Clause | How it is modelled |
|---|---|
| Each bid is an offer to deliver if awarded | A `claimable` burden per bidder (`supplierAContractBurden`, `supplierBContractBurden`) in the `any_discharged` group `contractGroup`, created by each bidder's commitment. |
| The panel evaluates and signs off once bids close | `panelSignOffBurden`, **strict**: triggered by `tenderClosed`, committed by the buyer agency and delegated to the panel chair. While it is open, the process can't advance the clock or take unrelated actions. |
| An overdue sign-off can be called | The probity officer, the only party filling `probityRole` and holding `signOffDeclarationPermit`, may declare `panelSignOffBurden` violated, but not before its deadline ("10 working days"). The response `overdueSignOff` obliges the buyer to reconvene the panel. |
| No award before sign-off | An **ordering constraint**, not strictness. Both award actions `requires_permit awardPermit`, and only `signOffEvaluation` creates that permit (`effect create awardPermit to buyerRole`). |
| Only one award | The award activates `awardMadeEmbargo`, which inhibits both award actions. |
| The winner accepts; the other bid lapses | The award creates the winner's award notice permit, which its `performContract` action requires. The winner's acceptance is a live accept Evaluation by the holder (`Runtime.claim()`), which claims its burden and lapses the other bid. The other bidder can't accept without an award notice. |
| Notify any WHS incident within 24 hours | Per bidder, an **eventual** burden held from the start as a conditional commitment ("if awarded"), `triggered_by` that bidder's own incident event, deadline `"24 hours"`. Reporting an incident requires the award notice, so only the winner's duty can activate. A late notification is violated and escalated to the principal. |
| No subcontracting without prior written approval | Supplier A's `subcontractCivilWorks` action requires its award notice and `subcontractApproval`. The approval is granted by an authorization from the buyer agency, and revoking it activates `subcontractEmbargo`. |
| Addendum | `tenderAddendum1` is a `prescription`, kept declarative: the engine doesn't change existing tokens or deadlines. |
| Hold public liability cover of at least $20M at submission | `minPublicLiability`, an `amount` policy (`20000000 AUD`) with an envelope, applied to both bidder roles. Each award action has a comparison precondition, `"Supplier A public liability cover at submission" >= minPublicLiability`, so the award is refused unless the cover is reported, as text in the same currency, and meets the minimum. |
| Maintain that cover for the term of the contract | Per bidder, a **standing duty** (`keepPublicLiabilityA`, `keepPublicLiabilityB`): `keeps: "Supplier A public liability cover" >= minPublicLiability`, held from the start, `triggered_by` that bidder's award event and `ended_by` its performance of the contract. It is judged at each `check_live_violations(as_at=..., facts=...)` under a `DeadlineClock`. A reported lapse is a breach, and the response `coverLapseA` obliges the principal to require the cover restored. Each bidder has its own fact key, so one report can't judge both (`[W-standing-shared-fact]`). |

The panel chair, the probity officer and the suppliers are parties filling roles. No delegation of authority to staff is modelled, so none is an agent.

## Constructs used

`party`, `burden` (`claimable`, `pending`, `strict`, `eventual`, `standing` with `keeps`, `ended_by`), `permit`, `embargo`, `token_group`, an `amount` `policy` with `envelope`, `contract community` with `satisfaction: any_discharged(...)`, `event`, `invariant`, `on_join ... transfer`, `fills`, role actions with a comparison `precondition`, `requires_permit`, `inhibited_by_embargo`, `favoured_by_burden`, `emits`, `effect create`, `effect activate` and `declares_violation_of`, `applies ... to role`, `lifecycle`, `commitment`, `delegation`, `authorization` (`to_role`, `to_agent`, `on_revocation`), `prescription` and `violation_response` (`creates_burden_for_role`).

## Limits of the current release

Each limit is stated as what 2.2.0 does. The toolchain lists 3 and 4 under "Found by running contract clauses" in [Known Limitations](../../docs/DSL_TOOLCHAIN_REFERENCE.md#known-limitations-and-open-issues). The scenario file marks the two workarounds with a `WORKAROUND` comment.

1. **The verifier doesn't model standing duties** (`[W-standing-not-modelled]`, `docs/ENGINE_VERIFIER_PARITY.md` R13 to R18). The cover duties are tested on the live engine only. They are kept only at the moments checked: a lapse between two checks isn't seen, and the reported values are trusted as the adapter sends them.
2. **A role can't change hands while a specification runs.** There is no contractor role for the winner to join at award. Each bidder has its own role and holds its post-award duties from the start, as conditional commitments that only the award makes reachable. With N bidders, those duties are written N times.
3. **`effect destroy` discharges burdens only.** Aimed at a permit or an embargo, it does nothing and doesn't report it. A single award is therefore enforced by an embargo the award activates (`awardMadeEmbargo`, marked as a workaround), not by destroying `awardPermit`.
4. **`effect create` grants a token `active` whatever its declared state.** A pending duty created at award with `triggered_by` would start its deadline at the award, not at the trigger. Post-award duties, including the cover duties, are therefore held from the start and triggered by the bidder's award or incident events (marked as a workaround).
5. **The static verifier doesn't reach the award.** Its claim handling is a self-claim: it fires only when an Evaluation's `by:` is the holder of the burden being claimed. Here the winner is decided at runtime, so the specification has no such Evaluation. A buyer-side accept would parse and validate but never be read, and it wouldn't let the verifier check the sign-off ordering either. The award decision stays in the live engine, and the tests check that engine only.
6. **Commitment, delegation and authorization tokens are granted in the test**, not by `Runtime.build_from_spec()` (its documented known gap), as in the other scenario builders.
