# Scenarios

This directory contains example ODP-EL governance specifications
demonstrating the grammar and toolchain across different domains.

## Structure

### `consent/`
Clinical AI consent governance scenario.

- `consent.odpl` — v1 grammar scenario (SoSyM 2025 baseline)
- `consent_scenario.el` — v2 grammar scenario; full consent pathway
  for a GP referral involving an AI diagnostic agent, covering
  obligation creation, delegation, and discharge

### `fhir/`
FHIR R4 integration scenario.

- `generated_governance.el` — governance specification generated
  automatically from a FHIR R4 bundle by `toolchain/fhir_mapper.py`;
  demonstrates the Layer 1 → Layer 2 translation

### `ecommerce/`
E-commerce governance scenario. *(in development)*
