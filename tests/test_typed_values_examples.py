"""
2.1.0-4 — shared typed-value examples in tests/examples/typed_values/.

The file name prefix is the contract, and the first line of each file is
a comment '// expect: <outcome>':

  ok_*.el       parses and validates with no error or warning
                ('// expect: ok');
  invalid_*.el  parses, and the typed-value rules report exactly the rule
                named on the first line ('// expect: <rule>').

The files are self-contained so another toolchain can run the same set.

Layer 2 (validator) tests per tests/README.md's strategy.
"""
import re
from pathlib import Path

import pytest

from el_parser import parse


_EXAMPLES = Path(__file__).resolve().parent / 'examples' / 'typed_values'
_TYPED_RULES = ('policy-value-type', 'calendar-date', 'instant-valid',
                'range-ends', 'currency-code')


def _expect(path):
    m = re.match(r'// expect: (\S+)', path.read_text().splitlines()[0])
    assert m, f'{path.name}: first line must be "// expect: <outcome>"'
    return m.group(1)


def _typed_rules(errors):
    return {e[1:e.index(']')] for e in errors
            if e.startswith(tuple(f'[{r}]' for r in _TYPED_RULES))}


_FILES = sorted(_EXAMPLES.glob('*.el'))


def test_example_set_covers_every_rule():
    assert any(p.name.startswith('ok_') for p in _FILES)
    expected = {_expect(p) for p in _FILES if p.name.startswith('invalid_')}
    assert expected == set(_TYPED_RULES)


@pytest.mark.parametrize('path', [p for p in _FILES if p.name.startswith('ok_')],
                         ids=lambda p: p.name)
def test_ok_example(path):
    assert _expect(path) == 'ok'
    result = parse(path)
    assert result.ok, result.errors
    assert result.errors == [] and result.warnings == []


@pytest.mark.parametrize('path', [p for p in _FILES if p.name.startswith('invalid_')],
                         ids=lambda p: p.name)
def test_invalid_example(path):
    result = parse(path)
    assert result.model is not None, result.errors
    assert _typed_rules(result.errors) == {_expect(path)}, result.errors
