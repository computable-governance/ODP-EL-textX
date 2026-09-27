"""
AM-115 — el_engine.declare_violation() and the response changes it pairs
with (inline fixture; the terms-of-engagement scenarios are in
test_am115_terms_of_engagement.py).

declare_violation(state, spec, burden, declarer, at_tick): an authorised
declaration (§6.6.5) that an overdue strict burden is violated.
  - Authorisation: the declarer passes, for an Action carrying
    `declares_violation_of burden`, advance()'s role (AM-114), precondition,
    embargo and permit checks (§7.10.4).
  - Prohibitions, refused: before the deadline (judged at the declarer's
    wall-clock step at_tick, not WorldState.tick); a burden the declarer
    holds; anything but active -> violated.
  - No strict guard (it ends a Step 3.5 freeze); tick + 1; no response
    fired; advance() refuses declaration Actions.
fire_violation_responses(): creates_burden_for_role grants to the role's
fillers; revokes revokes exactly the listed Authorizations.
"""
import pytest

from el_engine import (
    _build_obligation_descriptors,
    declare_violation,
    grant_token,
    token_from_spec,
)
from el_parser import parse_string
from el_runtime import Runtime


_SPEC = """
enterprise specification DeclareProbe
party Org
agent Gate {{ delegated_from Org }}
agent Dog {{ delegated_from Org }}
party Mgr
agent Ag
burden recB {{
    for_action: "rec"
    state: active
    {rec_deadline}
    discharge_mode: strict
}}
burden loneB {{
    for_action: "rec"
    state: active
    deadline: "5 minutes"
    discharge_mode: strict
}}
burden invB {{
    for_action: "inv"
    state: active
    deadline: "1 day"
}}
permit declP {{
    for_action: "declRec"
    state: active
}}
permit useP {{
    for_action: "use"
    state: active
}}
embargo outE {{
    for_action: "use"
    state: pending
}}
embargo declE {{
    for_action: "declRec"
    state: active
}}
community C {{
    objective: "o"
    Gate fills gw
    Dog fills dec
    {inv_filler}
    Ag fills user
    role gw {{ action rec {{ actor: gw }} }}
    role dec {{
        action declRec {{
            actor: dec
            requires_permit declP
            declares_violation_of recB
            {decl_extra}
        }}
    }}
    role inv {{ action inv {{ actor: inv favoured_by_burden invB }} }}
    role user {{ action use {{ actor: user requires_permit useP }} }}
}}
authorization UseAuth {{
    authority: Org
    to_agent: Ag
    grants_permit: useP
    revocable: true
    on_revocation: activate outE
}}
authorization DeclAuth {{
    authority: Org
    to_agent: Dog
    grants_permit: declP
}}
commitment GateRecords {{
    by: Gate
    obligation: "record"
    creates_burden: recB
    principals_obligated: Gate
}}
violation_response R {{
    on_violation_of: recB
    obligates: Org
    response_kind: {kind}
    creates_burden: invB
    creates_burden_for_role: inv
    revokes: UseAuth
}}
"""


def _spec(**over):
    params = dict(rec_deadline='deadline: "5 minutes"', inv_filler="Mgr fills inv",
                  decl_extra="", kind="remediate")
    params.update(over)
    result = parse_string(_SPEC.format(**params))
    assert result.model is not None, result.errors
    return result.model


def _runtime(spec=None, grants=(("recB", "Gate"), ("declP", "Dog"), ("useP", "Ag"))):
    spec = spec or _spec()
    rt = Runtime.build_from_spec(spec)
    state = rt.current_state()
    for token, holder in grants:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    return Runtime(state, spec)


def _states(rt, token):
    return sorted((t.holder, t.state) for t in rt.current_state().tokens if t.token_name == token)


# ── The freeze and its end ───────────────────────────────────────────────────

