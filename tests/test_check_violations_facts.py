"""
2.1.0-21 — facts on POST /check-violations.

An optional JSON body {"facts": {...}} carries the values the adapter
reports for the standing duties' keeps conditions, as text. The response
adds standing: [{token, holder, verdict, text}], with verdict kept,
breached, met or not judged, built from the engine's structured report
(not from the effect lines). Without a body, or with no facts, the route
behaves as before; a naive as_at is still a 422; a JSON number fact is not
established. Facts are not stored.

A test-only scenario with two standing duties and a +10:00 clock is
installed with monkeypatch; the endpoint function is called directly.

Layer 3 (API) tests per tests/README.md's strategy.
"""
import contextlib
import io
from datetime import timedelta, timezone

import pytest
from fastapi import HTTPException

import el_api
from el_api import CheckViolationsRequest
from el_engine import DeadlineClock
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


CLOCK = DeadlineClock(utc_offset=timezone(timedelta(hours=10)))

_SPEC = """enterprise specification FactsProbe
policy MinimumCover : amount { initial_value: 20000000 AUD }
policy MaximumShare : percentage { initial_value: 10% }
party Supplier { holds keepCover holds keepShare }
burden keepCover { standing keeps: "insurance cover" >= MinimumCover ends_at: 2027-06-30 state: active }
burden keepShare { standing keeps: "subcontract share" <= MaximumShare ends_at: 2027-06-30 state: active }
community Contract { objective: "o" Supplier fills r role r { action file { actor: r } } }
"""

GOOD = {"insurance cover": "25000000.00 AUD", "subcontract share": "8.5%"}


@pytest.fixture
def api(monkeypatch):
    model = _quiet(parse_string, _SPEC, validate=False).model
    monkeypatch.setitem(el_api._SCENARIO_BUILDERS, "facts_probe",
                        lambda: _quiet(Runtime.build_from_spec, model))
    monkeypatch.setitem(el_api._SCENARIO_CLOCK, "facts_probe", CLOCK)
    monkeypatch.setattr(el_api, "_active_scenario", "facts_probe")
    monkeypatch.setattr(el_api, "_active_community", "Contract")
    monkeypatch.setattr(el_api, "_runtime", el_api._new_runtime("facts_probe"))
    return el_api


def _check(api, as_at=None, facts=None, body=True):
    return _quiet(api.check_violations_endpoint, as_at,
                  CheckViolationsRequest(facts=facts or {}) if body else None)


def _verdicts(resp):
    return [(s.token, s.holder, s.verdict, s.text) for s in resp.standing]


def test_route_binds_as_at_as_query_and_facts_as_optional_body():
    route = next(r for r in el_api.app.routes if getattr(r, "path", None) == "/check-violations")
    assert [p.name for p in route.dependant.query_params] == ["as_at"]
    assert [(p.name, p.field_info.is_required()) for p in route.dependant.body_params] == [("body", False)]


def test_kept_and_breached(api):
    resp = _check(api, "2027-01-01T09:00+10:00",
                  {"insurance cover": "25000000.00 AUD", "subcontract share": "12%"})
    assert _verdicts(resp) == [
        ("keepCover", "Supplier", "kept",
         "'insurance cover' 25000000.00 AUD >= 20000000 AUD (MinimumCover)"),
        ("keepShare", "Supplier", "breached", "'subcontract share' 12% <= 10% (MaximumShare)"),
    ]
    assert resp.violations == ["keepShare"]


def test_met_at_the_end(api):
    resp = _check(api, "2027-07-01T00:00+10:00", GOOD)
    assert [(s.token, s.verdict, s.text) for s in resp.standing] == [
        ("keepCover", "met", "ends_at 2027-07-01T00:00:00+10:00"),
        ("keepShare", "met", "ends_at 2027-07-01T00:00:00+10:00"),
    ]


@pytest.mark.parametrize("body", [True, False])
def test_no_facts_not_judged(api, body):
    resp = _check(api, "2027-01-01T09:00+10:00", None, body=body)
    assert [(s.token, s.verdict, s.text) for s in resp.standing] == [
        ("keepCover", "not judged", "'insurance cover' not reported"),
        ("keepShare", "not judged", "'subcontract share' not reported"),
    ]
    assert resp.violations == []


def test_json_number_fact_is_not_established(api):
    resp = _check(api, "2027-01-01T09:00+10:00",
                  {"insurance cover": 25000000, "subcontract share": "8.5%"})
    cover = next(s for s in resp.standing if s.token == "keepCover")
    assert cover.verdict == "not judged"
    assert cover.text == ("'insurance cover' reported a value of type int, not text; send text, "
                          "e.g. \"25000000.00 AUD\"")


def test_no_as_at_not_judged(api):
    resp = _check(api, None, GOOD)
    assert {s.text for s in resp.standing} == {"term end, no as_at"}


def test_naive_as_at_still_422(api):
    entries = len(api._runtime._ledger)
    with pytest.raises(HTTPException) as exc:
        _check(api, "2027-01-01T09:00", GOOD)
    assert exc.value.status_code == 422 and len(api._runtime._ledger) == entries


def test_facts_are_not_stored(api):
    _check(api, "2027-01-01T09:00+10:00", GOOD)
    resp = _check(api, "2027-01-02T09:00+10:00", None, body=False)
    assert {s.verdict for s in resp.standing} == {"not judged"}


def test_verdicts_match_the_effect_lines(api):
    resp = _check(api, "2027-01-01T09:00+10:00", GOOD)
    assert len(resp.standing) == len(resp.effects) == 2
    assert all(e.startswith(("kept", "breached", "term ended", "not judged")) for e in resp.effects)


def test_body_parses_from_json():
    body = CheckViolationsRequest.model_validate_json('{"facts": {"insurance cover": "1 AUD"}}')
    assert body.facts == {"insurance cover": "1 AUD"}
    assert CheckViolationsRequest.model_validate_json("{}").facts == {}


def test_shipped_scenario_without_body_unchanged():
    resp = _quiet(el_api.check_violations_endpoint)
    assert resp.standing == []
