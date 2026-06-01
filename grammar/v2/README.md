# ODP-EL Grammar — Version 2

This directory contains the extended, unified textX-based implementation
of the ODP Enterprise Language (ISO/IEC 15414:2015), developed by
Zoran Milosevic (Deontik) as the basis for the EDOC 2026 paper.

## Files

- `el_grammar.tx` — unified ODP-EL grammar with greatly extended coverage
  of ISO/IEC 15414 concepts (estimated ~95%) in a single file

## Coverage

Version 2 provides greatly extended coverage of ISO/IEC 15414 concepts
(estimated ~95%). Key advances over v1:

- Unified single-file grammar (no partitioning required)
- Top-level speech act declarations (commitment, delegation, authorization,
  declaration) as first-class constructs
- Order-independent body items within enterprise specifications
- Complete deontic token lifecycle (burden, permit, embargo)
- Delegation chains with sub-delegation control and discharge modes
- Federation constructs for multi-community governance
- Policy envelope and policy value integrated into the unified grammar
- Cross-reference resolution across all construct types

## Known Gaps

The remaining gaps are semantic precision items rather than missing
concepts — see `docs/el_grammar_amendments.md` for the full list of
15 pending amendments (AM-01 through AM-15). The most significant
outstanding item is `ViolationResponseDecl` (AM-15), which captures
the declarative response to a deontic constraint violation.

## Reference

This grammar is described in:

> Milosevic, Z. (2026). *Computable Governance for Autonomous Agents.*
> EDOC 2026. *(in preparation)*

## Relationship to v1

Version 2 is not a direct extension of v1 — it is an independent
reimplementation that addresses the open design questions documented
during v1 development, particularly around token lifecycle, delegation
semantics, and the integration of policy constructs. Both versions are
MIT licensed and can be used independently.
