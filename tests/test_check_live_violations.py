"""
Layer 3 — el_engine.check_live_violations().

Closes the live-detection gap logged in docs/CONCEPTS_INDEX.md ("Live
violation triggering — detection mechanism exists and is tested; wiring to
on_violation_of effects is the actual gap", corrected same day 2026-08-20):
before this function, the only deadline→VIOLATED logic anywhere in the
codebase lived inside el_kripke.py's BFS world-expansion, walking the
verifier's own hypothetical `step` counter with no connection to a live
WorldState.tick. check_live_violations() is tick-based (the finding's first
open design question) and an explicit call, not something advance() invokes
automatically (the finding's second open design question).

Also the first test to exercise TransitionRecord.outcome == 'violation' —
documented as a valid value since TransitionRecord's own docstring was
written, but never produced by any code path until now (same finding).

Minimal inline spec via parse_string(), same throwaway-probe pattern as
tests/test_t6_examine_embargo_guard.py / test_v17_burden_embargo_conflict.py.
"deadline: "1 hour"" parses to 5 steps via _parse_deadline_steps — chosen
for a small, exact elapsed-vs-deadline boundary to assert on. Both burdens
are wired through a real Commitment (`by: Holder`), matching Tier 1 of the
two-tier deadline lookup — the same Commitment-derived path
referralResponseBurden/assessmentSchedulingBurden use in the real
scenarios (see docs/CONCEPTS_INDEX.md's double-grant/pre-seed finding for
why that path matters, not just the bare-string fallback).
"""
from el_engine import _transition, check_live_violations
from el_parser import parse_string
from el_runtime import Runtime


_PROBE = """
enterprise specification CheckLiveViolationsProbe

party Holder {
    holds eventualBurden
    holds strictBurden
    holds episodeScopedBurden
    holds bareEpisodeScopedBurden
}

burden eventualBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden strictBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: strict
}

// No genuine elapsed-time magnitude in this deadline string (no digit
// adjacent to a unit word) -- matches referralResponseBurden's real-world
// counterpart, clinicalHandoverBurden/aiExaminationBurden's
// deadline: "referral episode" (see docs/CONCEPTS_INDEX.md's 2026-08-29
// finding). Wired through a real Commitment, matching Tier 1 -- the same
// path those real burdens use.
burden episodeScopedBurden {
    state: active
    deadline: "referral episode"
    discharge_mode: eventual
}

// Same no-magnitude deadline, but with NO Commitment -- exercises Tier 2
// (the bare-DeonticToken fallback path) rather than Tier 1.
burden bareEpisodeScopedBurden {
    state: active
    deadline: "referral episode"
    discharge_mode: eventual
}

commitment eventualCommitment {
    by: Holder
    obligation: "Discharge the eventual burden"
    creates_burden: eventualBurden
}

commitment strictCommitment {
    by: Holder
    obligation: "Discharge the strict burden"
    creates_burden: strictBurden
}

commitment episodeScopedCommitment {
    by: Holder
    obligation: "Discharge the episode-scoped burden"
    creates_burden: episodeScopedBurden
}
"""


def _build_probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


def _token(state, name):
    return next(t for t in state.tokens if t.token_name == name)


def test_eventual_burden_stays_active_before_deadline_elapsed():
    rt = _build_probe_runtime()
    state = rt.current_state()
    assert _token(state, "eventualBurden").granted_at_tick == 0

    # deadline_steps == 5 ("1 hour"); elapsed == 4 < 5 — not yet violated.
    almost_due = state.with_tick(4)
    new_state, record = check_live_violations(almost_due, rt._spec)

    assert record.outcome == "ok"
    assert record.violations == ()
    assert _token(new_state, "eventualBurden").state == "active"
    # No-op poll must not consume a tick — see el_engine.check_live_violations()'s
    # docstring: this is a deliberate exception to the "every mutation advances
    # tick unconditionally" convention, specifically to keep repeated polling safe.
    assert new_state.tick == 4


def test_eventual_burden_transitions_to_violated_once_elapsed_reaches_deadline():
    rt = _build_probe_runtime()
    state = rt.current_state()

    # elapsed == 5 == deadline_steps — boundary is inclusive ("elapsed >= deadline").
    exactly_due = state.with_tick(5)
    new_state, record = check_live_violations(exactly_due, rt._spec)

    assert record.outcome == "violation"
    assert record.violations == ("eventualBurden",)
    assert "eventualBurden" in record.effects[0]
    assert _token(new_state, "eventualBurden").state == "violated"
    # Non-mutating on the input WorldState (frozen dataclass, copy-on-write).
    assert _token(state, "eventualBurden").state == "active"
    assert new_state.tick == 6  # a real transition happened — tick DOES advance


