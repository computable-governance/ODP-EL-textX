"""
AM-58: scenario-level confirmation for specialist_pool_scenario.el, the
first named, standalone scenario demonstrating the any_discharged/
SUPERSEDED collective-obligation mechanism (Layer 4 verifier: el_kripke.py's
P6b, since AM-27; Layer 3 live engine: el_engine.py, since AM-57).

Deliberately scenario-level only -- confirms this named scenario actually
exercises the mechanism end-to-end, not a re-test of the mechanism's own
logic (that's AM-57's job: tests/test_any_discharged_sibling_supersession.py).
Two checks, both run against the real parsed scenario model, matching the
two Layer 4 verification questions in the scenario file's own header
comment:

  Q1: EF(objective_satisfied:OnCallConsultCommunity) holds -- either
      specialist discharging satisfies the community objective.
  Q2: discharging specialistAResponseBurden via the live engine supersedes
      specialistBResponseBurden (AM-57's mechanism, exercised here under
      a real scenario name for the first time).
"""
from el_engine import TokenInstance, advance, enroll, grant_token, initial_state
from el_kripke import build_kripke_model
from el_parser import parse


def _spec():
    result = parse("scenarios/specialist_pool/specialist_pool_scenario.el", validate=True)
    assert result.ok, result.errors
    return result.model


def test_specialist_pool_scenario_parses_and_validates_cleanly():
    """Zero errors -- V-16a passes since both consultResponseGroup members
    are Commitment-backed (specialistAResponseCommitment/
    specialistBResponseCommitment)."""
    result = parse("scenarios/specialist_pool/specialist_pool_scenario.el", validate=True)
    assert result.ok, result.errors


# ── Q1: EF(objective_satisfied:OnCallConsultCommunity) ─────────────────────────

def test_ef_objective_satisfied_holds():
    spec = _spec()
    km = build_kripke_model(spec)
    assert km.EF(km.initial, "objective_satisfied:OnCallConsultCommunity")


# ── Q2: live discharge supersedes the sibling ───────────────────────────────────

def test_live_discharge_of_specialist_a_supersedes_specialist_b():
    spec = _spec()
    state = initial_state()
    state = enroll(state, "SpecialistOnCallA", role_name="onCallSpecialistA")
    state = enroll(state, "SpecialistOnCallB", role_name="onCallSpecialistB")
    state = grant_token(state, TokenInstance(
        token_name="specialistAResponseBurden", kind="burden", holder="SpecialistOnCallA",
        state="active", discharge_mode="eventual", priority="high",
        granted_at_tick=0, deadline="2 hours from consult request",
        for_action="acceptConsultA",
    ))
    state = grant_token(state, TokenInstance(
        token_name="specialistBResponseBurden", kind="burden", holder="SpecialistOnCallB",
        state="active", discharge_mode="eventual", priority="high",
        granted_at_tick=0, deadline="2 hours from consult request",
        for_action="acceptConsultB",
    ))

    new_state, record = advance(state, "acceptConsultA", spec, "SpecialistOnCallA")

    assert record.outcome == "ok"
    by_name = {t.token_name: t for t in new_state.tokens}
    assert by_name["specialistAResponseBurden"].state == "discharged"
    assert by_name["specialistBResponseBurden"].state == "superseded"
    assert record.effects == (
        "discharged burden 'specialistAResponseBurden'",
        "superseded burden 'specialistBResponseBurden' held by 'SpecialistOnCallB' "
        "(sibling 'specialistAResponseBurden' discharged, group 'consultResponseGroup')",
    )
