"""
AM-107 — horizon-honest AF, genuine counterexamples, deterministic ties.

AF (check_obligation()) and the AF inside the bounded response property
(check_response()) are three-valued: holds; fails with a counterexample
(the obligation violated, a dead end below the horizon, or a cycle); or
"not resolved within horizon" (status set, satisfied False, no
counterexample) when the answer depends on what happens after the
horizon. Before AM-107 a horizon-step world was expanded like any other,
so an eventual obligation whose deadline lies beyond the horizon could be
reported AF true only because no tick was left (erequesting_claiming's
claim burdens: deadline 20 steps, horizon 10).

Ties among equal-value actions and equal-length paths are broken by edge
label and World.sort_key(), not by hash order, so recommendations and
witnesses replay identically across processes.
"""
import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from el_api import _SCENARIO_BUILDERS
from el_kripke import (
    NOT_RESOLVED_WITHIN_HORIZON,
    RESPONSE_OPERATOR,
    build_kripke_from_runtime,
    build_kripke_model,
)
from el_parser import parse, parse_string
from el_runtime import Runtime

_ROOT = Path(__file__).resolve().parent.parent


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _assert_not_resolved(verdict):
    assert verdict.satisfied is False
    assert verdict.status == NOT_RESOLVED_WITHIN_HORIZON
    assert verdict.counterexample_path is None


# ── erequesting_claiming: the three verdicts AF used to report true ────────

def test_erequesting_claim_burden_static_not_resolved():
    model = _quiet(parse, _ROOT / "scenarios/erequesting_claiming/erequesting_claiming_scenario.el",
                   validate=False).model
    km = _quiet(build_kripke_model, model, horizon=10)
    verdict = km.check_obligation("providerAClaimBurden")
    assert verdict.modal_operator == "AF"
    _assert_not_resolved(verdict)


@pytest.mark.parametrize("oid", ["providerAClaimBurden", "providerBClaimBurden"])
def test_erequesting_claim_burden_hybrid_not_resolved(oid):
    km = _quiet(build_kripke_from_runtime, _quiet(_SCENARIO_BUILDERS["erequesting_claiming"]),
                horizon=10)
    _assert_not_resolved(km.check_obligation(oid))


# ── one probe per outcome ──────────────────────────────────────────────────

_PROBE = """
enterprise specification HorizonProbe

party Holder {{
    holds probeBurden
}}

burden probeBurden {{ for_action: "act" state: active deadline: "{deadline}" discharge_mode: {mode} }}
commitment C {{ by: Holder obligation: "act" creates_burden: probeBurden }}
"""


def _probe_models(deadline, mode):
    model = _quiet(parse_string, _PROBE.format(deadline=deadline, mode=mode), validate=False).model
    return {
        "static": _quiet(build_kripke_model, model, horizon=10),
        "hybrid": _quiet(build_kripke_from_runtime, _quiet(Runtime.build_from_spec, model), horizon=10),
    }


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_holds(builder):
    """Strict: discharged before time can pass — holds, no horizon involved."""
    verdict = _probe_models("1 hour", "strict")[builder].check_obligation("probeBurden")
    assert verdict.satisfied is True
    assert verdict.status is None


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_fails_with_genuine_counterexample(builder):
    """Eventual, 1 hour (5 steps): a path violates it within the horizon."""
    km = _probe_models("1 hour", "eventual")[builder]
    verdict = km.check_obligation("probeBurden")
    assert verdict.satisfied is False
    assert verdict.status is None
    last_world, last_label = verdict.counterexample_path[-1]
    assert last_label.startswith("✗ violated")
    assert km.satisfies(last_world, "violated:probeBurden")


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_not_resolved_when_deadline_beyond_horizon(builder):
    """Eventual, 1 week (12 steps > horizon 10): before AM-107, AF true
    because the horizon world's only move left was the discharge."""
    _assert_not_resolved(_probe_models("1 week", "eventual")[builder].check_obligation("probeBurden"))


_RESPONSE_PROBE = """
enterprise specification ResponseHorizonProbe

party Holder {
    holds laterBurden
}

burden laterBurden {
    for_action: "later"
    state: pending
    deadline: "1 week"
    triggered_by: started
    discharge_mode: eventual
}
commitment C { by: Holder obligation: "later" creates_burden: laterBurden }

community ProbeCommunity {
    objective: "probe bounded response with a deadline beyond the horizon"
    event started
    role r {
        action start { emits: started }
    }
}
"""


