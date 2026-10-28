"""
Layer 3 — violation records for permits and embargoes (2.3.0-2).

el_engine.declare_breach() records a declared violation of an embargo
(its holder performed an action it covers), a permit (a third party
prevented the holder's permitted action) or a permit requirement (the
actor performed an action without the permit it requires) as a
ViolationRecord: on the record (violation_records) and in
WorldState.violation_records. No token changes state and the tick does not
advance. Runtime.declare_breach() reads from history() whether each token
was in force at the occurrence; unknown history is accepted with a warning.
Kripke: absent in both builders (parity R22).
"""
import contextlib
import io
from dataclasses import replace

import pytest

from el_engine import (
    ViolationRecord, breach_history_queries, declare_breach, enroll, grant_token,
    initial_state, token_from_spec,
)
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """
enterprise specification BreachProbe
party Gate
party Dog
party Ag
party Bo
burden recB { for_action: "rec" state: active deadline: "5 minutes" }
permit declP { for_action: "declUse" state: active }
permit useP { for_action: "use" state: active }
permit readP { for_action: "read" state: active }
embargo stopE { for_action: "use" state: active }
community C {
    objective: "o"
    Gate fills gw
    Dog fills dec
    Ag fills user
    Bo fills user
    role gw { action rec { actor: gw } }
    role dec {
        action declUse {
            actor: dec
            requires_permit declP
            declares_violation_of stopE
            declares_violation_of useP
        }
        action declRead {
            actor: dec
            requires_permit declP
            precondition: "evidence"
            declares_violation_of readP
        }
    }
    role user {
        action use { actor: user requires_permit useP }
        action read { actor: user }
        action other { actor: user }
    }
}
"""


def _spec():
    result = _quiet(parse_string, _SPEC, validate=False)
    assert result.ok, result.errors
    return result.model


def _state(spec, *grants):
    state = initial_state(spec)
    for actor, role in (("Gate", "gw"), ("Dog", "dec"), ("Ag", "user"), ("Bo", "user")):
        state = enroll(state, actor, role_name=role)
    for token, holder in grants:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    return state


def _runtime(*grants):
    spec = _spec()
    return Runtime(_state(spec, ("declP", "Dog"), *grants), spec)


# ── accepted declarations ─────────────────────────────────────────────────────

def test_embargo_breach_is_recorded_as_an_event():
    rt = _runtime(("stopE", "Ag"), ("useP", "Ag"))
    before = rt.current_state()
    record = rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    assert (record.outcome, record.action_name, record.actor_name) == (
        "violation", "declUse", "Dog")
    assert record.violations == ("stopE",)
    assert record.violation_records == (ViolationRecord(
        rule="stopE", kind="embargo", violator="Ag", behaviour="use", declared_by="Dog",
        occurred_at=0, declared_at=0, source="declared", rule_holder="Ag"),)
    assert record.effects == (
        "declared violation of embargo 'stopE' by 'Ag' in 'use' at step 0 "
        "(declared at step 0)",)
    after = rt.current_state()
    assert after.tokens == before.tokens and after.tick == before.tick
    assert record.token_events == () and record.discharged == ()
    assert after.violation_records == record.violation_records
    assert after.violation_records[0] is record.violation_records[0]
    assert rt.history()[-1] is record


def test_permit_denial_names_the_third_party_as_violator():
    rt = _runtime(("useP", "Ag"))
    record = rt.declare_breach("useP", "permit", "Bo", "use", "Dog", occurred_at=0,
                               rule_holder="Ag")
    assert record.outcome == "violation"
    (rec,) = record.violation_records
    assert (rec.rule, rec.kind, rec.violator, rec.rule_holder, rec.warnings) == (
        "useP", "permit", "Bo", "Ag", ())
    assert record.effects == (
        "declared violation of permit 'useP' by 'Bo' in 'use' at step 0 "
        "(declared at step 0)",)


def test_acting_without_a_required_permit_names_the_requirement():
    rt = _runtime()
    record = rt.declare_breach("useP", "permit_requirement", "Ag", "use", "Dog",
                               occurred_at=0)
    (rec,) = record.violation_records
    assert (rec.rule, rec.kind, rec.violator, rec.rule_holder) == (
        "useP", "permit_requirement", "Ag", None)
    assert record.effects[0] == (
        "declared violation of permit requirement 'useP' by 'Ag' in 'use' at step 0 "
        "(declared at step 0)")


def test_a_permit_for_action_covers_an_action_that_does_not_require_it():
    rt = _runtime(("readP", "Ag"))
    record = rt.declare_breach("readP", "permit", "Bo", "read", "Dog", occurred_at=0,
                               rule_holder="Ag", facts={"evidence": True})
    assert record.outcome == "violation" and record.action_name == "declRead"
    assert len(record.effects) == 1               # a plain precondition adds no line


