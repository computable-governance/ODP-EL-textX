"""
R35 verification — Encounter → Process/Step mapping.

toolchain/fhir_mapper.py's R35 rule (docs/design_notes/DN_009_consolidated_
mapping_analysis.md §2.3) maps a FHIR Encounter onto the grammar's Process
construct (§7.8.5): Encounter.period.start/.end -> initiates/terminates,
and any bundle resource referencing the Encounter via .encounter.reference
(resourceType-agnostic — ServiceRequest today, Procedure or others for free
later) -> a Step. Static/batch mapping only, run at map_bundle() time — no
grammar or engine change.

Only "finished" and "in-progress" Encounters with a period.start qualify;
an Encounter with neither status, or with no referencing resource in the
bundle, produces no Process at all (the grammar requires steps+=Step+, at
least one — a zero-step Process would fail to parse, not just validate).

tests/fixtures/hospital_episode_bundle.json (already built for R33a) covers
both required cases without needing a new fixture:

  Encounter/556 — status "finished", period.start/period.end both set,
    referenced by ServiceRequest/558 and ServiceRequest/559. Exercises the
    positive case: a Process with two Steps and a real 'terminates' value.

  Encounter/557 — status "in-progress", period.start set, no period.end,
    referenced by ServiceRequest/560. Exercises the no-period.end case: a
    Process still gets emitted (one Step), with 'terminates' set to
    explicit "not yet concluded" phrasing rather than a fabricated or
    empty value.
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


def _community_block(el: str) -> str:
    """Locate the community *block* itself (not just the keyword —
    "community " also occurs inside the generated description text)."""
    community_start = el.index("community HospitalEpisodeBundle001Community")
    community_body_start = el.index("{", community_start)
    community_body_end = el.index("\n    }", community_body_start)
    return el[community_body_start:community_body_end]


def test_r35_finished_encounter_emits_process_with_real_terminates():
    """[R35] Encounter/556 (finished, period.end set) produces a Process
    whose 'terminates' embeds the real period.end timestamp."""
    el = _generate()
    assert "process Id556Process" in el
    block = el.split("process Id556Process")[1].split("step Id558Step")[0]
    assert 'initiates: "Encounter/556 begins (period.start: 2024-06-10T08:00:00+10:00)"' in block
    assert 'terminates: "Encounter/556 concludes (period.end: 2024-06-10T14:00:00+10:00)"' in block


def test_r35_finished_encounter_gets_one_step_per_referencing_service_request():
    """[R35] Both ServiceRequest/558 and ServiceRequest/559 reference
    Encounter/556 — each gets its own Step inside the same Process."""
    el = _generate()
    process_block = el.split("process Id556Process")[1].split("process Id557Process")[0]
    assert "step Id558Step {" in process_block
    assert "actor: id558ParticipantRole" in process_block
    assert "artefact: Id558" in process_block
    assert "step Id559Step {" in process_block
    assert "actor: id559ParticipantRole" in process_block


def test_r35_in_progress_encounter_still_emits_process_with_placeholder_terminates():
    """[R35] Encounter/557 (in-progress, no period.end) still produces a
    Process — 'terminates' uses explicit not-yet-concluded phrasing rather
    than an empty or fabricated value (V-04 requires a non-empty string)."""
    el = _generate()
    assert "process Id557Process" in el
    block = el.split("process Id557Process")[1]
    assert 'initiates: "Encounter/557 begins (period.start: 2024-06-12T08:00:00+10:00)"' in block
    assert 'terminates: "Encounter/557 not yet concluded (status: in-progress)"' in block
    assert "step Id560Step {" in block
    assert "actor: id560ParticipantRole" in block


def test_r35_processes_declared_inside_generated_community():
    """[R35] Process is not a valid top-level SpecElement — grammar/v2/
    el_grammar.tx's Community rule scopes processes+=Process to the
    community body."""
    el = _generate()
    community_block = _community_block(el)
    assert "process Id556Process" in community_block
    assert "process Id557Process" in community_block


def test_r35_bundle_output_parses_and_validates():
    """The generated spec — processes and steps included — must be
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
