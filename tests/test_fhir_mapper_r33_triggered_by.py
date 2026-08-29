"""
R33a verification — static triggered_by provenance from discharge-generated
ServiceRequests.

toolchain/fhir_mapper.py's R33a rule (docs/design_notes/R33_triggered_by_rule_spec.md)
records provenance — not masking — on a burden token generated (via the
existing R07 rule) from a ServiceRequest whose referenced Encounter is
already `status: finished` at mapper-run time, and whose `authoredOn` is at
or after that Encounter's `period.end`. This is the static/batch sub-case
(R33a); the live/masking sub-case (R33b, pre-discharge extraction) is
explicitly out of scope — R33a never fires anything at runtime, it only
emits `triggered_by:` on the token plus a top-level `event` block inside the
generated community, in the same .el text produced by map_bundle().

tests/fixtures/hospital_episode_bundle.json carries:

  ServiceRequest/558 and ServiceRequest/559 — both reference the same
    finished Encounter/556 (period.end 2024-06-10T14:00:00+10:00), both
    authoredOn at/after that period.end. Exercises the positive case for
    two different tokens sharing one event, and the event dedup path (only
    one `event Id556Discharge` block, not two).

  ServiceRequest/560 — references Encounter/557, which has status
    "in-progress" (never reaches "finished"). Exercises the negative case:
    no triggered_by line, no event referencing Encounter/557.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "hospital_episode_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _generate() -> str:
    mapper = FHIRConsentMapper()
    bundle = json.loads(FIXTURE.read_text())
    return mapper.map_bundle(bundle)


def test_r33a_triggered_by_emitted_on_discharge_generated_burden():
    """[R33a] A burden whose ServiceRequest was authored at/after its
    referenced Encounter's period.end (Encounter already finished) gets a
    triggered_by line naming the discharge event, plus an [R33] tag in its
    description."""
    el = _generate()
    assert "burden Id558Obligation {" in el
    block = el.split("burden Id558Obligation {")[1].split("}")[0]
    assert "triggered_by: Id556Discharge" in block
    assert "[R33] triggered by discharge of Encounter/556" in block


def test_r33a_event_declared_inside_generated_community():
    """[R33a] The event backing triggered_by is a real EventDecl, declared
    inside the generated community block (EventDecl is not a valid
    top-level SpecElement — grammar/v2/el_grammar.tx's Community rule
    scopes `events+=EventDecl` to the community body)."""
    el = _generate()
    assert "event Id556Discharge" in el
    assert 'description: "Encounter/556 discharged' in el

    # Locate the community *block* itself (`community <Name>\n ... {`), not
    # just the keyword — "community " also occurs inside the generated
    # description text ("Generated governance community for ...").
    community_start = el.index("community HospitalEpisodeBundle001Community")
    community_body_start = el.index("{", community_start)
    community_body_end = el.index("\n    }", community_body_start)
    community_block = el[community_body_start:community_body_end]
    assert "event Id556Discharge" in community_block


def test_r33a_dedups_shared_event_across_multiple_service_requests():
    """[R33a] ServiceRequest/558 and ServiceRequest/559 both reference the
    same finished Encounter/556 — they must share one EventDecl, not each
    generate their own."""
    el = _generate()
    assert el.count("event Id556Discharge") == 1

    assert "burden Id559Obligation {" in el
    block_559 = el.split("burden Id559Obligation {")[1].split("}")[0]
    assert "triggered_by: Id556Discharge" in block_559


def test_r33a_no_triggered_by_when_encounter_not_finished():
    """[R33a] ServiceRequest/560 references Encounter/557, which never
    reaches status: finished — no triggered_by line, no event for it, and
    no [R33] tag in the description."""
    el = _generate()
    assert "burden Id560Obligation {" in el
    block = el.split("burden Id560Obligation {")[1].split("}")[0]
    assert "triggered_by:" not in block
    assert "[R33]" not in block
    assert "event Id557Discharge" not in el


def test_r33a_bundle_output_parses_and_validates():
    """The generated spec — events, triggered_by fields and all — must be
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
