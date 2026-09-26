"""
AM-106 — hybrid T2 applies to permit-gated burdens; the fallback
descriptor uses the live token's for_action and static deadline parsing.

Before AM-106, hybrid T2 sat inside the T1 loop after the permit gate, so
a burden whose discharging action requires a permit was never VIOLATED in
a hybrid model, and a ViolationResponse on it could never fire in the
model. Now T2 is its own loop over every PENDING obligation, as in the
static builder; the gate stays on T1 only.
"""
import contextlib
import io

from el_api import _SCENARIO_BUILDERS
from el_kripke import (
    RESPONSE_OPERATOR,
    ObligationState,
    _build_permit_requirement_index,
    build_kripke_from_runtime,
    build_kripke_model,
)
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _labels(km, prefix):
    return [label for label in km.labels.values() if label.startswith(prefix)]


# A gated burden with a short deadline; its violation's response creates a
# strict notice burden on another party (response-only root, AM-105).
_GATED_PROBE = """
enterprise specification GatedViolationProbe

party Clinic {
    holds answerBurden
    holds answerPermit
}
party Practice
party GP

burden answerBurden { for_action: "answer" state: active deadline: "1 hour" discharge_mode: eventual }
permit answerPermit { for_action: "answer" state: active }
burden noticeBurden { for_action: "notify" state: active deadline: "1 hour" discharge_mode: strict }

commitment ClinicAnswers { by: Clinic obligation: "answer" creates_burden: answerBurden }

community ProbeCommunity {
    objective: "probe hybrid T2 on a gated burden"
    role clinicRole {
        action answer { requires_permit answerPermit }
    }
    role practiceRole {
        action notify { }
    }
}

violation_response lateAnswer {
    on_violation_of: answerBurden
    obligates: Practice
    response_kind: escalate
    creates_burden: noticeBurden
    escalate_to: GP
}
"""


def _gated_spec():
    result = _quiet(parse_string, _GATED_PROBE, validate=False)
    assert result.ok, result.errors
    return result.model


def test_gated_burden_violated_in_hybrid_and_response_activates():
    spec = _gated_spec()
    assert "answer" in _build_permit_requirement_index(spec)
    km = _quiet(build_kripke_from_runtime, _quiet(Runtime.build_from_spec, spec), horizon=10)

    assert _labels(km, "examine:answerBurden")          # discharge via T6, not T1
    assert not _labels(km, "discharge:answerBurden")
    assert km.EF(km.initial, "violated:answerBurden") is True
    assert set(_labels(km, "violate:answerBurden")) == {"violate:answerBurden"}

    # AM-105: seeded WAITING; the gated burden's T2 edge activates it.
    assert dict(km.initial.obligation_states)["noticeBurden"] == ObligationState.WAITING
    violated = [s for (w, s), label in km.labels.items() if label == "violate:answerBurden"]
    assert violated
    assert all(dict(s.obligation_states)["noticeBurden"] == ObligationState.PENDING
               for s in violated)

    verdict = km.check_obligation("noticeBurden")
    assert verdict.modal_operator == RESPONSE_OPERATOR
    assert verdict.satisfied is True
    assert km.check_permission("noticeBurden").satisfied is True


def test_gated_probe_hybrid_matches_static():
    spec = _gated_spec()
    hybrid = _quiet(build_kripke_from_runtime, _quiet(Runtime.build_from_spec, spec), horizon=10)
    static = _quiet(build_kripke_model, spec, horizon=10)
    for km in (hybrid, static):
        assert km.EF(km.initial, "violated:answerBurden") is True
        assert km.check_obligation("noticeBurden").satisfied is True


def test_referral_ai_examination_now_violable_in_hybrid():
    """referral's aiExaminationBurden (gated): violation now reachable in
    hybrid, matching static; AF/EF unchanged (AF false, EF true).
    Its deadline, "referral episode", has no elapsed-time magnitude: the 5
    steps are _parse_deadline_steps()'s default, and the engine never
    clock-violates it. This pins the verifier as it is (verifier-wide
    no-magnitude mismatch, see the AM-106 entry), not engine behaviour."""
    km = _quiet(build_kripke_from_runtime, _quiet(_SCENARIO_BUILDERS["referral"]), horizon=10)
    assert km.EF(km.initial, "violated:aiExaminationBurden") is True
    assert km.check_obligation("aiExaminationBurden").satisfied is False
    assert km.check_permission("aiExaminationBurden").satisfied is True


def test_fallback_descriptor_uses_token_for_action():
    """ereferral's aiExaminationBurden has no spec descriptor. Its fallback
    descriptor now carries the token's for_action, so it is gated: T6
    discharges it (examine), T1 no longer does."""
    km = _quiet(build_kripke_from_runtime, _quiet(_SCENARIO_BUILDERS["ereferral"]), horizon=10)
    assert km.obligation_descriptors["aiExaminationBurden"].for_action == "conductAIExamination"
    assert _labels(km, "examine:aiExaminationBurden → conductAIExamination")
    assert not _labels(km, "discharge:aiExaminationBurden")


_BARE_DEADLINE_PROBE = """
enterprise specification BareDeadlineProbe

party Holder {
    holds bareBurden
}

burden bareBurden { for_action: "act" state: active deadline: "10" discharge_mode: eventual }
"""


def test_fallback_deadline_parsed_as_static():
    """A live token with no spec descriptor (no Commitment root) and a bare
    number deadline: parsed as _build_obligation_descriptors() parses it —
    no elapsed-time magnitude, so the default of 5 steps, not int("10")."""
    result = _quiet(parse_string, _BARE_DEADLINE_PROBE, validate=False)
    assert result.ok, result.errors
    km = _quiet(build_kripke_from_runtime, _quiet(Runtime.build_from_spec, result.model), horizon=10)
    assert km.obligation_descriptors["bareBurden"].deadline_steps == 5
