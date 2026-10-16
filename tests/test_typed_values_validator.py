"""
2.1.0-2 — the five typed-value validator rules.

  policy-value-type  a value matches its policy's keyword type
  calendar-date      a Date (or an Instant's date part) is a calendar date
  instant-valid      an Instant's time of day and UTC offset are in range
  range-ends         a range's ends are of one kind, in order
  currency-code      an Amount's code has the ISO 4217 form (A-Z x 3)

Values are checked in initial_value, in list envelopes and at range ends,
for Policy and NormativePolicy. Envelope membership is not checked in
2.1.0-2. Every message ends "(clause to be confirmed)".

Also scans grammar/v2/el_grammar.tx for every quoted three-letter keyword
and asserts none can directly follow a PolicyValue position, so a
lower-case currency code can never swallow a keyword.

Layer 2 (validator) tests per tests/README.md's strategy.
"""
import re
from pathlib import Path

import pytest

from el_parser import parse_string


_HEADER = 'enterprise specification Probe\n\n'
_CITATION = '(clause to be confirmed)'
_RULES = ('policy-value-type', 'calendar-date', 'instant-valid',
          'range-ends', 'currency-code')


def _errors(policy_type, value, envelope=None, name='P'):
    env = f'    envelope {{ {envelope} }}\n' if envelope else ''
    src = _HEADER + (
        f'policy {name} : {policy_type} {{\n'
        f'    initial_value: {value}\n'
        f'{env}'
        '}\n'
    )
    result = parse_string(src)
    assert result.model is not None, result.errors
    return [e for e in result.errors if e.startswith(tuple(f'[{r}]' for r in _RULES))]


def _rules(errors):
    return [e[1:e.index(']')] for e in errors]


# ── policy-value-type ────────────────────────────────────────────────────

@pytest.mark.parametrize('policy_type, value', [
    ('integer', '5'), ('integer', '-3'), ('integer', '7..10'),
    ('decimal', '4.5'), ('decimal', '4'), ('decimal', '1..2'),
    ('number', '4.5'), ('number', '4'),
    ('percentage', '4.25%'), ('amount', '250.00 AUD'),
    ('string', '"five"'), ('boolean', 'true'), ('duration', '5 days'),
    ('date', '2026-11-30'), ('instant', '2026-11-30T17:00+10:00'),
])
def test_value_matches_type(policy_type, value):
    assert _errors(policy_type, value) == []


@pytest.mark.parametrize('policy_type, value, text, article', [
    ('integer', '4.5', '4.5', 'an'),
    ('integer', '"five"', '"five"', 'an'),
    ('decimal', '4.5%', '4.5%', 'a'),
    ('percentage', '4.5', '4.5', 'a'),
    ('amount', '250.00', '250.00', 'an'),
    ('boolean', '1', '1', 'a'),
    ('date', '2026-11-30T17:00Z', '2026-11-30T17:00Z', 'a'),
    ('instant', '2026-11-30', '2026-11-30', 'an'),
    ('duration', '60', '60', 'a'),
    ('string', '5', '5', 'a'),
])
def test_value_does_not_match_type(policy_type, value, text, article):
    errors = _errors(policy_type, value, name='MaxRetries')
    assert errors == [
        f"[policy-value-type] Policy 'MaxRetries': initial_value {text} is not "
        f"{article} {policy_type} value. {_CITATION}"
    ]


def test_type_checked_in_list_envelope_and_range_ends():
    errors = _errors('integer', '5', 'one of [1, 2.5] range of [1 to 9.5]')
    assert errors == [
        f"[policy-value-type] Policy 'P': envelope 'one of' value 2.5 is not "
        f"an integer value. {_CITATION}",
        f"[policy-value-type] Policy 'P': envelope range high end 9.5 is not "
        f"an integer value. {_CITATION}",
    ]


