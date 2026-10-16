"""
2.1.0-19 — standing duty validation.

Errors:
  standing-fields    a standing duty is an eventual burden, active or
                     pending, with no deadline, discharged_by or for_action,
                     and an ended_by other than its triggered_by;
  standing-in-group  it is no TokenGroup member;
  term-end-type      ends_at is a valid date or instant, or a Policy of type
                     date or instant;
  comparison-type and fact-key-clash also read a standing duty's keeps.
Warnings:
  [W-standing-no-end]       neither ends_at nor ended_by: never met;
  [W-standing-shared-fact]  standing duties of different holders read the
                            same keeps fact key.
[W-24] no longer reports a standing duty. Every message ends "(clause to
be confirmed)".

Layer 2 (validator) tests per tests/README.md's strategy.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_parser import parse, parse_string
from el_validator import validate_spec


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_CITATION = "(clause to be confirmed)"
_HEAD = """enterprise specification StandingRules
policy MinimumCover : amount { initial_value: 20000000 AUD }
policy MaximumShare : percentage { initial_value: 10% }
policy ContractEnd : instant { initial_value: 2027-06-30T17:00+10:00 }
policy ContractEndDate : date { initial_value: 2027-06-30 }
policy ContractLength : duration { initial_value: 365 days }
policy Label : string { initial_value: "x" }
party Supplier { holds duty }
party Other
community C { objective: "o" event signed event ended }
"""
_KEEPS = 'standing keeps: "insurance cover" >= MinimumCover'


def _result(tokens, extra=""):
    result = _quiet(parse_string, _HEAD + tokens + "\n" + extra)
    assert result.model is not None, result.errors
    return result


def _tagged(messages, tag):
    return [m for m in messages if m.startswith(f"[{tag}]")]


# ── standing-fields ──────────────────────────────────────────────────────

def test_valid_duty_has_no_errors_or_standing_warnings():
    result = _result(f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active }}")
    assert result.ok, result.errors
    assert [w for w in result.warnings
            if "duty" in w and not w.startswith("[W-standing-not-modelled]")] == []


@pytest.mark.parametrize("mode", ["", "discharge_mode: eventual"])
def test_default_and_explicit_eventual_pass(mode):
    result = _result(f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active {mode} }}")
    assert _tagged(result.errors, "standing-fields") == []
    duty = next(e for e in result.model.elements if getattr(e, "name", "") == "duty")
    assert duty.discharge_mode == "eventual"


@pytest.mark.parametrize("tokens, problem", [
    (f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active discharge_mode: strict }}",
     "it is strict; a standing duty must be eventual"),
    (f"permit duty {{ {_KEEPS} ends_at: ContractEnd state: active }}",
     "it is a permit; only a burden can be a standing duty"),
    (f"embargo duty {{ {_KEEPS} ends_at: ContractEnd state: active }}",
     "it is an embargo; only a burden can be a standing duty"),
    (f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: claimable }}",
     "its state is 'claimable'; it must be active or pending"),
    (f'burden duty {{ {_KEEPS} state: active deadline: "30 days" }}',
     "it has a deadline; its term is set by ends_at or ended_by"),
    (f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active discharged_by: ended }}",
     "it has discharged_by; only its term end ends it"),
    (f'burden duty {{ {_KEEPS} ends_at: ContractEnd for_action: "keep" state: active }}',
     "it has a for_action; no action ends it"),
    (f"burden duty {{ {_KEEPS} ended_by: signed state: pending triggered_by: signed }}",
     "'signed' both starts and ends its term"),
])
def test_standing_fields(tokens, problem):
    errors = _result(tokens).errors
    assert f"[standing-fields] Standing duty 'duty': {problem}. {_CITATION}" in errors


def test_strict_standing_duty_refused_on_every_validation_path():
    tokens = f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active discharge_mode: strict }}"
    result = _result(tokens)
    assert not result.ok                                         # parse(validate=True)
    model = _quiet(parse_string, _HEAD + tokens, validate=False).model
    assert _tagged(validate_spec(model), "standing-fields")      # validate_spec() directly
    assert _tagged(_quiet(parse, Path(__file__).resolve().parent / "examples" / "standing"
                          / "invalid_standing_fields.el").errors, "standing-fields")


# ── standing-in-group ────────────────────────────────────────────────────

def test_standing_in_group():
    extra = ("burden plain { state: active }\n"
             "token_group g {\n    member: duty\n    member: plain\n}\n")
    errors = _result(f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active }}", extra).errors
    assert _tagged(errors, "standing-in-group") == [
        f"[standing-in-group] Standing duty 'duty' is a member of token group 'g'; a standing "
        f"duty is never a group member. {_CITATION}"]


# ── term-end-type ────────────────────────────────────────────────────────

@pytest.mark.parametrize("end", ["ContractEnd", "ContractEndDate", "2027-06-30",
                                 "2027-06-30T17:00+10:00", "2027-06-30T07:00Z"])
def test_valid_term_ends(end):
    assert _tagged(_result(f"burden duty {{ {_KEEPS} ends_at: {end} state: active }}").errors,
                   "term-end-type") == []


@pytest.mark.parametrize("end, problem", [
    ("ContractLength", "ends_at ContractLength is a policy of type 'duration'; it must be of "
                       "type date or instant"),
    ("Label", "ends_at Label is a policy of type 'string'; it must be of type date or instant"),
    ("2027-02-30", "ends_at 2027-02-30 is not a calendar date"),
    ("2027-06-30T24:00Z", "ends_at 2027-06-30T24:00Z is not an instant: not a time of day"),
    ("2027-06-30T17:00+24:00", "ends_at 2027-06-30T17:00+24:00 is not an instant: not a UTC offset"),
])
def test_invalid_term_ends(end, problem):
    errors = _result(f"burden duty {{ {_KEEPS} ends_at: {end} state: active }}").errors
    assert f"[term-end-type] Standing duty 'duty': {problem}. {_CITATION}" in errors


# ── keeps through comparison-type and fact-key-clash ────────────────────

@pytest.mark.parametrize("keeps, problem", [
    ('"x" <= 60 day', "limit 60 day has currency code 'day', not three upper-case letters "
                      "A-Z (ISO 4217 form); a duration cannot be compared"),
    ('"x" >= Label', "limit Label is a policy of type 'string'; a comparison takes a policy "
                     "of type integer, decimal, number, percentage or amount"),
])
def test_keeps_comparison_type(keeps, problem):
    errors = _result(f"burden duty {{ standing keeps: {keeps} ends_at: ContractEnd "
                     f"state: active }}").errors
    assert (f"[comparison-type] Standing duty 'duty': keeps {keeps}: {problem}. {_CITATION}"
            in errors)


def test_fact_key_clash_between_keeps_and_a_precondition():
    extra = ('community D { objective: "o" Supplier fills r role r { action assess { actor: r '
             'precondition: "insurance cover" <= 10% } } }')
    errors = _result(f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active }}", extra).errors
    assert len(_tagged(errors, "fact-key-clash")) == 1
    assert "Standing duty 'duty'" in _tagged(errors, "fact-key-clash")[0]


def test_same_reading_in_keeps_and_precondition_no_clash():
    extra = ('community D { objective: "o" Supplier fills r role r { action assess { actor: r '
             'precondition: "insurance cover" >= 20000000 AUD } } }')
    errors = _result(f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active }}", extra).errors
    assert _tagged(errors, "fact-key-clash") == []


# ── Warnings ─────────────────────────────────────────────────────────────

def test_standing_no_end():
    result = _result(f"burden duty {{ {_KEEPS} state: active }}")
    assert result.ok
    assert _tagged(result.warnings, "W-standing-no-end") == [
        f"[W-standing-no-end] Standing duty 'duty' has neither ends_at nor ended_by: its term "
        f"never ends, so it is never met, only kept or breached. {_CITATION}"]


@pytest.mark.parametrize("end", ["ends_at: ContractEnd", "ended_by: ended"])
def test_an_end_silences_no_end(end):
    assert _tagged(_result(f"burden duty {{ {_KEEPS} {end} state: active }}").warnings,
                   "W-standing-no-end") == []


def test_shared_fact_across_holders():
    tokens = (f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active }}\n"
              f"burden otherDuty {{ {_KEEPS} ends_at: ContractEnd state: active }}\n"
              "commitment OC { by: Other obligation: \"keep cover\" creates_burden: otherDuty }")
    warnings = _tagged(_result(tokens).warnings, "W-standing-shared-fact")
    assert warnings == [
        "[W-standing-shared-fact] Fact 'insurance cover' is read by standing duties of different "
        "holders ('duty' held by Supplier; 'otherDuty' held by Other): one reported value judges "
        f"all of them. Use one fact key per holder. {_CITATION}"]


@pytest.mark.parametrize("tokens", [
    # same holder, two limits on one fact
    (f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active }}\n"
     f"burden otherDuty {{ standing keeps: \"insurance cover\" <= 90000000 AUD ends_at: ContractEnd "
     f"state: active }}\ncommitment SC {{ by: Supplier obligation: \"o\" creates_burden: otherDuty }}"),
    # different holders, different facts
    (f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active }}\n"
     f"burden otherDuty {{ standing keeps: \"other cover\" >= MinimumCover ends_at: ContractEnd "
     f"state: active }}\ncommitment OC {{ by: Other obligation: \"o\" creates_burden: otherDuty }}"),
])
def test_no_shared_fact_warning(tokens):
    assert _tagged(_result(tokens).warnings, "W-standing-shared-fact") == []


def test_w24_skips_standing_but_not_plain():
    result = _result(f"burden duty {{ {_KEEPS} ends_at: ContractEnd state: active }}\n"
                     "burden plain { state: active }",
                     'party P { holds plain }')
    assert [w for w in _tagged(result.warnings, "W-24")] and \
        all("'plain'" in w for w in _tagged(result.warnings, "W-24"))


# ── Shipped scenarios ────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parent.parent
_NEW = ("[standing-fields]", "[standing-in-group]", "[term-end-type]",
        "[W-standing-no-end]", "[W-standing-shared-fact]")


@pytest.mark.parametrize("path", sorted(
    p for p in (_REPO / "scenarios").rglob("*.el") if p.name != "ecommerce_scenario.el"
), ids=lambda p: p.name)
def test_shipped_scenarios_unaffected(path):
    result = _quiet(parse, path)
    assert result.model is not None
    assert [m for m in result.errors + result.warnings if m.startswith(_NEW)] == []
