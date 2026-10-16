"""
2.1.0-13 — every consumer of a parsed model accepts a comparison
precondition.

A comparison precondition is a Comparison object in action.preconditions,
not a string, and it is unhashable. Only the engine reads preconditions
(Step 4 of advance() and declare_violation()); this test passes a spec
with a comparison through everything else that walks the model, so that
none of them trips on it: the validator, both Kripke builders, the
reasoner's queries, and the API's query routes in hybrid and spec mode.
The FHIR mapper renders its own objects, never a parsed model, so it has
no consumer to test.

Layer 2 to 4 tests per tests/README.md's strategy.
"""
import contextlib
import io

import pytest

import el_api
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse, parse_string
from el_reasoner import (
    can_perform, policy_conflicts, required_permits_by_action, ultimate_accountability,
)
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """
enterprise specification ConsumerProbe

policy MinimumCover : amount { initial_value: 20000000 AUD }

party Assessor { holds assessBurden }

burden assessBurden { for_action: "assess" state: active deadline: "1 day" discharge_mode: eventual }
commitment AssessCommitment { by: Assessor obligation: "assess" creates_burden: assessBurden }

community Engagement {
    objective: "engage only suppliers with enough cover"
    Assessor fills assessorRole
    role assessorRole {
        action assess {
            actor: assessorRole
            precondition: "registered"
            precondition: "insurance cover" >= MinimumCover
        }
    }
}
"""


@pytest.fixture
def model():
    result = _quiet(parse_string, _SPEC)
    assert result.ok, result.errors
    return result.model


def test_validator(model):
    result = _quiet(parse_string, _SPEC, validate=True)
    assert result.errors == []


def test_kripke_builders(model):
    km = _quiet(build_kripke_model, model, horizon=5)
    assert km.check_obligation("assessBurden") is not None
    rt = _quiet(Runtime.build_from_spec, model)
    km = _quiet(build_kripke_from_runtime, rt, horizon=5)
    assert km.check_obligation("assessBurden") is not None


def test_reasoner(model):
    assert can_perform(model, "Assessor", "assess") is not None
    required_permits_by_action(model)
    policy_conflicts(model)
    ultimate_accountability(model, "assess")


@pytest.fixture
def api(monkeypatch, tmp_path, model):
    path = tmp_path / "consumer_probe.el"
    path.write_text(_SPEC)
    monkeypatch.setitem(el_api._SCENARIO_PATHS, "referral", path)
    monkeypatch.setattr(el_api, "_active_scenario", "referral")
    monkeypatch.setattr(el_api, "_active_community", "Engagement")
    monkeypatch.setattr(el_api, "_runtime", _quiet(Runtime.build_from_spec, model))
    return el_api


def test_api_query_routes(api):
    _quiet(api.get_available_actions, "Assessor")
    _quiet(api.get_token_governance, "assessBurden")
    _quiet(api.get_objective_reachable, "Engagement")
    _quiet(api.get_objective_score, "Engagement")
    _quiet(api.get_recommended_action, "Engagement")
    for mode in ("hybrid", "spec"):
        status = _quiet(api.get_obligation_status, "assessBurden", deadline_scale=1, mode=mode)
        assert status.token_name == "assessBurden"
        _quiet(api.get_witness_path, "discharged:assessBurden", mode=mode, deadline_scale=1)


def test_api_execute_action(api):
    resp = _quiet(api.execute_action, "Assessor", api.ExecuteActionRequest(
        action_name="assess",
        facts={"registered": True, "insurance cover": "25000000 AUD"}))
    assert resp.outcome == "ok"