def test_id_type_not_checked():
    assert _errors('Options', '4.5', 'one of [1, "x", 2026-11-30]') == []


def test_envelope_membership_not_checked():
    assert _errors('integer', '50', 'one of [1, 2, 3] range of [1 to 10]') == []


# ── calendar-date ────────────────────────────────────────────────────────

@pytest.mark.parametrize('value', ['2026-02-30', '2026-13-01', '2026-00-10',
                                   '2025-02-29', '0000-01-01'])
def test_not_a_calendar_date(value):
    assert _errors('date', value, name='Cutoff') == [
        f"[calendar-date] Policy 'Cutoff': initial_value {value} is not a "
        f"calendar date. {_CITATION}"
    ]


def test_leap_day_is_a_calendar_date():
    assert _errors('date', '2028-02-29') == []


def test_instant_date_part_is_checked():
    assert _rules(_errors('instant', '2026-02-30T10:00Z')) == ['calendar-date']


# ── instant-valid ────────────────────────────────────────────────────────

@pytest.mark.parametrize('value, reason', [
    ('2026-11-30T24:00Z', 'not a time of day'),
    ('2026-11-30T17:60Z', 'not a time of day'),
    ('2026-11-30T17:00:30Z', 'not a whole minute'),
    ('2026-11-30T17:00+24:00', 'not a UTC offset'),
    ('2026-11-30T17:00+10:60', 'not a UTC offset'),
    ('2026-11-30T17:00-00:00', '-00:00 is not a UTC offset'),
])
def test_instant_out_of_range(value, reason):
    assert _errors('instant', value, name='Opens') == [
        f"[instant-valid] Policy 'Opens': initial_value {value} is not an "
        f"instant: {reason}. {_CITATION}"
    ]


@pytest.mark.parametrize('value', ['2026-11-30T23:59:00Z', '2026-11-30T00:00+00:00',
                                   '2026-11-30T17:00-23:59', '2026-11-30T17:00+23:59'])
def test_instant_in_range(value):
    assert _errors('instant', value) == []


# ── range-ends ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('policy_type, rng', [
    ('integer', '1 to 10'),
    ('decimal', '1 to 2.5'),                      # integer and decimal: one kind
    ('decimal', '2.5 to 2.50'),                   # equal ends
    ('percentage', '4.5% to 6%'),
    ('amount', '10.00 AUD to 20 AUD'),
    ('duration', '1 day to 24 hours'),            # equal through the unit table
    ('duration', '4 weeks to 1 month'),           # a month is 30 days
    ('date', '2026-01-01 to 2026-11-30'),
    ('instant', '2026-11-30T17:00+10:00 to 2026-11-30T07:00Z'),  # same moment
    ('instant', '2026-11-30T17:00+10:00 to 2026-11-30T07:01Z'),
])
def test_range_in_order(policy_type, rng):
    value = rng.split(' to ')[0]
    assert _errors(policy_type, value, f'range of [{rng}]') == []


@pytest.mark.parametrize('policy_type, rng', [
    ('integer', '10 to 1'),
    ('percentage', '9% to 4.5%'),
    ('amount', '20.00 AUD to 10.00 AUD'),
    ('duration', '1 month to 29 days'),
    ('date', '2026-11-30 to 2026-01-01'),
    ('instant', '2026-11-30T17:01+10:00 to 2026-11-30T07:00Z'),
])
def test_range_low_above_high(policy_type, rng):
    value = rng.split(' to ')[1]
    assert _errors(policy_type, value, f'range of [{rng}]', name='Rate') == [
        f"[range-ends] Policy 'Rate': range [{rng}] has its low end above its "
        f"high end. {_CITATION}"
    ]


