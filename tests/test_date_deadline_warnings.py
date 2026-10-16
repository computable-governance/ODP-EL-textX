"""
2.1.0-8 — date-deadline warnings.

  [W-deadline-date-not-measured]  a deadline with a calendar date that is
      never judged: a date with other numbers, a second date, or a date not
      in the 2.1.0 notation (a date alone, or a date and time with a UTC
      offset);
  [W-deadline-date-invalid]       a date in the 2.1.0 notation that is not a
      calendar date, or whose time or UTC offset is out of range, named with
      the real reason;
  [W-deadline-several-durations]  more than one duration ("2 weeks and 3
      days"): only the first is measured.

Burdens only, top-level and role-scoped, eventual or strict. All three are
warnings (they start "[W-"), never errors. [W-19] is unchanged; [W-24]
skips an eventual burden whose deadline is a measured date; [W-25] skips
any deadline containing a date.

Layer 2 (validator) tests per tests/README.md's strategy.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_parser import parse, parse_string


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_NEW = ("[W-deadline-date-not-measured]", "[W-deadline-date-invalid]",
        "[W-deadline-several-durations]")


def _result(deadline, mode="eventual", kind="burden"):
    src = (
        "enterprise specification WarnProbe\n\nparty Holder\n\n"
        f'{kind} probe {{ state: active deadline: "{deadline}"'
        + (f" discharge_mode: {mode}" if kind == "burden" else "") + " }\n"
    )
    result = _quiet(parse_string, src)
    assert result.model is not None, result.errors
    return result


def _tags(result, prefixes=_NEW):
    return [w[:w.index("]") + 1] for w in result.warnings if w.startswith(prefixes)]


# ── Silent for a measured date or a single duration ──────────────────────

@pytest.mark.parametrize("deadline", [
    "by 2026-11-30", "2026-11-30", "by 2026-11-30 end of day",
    "2026-11-30T17:00+10:00", "2026-11-30T07:00Z", "2026-11-30T07:00:00Z",
    "30 days", "5 working days", "referral episode",
])
@pytest.mark.parametrize("mode", ["eventual", "strict"])
def test_silent(deadline, mode):
    assert _tags(_result(deadline, mode)) == []


# ── Not measured ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("deadline, reason", [
    ("2026-11-30 within 1 day", "a date with other numbers is not measured"),
    ("between 2026-11-01 and 2026-11-30", "a date with other numbers is not measured"),
    ("2026-11-30 17:00", "a date with other numbers is not measured"),
    ("2026-11-30T17:00", "date not in the 2.1.0 notation"),
    ("2026-11-30t17:00+10:00", "date not in the 2.1.0 notation"),
    ("2026-11-30T17:00+1000", "date not in the 2.1.0 notation"),
])
def test_not_measured(deadline, reason):
    result = _result(deadline)
    assert _tags(result) == ["[W-deadline-date-not-measured]"]
    message = next(w for w in result.warnings if w.startswith("[W-deadline-date-not-measured]"))
    assert message.startswith(
        f"[W-deadline-date-not-measured] Burden 'probe' has deadline '{deadline}': "
        f"{reason}, so it is never judged.")
    assert "one fixed UTC offset (no daylight saving or holidays)" in message
    assert message.endswith("(§6.4.3, §7.8.7)")


# ── Invalid, with the real reason ────────────────────────────────────────

@pytest.mark.parametrize("deadline, text, problem", [
    ("by 2026-02-30", "2026-02-30", "not a calendar date"),
    ("2026-13-01", "2026-13-01", "not a calendar date"),
    ("2026-02-30T10:00Z", "2026-02-30T10:00Z", "not a calendar date"),
    ("2026-11-30T24:00Z", "2026-11-30T24:00Z", "not a time of day"),
    ("2026-11-30T17:60+10:00", "2026-11-30T17:60+10:00", "not a time of day"),
    ("2026-11-30T17:00:30Z", "2026-11-30T17:00:30Z", "not a whole minute"),
    ("2026-11-30T17:00+24:00", "2026-11-30T17:00+24:00", "not a UTC offset"),
    ("2026-11-30T17:00-00:00", "2026-11-30T17:00-00:00", "-00:00 is not a UTC offset"),
    ("by 9999-12-31", "9999-12-31", "after the last representable time"),
])
@pytest.mark.parametrize("mode", ["eventual", "strict"])
def test_invalid_names_the_reason(deadline, text, problem, mode):
    result = _result(deadline, mode)
    assert _tags(result) == ["[W-deadline-date-invalid]"]
    assert (f"[W-deadline-date-invalid] Burden 'probe' has deadline '{deadline}': "
            f"{text} is not a valid date or time ({problem}), so the deadline is "
            f"never judged. (§6.4.3, §7.8.7)") in result.warnings


def test_invalid_date_with_other_numbers_gets_both():
    assert _tags(_result("2026-02-30 within 1 day")) == [
        "[W-deadline-date-not-measured]", "[W-deadline-date-invalid]"]


# ── Several durations ────────────────────────────────────────────────────

@pytest.mark.parametrize("deadline", ["2 weeks and 3 days", "within 1 day, 12 hours"])
def test_several_durations(deadline):
    result = _result(deadline)
    assert _tags(result) == ["[W-deadline-several-durations]"]
    assert any("only the first is measured" in w for w in result.warnings)


# ── Scope: burdens only, role-scoped too, warnings not errors ────────────

@pytest.mark.parametrize("kind", ["permit", "embargo"])
def test_permits_and_embargoes_not_checked(kind):
    assert _tags(_result("2026-02-30 within 1 day", kind=kind)) == []


def test_role_scoped_burden_checked():
    src = """
enterprise specification InlineProbe
party Holder
community C {
    objective: "probe"
    role r {
        burden inlineBurden { for_action: "act" state: active deadline: "2 weeks and 3 days" }
    }
}
"""
    result = _quiet(parse_string, src)
    assert result.model is not None, result.errors
    assert any(w.startswith("[W-deadline-several-durations] Burden 'inlineBurden'")
               for w in result.warnings)


def test_new_rules_are_warnings_not_errors():
    result = _result("2026-02-30 within 1 day")
    assert result.ok
    assert not any(e.startswith(_NEW) for e in result.errors)


# ── W-19, W-24 and W-25 ──────────────────────────────────────────────────

def test_w19_unchanged_for_a_strict_date_burden():
    # Strict date burdens are not judged in 2.1.0, so W-19 still warns.
    assert _tags(_result("by 2026-11-30", "strict"), "[W-19]") == ["[W-19]"]


def test_w24_skips_a_measured_date_only():
    assert _tags(_result("by 2026-11-30"), "[W-24]") == []
    assert _tags(_result("2026-11-30 within 1 day"), "[W-24]") == ["[W-24]"]
    assert _tags(_result("referral episode"), "[W-24]") == ["[W-24]"]


@pytest.mark.parametrize("deadline", ["by 2026-11-30", "2026-11-30 within 1 day",
                                      "2026-11-30T17:00"])
def test_w25_skips_any_date(deadline):
    assert _tags(_result(deadline), "[W-25]") == []


def test_w25_still_fires_without_a_date():
    assert _tags(_result("2 hrs"), "[W-25]") == ["[W-25]"]


# ── Shipped scenarios ────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("path", sorted(
    p for p in (_REPO / "scenarios").rglob("*.el") if p.name != "ecommerce_scenario.el"
), ids=lambda p: p.name)
def test_no_shipped_scenario_fires_the_new_warnings(path):
    result = _quiet(parse, path)
    assert result.model is not None
    assert _tags(result) == []
