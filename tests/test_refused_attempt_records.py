"""
Layer 3 — refused attempts recorded as violations (2.3.0-8).

When advance() refuses an act at Step 5 (an active embargo held by the
actor covers the action) or Step 6 (a required permit not held), and the
caller sets record_refused_attempts, the refusal is also recorded as a
ViolationRecord with source 'refused_attempt': kind 'embargo' or
'permit_requirement', violator the actor, behaviour the action,
occurred_at = declared_at = the tick, declared_by 'system'. Only
Runtime.advance() sets it; the keyword is off by default, so engine calls
and dry runs record nothing. The reason and blocked_by are unchanged; one
effect line is added. A repeat at the same tick adds no record. No other
refusal is recorded, nor claim(), decline() or a declarer's refusal.
Kripke: absent in both builders (parity R25).
"""
import contextlib
import io
from dataclasses import replace

import el_api
from el_engine import (
    ViolationRecord, advance, enroll, grant_token, initial_state, token_from_spec,
)
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """
enterprise specification RefusedProbe
party Gate
party Dog
party Ag
burden strictB { for_action: "rec" state: active deadline: "5 minutes" discharge_mode: strict }
burden takeB { for_action: "use" state: active deadline: "5 minutes" }
permit declP { for_action: "declUse" state: active }
permit useP { for_action: "use" state: active }
permit bareP { for_action: "bare" state: active }
embargo stopE { for_action: "use" state: active }
embargo guardE { for_action: "guarded" state: active }
community C {
    objective: "o"
    Gate fills gw
    Dog fills dec
    Ag fills user
    role gw { action rec { actor: gw } }
    role dec {
        action declUse {
            actor: dec
            requires_permit declP
            declares_violation_of stopE
            declares_violation_of useP
            declares_violation_of strictB
        }
    }
    role user {
        action use { actor: user requires_permit useP }
        action guarded { actor: user precondition: "ok" }
    }
}
violation_response onStop {
    on_violation_of: stopE
    obligates: Gate
    response_kind: escalate
    escalate_to: Dog
}
violation_response onUse {
    on_violation_of: useP
    obligates: Gate
    response_kind: escalate
    escalate_to: Dog
    also_on_refused_attempts: true
}
"""

_EMBARGO = "active embargo 'stopE' blocks action"
_PERMIT = "required permit 'useP' not held by actor"


def _spec():
    result = _quiet(parse_string, _SPEC, validate=False)
    assert result.ok, result.errors
    return result.model


def _state(spec, *grants, states=None):
    state = initial_state(spec)
    for actor, role in (("Gate", "gw"), ("Dog", "dec"), ("Ag", "user")):
        state = enroll(state, actor, role_name=role)
    for token, holder in grants:
        tok = token_from_spec(spec, token, holder, 0)
        if states and token in states:
            tok = replace(tok, state=states[token])
        state = grant_token(state, tok)
    return state


def _runtime(*grants, states=None):
    spec = _spec()
    return Runtime(_state(spec, *grants, states=states), spec)


# ── Step 5 and Step 6 ────────────────────────────────────────────────────────

def test_an_embargo_refusal_is_recorded():
    rt = _runtime(("stopE", "Ag"), ("useP", "Ag"))
    before = rt.current_state()
    record = rt.advance("use", "Ag")
    assert (record.outcome, record.reason) == ("blocked", _EMBARGO)
    assert record.blocked_by.token_name == "stopE"
    assert record.violation_records == (ViolationRecord(
        rule="stopE", kind="embargo", violator="Ag", behaviour="use", declared_by="system",
        occurred_at=0, declared_at=0, source="refused_attempt", rule_holder="Ag"),)
    assert record.effects == (
        "recorded refused attempt: violation of embargo 'stopE' by 'Ag' in 'use' at step 0",)
    assert record.violations == () and record.token_events == () and record.discharged == ()
    after = rt.current_state()
    assert after.tokens == before.tokens and after.tick == before.tick
    assert after.violation_records == record.violation_records
    assert after.violation_records[0] is record.violation_records[0]
    assert rt.history()[-1] is record


