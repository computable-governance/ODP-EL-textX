"""
2.5.0-2 — GET /obligations/{token}/status withholds `compelled` for a permit that a
violation response suspends or expires (parity row R31).

The verifier reads neither `suspends:` nor `expires:`. For a strict burden whose
discharge needs a permit granted by an Authorization that any ViolationResponse names
in either clause, the route gives `compelled: null` and status "permit suspension or
expiry by a response: not modelled", in both modes and whether or not the response
has fired. The test reads only the specification. A time limit (2.5.0-1, R28) takes
precedence. `detectable`, the witness and the counterexample stay as computed. A
permit named only by `revokes:` is not covered: that gap is an open finding in
docs/CONCEPTS_INDEX.md, and test_revokes_only_keeps_the_verdict pins it.

The probe: Holder holds the strict burden `duty`, triggered by an event that Holder's
`begin` emits, and the permit `gate`, granted by A1 (authority Boss). `file`
discharges `duty` and requires `gate`. The response VR answers a violation of
another burden, `other`, which times out after one minute.
"""
import contextlib
import io

import pytest

import el_api
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime


RESPONSE_NOT_MODELLED = "permit suspension or expiry by a response: not modelled"
TIME_NOT_MODELLED = "permit time limit: not modelled"


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


def _spec(clause, mode="strict", limit="", extra="", grantee="to_agent: Holder",
          burden=None, file_body="requires_permit gate", events=""):
    burden = burden or (f'burden duty {{ for_action: "file" state: pending deadline: "1 day"\n'
                        f'    triggered_by: startEvent discharge_mode: {mode} }}')
    return f"""
enterprise specification P
party Holder {{ holds duty holds gate holds other holds spare }}
party Boss
{burden}
burden other {{ for_action: "look" state: active deadline: "1 minute" }}
commitment C1 {{ by: Holder obligation: "o" creates_burden: duty }}
commitment C2 {{ by: Holder obligation: "o" creates_burden: other }}
permit gate {{ for_action: "file" state: active {limit} }}
permit spare {{ for_action: "look" state: active }}
embargo stop {{ for_action: "look" state: pending }}
authorization A1 {{ authority: Boss {grantee} grants_permit: gate
    revocable: true on_revocation: activate stop }}
authorization A2 {{ authority: Boss to_agent: Holder grants_permit: spare }}
violation_response VR {{ on_violation_of: other obligates: Boss response_kind: remediate
    {clause} }}
{extra}
community K {{
    objective: "o"
    event startEvent
    {events}
    Holder fills r
    Boss fills b
    role r {{
        action file {{ actor: r {file_body} }}
        action look {{ actor: r }}
        action begin {{ actor: r emits: startEvent }}
    }}
    role b {{ action peek {{ actor: b }} }}
}}
"""


@pytest.fixture
def install(monkeypatch, tmp_path):
    """Make `src` the active scenario, with a runtime built from it. Returns the runtime."""
    def _install(src):
        path = tmp_path / "probe.el"
        path.write_text(src)
        result = _quiet(parse_string, src, validate=True)
        assert result.ok, result.errors
        monkeypatch.setitem(el_api._SCENARIO_PATHS, "referral", path)
        monkeypatch.setitem(el_api._SCENARIO_DEADLINE_SCALE, "referral", 1)
        monkeypatch.setattr(el_api, "_active_scenario", "referral")
        monkeypatch.setattr(el_api, "_active_community", "K")
        runtime = _quiet(Runtime.build_from_spec, result.model)
        monkeypatch.setattr(el_api, "_runtime", runtime)
        return runtime
    return _install


def _status(mode):
    return _quiet(el_api.get_obligation_status, "duty", deadline_scale=1, mode=mode)


def _verifier(mode, runtime, src):
    """The verifier's own AF verdict on `duty`, as the route computes it."""
    if mode == "spec":
        km = _quiet(build_kripke_model, _quiet(parse_string, src, validate=False).model,
                    horizon=10)
    else:
        km = _quiet(build_kripke_from_runtime, runtime, horizon=10)
    return km.check_obligation("duty")


def _begin(runtime):
    assert _quiet(runtime.advance, "begin", "Holder", {}).outcome == "ok"


def _fire_then_begin(runtime):
    """Violate `other` by the clock, fire VR, then trigger `duty`."""
    _quiet(runtime.advance_clock, 2)
    _quiet(runtime.check_live_violations)
    assert _quiet(runtime.fire_violation_responses).fired_responses == ("VR",)
    _begin(runtime)


