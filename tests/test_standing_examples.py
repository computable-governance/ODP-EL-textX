"""
2.1.0-19 — shared standing-duty examples in
tests/examples/standing/.

As in tests/examples/typed_values/: the file name prefix is the contract
and the first line is '// expect: <outcome>'.
  ok_*.el       parses and validates with no error, and no warning but
                [W-standing-not-modelled] (2.1.0-20);
  invalid_*.el  parses, and the 2.1.0-19 rules report exactly the rule
                named on the first line.

Layer 2 (validator) tests per tests/README.md's strategy.
"""
import re
from pathlib import Path

import pytest

from el_parser import parse


_EXAMPLES = Path(__file__).resolve().parent / "examples" / "standing"
_RULES = ("standing-fields", "standing-in-group", "term-end-type")
_FILES = sorted(_EXAMPLES.glob("*.el"))


def _expect(path):
    m = re.match(r"// expect: (\S+)", path.read_text().splitlines()[0])
    assert m, f"{path.name}: first line must be '// expect: <outcome>'"
    return m.group(1)


def _rules(errors):
    return {e[1:e.index("]")] for e in errors if e.startswith(tuple(f"[{r}]" for r in _RULES))}


def test_example_set_covers_every_rule():
    assert any(p.name.startswith("ok_") for p in _FILES)
    assert {_expect(p) for p in _FILES if p.name.startswith("invalid_")} == set(_RULES)


@pytest.mark.parametrize("path", [p for p in _FILES if p.name.startswith("ok_")],
                         ids=lambda p: p.name)
def test_ok_example(path):
    assert _expect(path) == "ok"
    result = parse(path)
    assert result.ok, result.errors
    # 2.1.0-20: every standing duty carries [W-standing-not-modelled] (the
    # verifier does not model it); no other warning is expected.
    assert result.errors == []
    assert [w for w in result.warnings if not w.startswith("[W-standing-not-modelled]")] == []


@pytest.mark.parametrize("path", [p for p in _FILES if p.name.startswith("invalid_")],
                         ids=lambda p: p.name)
def test_invalid_example(path):
    result = parse(path)
    assert result.model is not None, result.errors
    assert _rules(result.errors) == {_expect(path)}, result.errors
