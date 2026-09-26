"""
Layer 3 — el_engine._parse_deadline_steps().

Regression guard for the deadline-bucketing bug found live via
referral-board-view.html (CC investigation, 2026-08-29) and fixed the same
day: the parser matched only the unit word in a deadline string and ignored
any leading magnitude, so "5 working days from referral receipt"
(referralResponseBurden) and "14 days from referral receipt"
(assessmentSchedulingBurden) both resolved to the same flat 8 steps. Both
burdens then went VIOLATED at the identical elapsed tick in
check_live_violations() (POST /check-violations), even though the 14-day
deadline should take materially longer to elapse than the 5-day one. Also
logged as the still-open "Convergence with live-violation-detection design"
finding in docs/CONCEPTS_INDEX.md's discharge_mode: strict entry
(2026-08-20), closed by this fix.

Also covers _has_deadline_magnitude() — the sibling function added
2026-08-29 to close a distinct, older gap this fix's own investigation
surfaced: deadline strings with no genuine elapsed-time magnitude at all
(e.g. "referral episode") were falling through to _parse_deadline_steps()'s
bare default (5) and getting tick-violated almost immediately in
check_live_violations() — see docs/CONCEPTS_INDEX.md's "referral episode"
finding (2026-08-29) and tests/test_check_live_violations.py's
test_no_magnitude_deadline_never_violates_* tests for the integration-level
coverage of that fix.

AM-111: one step is one minute (el_engine._STEP_SECONDS); every unit
converts through it, so the values below are durations in minutes.
"""
from el_engine import _has_deadline_magnitude, _parse_deadline_steps


# ── The exact regression this fix closes ────────────────────────────────────

def test_five_day_and_fourteen_day_deadlines_now_differ():
    """The reported bug: referralResponseBurden ("5 working days...") and
    assessmentSchedulingBurden ("14 days...") used to both resolve to 8.
    They must now resolve to different values, with the longer deadline
    strictly larger."""
    five_day  = _parse_deadline_steps("5 working days from referral receipt")
    fourteen_day = _parse_deadline_steps("14 days from referral receipt")

    assert five_day != fourteen_day
    assert fourteen_day > five_day


def test_magnitude_scales_linearly_with_the_unit_duration():
    """AM-111: one step is one minute. 14 days = 20160 minutes; 5 working
    days = 7 calendar days (the 7/5 working-day approximation) = 10080."""
    assert _parse_deadline_steps("5 working days from referral receipt") == 10080
    assert _parse_deadline_steps("14 days from referral receipt") == 20160


# ── Other real scenario deadline strings, magnitude present ─────────────────

def test_magnitude_parsed_for_hour_deadlines():
    assert _parse_deadline_steps("48 hours from clinical decision") == 2880
    assert _parse_deadline_steps("2 hours from consult request") == 120
    assert _parse_deadline_steps("4 hours from referral delegation") == 240


def test_magnitude_parsed_for_minute_deadlines():
    assert _parse_deadline_steps("10 minutes") == 10
    assert _parse_deadline_steps("15 minutes") == 15
    assert _parse_deadline_steps("5 minutes") == 5


# ── AM-111: every unit converts through one step duration ──────────────────

def test_every_unit_converts_through_one_step_duration():
    assert _parse_deadline_steps("1 minute") == 1
    assert _parse_deadline_steps("1 hour") == 60
    assert _parse_deadline_steps("1 day") == 1440
    assert _parse_deadline_steps("1 week") == 10080
    assert _parse_deadline_steps("1 month") == 43200      # 30 days
    assert _parse_deadline_steps("1 year") == 525600      # 365 days
    assert _parse_deadline_steps("0 minutes") == 0


def test_seconds_round_up_to_whole_steps():
    """A deadline is never shorter than stated."""
    assert _parse_deadline_steps("1 second") == 1
    assert _parse_deadline_steps("30 seconds") == 1
    assert _parse_deadline_steps("90 seconds") == 2


def test_qualified_units_are_documented_approximations():
    """Working/business days: 5 per 7-day week; business hours: 40 per
    168-hour week. Start weekday and public holidays are ignored."""
    assert _parse_deadline_steps("5 working days") == 7 * 1440
    assert _parse_deadline_steps("5 business days") == 7 * 1440
    assert _parse_deadline_steps("1 working day") == 2016          # 1.4 days
    assert _parse_deadline_steps("40 business hours") == 168 * 60
    assert _parse_deadline_steps("5 days") == 5 * 1440             # unqualified


