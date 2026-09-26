"""
Layer 2/3 — AM-89: `el_parser.py`'s `ParseResult` gains a `warnings` list,
and `parse()` splits `validate_spec()`'s single flat message list into
`.errors`/`.warnings` by the existing "[W-" prefix convention (already used
by V-16b since AM-29, never previously honoured by any caller).

Problem: before this amendment, `ParseResult.ok` was `len(self.errors) == 0`,
and every validator message — errors and warnings alike — landed in
`.errors`. A spec that triggered only an advisory warning (today, only
`[W-16b]`, singleton `SatisfactionCondition`) still made `.ok` `False`,
even though the model parsed and validated fine apart from the advisory
note. Every consumer that gates on `.ok` (134 test-suite call sites of the
`assert result.ok, result.errors` pattern, plus `el_reasoner.py`'s and
`fhir_mapper.py`'s CLIs) would treat that spec as having failed to load.
Confirmed empirically during recon: no tracked scenario triggers this
today, so nothing was actually broken — but a future warning-producing
rule (out of scope here) would immediately hit it.

Fix: `validate_spec()` itself is completely unchanged — same signature,
same flat `List[str]` return, same internal rule functions. `parse()`
partitions that list by prefix immediately after calling it: anything
starting with "[W-" goes to `.warnings`, everything else to `.errors`.
`.ok` needed no code change — it was already `len(self.errors) == 0`, and
warnings are simply never added there.

The two CLI entry points that previously called `parse()` with validation
on (`el_reasoner.py`'s and `fhir_mapper.py`'s `__main__` blocks) now print
`result.warnings` to stderr, unconditionally, before the `.ok` check — so
a warning-only spec is both reported and no longer treated as a failure.
`fhir_mapper.py`'s CLI validate-and-report step was extracted into a
module-level `_print_parse_report()` function purely so it can be
unit-tested directly against a hand-written probe file — its own mapper
output never emits a `satisfaction:` clause, so it can never exercise a
warning through the normal bundle-mapping pipeline.

Out of scope: W-16c, W-16d, V-08, and any strict/warnings-as-errors mode.
"""
import subprocess
import sys
from pathlib import Path

from el_parser import parse, parse_string
from el_runtime import Runtime
from el_validator import validate_spec


_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLCHAIN = _REPO_ROOT / "toolchain"

_WARNING_ONLY_PROBE = """
enterprise specification W16bProbe

burden singleBurden {
    state: active
}

community TestCommunity {
    objective: "Test community for W-16b probe"
    satisfaction: all_discharged(singleBurden)
}
"""

_WARNING_AND_ERROR_PROBE = """
enterprise specification W16bAndErrorProbe

burden singleBurden {
    state: active
}

community TestCommunity {
    objective: "Test community for W-16b + error probe"
    satisfaction: all_discharged(singleBurden)
    sub_objective so1: "needs a role that does not exist" assigned_to role missingRole
}
"""


# ── Test 1: a warning-only spec is ok, model returned, warning isolated ────

def test_warning_only_spec_is_ok_with_warning_isolated():
    result = parse_string(_WARNING_ONLY_PROBE, validate=True)
    assert result.ok is True
    assert result.errors == []
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("[W-16b]")
    assert result.model is not None


# ── Test 2: a genuine error alongside a warning — split correctly ──────────

def test_error_and_warning_together_are_split_correctly():
    result = parse_string(_WARNING_AND_ERROR_PROBE, validate=True)
    assert result.ok is False
    assert len(result.errors) == 1
    assert result.errors[0].startswith("[V-06]")
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("[W-16b]")
    # Neither message may leak into the other's list.
    assert not any(e.startswith("[W-") for e in result.errors)
    assert not any(w.startswith("[V-") for w in result.warnings)


# ── Test 3: validate_spec() itself is untouched — still one flat list ──────

def test_validate_spec_itself_returns_unsplit_flat_list():
    result = parse_string(_WARNING_AND_ERROR_PROBE, validate=False)
    assert result.ok  # no validator ran yet
    messages = validate_spec(result.model)
    assert isinstance(messages, list)
    assert any(m.startswith("[V-06]") for m in messages)
    assert any(m.startswith("[W-16b]") for m in messages)


# ── Test 4: a warning-only spec loads through Runtime.build_from_spec ──────

def test_warning_only_spec_loads_through_runtime_build_from_spec():
    """el_api.py never actually calls validate_spec() (every one of its
    parse() calls uses validate=False), so there is no el_api path to test
    here — see docs/CONCEPTS_INDEX.md's AM-89 recon note. The real,
    validate=True-by-default entry point a spec author's tooling goes
    through is parse()/parse_string() itself, feeding a Runtime."""
    result = parse_string(_WARNING_ONLY_PROBE)  # validate=True is the default
    assert result.ok is True
    rt = Runtime.build_from_spec(result.model)
    assert rt is not None