def test_bounded_response_not_resolved_when_deadline_beyond_horizon():
    model = _quiet(parse_string, _RESPONSE_PROBE, validate=False).model
    km = _quiet(build_kripke_model, model, horizon=10)
    verdict = km.check_obligation("laterBurden")
    assert verdict.modal_operator == RESPONSE_OPERATOR
    _assert_not_resolved(verdict)


# ── genuine counterexamples for the referral-family cases ──────────────────

# AM-108: the four static cases' genuine counterexample (an unrelated
# no-magnitude burden violated at the parser's default 5 steps, then a dead
# end) is gone — T2 no longer enforces a deadline without a magnitude — so
# they are now "not resolved within horizon" (deadlines 40 and 112 steps,
# horizon 10). The hybrid cycle case is unaffected.
_GENUINE_CASES = [
    ("static", "scenarios/referral/referral_scenario.el", "referralResponseBurden", None),
    ("static", "scenarios/referral/referral_scenario.el", "assessmentSchedulingBurden", None),
    ("static", "scenarios/gp_referral/gp_referral_scenario.el", "referralResponseBurden", None),
    ("static", "scenarios/gp_referral/gp_referral_scenario.el", "assessmentSchedulingBurden", None),
    ("hybrid", "referral", "referralResponseBurden", "↺ cycle"),
]


@pytest.mark.parametrize("builder,source,oid,ending", _GENUINE_CASES)
def test_counterexample_is_genuine(builder, source, oid, ending):
    """Before AM-107 these five showed a path cut off at the horizon.
    ending None: not resolved within horizon (since AM-108)."""
    if builder == "static":
        km = _quiet(build_kripke_model, _quiet(parse, _ROOT / source, validate=False).model, horizon=10)
    else:
        km = _quiet(build_kripke_from_runtime, _quiet(_SCENARIO_BUILDERS[source]), horizon=10)
    verdict = km.check_obligation(oid)
    if ending is None:
        _assert_not_resolved(verdict)
        return
    assert verdict.satisfied is False and verdict.status is None
    last_world, last_label = verdict.counterexample_path[-1]
    assert last_label.startswith(ending)
    if ending == "✗ dead-end":
        assert last_world.step < km.initial.step + km.horizon


# ── API ───────────────────────────────────────────────────────────────────

def test_status_endpoint_reports_not_resolved():
    import el_api
    importlib.reload(el_api)
    el_api._runtime = _quiet(el_api._SCENARIO_BUILDERS["erequesting_claiming"])
    resp = _quiet(el_api.get_obligation_status, "providerAClaimBurden")
    assert resp.modal_operator == "AF"
    assert resp.compelled is False
    assert resp.status == NOT_RESOLVED_WITHIN_HORIZON
    assert resp.counterexample_path is None


# ── determinism across processes ──────────────────────────────────────────

_REPLAY = r"""
import contextlib, io, json
import el_api
from el_kripke import build_kripke_from_runtime
out = {}
with contextlib.redirect_stdout(io.StringIO()):
    for scen in ("ereferral", "erequesting_claiming"):
        km = build_kripke_from_runtime(el_api._SCENARIO_BUILDERS[scen](), horizon=10)
        out[scen + ":recommend"] = km.recommend_action(km.initial)[0].action_label
        out[scen + ":witness"] = [label for _, label in
                                  km.check_permission(next(iter(sorted(km.obligation_descriptors)))).witness_path or []]
        el_api.switch_scenario(scen)
        out[scen + ":api"] = el_api.get_recommended_action(el_api._active_community).recommended_action
print(json.dumps(out, sort_keys=True))
"""


def _replay(seed):
    env = {**os.environ, "PYTHONHASHSEED": str(seed),
           "PYTHONPATH": str(_ROOT / "toolchain")}
    result = subprocess.run([sys.executable, "-c", _REPLAY], cwd=_ROOT, env=env,
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_same_recommendation_across_hash_seeds():
    """Before AM-107 the top action for ereferral and erequesting_claiming
    (ties at equal value) depended on PYTHONHASHSEED; ties now go by edge
    label, then World.sort_key()."""
    first, second = _replay(0), _replay(1)
    assert first == second
    assert first["ereferral:recommend"] == "discharge:acknowledgementBurden by SpecialistClinician"
    assert first["erequesting_claiming:api"] == "discharge:providerAClaimBurden by DiagnosticProviderA"