def test_a_permit_never_held_is_recorded_as_a_requirement():
    rt = _runtime()
    record = rt.advance("use", "Ag")
    assert record.reason == _PERMIT
    assert record.violation_records == (ViolationRecord(
        rule="useP", kind="permit_requirement", violator="Ag", behaviour="use",
        declared_by="system", occurred_at=0, declared_at=0, source="refused_attempt",
        rule_holder=None),)
    assert record.effects == (
        "recorded refused attempt: violation of permit requirement 'useP' by 'Ag' in 'use' "
        "at step 0",)


def test_a_permit_held_but_not_active_is_recorded():
    rt = _runtime(("useP", "Ag"), states={"useP": "superseded"})
    record = rt.advance("use", "Ag")
    assert record.reason == _PERMIT
    assert record.blocked_by.state == "superseded"
    assert [r.kind for r in rt.current_state().violation_records] == ["permit_requirement"]


# ── repeats ──────────────────────────────────────────────────────────────────

def test_a_repeat_at_the_same_step_adds_no_record():
    rt = _runtime(("stopE", "Ag"), ("useP", "Ag"))
    rt.advance("use", "Ag")
    again = rt.advance("use", "Ag")
    assert (again.outcome, again.reason) == ("blocked", _EMBARGO)
    assert again.violation_records == ()
    assert again.effects == (
        "refused attempt already recorded: violation of embargo 'stopE' by 'Ag' in 'use' "
        "at step 0",)
    assert len(rt.current_state().violation_records) == 1


def test_a_later_attempt_is_a_new_occurrence():
    rt = _runtime(("stopE", "Ag"), ("useP", "Ag"))
    rt.advance("use", "Ag")
    rt.advance_clock(1)
    record = rt.advance("use", "Ag")
    assert record.violation_records[0].occurred_at == 1
    assert [r.occurred_at for r in rt.current_state().violation_records] == [0, 1]


# ── the keyword ──────────────────────────────────────────────────────────────

def test_the_engine_records_nothing_by_default():
    spec = _spec()
    state = _state(spec, ("stopE", "Ag"), ("useP", "Ag"))
    new_state, record = advance(state, "use", spec, "Ag")
    assert new_state is state
    assert record.violation_records == () and record.effects == ()
    assert record.reason == _EMBARGO


def test_the_engine_records_when_asked():
    spec = _spec()
    state = _state(spec, ("stopE", "Ag"), ("useP", "Ag"))
    new_state, record = advance(state, "use", spec, "Ag", record_refused_attempts=True)
    assert new_state.violation_records == record.violation_records
    assert new_state.tokens == state.tokens and new_state.tick == state.tick


# ── no record ────────────────────────────────────────────────────────────────

def test_other_refusals_are_not_recorded():
    rt = _runtime(("stopE", "Ag"), ("useP", "Ag"))
    assert "not enrolled" in rt.advance("use", "Zed").reason          # Step 2
    assert rt.advance("use", "Gate").outcome == "blocked"             # role
    assert rt.advance("declUse", "Dog").outcome == "blocked"          # a declaration
    assert rt.current_state().violation_records == ()


def test_a_strict_freeze_refusal_is_not_recorded():
    rt = _runtime(("strictB", "Gate"), ("stopE", "Ag"), ("useP", "Ag"))
    record = rt.advance("use", "Ag")                                  # Step 3.5 first
    assert record.outcome == "blocked" and "strictB" in record.reason
    assert rt.current_state().violation_records == ()


def test_an_embargoed_act_refused_by_its_precondition_is_not_recorded():
    rt = _runtime(("guardE", "Ag"))
    record = rt.advance("guarded", "Ag")                              # Step 4 first
    assert record.outcome == "blocked" and "guardE" not in record.reason
    assert rt.current_state().violation_records == ()
    record = rt.advance("guarded", "Ag", facts={"ok": True})         # then Step 5
    assert record.reason == "active embargo 'guardE' blocks action"
    assert len(rt.current_state().violation_records) == 1


