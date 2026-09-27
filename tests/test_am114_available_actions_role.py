"""
AM-114 part 6 — available-actions flags an obligation whose holder fills no
role declaring its action ("obligated_not_role"), as AM-103 flags one an
embargo blocks ("obligated_blocked"). A permit whose holder fills no such
role is omitted, as an embargoed one is. Each flag matches the engine's
refusal: Step 2 (role) before Step 5 (embargo).

The API runtimes carry the two cases logged as open findings: gp_referral's
SpecialistParty holds assessmentSchedulingBurden for scheduleAssessment
(specialistRole), and referral's SpecialistClinician holds
patientRecordAccessPermitByRole for access_patient_clinical_records
(aiExaminationRole).
"""
import contextlib
import io

import pytest

import el_api
from el_engine import _role_refusal


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _entries(monkeypatch, name, actor):
    monkeypatch.setattr(el_api, "_runtime", _quiet(el_api._SCENARIO_BUILDERS[name]))
    return el_api.get_available_actions(actor).available_actions


@pytest.mark.parametrize("name", sorted(el_api._SCENARIO_BUILDERS))
def test_obligation_flags_match_the_engine(monkeypatch, name):
    rt = _quiet(el_api._SCENARIO_BUILDERS[name])
    for actor in sorted({a.actor_name for a in rt.current_state().actors}):
        for entry in _entries(monkeypatch, name, actor):
            if not entry.reason.startswith("obligated"):
                continue
            rec = _quiet(el_api._SCENARIO_BUILDERS[name]).advance(entry.action, actor)
            role_refused = rec.outcome == "blocked" and "does not fill role" in rec.reason
            assert role_refused is (entry.reason == "obligated_not_role"), (actor, entry, rec.reason)


def test_out_of_role_tokens_in_the_api_runtimes():
    """Pins the two open findings: exactly these tokens are held by an actor
    that fills no role declaring their action."""
    found = set()
    for name, build in el_api._SCENARIO_BUILDERS.items():
        rt = _quiet(build)
        state = rt.current_state()
        for tok in state.tokens:
            if tok.for_action and _role_refusal(rt._spec, state, tok.holder, tok.for_action):
                found.add((name, tok.token_name, tok.holder))
    assert found == {
        ("gp_referral", "assessmentSchedulingBurden", "SpecialistParty"),
        ("referral", "patientRecordAccessPermitByRole", "SpecialistClinician"),
    }


def test_gp_referral_specialist_party_obligation_is_flagged(monkeypatch):
    entries = {e.token: e.reason for e in _entries(monkeypatch, "gp_referral", "SpecialistParty")}
    assert entries["assessmentSchedulingBurden"] == "obligated_not_role"


def test_referral_clinician_role_permit_is_omitted(monkeypatch):
    tokens = {e.token for e in _entries(monkeypatch, "referral", "SpecialistClinician")}
    assert "patientRecordAccessPermitByRole" not in tokens
    tokens = {e.token for e in _entries(monkeypatch, "referral", "SpecialistAIAgent")}
    assert "patientRecordAccessPermitByAuthorization" in tokens
