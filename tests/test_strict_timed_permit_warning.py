"""
2.5.0-1 — [W-strict-timed-permit] (slot W-31).

A strict burden whose discharging action requires a permit with a time limit can
get stuck: the use check refuses the discharge once the permit's time is up, and
a strict burden is never violated by the clock. The validator warns, naming the
burden, the action and the permit. Nothing else changes.
"""
from pathlib import Path

from el_parser import parse, parse_string


REPO_ROOT = Path(__file__).resolve().parent.parent

_SPEC = """
enterprise specification StrictTimedPermitProbe

party Holder

policy NoticePeriod : duration { initial_value: 5 minutes }

community ProbeCommunity
    description: "A burden discharged under a permit"
    {
        objective: "Exercise a strict burden under a timed permit"

        event doneEvent

        Holder fills holderRole

        role holderRole
            description: "Discharges the burden"
            {
                INLINE_BURDEN

                action fileReport {
                    actor: holderRole
                    requires_permit gatePermit
                    EMITS
                }
            }
    }

permit gatePermit {
    for_action: "fileReport"
    state: active
    PERMIT_DEADLINE
}

TOP_LEVEL_BURDEN
"""

_FOR_ACTION_BURDEN = """
burden dutyBurden {
    for_action: "fileReport"
    state: active
    deadline: "1 day"
    discharge_mode: MODE
}
"""

_EVENT_BURDEN = """
burden dutyBurden {
    state: active
    deadline: "1 day"
    discharged_by: doneEvent
    discharge_mode: strict
}
"""

_INLINE_BURDEN = """
burden inlineBurden {
    for_action: "fileReport"
    state: active
    deadline: "1 day"
    discharge_mode: strict
}
"""


def _warnings(permit_deadline='deadline: "5 minutes"', top_level=_FOR_ACTION_BURDEN,
              mode="strict", inline="", emits=""):
    text = (_SPEC
            .replace("PERMIT_DEADLINE", permit_deadline)
            .replace("TOP_LEVEL_BURDEN", top_level.replace("MODE", mode))
            .replace("INLINE_BURDEN", inline)
            .replace("EMITS", emits))
    result = parse_string(text, validate=True)
    assert result.ok, result.errors
    return [w for w in result.warnings if w.startswith("[W-strict-timed-permit]")]


def _expected(limit, burden="dutyBurden"):
    return (f"[W-strict-timed-permit] Strict burden '{burden}' is discharged by action "
            f"'fileReport', which requires permit 'gatePermit' with a time limit ('{limit}'): "
            f"once the permit's time is up the discharge can be refused, and a strict burden "
            f"is never violated by the clock, so it can get stuck. (clause to be confirmed)")


def test_a_duration_limit_warns_naming_burden_action_and_permit():
    assert _warnings() == [_expected("5 minutes")]


def test_a_date_limit_warns():
    assert _warnings(permit_deadline='deadline: "by 2026-05-20"') == [_expected("by 2026-05-20")]


def test_a_policy_fed_limit_warns_with_the_policy_value():
    assert _warnings(permit_deadline="deadline: NoticePeriod") == [_expected("5 minutes")]


def test_an_eventual_burden_is_silent():
    assert _warnings(mode="eventual") == []


def test_a_permit_with_no_time_limit_is_silent():
    assert _warnings(permit_deadline="") == []


def test_the_discharged_by_route_warns():
    assert _warnings(top_level=_EVENT_BURDEN, emits="emits: doneEvent") == [_expected("5 minutes")]


def test_an_inline_burden_warns():
    assert _warnings(top_level="", inline=_INLINE_BURDEN) == [_expected("5 minutes", "inlineBurden")]


def test_published_specifications_are_silent():
    paths = [p for d in ("scenarios", "tests/examples") for p in (REPO_ROOT / d).rglob("*.el")]
    assert paths
    fired = [(p.name, w) for p in paths
             for w in parse(str(p), validate=True).warnings
             if w.startswith("[W-strict-timed-permit]")]
    assert fired == []
