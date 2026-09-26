"""
AM-99a (part 3) — bounded response property for triggered obligations.

For an obligation with triggered_by, AF(discharged) from w0 asks the wrong
question: the trigger may never fire. check_obligation() instead
reports the bounded response property ("within horizon"):

    AG(pending:O -> AF discharged:O), from every PENDING world before
    the horizon step.

"not triggered within horizon" and "not resolved within horizon" are never
reported as satisfied. Obligations without triggered_by keep the
AF-from-w0 verdict (docs/el_grammar_amendments.md, AM-99a). AM-99a
limited this to static models with a temporary response_semantics flag;
AM-99b removed it, so hybrid models use the same semantics.
"""
from pathlib import Path

import pytest

from el_engine import ObligationDescriptor
from el_kripke import (
    NOT_RESOLVED_WITHIN_HORIZON,
    NOT_TRIGGERED_WITHIN_HORIZON,
    RESPONSE_OPERATOR,
    KripkeModel,
    ObligationState,
    ObligationVerdict,
    _build_propositions,
    _make_world,
    build_kripke_from_runtime,
    build_kripke_model,
)
from el_parser import parse, parse_string
from el_api import _SCENARIO_BUILDERS


_REPO = Path(__file__).resolve().parent.parent
_TOE = _REPO / "scenarios" / "terms_of_engagement" / "external_agent_access_scenario.el"
_CONSENT = _REPO / "scenarios" / "consent" / "consent_scenario.el"
_REFERRAL = _REPO / "scenarios" / "referral" / "referral_scenario.el"


def _km_from_file(path, horizon=10):
    result = parse(path, validate=False)
    assert result.ok, result.errors
    return build_kripke_model(result.model, horizon=horizon)


@pytest.fixture(scope="module")
def toe():
    return _km_from_file(_TOE)


# ── The motivating scenario ──────────────────────────────────────────────────

def test_refusal_record_response_property_holds(toe):
    """Strict: once refused, the refusal is recorded on every path."""
    v = toe.check_obligation("refusalRecordBurden")
    assert v.modal_operator == RESPONSE_OPERATOR
    assert v.status is None
    assert v.satisfied is True


def test_eventual_response_property_fails_but_reachable(toe):
    """Eventual: detectable (EF) but not compelled once pending."""
    v = toe.check_obligation("refusalReviewBurden")
    assert v.modal_operator == RESPONSE_OPERATOR
    assert v.status is None
    assert v.satisfied is False
    assert v.counterexample_path
    assert toe.check_permission("refusalReviewBurden").satisfied is True


def test_incident_notification_not_resolved_within_horizon(toe):
    """AM-109: incidentNotificationBurden was 'fails' here only because its
    counterexample ended at another obligation's violation, then a dead
    end (the terminal-violated-world rule). With violated worlds
    continuing, no path fails within the horizon: its own genuine failure,
    silence until the 72-hour deadline (360 steps), lies beyond horizon 10.
    Detectable (EF) as before. See CONCEPTS_INDEX, horizon sizing."""
    v = toe.check_obligation("incidentNotificationBurden")
    assert v.modal_operator == RESPONSE_OPERATOR
    assert v.satisfied is False
    assert v.status == NOT_RESOLVED_WITHIN_HORIZON
    assert toe.check_permission("incidentNotificationBurden").satisfied is True


def test_counterexample_starts_at_initial_world(toe):
    v = toe.check_obligation("refusalReviewBurden")
    assert v.counterexample_path[0][0] == toe.initial


# ── Scoping: untriggered obligations and hybrid models unchanged ─────────────

def test_untriggered_obligation_keeps_af_from_w0():
    km = _km_from_file(_CONSENT)
    v = km.check_obligation("seekConsentObligation")
    assert v.modal_operator == "AF"
    assert v.status is None
    assert v.satisfied is True


def test_hybrid_model_uses_response_semantics():
    """AM-99b removed the temporary flag: a hybrid model judges a
    triggered obligation by the response property too. The referral
    builder grants referralInitiationBurden active at tick 0, so it is
    PENDING at w0 and the verdict is unchanged: satisfied
    (test_referral_kripke.py pins True); only the operator changes,
    from AF to the response operator."""
    km = build_kripke_from_runtime(_SCENARIO_BUILDERS["referral"](), horizon=10)
    v = km.check_obligation("referralInitiationBurden")
    assert v.modal_operator == RESPONSE_OPERATOR
    assert v.status is None
    assert v.satisfied is True


# ── The two statuses never reported as satisfied ─────────────────────────────

def test_not_triggered_within_horizon_static_referral():
    """encounterConcluded is fired only from FHIR (fire_event), never by a
    DSL action or discharge, so statically the burden stays WAITING."""
    km = _km_from_file(_REFERRAL)
    v = km.check_obligation("referralInitiationBurden")
    assert v.modal_operator == RESPONSE_OPERATOR
    assert v.status == NOT_TRIGGERED_WITHIN_HORIZON
    assert v.satisfied is False


def test_not_triggered_within_horizon_minimal_fixture():
    src = """
enterprise specification NeverTriggeredProbe

party Operator

burden waitingBurden {
    for_action: "respond"
    state: pending
    triggered_by: neverFired
    discharge_mode: strict
}

community ProbeCommunity {
    objective: "probe an event nothing fires"
    event neverFired
}

commitment OperatorResponds {
    by: Operator
    obligation: "respond"
    creates_burden: waitingBurden
}
"""
    result = parse_string(src, validate=False)
    assert result.ok, result.errors
    km = build_kripke_model(result.model, horizon=5)
    v = km.check_obligation("waitingBurden")
    assert v.status == NOT_TRIGGERED_WITHIN_HORIZON
    assert v.satisfied is False
    assert "not triggered within horizon" in v.render()
    assert "NOT satisfied" in v.render()


def test_not_resolved_within_horizon_pending_only_at_horizon_step():
    """Hand-built model: O becomes PENDING only in a world at step ==
    horizon (an unexpanded dead end, see the horizon-enqueue asymmetry
    finding). No in-horizon PENDING world exists to check, so the
    verdict is 'not resolved within horizon', not satisfied."""
    horizon = 3
    desc = ObligationDescriptor(
        obligation_id="O", obligation_text="probe", deadline_steps=5,
        holder="A", chain=["A"], revocable=False,
        sub_delegation_allowed=False, triggered_by="E",
    )
    w0 = _make_world({"O": ObligationState.WAITING}, {}, frozenset(), step=0)
    w_h = _make_world({"O": ObligationState.PENDING}, {}, frozenset(), step=horizon)
    km = KripkeModel(
        initial=w0,
        worlds={w0, w_h},
        edges={w0: {w_h}},
        propositions={w: _build_propositions(w) for w in (w0, w_h)},
        labels={(w0, w_h): "fire:E via probe"},
        obligation_descriptors={"O": desc},
        horizon=horizon,
    )
    v = km.check_obligation("O")
    assert v.modal_operator == RESPONSE_OPERATOR
    assert v.status == NOT_RESOLVED_WITHIN_HORIZON
    assert v.satisfied is False


@pytest.mark.parametrize("status", [NOT_TRIGGERED_WITHIN_HORIZON,
                                    NOT_RESOLVED_WITHIN_HORIZON])
def test_status_can_never_be_satisfied(status):
    with pytest.raises(ValueError):
        ObligationVerdict(
            obligation_id="O", obligation_text="probe",
            modal_operator=RESPONSE_OPERATOR, satisfied=True,
            worlds_checked=1, holder="A", chain=[], status=status,
        )