def test_occurrence_is_judged_at_its_own_step():
    rt = _runtime(("stopE", "Ag"))
    rt.advance("rec", "Gate")                     # tick 0 -> 1, no token of Ag changes
    record = rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    rec = record.violation_records[0]
    assert (rec.occurred_at, rec.declared_at, record.tick) == (0, 1, 1)


# ── refusals ──────────────────────────────────────────────────────────────────

def _refused(rt, *args, **kwargs):
    before = rt.current_state()
    record = rt.declare_breach(*args, **kwargs)
    assert record.outcome == "blocked"
    assert rt.current_state() == before
    assert record.violation_records == ()
    return record.reason


def test_refusals_before_the_declaring_action_is_chosen():
    rt = _runtime(("stopE", "Ag"))
    assert _refused(rt, "stopE", "embargo", "Ag", "use", "Dog", occurred_at=1) == (
        "'use' at step 1 has not happened yet: the current step is 0")
    assert _refused(rt, "stopE", "embargo", "Ag", "use", "Nobody", occurred_at=0) == (
        "actor 'Nobody' is not enrolled")
    spec = _spec()
    bare = Runtime(_state(spec, ("stopE", "Ag")), spec)   # Dog holds no declP
    assert _refused(bare, "stopE", "embargo", "Ag", "use", "Dog", occurred_at=0) == (
        "required permit 'declP' not held by actor")
    assert _refused(rt, "stopE", "embargo", "Ag", "use", "Ag", occurred_at=0) == (
        "actor 'Ag' does not fill role 'dec', which declares action 'declUse'")
    assert _refused(rt, "readP", "permit", "Bo", "read", "Dog", occurred_at=0,
                    rule_holder="Ag").startswith("precondition")


def test_no_declaring_action():
    spec = _spec()
    rt = Runtime(_state(spec, ("declP", "Dog")), spec)
    with pytest.raises(KeyError):
        rt.declare_breach("noSuch", "permit", "Bo", "use", "Dog", occurred_at=0)
    # declP is a permit no Action declares violated
    assert _refused(rt, "declP", "permit", "Bo", "declUse", "Dog", occurred_at=0,
                    rule_holder="Ag") == (
        "no action declares 'declP' violated (declares_violation_of)")


def test_the_violator_may_not_declare_its_own_violation():
    spec = _spec()
    state = _state(spec, ("declP", "Dog"), ("stopE", "Dog"))
    rt = Runtime(state, spec)
    # stopE covers only "use"; Dog may still perform declUse.
    assert _refused(rt, "stopE", "embargo", "Dog", "use", "Dog", occurred_at=0) == (
        "'Dog' is the violator and may not declare its own violation of 'stopE'")


def test_the_violator_is_an_enterprise_object_and_the_behaviour_an_action():
    rt = _runtime(("stopE", "Ag"))
    assert _refused(rt, "stopE", "embargo", "user", "use", "Dog", occurred_at=0) == (
        "'user' is a role; name the enterprise object that filled it")
    assert _refused(rt, "stopE", "embargo", "Zed", "use", "Dog", occurred_at=0) == (
        "'Zed' is not an enterprise object of the specification")
    assert _refused(rt, "stopE", "embargo", "Ag", "fly", "Dog", occurred_at=0) == (
        "no role declares an action 'fly'")


def test_embargo_refusals():
    rt = _runtime(("stopE", "Ag"))
    assert _refused(rt, "stopE", "embargo", "Ag", "other", "Dog", occurred_at=0) == (
        "embargo 'stopE' does not apply to 'other'")
    assert _refused(rt, "stopE", "embargo", "Bo", "use", "Dog", occurred_at=0) == (
        "'Bo' did not hold embargo 'stopE' in force at step 0")


def test_permit_refusals():
    rt = _runtime(("useP", "Ag"))
    assert _refused(rt, "useP", "permit", "Bo", "use", "Dog", occurred_at=0) == (
        "a denial of permission names the holder whose action was prevented "
        "(rule_holder)")
    assert _refused(rt, "useP", "permit", "Ag", "use", "Dog", occurred_at=0,
                    rule_holder="Ag") == (
        "'Ag' holds 'useP': the holder cannot deny its own permission")
    assert _refused(rt, "useP", "permit", "Bo", "other", "Dog", occurred_at=0,
                    rule_holder="Ag") == "permit 'useP' does not cover 'other'"
    assert _refused(rt, "useP", "permit", "Ag", "use", "Dog", occurred_at=0,
                    rule_holder="Bo") == (
        "'Bo' did not hold permit 'useP' in force at step 0")


def test_permit_requirement_refusals():
    rt = _runtime(("useP", "Ag"))
    assert _refused(rt, "useP", "permit_requirement", "Ag", "other", "Dog",
                    occurred_at=0) == "'other' does not require permit 'useP'"
    assert _refused(rt, "useP", "permit_requirement", "Ag", "use", "Dog",
                    occurred_at=0) == (
        "'Ag' held permit 'useP' at step 0: acting under it is not a violation")


