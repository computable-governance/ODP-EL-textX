"""
Layer 3 — el_engine.join_role() (AM-83).

Closes the gap where JoinLeaveEffect (§7.8.7 NOTE 3, `on_join <role>
transfer <token>` / `on_leave <role> revert <token>`) is parsed into the
domain model but never consulted by anything: enroll() has no `spec`
parameter and so cannot see these declarations at all. join_role() is a
new, additive entry point — enroll() itself is untouched.

Exercised directly against referral_scenario.el's three live, previously
inert on_join declarations (no synthetic probe needed):
    on_join gpClinicianRole transfer referralInitiationBurden
    on_join referringRole   transfer clinicalHandoverBurden
    on_join referredToRole  transfer patientRecordAccessPermitByRole

on_leave/revert is out of scope (no leave/unenroll primitive in this
engine yet) and is not exercised here.
"""
from pathlib import Path

from el_engine import enroll, initial_state, join_role
from el_parser import parse

_REFERRAL_SCENARIO = (
    Path(__file__).resolve().parent.parent
    / "scenarios" / "referral" / "referral_scenario.el"
)


def _spec():
    result = parse(_REFERRAL_SCENARIO, validate=True)
    assert result.ok, result.errors
    return result.model


def _tokens(state, name, holder=None):
    return [
        t for t in state.tokens
        if t.token_name == name and (holder is None or t.holder == holder)
    ]


def test_join_role_grants_declared_token_on_join():
    spec = _spec()
    state = initial_state()

    new_state, effects = join_role(state, spec, "NewGPClinician", "gpClinicianRole")

    matches = _tokens(new_state, "referralInitiationBurden", "NewGPClinician")
    assert len(matches) == 1
    tok = matches[0]
    assert tok.state == "active"
    assert tok.kind == "burden"
    assert tok.granted_at_tick == state.tick
    assert (
        "on_join 'gpClinicianRole': granted 'referralInitiationBurden' "
        "to 'NewGPClinician'"
    ) in effects

    # Actor really is enrolled, same as bare enroll() would do.
    assert any(
        a.actor_name == "NewGPClinician" and a.role_name == "gpClinicianRole"
        for a in new_state.actors
    )


def test_join_role_grants_token_for_referring_role():
    spec = _spec()
    state = initial_state()

    new_state, effects = join_role(state, spec, "SomeGP", "referringRole")

    assert len(_tokens(new_state, "clinicalHandoverBurden", "SomeGP")) == 1
    assert (
        "on_join 'referringRole': granted 'clinicalHandoverBurden' to 'SomeGP'"
        in effects
    )


def test_join_role_grants_token_for_referred_to_role():
    spec = _spec()
    state = initial_state()

    new_state, effects = join_role(state, spec, "SomeSpecialist", "referredToRole")

    assert len(_tokens(new_state, "patientRecordAccessPermitByRole", "SomeSpecialist")) == 1
    assert (
        "on_join 'referredToRole': granted 'patientRecordAccessPermitByRole' "
        "to 'SomeSpecialist'"
        in effects
    )


def test_join_role_idempotent_when_actor_already_holds_token():
    spec = _spec()
    state = initial_state()

    once_state, _ = join_role(state, spec, "NewGPClinician", "gpClinicianRole")
    twice_state, second_effects = join_role(once_state, spec, "NewGPClinician", "gpClinicianRole")

    assert len(_tokens(twice_state, "referralInitiationBurden", "NewGPClinician")) == 1
    assert not any("referralInitiationBurden" in e for e in second_effects)


def test_join_role_idempotent_when_token_pre_granted_by_other_means():
    spec = _spec()
    state = initial_state()
    state = enroll(state, "PreGranted", "gpClinicianRole")
    from el_engine import TokenInstance
    pre_granted = state.with_tokens(list(state.tokens) + [
        TokenInstance(
            token_name="referralInitiationBurden",
            kind="burden",
            holder="PreGranted",
            state="active",
            discharge_mode="eventual",
            priority="normal",
            granted_at_tick=0,
        )
    ])

    new_state, effects = join_role(pre_granted, spec, "PreGranted", "gpClinicianRole")

    assert len(_tokens(new_state, "referralInitiationBurden", "PreGranted")) == 1
    assert effects == []


def test_join_role_on_role_with_no_join_leave_effect_matches_bare_enroll():
    spec = _spec()
    state = initial_state()

    new_state, effects = join_role(state, spec, "AIAgent", "aiExaminationRole")

    assert effects == []
    assert new_state.tokens == state.tokens
    assert any(
        a.actor_name == "AIAgent" and a.role_name == "aiExaminationRole"
        for a in new_state.actors
    )


def test_bare_enroll_still_produces_zero_token_effects():
    spec = _spec()
    state = initial_state()

    new_state = enroll(state, "UntouchedActor", "gpClinicianRole")

    assert new_state.tokens == state.tokens
    assert any(
        a.actor_name == "UntouchedActor" and a.role_name == "gpClinicianRole"
        for a in new_state.actors
    )