def test_real_time_order_is_preserved():
    """Before AM-111 "48 hours" (240) outlasted "14 days" (112), and
    "5 minutes" (15) outlasted "2 hours" (10) and "1 day" (8)."""
    ordered = ["30 seconds", "5 minutes", "10 minutes", "15 minutes",
               "2 hours", "4 hours", "1 day", "48 hours", "72 hours",
               "5 working days", "14 days", "1 month", "1 year"]
    steps = [_parse_deadline_steps(d) for d in ordered]
    assert steps == sorted(steps)
    assert len(set(steps)) == len(steps)


# ── No digit alongside the unit word: one unit's duration ──────────────────

def test_word_form_magnitude_falls_back_to_one_unit():
    """"thirty days" has no digit for the parser to find — this parser does
    not spell out word-form numbers — so it falls back to one unit (a day),
    not silently to something else. Never clock-violated (no magnitude)."""
    assert _parse_deadline_steps("thirty days from cancellation") == 1440


def test_bare_unit_only_deadline_falls_back_to_one_unit():
    assert _parse_deadline_steps("referral response window: day") == 1440


# ── No unit keyword at all: default, unaffected by this fix ────────────────

def test_non_unit_deadline_strings_use_default():
    assert _parse_deadline_steps("referral episode") == 5
    assert _parse_deadline_steps("end of session") == 5
    assert _parse_deadline_steps("by 2026-05-20") == 5
    assert _parse_deadline_steps(None) == 5
    assert _parse_deadline_steps("") == 5


def test_non_unit_deadline_strings_respect_custom_default():
    assert _parse_deadline_steps("referral episode", default=3) == 3
    assert _parse_deadline_steps(None, default=3) == 3


# ── An unrelated number elsewhere in the string must not be mistaken for
# the deadline's magnitude when it isn't adjacent to a unit word ───────────

def test_distant_unrelated_number_does_not_pair_with_a_later_unit():
    """The 20-char adjacency window should not stretch across an unrelated
    number far from any unit word."""
    steps = _parse_deadline_steps(
        "referral 12345 must be actioned promptly within the current day"
    )
    # "day" is present with no adjacent digit within the window -> falls
    # back to one unit, not 12345 days.
    assert steps == 1440


# ── _has_deadline_magnitude() — the 2026-08-29 sibling function ────────────

def test_has_magnitude_true_for_every_magnitude_bearing_deadline():
    assert _has_deadline_magnitude("5 working days from referral receipt") is True
    assert _has_deadline_magnitude("14 days from referral receipt") is True
    assert _has_deadline_magnitude("48 hours from clinical decision") is True
    assert _has_deadline_magnitude("1 hour") is True
    assert _has_deadline_magnitude("10 minutes") is True
    assert _has_deadline_magnitude("1 year") is True   # AM-111: new unit


def test_has_magnitude_false_for_the_reported_referral_episode_case():
    """The exact string this finding is about: no digit, no unit keyword."""
    assert _has_deadline_magnitude("referral episode") is False


def test_has_magnitude_false_for_every_no_digit_deadline_found_across_scenarios():
    """Every no-digit deadline: string found by grepping every .el scenario
    file in the repo (2026-08-29 scope check), not just referral_scenario.el's
    "referral episode" -- ecommerce_scenario.el and consent_scenario.el each
    contribute distinct cases."""
    assert _has_deadline_magnitude("invoice due date") is False
    assert _has_deadline_magnitude("agreed delivery date") is False
    assert _has_deadline_magnitude("reorder point") is False
    assert _has_deadline_magnitude("clinical session") is False
    assert _has_deadline_magnitude("end of session") is False


def test_has_magnitude_false_for_word_form_magnitude():
    """"thirty days" has a unit word but no digit -- _parse_deadline_steps()
    still falls back to one unit's duration for this case (see
    test_word_form_magnitude_falls_back_to_one_unit above), but
    _has_deadline_magnitude() must say False: a one-unit fallback is exactly the kind of guessed value check_live_violations() should not
    tick-violate on for a burden whose real deadline it cannot compute."""
    assert _has_deadline_magnitude("thirty days from cancellation") is False


def test_has_magnitude_false_for_digit_with_no_adjacent_unit():
    """"by 2026-05-20" contains digits, but none adjacent to a recognised
    unit word -- an absolute calendar date is exactly as unusable for an
    elapsed-time magnitude as no digit at all, and must be treated the same
    way, not merely "contains a digit character somewhere" (this deadline
    string appears only on a permit today, not a burden, so this doesn't
    currently change check_live_violations()' behaviour -- but the function
    must still get it right in case a future burden ever uses a similarly-
    shaped deadline)."""
    assert _has_deadline_magnitude("by 2026-05-20") is False


def test_has_magnitude_false_for_none_and_empty():
    assert _has_deadline_magnitude(None) is False
    assert _has_deadline_magnitude("") is False
