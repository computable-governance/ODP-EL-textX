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
"""
from el_engine import _parse_deadline_steps


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


def test_magnitude_scales_linearly_with_the_per_unit_step_value():
    """5 * 8 = 40, 14 * 8 = 112 — proportional to the real 14/5 = 2.8x ratio
    the two deadlines actually encode, not just "different"."""
    assert _parse_deadline_steps("5 working days from referral receipt") == 40
    assert _parse_deadline_steps("14 days from referral receipt") == 112


# ── Other real scenario deadline strings, magnitude present ─────────────────

def test_magnitude_parsed_for_hour_deadlines():
    assert _parse_deadline_steps("48 hours from clinical decision") == 240
    assert _parse_deadline_steps("2 hours from consult request") == 10
    assert _parse_deadline_steps("4 hours from referral delegation") == 20


def test_magnitude_parsed_for_minute_deadlines():
    assert _parse_deadline_steps("10 minutes") == 30
    assert _parse_deadline_steps("15 minutes") == 45
    assert _parse_deadline_steps("5 minutes") == 15


# ── magnitude == 1 must reproduce the original flat bucket exactly ─────────
# (existing tests in test_check_live_violations.py / test_check_violations_
# endpoint.py hardcode deadline_steps == 5 for "1 hour" — this fix must not
# disturb that.)

def test_magnitude_one_matches_original_flat_bucket_value():
    assert _parse_deadline_steps("1 hour") == 5
    assert _parse_deadline_steps("1 day") == 8
    assert _parse_deadline_steps("1 week") == 12


# ── No digit alongside the unit word: falls back to the original flat
# per-unit bucket, unchanged from before this fix ───────────────────────────

def test_word_form_magnitude_falls_back_to_flat_bucket():
    """"thirty days" has no digit for the parser to find — this parser does
    not spell out word-form numbers — so it must fall back to the original
    unit-only bucket (8), not silently default to something else."""
    assert _parse_deadline_steps("thirty days from cancellation") == 8


def test_bare_unit_only_deadline_falls_back_to_flat_bucket():
    assert _parse_deadline_steps("referral response window: day") == 8


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
    # back to the flat per-unit bucket, not 12345 * 8.
    assert steps == 8
