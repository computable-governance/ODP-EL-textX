"""
Layer 3 — Runtime.in_force_at() and Runtime.token_states_at().

Whether a holder held a token active when an act at a given tick was
judged, read from the token events of Runtime.history() (the build record,
then the ledger): the events of every record with a lower tick apply. The
answer is None (unknown) for a tick outside the run, or when the history
does not reproduce the holder's current instances of the token.
"""
import contextlib
import io
from dataclasses import replace

import el_api
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


PERMIT = "patientRecordAccessPermitByAuthorization"
EMBARGO = "patientRecordAccessEmbargo"
AGENT = "SpecialistAIAgent"
AUTH = "patientDataAuthorization"
FACTS = {"Patient must have an active episode of care and clinical indication for "
         "referral": True}


def _revoked_and_reinstated():
    """initiateReferral at tick 0, the revocation at tick 1, the
    reinstatement at tick 2; the run ends at tick 3."""
    rt = _quiet(el_api._build_referral_runtime)
    assert rt.advance("initiateReferral", "GPClinician", facts=FACTS).tick == 0
    assert rt.revoke_authorization(AUTH).tick == 1
    assert rt.reinstate_authorization(AUTH).tick == 2
    assert rt.current_state().tick == 3
    return rt


def test_permit_in_force_until_revoked_and_again_after_reinstatement():
    rt = _revoked_and_reinstated()
    assert [rt.in_force_at(PERMIT, AGENT, t) for t in range(4)] == [True, True, False, True]
    assert [rt.token_states_at(PERMIT, AGENT, t) for t in range(4)] == [
        ("active",), ("active",), ("superseded",), ("active",)]


def test_embargo_in_force_from_revocation_until_lifted():
    rt = _revoked_and_reinstated()
    assert [rt.in_force_at(EMBARGO, AGENT, t) for t in range(4)] == [False, False, True, False]
    assert rt.token_states_at(EMBARGO, AGENT, 1) == ()
    assert rt.token_states_at(EMBARGO, AGENT, 3) == ("lifted",)


def test_never_granted_and_ticks_outside_the_run():
    rt = _revoked_and_reinstated()
    assert rt.in_force_at(PERMIT, "GPClinician", 2) is False
    assert rt.token_states_at("noSuchToken", AGENT, 0) == ()
    assert rt.in_force_at(PERMIT, AGENT, 4) is None
    assert rt.in_force_at(PERMIT, AGENT, -1) is None


def test_a_change_outside_the_runtime_makes_that_token_unknown():
    rt = _revoked_and_reinstated()
    rt._state = grant_token(rt._state, token_from_spec(rt._spec, EMBARGO, "GPClinician", 3))
    assert rt.in_force_at(EMBARGO, "GPClinician", 3) is None
    assert rt.in_force_at(EMBARGO, AGENT, 2) is True     # another holder: still answered
    assert rt.in_force_at(PERMIT, AGENT, 2) is False


_PROBE = """
enterprise specification InForceAtProbe

party Lead
party Worker

community ProbeCommunity
    description: "A lead hands a burden over"
    {
        objective: "o"

        role leadRole
            description: "The lead"
            {
                action handOver {
                    description: "Transfers handBurden to the worker"
                    actor: leadRole
                    effect transfer handBurden to workerRole
                }
            }

        role workerRole
            description: "The worker"
            {
            }
    }

burden handBurden {
    state: active
    discharge_mode: eventual
}

permit sharedPermit {
    state: active
}
"""


def test_per_holder_and_several_instances():
    result = _quiet(parse_string, _PROBE, validate=False)
    assert result.ok, result.errors
    spec = result.model
    state = initial_state()
    state = enroll(state, "Lead", role_name="leadRole")
    state = enroll(state, "Worker", role_name="workerRole")
    state = grant_token(state, token_from_spec(spec, "handBurden", "Lead", 0))
    permit = token_from_spec(spec, "sharedPermit", "Worker", 0)
    state = grant_token(state, permit)
    state = grant_token(state, replace(permit, state="pending"))
    rt = Runtime(state, spec)

    assert rt.advance("handOver", "Lead").outcome == "ok"
    assert (rt.in_force_at("handBurden", "Lead", 0), rt.in_force_at("handBurden", "Lead", 1)) == (
        True, False)
    assert (rt.in_force_at("handBurden", "Worker", 0),
            rt.in_force_at("handBurden", "Worker", 1)) == (False, True)
    assert rt.token_states_at("handBurden", "Lead", 1) == ()

    assert rt.token_states_at("sharedPermit", "Worker", 1) == ("active", "pending")
    assert rt.in_force_at("sharedPermit", "Worker", 1) is True
