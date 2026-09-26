"""
AM-111 — each API scenario's configured deadline scale factor k.

el_api._SCENARIO_DEADLINE_SCALE holds one k per _SCENARIO_BUILDERS entry,
stated in code (never derived at runtime). GET /obligations/{token}/status
and GET /kripke/witness use it when no deadline_scale is given and report
it; the query parameter still overrides it. Every other endpoint builds at
k = 1.
"""
import contextlib
import io

import pytest

import el_api
from el_api import _SCENARIO_BUILDERS, _SCENARIO_DEADLINE_SCALE, _SCENARIO_PATHS
from el_kripke import suggest_deadline_scale
from el_parser import parse


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


@pytest.fixture
def pin(monkeypatch):
    """Point the API's shared runtime and active scenario at `name`."""
    def _pin(name):
        monkeypatch.setattr(el_api, "_runtime", _quiet(_SCENARIO_BUILDERS[name]))
        monkeypatch.setattr(el_api, "_active_scenario", name)
    return _pin


def test_every_scenario_has_a_configured_k():
    assert set(_SCENARIO_DEADLINE_SCALE) == set(_SCENARIO_BUILDERS)
    assert _SCENARIO_DEADLINE_SCALE == {
        "gp_referral": 2240, "referral": 2240,
        "erequesting_claiming": 27, "ereferral": 1,
        "public_data_portal": 480, "external_agent_access": 480,
    }


@pytest.mark.parametrize("name", sorted(_SCENARIO_PATHS))
def test_configured_k_is_the_current_suggestion(name):
    """Drift guard: a change to a scenario's deadlines that moves the
    suggested k must update the configured value deliberately."""
    spec = _quiet(parse, _SCENARIO_PATHS[name], validate=False).model
    assert suggest_deadline_scale(spec, el_api._KRIPKE_HORIZON) == _SCENARIO_DEADLINE_SCALE[name]


@pytest.mark.parametrize("name, token", [
    ("referral", "referralResponseBurden"),
    ("gp_referral", "referralResponseBurden"),
    ("erequesting_claiming", "providerAClaimBurden"),
    ("ereferral", "acknowledgementBurden"),
    ("public_data_portal", "incidentNotificationBurden"),
    ("external_agent_access", "incidentNotificationBurden"),
])
def test_status_defaults_to_configured_k(pin, name, token):
    pin(name)
    assert el_api.get_obligation_status(token).deadline_scale == _SCENARIO_DEADLINE_SCALE[name]
    assert el_api.get_obligation_status(token, deadline_scale=1).deadline_scale == 1


def test_referral_default_makes_the_response_deadline_checkable(pin):
    """At k = 1 the 5-working-day response (10080 steps) lies beyond the
    horizon: no violation witness. At the configured k = 2240 it is 5
    steps, and the witness ends at the violation — in both modes."""
    pin("referral")
    assert el_api.get_witness_path("violated:referralResponseBurden",
                                   deadline_scale=1)["witness_path"] == []
    for mode in ("hybrid", "spec"):
        witness = el_api.get_witness_path("violated:referralResponseBurden", mode=mode)
        assert witness["deadline_scale"] == 2240
        assert witness["witness_path"][-1]["edge_from_previous"] == (
            "violate:referralResponseBurden (deadline=5 steps at k=2240; 10080 unscaled)")


def test_override_below_one_rejected(pin):
    from fastapi import HTTPException
    pin("referral")
    with pytest.raises(HTTPException) as exc:
        el_api.get_obligation_status("referralResponseBurden", deadline_scale=0)
    assert exc.value.status_code == 400
