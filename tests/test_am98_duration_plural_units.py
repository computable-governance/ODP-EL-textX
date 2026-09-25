"""
AM-98 — DurationUnit lists plurals first so plural units parse.

Grammar: DurationUnit previously listed each singular before its plural
('hour' | 'hours' ...), so PEG ordered choice matched 'hour' inside
'hours' and then failed on the trailing 's'. Every plural unit was
unparseable in Policy.initial_value and NormativePolicy.review_cycle
(docs/el_grammar_amendments.md, AM-98).

Each test asserts the parsed unit string, not just that parsing
succeeded, so a future reorder can't silently collapse a plural onto
its singular.

Minimal Layer 1 (grammar/parse) tests per tests/README.md's strategy.
"""
from el_parser import parse_string


_HEADER = 'enterprise specification Probe\n\n'


def _policy_value(value):
    src = _HEADER + (
        'policy ProbePolicy : duration {\n'
        f'    initial_value: {value}\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors
    return result.model.elements[0].initial_value


def _review_cycle(value):
    src = _HEADER + (
        'normative_policy ProbeAct {\n'
        '    source: "Probe Act 2026"\n'
        '    kind: legislation\n'
        f'    review_cycle: {value}\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors
    return result.model.elements[0].review_cycle


def test_policy_initial_value_plural_hours():
    duration = _policy_value('24 hours')
    assert duration.value == 24
    assert duration.unit == 'hours'


def test_policy_initial_value_singular_hour():
    duration = _policy_value('1 hour')
    assert duration.value == 1
    assert duration.unit == 'hour'


def test_normative_policy_review_cycle_plural_months():
    duration = _review_cycle('12 months')
    assert duration.value == 12
    assert duration.unit == 'months'


def test_normative_policy_review_cycle_singular_month():
    duration = _review_cycle('1 month')
    assert duration.value == 1
    assert duration.unit == 'month'
