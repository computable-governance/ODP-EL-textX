"""
Procurement tender scenario (scenarios/procurement_tender/): claim-and-award,
panel sign-off, incident notification and subcontracting, checked against the
real parsed specification and the live engine (Layer 3).

Mechanisms under test:
  - "no award before sign-off" as an ordering constraint: the award actions
    require awardPermit, which only the panel's sign-off creates
  - panelSignOffBurden (strict) freezes the process once the tender closes;
    only the probity officer may declare it violated, and not before its
    deadline
  - a single award: the award activates awardMadeEmbargo, which inhibits both
    award actions
  - the winner's acceptance (a live accept Evaluation, Runtime.claim()) claims
    its contract burden and lapses the other bid; the other bidder cannot
    accept without an award notice
  - incident notification: eventual, "24 hours" from the contractor's own
    incident report, escalated to the principal when late
  - subcontracting: gated by the award notice and an authorization; revoking
    the authorization activates subcontractEmbargo
  - public liability cover: a comparison precondition on the award (cover
    at submission), and a standing duty for the term, triggered by the
    award and ended by performance; a reported lapse is a breach

The static verifier (Layer 4) is not exercised: it models claiming only from
a spec-declared accept Evaluation, and this scenario decides the winner at
runtime; nor does it model standing duties (see the scenario README).
"""
import contextlib
import io
from datetime import datetime, timedelta, timezone

import pytest

from el_engine import DeadlineClock, grant_token, token_from_spec
from el_parser import parse
from el_runtime import Runtime

SCENARIO = "scenarios/procurement_tender/procurement_tender_scenario.el"

# Tokens created by the specification's commitments, delegation and
# authorizations. Runtime.build_from_spec() does not resolve those chains
# (its documented known gap), so they are granted here, as the other
# scenario builders do.
GRANTS = [
    ("supplierAContractBurden", "SupplierA"),       # commitment supplierABid
    ("supplierBContractBurden", "SupplierB"),       # commitment supplierBBid
    ("panelSignOffBurden", "PanelChair"),           # delegation evaluationToPanel
    ("incidentNotificationBurdenA", "SupplierA"),   # commitment supplierANotifiesIncidents
    ("incidentNotificationBurdenB", "SupplierB"),   # commitment supplierBNotifiesIncidents
    ("keepPublicLiabilityA", "SupplierA"),          # commitment supplierAKeepsCover
    ("keepPublicLiabilityB", "SupplierB"),          # commitment supplierBKeepsCover
    ("subcontractApproval", "SupplierA"),           # authorization subcontractApprovalForSupplierA
    ("signOffDeclarationPermit", "ProbityOfficer"), # authorization probityDeclarationAuthority
]

# "10 working days" and "24 hours" in one-minute steps (AM-111).
SIGN_OFF_DEADLINE_STEPS = 20160
INCIDENT_DEADLINE_STEPS = 1440

# Standing duties are judged only at a check with an as_at, under a clock.
AEST = timezone(timedelta(hours=10))
CLOCK = DeadlineClock(utc_offset=AEST)

# Facts reported with the award (cover at submission) and at checks (cover
# for the term), as text in the toolchain's amount notation.
BID_COVER_A = {"Supplier A public liability cover at submission": "25000000.00 AUD"}
BID_COVER_B = {"Supplier B public liability cover at submission": "25000000.00 AUD"}
COVER_KEPT = {"Supplier A public liability cover": "25000000.00 AUD"}
COVER_LAPSED = {"Supplier A public liability cover": "15000000.00 AUD"}

# The only warnings: [W-standing-not-modelled] on each cover duty (the
# verifier doesn't model standing duties; see the scenario README).
STANDING_DUTIES = ("keepPublicLiabilityA", "keepPublicLiabilityB")


def _at(day):
    return datetime(2027, 1, day, 9, 0, tzinfo=AEST)


@pytest.fixture(scope="module")
def spec():
    result = parse(SCENARIO, validate=True)
    assert result.ok, result.errors
    return result.model


def _runtime(spec):
    with contextlib.redirect_stdout(io.StringIO()):
        rt = Runtime.build_from_spec(spec)
    state = rt.current_state()
    for token, holder in GRANTS:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    return Runtime(state, spec, clock=CLOCK)


def _state(rt, token, holder):
    return next(t.state for t in rt.current_state().tokens
                if t.token_name == token and t.holder == holder)


