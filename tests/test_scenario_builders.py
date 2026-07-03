"""
Layer 5 — drift/consistency tests.

toolchain/el_api.py's scenario builders (_build_gp_referral_runtime,
_build_ereferral_runtime) hardcode Python-side token/actor name literals
that must be kept in sync by hand with the .el scenario files they parse
(el_api.py's own docstring flags this explicitly as the CLAUDE.md §6.1
"two parallel representations" drift risk).

AM-31b (2026-07-02, commit 22b0d86) silently broke this exact way:
gp_referral_scenario.el's patientRecordAccessPermit was renamed/split into
patientRecordAccessPermitByRole / patientRecordAccessPermitByAuthorization,
but _build_gp_referral_runtime's hardcoded grant table still referenced the
old name — causing a fatal KeyError at module-load time (the app couldn't
even start). This went undetected until 2026-07-03, found by accident while
tracing a UI widget, not by any automated check.

This test exists so that specific failure mode can never happen silently
again: every registered scenario builder must construct a Runtime without
raising, on every test run.
"""
import pytest

from el_api import _SCENARIO_BUILDERS


@pytest.mark.parametrize("scenario_name", sorted(_SCENARIO_BUILDERS.keys()))
def test_scenario_builder_constructs_without_error(scenario_name):
    builder = _SCENARIO_BUILDERS[scenario_name]
    runtime = builder()
    assert runtime is not None