def test_declaration_ends_the_freeze():
    rt = _runtime()
    assert rt.advance("use", "Ag").outcome == "blocked"
    assert rt.advance_clock(10).outcome == "blocked"

    tick = rt.current_state().tick
    rec = rt.declare_violation("recB", "Dog", at_tick=5)
    assert rec.outcome == "violation"
    assert rec.actor_name == "Dog" and rec.action_name == "declRec"
    assert rec.violations == ("recB",) and rec.discharged == ()
    assert rec.effects == ("declared 'recB' held by 'Gate' violated "
                           "(elapsed 5 >= deadline 5 steps at step 5)",)
    assert rec.fired_responses == ()
    assert rt.current_state().tick == tick + 1            # never jumps to at_tick
    assert _states(rt, "recB") == [("Gate", "violated")]
    assert _states(rt, "invB") == []                      # no response fired yet

    assert rt.advance("use", "Ag").outcome == "ok"
    assert rt.advance_clock(10).outcome == "ok"
    assert rec in rt.accountability_chain("recB")


def test_declaration_is_judged_at_the_declarers_step_not_the_frozen_tick():
    rt = _runtime()
    rec = rt.declare_violation("recB", "Dog", at_tick=4)
    assert rec.outcome == "blocked"
    assert rec.reason == "'recB' is not overdue: 4 of 5 steps elapsed at step 4"
    assert rt.current_state().tick == 0
    assert _states(rt, "recB") == [("Gate", "active")]
    assert rt.declare_violation("recB", "Dog", at_tick=1000).outcome == "violation"


def test_declaration_counts_from_activation():
    spec = _spec()
    state = Runtime.build_from_spec(spec).current_state()
    tok = token_from_spec(spec, "recB", "Gate", 0)
    from dataclasses import replace
    state = grant_token(state, replace(tok, activated_at_tick=3))
    state = grant_token(state, token_from_spec(spec, "declP", "Dog", 0))
    _, rec = declare_violation(state, spec, "recB", "Dog", at_tick=7)
    assert rec.outcome == "blocked" and "4 of 5 steps" in rec.reason
    _, rec = declare_violation(state, spec, "recB", "Dog", at_tick=8)
    assert rec.outcome == "violation"


# ── Authorisation ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("declarer,fragment", [
    ("Ag", "does not fill role 'dec'"),
    ("Mgr", "does not fill role 'dec'"),
    ("Gate", "does not fill role 'dec'"),
    ("Org", "does not fill role 'dec'"),
    ("Nobody", "actor 'Nobody' is not enrolled"),
])
def test_unauthorised_declarers_are_refused(declarer, fragment):
    rt = _runtime()
    rec = rt.declare_violation("recB", declarer, at_tick=100)
    assert rec.outcome == "blocked" and fragment in rec.reason
    assert _states(rt, "recB") == [("Gate", "active")]
    assert rt.advance("use", "Ag").outcome == "blocked"   # freeze holds


def test_declarer_without_permit_is_refused():
    rt = _runtime(grants=(("recB", "Gate"), ("useP", "Ag")))
    rec = rt.declare_violation("recB", "Dog", at_tick=100)
    assert rec.outcome == "blocked"
    assert rec.reason == "required permit 'declP' not held by actor"


def test_embargo_covering_the_declaration_blocks_it():
    rt = _runtime(grants=(("recB", "Gate"), ("declP", "Dog"), ("declE", "Dog")))
    rec = rt.declare_violation("recB", "Dog", at_tick=100)
    assert rec.outcome == "blocked" and rec.reason == "active embargo 'declE' blocks action"


def test_precondition_is_fail_safe():
    spec = _spec(decl_extra='precondition: "watchdog healthy"')
    rt = _runtime(spec)
    rec = rt.declare_violation("recB", "Dog", at_tick=100)
    assert rec.outcome == "blocked"
    assert rec.reason == "precondition not satisfied: 'watchdog healthy'"
    rec = rt.declare_violation("recB", "Dog", at_tick=100, facts={"watchdog healthy": True})
    assert rec.outcome == "violation"


def test_no_declaration_action_for_the_burden():
    rt = _runtime(grants=(("loneB", "Gate"), ("declP", "Dog")))
    rec = rt.declare_violation("loneB", "Dog", at_tick=100)
    assert rec.outcome == "blocked"
    assert rec.reason == "no action declares 'loneB' violated (declares_violation_of)"


def test_undeclared_or_non_burden_token_raises():
    rt = _runtime()
    with pytest.raises(KeyError):
        rt.declare_violation("noSuchBurden", "Dog", at_tick=100)
    with pytest.raises(KeyError):
        rt.declare_violation("useP", "Dog", at_tick=100)


# ── Prohibitions ─────────────────────────────────────────────────────────────