def _awarded_to_a(spec):
    rt = _runtime(spec)
    assert rt.advance("closeTender", "BuyerAgency").outcome == "ok"
    assert rt.advance("signOffEvaluation", "PanelChair").outcome == "ok"
    assert rt.advance("awardToSupplierA", "BuyerAgency", facts=BID_COVER_A).outcome == "ok"
    return rt


def test_parses_and_validates_with_only_the_standing_duty_warnings():
    result = parse(SCENARIO, validate=True)
    assert result.ok, result.errors
    assert len(result.warnings) == len(STANDING_DUTIES)
    assert all(w.startswith("[W-standing-not-modelled]") for w in result.warnings)
    assert all(any(f"'{duty}'" in w for w in result.warnings) for duty in STANDING_DUTIES)


# ── Award ordering and the strict sign-off ─────────────────────────────────────

def test_no_award_before_sign_off(spec):
    rt = _runtime(spec)
    record = rt.advance("awardToSupplierA", "BuyerAgency", facts=BID_COVER_A)
    assert record.outcome == "blocked"
    assert "awardPermit" in record.reason


def test_closing_the_tender_activates_the_strict_sign_off(spec):
    rt = _runtime(spec)
    assert _state(rt, "panelSignOffBurden", "PanelChair") == "pending"
    rt.advance("closeTender", "BuyerAgency")
    assert _state(rt, "panelSignOffBurden", "PanelChair") == "active"
    # the process waits on the panel: no clock advance, no unrelated action
    assert rt.advance_clock(1).outcome == "blocked"
    assert rt.advance("awardToSupplierA", "BuyerAgency").outcome == "blocked"


def test_sign_off_grants_the_award_permit(spec):
    rt = _runtime(spec)
    rt.advance("closeTender", "BuyerAgency")
    record = rt.advance("signOffEvaluation", "PanelChair")
    assert record.outcome == "ok"
    assert _state(rt, "panelSignOffBurden", "PanelChair") == "discharged"
    assert _state(rt, "awardPermit", "BuyerAgency") == "active"


def test_only_the_probity_officer_declares_an_overdue_sign_off(spec):
    rt = _runtime(spec)
    rt.advance("closeTender", "BuyerAgency")
    late = SIGN_OFF_DEADLINE_STEPS + 1
    assert rt.declare_violation("panelSignOffBurden", "ProbityOfficer",
                                at_tick=100).outcome == "blocked"
    assert rt.declare_violation("panelSignOffBurden", "SupplierA",
                                at_tick=late).outcome == "blocked"
    assert rt.declare_violation("panelSignOffBurden", "ProbityOfficer",
                                at_tick=late).outcome == "violation"
    assert _state(rt, "panelSignOffBurden", "PanelChair") == "violated"
    rt.fire_violation_responses()
    assert _state(rt, "reconvenePanelBurden", "BuyerAgency") == "active"


# ── Award and acceptance ───────────────────────────────────────────────────────

def test_only_one_award(spec):
    rt = _awarded_to_a(spec)
    assert _state(rt, "awardNoticeA", "SupplierA") == "active"
    record = rt.advance("awardToSupplierB", "BuyerAgency", facts=BID_COVER_B)
    assert record.outcome == "blocked"
    assert "awardMadeEmbargo" in record.reason


def test_unawarded_bidder_cannot_accept(spec):
    rt = _awarded_to_a(spec)
    record = rt.claim("supplierBContractBurden", "SupplierB")
    assert record.outcome == "blocked"
    assert _state(rt, "supplierBContractBurden", "SupplierB") == "claimable"


def test_acceptance_claims_the_contract_and_lapses_the_other_bid(spec):
    rt = _awarded_to_a(spec)
    record = rt.claim("supplierAContractBurden", "SupplierA")
    assert record.outcome == "ok"
    assert _state(rt, "supplierAContractBurden", "SupplierA") == "active"
    assert _state(rt, "supplierBContractBurden", "SupplierB") == "lapsed"
    assert rt.advance("performContractA", "SupplierA").outcome == "ok"
    assert _state(rt, "supplierAContractBurden", "SupplierA") == "discharged"


def test_award_needs_cover_at_submission(spec):
    rt = _runtime(spec)
    rt.advance("closeTender", "BuyerAgency")
    rt.advance("signOffEvaluation", "PanelChair")
    record = rt.advance("awardToSupplierA", "BuyerAgency")
    assert record.outcome == "blocked"
    assert "not reported" in record.reason
    below = {"Supplier A public liability cover at submission": "15000000.00 AUD"}
    assert rt.advance("awardToSupplierA", "BuyerAgency", facts=below).outcome == "blocked"
    assert rt.advance("awardToSupplierA", "BuyerAgency", facts=BID_COVER_A).outcome == "ok"


