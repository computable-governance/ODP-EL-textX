"""
2.1.0-17 — a standing duty ends only at its term end.

No action (its for_action), destroy effect, discharged_by event,
discharge_burden() or declaration discharges or violates a standing duty,
and no deadline or episode conclusion violates it (the 2.1.0 principle
that a duty measured by time or reports is not ended by a group
concluding). Each case runs beside a plain burden in the same position, which
is still discharged or violated, so the exclusion is what differs.

Several specs here are invalid by design (the validator refuses a
for_action, discharged_by, deadline or group membership on a standing
duty from 2.1.0-19); they are parsed without validation to show the
engine holds even so.

The verifier does not know standing duties (parity row R13): its T1 still
discharges one. The last test pins that, so that a change is deliberate.

Layer 3 (runtime) and Layer 4 (verifier) tests per tests/README.md.
"""
import contextlib
import io

import pytest

from el_kripke import build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _runtime(tokens, extra="", actions=""):
    holds = " ".join(f"holds {name}" for name in ("duty", "plainTwin"))
    src = f"""enterprise specification ExclusionProbe
policy MinimumCover : amount {{ initial_value: 20000000 AUD }}
party Supplier {{ {holds} }}
community C {{
    objective: "o"
    event done
    Supplier fills r
    role r {{
        action file {{ actor: r }}
        action finish {{ actor: r emits: done }}
        action withdraw {{ actor: r effect destroy duty effect destroy plainTwin }}
{actions}
    }}
}}
{tokens}
{extra}
"""
    result = _quiet(parse_string, src, validate=False)
    assert result.ok, result.errors
    return _quiet(Runtime.build_from_spec, result.model)


def _states(rt):
    return {t.token_name: t.state for t in rt.current_state().tokens}


_STANDING = 'standing keeps: "insurance cover" >= MinimumCover'


def _pair(fields):
    return (f"burden duty {{ {_STANDING} {fields} }}\n"
            f"burden plainTwin {{ {fields} }}")


def test_not_discharged_by_its_for_action():
    rt = _runtime(_pair('for_action: "file" state: active'))
    record = _quiet(rt.advance, "file", "Supplier", {})
    assert record.outcome == "ok"
    assert _states(rt) == {"duty": "active", "plainTwin": "discharged"}
    assert ("standing duty 'duty' held by 'Supplier' not discharged: it ends only at "
            "its term end") in record.effects


def test_not_discharged_by_a_destroy_effect():
    rt = _runtime(_pair("state: active"))
    _quiet(rt.advance, "withdraw", "Supplier", {})
    assert _states(rt) == {"duty": "active", "plainTwin": "discharged"}


@pytest.mark.parametrize("how", ["action", "fire_event"])
def test_not_discharged_by_its_discharged_by_event(how):
    rt = _runtime(_pair("state: active discharged_by: done"))
    if how == "action":
        _quiet(rt.advance, "finish", "Supplier", {})
    else:
        _quiet(rt.fire_event, "done")
    assert _states(rt) == {"duty": "active", "plainTwin": "discharged"}


def test_discharge_burden_refused():
    rt = _runtime(_pair("state: active"))
    tick = rt.current_state().tick
    record = rt.discharge_burden("duty")
    assert record.outcome == "blocked"
    assert record.reason == ("'duty' is a standing duty: it ends only at its term end, "
                             "not by discharge_burden() (clause to be confirmed)")
    assert _states(rt)["duty"] == "active" and rt.current_state().tick == tick
    assert rt.discharge_burden("plainTwin").outcome == "ok"
    assert _states(rt)["plainTwin"] == "discharged"


def test_declaration_refused():
    rt = _runtime(_pair("state: active"))
    record = rt.declare_violation("duty", "Supplier", 10 ** 6)
    assert record.outcome == "blocked"
    assert record.reason.startswith("'duty' is a standing duty: declaring its breach is "
                                    "not supported")
    assert record.reason.endswith("(clause to be confirmed)")
    assert _states(rt)["duty"] == "active"


def test_not_violated_by_a_deadline():
    rt = _runtime(_pair('state: active deadline: "1 minute"'))
    _quiet(rt.advance_clock, 10)
    record = _quiet(rt.check_live_violations)
    assert record.violations == ("plainTwin",)
    assert _states(rt)["duty"] == "active"


_EPISODE = """
burden other { for_action: "file" state: active deadline: "1 week" }
token_group dutyGroup {
    member: other
    member: duty
}
token_group twinGroup {
    member: other
    member: plainTwin
}
community DutyEpisode {
    objective: "o"
        satisfaction: all_discharged(dutyGroup)
    lifecycle { terminating { on_objective_achieved: true } }
}
community TwinEpisode {
    objective: "o"
        satisfaction: all_discharged(twinGroup)
    lifecycle { terminating { on_objective_achieved: true } }
}
"""


def test_episode_conclusion_neither_ends_nor_violates_it():
    # Two groups share 'other'. Once it is discharged, each episode has
    # concluded around its last member: the plain twin (no magnitude in its
    # deadline) is violated by conclusion; the standing duty is not.
    src = _runtime(_pair('state: active deadline: "for the term"'), extra=_EPISODE)._spec
    from el_engine import grant_token, token_from_spec
    rt = _quiet(Runtime.build_from_spec, src)
    rt._state = grant_token(rt.current_state(), token_from_spec(src, "other", "Supplier", 0))
    _quiet(rt.advance, "file", "Supplier", {})          # discharges 'other'
    record = _quiet(rt.check_live_violations)
    assert record.violations == ("plainTwin",)
    assert _states(rt)["duty"] == "active"


def test_not_superseded_as_a_group_sibling():
    extra = """
token_group pool {
    member: duty
    member: plainTwin
}
community Pool {
    objective: "o"
        satisfaction: any_discharged(pool)
}
"""
    rt = _runtime(_pair('for_action: "file" state: active'), extra=extra)
    _quiet(rt.advance, "file", "Supplier", {})
    assert _states(rt)["duty"] == "active"


def test_plain_burdens_unchanged_without_standing_duties():
    rt = _runtime("burden duty { state: active }\nburden plainTwin { for_action: \"file\" state: active }")
    _quiet(rt.advance, "file", "Supplier", {})
    _quiet(rt.advance, "withdraw", "Supplier", {})
    assert _states(rt) == {"duty": "discharged", "plainTwin": "discharged"}


# ── Verifier: R13 pinned ─────────────────────────────────────────────────

def test_verifier_still_discharges_a_standing_duty():
    # Parity row R13: the verifier treats a standing duty as an ordinary
    # obligation (T1 discharges it by its holder). If this test fails, the
    # verifier now models standing duties: update the matrix with it.
    src = f"""enterprise specification VerifierProbe
policy MinimumCover : amount {{ initial_value: 20000000 AUD }}
party Supplier {{ holds duty }}
burden duty {{ {_STANDING} state: active }}
commitment C {{ by: Supplier obligation: "keep cover" creates_burden: duty }}
"""
    model = _quiet(parse_string, src, validate=False).model
    km = _quiet(build_kripke_model, model, horizon=5)
    assert "discharge:duty by Supplier" in set(km.labels.values())
    assert km.check_obligation("duty").satisfied is False      # never compelled (eventual)
    rt = _quiet(Runtime.build_from_spec, model)
    assert rt.discharge_burden("duty").outcome == "blocked"
