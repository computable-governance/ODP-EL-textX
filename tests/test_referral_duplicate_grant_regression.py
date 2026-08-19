"""
Layer 4 — regression test for the duplicate-grant bug (docs/CONCEPTS_INDEX.md,
"Double role-enrollment bug (GET /actors/SpecialistClinician/available-actions)
— actually a double-grant, root cause traced to yesterday's paused delegation
finding, fixed 2026-08-20").

Before the fix, referralResponseBurden/assessmentSchedulingBurden were
granted twice to SpecialistClinician: once by the scenario builder's
pre-seed (_build_referral_runtime / _build_gp_referral_runtime) and again
by initiateReferral's grammar `create` effect, which appended a fresh
TokenInstance unconditionally on every fire with no check for an existing
same-name/holder token. The fix added an idempotency guard to el_engine.py's
`create` effect handler (skip if the target already holds a token of that
name) and, as defense-in-depth, a first-occurrence-wins dedupe in
el_api.py's get_available_actions().

referral_scenario.el: both burdens' pre-seed holder matches the create
effect's resolved holder (SpecialistClinician via referredToRole) exactly
-- the guard fully suppresses the duplicate for both.

gp_referral_scenario.el: only referralResponseBurden's pre-seed holder
matches (SpecialistClinician via specialistRole). assessmentSchedulingBurden's
pre-seed holder (SpecialistParty) does NOT match the create effect's
resolved holder (SpecialistClinician) -- a separate, still-open
wrong-pre-seed-holder bug (logged in the same finding, not fixed here).
The guard must not touch this case: two distinct-holder tokens are
correct, not a duplicate.
"""
from el_api import _build_gp_referral_runtime, _build_referral_runtime, get_available_actions
import el_api

FACTS = {"Patient must have an active episode of care and clinical indication for referral": True}


def _tokens(state, name, holder=None):
    return [
        t for t in state.tokens
        if t.token_name == name and (holder is None or t.holder == holder)
    ]


def test_referral_response_burden_not_duplicated_in_referral_scenario():
    rt = _build_referral_runtime()
    record = rt.advance("initiateReferral", "GPClinician", FACTS)

    assert record.outcome == "ok"
    assert "created 'referralResponseBurden' for 'SpecialistClinician'" not in record.effects
    tokens = _tokens(rt.current_state(), "referralResponseBurden")
    assert len(tokens) == 1
    assert tokens[0].holder == "SpecialistClinician"


def test_assessment_scheduling_burden_not_duplicated_in_referral_scenario():
    rt = _build_referral_runtime()
    record = rt.advance("initiateReferral", "GPClinician", FACTS)

    assert record.outcome == "ok"
    assert "created 'assessmentSchedulingBurden' for 'SpecialistClinician'" not in record.effects
    assert len(_tokens(rt.current_state(), "assessmentSchedulingBurden")) == 1


def test_available_actions_not_duplicated_after_initiate_referral():
    el_api._runtime = _build_referral_runtime()
    el_api._runtime.advance("initiateReferral", "GPClinician", FACTS)

    resp = get_available_actions("SpecialistClinician")
    actions = [a.action for a in resp.available_actions]

    assert actions.count("acknowledgeReferral") == 1
    assert actions.count("scheduleAssessment") == 1


def test_gp_referral_response_burden_not_duplicated():
    rt = _build_gp_referral_runtime()
    record = rt.advance("initiateReferral", "GPClinician", FACTS)

    assert record.outcome == "ok"
    assert "created 'referralResponseBurden' for 'SpecialistClinician'" not in record.effects
    assert len(_tokens(rt.current_state(), "referralResponseBurden")) == 1


def test_gp_referral_assessment_scheduling_burden_guard_does_not_overreach():
    """Regression guard for the fix itself, not the still-open wrong-holder
    bug: the two assessmentSchedulingBurden instances here have different
    holders (SpecialistParty from the pre-seed, SpecialistClinician from
    the create effect), so the idempotency guard must leave both in place.
    If this ever collapses to one token, the guard has started matching on
    something looser than (token_name, holder) and is now over-suppressing."""
    rt = _build_gp_referral_runtime()
    record = rt.advance("initiateReferral", "GPClinician", FACTS)

    assert record.outcome == "ok"
    assert "created 'assessmentSchedulingBurden' for 'SpecialistClinician'" in record.effects
    tokens = _tokens(rt.current_state(), "assessmentSchedulingBurden")
    assert {t.holder for t in tokens} == {"SpecialistParty", "SpecialistClinician"}
