"""
2.1.0-20 — the standing duty guard (claim side; the verifier is unchanged).

The verifier treats a standing duty as an ordinary obligation that its
holder can discharge at any step (parity row R13), and does not model its
term end or breach (R14 to R16). The toolchain therefore withholds its
claims about a standing duty:

- [W-standing-not-modelled], one per standing duty;
- GET /obligations/{token}/status: status "standing duty: not modelled",
  standing true, compelled and detectable null, no path;
- GET /kripke/witness: 422 for discharged:<duty>, violated:<duty>, and
  all_discharged when the model tracks a standing duty;
- recommended action (its route, and execute-action's
  new_recommended_action): no alternative that discharges a standing duty.

A spec with no standing duty gives byte-identical responses on every route
with the guard on or off, and no shipped scenario gains a warning.

Layer 2 to 4 tests per tests/README.md's strategy.
"""
import contextlib
import io
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

import el_api
from el_kripke import build_kripke_from_runtime
from el_parser import parse, parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """enterprise specification GuardProbe
policy MinimumCover : amount {{ initial_value: 20000000 AUD }}
policy ContractEnd : instant {{ initial_value: 2027-06-30T17:00+10:00 }}
party Supplier {{ holds plain {holds} }}
burden plain {{ for_action: "file" state: active deadline: "1 day" }}
commitment PC {{ by: Supplier obligation: "file" creates_burden: plain }}
{duties}
community Contract {{
    objective: "o"
    Supplier fills r
    role r {{ action file {{ actor: r }} }}
}}
"""
_DUTY = ('burden keepCover { standing keeps: "insurance cover" >= MinimumCover '
         'ends_at: ContractEnd state: active }\n'
         'commitment KC { by: Supplier obligation: "keep cover" creates_burden: keepCover }')


def _src(with_duty=True):
    return _SPEC.format(holds="holds keepCover" if with_duty else "",
                        duties=_DUTY if with_duty else "")


@pytest.fixture
def api(monkeypatch, tmp_path):
    def install(with_duty=True):
        src = _src(with_duty)
        path = tmp_path / "guard_probe.el"
        path.write_text(src)
        model = _quiet(parse_string, src, validate=False).model
        monkeypatch.setitem(el_api._SCENARIO_PATHS, "referral", path)
        monkeypatch.setattr(el_api, "_active_scenario", "referral")
        monkeypatch.setattr(el_api, "_active_community", "Contract")
        monkeypatch.setattr(el_api, "_runtime", _quiet(Runtime.build_from_spec, model))
        return el_api
    return install


# ── The warning ──────────────────────────────────────────────────────────

def test_one_warning_per_standing_duty():
    two = _src().replace("holds keepCover", "holds keepCover holds keepCover2") + _DUTY.replace(
        "keepCover", "keepCover2").replace("KC", "KC2")
    result = _quiet(parse_string, two)
    warnings = [w for w in result.warnings if w.startswith("[W-standing-not-modelled]")]
    assert warnings == [
        f"[W-standing-not-modelled] Standing duty '{name}': the verifier does not model its "
        f"term end or breach; the status route gives no verdict for it and the recommended "
        f"action never discharges it. (clause to be confirmed)"
        for name in ("keepCover", "keepCover2")]


def test_no_warning_without_standing_duties():
    result = _quiet(parse_string, _src(with_duty=False))
    assert not any(w.startswith("[W-standing-not-modelled]") for w in result.warnings)


# ── Status ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["hybrid", "spec"])
def test_status_for_a_standing_duty(api, mode):
    routes = api()
    status = _quiet(routes.get_obligation_status, "keepCover", deadline_scale=1, mode=mode)
    assert status.status == "standing duty: not modelled"
    assert status.standing is True
    assert status.compelled is None and status.detectable is None
    assert status.counterexample_path is None and status.witness_path is None


@pytest.mark.parametrize("mode", ["hybrid", "spec"])
def test_status_for_a_plain_burden_beside_it(api, mode):
    routes = api()
    status = _quiet(routes.get_obligation_status, "plain", deadline_scale=1, mode=mode)
    assert status.standing is False
    assert isinstance(status.compelled, bool) and isinstance(status.detectable, bool)


# ── Witness ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("proposition", ["discharged:keepCover", "violated:keepCover",
                                         "all_discharged"])
@pytest.mark.parametrize("mode", ["hybrid", "spec"])
def test_witness_refused(api, proposition, mode):
    routes = api()
    with pytest.raises(HTTPException) as exc:
        _quiet(routes.get_witness_path, proposition, mode=mode, deadline_scale=1)
    assert exc.value.status_code == 422
    assert exc.value.detail.startswith(f"standing duty: not modelled: '{proposition}'")
    assert exc.value.detail.endswith("(clause to be confirmed)")


def test_witness_for_a_plain_burden_still_given(api):
    routes = api()
    result = _quiet(routes.get_witness_path, "discharged:plain", mode="hybrid", deadline_scale=1)
    assert result["witness_path"]


# ── Recommended action ───────────────────────────────────────────────────

def test_recommendation_never_discharges_a_standing_duty(api):
    routes = api()
    km = _quiet(build_kripke_from_runtime, routes._runtime, horizon=routes._KRIPKE_HORIZON)
    labels = {km.labels[(km.initial, s)] for s in km.successors(km.initial)}
    assert "discharge:keepCover by Supplier" in labels            # the model offers it (R13)
    rec = _quiet(routes.get_recommended_action, "Contract")
    shown = [rec.recommended_action] + [a.action_label for a in rec.alternatives]
    assert not any(l.startswith("discharge:keepCover") for l in shown)
    assert any(l.startswith("discharge:plain") for l in shown)


def test_execute_action_recommendation_never_discharges_a_standing_duty(api):
    routes = api()
    resp = _quiet(routes.execute_action, "Supplier",
                  routes.ExecuteActionRequest(action_name="file", facts={}))
    assert not resp.new_recommended_action.startswith("discharge:keepCover")


# ── No standing duty: byte-identical on every route ─────────────────────

def _all_routes(routes):
    out = {
        "available": _quiet(routes.get_available_actions, "Supplier"),
        "governance": _quiet(routes.get_token_governance, "plain"),
        "reachable": _quiet(routes.get_objective_reachable, "Contract"),
        "score": _quiet(routes.get_objective_score, "Contract"),
        "recommended": _quiet(routes.get_recommended_action, "Contract"),
    }
    for mode in ("hybrid", "spec"):
        out[f"status-{mode}"] = _quiet(routes.get_obligation_status, "plain",
                                       deadline_scale=1, mode=mode)
        for prop in ("discharged:plain", "all_discharged"):
            out[f"witness-{mode}-{prop}"] = _quiet(routes.get_witness_path, prop,
                                                   mode=mode, deadline_scale=1)
    return json.dumps({k: (v.model_dump() if hasattr(v, "model_dump") else v)
                       for k, v in out.items()}, sort_keys=True, default=str)


def test_no_standing_duty_byte_identical_with_guard_off(api, monkeypatch):
    routes = api(with_duty=False)
    guarded = _all_routes(routes)
    monkeypatch.setattr(el_api, "_standing_names", lambda spec: set())
    assert _all_routes(routes) == guarded


# ── Shipped scenarios ────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("path", sorted(
    p for p in (_REPO / "scenarios").rglob("*.el") if p.name != "ecommerce_scenario.el"
), ids=lambda p: p.name)
def test_shipped_scenarios_gain_no_warning(path):
    result = _quiet(parse, path)
    assert not any(w.startswith("[W-standing-not-modelled]") for w in result.warnings)
