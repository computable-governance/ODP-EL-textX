"""
R37a verification — static Procedure-discharge provenance (the static half
of DN_009 §2.5, mirroring R33a/R33b's established static-vs-live split for
triggered_by).

toolchain/fhir_mapper.py's R37a rule enriches an existing R07 burden's
description with the completed Procedure that fulfils it, when a Procedure
in the same bundle has status "completed" and .basedOn referencing the
ServiceRequest that created the burden. Description enrichment only,
exactly like R33a/R34/R36 — no token.state change.

This is deliberately NOT what DN_009 §2.5's literal wording describes
("a mapper rule connecting Procedure.status: completed to a discharge
call"). Confirmed via grep against grammar/v2/el_grammar.tx: TokenState
only permits 'active' | 'pending' | 'claimable' as an AUTHORED state —
'discharged' is a runtime-only outcome state and cannot be written into
generated .el source at all. There is no static mechanism to pre-discharge
a burden from map_bundle(); the actual state transition is R37b (live,
future work) — a bridge endpoint calling Runtime.discharge_burden()
(AM-68) against a live WorldState, entirely disjoint from this static
code path. This test file's job is partly to pin that boundary down:
every burden here stays 'state: active' regardless of R37a firing.

Only Procedure.status == "completed" qualifies (confirmed against the
real AU Procedure profile's event-status binding, StructureDefinition-
au-procedure.json) — "not-done" is the explicit negative and the rest
(preparation/in-progress/on-hold/stopped/entered-in-error/unknown) are
incomplete or erroneous states.

tests/fixtures/procedure_fulfilment_bundle.json (new fixture — no
existing fixture in the repo carries a Procedure resource) covers three
cases:

  ServiceRequest/401 — Procedure/501 (status "completed") references it
    via basedOn. Positive case: [R37a] tag naming the Procedure, state
    stays 'active'.

  ServiceRequest/402 — no Procedure references it at all. Negative case:
    no [R37a] tag, description unchanged from R07's own text. This is the
    regression check that matters most: current no-Procedure behaviour
    must be untouched.

  ServiceRequest/403 — Procedure/502 (status "stopped") references it via
    basedOn. Negative case: a non-completed Procedure must not trigger
    the tag, even though the basedOn link exists.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "procedure_fulfilment_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def test_r37a_completed_procedure_enriches_burden_description():
    """[R37a] Procedure/501 (completed) basedOn ServiceRequest/401 — the
    resulting burden's description gains an [R37a] tag naming it."""
    el = _generate()
    assert "burden Id401Obligation {" in el
    block = el.split("burden Id401Obligation {")[1].split("}")[0]
    assert "[R37a] Fulfilled by Procedure/501" in block


def test_r37a_never_changes_declared_token_state():
    """[R37a] The burden must stay 'state: active' even though it has been
    fulfilled — 'discharged' is not an authorable TokenState (grammar/v2/
    el_grammar.tx confirms only active|pending|claimable), so R37a can
    only ever be description provenance, never a state change."""
    el = _generate()
    block = el.split("burden Id401Obligation {")[1].split("}")[0]
    assert "state: active" in block
    assert "state: discharged" not in block


def test_r37a_no_procedure_at_all_leaves_burden_untagged():
    """[R37a] ServiceRequest/402 has no referencing Procedure at all — no
    [R37a] tag anywhere in its burden's description. Confirms current
    no-Procedure behaviour is unchanged."""
    el = _generate()
    assert "burden Id402Obligation {" in el
    block = el.split("burden Id402Obligation {")[1].split("}")[0]
    assert "[R37a]" not in block
    assert "state: active" in block


def test_r37a_non_completed_procedure_does_not_enrich():
    """[R37a] Procedure/502 (status 'stopped') basedOn ServiceRequest/403 —
    the basedOn link exists but the status doesn't qualify, so no [R37a]
    tag."""
    el = _generate()
    assert "burden Id403Obligation {" in el
    block = el.split("burden Id403Obligation {")[1].split("}")[0]
    assert "[R37a]" not in block


def test_r37a_bundle_output_parses_and_validates():
    """The generated spec — [R37a]-enriched description included — must be
    structurally valid, not just textually plausible: parses and passes
    all validator rules."""
    from el_parser import parse

    el = _generate()
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".el", mode="w", delete=False) as f:
        f.write(el)
        path = f.name
    try:
        result = parse(path, validate=True)
        assert result.ok, f"Validation errors: {result.errors}"
    finally:
        os.unlink(path)
