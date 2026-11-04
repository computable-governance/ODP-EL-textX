"""
2.4.1-1 — `effect activate` on a closed burden, through the paths that read it.

The hybrid Kripke builder reads a burden's state from the runtime, so it has
to agree with the engine after a no-op activate. The shipped ereferral
scenario can repeat acknowledgeReferral, which has no precondition and
activates examinationBurden, after that burden has been discharged.

ereferral's examinationBurden has no deadline, so the clock cannot violate
it. The discharged path is the one the shipped scenario reaches.
"""
import contextlib
import io

from el_api import _SCENARIO_BUILDERS
from el_engine import _parse_deadline_steps, enroll, grant_token, initial_state, token_from_spec
from el_kripke import ObligationState, build_kripke_from_runtime
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification ActivateEffectRealPathsProbe

party Operator

community ProbeCommunity
    description: "Single role whose action activates a burden"
    {
        objective: "Exercise the activate effect on a violated burden"

        role operatorRole
            description: "Performs the act"
            {
                action openFollowUp {
                    actor: operatorRole
                    effect activate followUpBurden
                }
            }
    }

burden followUpBurden {
    state: pending
    deadline: "1 hour"
    discharge_mode: eventual
}
"""


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _token(rt, name):
    return next(t for t in rt.current_state().tokens if t.token_name == name)


def _hybrid(rt):
    return _quiet(build_kripke_from_runtime, rt, horizon=10)


def test_hybrid_reads_violated_after_noop_activate():
    result = _quiet(parse_string, _PROBE, validate=True)
    assert result.ok, result.errors
    spec = result.model
    state = enroll(initial_state(), "Operator", role_name="operatorRole")
    state = grant_token(state, token_from_spec(spec, "followUpBurden", "Operator", 0))
    rt = Runtime(state, spec)

    assert rt.advance("openFollowUp", "Operator").outcome == "ok"
    assert rt.advance_clock(_parse_deadline_steps("1 hour")).outcome == "ok"
    assert rt.check_live_violations().violations == ("followUpBurden",)
    assert _token(rt, "followUpBurden").state == "violated"
    before = _hybrid(rt)
    assert before.initial.get_obligation("followUpBurden") == ObligationState.VIOLATED

    assert rt.advance("openFollowUp", "Operator").outcome == "ok"

    after = _hybrid(rt)
    assert after.initial.get_obligation("followUpBurden") == ObligationState.VIOLATED
    assert all(w.get_obligation("followUpBurden") == ObligationState.VIOLATED
               for w in after.reachable(after.initial))
    assert _token(rt, "followUpBurden").state == "violated"


def test_ereferral_repeated_act_does_not_revive():
    rt = _quiet(_SCENARIO_BUILDERS["ereferral"])
    for action, actor in (("submitReferral", "GPClinician"),
                          ("acknowledgeReferral", "SpecialistClinician"),
                          ("scheduleAssessment", "SpecialistClinician")):
        assert rt.advance(action, actor).outcome == "ok"
    before = _token(rt, "examinationBurden")
    assert before.state == "discharged"
    assert before.activated_at_tick == 1

    for _ in range(2):
        record = rt.advance("acknowledgeReferral", "SpecialistClinician")

        assert _token(rt, "examinationBurden") == before
        assert record.outcome == "ok"
        assert record.discharged == ()
        assert record.effects == (
            "activate 'examinationBurden' had no effect: "
            "'SpecialistClinician' holds it discharged",)
