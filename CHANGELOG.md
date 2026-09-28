# ODP-EL-textX changelog

All _notable_ changes to this project will be documented in this file.

The format is based on _[Keep a Changelog][keepachangelog]_, and this project
adheres to _[Semantic Versioning][semver]_.

## [Unreleased]

## [2.0.0] - 2026-09-28

First reference release of the ODP Enterprise Language (ISO/IEC 15414:2015,
ITU-T X.911) as a textX DSL for computable governance. The detailed,
per-amendment record (AM-1 to AM-115, with V-NEW validator rules and DOC
notes) is [docs/el_grammar_amendments.md](docs/el_grammar_amendments.md).

### Added

- **Grammar v2** (`grammar/v2/el_grammar.tx`): a single unified grammar
  covering communities, federations and domains, enterprise objects, roles
  and role fulfilment, deontic tokens (burden, permit, embargo) and token
  groups, policies, the accountability concepts (commitment, delegation,
  authorization, prescription, declaration, evaluation), violation responses
  and correspondences. Parsed straight into typed domain classes
  (`toolchain/el_domain.py`, `toolchain/el_parser.py`); the grammar is the
  schema.
- **Validator** (`toolchain/el_validator.py`): semantic checks, each traced
  to an ISO/IEC 15414 clause.
- **Reasoner** (`toolchain/el_reasoner.py`): ultimate accountability,
  can-perform and policy-conflict queries.
- **Runtime engine** (`toolchain/el_engine.py`, `toolchain/el_runtime.py`):
  stateless engine over an immutable WorldState with an append-only ledger;
  role-restricted actions (AM-114) and authorised violation declaration
  (AM-115).
- **Verifiers** (`toolchain/el_kripke.py`): Kripke verification after
  Annex C, in static (pre-execution) and hybrid (anchored to the current
  WorldState) modes; AF/EF/AG checks, `discharge_mode: strict`, and a Bellman
  planner.
- **Agent-facing API** (`toolchain/el_api.py`): REST endpoints for available
  actions, objective reachability and score, recommended action, action
  execution and reset.
- **FHIR R4 mapper** (`toolchain/fhir_mapper.py`): Layer 1 adapter from FHIR
  bundles to DSL-EL specifications.
- **Scenarios** (`scenarios/`, status per `scenarios/README.md`):
  - Reference: `consent/consent_scenario.el`, `referral/referral_scenario.el`.
  - Demo: `terms_of_engagement/external_agent_access_scenario.el`,
    `terms_of_engagement/public_data_portal_scenario.el`.
  - Probe: `consent/federation_consent_scenario.el`,
    `ereferral/ereferral_model.el`, `specialist_pool/specialist_pool_scenario.el`,
    `vendor/ai_vendor_probe.el`,
    `erequesting_claiming/erequesting_claiming_scenario.el`,
    `probes/transfer_probe.el`.
  - Generated: `fhir/generated_governance.el`.
  - Superseded: `gp_referral/gp_referral_scenario.el`.
  - Historical: `consent/consent.odpl` (v1 grammar),
    `ecommerce/ecommerce_scenario.el` (does not parse).
- Grammar v1 (`grammar/v1/`) is kept unchanged as published.

### Known limitations

- Install from source; packaging to follow.


[Unreleased]: https://github.com/computable-governance/ODP-EL-textX/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/computable-governance/ODP-EL-textX/releases/tag/v2.0.0


[keepachangelog]: https://keepachangelog.com/
[semver]: https://semver.org/spec/v2.0.0.html
