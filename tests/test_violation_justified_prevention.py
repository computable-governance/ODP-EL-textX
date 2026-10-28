"""
Layer 3 — justified prevention (2.3.0-3, Annex B.1.7.4).

A declared denial of permission (declare_breach(), kind 'permit') is
refused when an embargo covering the prevented behaviour was in force on
the permit's holder at the occurrence: that prevention is justified, not a
violation of the permission. Runtime.declare_breach() reads it from
history(); unknown history is accepted with a warning. Kripke: absent
(parity R23).
"""
from el_engine import (
    _deontic_refusal, _find_action, breach_history_queries, declare_breach, grant_token,
    token_from_spec,
)
from el_kripke import build_kripke_from_runtime, build_kripke_model
from test_violation_records import _quiet, _runtime, _shape, _spec, _state


def _deny(rt, occurred_at=0):
    return rt.declare_breach("useP", "permit", "Bo", "use", "Dog",
                             occurred_at=occurred_at, rule_holder="Ag")


def test_an_embargo_on_the_holder_justifies_the_prevention():
    rt = _runtime(("useP", "Ag"), ("stopE", "Ag"))
    before = rt.current_state()
    record = _deny(rt)
    assert record.outcome == "blocked"
    assert record.reason == (
        "preventing 'use' at step 0 was justified by embargo 'stopE' held by 'Ag': "
        "not a violation of permit 'useP'")
    assert rt.current_state() == before
    # The engine would have refused Ag's act on the same embargo.
    use, _ = _find_action(rt._spec, "use")
    assert _deontic_refusal(rt._spec, before, "Ag", "use", use)[0] == (
        "active embargo 'stopE' blocks action")


def test_an_embargo_on_someone_else_does_not_justify_it():
    rt = _runtime(("useP", "Ag"), ("stopE", "Bo"))
    record = _deny(rt)
    assert record.outcome == "violation"
    assert record.violation_records[0].warnings == ()


def test_only_an_embargo_in_force_at_the_occurrence_justifies_it():
    # The answer is the embargo's standing at occurred_at, not now: the same
    # state, judged with the embargo not yet (or no longer) in force, records.
    spec = _spec()
    state = _state(spec, ("declP", "Dog"), ("useP", "Ag"), ("stopE", "Ag"))
    for in_force_then, outcome in ((False, "violation"), (True, "blocked")):
        _, record = declare_breach(state, spec, "useP", "permit", "Bo", "use", "Dog",
                                   occurred_at=0, rule_holder="Ag",
                                   in_force={("useP", "Ag"): True,
                                             ("stopE", "Ag"): in_force_then})
        assert record.outcome == outcome


def test_unknown_embargo_history_is_accepted_with_a_warning():
    rt = _runtime(("useP", "Ag"))
    rt._state = grant_token(rt._state, token_from_spec(rt._spec, "stopE", "Ag", 0))
    assert rt.in_force_at("stopE", "Ag", 0) is None
    record = _deny(rt)
    assert record.outcome == "violation"
    warning = ("history unknown: could not establish whether 'Ag' held embargo 'stopE' "
               "at step 0; accepted on the declaration (an embargo would justify the "
               "prevention)")
    assert record.violation_records[0].warnings == (warning,)
    assert record.effects[-1] == warning


def test_only_a_denial_of_permission_is_justified_this_way():
    # An embargo breach and a missing permit are judged as before.
    rt = _runtime(("stopE", "Ag"))
    assert rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog",
                             occurred_at=0).outcome == "violation"
    assert rt.declare_breach("useP", "permit_requirement", "Ag", "use", "Dog",
                             occurred_at=0).outcome == "violation"


def test_history_queries_include_the_covering_embargoes():
    spec = _spec()
    assert breach_history_queries(spec, "useP", "permit", "Bo", "use", "Ag") == (
        ("useP", "Ag"), ("stopE", "Ag"))
    assert breach_history_queries(spec, "readP", "permit", "Bo", "read", "Ag") == (
        ("readP", "Ag"),)


def test_justification_is_absent_from_both_builders():
    rt = _runtime(("useP", "Ag"), ("stopE", "Ag"))
    static_before = _shape(_quiet(build_kripke_model, rt._spec, horizon=8))
    hybrid_before = _shape(_quiet(build_kripke_from_runtime, rt, horizon=8))
    assert _deny(rt).outcome == "blocked"
    assert _shape(_quiet(build_kripke_model, rt._spec, horizon=8)) == static_before
    assert _shape(_quiet(build_kripke_from_runtime, rt, horizon=8)) == hybrid_before
