# Design Note DN-001: _build_obligation_descriptors() Fix (el_kripke.py)

**Status:** Implemented — commit d7f98b8
**Priority:** Medium
**Date:** 2026-06-24
**Relates to:** el_kripke.py `_build_obligation_descriptors()`, DSL_DESIGN_NOTES.md

## Problem

The Kripke engine had no `for_action` field on `ObligationDescriptor`, and
did not discover burdens introduced exclusively via
`DelegationDecl.transfers_token_group` (only `Commitment`-backed burdens
were registered).

Discovered during eReferral scenario implementation (June 2026).

## Implementation (d7f98b8)

Four changes to `toolchain/el_kripke.py`:

**Change A** — `for_action: Optional[str] = None` added as final field of
`ObligationDescriptor`.

**Change B** — `_find_action_for_burden(model, burden_name)` helper added.
Traverses `Community`/`Domain`/`Federation` → `roles` → `items` (Action) →
`items` (ConditionalAction) → `favoured_by_burden` to discover the Action
name that is favoured by the named burden.

**Change C** — Tier 1/2 resolution in the Commitment loop:
- Tier 1: `DeonticToken.for_action` STRING (if set directly on the token)
- Tier 2: `_find_action_for_burden()` structural scan
- Tier 3: `None` — standing obligation, no named discharging action

**Change D** — Second pass over `Delegation` elements with
`transfers_token_group` set, registering descriptors for group member burdens
not captured via the Commitment path (ISO/IEC 15414 §7.8.7 NOTE).

## Workaround (now superseded)

The workaround `for_action: "scheduleAssessment"` on `examinationBurden` in
`scenarios/ereferral/ereferral_model.el` and `ACTION_LABELS` aliases in the
eReferral widget remain in place. They can be removed once `el_engine.py`
gains the same Tier 2 structural scan for `token_from_spec()` — that is a
separate task.

## Related Gap

`_build_obligation_descriptors()` should also discover burdens via
`DelegationDecl.transfers_token_group` (per ISO/IEC 15414 §7.8.7 NOTE)
in addition to `Commitment.burden`. Both gaps addressed in commit d7f98b8.

## Affected Files

- `toolchain/el_kripke.py` — all four changes (commit d7f98b8)
- `scenarios/ereferral/ereferral_model.el` — workaround `for_action` value
  (still present; remove when `el_engine.py` gains Tier 2 scan)
- `computable-governance-ui/widgets/ereferral/ereferral-simulator.html`
  — workaround `ACTION_LABELS` aliases (still present; remove together with above)
