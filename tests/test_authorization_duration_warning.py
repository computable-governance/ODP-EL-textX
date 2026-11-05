"""
2.5.0-1 — [W-authorization-duration] (slot W-30).

An Authorization's `duration` is recorded and not enforced. The validator says
so and nothing else changes: the permit it grants is still usable after the
duration has passed. A permit's time limit is the permit's own `deadline`.
"""
from el_parser import parse_string
from el_runtime import Runtime


_SPEC = """
enterprise specification AuthorizationDurationProbe

party Issuer
party Worker {
    holds dataPermit
}

community ProbeCommunity
    description: "One action gated by a permit"
    {
        objective: "Exercise an Authorization's duration"

        Worker fills workerRole

        role workerRole
            description: "Performs the gated action"
            {
                action useData {
                    actor: workerRole
                    requires_permit dataPermit
                }
            }
    }

permit dataPermit {
    for_action: "useData"
    state: active
    PERMIT_DEADLINE
}

authorization DataAuthorization {
    authority: Issuer
    to_agent: Worker
    grants_permit: dataPermit
    AUTHORIZATION_DURATION
}
"""

_NINETY_DAYS_IN_TICKS = 90 * 24 * 60


def _parse(duration, permit_deadline=""):
    text = _SPEC.replace("AUTHORIZATION_DURATION", duration).replace("PERMIT_DEADLINE", permit_deadline)
    result = parse_string(text, validate=True)
    assert result.ok, result.errors
    return result


def _duration_warnings(result):
    return [w for w in result.warnings if w.startswith("[W-authorization-duration]")]


def test_a_duration_warns_and_names_the_authorization():
    assert _duration_warnings(_parse('duration: "90 days"')) == [
        "[W-authorization-duration] Authorization 'DataAuthorization' has duration "
        "'90 days': the duration is recorded and not enforced, so it does not limit "
        "the permit it grants. (clause to be confirmed)"
    ]


def test_no_duration_is_silent():
    assert _duration_warnings(_parse("")) == []


def _use_after_ninety_days(result):
    rt = Runtime.build_from_spec(result.model)
    rt.advance_clock(_NINETY_DAYS_IN_TICKS + 1)
    return rt.advance("useData", "Worker").outcome


def test_the_permit_is_still_usable_after_the_duration_has_passed():
    assert _use_after_ninety_days(_parse('duration: "90 days"')) == "ok"
    # Control: the same time limit on the permit itself does refuse the use.
    assert _use_after_ninety_days(_parse("", 'deadline: "90 days"')) == "blocked"
