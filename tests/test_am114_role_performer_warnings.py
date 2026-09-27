"""
AM-114 part 7 — [W-27] a burden that can never be discharged because nobody
who may perform its discharging action does; [W-28] a permit whose holder
fills no role declaring its for_action.

Checked only where every element declaring the action states its fillers
(`fills`). No tracked scenario raises either warning; the gp_referral case
(SpecialistParty holds assessmentSchedulingBurden, a specialistRole action)
is raised once the scenario states its fillers.
"""
import contextlib
import glob
import io
from pathlib import Path

import pytest

from el_parser import parse, parse_string


_REPO = Path(__file__).resolve().parent.parent


def _warnings(src):
    with contextlib.redirect_stdout(io.StringIO()):
        result = parse_string(src, validate=True)
    assert result.model is not None, result.errors
    return [w for w in result.warnings + result.errors if "[W-27]" in w or "[W-28]" in w]


_PROBE = """
enterprise specification PerformerWarningProbe
party Owner
agent Doer
agent Other

burden doBurden { for_action: "doIt" state: active discharge_mode: eventual }
burden ackBurden { for_action: "notify" state: active discharged_by: acked discharge_mode: eventual }
permit usePermit { for_action: "useIt" state: active }

commitment OwnerDoes { by: Owner obligation: "do it" creates_burden: doBurden }
commitment OwnerNotifies { by: Owner obligation: "notify" creates_burden: ackBurden }
authorization UseAuth { authority: Owner to_agent: Other grants_permit: usePermit }

community C {
    objective: "probe W-27/W-28"
    event acked
    FILLS
    role doerRole {
        action doIt { actor: doerRole }
        action useIt { actor: doerRole requires_permit usePermit }
        action notify { actor: doerRole }
    }
    role ackRole {
        action ack { actor: ackRole emits: acked }
    }
}
"""


def test_w27_w28_fire_when_nobody_may_perform():
    warnings = _warnings(_PROBE.replace("FILLS", "Doer fills doerRole"))
    assert len(warnings) == 3, warnings
    assert any(w.startswith("[W-27] Burden 'doBurden' is held by 'Owner', which fills no role "
                            "declaring its for_action 'doIt' ('doerRole')") for w in warnings)
    assert any(w.startswith("[W-27] Burden 'ackBurden' is discharged_by 'acked', emitted only "
                            "by 'ack', but nobody fills role 'ackRole'") for w in warnings)
    assert any(w.startswith("[W-28] Permit 'usePermit' is held by 'Other', which fills no role "
                            "declaring its for_action 'useIt' ('doerRole')") for w in warnings)


def test_silent_when_performers_fill_the_roles():
    fills = "Owner fills doerRole\n    Other fills doerRole\n    Doer fills ackRole"
    assert _warnings(_PROBE.replace("FILLS", fills)) == []


def test_silent_without_fills_statements():
    assert _warnings(_PROBE.replace("FILLS", "")) == []


@pytest.mark.parametrize("path", sorted(glob.glob(str(_REPO / "scenarios" / "**" / "*.el"),
                                                  recursive=True)),
                         ids=lambda p: Path(p).stem)
def test_no_tracked_scenario_raises_w27_or_w28(path):
    with contextlib.redirect_stdout(io.StringIO()):
        result = parse(path, validate=True)
    if result.model is None:
        pytest.skip("does not parse (ecommerce, AM-93 note)")
    assert not [w for w in result.warnings + result.errors if "[W-27]" in w or "[W-28]" in w]


def test_gp_referral_specialist_party_raised_once_fillers_are_stated():
    """The open finding: SpecialistParty commits to assessmentSchedulingBurden
    but scheduleAssessment is a specialistRole action. The scenario states no
    fillers, so W-27 is silent on it; stating them (in memory) raises it."""
    src = (_REPO / "scenarios" / "gp_referral" / "gp_referral_scenario.el").read_text()
    anchor = "        on_leave specialistRole revert patientRecordAccessPermitByRole\n"
    assert src.count(anchor) == 1
    src = src.replace(anchor, anchor + "        SpecialistClinician fills specialistRole\n")
    warnings = _warnings(src)
    assert warnings == [
        "[W-27] Burden 'assessmentSchedulingBurden' is held by 'SpecialistParty', which "
        "fills no role declaring its for_action 'scheduleAssessment' ('specialistRole'): "
        "the holder may not perform it, so the burden can never be discharged. "
        "(§7.8.2, §6.4.3)"
    ]
