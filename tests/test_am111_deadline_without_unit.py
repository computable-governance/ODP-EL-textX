"""
AM-111 — [W-25]: a burden deadline with a number but no recognised time unit.

_parse_deadline_steps() reads a magnitude only when a number is followed,
within 20 characters, by second/minute/hour/day/week/month/year. Otherwise
the number is ignored and the deadline is never measured — by the engine's
check_live_violations() or by the verifier's T2 (AM-108). Before AM-111,
"1 year" was such a case; "2 hrs" and a bare "10" still are. [W-25] names
the cause for every burden, eventual or strict, top-level or role-scoped.
It fires in no tracked scenario.
"""
import contextlib
import glob
import io
from pathlib import Path

import pytest

from el_parser import parse, parse_string


_ROOT = Path(__file__).resolve().parent.parent


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_PROBE = """
enterprise specification DeadlineUnitProbe

party Holder {{
    holds probeBurden
    holds probePermit
}}

burden probeBurden {{
    for_action: "act"
    state: active
    deadline: "{deadline}"
    discharge_mode: {mode}
}}

permit probePermit {{
    for_action: "read"
    state: active
    deadline: "by 2026-05-20"
}}
"""


def _w25(deadline, mode="eventual"):
    result = _quiet(parse_string, _PROBE.format(deadline=deadline, mode=mode))
    assert result.ok, result.errors
    return [w for w in result.warnings if w.startswith("[W-25]")]


@pytest.mark.parametrize("deadline", ["2 hrs", "10", "by 2026-05-20", "within 3 business"])
@pytest.mark.parametrize("mode", ["eventual", "strict"])
def test_fires_for_number_without_unit(deadline, mode):
    warnings = _w25(deadline, mode)
    assert len(warnings) == 1
    assert f"Burden 'probeBurden' has deadline '{deadline}'" in warnings[0]
    assert "(§6.4.3, §7.8.7)" in warnings[0]


@pytest.mark.parametrize("deadline", [
    "2 hours", "1 year", "5 working days from referral receipt", "90 seconds",
    "referral episode", "thirty days",
])
def test_silent_for_a_unit_or_no_number(deadline):
    """A recognised unit, or no digit at all ([W-24]/[W-19] cover prose)."""
    assert _w25(deadline) == []


def test_permits_are_not_checked():
    """probePermit's 'by 2026-05-20' is never reported: only burdens are
    violated on a deadline."""
    assert all("probePermit" not in w for w in _w25("2 hours"))


def test_role_scoped_inline_burden():
    src = """
enterprise specification InlineDeadlineProbe

community C
    description: "Probe"
    {
        objective: "Probe W-25 on an InlineToken"

        role r
            description: "Holds an inline burden"
            {
                burden inlineBurden { for_action: "act" state: active deadline: "3 hrs" }
            }
    }
"""
    result = _quiet(parse_string, src)
    assert result.ok, result.errors
    assert [w.split("'")[1] for w in result.warnings
            if w.startswith("[W-25]")] == ["inlineBurden"]


# ecommerce_scenario.el does not parse (CONCEPTS_INDEX, AM-93 note).
_SCENARIOS = sorted(p for p in glob.glob(str(_ROOT / "scenarios" / "**" / "*.el"), recursive=True)
                    if not p.endswith("ecommerce_scenario.el"))


@pytest.mark.parametrize("path", _SCENARIOS, ids=lambda p: Path(p).stem)
def test_fires_in_no_tracked_scenario(path):
    result = _quiet(parse, path)
    assert result.model is not None, result.errors
    assert [w for w in result.warnings if w.startswith("[W-25]")] == []
