# FHIR Toolchain Amendments Log

Companion to `docs/el_grammar_amendments.md`, scoped to changes that touch
only the FHIR-integration toolchain (`toolchain/fhir_mapper.py`,
`toolchain/fhir_event_handler.py`, `toolchain/el_api.py`) and its tests —
no `grammar/v2/el_grammar.tx` or `toolchain/el_domain.py` changes involved.
Entries here share the AM-xx numbering sequence with the grammar log but
use a shorter template (no Grammar/Domain classes/Object processors
sections, since those don't apply to this class of change).

Per CLAUDE.md §7.3/§8: this toolchain is domain-specific (FHIR/clinical);
none of these entries touch Layers 2-4 (`el_validator.py`, `el_reasoner.py`,
`el_kripke.py`).

---

## AM-34 (2026-07-09) — fhir_event_handler.py: R31 Consent revoke + R30 bootstrap note

**Status:** CONFIRMED

**Commit:** `8a200fa`

**Summary:** Added `toolchain/fhir_event_handler.py`, implementing R31
(FHIR `Consent.status` transition to `inactive` → authorization
revocation) and an R30 bootstrap note. Wired into `toolchain/el_api.py`
(`POST /fhir/consent-events`).

**Files changed:** `toolchain/fhir_event_handler.py` (new),
`toolchain/el_api.py`, `tests/test_fhir_event_handler.py` (new, 114 lines).

---

## AM-35 (2026-07-10) — extract_federation_from_contract(): R23+R24 Contract-based federation extraction

**Status:** CONFIRMED

**Commit:** `c2b9852`

**Summary:** Added `extract_federation_from_contract()` to
`toolchain/fhir_mapper.py` — the merged R23+R24 rule (superseding earlier
OrganizationAffiliation-/Consent.policyRule-based proposals). Maps FHIR
`Contract.signer[]`/`.term[]`/`.rule[]` to an ODP-EL `contract federation`
block plus `community_object` declarations and commented
`normative_policy` stubs. Standalone extraction function, not wired into
`el_api.py` (federation membership is standing structure, not a runtime
event).

**Files changed:** `toolchain/fhir_mapper.py`,
`tests/test_fhir_federation_mapper.py` (new, 279 lines).

---

## AM-36 (2026-07-10) — R05-R08 corrections against referral_scenario.el

**Status:** CONFIRMED

**Commit:** `c6aa5db`

**Summary:** Corrected four issues in `_map_service_request()` found while
checking R05-R08 against the reference `referral_scenario.el`:
- **R06:** resolve `Practitioner` requester to organisational
  accountability via `PractitionerRole.organization`, with a flagged
  fallback when unresolved (`_resolve_commitment_accountable_party()`).
- **R07:** split the `discharge_mode` heuristic into independent
  time-criticality (`_is_time_critical()`) and consent-related
  (`_is_consent_related()`) signals — previously consent-keyword-only.
- **R07:** resolve `for_action` via an explicit `SERVICE_REQUEST_ACTION_MAP`
  (FHIR coding → DSL action identifier) instead of sanitized display
  text; unresolved codes are flagged rather than guessed.
- **R08:** dropped the `occurrenceDateTime` → deadline mapping
  (a scheduling field, not an SLA deadline) — left blank pending an
  extension-based approach.

**Files changed:** `toolchain/fhir_mapper.py`,
`tests/test_fhir_mapper_referral.py` (new, 8 tests),
`tests/fixtures/referral_service_request_bundle.json` (new),
`scenarios/fhir/generated_governance.el` (regenerated).

**Verification:** 43/43 tests passing.

---

## AM-37 (2026-07-13) — R26-R29 (partial): Encounter-based episode grounding

**Status:** CONFIRMED

**Commit:** `f8543ab`

**Summary:** Added `EncounterContext` dataclass and
`extract_encounter_context()` to `toolchain/fhir_mapper.py`, mapping FHIR
`Encounter.participant[type=ATND]` → `referring_practitioner`,
`Encounter.serviceProvider` → `gp_practice`, and
`Encounter.episodeOfCare[0]` → `episode_reference` (traceability only).
Reuses `_ref_id()` and the `by_ref` reference-resolution dict pattern
from `_resolve_commitment_accountable_party()` /
`extract_federation_from_contract()` — no new resolution helper
introduced. Errors (missing `Encounter`, no `ATND` participant,
unresolvable `serviceProvider`) raise `ValueError`, matching
`extract_federation_from_contract()`'s philosophy that a mis-grounded
episode is a governance-integrity gap, not a recoverable detail.

`_build_referral_runtime()` in `toolchain/el_api.py` made optionally
parametrizable: `encounter_context: Optional[EncounterContext] = None`.
When supplied, only the GP side is substituted — `GPClinician` and
`GPPractice` (both role enrollments plus the two GP-held burdens,
`referralInitiationBurden`/`clinicalHandoverBurden`) are replaced by
`encounter_context.referring_practitioner`/`.gp_practice`.
`SpecialistClinician`, `SpecialistAIAgent`, `SpecialistPractice`, and
`Patient` are untouched in all cases. Default behavior (`encounter_context`
omitted or `None`) is unchanged — the module-level
`_runtime = _build_referral_runtime()` call at startup is unaffected.

**Not covered by this entry (remains open):** status-driven token-state
initialisation from `Encounter.status` (e.g. using `finished` vs.
`in-progress` to seed initial burden/permit token states) is NOT part of
this amendment. `EncounterContext` currently only grounds actor identity
(who), not token lifecycle state (what state things start in).

**Files changed:** `toolchain/fhir_mapper.py`, `toolchain/el_api.py`,
`tests/test_scenario_builders.py`.

**Verification:** 45/45 tests passing (43 pre-existing + 2 new:
`test_referral_runtime_default_matches_hardcoded_gp_actors`,
`test_referral_runtime_encounter_context_grounds_gp_side_only`).