def test_programming_errors_raise():
    rt = _runtime()
    with pytest.raises(ValueError, match="declare_violation"):
        rt.declare_breach("recB", "burden", "Gate", "rec", "Dog", occurred_at=0)
    with pytest.raises(ValueError, match="kind must be"):
        rt.declare_breach("useP", "deny", "Bo", "use", "Dog", occurred_at=0)
    with pytest.raises(ValueError, match="is a 'permit', not a embargo"):
        rt.declare_breach("useP", "embargo", "Ag", "use", "Dog", occurred_at=0)
    with pytest.raises(ValueError, match="is a 'embargo', not a permit"):
        rt.declare_breach("stopE", "permit_requirement", "Ag", "use", "Dog", occurred_at=0)
    assert len(rt.history()) == 1                  # nothing appended


# ── identity ──────────────────────────────────────────────────────────────────

def test_the_same_occurrence_is_recorded_once():
    rt = _runtime(("stopE", "Ag"))
    rt.advance("rec", "Gate")                     # tick 1
    first = rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    assert first.outcome == "violation"
    assert _refused(rt, "stopE", "embargo", "Ag", "use", "Dog", occurred_at=0) == (
        "already recorded: violation of 'stopE' by 'Ag' in 'use' at step 0, "
        "declared at step 1 by 'Dog'")
    other = rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=1)
    assert other.outcome == "violation"
    assert len(rt.current_state().violation_records) == 2


def test_one_behaviour_breaking_two_rules_gives_two_records():
    rt = _runtime(("stopE", "Ag"))                 # Ag holds the embargo, not useP
    a = rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    b = rt.declare_breach("useP", "permit_requirement", "Ag", "use", "Dog", occurred_at=0)
    assert (a.outcome, b.outcome) == ("violation", "violation")
    assert [r.rule for r in rt.current_state().violation_records] == ["stopE", "useP"]


# ── history unknown ───────────────────────────────────────────────────────────

def test_direct_engine_call_without_history_warns():
    spec = _spec()
    state = _state(spec, ("declP", "Dog"))         # nobody holds stopE, but unknown
    new_state, record = declare_breach(state, spec, "stopE", "embargo", "Ag", "use",
                                       "Dog", occurred_at=0)
    warning = ("history unknown: could not establish whether 'Ag' held embargo 'stopE' "
               "at step 0; accepted on the declaration")
    assert record.outcome == "violation"
    assert record.violation_records[0].warnings == (warning,)
    assert record.effects[-1] == warning
    assert new_state.violation_records == record.violation_records


def test_runtime_warns_when_history_does_not_reproduce_the_state():
    rt = _runtime()
    spec = rt._spec
    # A grant made outside the runtime's methods: the history cannot explain it.
    rt._state = grant_token(rt._state, token_from_spec(spec, "stopE", "Ag", 0))
    assert rt.in_force_at("stopE", "Ag", 0) is None
    record = rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    assert record.outcome == "violation"
    assert record.violation_records[0].warnings[0].startswith("history unknown:")


def test_history_queries():
    spec = _spec()
    assert breach_history_queries(spec, "stopE", "embargo", "Ag", "use") == (("stopE", "Ag"),)
    assert breach_history_queries(spec, "useP", "permit_requirement", "Ag", "use") == (
        ("useP", "Ag"),)
    assert breach_history_queries(spec, "readP", "permit", "Bo", "read", "Ag") == (
        ("readP", "Ag"),)
    assert breach_history_queries(spec, "useP", "permit", "Bo", "use") == ()


# ── verifier: absent (R22) ────────────────────────────────────────────────────

def _shape(km):
    return (len(km.worlds), sum(len(v) for v in km.edges.values()),
            km.check_obligation("recB").satisfied, km.check_permission("recB").satisfied)


def test_records_are_absent_from_both_builders():
    rt = _runtime(("stopE", "Ag"), ("useP", "Bo"))
    static_before = _shape(_quiet(build_kripke_model, rt._spec, horizon=8))
    hybrid_before = _shape(_quiet(build_kripke_from_runtime, rt, horizon=8))
    assert rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog",
                             occurred_at=0).outcome == "violation"
    assert rt.declare_breach("useP", "permit", "Ag", "use", "Dog", occurred_at=0,
                             rule_holder="Bo").outcome == "violation"
    assert _shape(_quiet(build_kripke_model, rt._spec, horizon=8)) == static_before
    assert _shape(_quiet(build_kripke_from_runtime, rt, horizon=8)) == hybrid_before


def test_a_state_built_without_records_is_unchanged():
    spec = _spec()
    state = _state(spec)
    assert state.violation_records == ()
    assert replace(state, violation_records=()) == state
