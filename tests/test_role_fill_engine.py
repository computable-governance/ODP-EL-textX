"""
Layer 3 — 2.4.0-3: an action fills a role (`effect fill <Role> with <Object>`).

advance() checks every fill of the act at Step 6b, after the embargo and
permit checks, and refuses the whole act on the first failure (§7.8.2: at
most one object fills a role at a time, no refill; NOTE 5: excludes_role
both ways from the roles' assignment_policy; the role is declared in one
community). A refusal leaves state and tick unchanged, with blocked_by None
and no refused-attempt record. Then, before Step 7a, each fill runs through
join_role() in declared order: the filler is enrolled in the role and the
role's on_join tokens are granted in their declared state at the act's tick
(§7.6.2, §7.8.7 NOTE 3). The rest of Step 7 resolves roles against the new
fillers.
"""
import contextlib
import io
from dataclasses import replace

from el_engine import advance, grant_token, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_FILL_A = "            effect fill contractorRole with SupplierA"


def _src(award_body=_FILL_A, tokens="", fills="", community_extra="",
         buyer_extra="", second_community=""):
    return f"""
enterprise specification RoleFillEngine

permit awardPermit {{ state: active }}
embargo awardEmbargo {{ state: pending }}
burden incidentBurden {{ for_action: "notify" state: active deadline: "1 day" }}
burden coverBurden {{ state: pending }}
burden startBurden {{ state: pending triggered_by: awarded }}
burden handoverBurden {{ state: active }}
{tokens}
party Buyer {{ holds awardPermit holds awardEmbargo }}
party SupplierA
party SupplierB
party Auditor

community C {{
    objective: "probe"
    event awarded
{community_extra}
    on_join contractorRole transfer incidentBurden
    on_join contractorRole transfer coverBurden
    on_join contractorRole transfer startBurden
    Buyer fills buyerRole
{fills}
    role buyerRole {{
        action award {{
            actor: buyerRole
            requires_permit awardPermit
{award_body}
        }}
{buyer_extra}
    }}
    role contractorRole {{
        action notify {{
            actor: contractorRole
        }}
    }}
    role auditorRole {{
        action audit {{
            actor: auditorRole
        }}
    }}
}}
{second_community}
"""


def _spec(**kwargs):
    result = _quiet(parse_string, _src(**kwargs), validate=False)
    assert result.ok, result.errors
    return result.model


def _runtime(**kwargs):
    return Runtime.build_from_spec(_spec(**kwargs))


def _tokens(state, holder):
    return {t.token_name: t for t in state.tokens if t.holder == holder}


def _fills(state, role):
    return [a.actor_name for a in state.actors if a.role_name == role]


def _award(rt, facts=None):
    return rt.advance("award", "Buyer", facts)


# ── The fill is applied ────────────────────────────────────────────────────

def test_the_filler_is_enrolled_and_may_then_perform_the_roles_actions():
    rt = _runtime()
    refused = rt.advance("notify", "SupplierA")
    assert refused.outcome == "blocked"
    assert "does not fill role 'contractorRole'" in refused.reason
    record = _award(rt)
    assert record.outcome == "ok", record.reason
    assert _fills(rt.current_state(), "contractorRole") == ["SupplierA"]
    done = rt.advance("notify", "SupplierA")
    assert done.outcome == "ok", done.reason
    assert done.discharged == ("incidentBurden",)


def test_on_join_tokens_are_granted_in_their_declared_state_at_the_fill_tick():
    rt = _runtime()
    tick = rt.current_state().tick
    _award(rt)
    held = _tokens(rt.current_state(), "SupplierA")
    assert held["incidentBurden"].state == "active"
    assert held["coverBurden"].state == "pending"
    assert {t.granted_at_tick for t in held.values()} == {tick}


def test_token_events_name_the_on_join_cause_the_role_and_the_actor():
    rt = _runtime()
    record = _award(rt)
    events = {e.token_name: e for e in record.token_events if e.holder == "SupplierA"}
    assert set(events) == {"incidentBurden", "coverBurden", "startBurden"}
    for e in events.values():
        assert (e.event, e.cause, e.cause_ref, e.by) == (
            "granted", "on_join", "contractorRole", "Buyer")


