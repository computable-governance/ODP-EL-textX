"""
2.1.0-16 — standing duty grammar.

A burden may be a standing duty, kept for its term:

    burden keepCover {
        standing
        keeps: "insurance cover" >= MinimumCover
        ends_at: ContractEnd
        ended_by: contractTerminated
        state: pending
        triggered_by: contractSigned
    }

`standing` and `keeps` (a Comparison) come together, first in the body;
`ends_at` takes a date or instant, or a date or instant Policy; `ended_by`
an event. Every existing token parses as before.

Layer 1 (grammar/parse) tests per tests/README.md's strategy.
"""
import contextlib
import io
import re
from decimal import Decimal
from pathlib import Path

import pytest

from el_domain import Amount, Comparison, Date, Instant, Percentage
from el_parser import parse_string


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_HEAD = """enterprise specification StandingProbe
policy MinimumCover : amount { initial_value: 20000000 AUD }
policy MaximumShare : percentage { initial_value: 10% }
policy ContractEnd : instant { initial_value: 2027-06-30T17:00+10:00 }
policy ContractEndDate : date { initial_value: 2027-06-30 }
party Supplier
community Contract { objective: "o" event contractSigned event contractTerminated }
"""


def _parse(token):
    return _quiet(parse_string, _HEAD + token + "\n", validate=False)


def _token(token):
    result = _parse(token)
    assert result.ok, result.errors
    return [e for e in result.model.elements if type(e).__name__ == "DeonticToken"][-1]


# ── Five standing duty forms ─────────────────────────────────────────────

def test_cover_until_a_shared_instant_policy():
    t = _token('burden keepCover { standing keeps: "insurance cover" >= MinimumCover '
               'ends_at: ContractEnd state: active }')
    assert t.standing is True
    assert isinstance(t.keeps, Comparison)
    assert (t.keeps.fact, t.keeps.op, t.keeps.policy.name) == ("insurance cover", ">=", "MinimumCover")
    assert t.ends_at is None and t.ends_at_policy.name == "ContractEnd"
    assert t.ended_by is None


def test_share_until_a_date():
    t = _token('burden keepShare { standing keeps: "subcontract share" <= 10% '
               'ends_at: 2027-06-30 state: active }')
    assert isinstance(t.keeps.literal, Percentage) and t.keeps.literal.value == 10
    assert isinstance(t.ends_at, Date) and t.ends_at.value == "2027-06-30"


def test_cover_from_an_event_until_an_event():
    t = _token('burden keepCover2 { standing keeps: "insurance cover" >= 20000000 AUD '
               'ended_by: contractTerminated state: pending triggered_by: contractSigned }')
    assert isinstance(t.keeps.literal, Amount) and t.keeps.literal.code == "AUD"
    assert t.ended_by.name == "contractTerminated"
    assert t.triggered_by.name == "contractSigned"
    assert t.state == "pending"


def test_share_until_an_instant_or_an_event():
    t = _token('burden keepShare2 { standing keeps: "subcontract share" <= MaximumShare '
               'ends_at: 2027-06-30T17:00+10:00 ended_by: contractTerminated state: active }')
    assert isinstance(t.ends_at, Instant) and t.ends_at.value == "2027-06-30T17:00+10:00"
    assert t.ended_by.name == "contractTerminated"


def test_plain_burden_unchanged():
    t = _token('burden fileReport { for_action: "file" state: active deadline: "21 days" }')
    assert t.standing is False
    assert (t.keeps, t.ends_at, t.ends_at_policy, t.ended_by) == (None, None, None, None)
    assert t.deadline == "21 days" and t.discharge_mode == "eventual"


# ── Other accepted forms ─────────────────────────────────────────────────

@pytest.mark.parametrize("limit, cls, value", [
    ("5", int, 5), ("2.5", Decimal, Decimal("2.5")),
])
def test_number_limit(limit, cls, value):
    t = _token(f'burden b {{ standing keeps: "x" >= {limit} state: active }}')
    assert type(t.keeps.literal) is cls and t.keeps.literal == value