@pytest.mark.parametrize('rng, kinds', [
    ('60 days to 6%', 'duration and percentage'),
    ('2026-01-01 to 2026-11-30T17:00Z', 'date and instant'),
    ('5 to 6%', 'integer and percentage'),
    ('5.00 AUD to 6', 'amount and integer'),
])
def test_range_mixed_kinds(rng, kinds):
    errors = _errors('Window', '1', f'range of [{rng}]', name='Window')
    assert errors == [
        f"[range-ends] Policy 'Window': range [{rng}] has ends of different "
        f"kinds ({kinds}). {_CITATION}"
    ]


def test_range_mixed_currencies_never_converted():
    errors = _errors('amount', '10.00 AUD', 'range of [10.00 AUD to 20.00 NZD]',
                     name='Fee')
    assert errors == [
        f"[range-ends] Policy 'Fee': range [10.00 AUD to 20.00 NZD] has ends in "
        f"different currencies (AUD and NZD); amounts are compared only within "
        f"one currency. {_CITATION}"
    ]


@pytest.mark.parametrize('rng, rule', [
    ('2026-02-30 to 2026-01-01', 'calendar-date'),
    ('2026-11-30T24:00Z to 2026-11-30T07:00Z', 'instant-valid'),
])
def test_invalid_end_reported_once(rng, rule):
    # The range is out of order too, but the faulty end is reported once,
    # by its own rule, and range-ends skips it.
    assert _rules(_errors('Window', '1', f'range of [{rng}]')) == [rule]


# ── currency-code ────────────────────────────────────────────────────────

def test_lower_case_code():
    assert _errors('amount', '250.00 aud', name='Fee') == [
        f"[currency-code] Policy 'Fee': initial_value 250.00 aud has currency "
        f"code 'aud', not three upper-case letters A-Z (ISO 4217 form). "
        f"{_CITATION}"
    ]


def test_mixed_case_code():
    assert _rules(_errors('amount', '250 Aud')) == ['currency-code']


@pytest.mark.parametrize('value, hint', [
    ('5 min', '5 minutes'), ('5 hrs', '5 hours'), ('1 hrs', '1 hour'),
    ('3 wks', '3 weeks'), ('2 yrs', '2 years'), ('5 Min', '5 minutes'),
])
def test_mistyped_duration_unit_gets_a_hint(value, hint):
    errors = _errors('duration', value)
    assert any(e.startswith('[currency-code]') and
               f'; if you meant a duration, write it as {hint}. {_CITATION}' in e
               for e in errors), errors


def test_decimal_mistyped_duration_hint():
    errors = _errors('amount', '2.5 hrs')
    assert errors[0].endswith(
        f"; if you meant a duration, write it as a whole number of hours. {_CITATION}")


def test_upper_case_code_accepted_without_list_membership():
    # ISO 4217 form only; 'XYZ' is not looked up in the code list.
    assert _errors('amount', '1 XYZ') == []


def test_currency_code_checked_in_envelope():
    errors = _errors('amount', '5 AUD', 'one of [5 AUD, 7 nzd]')
    assert _rules(errors) == ['currency-code']
    assert "envelope 'one of' value 7 nzd" in errors[0]


# ── NormativePolicy ──────────────────────────────────────────────────────

def _normative_errors(type_line, value):
    src = _HEADER + (
        'normative_policy Schedule {\n'
        '    source: "Schedule of fees"\n'
        '    kind: contractual\n'
        f'{type_line}'
        f'    initial_value: {value}\n'
        '}\n'
    )
    result = parse_string(src)
    assert result.model is not None, result.errors
    return [e for e in result.errors if e.startswith(tuple(f'[{r}]' for r in _RULES))]


def test_normative_policy_typed():
    assert _normative_errors('    type: amount\n', '250.00 AUD') == []
    assert _normative_errors('    type: integer\n', '2.5') == [
        f"[policy-value-type] NormativePolicy 'Schedule': initial_value 2.5 is "
        f"not an integer value. {_CITATION}"
    ]


def test_normative_policy_untyped_value_form_checked():
    assert _rules(_normative_errors('', '2026-02-30')) == ['calendar-date']


