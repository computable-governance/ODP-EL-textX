"""
2.1.0-14 — the strict-precondition guard.

The verifier assumes every precondition holds (docs/ENGINE_VERIFIER_PARITY.md,
R11; strict burdens, R8). For a strict burden whose discharging action has a
precondition, plain or a comparison, the status route may report it
compelled while the engine refuses the discharge. 2.1.0-14 does not change
the verifier; it states the assumption:

- [W-strict-precondition]: a warning at specification time;
- assumes_preconditions on GET /obligations/{token}/status: the
  discharging actions' preconditions, as "<action>: <precondition>".

The last test pins the gap itself (engine refuses, model says compelled),
so that a change to it is deliberate and updates the matrix.

Layer 2 to 4 tests per tests/README.md's strategy.
"""
import contextlib
import io

import pytest

import el_api
from el_engine import discharging_actions
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """
enterprise specification GuardProbe

policy MinimumCover : amount {{ initial_value: 20000000 AUD }}

party Holder {{ holds fileBurden }}

burden fileBurden {{ for_action: "file" state: active deadline: "1 hour" discharge_mode: {mode} }}
commitment FileCommitment {{ by: Holder obligation: "file" creates_burden: fileBurden }}

community GuardCommunity {{
    objective: "probe"
    Holder fills r
    role r {{
        action file {{
            actor: r
{preconditions}
        }}
    }}
}}
"""


def _parsed(preconditions=(), mode="strict"):
    pre = "\n".join(f"            precondition: {p}" for p in preconditions)
    result = _quiet(parse_string, _SPEC.format(mode=mode, preconditions=pre))
    assert result.model is not None, result.errors
    return result


def _guard(result):
    return [w for w in result.warnings if w.startswith("[W-strict-precondition]")]


# ── The warning ──────────────────────────────────────────────────────────

def test_warning_for_a_comparison():
    result = _parsed(['"insurance cover" >= MinimumCover'])
    assert _guard(result) == [
        "[W-strict-precondition] Strict burden 'fileBurden' is discharged by action "
        "'file', which has preconditions (\"insurance cover\" >= MinimumCover): the "
        "verifier assumes they hold, so the status route may report it compelled while "
        "the engine refuses the discharge. (clause to be confirmed)"]
    assert result.ok      # a warning, not an error


def test_warning_for_a_plain_precondition():
    assert len(_guard(_parsed(['"registered"', '"x" >= 5']))) == 1
    assert '("registered"; "x" >= 5)' in _guard(_parsed(['"registered"', '"x" >= 5']))[0]


@pytest.mark.parametrize("preconditions, mode", [((), "strict"), (('"registered"',), "eventual")])
def test_no_warning(preconditions, mode):
    assert _guard(_parsed(preconditions, mode)) == []


def test_role_scoped_strict_burden():
    src = """
enterprise specification InlineGuard
party H
community C {
    objective: "o"
    H fills r
    role r {
        burden inlineBurden { for_action: "close" state: active deadline: "1 hour" discharge_mode: strict }
        action close { actor: r precondition: "approved" }
    }
}
"""
    result = _quiet(parse_string, src)
    assert result.model is not None, result.errors
    assert [w[:76] for w in _guard(result)] == [
        "[W-strict-precondition] Strict burden 'inlineBurden' is discharged by action"]


def test_destroy_effect_is_a_discharging_action():
    src = """
enterprise specification DestroyGuard
party H { holds topBurden }
burden topBurden { for_action: "file" state: active deadline: "1 hour" discharge_mode: strict }
commitment TC { by: H obligation: "o" creates_burden: topBurden }
community C {
    objective: "o"
    H fills r
    role r {
        action file { actor: r }
        action withdraw { actor: r precondition: "approved" effect destroy topBurden }
    }
}
"""
    result = _quiet(parse_string, src)
    assert [a.name for a in discharging_actions(result.model, "topBurden")] == ["file", "withdraw"]
    assert len(_guard(result)) == 1 and "action 'withdraw'" in _guard(result)[0]


def test_discharged_by_event_uses_the_emitting_actions():
    src = """
enterprise specification EventGuard
party H { holds eventBurden }
burden eventBurden { for_action: "ignored" state: active deadline: "1 hour" discharged_by: done discharge_mode: strict }
commitment EC { by: H obligation: "o" creates_burden: eventBurden }
community C {
    objective: "o"
    event done
    H fills r
    role r {
        action ignored { actor: r precondition: "never read" }
        action finish { actor: r precondition: "checked" emits: done }
    }
}
"""
    model = _quiet(parse_string, src, validate=False).model
    assert [a.name for a in discharging_actions(model, "eventBurden")] == ["finish"]


# ── assumes_preconditions on the status route ────────────────────────────

@pytest.fixture
def api(monkeypatch, tmp_path):
    def install(preconditions):
        result = _parsed(preconditions)
        path = tmp_path / "guard_probe.el"
        path.write_text(_SPEC.format(mode="strict", preconditions="\n".join(
            f"            precondition: {p}" for p in preconditions)))
        monkeypatch.setitem(el_api._SCENARIO_PATHS, "referral", path)
        monkeypatch.setattr(el_api, "_active_scenario", "referral")
        monkeypatch.setattr(el_api, "_active_community", "GuardCommunity")
        monkeypatch.setattr(el_api, "_runtime", _quiet(Runtime.build_from_spec, result.model))
        return el_api
    return install


@pytest.mark.parametrize("mode", ["hybrid", "spec"])
def test_status_lists_assumed_preconditions(api, mode):
    routes = api(['"registered"', '"insurance cover" >= MinimumCover'])
    status = _quiet(routes.get_obligation_status, "fileBurden", deadline_scale=1, mode=mode)
    assert status.assumes_preconditions == [
        'file: "registered"', 'file: "insurance cover" >= MinimumCover']


def test_status_field_empty_without_preconditions(api):
    routes = api([])
    status = _quiet(routes.get_obligation_status, "fileBurden", deadline_scale=1)
    assert status.assumes_preconditions == []


def test_shipped_scenario_status_has_the_field():
    status = _quiet(el_api.get_obligation_status, "referralResponseBurden", deadline_scale=None)
    assert isinstance(status.assumes_preconditions, list)


# ── The gap itself, pinned ───────────────────────────────────────────────

@pytest.mark.parametrize("precondition, facts", [
    ('"registered"', {}),
    ('"insurance cover" >= MinimumCover', {"insurance cover": "15000000 AUD"}),
])
def test_engine_refuses_while_model_says_compelled(precondition, facts):
    # Parity rows R8 and R11: the verifier assumes preconditions hold. If
    # this test starts failing, the verifier now models preconditions:
    # update docs/ENGINE_VERIFIER_PARITY.md and the warning together.
    model = _parsed([precondition]).model
    rt = _quiet(Runtime.build_from_spec, model)
    record = _quiet(rt.advance, "file", "Holder", facts)
    assert record.outcome == "blocked"
    assert record.reason.startswith("precondition not satisfied")
    static = _quiet(build_kripke_model, model, horizon=10)
    hybrid = _quiet(build_kripke_from_runtime, rt, horizon=10)
    assert static.check_obligation("fileBurden").satisfied is True
    assert hybrid.check_obligation("fileBurden").satisfied is True