def test_an_undeclared_action_needs_no_permit_and_records_nothing():
    # Step 6 applies only to declared actions (open finding).
    rt = _runtime()
    assert rt.advance("bare", "Ag").outcome == "ok"
    assert rt.current_state().violation_records == ()


def test_claim_and_decline_record_nothing():
    for method in ("claim", "decline"):
        rt = _runtime(("takeB", "Ag"), ("stopE", "Ag"), ("useP", "Ag"),
                      states={"takeB": "claimable"})
        record = getattr(rt, method)("takeB", "Ag")
        assert (record.outcome, record.reason) == ("blocked", _EMBARGO)
        assert record.violation_records == () and record.effects == ()
        assert rt.current_state().violation_records == ()


def test_a_declarers_refusal_is_not_recorded():
    rt = _runtime(("stopE", "Ag"))                                    # Dog lacks declP
    record = rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    assert record.reason == "required permit 'declP' not held by actor"
    record = rt.declare_violation("strictB", "Dog", at_tick=0)
    assert record.outcome == "blocked"
    assert rt.current_state().violation_records == ()


# ── declarations and responses ───────────────────────────────────────────────

def test_a_declaration_confirms_the_recorded_attempt():
    rt = _runtime(("declP", "Dog"), ("stopE", "Ag"), ("useP", "Ag"))
    rt.advance("use", "Ag")
    record = rt.declare_breach("stopE", "embargo", "Ag", "use", "Dog", occurred_at=0)
    assert record.outcome == "violation"
    assert record.effects[-1] == "confirms the refused attempt recorded at step 0"
    assert [r.source for r in rt.current_state().violation_records] == [
        "refused_attempt", "declared"]


def test_responses_fire_on_refused_attempts_only_with_the_flag():
    rt = _runtime(("stopE", "Ag"))
    rt.advance("use", "Ag")                       # Step 5: stopE (onStop, no flag)
    rt.advance("use", "Ag")                       # a repeat
    assert rt.fire_violation_responses().fired_responses == ()
    rt = _runtime()
    rt.advance("use", "Ag")                       # Step 6: useP (onUse, flagged)
    record = rt.fire_violation_responses()
    assert record.fired_responses == ("onUse",)
    assert record.effects[0] == (
        "fired 'onUse' (escalate) on violation of permit requirement 'useP' by 'Ag' in "
        "'use' at step 0")
    assert rt.fire_violation_responses().fired_responses == ()


# ── API and verifier ─────────────────────────────────────────────────────────

def test_execute_action_shows_the_effect_line(monkeypatch):
    rt = _runtime(("stopE", "Ag"), ("useP", "Ag"))
    monkeypatch.setattr(el_api, "_runtime", rt)
    monkeypatch.setattr(el_api, "_active_community", "C")
    response = _quiet(el_api.execute_action, "Ag",
                      el_api.ExecuteActionRequest(action_name="use"))
    assert (response.outcome, response.reason) == ("blocked", _EMBARGO)
    assert response.effects == [
        "recorded refused attempt: violation of embargo 'stopE' by 'Ag' in 'use' at step 0"]
    assert len(rt.current_state().violation_records) == 1


def _shape(km):
    return (len(km.worlds), sum(len(km.successors(w)) for w in km.worlds),
            sorted(map(str, km.initial.obligation_states)))


def test_the_verifier_is_unchanged_by_a_refused_attempt():
    spec = _spec()
    static = _shape(_quiet(build_kripke_model, spec, horizon=6))
    rt = _runtime(("stopE", "Ag"), ("useP", "Ag"), ("takeB", "Ag"))
    hybrid_before = _shape(_quiet(build_kripke_from_runtime, rt, horizon=6))
    rt.advance("use", "Ag")
    assert rt.current_state().violation_records
    assert _shape(_quiet(build_kripke_from_runtime, rt, horizon=6)) == hybrid_before
    assert _shape(_quiet(build_kripke_model, spec, horizon=6)) == static