def test_declarer_may_not_declare_a_burden_it_holds():
    rt = _runtime(grants=(("recB", "Dog"), ("declP", "Dog")))
    rec = rt.declare_violation("recB", "Dog", at_tick=100)
    assert rec.outcome == "blocked"
    assert rec.reason == "'Dog' holds 'recB' and may not declare it violated"
    assert _states(rt, "recB") == [("Dog", "active")]


def test_only_active_becomes_violated():
    rt = _runtime()
    assert rt.declare_violation("recB", "Dog", at_tick=5).outcome == "violation"
    rec = rt.declare_violation("recB", "Dog", at_tick=6)
    assert rec.outcome == "blocked"
    assert "no active instance (violated)" in rec.reason

    rt = _runtime()
    assert rt.advance("rec", "Gate").outcome == "ok"      # discharged by its holder
    rec = rt.declare_violation("recB", "Dog", at_tick=100)
    assert rec.outcome == "blocked" and "no active instance (discharged)" in rec.reason
    assert _states(rt, "recB") == [("Gate", "discharged")]

    rt = _runtime(grants=(("declP", "Dog"),))
    rec = rt.declare_violation("recB", "Dog", at_tick=100)
    assert rec.outcome == "blocked" and "(never granted)" in rec.reason


def test_no_deadline_magnitude_is_refused():
    rt = _runtime(_spec(rec_deadline=""))
    rec = rt.declare_violation("recB", "Dog", at_tick=10_000)
    assert rec.outcome == "blocked"
    assert rec.reason == ("'recB' has no deadline with an elapsed-time magnitude "
                          "to judge against")


def test_advance_refuses_the_declaration_action():
    rt = _runtime()
    rec = rt.advance("declRec", "Dog")
    assert rec.outcome == "blocked"
    assert rec.reason == "action 'declRec' is a declaration; make it through declare_violation()"


def test_check_live_violations_still_never_violates_strict():
    rt = _runtime()
    rt.check_live_violations()
    assert _states(rt, "recB") == [("Gate", "active")]


# ── Responses: role target and revokes ───────────────────────────────────────

def test_response_grants_role_filler_and_revokes_listed_authorization():
    rt = _runtime()
    rt.declare_violation("recB", "Dog", at_tick=5)
    rec = rt.fire_violation_responses()
    assert rec.fired_responses == ("R",)
    assert rec.effects == (
        "fired 'R': granted 'invB' to 'Mgr'",
        "fired 'R' (remediate) on violation of 'recB' by 'Gate'",
        "revoked 'UseAuth' (to 'Ag')",
        "  superseded permit 'useP'",
        "  activated embargo 'outE'",
    )
    assert _states(rt, "invB") == [("Mgr", "active")]
    assert _states(rt, "useP") == [("Ag", "superseded")]
    assert _states(rt, "outE") == [("Ag", "active")]
    assert rt.advance("use", "Ag").outcome == "blocked"   # access suspended
    assert rt.fire_violation_responses().fired_responses == ()   # once only (AM-104)


def test_response_role_with_no_filler_grants_nothing():
    rt = _runtime(_spec(inv_filler=""))
    rt.declare_violation("recB", "Dog", at_tick=5)
    rec = rt.fire_violation_responses()
    assert rec.fired_responses == ("R",)
    assert "fired 'R': no actor fills role 'inv'; 'invB' not granted" in rec.effects
    assert _states(rt, "invB") == []


def test_terminate_with_revokes_revokes_only_the_list():
    rt = _runtime(_spec(kind="terminate"))
    rt.declare_violation("recB", "Dog", at_tick=5)
    rec = rt.fire_violation_responses()
    revoked = [e for e in rec.effects if e.startswith("revoked") or e.startswith("not revoked")]
    assert revoked == ["revoked 'UseAuth' (to 'Ag')"]


def test_descriptor_holder_is_the_role_filler():
    descriptors = _build_obligation_descriptors(_spec())
    assert descriptors["invB"].holder == "Mgr"
    assert "invB" not in _build_obligation_descriptors(_spec(inv_filler=""))


def test_w27_silent_for_role_targeted_burden():
    result = parse_string(_SPEC.format(rec_deadline='deadline: "5 minutes"',
                                       inv_filler="Mgr fills inv", decl_extra="",
                                       kind="remediate"))
    assert not [w for w in result.warnings if w.startswith("[W-27]") and "invB" in w]
