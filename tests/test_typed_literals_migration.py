"""
2.1.0-1 — pins each v2.0.0 → 2.1.0 change in how policy literals parse.

In v2.0.0, PolicyValue was Duration | NumberInterval | FLOAT | INT |
STRING | BOOL | ID. textX's FLOAT also matches '5', so INT was never
reached: every number was a Python float, and FLOAT accepted exponents,
'5.', '.5', a leading '+' and non-ASCII digits. 2.1.0-1 replaces FLOAT
and INT with plain ASCII numbers held as decimal.Decimal and int.

Each test names the v2.0.0 behaviour it changes, so the break is
intentional and visible. Durations and intervals are unchanged.

Minimal Layer 1 (grammar/parse) tests per tests/README.md's strategy.
"""
from decimal import Decimal

import pytest

from el_domain import Date, Duration, NumberInterval
from el_parser import parse_string


_HEADER = 'enterprise specification Probe\n\n'


def _parse(value, policy_type='integer'):
    src = _HEADER + (
        f'policy ProbePolicy : {policy_type} {{\n'
        f'    initial_value: {value}\n'
        '}\n'
    )
    return parse_string(src, validate=False)


def _value(value, policy_type='integer'):
    result = _parse(value, policy_type)
    assert result.ok, result.errors
    return result.model.elements[0].initial_value


def test_integer_was_float_now_int():
    # v2.0.0: 5 → 5.0 (float). Now: 5 (int).
    v = _value('5')
    assert type(v) is int and v == 5


def test_decimal_was_float_now_exact_decimal():
    # v2.0.0: 5.25 → float. Now: Decimal('5.25'); 5.0 stays a decimal.
    assert _value('5.25', 'decimal') == Decimal('5.25')
    v = _value('5.0', 'decimal')
    assert type(v) is Decimal and str(v) == '5.0'


@pytest.mark.parametrize('text', ['1e3', '2.5E-2'])
def test_exponent_was_float_now_parse_error(text):
    # v2.0.0: 1e3 → 1000.0. Now refused; write 1000 or 0.025.
    assert not _parse(text).ok


@pytest.mark.parametrize('text', ['+5', '+2.5'])
def test_leading_plus_was_accepted_now_parse_error(text):
    # v2.0.0: +5 → 5.0. Now refused; drop the '+'.
    assert not _parse(text).ok


def test_leading_plus_on_duration_and_interval_unchanged():
    # Not changed in 2.1.0-1: Duration and NumberInterval still use INT.
    d = _value('+5 days', 'duration')
    assert isinstance(d, Duration) and d.value == 5
    i = _value('+1..3')
    assert isinstance(i, NumberInterval) and (i.lower, i.upper) == (1, 3)


@pytest.mark.parametrize('text', ['5.', '.5'])
def test_bare_dot_forms_were_floats_now_parse_error(text):
    # v2.0.0: 5. → 5.0, .5 → 0.5. Now refused; write 5 or 5.0, and 0.5.
    assert not _parse(text).ok


@pytest.mark.parametrize('text', ['٣.٥', '５'])
def test_non_ascii_digits_were_floats_now_parse_error(text):
    # v2.0.0: Arabic-Indic 3.5 → 3.5, full-width 5 → 5.0. Now refused.
    assert not _parse(text).ok


@pytest.mark.parametrize('text, expected', [('0', 0), ('1', 1)])
def test_zero_and_one_were_floats_now_int_not_bool(text, expected):
    # v2.0.0: 0/1 in a boolean policy → 0.0/1.0. Now int 0/1, never
    # True/False (the type check is the validator's, in a later change).
    v = _value(text, 'boolean')
    assert type(v) is int and v == expected


def test_policy_type_with_keyword_prefix_was_parse_error_now_id():
    # v2.0.0: 'integerCodes' failed ('integer' matched its prefix).
    result = _parse('"x"', 'integerCodes')
    assert result.ok, result.errors
    assert result.model.elements[0].policy_type == 'integerCodes'


def test_date_was_parse_error_now_date():
    # v2.0.0: 2026-11-30 failed (float 2026, then a stray -11-30).
    v = _value('2026-11-30', 'date')
    assert isinstance(v, Date) and v.value == '2026-11-30'
