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


def test_every_scenario_builder_has_a_community_mapping():
    """
    _SCENARIO_BUILDERS and _COMMUNITY_FOR_SCENARIO must be registered
    together — switch_scenario() does _COMMUNITY_FOR_SCENARIO[scenario_name]
    unconditionally, with no guard, so a scenario present in one dict but
    missing from the other raises KeyError at switch time, not at
    collection/import time. Found live 2026-07-07: "referral" was added to
    _SCENARIO_BUILDERS (registering the new referral_scenario.el) without
    the matching _COMMUNITY_FOR_SCENARIO entry, when the runtime builder
    was added but nothing exercised switch_scenario() against it.
    """
    from el_api import _SCENARIO_BUILDERS, _COMMUNITY_FOR_SCENARIO
    assert set(_SCENARIO_BUILDERS.keys()) == set(_COMMUNITY_FOR_SCENARIO.keys())