def test_the_record_lines_and_the_tick():
    rt = _runtime()
    tick = rt.current_state().tick
    record = _award(rt)
    assert record.effects == (
        "filled role 'contractorRole' with 'SupplierA'",
        "on_join 'contractorRole': granted 'incidentBurden' to 'SupplierA'",
        "on_join 'contractorRole': granted 'coverBurden' to 'SupplierA'",
        "on_join 'contractorRole': granted 'startBurden' to 'SupplierA'",
    )
    assert record.tick == tick
    assert rt.current_state().tick == tick + 1


def test_an_on_join_token_triggered_by_the_acts_event_is_activated_in_the_same_act():
    rt = _runtime(award_body=_FILL_A + "\n            emits: awarded")
    record = _award(rt)
    assert record.outcome == "ok", record.reason
    assert _tokens(rt.current_state(), "SupplierA")["startBurden"].state == "active"
    assert record.effects[0] == "filled role 'contractorRole' with 'SupplierA'"
    assert [e.event for e in record.token_events if e.token_name == "startBurden"] == ["granted"]


def test_effect_create_to_the_role_in_the_same_act_grants_to_the_new_filler():
    rt = _runtime(award_body=_FILL_A + "\n            effect create handoverBurden to contractorRole")
    record = _award(rt)
    assert record.outcome == "ok", record.reason
    assert "created 'handoverBurden' for 'SupplierA'" in record.effects
    assert _tokens(rt.current_state(), "SupplierA")["handoverBurden"].state == "active"
    assert not [t for t in rt.current_state().tokens if t.holder == "contractorRole"]


# ── Refused at Step 6b: state and tick unchanged ───────────────────────────

def _assert_refused_at_6b(rt, reason):
    before = rt.current_state()
    record = _award(rt)
    assert record.outcome == "blocked"
    assert record.reason == reason
    assert record.blocked_by is None
    assert record.effects == () and record.token_events == ()
    assert rt.current_state() == before
    assert rt.current_state().violation_records == ()


def test_the_same_filler_again_is_refused():
    rt = _runtime()
    assert _award(rt).outcome == "ok"
    _assert_refused_at_6b(rt, "'SupplierA' already fills role 'contractorRole'")


def test_another_filler_by_an_earlier_fill_is_refused():
    rt = _runtime(buyer_extra="""        action awardB {
            actor: buyerRole
            effect fill contractorRole with SupplierB
        }""")
    assert rt.advance("awardB", "Buyer").outcome == "ok"
    _assert_refused_at_6b(rt, "role 'contractorRole' is already filled by 'SupplierB'")


def test_a_filler_stated_by_spec_fills_is_refused():
    rt = _runtime(fills="    SupplierB fills contractorRole")
    _assert_refused_at_6b(rt, "role 'contractorRole' is already filled by 'SupplierB'")


def test_a_role_the_new_roles_assignment_policy_excludes_is_refused():
    rt = _runtime(fills="    SupplierA fills auditorRole", community_extra="""
    assignment_policy for contractorRole {
        excludes_role auditorRole
    }""")
    _assert_refused_at_6b(
        rt, "'SupplierA' fills 'auditorRole', which the assignment policy of "
            "'contractorRole' excludes")


def test_a_role_whose_assignment_policy_excludes_the_new_role_is_refused():
    rt = _runtime(fills="    SupplierA fills auditorRole", community_extra="""
    assignment_policy for auditorRole {
        excludes_role contractorRole
    }""")
    _assert_refused_at_6b(
        rt, "'SupplierA' fills 'auditorRole', whose assignment policy excludes "
            "'contractorRole'")


def test_a_role_declared_in_two_communities_is_refused():
    # The parser refuses an ambiguous `effect fill` role reference, so the
    # second declaration is made on the parsed specification.
    spec = _spec(second_community="""
community D {
    objective: "second"
    role otherRole {
        action deliver {
            actor: otherRole
        }
    }
}""")
    d = next(e for e in spec.elements if getattr(e, "name", None) == "D")
    d.roles[0].name = "contractorRole"
    rt = Runtime.build_from_spec(spec)
    _assert_refused_at_6b(
        rt, "role 'contractorRole' is declared in more than one community ('C', 'D')")


