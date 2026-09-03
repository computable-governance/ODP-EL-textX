# Scenario Catalog

Purpose: before building a new scenario to explore a concept, check here
first — a prior attempt may already exist. Maintained alongside
docs/CONCEPTS_INDEX.md (which tracks concepts; this tracks scenario files).

**Maturity tiers:**
- **Probe** — built to validate one specific construct or decision;
  disposable by design. Success means its lesson gets absorbed into the
  grammar/reference scenario, after which the probe is not expected to be
  touched again.
- **Candidate reference scenario** — under active construction, not yet
  verified against its own test suite or the full set of settled
  modelling decisions in docs/CONCEPTS_INDEX.md; intended to become a
  reference scenario once promoted. Promotion criteria: passes its own
  test suite (built following tests/README.md's Layer 4/5/6 pattern) and
  correctly applies every settled decision current in the concept index.
- **Reference scenario** — the settled, maintained embodiment of current
  modelling decisions. Carries tests. Changes go through the AM discipline.
  There should be few of these.
- **Demo** — derived from a reference scenario, packaged for an audience
  (board widget, presentation). May simplify but must never contradict
  the reference scenario it derives from.
- **Historical** — predates the current grammar/design generation; kept
  for record, not actively used.
- **Superseded** — was a reference scenario or probe, replaced by a newer
  one; kept for record/history, not actively extended.

| File | Tier | Grammar | First / last commit | Purpose |
|---|---|---|---|---|
| `consent/consent.odpl` | Historical | v1 | 2024-08-26 | Generic Grantor/Grantee consent pattern. Predates v2 grammar entirely. |
| `consent/consent_scenario.el` | Reference | v2 | 2026-06-01 → AM-21–24 | Clinical AI consent chain (GPPracticeParty → SpecialistAgent → AIDiagnosticAgent), `discharge_mode: strict` AF/EF demonstration. EDOC 2026 primary demonstration (per CLAUDE.md §9). |
| `ecommerce/ecommerce_scenario.el` | Historical | v2 | 2026-06-01 (single commit) | ISO/IEC 15414 Annex B e-commerce validation case, non-clinical. Known pre-existing syntax error at line 57 (unfixed). Never iterated on. |
| `consent/federation_consent_scenario.el` | Probe | v2 | 2026-06-06 (single commit) | Proved AM-25's federation grammar extension. Contained the domain/federation/party pattern (both clinicians as `party`) later forgotten and re-derived 2026-07-05. Patterns absorbed into `referral/referral_scenario.el` (see below); this file itself is not expected to be touched again. |
| `gp_referral/gp_referral_scenario.el` | **Superseded** | v2 | 2026-06-16 → 2026-07-05 (AM-18 through AM-31b/c + drift fixes) | Standing communities + federation, no episodic community, GPClinician modelled as agent not party. Was the board-facing UI's backend until superseded by `referral/referral_scenario.el` (confirmed: `el_api.py`'s `_active_scenario` default is now `"referral"`, not `"gp_referral"`). Kept for record only — not modified further, not a fix target. |
| `ereferral/ereferral_model.el` | Probe | v2 | 2026-06-23 → 2026-06-26 | Explored `CommunityObject` (AM-26) and Creation-style community (`ReferralEpisodeCommunity`, prose-only trigger). Predates AM-31 series — no patient authorization/revocation, no permit split. Patterns fully absorbed into `referral/referral_scenario.el`, now Reference status. |
| `referral/referral_scenario.el` | **Reference (promoted from candidate 2026-07-07)** | v2 | 2026-07-07 | Unified referral model, intended to supersede both `gp_referral_scenario.el` and `ereferral_model.el`. Standing `ReferralNetworkFederation` (GPPracticeCommunity + SpecialistPracticeCommunity via CommunityObject) separate from created `ReferralEpisodeCommunity` (plain community, not federation — individuals cannot be federation members per §7.5.2; established via AM-33's `established_by`). Both clinicians as party (HPI-I); two-hop clinician-to-clinician delegation (GPClinician → SpecialistClinician → SpecialistAIAgent) with layered principal_of/delegated_from accountability; aiExaminationBurden/specialistToAIDelegation; patient authorization/revocation/permit split carried forward from `gp_referral_scenario.el`. Wired into toolchain/el_api.py as a registered scenario (`_build_referral_runtime`), alongside `gp_referral`/`ereferral` — and is now the board UI's backend (`_active_scenario` default is `"referral"`). 17 tests passing: scenario-builder construction, revocation (AM-31b guarantee under the new structure), compelled/detectable AF/EF for all three burdens, PatientDataAuthorshipDomain/PatientDataConsentDomain structure (split 2026-07-22 from the original single PatientDataDomain), two-hop delegation chain. Promotion criteria (this file's own tier definition) satisfied 2026-07-07.|
| `specialist_pool/specialist_pool_scenario.el` | Probe | v2 | 2026-08-22 (single commit, AM-58) | First named `any_discharged`/`SUPERSEDED` collective-obligation demonstration — Zoran Milosevic's own formalization of a challenge the standard's supporting literature (Linington et al.) names as explicitly unsolved. Two equivalent on-call specialists; either discharging satisfies the community, the other supersedes. Proved AM-57's live-engine sibling supersession end-to-end (Kripke layer already had it; engine didn't until AM-57). Deliberately not folded into `referral_scenario.el` — that scenario exercises `all_discharged` only and is kept untouched by design. 3 tests passing (`tests/test_specialist_pool_scenario.py`); independently re-verified 2026-08-23 (`docs/CONCEPTS_INDEX.md`, "TokenGroup/any_discharged coordination semantics" — RESOLVED). |
| `vendor/ai_vendor_probe.el` | Probe | v2 | 2026-08-23 (single commit, AM-59) | Closes the AM-40 loop — first live exercise of role-based `Domain` syntax (`controlling_role`/`controlled_role`, `via=[Federation]` provenance). Models EU AI Act provider/deployer split (mirrored by GDPR controller/processor, HIPAA covered-entity/business-associate) as two constructs: a standing peer contract federation per vendor plus a subordination domain for deployed agents, with N=2 vendors proving the multi-peer case (per Pieter van Schalkwyk's industrial N-peer motivating case). 3 tests passing (`tests/test_ai_vendor_probe_scenario.py`). |
| `erequesting_claiming/erequesting_claiming_scenario.el` | Probe | v2 | 2026-08-24 (AM-60–63; renamed same day from `referral_claiming_scenario.el`) | Accept-side sibling of `specialist_pool_scenario.el`'s discharge-side demonstration — first named demonstration of pool claiming (`claimable`/`lapsed` TokenStates, Kripke C1 transition). Closes two gaps DN_003 exposed empirically before AM-60–62 landed: `Evaluation` had zero runtime handlers, and the live engine had no `pending → active` activation step at all. Grounded directly in AU eRequesting's own out-of-scope item, "claiming of diagnostic requests by fillers." 9 tests passing (`tests/test_erequesting_claiming_scenario.py`). |
| `fhir/generated_governance.el` | Generated (not hand-maintained) | v2 | Regenerated by `toolchain/fhir_mapper.py` | Machine-generated from `ai_diagnostic_bundle.json`. Golden-file tested (tests/test_fhir_mapper_golden.py). Do not edit manually. |

**Reconciliation, resolved:** `gp_referral_scenario.el` and
`ereferral_model.el` independently explored overlapping territory
(referral governance) with divergent structure. `referral/referral_scenario.el`
reached Reference status 2026-07-07 (own test suite complete, wired into
toolchain/el_api.py) and supersedes both — see docs/CONCEPTS_INDEX.md for
the specific concepts each predecessor got right that were carried
forward. The board UI has since switched backends: `el_api.py`'s
`_active_scenario` default is `"referral"`, not `"gp_referral"`.
