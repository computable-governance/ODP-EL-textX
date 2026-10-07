# Testing strategy

This directory holds the automated test suite for the ODP-EL toolchain.
The suite is organised around an eight-layer strategy; not all layers are
implemented yet. Each layer targets a distinct class of correctness
question, and several map directly to real bugs found (the hard way)
during development.

## Running the suite

From the repository root, with the dependencies installed
(`pip install -r requirements.txt -r requirements-dev.txt`), bare
`python -m pytest` works; `pytest.ini` is picked up automatically:

    python -m pytest -v

### Slow tests

Tests marked `@pytest.mark.slow` (tens of seconds each) are excluded by
default: `pytest.ini` sets `addopts = -m "not slow"`. Run only them with

    /opt/homebrew/bin/python3.11 -m pytest -c pytest.ini -m slow

or everything, slow tests included, with `-m "slow or not slow"`. A `-m`
on the command line replaces the default. Currently one:
`test_am110_deadline_scale.py::test_cross_check_gp_referral_static_wide`
(a 133,674-world cross-check of the deadline scale factor; its
9,279-world counterpart runs by default). Run the slow tests before
changing `el_kripke.py`'s deadline handling.

## Why a DSL needs layered testing

This is not an ordinary application — it is a small compiler (textX
grammar + parser), a model checker (the Kripke AF/EF machinery in
`el_kripke.py`), a runtime, and a REST API. textX guarantees syntactic
correctness and cross-reference resolution for free, but gives nothing
toward semantic correctness: everything below the parse tree — the modal
operators, discharge modes, TokenGroup satisfaction, the compelled vs.
detectable distinction — is hand-written interpretation of ISO/IEC 15414
Annex C, with no framework verifying it matches the standard. The layers
below exist because that semantic core is entirely unguarded by the
tooling.

## The eight layers

**Layer 1 — Grammar / parse tests.** [DESIGNED, NOT YET BUILT] A corpus of
minimal `.el` snippets that should and should not parse, one assertion
each. Positive/negative pairs, compiler-test-suite style.

**Layer 2 — Validator rule tests.** [DESIGNED, NOT YET BUILT] For each
validator rule (AM-31-V1 through V5, etc.), one minimal spec that triggers
it and one that does not — lint-suite style valid/invalid pairs.

**Layer 3 — Model-checker correctness.** [DESIGNED, NOT YET BUILT] Tiny
synthetic scenarios with hand-computable AF/EF answers, testing
`el_kripke.py` itself against ground truth — as opposed to testing the
checker applied to one business scenario (which `verify_gp_referral.py`
already does). Should include property-based tests (hypothesis) asserting
invariants that hold for any spec, e.g. compelled ⇒ detectable, never the
reverse.

**Layer 4 — Runtime / API integration.** [IMPLEMENTED —
test_revocation_endpoint.py] End-to-end tests driving the API endpoints and
asserting on the resulting state transitions. The revocation test locks in
the AM-31b guarantee: patient consent withdrawal supersedes only the AI
agent's authorization-based permit, leaving the clinician's role-based
permit intact.

**Layer 5 — Drift / consistency.** [IMPLEMENTED —
test_scenario_builders.py] Catches hardcoded Python-side representations of
`.el` scenarios silently going stale. Every scenario builder in
`el_api.py` must construct without raising. This is the test that, had it
existed, would have caught the AM-31b `_build_gp_referral_runtime` KeyError
the day it was introduced rather than a day later (found by accident).

**Layer 6 — Golden-file regeneration.** [IMPLEMENTED —
test_fhir_mapper_golden.py] `fhir_mapper.py`'s generated output must
exactly match the checked-in `generated_governance.el` and must validate.
Automates the manual regeneration check that found the AM-31c bugs (missing
on_revocation link, and a stray `contract{}` wrapper that meant the mapper
could not regenerate any valid file at all).

**Layer 7 — Cross-cutting invariants.** [DESIGNED, NOT YET BUILT] Universal
property tests independent of any scenario — e.g. for every burden in every
scenario, compelled ⇒ detectable. Overlaps with Layer 3's property-based
component; distinguished here as invariants asserted across the real
scenarios rather than synthetic ones.

**Layer 8 — One test per amendment (house rule).**