# ── Test 5: portable clean-spec check — named tracked files only, no glob ──

def test_tracked_reference_scenarios_have_no_warnings():
    """Only scenarios/referral/referral_scenario.el and
    scenarios/consent/consent_scenario.el, named explicitly — no glob over
    scenarios/**, so this never depends on a local-only file (the AM-88
    portability lesson: some local checkouts have additional, untracked
    scenario files a public clone never has).

    AM-95: referral_scenario.el's SpecialistClinician is a genuine,
    tracked-corpus [W-16g] true positive (GPClinician + SpecialistPractice
    — see AM-95's amendment entry) — not modified, expected here.

    AM-96 found two genuine, tracked-corpus [W-16h] true positives here
    (aiAnalysisPermit, required but never granted); AM-97 fixed the
    scenario content (seekConsent now grants aiAnalysisPermit via effect
    create, per its own narrative) — see AM-97's amendment entry.
    consent_scenario.el is warning-free again."""
    # AM-103: [W-19]/[W-20] (strict burdens with no measurable deadline /
    # no ViolationResponse) are known deployment gaps in these scenarios,
    # pending the violation-declaration amendment; excluded here.
    result = parse("scenarios/referral/referral_scenario.el", validate=True)
    assert result.ok, result.errors
    assert _without_strict_gaps(result.warnings) == [
        "[W-16g] Agent 'SpecialistClinician' has 2 declared parents across all "
        "channels: GPClinician (gpToSpecialistDelegation, delegated_from), "
        "SpecialistPractice (standing principal_of). Principals are collectively "
        "responsible (§7.10.1); delegated_from is itself a self-sufficient static "
        "declaration (§6.6.8 NOTE 3) and is counted here even with no backing "
        "Delegation. How these authorities combine is application-defined; the "
        "toolchain does not compose them. See "
        "el_reasoner.all_declared_parents_of(model, 'SpecialistClinician')."
    ]

    result = parse("scenarios/consent/consent_scenario.el", validate=True)
    assert result.ok, result.errors
    assert _without_strict_gaps(result.warnings) == [], \
        f"unexpectedly produced warnings: {result.warnings}"


def _without_strict_gaps(warnings):
    """All warnings except AM-103's [W-19]/[W-20]."""
    return [w for w in warnings if not w.startswith(("[W-19]", "[W-20]"))]


# ── Test 6: el_reasoner.py's CLI prints warnings to stderr, exit status ok ─

def test_el_reasoner_cli_prints_warnings_and_succeeds(tmp_path):
    probe_file = tmp_path / "w16b_probe.el"
    probe_file.write_text(_WARNING_ONLY_PROBE)

    proc = subprocess.run(
        [sys.executable, str(_TOOLCHAIN / "el_reasoner.py"), str(probe_file), "--policy-conflicts"],
        capture_output=True,
        text=True,
        cwd=_TOOLCHAIN,
    )
    assert proc.returncode == 0, proc.stderr
    assert "[W-16b]" in proc.stderr
    assert "[W-16b]" not in proc.stdout
    assert "No policy conflicts detected." in proc.stdout


def test_el_reasoner_cli_still_fails_on_a_genuine_error(tmp_path):
    """Regression guard: a spec with a real error must still exit non-zero
    — the fix must not have accidentally suppressed error handling."""
    probe_file = tmp_path / "error_probe.el"
    probe_file.write_text(_WARNING_AND_ERROR_PROBE)

    proc = subprocess.run(
        [sys.executable, str(_TOOLCHAIN / "el_reasoner.py"), str(probe_file), "--policy-conflicts"],
        capture_output=True,
        text=True,
        cwd=_TOOLCHAIN,
    )
    assert proc.returncode == 1
    assert "[V-06]" in proc.stdout
    assert "[W-16b]" in proc.stderr


# ── Test 7: fhir_mapper.py's extracted report function prints warnings ─────

def test_fhir_mapper_print_parse_report_prints_warnings(tmp_path, capsys):
    from fhir_mapper import _print_parse_report

    probe_file = tmp_path / "w16b_probe.el"
    probe_file.write_text(_WARNING_ONLY_PROBE)

    _print_parse_report(str(probe_file))

    captured = capsys.readouterr()
    assert "[W-16b]" in captured.err
    assert "[W-16b]" not in captured.out
    assert "✓ Parsed successfully" in captured.out


def test_fhir_mapper_print_parse_report_still_reports_a_genuine_error(tmp_path, capsys):
    from fhir_mapper import _print_parse_report

    probe_file = tmp_path / "error_probe.el"
    probe_file.write_text(_WARNING_AND_ERROR_PROBE)

    _print_parse_report(str(probe_file))

    captured = capsys.readouterr()
    assert "✗ Parse errors" in captured.out
    assert "[V-06]" in captured.out
    assert "[W-16b]" in captured.err