def test_two_fill_lines_are_applied_together_or_not_at_all():
    two = _FILL_A + "\n            effect fill auditorRole with SupplierA"
    rt = _runtime(award_body=two)
    assert _award(rt).outcome == "ok"
    assert _fills(rt.current_state(), "contractorRole") == ["SupplierA"]
    assert _fills(rt.current_state(), "auditorRole") == ["SupplierA"]

    refused = _runtime(award_body=two, community_extra="""
    assignment_policy for auditorRole {
        excludes_role contractorRole
    }""")
    _assert_refused_at_6b(
        refused, "'SupplierA' fills 'contractorRole', which the assignment policy "
                 "of 'auditorRole' excludes")
    assert _fills(refused.current_state(), "contractorRole") == []
    assert _tokens(refused.current_state(), "SupplierA") == {}


# ── Earlier steps refuse first ─────────────────────────────────────────────

def test_a_missing_permit_is_refused_at_step_6_with_a_refused_attempt_record():
    rt = _runtime(fills="    SupplierB fills contractorRole")
    rt._state = rt.current_state().with_tokens(
        [t for t in rt.current_state().tokens if t.token_name != "awardPermit"])
    record = _award(rt)
    assert record.reason == "required permit 'awardPermit' not held by actor"
    assert record.blocked_by is not None
    assert [v.kind for v in rt.current_state().violation_records] == ["permit_requirement"]
    assert _fills(rt.current_state(), "contractorRole") == ["SupplierB"]


def test_an_active_embargo_is_refused_at_step_5_first():
    rt = _runtime(fills="    SupplierB fills contractorRole")
    rt._state = rt.current_state().with_tokens(
        [replace(t, state="active") if t.token_name == "awardEmbargo" else t
         for t in rt.current_state().tokens])
    record = _award(rt)
    assert record.reason == "active embargo 'awardEmbargo' blocks action"
    assert record.blocked_by.token_name == "awardEmbargo"


def test_a_precondition_is_refused_at_step_4_first():
    rt = _runtime(award_body=_FILL_A + '\n            precondition: "bid evaluated"',
                  fills="    SupplierB fills contractorRole")
    record = _award(rt)
    assert record.reason.startswith("precondition not")
    assert record.blocked_by is None


def test_the_strict_guard_refuses_a_fill_that_discharges_nothing():
    strict = 'burden reviewBurden { for_action: "audit" state: active discharge_mode: strict }'
    spec = _spec(tokens=strict, award_body=_FILL_A + "\n            effect destroy handoverBurden")
    rt = Runtime.build_from_spec(spec)
    rt._state = grant_token(rt.current_state(), token_from_spec(spec, "reviewBurden", "Buyer", 0))
    record = _award(rt)
    assert record.outcome == "blocked"
    assert "must be discharged before this action can proceed" in record.reason
    assert _fills(rt.current_state(), "contractorRole") == []

    rt._state = grant_token(rt.current_state(), token_from_spec(spec, "handoverBurden", "Buyer", 0))
    record = _award(rt)
    assert record.outcome == "ok", record.reason
    assert record.discharged == ("handoverBurden",)
    assert _fills(rt.current_state(), "contractorRole") == ["SupplierA"]


# ── claim() and acts without fills ─────────────────────────────────────────

def test_claim_of_a_burden_whose_action_fills_a_role_fills_at_the_claim():
    spec = _spec(tokens='burden awardBurden { for_action: "award" state: claimable }')
    rt = Runtime.build_from_spec(spec)
    rt._state = grant_token(rt.current_state(), token_from_spec(spec, "awardBurden", "Buyer", 0))
    record = rt.claim("awardBurden", "Buyer")
    assert record.outcome == "ok", record.reason
    assert "claimed burden 'awardBurden'" in record.effects
    assert "filled role 'contractorRole' with 'SupplierA'" in record.effects
    assert _fills(rt.current_state(), "contractorRole") == ["SupplierA"]


def test_an_act_without_fills_is_unchanged():
    spec = _spec(award_body="            effect create handoverBurden to contractorRole",
                 fills="    SupplierB fills contractorRole")
    state = Runtime.build_from_spec(spec).current_state()
    new_state, record = advance(state, "award", spec, "Buyer")
    assert record.effects == ("created 'handoverBurden' for 'SupplierB'",)
    assert [(e.event, e.token_name, e.holder, e.by, e.cause, e.cause_ref)
            for e in record.token_events] == [
        ("granted", "handoverBurden", "SupplierB", "Buyer", "action", "award")]
    assert new_state.actors == state.actors
    assert new_state == state.with_tokens(new_state.tokens).with_tick(state.tick + 1)
    assert new_state.tokens[:-1] == state.tokens