def test_strict_burden_never_touched_regardless_of_elapsed_time():
    rt = _build_probe_runtime()
    state = rt.current_state()

    # Wildly past any plausible deadline — must still be skipped entirely.
    way_past_due = state.with_tick(1000)
    new_state, record = check_live_violations(way_past_due, rt._spec)

    assert "strictBurden" not in record.violations
    assert _token(new_state, "strictBurden").state == "active"
    # The eventual sibling, by contrast, does get caught at the same tick —
    # confirms strictBurden's exclusion is discharge_mode-specific, not an
    # accident of the fixture never reaching the deadline check at all.
    assert "eventualBurden" in record.violations


def test_tick_advances_when_a_violation_is_found():
    rt = _build_probe_runtime()
    state = rt.current_state().with_tick(5)
    new_state, _record = check_live_violations(state, rt._spec)
    assert new_state.tick == 6


def test_tick_does_not_advance_on_no_op():
    """The no-op-still-advances precedent (reinstate_authorization()) is
    deliberately NOT followed here — see el_engine.check_live_violations()'s
    docstring. A poll that finds nothing must be free to repeat without
    consuming ticks other live Burdens' deadlines are measured against."""
    rt = _build_probe_runtime()
    state = rt.current_state().with_tick(4)  # elapsed 4 < deadline_steps 5
    new_state, record = check_live_violations(state, rt._spec)
    assert record.outcome == "ok"
    assert new_state.tick == 4


def test_no_magnitude_deadline_never_violates_regardless_of_elapsed_time():
    """episodeScopedBurden ("referral episode", Tier 1/Commitment-backed):
    a deadline with no genuine elapsed-time magnitude must never tick-
    violate, no matter how far past any plausible threshold the clock
    advances -- see docs/CONCEPTS_INDEX.md's 2026-08-29 finding and
    _has_deadline_magnitude()'s docstring. Wildly past even the largest
    numeric deadline anywhere in the real scenarios (assessmentScheduling-
    Burden's 112, post-5b21dc9) to make sure this isn't just "hasn't
    reached some large threshold yet."""
    rt = _build_probe_runtime()
    state = rt.current_state()

    way_past_due = state.with_tick(10_000)
    new_state, record = check_live_violations(way_past_due, rt._spec)

    assert "episodeScopedBurden" not in record.violations
    assert _token(new_state, "episodeScopedBurden").state == "active"
    # eventualBurden, by contrast, does violate at the same tick -- confirms
    # episodeScopedBurden's exclusion is deadline-shape-specific, not an
    # accident of the fixture never reaching any check at all.
    assert "eventualBurden" in record.violations


def test_no_magnitude_deadline_never_violates_via_bare_token_fallback():
    """Same as above, but for bareEpisodeScopedBurden -- no Commitment, so
    this exercises Tier 2 (the bare-DeonticToken fallback path) rather than
    Tier 1. The magnitude gate must apply identically regardless of which
    tier resolves the burden's deadline."""
    rt = _build_probe_runtime()
    state = rt.current_state()

    way_past_due = state.with_tick(10_000)
    new_state, record = check_live_violations(way_past_due, rt._spec)

    assert "bareEpisodeScopedBurden" not in record.violations
    assert _token(new_state, "bareEpisodeScopedBurden").state == "active"


def test_runtime_wrapper_appends_to_ledger():
    rt = _build_probe_runtime()
    rt._state = rt._state.with_tick(5)

    record = rt.check_live_violations()

    assert record.outcome == "violation"
    assert record in rt._ledger
    assert _token(rt.current_state(), "eventualBurden").state == "violated"


# ── DN_010, option (b): episode-conclusion-based deadline checking ────────────
#
# episodeScopedBurden (above) never tick-violates regardless of elapsed time —
# that's the 2026-08-29 mitigation (a), unchanged. This second probe exercises
# the DN_010 (b) extension on top of it: a no-magnitude burden that IS a
# member of its owning element's declared satisfaction-condition group
# violates once every OTHER member of that group has resolved, but ONLY when
# the owning element opted in via lifecycle { terminating {
# on_objective_achieved: true } }.
#
# ConcludingCommunity opts in; NonConcludingCommunity declares the same
# shape of satisfaction condition but withholds the terminating block —
# isolating the opt-in gate itself, not just the group-conclusion logic.

