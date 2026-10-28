"""
Layer 3 — a violation record's identity holds its source (2.3.0-7).

ViolationRecord.occurrence is (rule, violator, behaviour, occurred_at);
ViolationRecord.identity is the occurrence and the source. declare_breach()
refuses only an occurrence already declared; an occurrence recorded as a
refused attempt is declared as a second record, with the effect line
"confirms the refused attempt recorded at step N". A ViolationResponse's
marker key is (response,) + occurrence, the same five items as in 2.3.0-4:
one firing per occurrence, whichever records it has. Kripke: unchanged
(parity R22, R24).
"""
from dataclasses import replace

from el_engine import ViolationRecord, declare_breach, fire_violation_responses
from el_runtime import Runtime
from test_violation_record_responses import _spec as _response_spec
from test_violation_records import _spec, _state


def _refused(rule="stopE", kind="embargo", rule_holder="Ag"):
    return ViolationRecord(rule=rule, kind=kind, violator="Ag", behaviour="use",
                           declared_by="system", occurred_at=0, declared_at=0,
                           source="refused_attempt", rule_holder=rule_holder)


def test_identity_holds_the_source_and_occurrence_does_not():
    refused = _refused()
    declared = replace(refused, source="declared", declared_by="Dog")
    assert refused.occurrence == ("stopE", "Ag", "use", 0)
    assert refused.identity == ("stopE", "Ag", "use", 0, "refused_attempt")
    assert refused.occurrence == declared.occurrence
    assert refused.identity != declared.identity


def test_a_declaration_confirms_a_refused_attempt():
    spec = _spec()
    state = _state(spec, ("declP", "Dog"), ("stopE", "Ag")).with_violation_records(
        (_refused(),))
    new_state, record = declare_breach(state, spec, "stopE", "embargo", "Ag", "use", "Dog",
                                       occurred_at=0, in_force={("stopE", "Ag"): True})
    assert record.outcome == "violation"
    assert record.effects == (
        "declared violation of embargo 'stopE' by 'Ag' in 'use' at step 0 "
        "(declared at step 0)",
        "confirms the refused attempt recorded at step 0",
    )
    assert [r.source for r in new_state.violation_records] == ["refused_attempt", "declared"]
    assert record.violation_records == (new_state.violation_records[1],)


def test_a_second_declaration_is_still_refused():
    spec = _spec()
    state = _state(spec, ("declP", "Dog"), ("stopE", "Ag")).with_violation_records(
        (_refused(),))
    answers = {("stopE", "Ag"): True}
    state, _ = declare_breach(state, spec, "stopE", "embargo", "Ag", "use", "Dog",
                              occurred_at=0, in_force=answers)
    again, record = declare_breach(state, spec, "stopE", "embargo", "Ag", "use", "Dog",
                                   occurred_at=0, in_force=answers)
    assert record.outcome == "blocked"
    assert record.reason == (
        "already recorded: violation of 'stopE' by 'Ag' in 'use' at step 0, "
        "declared at step 0 by 'Dog'")
    assert again is state


def test_a_declaration_without_a_refused_attempt_has_no_confirmation():
    rt = Runtime(_state(_spec(), ("declP", "Dog"), ("stopE", "Ag")), _spec())
    record = rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    assert not any(line.startswith("confirms") for line in record.effects)


def test_a_flagged_response_fires_once_per_occurrence():
    # onUse has also_on_refused_attempts: true.
    spec = _response_spec()
    refused = _refused("useP", "permit_requirement", None)
    state = _state(spec).with_violation_records((refused,))
    state, first = fire_violation_responses(state, spec)
    assert first.fired_responses == ("onUse",)
    state = state.with_violation_records(
        state.violation_records + (replace(refused, source="declared", declared_by="Dog"),))
    state, second = fire_violation_responses(state, spec)
    assert second.fired_responses == ()
    assert ("onUse", "useP", "Ag", "use", 0) in state.responded
    assert {len(k) for k in state.responded} == {5}


def test_an_unflagged_response_fires_once_on_the_declaration():
    # onStop has no flag: the refused attempt is skipped, its declaration fires.
    spec = _response_spec()
    refused = _refused()
    state = _state(spec).with_violation_records((refused,))
    state, first = fire_violation_responses(state, spec)
    assert first.fired_responses == ()
    state = state.with_violation_records(
        state.violation_records + (replace(refused, source="declared", declared_by="Dog"),))
    state, second = fire_violation_responses(state, spec)
    assert second.fired_responses == ("onStop",)
    state, third = fire_violation_responses(state, spec)
    assert third.fired_responses == ()
