"""
AM-57: live any_discharged sibling supersession in el_engine.py, parity
with el_kripke.py's P6b transition.

Ground truth confirmed before writing this fixture (see AM-57's amendment
entry, docs/el_grammar_amendments.md): el_kripke.py already implements
P6b (SUPERSEDED sibling suppression) for any_discharged TokenGroups in the
pre-execution/hybrid verifier; el_engine.py (Layer 3, the live runtime)
had zero references to SUPERSEDED/any_discharged/TokenGroup anywhere,
confirmed by grep. No currently committed scenario declares
any_discharged either (referral_scenario.el/gp_referral_scenario.el both
use all_discharged), so this fixture is a standalone minimal spec, not a
change to any real scenario file.

Fixture: a two-member any_discharged TokenGroup (probeBurdenGroup:
burdenA, burdenB), each burden backed by its own top-level Commitment (so
a real scenario wouldn't trip V-16a), held by two different actors
(ActorA, ActorB), each dischargeable by its own action (actionA/actionB)
via for_action match — mirrors referral_scenario.el's own discharge
pattern, just minimal.
"""
from el_engine import (
    TokenInstance,
    advance,
    check_live_violations,
    enroll,
    grant_token,
    initial_state,
)
from el_parser import parse_string


_ANY_DISCHARGED_PROBE = """
enterprise specification AnyDischargedSupersessionProbe
    description: "AM-57 unit fixture: two-member any_discharged TokenGroup, two Commitment-backed burdens, two actors"

party ActorA
party ActorB

community ProbeCommunity
    description: "Either actor completing their task satisfies the community"
    {
        objective: "Either actor completing their task satisfies the community"
            satisfaction: any_discharged(probeBurdenGroup)

        role roleA
            description: "ActorA's role"
            {
                action actionA {
                    description: "Discharges burdenA"
                    actor: roleA
                }
            }

        role roleB
            description: "ActorB's role"
            {
                action actionB {
                    description: "Discharges burdenB"
                    actor: roleB
                }
            }
    }

burden burdenA {
    for_action: "actionA"
    state: active
    discharge_mode: eventual
    priority: normal
    description: "ActorA's half of the any_discharged group"
}

burden burdenB {
    for_action: "actionB"
    state: active
    discharge_mode: eventual
    priority: normal
    description: "ActorB's half of the any_discharged group"
}

token_group probeBurdenGroup {
    member: burdenA
    member: burdenB
}

commitment commitmentA {
    by: ActorA
    obligation: "ActorA completes actionA"
    creates_burden: burdenA
}

commitment commitmentB {
    by: ActorB
    obligation: "ActorB completes actionB"
    creates_burden: burdenB
}
"""

# Control fixture (test 4): structurally identical, but all_discharged --
# P6b-equivalent must NOT fire here. Distinct spec/token/actor names to
# avoid any risk of cross-fixture bleed within one test module.
_ALL_DISCHARGED_CONTROL = """
enterprise specification AllDischargedControlProbe
    description: "AM-57 control fixture: all_discharged group must NOT trigger sibling supersession"

party CtrlActorA
party CtrlActorB

community CtrlCommunity
    description: "Both actors must complete their task"
    {
        objective: "Both actors completing their task satisfies the community"
            satisfaction: all_discharged(ctrlBurdenGroup)

        role ctrlRoleA
            description: "CtrlActorA's role"
            {
                action ctrlActionA {
                    description: "Discharges ctrlBurdenA"
                    actor: ctrlRoleA
                }
            }

        role ctrlRoleB
            description: "CtrlActorB's role"
            {
                action ctrlActionB {
                    description: "Discharges ctrlBurdenB"
                    actor: ctrlRoleB
                }
            }
    }

burden ctrlBurdenA {
    for_action: "ctrlActionA"
    state: active
    discharge_mode: eventual
    priority: normal
    description: "CtrlActorA's half of the all_discharged group"
}

burden ctrlBurdenB {
    for_action: "ctrlActionB"
    state: active
    discharge_mode: eventual
    priority: normal
    description: "CtrlActorB's half of the all_discharged group"
}

token_group ctrlBurdenGroup {
    member: ctrlBurdenA
    member: ctrlBurdenB
}

commitment ctrlCommitmentA {
    by: CtrlActorA
    obligation: "CtrlActorA completes ctrlActionA"
    creates_burden: ctrlBurdenA
}

commitment ctrlCommitmentB {
    by: CtrlActorB
    obligation: "CtrlActorB completes ctrlActionB"
    creates_burden: ctrlBurdenB
}
"""


def _parsed(spec_text: str):
    result = parse_string(spec_text, validate=True)
    assert result.ok, result.errors
    return result.model


def _probe_state():
    state = initial_state()
    state = enroll(state, "ActorA", role_name="roleA")
    state = enroll(state, "ActorB", role_name="roleB")
    state = grant_token(state, TokenInstance(
        token_name="burdenA", kind="burden", holder="ActorA",
        state="active", discharge_mode="eventual", priority="normal",
        granted_at_tick=0, deadline=None, for_action="actionA",
    ))
    state = grant_token(state, TokenInstance(
        token_name="burdenB", kind="burden", holder="ActorB",
        state="active", discharge_mode="eventual", priority="normal",
        granted_at_tick=0, deadline=None, for_action="actionB",
    ))
    return state