_CONCLUSION_PROBE = """
enterprise specification CheckLiveViolationsConclusionProbe

party Holder {
    holds siblingBurden
    holds episodeScopedBurden
}

party OptOutHolder {
    holds optOutSiblingBurden
    holds optOutEpisodeScopedBurden
}

burden siblingBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

// No genuine elapsed-time magnitude -- the DN_010 (b-2) target, same shape
// as clinicalHandoverBurden/aiExaminationBurden's "referral episode".
burden episodeScopedBurden {
    state: active
    deadline: "referral episode"
    discharge_mode: eventual
}

burden optOutSiblingBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

burden optOutEpisodeScopedBurden {
    state: active
    deadline: "referral episode"
    discharge_mode: eventual
}

commitment siblingCommitment {
    by: Holder
    obligation: "Discharge the sibling burden"
    creates_burden: siblingBurden
}

commitment episodeScopedCommitment {
    by: Holder
    obligation: "Discharge the episode-scoped burden"
    creates_burden: episodeScopedBurden
}

commitment optOutSiblingCommitment {
    by: OptOutHolder
    obligation: "Discharge the opt-out sibling burden"
    creates_burden: optOutSiblingBurden
}

commitment optOutEpisodeScopedCommitment {
    by: OptOutHolder
    obligation: "Discharge the opt-out episode-scoped burden"
    creates_burden: optOutEpisodeScopedBurden
}

token_group episodeGroup {
    member: siblingBurden
    member: episodeScopedBurden
}

token_group optOutGroup {
    member: optOutSiblingBurden
    member: optOutEpisodeScopedBurden
}

community ConcludingCommunity
    description: "Opts into DN_010 conclusion-based checking"
    {
        objective: "Conclude once both burdens are discharged"
            satisfaction: all_discharged(episodeGroup)

        lifecycle {
            terminating {
                on_objective_achieved: true
            }
        }
    }

community NonConcludingCommunity
    description: "Has a satisfaction condition but does NOT opt in via terminating"
    {
        objective: "Conclude once both burdens are discharged"
            satisfaction: all_discharged(optOutGroup)
    }
"""


def _build_conclusion_probe_runtime() -> Runtime:
    result = parse_string(_CONCLUSION_PROBE, validate=True)
    assert result.ok, result.errors
    return Runtime.build_from_spec(result.model)


def _with_token_state(state, token_name, new_state_str):
    tokens = [
        _transition(t, new_state_str) if t.token_name == token_name else t
        for t in state.tokens
    ]
    return state.with_tokens(tokens)


def test_episode_scoped_burden_violates_once_owning_community_concludes():
    """Positive case. siblingBurden (episodeGroup's other member) discharged
    -- ConcludingCommunity's all_discharged(episodeGroup) is now true
    excluding episodeScopedBurden itself, and ConcludingCommunity opted in
    via terminating: on_objective_achieved: true. episodeScopedBurden must
    violate, even though tick is unchanged from 0 and it has no elapsed-time
    magnitude to check against."""
    rt = _build_conclusion_probe_runtime()
    state = _with_token_state(rt.current_state(), "siblingBurden", "discharged")

    new_state, record = check_live_violations(state, rt._spec)

    assert record.outcome == "violation"
    assert "episodeScopedBurden" in record.violations
    assert _token(new_state, "episodeScopedBurden").state == "violated"


def test_episode_scoped_burden_stays_active_while_sibling_still_active():
    """Negative case. siblingBurden left active -- ConcludingCommunity has
    NOT concluded. episodeScopedBurden must not violate via the conclusion
    path, no matter how far past any plausible threshold the clock
    advances -- confirms this path checks conclusion, not elapsed time."""
    rt = _build_conclusion_probe_runtime()
    state = rt.current_state().with_tick(10_000)

    new_state, record = check_live_violations(state, rt._spec)

    assert "episodeScopedBurden" not in record.violations
    assert _token(new_state, "episodeScopedBurden").state == "active"


def test_episode_scoped_burden_in_non_concluding_community_never_violates_via_conclusion():
    """Opt-out case. NonConcludingCommunity declares the same shape of
    satisfaction condition (all_discharged(optOutGroup)) as
    ConcludingCommunity, and its other group member (optOutSiblingBurden) IS
    discharged here -- but NonConcludingCommunity has no lifecycle {
    terminating { on_objective_achieved: true } }. optOutEpisodeScopedBurden
    must NOT violate via the conclusion path -- confirms the opt-in gate is
    actually consulted, not just that group-membership resolution works."""
    rt = _build_conclusion_probe_runtime()
    state = _with_token_state(rt.current_state(), "optOutSiblingBurden", "discharged")

    new_state, record = check_live_violations(state, rt._spec)

    assert "optOutEpisodeScopedBurden" not in record.violations
    assert _token(new_state, "optOutEpisodeScopedBurden").state == "active"
