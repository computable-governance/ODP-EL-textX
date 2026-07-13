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

from el_api import _SCENARIO_BUILDERS, _build_referral_runtime
from fhir_mapper import EncounterContext


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


def test_referral_runtime_default_matches_hardcoded_gp_actors():
    """
    _build_referral_runtime()'s new encounter_context parameter (R26-R29)
    must be fully optional: called with no argument (module load path,
    `_runtime = _build_referral_runtime()` at the bottom of el_api.py) it
    has to produce byte-for-byte the same WorldState as before the
    parameter existed. Passing encounter_context=None explicitly must be
    indistinguishable from omitting it.
    """
    default_state = _build_referral_runtime().current_state()
    explicit_none_state = _build_referral_runtime(encounter_context=None).current_state()

    assert explicit_none_state.actors == default_state.actors
    assert explicit_none_state.tokens == default_state.tokens

    actor_names = {a.actor_name for a in default_state.actors}
    assert "GPPractice" in actor_names
    assert "GPClinician" in actor_names

    holders = {t.token_name: t.holder for t in default_state.tokens}
    assert holders["referralInitiationBurden"] == "GPClinician"
    assert holders["clinicalHandoverBurden"] == "GPClinician"


def test_referral_runtime_encounter_context_grounds_gp_side_only():
    """
    When an EncounterContext (R26-R29) is supplied, only the GP side
    (GPPractice party enrollment, GPClinician's two role fills, and the
    two GP-held burdens) is substituted. SpecialistClinician,
    SpecialistAIAgent, SpecialistPractice, and Patient — actors and
    tokens alike — must come out byte-for-byte identical to the
    unGrounded default run.
    """
    default_state = _build_referral_runtime().current_state()
    ec = EncounterContext(
        referring_practitioner="DrChen",
        gp_practice="NorthsideGPPractice",
        episode_reference="EpisodeOfCare/ep-001",
    )
    grounded_state = _build_referral_runtime(ec).current_state()

    grounded_actor_names = {a.actor_name for a in grounded_state.actors}
    assert "DrChen" in grounded_actor_names
    assert "NorthsideGPPractice" in grounded_actor_names
    assert "GPClinician" not in grounded_actor_names
    assert "GPPractice" not in grounded_actor_names

    grounded_holders = {t.token_name: t.holder for t in grounded_state.tokens}
    assert grounded_holders["referralInitiationBurden"] == "DrChen"
    assert grounded_holders["clinicalHandoverBurden"] == "DrChen"

    gp_actor_names = {"GPClinician", "GPPractice", "DrChen", "NorthsideGPPractice"}
    non_gp = lambda actors: sorted(
        (a for a in actors if a.actor_name not in gp_actor_names),
        key=lambda a: (a.actor_name, a.role_name or ""),
    )
    assert non_gp(grounded_state.actors) == non_gp(default_state.actors)

    gp_token_names = {"referralInitiationBurden", "clinicalHandoverBurden"}
    non_gp_tokens = lambda tokens: sorted(
        (t for t in tokens if t.token_name not in gp_token_names),
        key=lambda t: t.token_name,
    )
    assert non_gp_tokens(grounded_state.tokens) == non_gp_tokens(default_state.tokens)
