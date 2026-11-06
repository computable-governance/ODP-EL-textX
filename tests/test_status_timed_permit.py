"""
2.5.0-1 — GET /obligations/{token}/status withholds `compelled` (parity rows R28, R29).

The verifier has no permit time. For a strict burden whose discharge needs a permit
with a time limit, its discharge edge replaces what is a dead end in the engine once
the time is up, so `compelled: true` could be false. The route gives `compelled: null`
and status "permit time limit: not modelled", in both modes. Nothing else in the
response changes, and the verifier does not change.

Rows R28 and R29 are also pinned here at the verifier: the model still offers an
elapsed permit's exercise, and an anchor whose permit is pending or expired has no
edge that uses it.
"""
import contextlib
import io

import pytest

import el_api
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime


NOT_MODELLED = "permit time limit: not modelled"
TRIGGERED = ('burden duty { for_action: "file" state: pending deadline: "1 day" '
             'triggered_by: startEvent discharge_mode: strict }')


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


def _spec(limit='deadline: "5 minutes"', mode="strict", holds="holds duty holds gate",
          other_holds="", file_body="requires_permit gate", extra="", other_fill="",
          other_role="", burden=None):
    burden = burden or ('burden duty { for_action: "file" state: active deadline: "1 day" '
                        f'discharge_mode: {mode} }}')
    return f"""
enterprise specification P
party Holder {{ {holds} }}
party Other {{ {other_holds} }}
policy Notice : duration {{ initial_value: 5 minutes }}
{burden}
commitment C1 {{ by: Holder obligation: "o" creates_burden: duty }}
permit gate {{ for_action: "file" state: active {limit} }}
community K {{
    objective: "o"
    event doneEvent
    event startEvent
    Holder fills r
    {other_fill}
    role r {{
        action file {{ actor: r {file_body} }}
        {extra}
    }}
    {other_role}
}}
"""


_HELD_ELSEWHERE = dict(holds="holds duty", other_holds="holds gate", other_fill="Other fills s",
                       other_role="role s { action look { actor: s } }")

# Two parties, and a permit whose revocation has an embargo, so that it has a reinstate.
_ANCHOR_SPEC = """
enterprise specification P
party Holder {{ holds gate }}
party Boss
permit gate {{ for_action: "use" state: {state} deadline: "5 minutes" }}
{authorization}
community K {{
    objective: "o"
    Holder fills r
    Boss fills b
    role r {{ action use {{ actor: r requires_permit gate }} action rouse {{ actor: r {effect} }} }}
    role b {{ action look {{ actor: b }} }}
}}
"""
_AUTHORIZATION = ('embargo stop { for_action: "use" state: pending }\n'
                  'authorization A1 { authority: Boss to_agent: Holder grants_permit: gate '
                  'revocable: true on_revocation: activate stop }')


@pytest.fixture
def install(monkeypatch, tmp_path):
    """Make `src` the active scenario, with a runtime built from it. Returns the runtime."""
    def _install(src):
        path = tmp_path / "probe.el"
        path.write_text(src)
        result = _quiet(parse_string, src, validate=True)
        assert result.model is not None, result.errors
        monkeypatch.setitem(el_api._SCENARIO_PATHS, "referral", path)
        monkeypatch.setitem(el_api._SCENARIO_DEADLINE_SCALE, "referral", 1)
        monkeypatch.setattr(el_api, "_active_scenario", "referral")
        monkeypatch.setattr(el_api, "_active_community", "K")
        runtime = _quiet(Runtime.build_from_spec, result.model)
        monkeypatch.setattr(el_api, "_runtime", runtime)
        return runtime
    return _install


def _status(mode, name="duty"):
    return _quiet(el_api.get_obligation_status, name, deadline_scale=1, mode=mode)


def _hybrid_model(runtime):
    return _quiet(build_kripke_from_runtime, runtime, horizon=10)


def _static_model(src):
    return _quiet(build_kripke_model, _quiet(parse_string, src, validate=False).model, horizon=10)


def _labels_from_anchor(km):
    return [km.labels.get((km.initial, s)) for s in km.ordered_successors(km.initial)]


@pytest.mark.parametrize("mode", ["hybrid", "spec"])
def test_strict_timed_permit_withholds(install, monkeypatch, mode):
    src = _spec()
    runtime = install(src)
    if mode == "spec":
        monkeypatch.setattr(el_api, "_runtime", None)  # the static model needs no runtime
        verifier_says = _static_model(src).check_obligation("duty")
    else:
        verifier_says = _hybrid_model(runtime).check_obligation("duty")
    assert verifier_says.satisfied is True  # the claim being withheld

    status = _status(mode)
    assert status.compelled is None
    assert status.status == NOT_MODELLED
    assert status.modal_operator == "AF"
    assert status.standing is False

    if mode == "hybrid":
        # No state test. A burden discharged in time is withheld too.
        assert _quiet(runtime.advance, "file", "Holder", {}).outcome == "ok"
        assert _hybrid_model(runtime).check_obligation("duty").satisfied is True
        status = _status(mode)
        assert status.compelled is None
        assert status.status == NOT_MODELLED