def _gate_states(runtime):
    return [t.state for t in runtime.current_state().tokens if t.token_name == "gate"]


@pytest.mark.parametrize("mode", ["spec", "hybrid"])
@pytest.mark.parametrize("clause", ["suspends: A1", "expires: A1"])
def test_response_clause_withholds(install, clause, mode):
    src = _spec(clause)
    runtime = install(src)
    _begin(runtime)  # duty active; the response has not fired
    assert _gate_states(runtime) == ["active"]
    assert _verifier(mode, runtime, src).satisfied is True  # the claim being withheld

    status = _status(mode)
    assert status.compelled is None
    assert status.status == RESPONSE_NOT_MODELLED
    # As computed: only `compelled` is withheld.
    assert status.detectable is True
    assert status.witness_path
    assert status.counterexample_path is None
    assert status.standing is False


@pytest.mark.parametrize("clause, permit_state", [
    ("suspends: A1", "pending"),
    ("expires: A1", "expired"),
])
def test_fired_anchor_withholds(install, clause, permit_state):
    src = _spec(clause)
    runtime = install(src)
    _fire_then_begin(runtime)
    assert _gate_states(runtime) == [permit_state]

    # The hybrid model's answer is a correct false here; it is withheld too.
    assert _verifier("hybrid", runtime, src).satisfied is False
    status = _status("hybrid")
    assert status.compelled is None
    assert status.status == RESPONSE_NOT_MODELLED
    assert status.detectable is False
    assert status.witness_path is None
    assert status.counterexample_path

    refused = _quiet(runtime.advance, "file", "Holder", {})
    assert refused.outcome == "blocked"
    assert "required permit 'gate' not held" in refused.reason


def test_permit_not_gating_keeps_the_verdict(install):
    # VR suspends A2, whose permit `spare` no discharging action of duty requires.
    src = _spec("suspends: A2")
    runtime = install(src)
    _begin(runtime)
    for mode in ("spec", "hybrid"):
        status = _status(mode)
        assert status.compelled is True
        assert status.status is None


def test_eventual_burden_keeps_its_verdict(install):
    src = _spec("suspends: A1", mode="eventual")
    runtime = install(src)
    _begin(runtime)
    for mode in ("spec", "hybrid"):
        verdict = _verifier(mode, runtime, src)
        status = _status(mode)
        assert status.compelled is verdict.satisfied
        assert status.status == verdict.status
        assert status.status != RESPONSE_NOT_MODELLED


def test_revokes_only_keeps_the_verdict(install):
    # Known gap, left open on purpose (open finding in docs/CONCEPTS_INDEX.md: a
    # response's `revokes:` leaves the static status route saying `compelled:
    # true`). This test pins that the 2.5.0-2 withholding does not cover
    # `revokes:`; change it when that finding is fixed.
    install(_spec("revokes: A1"))
    status = _status("spec")
    assert status.compelled is True
    assert status.status is None


def test_time_limit_status_takes_precedence(install):
    runtime = install(_spec("expires: A1", limit='deadline: "5 minutes"'))
    _begin(runtime)
    for mode in ("spec", "hybrid"):
        status = _status(mode)
        assert status.compelled is None
        assert status.status == TIME_NOT_MODELLED


def test_to_role_authorization_is_withheld(install):
    # A1 is granted to the role Holder fills; the match is by permit name, so no
    # role is resolved.
    runtime = install(_spec("suspends: A1", grantee="to_role: r"))
    _begin(runtime)
    for mode in ("spec", "hybrid"):
        status = _status(mode)
        assert status.compelled is None
        assert status.status == RESPONSE_NOT_MODELLED


_EVENT_DISCHARGED = dict(
    burden=('burden duty { state: active deadline: "1 day" discharged_by: doneEvent '
            'discharge_mode: strict }'),
    file_body="requires_permit gate emits: doneEvent",
    events="event doneEvent",
)


def test_event_discharged_route_is_withheld(install):
    # duty is discharged by an event that `file` emits, and `file` requires gate.
    install(_spec("suspends: A1", **_EVENT_DISCHARGED))
    status = _status("spec")
    assert status.compelled is None
    assert status.status == RESPONSE_NOT_MODELLED

    # Control: without the clause the response status is not given.
    install(_spec("", **_EVENT_DISCHARGED))
    assert _status("spec").status != RESPONSE_NOT_MODELLED
