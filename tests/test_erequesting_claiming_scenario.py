"""
AM-63: scenario-level confirmation for
erequesting_claiming_scenario.el, the first named scenario demonstrating pool
CLAIMING — the accept-side mirror of specialist_pool_scenario.el's
discharge-side any_discharged/SUPERSEDED demonstration (AM-58).

Grammar/parser/domain layer: AM-60. Layer 4 (el_kripke.py): AM-61.
Layer 3 (el_engine.py): AM-62. See docs/el_grammar_amendments.md.

Mechanism under test (both layers):
  - Grammar/parser: Evaluation extended with a structured form
    (target_token=[DeonticToken], result_code=accept|reject), backward
    compatible with the pre-existing free-text form which stays inert.
  - Layer 4 (el_kripke.py): new ObligationState.CLAIMABLE/LAPSED and the
    C1 (claim) transition — a CLAIMABLE obligation with a matching accept
    Evaluation transitions CLAIMABLE -> PENDING, lapsing CLAIMABLE
    siblings in the same any_discharged group.
  - Layer 3 (el_engine.py): the live claim: 'claimable' -> 'active' on a
    matching accept Evaluation, lapsing 'claimable' siblings; a reject (or
    absent) Evaluation is a no-op leaving the burden 'claimable'.

Empirical, not asserted-from-design: each check runs against the real
parsed scenario model / real engine, mirroring
tests/test_specialist_pool_scenario.py's discipline.

Layer 4 verification questions (see the scenario file header):
  Q1: EF(objective_satisfied:DiagnosticReferralPoolCommunity) holds.
  Qc: EF(discharged:providerAClaimBurden) holds — the full
      claim -> discharge path is reachable.
  Ql: EF(lapsed:providerBClaimBurden) holds — the sibling correctly
      lapses when a peer claims first.
"""
from el_engine import TokenInstance, advance, enroll, grant_token, initial_state
from el_kripke import build_kripke_model
from el_parser import parse

SCENARIO = "scenarios/erequesting_claiming/erequesting_claiming_scenario.el"


def _spec():
    result = parse(SCENARIO, validate=True)
    assert result.ok, result.errors
    return result.model


def test_erequesting_claiming_scenario_parses_and_validates_cleanly():
    result = parse(SCENARIO, validate=True)
    assert result.ok, result.errors


# ── Parser: the structured Evaluation form resolves correctly ──────────────────

def test_evaluation_structured_form_resolves():
    spec = _spec()
    evals = [e for e in spec.elements if type(e).__name__ == "Evaluation"]
    assert len(evals) == 1
    ev = evals[0]
    assert ev.target_token is not None
    assert ev.target_token.name == "providerAClaimBurden"
    assert ev.result_code == "accept"
    # flat fields still populated for backward compatibility
    assert ev.target == "providerAClaimBurden"
    assert ev.result == "accept"


# ── Layer 4 (Kripke) ───────────────────────────────────────────────────────────

def test_both_pool_members_start_claimable():
    km = build_kripke_model(_spec())
    states = {k: v.name for k, v in km.initial.obligation_dict().items()}
    assert states["providerAClaimBurden"] == "CLAIMABLE"
    assert states["providerBClaimBurden"] == "CLAIMABLE"


def test_q1_objective_satisfied_reachable():
    km = build_kripke_model(_spec())
    assert km.EF(km.initial, "objective_satisfied:DiagnosticReferralPoolCommunity")


def test_qc_claim_then_discharge_reachable():
    km = build_kripke_model(_spec())
    assert km.EF(km.initial, "discharged:providerAClaimBurden")


def test_ql_sibling_lapses_when_peer_claims():
    km = build_kripke_model(_spec())
    assert km.EF(km.initial, "lapsed:providerBClaimBurden")


# ── Layer 3 (live engine) ───────────────────────────────────────────────────────

def _seeded_state():
    state = initial_state()
    state = enroll(state, "DiagnosticProviderA", role_name="eligibleProviderA")
    state = enroll(state, "DiagnosticProviderB", role_name="eligibleProviderB")
    state = grant_token(state, TokenInstance(
        token_name="providerAClaimBurden", kind="burden", holder="DiagnosticProviderA",
        state="claimable", discharge_mode="eventual", priority="high",
        granted_at_tick=0, deadline="4 hours from referral delegation",
        for_action="claimReferralA",
    ))
    state = grant_token(state, TokenInstance(
        token_name="providerBClaimBurden", kind="burden", holder="DiagnosticProviderB",
        state="claimable", discharge_mode="eventual", priority="high",
        granted_at_tick=0, deadline="4 hours from referral delegation",
        for_action="claimReferralB",
    ))
    return state


def test_live_claim_activates_holder_and_lapses_sibling():
    spec = _spec()
    state = _seeded_state()
    new_state, record = advance(state, "claimReferralA", spec, "DiagnosticProviderA")

    assert record.outcome == "ok"
    by_name = {t.token_name: t for t in new_state.tokens}
    assert by_name["providerAClaimBurden"].state == "active"
    assert by_name["providerBClaimBurden"].state == "lapsed"
    assert record.effects == (
        "claimed burden 'providerAClaimBurden'",
        "lapsed burden 'providerBClaimBurden' held by 'DiagnosticProviderB' "
        "(sibling 'providerAClaimBurden' claimed, group 'referralClaimGroup')",
    )


def test_live_claimed_burden_then_discharges_normally():
    spec = _spec()
    state = _seeded_state()
    state, _ = advance(state, "claimReferralA", spec, "DiagnosticProviderA")
    # second call discharges the now-active burden via the existing pathway
    new_state, record = advance(state, "claimReferralA", spec, "DiagnosticProviderA")

    assert record.outcome == "ok"
    by_name = {t.token_name: t for t in new_state.tokens}
    assert by_name["providerAClaimBurden"].state == "discharged"
    assert by_name["providerBClaimBurden"].state == "lapsed"
    assert record.effects == ("discharged burden 'providerAClaimBurden'",)


def test_live_reject_evaluation_is_a_no_op():
    spec = _spec()
    # flip the accept Evaluation to reject in the parsed model
    ev = [e for e in spec.elements if type(e).__name__ == "Evaluation"][0]
    ev.result_code = "reject"

    state = _seeded_state()
    new_state, record = advance(state, "claimReferralA", spec, "DiagnosticProviderA")

    assert record.outcome == "ok"
    assert record.effects == ()
    by_name = {t.token_name: t for t in new_state.tokens}
    # burden stays claimable — still available to the residual pool
    assert by_name["providerAClaimBurden"].state == "claimable"
    assert by_name["providerBClaimBurden"].state == "claimable"
