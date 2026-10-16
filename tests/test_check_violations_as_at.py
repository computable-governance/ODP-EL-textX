"""
2.1.0-9 — `as_at` on POST /check-violations.

`as_at` (query, optional) is the wall-clock time of the check, ISO 8601
with a UTC offset. A burden whose deadline is a date is judged against it
under the scenario's DeadlineClock (`_SCENARIO_CLOCK`), never against the
tick. 422 for an unparseable value, a value with no offset, or one earlier
than the last accepted, with nothing ledgered. The response echoes `as_at`
and lists `not_judged` date burdens. No shipped scenario has a clock.

A test-only scenario (a date burden, a +10:00 clock) is installed with
monkeypatch; the endpoint function is called directly, as in the other
endpoint tests. The query-string test decodes with urllib, as the server
does, so an unencoded '+' arrives as a space.

Layer 3 (API) tests per tests/README.md's strategy.
"""
import contextlib
import io
from datetime import timedelta, timezone
from urllib.parse import parse_qsl

import pytest
from fastapi import HTTPException

import el_api
from el_engine import DeadlineClock
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


CLOCK = DeadlineClock(utc_offset=timezone(timedelta(hours=10)))

_SPEC = """
enterprise specification DateApiProbe

party Holder {
    holds byDate
}

burden byDate { for_action: "file" state: active deadline: "by 2026-11-30" discharge_mode: eventual }
commitment C1 { by: Holder obligation: "file" creates_burden: byDate }

community DateCommunity {
    objective: "probe"
}
"""


@pytest.fixture
def api(monkeypatch):
    spec = _quiet(parse_string, _SPEC, validate=False).model

    def build():
        return _quiet(Runtime.build_from_spec, spec)

    monkeypatch.setitem(el_api._SCENARIO_BUILDERS, "date_probe", build)
    monkeypatch.setitem(el_api._SCENARIO_CLOCK, "date_probe", CLOCK)
    monkeypatch.setattr(el_api, "_active_scenario", "date_probe")
    monkeypatch.setattr(el_api, "_active_community", "DateCommunity")
    monkeypatch.setattr(el_api, "_runtime", el_api._new_runtime("date_probe"))
    return el_api


def _check(api, as_at=None):
    return _quiet(api.check_violations_endpoint, as_at)


def _refused(api, as_at):
    entries = len(api._runtime._ledger)
    with pytest.raises(HTTPException) as exc:
        _check(api, as_at)
    assert exc.value.status_code == 422
    assert len(api._runtime._ledger) == entries     # nothing ledgered
    return exc.value.detail


def test_route_takes_as_at():
    route = next(r for r in el_api.app.routes if getattr(r, "path", None) == "/check-violations")
    assert route.endpoint is el_api.check_violations_endpoint
    assert [p.name for p in route.dependant.query_params] == ["as_at"]


def test_runtime_gets_the_scenario_clock(api):
    assert api._runtime.clock is CLOCK
    api.reset_runtime()
    assert api._runtime.clock is CLOCK


def test_end_of_day_boundary(api):
    resp = _check(api, "2026-11-30T23:59+10:00")
    assert resp.outcome == "ok" and resp.violations == []
    assert resp.as_at == "2026-11-30T23:59:00+10:00"
    assert resp.not_judged == []

    resp = _check(api, "2026-12-01T00:00+10:00")
    assert resp.violations == ["byDate"]
    assert resp.effects == [
        "violated 'byDate' held by 'Holder' (due 2026-12-01T00:00:00+10:00; "
        "as_at 2026-12-01T00:00:00+10:00; activated at tick 0)"]


def test_trailing_z_accepted(api):
    resp = _check(api, "2026-11-30T14:00Z")     # = 2026-12-01T00:00+10:00
    assert resp.violations == ["byDate"]
    assert resp.as_at == "2026-11-30T14:00:00+00:00"


def test_without_as_at_not_judged(api):
    resp = _check(api)
    assert resp.as_at is None and resp.violations == []
    assert [(e.token, e.holder, e.reason) for e in resp.not_judged] == [
        ("byDate", "Holder", "date deadline, no as_at")]


def test_without_clock_not_judged(api, monkeypatch):
    monkeypatch.setitem(el_api._SCENARIO_CLOCK, "date_probe", None)
    api._runtime = api._new_runtime("date_probe")
    resp = _check(api, "2027-01-01T00:00+10:00")
    assert resp.violations == []
    assert [e.reason for e in resp.not_judged] == ["date deadline, no clock"]


@pytest.mark.parametrize("value", ["tomorrow", "2026-13-01T00:00+10:00", ""])
def test_unparseable_refused(api, value):
    _refused(api, value)


@pytest.mark.parametrize("value", ["2026-12-01T00:00", "2026-12-01"])
def test_naive_refused(api, value):
    assert "no UTC offset" in _refused(api, value)


def test_backwards_refused(api):
    _check(api, "2026-11-20T00:00+10:00")
    assert "earlier than the last as_at" in _refused(api, "2026-11-19T00:00+10:00")
    assert _check(api, "2026-11-19T14:00Z").outcome == "ok"   # the same moment


def test_unencoded_plus_in_query_refused(api):
    # '+' in a query string decodes to a space; it must be sent as %2B.
    (_, raw), = parse_qsl("as_at=2026-12-01T00:00+10:00")
    assert raw == "2026-12-01T00:00 10:00"
    assert "%2B" in _refused(api, raw)
    (_, encoded), = parse_qsl("as_at=2026-12-01T00:00%2B10:00")
    assert _check(api, encoded).violations == ["byDate"]


def test_shipped_scenarios_have_no_clock():
    assert set(el_api._SCENARIO_CLOCK) == set(el_api._SCENARIO_BUILDERS)
    assert all(clock is None for clock in el_api._SCENARIO_CLOCK.values())
