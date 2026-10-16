"""
2.1.0-23 — recommended action when the only discharge edges in the model
are a standing duty's.

The verifier offers "discharge:<duty> by <holder>" for a standing duty
(parity row R13); the engine never takes that step. The recommended-action
route and execute-action's new_recommended_action never offer it
(2.1.0-20), and their Q-values are computed on the model without those
edges, so a Q-value never counts a discharge that cannot happen. The model
itself is unchanged.

Two shapes: the shipped example (both duties pending until contractSigned)
and the same duties active from the start with no other action, where the
standing discharges and the tick are the only edges.

Layer 3 to 4 (API) tests per tests/README.md's strategy.
"""
import contextlib
import io
from pathlib import Path

import pytest

import el_api
from el_kripke import build_kripke_from_runtime
from el_parser import parse, parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_EXAMPLE = (Path(__file__).resolve().parent / "examples" / "standing"
            / "ok_cover_for_the_term.el")

_ACTIVE = """enterprise specification StandingOnly
policy MinimumCover : amount { initial_value: 20000000 AUD }
policy MaximumShare : percentage { initial_value: 10% }
policy ContractEnd : instant { initial_value: 2027-06-30T17:00+10:00 }
party Supplier { holds keepCover holds keepShare }
burden keepCover { standing keeps: "insurance cover" >= MinimumCover ends_at: ContractEnd state: active }
burden keepShare { standing keeps: "subcontract share" <= MaximumShare ends_at: ContractEnd state: active }
community Contract { objective: "o" Supplier fills r role r { action report { actor: r } } }
"""

GAMMA = 0.9


@pytest.fixture
def install(monkeypatch):
    def _install(model):
        monkeypatch.setattr(el_api, "_active_community", "Contract")
        monkeypatch.setattr(el_api, "_runtime", _quiet(Runtime.build_from_spec, model))
        return el_api
    return _install


def _active_model():
    result = _quiet(parse_string, _ACTIVE)
    assert result.ok, result.errors
    return result.model


def _labels(km):
    return sorted(km.labels[(km.initial, s)] for s in km.successors(km.initial))


def _tick_chain_q(km):
    """Q of 'tick' from the initial world when the only real moves are
    ticks: sum of gamma^k * utility along the tick chain, plus the last
    world's utility once more (V of a terminal world is its utility). At
    the horizon the model offers only the standing discharges, so without
    them the last world is terminal."""
    q, w, k = 0.0, km.initial, 0
    while True:
        nxt = [s for s in km.successors(w) if km.labels[(w, s)] == "tick"]
        if not nxt:
            assert all(km.labels[(w, s)].startswith("discharge:keep") for s in km.successors(w))
            return q + GAMMA ** k * km.utility(w)
        w = nxt[0]
        q += GAMMA ** k * km.utility(w)
        k += 1


# ── Only standing discharges and the tick ────────────────────────────────

def test_model_offers_only_standing_discharges_and_tick(install):
    routes = install(_active_model())
    km = _quiet(build_kripke_from_runtime, routes._runtime, horizon=routes._KRIPKE_HORIZON)
    assert _labels(km) == ["discharge:keepCover by Supplier",
                           "discharge:keepShare by Supplier", "tick"]


def test_recommended_action_is_the_tick(install):
    routes = install(_active_model())
    rec = _quiet(routes.get_recommended_action, "Contract")
    assert rec.recommended_action == "tick"
    assert rec.alternatives == []
    assert rec.current_world["obligations"] == {"keepCover": "PENDING", "keepShare": "PENDING"}


def test_q_value_counts_no_standing_discharge(install):
    routes = install(_active_model())
    km = _quiet(build_kripke_from_runtime, routes._runtime, horizon=routes._KRIPKE_HORIZON)
    rec = _quiet(routes.get_recommended_action, "Contract")
    assert rec.q_value == pytest.approx(_tick_chain_q(km))
    # the unfiltered model values the tick higher, by discharges that never happen
    tick = next(s for s in km.successors(km.initial) if km.labels[(km.initial, s)] == "tick")
    phantom = km.utility(tick) + GAMMA * km.bellman_values(gamma=GAMMA)[tick]
    assert rec.q_value < phantom


def test_execute_action_recommends_the_tick(install):
    routes = install(_active_model())
    resp = _quiet(routes.execute_action, "Supplier",
                  routes.ExecuteActionRequest(action_name="report", facts={}))
    assert resp.outcome == "ok"
    assert resp.new_recommended_action == "tick"
    km = _quiet(build_kripke_from_runtime, routes._runtime, horizon=routes._KRIPKE_HORIZON)
    assert resp.new_q_value == round(_tick_chain_q(km), 4)


def test_model_is_not_changed(install):
    routes = install(_active_model())
    km = _quiet(build_kripke_from_runtime, routes._runtime, horizon=routes._KRIPKE_HORIZON)
    before = {w: set(s) for w, s in km.edges.items()}
    view = routes._without_standing_discharges(km, {"keepCover", "keepShare"})
    assert km.edges == before
    assert all(not l.startswith("discharge:")
               for (w, s), l in km.labels.items() if s in view.edges.get(w, set()))


def test_no_standing_duty_returns_the_model_itself(install):
    routes = install(_active_model())
    km = _quiet(build_kripke_from_runtime, routes._runtime, horizon=routes._KRIPKE_HORIZON)
    assert routes._without_standing_discharges(km, set()) is km


# ── The shipped example: pending until the contract is signed ───────────

def test_example_recommends_signing_then_the_tick(install):
    routes = install(_quiet(parse, _EXAMPLE).model)
    rec = _quiet(routes.get_recommended_action, "Contract")
    assert rec.recommended_action == "fire:contractSigned via sign"
    resp = _quiet(routes.execute_action, "Supplier",
                  routes.ExecuteActionRequest(action_name="sign", facts={}))
    assert resp.outcome == "ok"
    assert resp.new_recommended_action == "tick"
    rec = _quiet(routes.get_recommended_action, "Contract")
    assert rec.recommended_action == "tick"
    assert not any(a.action_label.startswith("discharge:") for a in rec.alternatives)
