"""
AM-99b — hybrid mode (build_kripke_from_runtime()) mirrors the live
engine's event model for triggered obligations.

Part 1: w0 seeding and Rule T2.
  - an engine 'pending' burden with triggered_by maps to WAITING, not
    PENDING; one without triggered_by (masked while delegated) stays
    PENDING, as before;
  - every burden PENDING at w0 has its engine activation tick
    (activated_at_tick, else granted_at_tick) seeded into
    w0.activation_steps, and hybrid T2 counts its deadline from there.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_api import _SCENARIO_BUILDERS
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_kripke import ObligationState, build_kripke_from_runtime, build_kripke_model
from el_parser import parse
from el_runtime import Runtime


_REPO = Path(__file__).resolve().parent.parent
_TOE = _REPO / "scenarios" / "terms_of_engagement" / "external_agent_access_scenario.el"

# Holders follow the scenario's Commitment/Delegation chains and on_join
# transfers; build_from_spec() enrols none of these (no `holds` in bodies).
_TOE_ACTORS = ["ProviderOrg", "ProviderSecurityContact", "ProviderAPIGateway",
               "VendorOrg", "VendorReferralAgent"]
_TOE_GRANTS = [
    ("refusalRecordBurden", "ProviderAPIGateway"),
    ("refusalReviewBurden", "ProviderSecurityContact"),
    ("incidentNotificationBurden", "VendorOrg"),
    ("serviceRequestSubmitPermit", "VendorReferralAgent"),
    ("patientLookupPermit", "VendorReferralAgent"),
    ("outsideScopeEmbargo", "VendorReferralAgent"),
    ("noCircumventionEmbargo", "VendorReferralAgent"),
]


@pytest.fixture(scope="module")
def toe_spec():
    result = parse(_TOE, validate=False)
    assert result.ok, result.errors
    return result.model


def _toe_runtime(spec) -> Runtime:
    state = initial_state()
    for actor in _TOE_ACTORS:
        state = enroll(state, actor)
    for token, holder in _TOE_GRANTS:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    return Runtime(state, spec)


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _obligs(km):
    return dict(km.initial.obligation_states)


# ── w0 seeding ───────────────────────────────────────────────────────────────

def test_no_event_fired_matches_static_w0(toe_spec):
    static = _quiet(build_kripke_model, toe_spec, horizon=10)
    hybrid = _quiet(build_kripke_from_runtime, _toe_runtime(toe_spec), horizon=10)
    assert _obligs(hybrid) == _obligs(static)
    assert set(_obligs(hybrid).values()) == {ObligationState.WAITING}
    assert hybrid.initial.activation_steps == static.initial.activation_steps == frozenset()


def test_untriggered_pending_stays_pending():
    """ereferral's pending burdens have no triggered_by (masked while
    delegated): they keep the PENDING mapping, not WAITING."""
    km = _quiet(build_kripke_from_runtime, _SCENARIO_BUILDERS["ereferral"](), horizon=10)
    for oid in ("acknowledgementBurden", "examinationBurden", "aiExaminationBurden"):
        assert km.initial.get_obligation(oid) == ObligationState.PENDING


def test_activation_tick_seeded_from_engine(toe_spec):
    rt = _toe_runtime(toe_spec)
    rt.advance_clock(7)
    rt.advance("refuseRequest", "ProviderAPIGateway")   # tick 7: activates record
    rt.advance("recordRefusal", "ProviderAPIGateway")   # tick 8: activates review
    km = _quiet(build_kripke_from_runtime, rt, horizon=10)
    obligs = _obligs(km)
    assert obligs["refusalRecordBurden"] == ObligationState.DISCHARGED
    assert obligs["refusalReviewBurden"] == ObligationState.PENDING
    assert obligs["incidentNotificationBurden"] == ObligationState.WAITING
    assert dict(km.initial.activation_steps) == {"refusalReviewBurden": 8}


def test_activation_seed_falls_back_to_grant_tick():
    """Burdens active since grant carry granted_at_tick (0 in every builder)."""
    km = _quiet(build_kripke_from_runtime, _SCENARIO_BUILDERS["referral"](), horizon=10)
    seeds = dict(km.initial.activation_steps)
    pending = {o for o, s in km.initial.obligation_states if s == ObligationState.PENDING}
    assert set(seeds) == pending
    assert set(seeds.values()) == {0}


# ── Rule T2 counts from activation ───────────────────────────────────────────

def test_triggered_burden_violated_no_earlier_than_activation_plus_deadline(toe_spec):
    rt = _toe_runtime(toe_spec)
    rt.advance_clock(7)
    rt.advance("refuseRequest", "ProviderAPIGateway")
    rt.advance("recordRefusal", "ProviderAPIGateway")
    activated = next(t.activated_at_tick for t in rt.current_state().tokens
                     if t.token_name == "refusalReviewBurden")
    km = _quiet(build_kripke_from_runtime, rt, horizon=30)
    deadline = km.obligation_descriptors["refusalReviewBurden"].deadline_steps
    violation_steps = {
        w.step for (src, w), label in km.labels.items()
        if label == "violate:refusalReviewBurden"
    }
    assert violation_steps, "deadline must still be reachable within horizon"
    assert min(violation_steps) == activated + deadline
