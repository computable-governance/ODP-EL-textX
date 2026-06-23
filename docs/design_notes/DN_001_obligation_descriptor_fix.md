# Design Note DN-001: _build_obligation_descriptors() Fix (el_kripke.py)

**Status:** Deferred — workaround in place  
**Priority:** Medium  
**Date:** 2026-06-24  
**Relates to:** el_kripke.py `_build_obligation_descriptors()`, DSL_DESIGN_NOTES.md

## Problem

The Kripke engine synthesises action labels from burden names by convention
(e.g. `examinationBurden` → `conductExamination`) rather than reading declared
action names from the spec. This causes two symptoms:

1. The wrong action name appears in the widget's available-actions panel
2. The wrong `for_action` value gets stored on the token, so the
   available-actions API endpoint surfaces the wrong action name

Discovered during eReferral scenario implementation (June 2026).

## Current Workaround

Two-part patch applied during eReferral implementation session:
- `examinationBurden.for_action` set to `scheduleAssessment` (the actual
  discharging action) in `scenarios/ereferral/ereferral_model.el`
- `ACTION_LABELS` aliases added to the widget for any remaining synthesised
  labels (`conductExamination`, `discharge:examinationBurden`,
  `discharge:aiExaminationBurden`)

## Proper Fix

In `el_kripke.py`, `_build_obligation_descriptors()` should traverse the
spec's `Action` declarations and look for `Action.favoured_by_burden`
references to discover the correct action name for each burden descriptor,
rather than synthesising it from the burden name.

Pseudocode:

```python
# Current (synthesised from burden name — incorrect):
for_action = "conduct" + burden_name[0].upper() + burden_name[1:]

# Correct (discovered from spec Action declarations):
for burden in spec_burdens:
    for action in spec_actions:
        if burden in action.favoured_by_burden:
            descriptor.for_action = action.name
            break
```

## Related Gap

`_build_obligation_descriptors()` should also discover burdens via
`DelegationDecl.transfers_token_group` (per ISO/IEC 15414 §7.8.7 NOTE)
in addition to `Commitment.burden`. Both gaps can be addressed in the
same pass.

## When to Address

Next implementation session after paper submission. Low risk of breaking
the existing GP-referral scenario since that scenario's burden names and
action names are already aligned by convention.

## Affected Files

- `toolchain/el_kripke.py` — `_build_obligation_descriptors()` function
- `scenarios/ereferral/ereferral_model.el` — workaround `for_action` values
- `computable-governance-ui/widgets/ereferral/ereferral-simulator.html`
  — workaround `ACTION_LABELS` aliases