def test_date_policy_end():
    assert _token('burden b { standing keeps: "x" >= 5 ends_at: ContractEndDate '
                  'state: active }').ends_at_policy.name == "ContractEndDate"


def test_no_end_parses():
    # Neither ends_at nor ended_by: parses (the validator warns, 2.1.0-19).
    t = _token('burden b { standing keeps: "x" >= 5 state: active }')
    assert t.ends_at is None and t.ended_by is None


def test_end_keyword_after_a_number_is_not_a_currency_code():
    t = _token('burden b { standing keeps: "x" >= 5 ended_by: contractTerminated state: active }')
    assert t.keeps.literal == 5 and t.ended_by.name == "contractTerminated"
    t = _token('burden b { standing keeps: "x" >= 5 ends_at: 2027-06-30 state: active }')
    assert t.keeps.literal == 5 and t.ends_at.value == "2027-06-30"


# ── Refused forms ────────────────────────────────────────────────────────

@pytest.mark.parametrize("token", [
    'burden b { keeps: "x" >= 5 state: active }',                        # keeps without standing
    'burden b { standing state: active }',                               # standing without keeps
    'burden b { standing keeps: "x" state: active }',                    # no comparison
    'burden b { standing keeps: "x" == 5 state: active }',
    'burden b { standing keeps: "x" >= 5 ends_at: 60 days state: active }',   # no duration term
    'burden b { standing keeps: "x" >= 5 ends_at: "2027-06-30" state: active }',
    'burden b { standing keeps: "x" >= 5 ended_by: 2027-06-30 state: active }',
    'burden b { state: active standing keeps: "x" >= 5 }',              # must come first
    'burden b { standing keeps: "x" >= 5 ended_by: e ends_at: 2027-06-30 state: active }',  # order
])
def test_refused(token):
    assert not _parse(token).ok


@pytest.mark.parametrize("token, name", [
    ('burden b { standing keeps: "x" >= 5 ends_at: NoSuchPolicy state: active }', "NoSuchPolicy"),
    ('burden b { standing keeps: "x" >= 5 ended_by: noSuchEvent state: active }', "noSuchEvent"),
])
def test_unknown_reference_refused(token, name):
    result = _parse(token)
    assert not result.ok and name in result.errors[0]


# ── Every shipped scenario parses as before ─────────────────────────────

_REPO = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("path", sorted(
    p for p in (_REPO / "scenarios").rglob("*.el") if p.name != "ecommerce_scenario.el"
), ids=lambda p: p.name)
def test_shipped_tokens_are_not_standing(path):
    from el_parser import parse
    result = _quiet(parse, path, validate=False)
    assert result.model is not None
    assert not any(getattr(e, "standing", False) for e in result.model.elements)


# ── No three-letter keyword can follow a value in the standing group ────

_GRAMMAR = (_REPO / "grammar" / "v2" / "el_grammar.tx").read_text()


def test_no_three_letter_keyword_after_keeps_or_term_values():
    # Everything that may follow the keeps limit, the ends_at value or the
    # ended_by reference is a later keyword of the DeonticToken body (or its
    # closing brace). Take every quoted keyword after 'keeps' in that body:
    # a superset of the followers.
    body = re.search(r"(?ms)^DeonticToken:\s*(.*?)^;", _GRAMMAR).group(1)
    body = re.sub(r"//[^\n]*", "", body)          # comments quote words too
    after_keeps = body[body.index("'keeps'"):]
    followers = {k for k in re.findall(r"'([^']*)'", after_keeps)}
    assert {"ends_at", "ended_by", "for_action", "state"} <= followers
    three_letter = set(re.findall(r"'([A-Za-z]{3})'", _GRAMMAR))
    assert three_letter and three_letter & followers == set()