# ── 1/2. Discharge -> sibling superseded, effects log names both ───────────────

def test_discharge_supersedes_any_discharged_sibling():
    """Actor A discharges burdenA; ActorB's sibling burdenB (a DIFFERENT
    holder, confirming the match is by token_name across all holders, not
    just the discharging actor) transitions to 'superseded', not left
    'active'. The effects log names both the superseded sibling and the
    triggering discharge."""
    spec = _parsed(_ANY_DISCHARGED_PROBE)
    state = _probe_state()

    new_state, record = advance(state, "actionA", spec, "ActorA")

    assert record.outcome == "ok"
    by_name = {t.token_name: t for t in new_state.tokens}
    assert by_name["burdenA"].state == "discharged"
    assert by_name["burdenB"].state == "superseded"
    assert by_name["burdenB"].holder == "ActorB"

    assert record.effects == (
        "discharged burden 'burdenA'",
        "superseded burden 'burdenB' held by 'ActorB' "
        "(sibling 'burdenA' discharged, group 'probeBurdenGroup')",
    )


# ── 3. Superseded sibling invisible to check_live_violations() ─────────────────

def test_superseded_sibling_never_violates_even_past_deadline():
    spec = _parsed(_ANY_DISCHARGED_PROBE)
    state = _probe_state()

    new_state, record = advance(state, "actionA", spec, "ActorA")
    assert record.outcome == "ok"

    # Push the tick far past any plausible deadline_steps for burdenB.
    far_state = new_state.with_tick(new_state.tick + 1000)
    violated_state, vrecord = check_live_violations(far_state, spec)

    by_name = {t.token_name: t for t in violated_state.tokens}
    assert by_name["burdenB"].state == "superseded"  # unchanged, not violated
    assert "burdenB" not in vrecord.violations
    assert vrecord.outcome == "ok"


# ── 4. Control: all_discharged group members unaffected ────────────────────────

def test_all_discharged_group_members_not_superseded():
    """Regression guard: the P6b-equivalent must not fire for an
    all_discharged group -- discharging one member must leave the sibling
    'active', exactly as before AM-57."""
    spec = _parsed(_ALL_DISCHARGED_CONTROL)
    state = initial_state()
    state = enroll(state, "CtrlActorA", role_name="ctrlRoleA")
    state = enroll(state, "CtrlActorB", role_name="ctrlRoleB")
    state = grant_token(state, TokenInstance(
        token_name="ctrlBurdenA", kind="burden", holder="CtrlActorA",
        state="active", discharge_mode="eventual", priority="normal",
        granted_at_tick=0, deadline=None, for_action="ctrlActionA",
    ))
    state = grant_token(state, TokenInstance(
        token_name="ctrlBurdenB", kind="burden", holder="CtrlActorB",
        state="active", discharge_mode="eventual", priority="normal",
        granted_at_tick=0, deadline=None, for_action="ctrlActionB",
    ))

    new_state, record = advance(state, "ctrlActionA", spec, "CtrlActorA")

    assert record.outcome == "ok"
    by_name = {t.token_name: t for t in new_state.tokens}
    assert by_name["ctrlBurdenA"].state == "discharged"
    assert by_name["ctrlBurdenB"].state == "active"  # untouched
    assert record.effects == ("discharged burden 'ctrlBurdenA'",)


# ── 5. Idempotency: already-discharged sibling is left alone ───────────────────

def test_already_discharged_sibling_not_overwritten_to_superseded():
    """If the sibling was already 'discharged' (not 'active') when the
    other member discharges, it must be left alone -- not overwritten to
    'superseded'. The supersession match is scoped to 'active' siblings
    only (see the 7a-cont comment in el_engine.py)."""
    spec = _parsed(_ANY_DISCHARGED_PROBE)
    state = initial_state()
    state = enroll(state, "ActorA", role_name="roleA")
    state = enroll(state, "ActorB", role_name="roleB")
    state = grant_token(state, TokenInstance(
        token_name="burdenA", kind="burden", holder="ActorA",
        state="active", discharge_mode="eventual", priority="normal",
        granted_at_tick=0, deadline=None, for_action="actionA",
    ))
    state = grant_token(state, TokenInstance(
        token_name="burdenB", kind="burden", holder="ActorB",
        state="discharged", discharge_mode="eventual", priority="normal",
        granted_at_tick=0, deadline=None, for_action="actionB",
    ))

    new_state, record = advance(state, "actionA", spec, "ActorA")

    assert record.outcome == "ok"
    by_name = {t.token_name: t for t in new_state.tokens}
    assert by_name["burdenA"].state == "discharged"
    assert by_name["burdenB"].state == "discharged"  # unchanged, not 'superseded'
    assert record.effects == ("discharged burden 'burdenA'",)
