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

## Project status
ODP-EL-textX 2.0 is a stable reference implementation of the ODP-EL v2 language and toolchain: grammar, validator, runtime engine, verifier and planner, with worked examples including the terms-of-engagement scenario. Release v2.0.0 is tagged so that results in our published work (SoEA4EE 2026, EDOC 2026 Forum, arXiv) remain reproducible.

The repository remains open under the MIT licence and maintained, with a focus on the language, validator and core semantics. Issues, questions and contributions are welcome; please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## Beyond this repository
Applied work building on this foundation, including enforcement integration, deployment tooling, domain packs and specification authoring, is developed by Deontik with partners. If you're interested in applying ODP-EL in your domain, please get in touch: zoran@deontik.com

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
├── scenarios/       11 scenario folders
│                    (see scenarios/README.md)
│
└── docs/            Design notes, toolchain reference, grammar amendments
```

## Getting Started

Tested with Python 3.13. The toolchain is run from source, from the
repository root; there is nothing to install beyond the dependencies.

```bash
git clone https://github.com/computable-governance/ODP-EL-textX.git
cd ODP-EL-textX
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Parse and validate a specification:

```bash
python toolchain/el_parser.py scenarios/consent/consent_scenario.el
```

Run the tests for one scenario (about a second), or the full suite
(about four minutes):

```bash
python -m pytest -q tests/test_erequesting_claiming_scenario.py
python -m pytest -q
```

Run the Kripke verifier demo on the consent scenario:

```bash
python toolchain/el_kripke.py
```

Start the coordination API (interactive docs at
http://127.0.0.1:8765/docs):

```bash
python -m uvicorn toolchain.el_api:app --port 8765
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

- Milosevic, Z. (2026). *Computable Governance for Autonomous Agents:
  Architecture and Implementation.* SoEA4EE 2026.
- Milosevic, Z. (2026). *Compelled versus Merely Detectable Obligations in
  Autonomous AI Governance.* EDOC 2026 Forum.
- Linington, P., Milosevic, Z., Tanaka, A., Dejanović, I. (2025).
  *Using DSLs to manage consistency in long-lived enterprise language
  specifications.* Software and Systems Modeling, 24, 741–754.
  https://doi.org/10.1007/s10270-024-01243-4
- Milosevic, Z., Dejanović, I. (2024). *Accountability using DSL for
  ODP Enterprise Language.* EDOC 2024.

## Contributors

- [Zoran Milosevic](https://github.com/zoranm) (Deontik, Brisbane)
- [Igor Dejanović](https://github.com/igordejanovic) (University of Novi Sad)
