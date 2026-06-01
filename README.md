# ODP-EL-textX

A textX-based implementation of the ODP Enterprise Language (ISO/IEC 15414:2015),
providing a computable governance framework for autonomous AI systems.

Part of the [computable-governance](https://github.com/computable-governance)
initiative.

---

## Overview

The ODP Enterprise Language defines governance constructs for distributed
systems: communities, roles, deontic tokens (obligations, permissions,
prohibitions), speech acts (commitment, delegation, authorization,
declaration), and policies. This repository provides a machine-readable
DSL implementation of these constructs, together with a four-layer
toolchain for governance validation and verification.

## Repository Structure

```
ODP-EL-textX/
│
├── grammar/
│   ├── v1/          Original grammar (SoSyM 2025) — stable, do not modify
│   └── v2/          Extended unified grammar (EDOC 2026) — greatly
│                    extended coverage of ISO/IEC 15414 (estimated ~95%)
│
├── toolchain/       Four-layer Python toolchain (parser, validator,
│                    reasoner, Kripke verifier, FHIR mapper)
│
├── scenarios/       Example governance specifications
│   ├── consent/     Clinical AI consent pathway (v1 and v2)
│   └── fhir/        FHIR R4 generated governance specification
│
└── docs/            Design notes, toolchain reference, grammar amendments
```

## Getting Started

```bash
python -m venv venv
source venv/bin/activate
pip install textx[dev]
pip install -e .
```

To verify the installation:

```bash
textx list-languages
```

## Grammar Versions

**Version 1** (`grammar/v1/`) — the original partitioned grammar developed
collaboratively by Zoran Milosevic and Igor Dejanović. Covers the core
subset of ISO/IEC 15414 concepts, estimated at 60-70%. Described in the
SoSyM 2025 and EDOC 2024 papers.

**Version 2** (`grammar/v2/`) — a unified single-file grammar covering
greatly extended coverage of ISO/IEC 15414 concepts (estimated ~95%), with first-class
speech act declarations, complete deontic token lifecycle, delegation chains,
and federation constructs. Described in the EDOC 2026 paper.

## Licence

MIT — see [LICENSE](LICENSE).

The v2 grammar extends the v1 MIT-licensed work by Igor Dejanović et al.

## References

- Milosevic, Z. (2026). *Computable Governance for Autonomous Agents.*
  EDOC 2026. *(in preparation)*
- Linington, P., Milosevic, Z., Tanaka, A., Dejanović, I. (2025).
  *Using DSLs to manage consistency in long-lived enterprise language
  specifications.* Software and Systems Modeling, 24, 741–754.
  https://doi.org/10.1007/s10270-024-01243-4
- Milosevic, Z., Dejanović, I. (2024). *Accountability using DSL for
  ODP Enterprise Language.* EDOC 2024.

## Contributors

- [Zoran Milosevic](https://github.com/zoranm) (Deontik, Brisbane)
- [Igor Dejanović](https://github.com/igordejanovic) (University of Novi Sad)