# ── Public liability cover for the term ────────────────────────────────────────

def test_cover_duty_starts_at_the_award(spec):
    rt = _runtime(spec)
    assert _state(rt, "keepPublicLiabilityA", "SupplierA") == "pending"
    rt = _awarded_to_a(spec)
    assert _state(rt, "keepPublicLiabilityA", "SupplierA") == "active"
    assert _state(rt, "keepPublicLiabilityB", "SupplierB") == "pending"


def test_cover_kept_then_a_lapse_is_breached_and_remediated(spec):
    rt = _awarded_to_a(spec)
    record = rt.check_live_violations(as_at=_at(15), facts=COVER_KEPT)
    assert record.outcome == "ok"
    assert any(e.startswith("kept 'keepPublicLiabilityA'") for e in record.effects)
    record = rt.check_live_violations(as_at=_at(16), facts=COVER_LAPSED)
    assert record.outcome == "violation"
    assert _state(rt, "keepPublicLiabilityA", "SupplierA") == "violated"
    rt.fire_violation_responses()
    assert _state(rt, "coverLapseReviewBurden", "BuyerAgency") == "active"


def test_performance_ends_the_cover_term(spec):
    rt = _awarded_to_a(spec)
    rt.claim("supplierAContractBurden", "SupplierA")
    assert rt.advance("performContractA", "SupplierA").outcome == "ok"
    assert _state(rt, "keepPublicLiabilityA", "SupplierA") == "discharged"
    assert rt.check_live_violations(as_at=_at(20), facts=COVER_LAPSED).outcome == "ok"


# ── Incident notification ──────────────────────────────────────────────────────

def test_incident_clock_starts_at_the_incident_not_the_award(spec):
    rt = _awarded_to_a(spec)
    rt.advance_clock(2 * INCIDENT_DEADLINE_STEPS)
    assert rt.check_live_violations().outcome == "ok"
    assert _state(rt, "incidentNotificationBurdenA", "SupplierA") == "pending"


def test_unawarded_bidder_cannot_report_an_incident(spec):
    rt = _awarded_to_a(spec)
    assert rt.advance("reportIncidentB", "SupplierB").outcome == "blocked"
    assert _state(rt, "incidentNotificationBurdenB", "SupplierB") == "pending"


def test_timely_notification_discharges(spec):
    rt = _awarded_to_a(spec)
    rt.advance("reportIncidentA", "SupplierA")
    assert _state(rt, "incidentNotificationBurdenA", "SupplierA") == "active"
    rt.advance_clock(60)
    assert rt.advance("notifyIncidentA", "SupplierA").outcome == "ok"
    assert _state(rt, "incidentNotificationBurdenA", "SupplierA") == "discharged"
    rt.advance_clock(2 * INCIDENT_DEADLINE_STEPS)
    assert rt.check_live_violations().outcome == "ok"


def test_late_notification_is_violated_and_escalated(spec):
    rt = _awarded_to_a(spec)
    rt.advance("reportIncidentA", "SupplierA")
    rt.advance_clock(INCIDENT_DEADLINE_STEPS + 1)
    assert rt.check_live_violations().outcome == "violation"
    assert _state(rt, "incidentNotificationBurdenA", "SupplierA") == "violated"
    rt.fire_violation_responses()
    assert _state(rt, "incidentFollowUpBurden", "BuyerAgency") == "active"


# ── Subcontracting ─────────────────────────────────────────────────────────────

def test_no_subcontracting_before_award(spec):
    rt = _runtime(spec)
    record = rt.advance("subcontractCivilWorks", "SupplierA")
    assert record.outcome == "blocked"
    assert "awardNoticeA" in record.reason


def test_subcontracting_needs_approval_and_stops_on_revocation(spec):
    rt = _awarded_to_a(spec)
    assert rt.advance("subcontractCivilWorks", "SupplierA").outcome == "ok"
    rt.revoke_authorization("subcontractApprovalForSupplierA")
    assert _state(rt, "subcontractEmbargo", "SupplierA") == "active"
    record = rt.advance("subcontractCivilWorks", "SupplierA")
    assert record.outcome == "blocked"
    assert "subcontractEmbargo" in record.reason