def test_eventual_burden_keeps_its_verdict(install):
    install(_spec(mode="eventual"))
    for mode in ("hybrid", "spec"):
        status = _status(mode)
        assert status.compelled is False
        assert status.status == "not resolved within horizon"


def test_no_usable_limit_keeps_the_verdict(install):
    no_permit = _spec(holds="holds duty", file_body="")
    no_deadline = _spec(limit="")
    no_magnitude = _spec(limit='deadline: "thirty days"')
    for src in (no_permit, no_deadline, no_magnitude):
        install(src)
        for mode in ("hybrid", "spec"):
            status = _status(mode)
            assert status.compelled is True
            assert status.status is None
    # The warning still fires for a limit the route does not withhold on.
    warnings = _quiet(parse_string, no_magnitude).warnings
    assert any(w.startswith("[W-strict-timed-permit]") for w in warnings)


def test_detectable_and_paths_stay_as_computed(install):
    install(_spec())
    for mode in ("hybrid", "spec"):
        status = _status(mode)
        assert status.detectable is True
        assert status.witness_path
        assert status.counterexample_path is None

    install(_spec(**_HELD_ELSEWHERE))
    for mode in ("hybrid", "spec"):
        status = _status(mode)
        assert status.compelled is None
        assert status.status == NOT_MODELLED
        assert status.detectable is False
        assert status.witness_path is None
        assert status.counterexample_path


def test_any_discharging_route_withholds(install):
    emitter_needs_it = _spec(
        burden=('burden duty { state: active deadline: "1 day" discharged_by: doneEvent '
                'discharge_mode: strict }'),
        file_body="requires_permit gate emits: doneEvent")
    destroy_needs_it = _spec(
        file_body="",
        extra="action withdraw { actor: r requires_permit gate effect destroy duty }")
    timed_plus_free = _spec(extra="action withdraw { actor: r effect destroy duty }")
    for src in (emitter_needs_it, destroy_needs_it, timed_plus_free):
        install(src)
        for mode in ("hybrid", "spec"):
            status = _status(mode)
            assert status.compelled is None
            assert status.status == NOT_MODELLED


def test_date_and_policy_limits_withhold(install):
    for limit in ('deadline: "by 2026-05-20"', "deadline: Notice"):
        install(_spec(limit=limit))
        for mode in ("hybrid", "spec"):
            status = _status(mode)
            assert status.compelled is None
            assert status.status == NOT_MODELLED


def test_elapsed_unswept_permit_is_still_offered_by_the_model(install):
    runtime = install(_spec(burden=TRIGGERED))
    assert _quiet(runtime.advance_clock, 6).outcome == "ok"
    assert _quiet(runtime.fire_event, "startEvent").outcome == "ok"
    states = {t.token_name: t.state for t in runtime.current_state().tokens}
    assert states == {"duty": "active", "gate": "active"}

    km = _hybrid_model(runtime)
    assert any(label.startswith("exercise:gate") for label in _labels_from_anchor(km))
    assert km.check_obligation("duty").satisfied is True  # the false claim

    refused = _quiet(runtime.advance, "file", "Holder", {})
    assert refused.outcome == "blocked"
    assert "time has elapsed" in refused.reason

    status = _status("hybrid")
    assert status.compelled is None
    assert status.status == NOT_MODELLED
    assert status.detectable is True


def test_pending_anchor_is_unreachable_though_the_engine_restores_it(install):
    runs = (
        (_AUTHORIZATION, "", lambda rt: rt.reinstate_authorization("A1")),
        ("", "effect activate gate", lambda rt: rt.advance("rouse", "Holder", {})),
    )
    for authorization, effect, restore in runs:
        runtime = install(_ANCHOR_SPEC.format(state="pending", authorization=authorization,
                                              effect=effect))
        km = _hybrid_model(runtime)
        assert km.EF(km.initial, "occurred:use") is False

        assert _quiet(restore, runtime).outcome == "ok"
        assert _quiet(runtime.advance, "use", "Holder", {}).outcome == "ok"


def test_expired_anchor_is_unreachable_and_reinstate_refused(install):
    runtime = install(_ANCHOR_SPEC.format(state="active", authorization=_AUTHORIZATION, effect=""))
    _quiet(runtime.advance_clock, 6)
    _quiet(runtime.check_live_violations)
    states = {t.token_name: t.state for t in runtime.current_state().tokens}
    assert states["gate"] == "expired"

    km = _hybrid_model(runtime)
    assert km.EF(km.initial, "occurred:use") is False

    reinstate = _quiet(runtime.reinstate_authorization, "A1")
    assert reinstate.outcome == "blocked"
    assert "only a new grant restores it" in reinstate.reason
    assert _quiet(runtime.advance, "use", "Holder", {}).outcome == "blocked"
