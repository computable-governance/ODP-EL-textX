# CC Handover — DN_008 and AU PS Referral Fixture

*Docs-and-fixtures only, no code changes. Same pattern as the earlier
eRequesting-claiming fixture handover.*

## Files to add

1. `docs/design_notes/DN_008_composition_mapping_gap.md` — new design
   note, standard convention, no special handling needed.
2. `tests/fixtures/aups_referral_example/Composition-roberts-fred-summary.json`
3. `tests/fixtures/aups_referral_example/ServiceRequest-referral-endocrinology.json`
4. `tests/fixtures/aups_referral_example/README.md`

(Note the fixture directory name — `aups_referral_example`, sibling to
the existing `erequesting_claim_synthetic` directory under
`tests/fixtures/`, not inside it.)

## Verification before committing

1. Confirm the two JSON fixture files are valid JSON and match what's
   described in their own README (three mandatory AU PS sections with
   `emptyReason`; `ServiceRequest.supportingInfo` referencing the
   `Composition`).
2. Reproduce DN_008's central claim directly, the same way the earlier
   eRequesting fixture's finding was reproduced: run both fixture files
   through the real `fhir_mapper.py` as a bundle, and confirm the output
   shows a mapped `Commitment`/`Burden` from `ServiceRequest` (R05/R07)
   and zero references to `Composition` anywhere in the provenance table.
   A short Python snippet for this (mirroring the pattern used for the
   eRequesting fixture reproduction) is:

   ```python
   import json, sys
   sys.path.insert(0, "toolchain")
   from fhir_mapper import FHIRConsentMapper

   comp = json.load(open("tests/fixtures/aups_referral_example/Composition-roberts-fred-summary.json"))
   sr = json.load(open("tests/fixtures/aups_referral_example/ServiceRequest-referral-endocrinology.json"))
   bundle = {"resourceType": "Bundle", "id": "aups-referral-test", "type": "collection",
             "entry": [{"resource": sr}, {"resource": comp}]}
   print(FHIRConsentMapper().map_bundle(bundle))
   ```

3. Confirm this reproduces cleanly against the real committed repo state,
   not just the sandbox that produced it originally.

## CONCEPTS_INDEX.md entry

Per standing project discipline, add a short entry recording:
- The finding: `Composition`-based document bundles (as used by AU
  Patient Summary) have no mapping rule in `fhir_mapper.py` — confirmed
  empirically, not assumed.
- The DN_004 connection: the `au-ps-composition` profile carries real
  FHIR Obligation extensions (`SHALL:populate`, `SHALL:handle`,
  `SHOULD:display` per actor) that are currently invisible to governance
  — a concrete instance of the "declare vs verify" gap DN_004 already
  argues about in the abstract.
- Cross-reference to DN_008 for the full write-up.

## Commit

Single docs-only commit is fine given the size. Suggested message:
`Docs: DN_008 — Composition mapping gap (AU PS referral fixture,
empirically confirmed)`. Show diff for review before committing; hold
push until confirmed, same as every prior round.

## Explicitly out of scope

- No mapping rule for `Composition` should be implemented from this
  handover — DN_008 §5 sketches two options but commits to neither.
  This is documentation of a finding, not a fix.
- The presentation deck and talking notes from today's session are
  **not** part of this handover and should not go into this repo at
  all — they're Commercial-project material, handled separately.