# ── Shipped scenarios unaffected ─────────────────────────────────────────

_REPO = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize('path', sorted(
    p for p in (_REPO / 'scenarios').rglob('*.el')
    if p.name != 'ecommerce_scenario.el'   # does not parse (known)
), ids=lambda p: p.name)
def test_shipped_scenarios_pass_typed_checks(path):
    from el_parser import parse
    result = parse(path)
    assert result.model is not None
    assert [e for e in result.errors if e.startswith(tuple(f'[{r}]' for r in _RULES))] == []


# ── No three-letter keyword can follow a PolicyValue ─────────────────────

_GRAMMAR = (_REPO / 'grammar' / 'v2' / 'el_grammar.tx').read_text()
_TOKEN_RE = re.compile(r"'[^']*'|\w+\s*[+?]?=\s*\w+|\w+|[()|]")


def _rule_body(name):
    m = re.search(rf'(?ms)^{name}\s*:(.*?);[ \t]*$', _GRAMMAR)
    assert m, name
    return m.group(1)


def _top_alternatives(body):
    alts, depth, start = [], 0, 0
    for i, ch in enumerate(body):
        depth += {'(': 1, ')': -1}.get(ch, 0)
        if ch == '|' and depth == 0:
            alts.append(body[start:i])
            start = i + 1
    return alts + [body[start:]]


def _first_terminals(name, seen=()):
    """Keywords that can begin a match of grammar rule `name`."""
    if name in ('ID', 'STRING', 'INT') or name in seen:
        return set()
    out = set()
    for alt in _top_alternatives(_rule_body(name)):
        tok = _TOKEN_RE.findall(alt.replace('(', ' ').strip())[0]
        if tok.startswith("'"):
            out.add(tok.strip("'"))
        else:
            out |= _first_terminals(tok.split('=')[-1].strip(), seen + (name,))
    return out


def _followers(remainder):
    """Keywords that can come first in `remainder`: the first token of each
    optional group, and every token up to and including the first
    mandatory one at the top level."""
    # Drop the ')?' that closes an optional group holding the value itself.
    remainder = re.sub(r'^\s*\)[?*+]?', '', remainder)
    out, depth, take = set(), 0, True
    for tok in _TOKEN_RE.findall(remainder):
        if tok == '(':
            depth += 1
            take = depth == 1
            continue
        if tok == ')':
            depth -= 1
            take = depth == 0
            continue
        if tok == '|' or not take:
            continue
        take = False
        if tok.startswith("'"):
            out.add(tok.strip("'"))
            if depth == 0:
                return out           # a mandatory keyword ends the followers
        elif depth >= 1:
            out |= _first_terminals(tok.split('=')[-1].strip())
    return out


def _policy_value_followers():
    followers = set()
    for rule in ('Policy', 'NormativePolicy'):
        body = _rule_body(rule)
        followers |= _followers(body.split('initial_value=PolicyValue', 1)[1])
    envelope = _rule_body('EnvelopeRule')
    followers |= {sep for sep in re.findall(r"PolicyValue\[('[^']*')\]", envelope)}
    followers |= set(re.findall(r"=(?:PolicyValue|RangeBound)(?:\[[^\]]*\])?\s*('[^']*')",
                                envelope))
    return {f.strip("'") for f in followers}


def test_no_three_letter_keyword_follows_a_policy_value():
    three_letter = set(re.findall(r"'([A-Za-z]{3})'", _GRAMMAR))
    followers = _policy_value_followers()
    # Sanity: the scan finds the known followers in both bodies and envelopes.
    assert {'envelope', 'obligation', 'affects', 'setting_behaviour',
            'enforcement', 'review_cycle', 'policy_setting_behaviour',
            '}', ',', ']', 'to'} <= followers, followers
    assert three_letter, 'scan found no three-letter keywords'
    assert three_letter & followers == set()
