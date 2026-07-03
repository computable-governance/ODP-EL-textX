"""
Layer 6 — golden-file regeneration tests.

toolchain/fhir_mapper.py generates scenarios/fhir/generated_governance.el
from toolchain/ai_diagnostic_bundle.json. The generated file's own header
says "machine-generated — do not edit manually," but nothing previously
verified that regenerating it actually reproduces the checked-in file, or
that the output even parses.

AM-31c (2026-07-03, commit d671d7e) found two bugs this way, only by
manually attempting a fresh regeneration: a missing on_revocation link
(AM-31-V2 validation failure) and a stray, invalid "contract {" wrapper in
_render_community with no basis in the grammar, which meant fhir_mapper.py
could not regenerate any valid file from scratch at all, independent of
AM-31-V2. Both tests below automate that manual check.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
GENERATED = REPO_ROOT / "scenarios" / "fhir" / "generated_governance.el"
BUNDLE = TOOLCHAIN / "ai_diagnostic_bundle.json"


def test_fhir_mapper_regenerates_identical_output(tmp_path):
    """Regenerating from the bundle must exactly match the checked-in file."""
    out = tmp_path / "regenerated.el"
    subprocess.run(
        [sys.executable, str(TOOLCHAIN / "fhir_mapper.py"), str(BUNDLE), str(out)],
        check=True,
        cwd=TOOLCHAIN,
    )
    assert out.read_text() == GENERATED.read_text(), (
        "Regenerated output does not match the checked-in file — either "
        "fhir_mapper.py changed without regenerating generated_governance.el, "
        "or generated_governance.el was hand-edited despite its "
        "'do not edit manually' header."
    )


def test_fhir_mapper_output_parses_and_validates():
    """The checked-in generated file must parse and pass all validator rules."""
    from el_parser import parse

    result = parse(str(GENERATED), validate=True)
    assert result.ok, f"Validation errors: {result.errors}"
