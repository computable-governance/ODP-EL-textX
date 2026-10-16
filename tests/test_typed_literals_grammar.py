"""
2.1.0-1 — typed policy literals in grammar/v2/el_grammar.tx.

Covers the new PolicyValue literals (Instant, Date, Amount, Percentage,
DecimalNumber, IntegerNumber), their order in PolicyValue, the plain
number rules (ASCII digits, minus only, no exponent, no '5.' or '.5',
no grouping), the PolicyType keywords, and the 'range of [a to b]'
envelope rule with its RangeBound ends.

Value types are adopted from existing standards: Instant and Date from
ISO 8601 (extended format, strict profile; part and edition to be
confirmed), the Amount currency code form from ISO 4217 (edition to be
confirmed). Value form checks (calendar dates, instant field ranges,
upper-case currency codes) belong to the validator, not to these tests.

Minimal Layer 1 (grammar/parse) tests per tests/README.md's strategy.
"""
from decimal import Decimal

import pytest

from el_domain import Amount, Date, Duration, Instant, NumberInterval, Percentage
from el_parser import parse_string


_HEADER = 'enterprise specification Probe\n\n'


def _parse_policy(value, policy_type='integer', tail=''):
    src = _HEADER + (
        f'policy ProbePolicy : {policy_type} {{\n'
        f'    initial_value: {value}\n'
        f'{tail}'
        '}\n'
    )
    return parse_string(src, validate=False)


def _value(value, policy_type='integer'):
    result = _parse_policy(value, policy_type)
    assert result.ok, result.errors
    return result.model.elements[0].initial_value


def _envelope_rule(rule_text):
    result = _parse_policy('5', tail=f'    envelope {{ {rule_text} }}\n')
    assert result.ok, result.errors
    return result.model.elements[0].envelope.envelope_rules[0]


def _refused(value):
    result = _parse_policy(value)
    return not result.ok and result.errors[0].startswith('[SYNTAX]')


# ── Each literal parses to its class or Python type ──────────────────────

@pytest.mark.parametrize('text, expected', [
    ('5', 5), ('0', 0), ('-5', -5), ('-0', 0), ('007', 7),
])
def test_integer_is_int(text, expected):
    v = _value(text)
    assert type(v) is int
    assert v == expected


@pytest.mark.parametrize('text', ['5.25', '4.50', '-0.5', '-0.0', '0.0000001',
                                  '10000000000000000.5'])
def test_decimal_is_decimal_as_written(text):
    v = _value(text, 'decimal')
    assert type(v) is Decimal
    # Exact and as written: same digits and scale, never a binary float.
    assert v.as_tuple() == Decimal(text).as_tuple()


def test_percentage():
    v = _value('4.25%', 'percentage')
    assert isinstance(v, Percentage)
    assert v.value == Decimal('4.25') and type(v.value) is Decimal
    w = _value('6%', 'percentage')
    assert type(w.value) is int and w.value == 6


@pytest.mark.parametrize('text, value, code', [
    ('250.00 AUD', Decimal('250.00'), 'AUD'),
    ('250 aud', 250, 'aud'),          # any case here; upper case is a validator check
    ('-12.5 NZD', Decimal('-12.5'), 'NZD'),
])
def test_amount(text, value, code):
    v = _value(text, 'amount')
    assert isinstance(v, Amount)
    assert v.value == value and type(v.value) is type(value)
    assert v.code == code


def test_amount_keeps_scale():
    assert str(_value('250.00 AUD', 'amount').value) == '250.00'


def test_date_kept_as_written():
    v = _value('2026-11-30', 'date')
    assert isinstance(v, Date)
    assert v.value == '2026-11-30'


@pytest.mark.parametrize('text', [
    '2026-11-30T17:00+10:00', '2026-11-30T07:00Z', '2026-11-30T07:00:00Z',
    '2026-11-30T17:00-05:30',
])
def test_instant_kept_as_written(text):
    v = _value(text, 'instant')
    assert isinstance(v, Instant)
    assert v.value == text


# ── Literal order in PolicyValue ─────────────────────────────────────────

def test_date_is_not_read_as_integer():
    assert isinstance(_value('2026-11-30'), Date)


def test_instant_is_not_read_as_date():
    assert isinstance(_value('2026-11-30T17:00Z'), Instant)


@pytest.mark.parametrize('text', ['5 day', '5 days', '24 hours'])
def test_duration_is_not_read_as_amount(text):
    assert isinstance(_value(text, 'duration'), Duration)


def test_interval_is_not_read_as_integer():
    v = _value('7..10')
    assert isinstance(v, NumberInterval)
    assert (v.lower, v.upper) == (7, 10)


def test_percentage_is_not_read_as_decimal():
    assert isinstance(_value('4.5%'), Percentage)


def test_strings_booleans_and_names_unchanged():
    assert _value('"five"') == 'five'
    assert _value('true', 'boolean') is True
    assert _value('false', 'boolean') is False
    assert _value('someOption', 'Options') == 'someOption'


# ── Refused at parse ─────────────────────────────────────────────────────

