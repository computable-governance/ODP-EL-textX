"""
AM-43 — optional url field on NormativePolicy (§6.5 citation identity).

Grammar: NormativePolicy gained `('url' ':' url=STRING)?`, placed directly
after `source` — the field it complements: `source` is the citation's
descriptive text, `url` is an optional link to it. Plain STRING field, no
new sub-rule, no object processor — confirmed by smoke test before writing
these, same discipline as AM-42's plain-scalar fields.

Note on absent-value shape: textX resolves an absent optional STRING match
to `''` (empty string), not `None` — matching the pre-existing behaviour of
NormativePolicy's other optional STRING field, `description` (confirmed by
direct smoke test). `url`'s dataclass default is `Optional[str] = None`,
but that default is never actually observed at parse time for a real
grammar match; only relevant if a NormativePolicy is constructed directly
in Python without going through the parser. `''` is falsy in both Python
(`if p.url:`) and JS (`if (g.url)`), so downstream present/absent checks
work correctly either way.

Minimal Layer 1 (grammar/parse) tests per tests/README.md's strategy —
throwaway fixtures, plus the three real referral-scenario citations.
"""
from pathlib import Path

from el_parser import parse, parse_string


_HEADER = 'enterprise specification UrlProbe\n\n'

_SCENARIO = Path(__file__).resolve().parent.parent / "scenarios" / "referral" / "referral_scenario.el"


def _find(model, cls_name, name=None):
    matches = [e for e in model.elements if type(e).__name__ == cls_name]
    if name is None:
        return matches
    return next(e for e in matches if e.name == name)


def test_url_present_resolves():
    src = _HEADER + (
        'normative_policy TestAct {\n'
        '    source: "Test Act 2026"\n'
        '    url: "https://example.org/test-act"\n'
        '    kind: legislation\n'
        '}\n'
    )
    result = parse_string(src, validate=False)
    assert result.ok, result.errors

    policy = _find(result.model, 'NormativePolicy', 'TestAct')
    assert policy.url == 'https://example.org/test-act'


def test_url_absent_defaults_to_empty_string():
    """url is optional — a NormativePolicy without it must not error, and
    .url must resolve the same way description already does when absent
    (empty string, not None — textX's behaviour for an unmatched optional
    STRING attribute)."""
    src = _HEADER + (
        'normative_policy TestAct {\n'
        '    source: "Test Act 2026"\n'
        '    kind: guideline\n'
        '}\n'
    )
    result = parse_string(src, validate=True)
    assert result.ok, result.errors

    policy = _find(result.model, 'NormativePolicy', 'TestAct')
    assert policy.url == ''


def test_referral_scenario_citations_have_real_urls():
    """AuthorshipBasis, ConsentRightsBasis, ReferralEpisodeAccountability
    (the three citations reachable by the board's Obligations panel, per
    docs/Board_NormativePolicy_Display_Investigation_2026-07-22.md's
    combined next-session scope addendum) each declare a real url."""
    result = parse(_SCENARIO, validate=True)
    assert result.ok, result.errors

    expected = {
        'AuthorshipBasis': 'https://legislation.nsw.gov.au/view/pdf/asmade/act-2002-71',
        'ConsentRightsBasis': 'https://www.legislation.gov.au/C2004A03712/latest',
        'ReferralEpisodeAccountability': 'https://www.safetyandquality.gov.au/clinical-topics/clinical-governance/2026-national-model',
    }
    for name, url in expected.items():
        policy = _find(result.model, 'NormativePolicy', name)
        assert policy.url == url
