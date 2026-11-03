# Procurement tender scenario

`procurement_tender_scenario.el` models a public-sector tender with two bidders, from close of bids to the first post-award clauses. All parties and values are illustrative.

Contributed by Andy Bond, BIDLOGIQ Pty Ltd.

Tested against `0e01411` (2.4.0) on Python 3.13. It parses and validates with no errors. It has three warnings, all expected, in this order: `[W-standing-not-modelled]` on the cover duty `keepPublicLiability` (see limit 1), `[W-burden-not-modelled]` on `incidentNotificationBurden` and `[W-fill-not-modelled]` on `contractorRole` (both limit 2). `tests/test_procurement_tender_scenario.py` has 22 tests, which check the live engine (Layer 3).

## What it models

| Clause | How it is modelled |
|---|---|
| Each bid is an offer to deliver if awarded | A `claimable` burden per bidder (`supplierAContractBurden`, `supplierBContractBurden`) in the `any_discharged` group `contractGroup`, created by each bidder's commitment. |
| The panel evaluates and signs off once bids close | `panelSignOffBurden`, **strict**: triggered by `tenderClosed`, committed by the buyer agency and delegated to the panel chair. While it is open, the process can't advance the clock or take unrelated actions. |
| An overdue sign-off can be called | The probity officer, the only party filling `probityRole` and holding `signOffDeclarationPermit`, may declare `panelSignOffBurden` violated, but not before its deadline ("10 working days"). The response `overdueSignOff` obliges the buyer to reconvene the panel. |
| No award before sign-off | An **ordering constraint**, not strictness. Both award actions `requires_permit awardPermit`, and only `signOffEvaluation` creates that permit (`effect create awardPermit to buyerRole`). |
| Only one award | The award activates `awardMadeEmbargo`, which inhibits both award actions. |
| The winner accepts; the other bid lapses | Both bids' `performContract` action belongs to `contractorRole`, which only the winner fills. The winner's acceptance is a live accept Evaluation by the holder (`Runtime.claim()`), which claims its burden and lapses the other bid. The other bidder doesn't fill the contractor role, so it can't accept. |
| The award makes the winner the contractor | Each award action has `effect fill contractorRole with SupplierA` (or `SupplierB`): the award makes that bidder the only filler of `contractorRole`, and the role's `on_join` tokens are granted to it, in their declared state, at the award. The contractor's duties are therefore written once, whoever wins. The role's `assignment_policy` has `excludes_role evaluationPanelRole` and `excludes_role probityRole`, so neither the panel chair nor the probity officer can be made the contractor. |
| Notify any WHS incident within 24 hours | One **eventual** burden, `incidentNotificationBurden`, granted to the contractor by `on_join contractorRole` and pending until its `triggered_by` event, `incidentOccurs`, which the contractor's `reportIncident` emits: the `"24 hours"` deadline runs from the incident, not from the award. Only the contractor can report an incident. A late notification is violated and escalated to the principal. |
| No subcontracting without prior written approval | The contractor's `subcontractCivilWorks` action requires `subcontractApproval`, whoever wins. The approval is granted to the contractor role by an authorization from the buyer agency, and revoking it activates `subcontractEmbargo`. |
| Addendum | `tenderAddendum1` is a `prescription`, kept declarative: the engine doesn't change existing tokens or deadlines. |
| Hold public liability cover of at least $20M at submission | `minPublicLiability`, an `amount` policy (`20000000 AUD`) with an envelope, applied to the contractor role. Each award action has a comparison precondition, `"Supplier A public liability cover at submission" >= minPublicLiability`, so the award is refused unless the cover is reported, as text in the same currency, and meets the minimum. |
| Maintain that cover for the term of the contract | One **standing duty**, `keepPublicLiability`, with one fact key: `keeps: "Contractor public liability cover" >= minPublicLiability`, granted active to the contractor by `on_join contractorRole` at the award and `ended_by: contractCompleted`, which the buyer's `certifyCompletion` emits. Accepting the award doesn't end it. It is judged at each `check_live_violations(as_at=..., facts=...)` under a `DeadlineClock`. A reported lapse is a breach, and the response `coverLapse` obliges the principal to require the cover restored. |

The panel chair, the probity officer and the suppliers are parties filling roles; the winning supplier fills the contractor role from the award. No delegation of authority to staff is modelled, so none is an agent.

## Constructs used

`party`, `burden` (`claimable`, `pending`, `strict`, `eventual`, `standing` with `keeps`, `ended_by`), `permit`, `embargo`, `token_group`, an `amount` `policy` with `envelope`, `contract community` with `satisfaction: any_discharged(...)`, `event`, `invariant`, `on_join ... transfer` (including on_join of a role filled by an action), `fills`, `assignment_policy` with `excludes_role`, role actions with a comparison `precondition`, `requires_permit`, `inhibited_by_embargo`, `favoured_by_burden`, `emits`, `effect fill`, `effect create`, `effect activate` and `declares_violation_of`, `applies ... to role`, `lifecycle`, `commitment`, `delegation`, `authorization` (`to_role`, `to_agent`, `on_revocation`), `prescription` and `violation_response` (`creates_burden_for_role`).

## Limits of the current release

Each limit is stated as what the current release (2.4.0) does. The toolchain lists 3 and 4 under "Found by running contract clauses" in [Known Limitations](../../docs/DSL_TOOLCHAIN_REFERENCE.md#known-limitations-and-open-issues). The scenario file marks the workaround for 3 with a `WORKAROUND` comment.

1. **The verifier doesn't model standing duties** (`[W-standing-not-modelled]`, `docs/ENGINE_VERIFIER_PARITY.md` R13 to R18). The cover duty is tested on the live engine only. It is kept only at the moments checked: a lapse between two checks isn't seen, and the reported values are trusted as the adapter sends them.
2. **A role is filled once and not left.** The award fills the contractor role (`effect fill`), and there is no leave or replacement act, so a contractor can't be terminated and replaced within one run. The verifier doesn't model the fill (`[W-fill-not-modelled]`, `docs/ENGINE_VERIFIER_PARITY.md` R27): a static model has no contractor, so the contractor's actions and its incident duty are not in it (`[W-burden-not-modelled]`). The tests check the live engine.
3. **`effect destroy` discharges burdens only.** Aimed at a permit or an embargo, it does nothing and doesn't report it. A single award is therefore enforced by an embargo the award activates (`awardMadeEmbargo`, marked as a workaround), not by destroying `awardPermit`.
4. **`effect create` grants a token `active` whatever its declared state.** A pending duty created at award with `triggered_by` would start its deadline at the award, not at the trigger. The scenario no longer needs a workaround for this: `on_join` grants the contractor's duties in their declared state, so the incident duty waits for the incident.
5. **The static verifier doesn't reach the award.** Its claim handling is a self-claim: it fires only when an Evaluation's `by:` is the holder of the burden being claimed. Here the winner is decided at runtime, so the specification has no such Evaluation. A buyer-side accept would parse and validate but never be read, and it wouldn't let the verifier check the sign-off ordering either. The award decision stays in the live engine, and the tests check that engine only.
6. **Commitment, delegation and authorization tokens are granted in the test**, not by `Runtime.build_from_spec()` (its documented known gap), as in the other scenario builders: the bids, the panel's sign-off, the declaration permit and, after the award, the winner's subcontract approval. The contractor's duties need no grant: the award grants them through `on_join`.