@pytest.mark.parametrize('text', [
    '1e3', '1.5E2', '2.5e-2',           # exponent
    '+5', '+2.5', '+5%', '+5 AUD',      # leading plus on a plain number
    '5.', '.5', '1.',                   # bare dot forms
    '1,000',                            # digit grouping
    '５',                           # full-width 5
    '٣.٥',                    # Arabic-Indic 3.5
    '٣',                           # Arabic-Indic 3
    '1e3%',
    '250.00AUD',                        # code must be a separate word
    '250.00 AUDX',                      # code is exactly three letters
])
def test_number_forms_refused(text):
    assert _refused(text), text


@pytest.mark.parametrize('text', [
    '2026-11-30T17:00',                 # no offset
    '2026-11-30T17:00+1000',            # basic-format offset
    '2026-11-30T17:00:00.5Z',           # fractional seconds
    '2026-11-30T17:00[Australia/Brisbane]',  # zone name
])
def test_instant_forms_refused(text):
    assert _refused(text), text


def test_basic_format_date_is_not_a_date():
    # Only the extended format is a Date; 20261130 is the integer.
    assert _value('20261130') == 20261130


def test_non_ascii_digits_in_date_refused():
    assert _refused('٢٠٢٦-11-30')


# ── PolicyType keywords ──────────────────────────────────────────────────

@pytest.mark.parametrize('kw', ['integer', 'decimal', 'number', 'percentage',
                                'amount', 'string', 'boolean', 'duration',
                                'date', 'instant'])
def test_policy_type_keyword(kw):
    result = _parse_policy('"x"', kw)
    assert result.ok, result.errors
    assert result.model.elements[0].policy_type == kw


@pytest.mark.parametrize('name', ['integerCodes', 'dateWindows', 'amountBands'])
def test_policy_type_beginning_with_a_keyword_is_an_id(name):
    result = _parse_policy('"x"', name)
    assert result.ok, result.errors
    assert result.model.elements[0].policy_type == name


# ── Envelope rules: range form and list forms ────────────────────────────

def test_range_of_numbers():
    rule = _envelope_rule('range of [1 to 2.5]')
    assert rule.kind == 'range'
    assert rule.values == []
    assert rule.lower == 1 and type(rule.lower) is int
    assert rule.upper == Decimal('2.5') and type(rule.upper) is Decimal


@pytest.mark.parametrize('text, lower_cls, upper_cls', [
    ('range of [2026-01-01 to 2026-11-30]', Date, Date),
    ('range of [2026-11-30T17:00+10:00 to 2026-11-30T07:00Z]', Instant, Instant),
    ('range of [60 days to 90 days]', Duration, Duration),
    ('range of [10.00 AUD to 20 AUD]', Amount, Amount),
    ('range of [4.5% to 6%]', Percentage, Percentage),
    ('range of [60 days to 6%]', Duration, Percentage),   # mixed kinds parse
])
def test_range_bound_kinds(text, lower_cls, upper_cls):
    rule = _envelope_rule(text)
    assert isinstance(rule.lower, lower_cls)
    assert isinstance(rule.upper, upper_cls)


@pytest.mark.parametrize('text', [
    'range of [7..10 to 12]',           # no interval end
    'range of ["a" to "b"]',            # no string end
    'range of [true to false]',         # no boolean end
    'range of [low to high]',           # no option name end
    'range of [+1 to 2]',               # no plus
    'range of [1e3 to 2000]',           # no exponent
])
def test_range_bound_refused(text):
    result = _parse_policy('5', tail=f'    envelope {{ {text} }}\n')
    assert not result.ok


def test_list_rule_keeps_values_and_has_no_ends():
    rule = _envelope_rule('one of [1, 2.5, 3%, 2026-11-30, 5 AUD]')
    assert rule.kind == 'one'
    assert rule.lower is None and rule.upper is None
    kinds = [type(v) for v in rule.values]
    assert kinds == [int, Decimal, Percentage, Date, Amount]


# ── An amount's code never takes a following keyword ─────────────────────

def test_lower_case_code_does_not_swallow_following_keyword():
    tail = (
        '    envelope { one of [5 aud, 7 aud] }\n'
        '    affects role SomeRole\n'
        '    enforcement unpoliced\n'
    )
    result = _parse_policy('5 aud', 'amount', tail)
    assert result.ok, result.errors
    policy = result.model.elements[0]
    assert policy.initial_value.code == 'aud'
    assert [v.code for v in policy.envelope.envelope_rules[0].values] == ['aud', 'aud']
    assert policy.enforcement.unpoliced is True


def test_integer_followed_by_keyword_is_not_an_amount():
    result = _parse_policy('5', tail='    enforcement unpoliced\n')
    assert result.ok, result.errors
    assert result.model.elements[0].initial_value == 5


# ── NormativePolicy shares PolicyValue ───────────────────────────────────

def test_normative_policy_initial_value_typed():
    src = _HEADER + (
        'normative_policy Fees {\n'
        '    source: "Schedule"\n'
        '    kind: contractual\n'
        '    type: amount\n'
        '    initial_value: 250.00 AUD\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors
    v = result.model.elements[0].initial_value
    assert isinstance(v, Amount) and v.value == Decimal('250.00')
