"""
Layer 3 — ViolationResponses on violation records (2.3.0-4).

A ViolationResponse whose on_violation_of names a permit or embargo fires
once per ViolationRecord naming it (declare_breach()): by default only
records with source 'declared'; with `also_on_refused_attempts: true`,
also 'refused_attempt' records (none is produced yet; the tests build one).
The once-only marker key is (response, rule, violator, behaviour,
occurred_at). Responses on violated burdens are unchanged. Kripke: a
burden such a response creates stays WAITING in the static model and is
not tracked by the hybrid one until granted (parity R24).
"""
from dataclasses import replace

import pytest

from el_engine import ViolationRecord, fire_violation_responses
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime
from test_violation_records import _SPEC, _quiet, _state

_RESPONSES = """
commitment GateRecords {
    by: Gate
    obligation: "record"
    creates_burden: recB
}
burden remedyB { for_action: "rec" state: active deadline: "5 minutes" }
authorization AgUse {
    authority: Gate
    to_agent: Ag
    grants_permit: useP
    revocable: true
    on_revocation: activate stopE
}
violation_response onStop {
    on_violation_of: stopE
    obligates: Gate
    response_kind: remediate
    creates_burden: remedyB
}
violation_response onUse {
    on_violation_of: useP
    obligates: Gate
    response_kind: terminate
    also_on_refused_attempts: true
}
violation_response onRec {
    on_violation_of: recB
    obligates: Gate
    response_kind: escalate
    escalate_to: Dog
}
"""


def _spec():
    result = _quiet(parse_string, _SPEC + _RESPONSES, validate=False)
    assert result.ok, result.errors
    return result.model


def _runtime(*grants):
    spec = _spec()
    return Runtime(_state(spec, ("declP", "Dog"), *grants), spec)


def test_the_flag_parses_with_default_false():
    spec = _spec()
    responses = {el.name: el for el in spec.elements
                 if type(el).__name__ == "ViolationResponse"}
    assert responses["onStop"].also_on_refused_attempts is False
    assert responses["onUse"].also_on_refused_attempts is True
    assert responses["onStop"].violated_burden.name == "stopE"


def test_a_declared_record_fires_its_response_once():
    rt = _runtime(("stopE", "Ag"))
    rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    tick = rt.current_state().tick
    record = rt.fire_violation_responses()
    assert record.fired_responses == ("onStop",)
    assert record.effects == (
        "fired 'onStop': granted 'remedyB' to 'Gate'",
        "fired 'onStop' (remediate) on violation of embargo 'stopE' by 'Ag' in 'use' "
        "at step 0",
    )
    state = rt.current_state()
    assert state.tick == tick + 1
    assert ("onStop", "stopE", "Ag", "use", 0) in state.responded
    assert any(t.token_name == "remedyB" and t.holder == "Gate" for t in state.tokens)
    again = rt.fire_violation_responses()
    assert again.fired_responses == () and rt.current_state().tick == tick + 1


def test_each_occurrence_fires_once():
    rt = _runtime(("stopE", "Ag"))
    rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    rt.fire_violation_responses()                 # tick 0 -> 1
    rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=1)
    record = rt.fire_violation_responses()
    assert record.fired_responses == ("onStop",)
    assert record.effects[-1].endswith("in 'use' at step 1")


def test_terminate_takes_the_records_violator():
    # Bo prevented Ag: the violator is Bo, who is granted no Authorization.
    rt = _runtime(("useP", "Ag"))
    rt.declare_breach("useP", "permit", "Bo", "use", "Dog", occurred_at=0, rule_holder="Ag")
    record = rt.fire_violation_responses()
    assert record.effects == (
        "fired 'onUse' (terminate) on violation of permit 'useP' by 'Bo' in 'use' at step 0",)
    # Ag acted without useP: the violator is Ag, so AgUse is considered.
    rt = _runtime()
    rt.declare_breach("useP", "permit_requirement", "Ag", "use", "Dog", occurred_at=0)
    record = rt.fire_violation_responses()
    assert record.effects == (
        "fired 'onUse' (terminate) on violation of permit requirement 'useP' by 'Ag' "
        "in 'use' at step 0",
        "not revoked 'AgUse': permit 'useP' is not active",
    )


@pytest.mark.parametrize("response,rule,kind,violator,fires", [
    ("onStop", "stopE", "embargo", "Ag", False),
    ("onUse", "useP", "permit_requirement", "Ag", True),
])
def test_refused_attempt_records_fire_only_with_the_flag(response, rule, kind, violator,
                                                         fires):
    spec = _spec()
    refused = ViolationRecord(rule=rule, kind=kind, violator=violator, behaviour="use",
                              declared_by="system", occurred_at=0, declared_at=0,
                              source="refused_attempt")
    state = _state(spec).with_violation_records((refused,))
    _, record = fire_violation_responses(state, spec)
    assert (response in record.fired_responses) is fires
    _, declared = fire_violation_responses(
        state.with_violation_records((replace(refused, source="declared"),)), spec)
    assert response in declared.fired_responses


def test_burden_responses_are_unchanged():
    rt = _runtime(("recB", "Gate"))
    rt.advance_clock(5)
    rt.check_live_violations()
    record = rt.fire_violation_responses()
    assert record.fired_responses == ("onRec",)
    assert record.effects == (
        "fired 'onRec' (escalate) on violation of 'recB' by 'Gate'",
        "escalated 'onRec' to 'Dog'",
    )
    assert ("onRec", "recB", "Gate", 0) in rt.current_state().responded


def test_burden_and_record_keys_never_collide():
    rt = _runtime(("stopE", "Ag"), ("recB", "Gate"))
    rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    rt.advance_clock(5)
    rt.check_live_violations()
    record = rt.fire_violation_responses()
    assert sorted(record.fired_responses) == ["onRec", "onStop"]
    assert {len(k) for k in rt.current_state().responded} == {4, 5}


def test_response_created_burden_is_waiting_or_absent_in_the_verifier():
    static = _quiet(build_kripke_model, _spec(), horizon=8)
    assert {str(w.get_obligation("remedyB")) for w in static.worlds} == {
        "ObligationState.WAITING"}
    hybrid = _quiet(build_kripke_from_runtime, _runtime(("stopE", "Ag"), ("recB", "Gate")),
                    horizon=8)
    with pytest.raises(KeyError):
        next(iter(hybrid.worlds)).get_obligation("remedyB")
