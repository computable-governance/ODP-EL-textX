# ODP-EL Grammar — Version 1

This directory contains the original textX-based implementation of the
ODP Enterprise Language (ISO/IEC 15414:2015), developed collaboratively
by Zoran Milosevic and Igor Dejanović.

## Files

- `odpel.tx` — core ODP-EL grammar covering community, role, behaviour,
  deontic, and accountability concepts
- `odppolicy.tx` — policy language grammar covering policy envelope,
  policy value, and policy constraint constructs (extracted as a separate
  grammar for the SoSyM 2025 paper)
- `odpel.pu` / `odppolicy.pu` — PlantUML meta-model diagrams
- `odpel.png` / `odppolicy.png` — rendered meta-model diagrams

## Coverage

Version 1 covers the core subset of ISO/IEC 15414 concepts, estimated
at 60-70%. The grammar is partitioned into two files: `odpel.tx` handles
the core enterprise language constructs and `odppolicy.tx` handles the
policy perspective. Both files are required together for a complete v1
parse.

## Reference

This grammar is described in:

> Linington, P., Milosevic, Z., Tanaka, A., Dejanović, I. (2025).
> *Using DSLs to manage consistency in long-lived enterprise language
> specifications.* Software and Systems Modeling, 24, 741–754.
> https://doi.org/10.1007/s10270-024-01243-4

> Milosevic, Z., Dejanović, I. (2024). *Accountability using DSL for
> ODP Enterprise Language.* EDOC 2024.

## Stability

This grammar is stable and should not be modified — it is the published
baseline referenced in the above papers. For extensions and improvements
see `grammar/v2/`.
