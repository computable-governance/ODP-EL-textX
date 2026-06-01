# ODP-EL Toolchain

This directory contains the four-layer computable governance toolchain
built on top of the v2 grammar (`grammar/v2/el_grammar.tx`).

## Files

| File | Layer | Description |
|---|---|---|
| `el_parser.py` | Layer 2 | textX-based parser; loads and validates grammar |
| `el_validator.py` | Layer 2 | Semantic validator; checks consistency of governance specifications |
| `el_reasoner.py` | Layer 2 | Accountability reasoner; traces delegation chains to root party |
| `el_kripke.py` | Layer 4 | Kripke verifier; proves modal properties (AF φ, EF φ, AG φ) over all possible futures |
| `fhir_mapper.py` | Layer 1 | 22-rule FHIR R4 to DSL-EL mapping; extracts governance constructs from clinical data |
| `fhir_mapping_table.md` | Layer 1 | Documentation of the 22 FHIR mapping rules |
| `ai_diagnostic_bundle.json` | Layer 1 | Example FHIR R4 bundle for the clinical AI consent scenario |

## The Four-Layer Stack

```
Layer 1 — FHIR R4 (clinical data layer)
          fhir_mapper.py extracts governance semantics from FHIR resources

Layer 2 — DSL-EL (specification layer)
          el_parser.py, el_validator.py, el_reasoner.py
          Q: Is the governance structure consistent? Who is accountable?

Layer 3 — Runtime Enforcement
          WorldState, deontic engine, append-only ledger
          Q: Did each action comply with the governance rules?
          (see Thomas Sepanosian, ODP-EL Toolchain, University of Twente, 2026)

Layer 4 — Kripke Verification
          el_kripke.py
          Q: Across all possible futures, will obligation O
             inevitably be discharged?
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Reference

The toolchain is described in:

> Milosevic, Z. (2026). *Computable Governance for Autonomous Agents.*
> EDOC 2026. *(in preparation)*
