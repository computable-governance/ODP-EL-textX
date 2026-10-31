"""
Procurement tender scenario (scenarios/procurement_tender/): claim-and-award,
panel sign-off, the contractor role, incident notification and subcontracting,
checked against the real parsed specification and the live engine (Layer 3).

Mechanisms under test:
  - "no award before sign-off" as an ordering constraint: the award actions
    require awardPermit, which only the panel's sign-off creates
  - panelSignOffBurden (strict) freezes the process once the tender closes;
    only the probity officer may declare it violated, and not before its
    deadline
  - a single award: the award activates awardMadeEmbargo, which inhibits both
    award actions; without the embargo, the filled contractor role refuses a
    second award
  - the award fills contractorRole with the winner (effect fill, 2.4.0-3),
    and the role's on_join duties are granted to the winner only; neither
    the panel nor the probity officer may fill it (excludes_role)
  - the winner's acceptance (a live accept Evaluation, Runtime.claim()) claims
    its contract burden and lapses the other bid; the other bidder does not
    fill the contractor role, so it cannot accept
  - incident notification: eventual, "24 hours" from the contractor's own
    incident report, escalated to the principal when late
  - subcontracting: gated by the contractor role and an authorization;
    revoking the authorization activates subcontractEmbargo
  - public liability cover: a comparison precondition on the award (cover
    at submission), and a standing duty for the term, granted at the award
    and ended when the buyer certifies completion; a reported lapse is a
    breach

The static verifier (Layer 4) is not exercised: it models claiming only from
a spec-declared accept Evaluation, and this scenario decides the winner at
runtime; nor does it model standing duties or a role filled by an action
(see the scenario README).
"""
import contextlib
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from el_engine import DeadlineClock, grant_token, token_from_spec
from el_parser import parse
from el_runtime import Runtime

SCENARIO = "scenarios/procurement_tender/procurement_tender_scenario.el"

# Tokens created by the specification's commitments, delegation and
# authorizations. Runtime.build_from_spec() does not resolve those chains
# (its documented known gap), so they are granted here, as the other
# scenario builders do. subcontractApproval goes to the contractor, so it
# is granted after the award (_approved()).
GRANTS = [
    ("supplierAContractBurden", "SupplierA"),       # commitment supplierABid
    ("supplierBContractBurden", "SupplierB"),       # commitment supplierBBid
    ("panelSignOffBurden", "PanelChair"),           # delegation evaluationToPanel
    ("signOffDeclarationPermit", "ProbityOfficer"), # authorization probityDeclarationAuthority
]

# The contractor's duties, granted by the award (on_join contractorRole).
CONTRACTOR_DUTIES = {"incidentNotificationBurden", "keepPublicLiability"}

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
COVER_KEPT = {"Contractor public liability cover": "25000000.00 AUD"}
COVER_LAPSED = {"Contractor public liability cover": "15000000.00 AUD"}

# The only warnings, in validator order (see the scenario README).
EXPECTED_WARNINGS = (
    ("[W-standing-not-modelled]", "'keepPublicLiability'"),
    ("[W-burden-not-modelled]", "'incidentNotificationBurden'"),
    ("[W-fill-not-modelled]", "'contractorRole'"),
)


def _at(day):
    return datetime(2027, 1, day, 9, 0, tzinfo=AEST)


@pytest.fixture(scope="module")
def spec():
    result = parse(SCENARIO, validate=True)
    assert result.ok, result.errors
    return result.model


def _variant(tmp_path, old, new):
    """The scenario with every `old` replaced by `new`, parsed unvalidated."""
    text = Path(SCENARIO).read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "variant.el"
    path.write_text(text.replace(old, new), encoding="utf-8")
    result = parse(str(path), validate=False)
    assert result.model is not None
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


def _held(rt, holder):
    return {t.token_name for t in rt.current_state().tokens if t.holder == holder}


def _fillers(rt, role):
    return [a.actor_name for a in rt.current_state().actors if a.role_name == role]


def _signed_off(spec):
    rt = _runtime(spec)
    assert rt.advance("closeTender", "BuyerAgency").outcome == "ok"
    assert rt.advance("signOffEvaluation", "PanelChair").outcome == "ok"
    return rt


def _awarded_to_a(spec):
    rt = _signed_off(spec)
    assert rt.advance("awardToSupplierA", "BuyerAgency", facts=BID_COVER_A).outcome == "ok"
    return rt


def _approved(rt, spec):
    """rt with subcontractApproval granted to the contractor
    (authorization subcontractApprovalForContractor)."""
    state = grant_token(rt.current_state(),
                        token_from_spec(spec, "subcontractApproval", "SupplierA",
                                        rt.current_state().tick))
    return Runtime(state, spec, clock=CLOCK)


def test_parses_and_validates_with_the_three_expected_warnings():
    result = parse(SCENARIO, validate=True)
    assert result.ok, result.errors
    assert len(result.warnings) == len(EXPECTED_WARNINGS)
    for warning, (tag, name) in zip(result.warnings, EXPECTED_WARNINGS):
        assert warning.startswith(tag) and name in warning, warning


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


# ── Award: the contractor role ─────────────────────────────────────────────────

def test_the_award_fills_the_contractor_role_and_grants_its_duties(spec):
    rt = _signed_off(spec)
    assert _fillers(rt, "contractorRole") == []
    record = rt.advance("awardToSupplierA", "BuyerAgency", facts=BID_COVER_A)
    assert record.outcome == "ok", record.reason
    assert "filled role 'contractorRole' with 'SupplierA'" in record.effects
    events = {e.token_name: e for e in record.token_events
              if e.holder == "SupplierA" and e.token_name in CONTRACTOR_DUTIES}
    assert set(events) == CONTRACTOR_DUTIES
    for e in events.values():
        assert (e.event, e.cause, e.cause_ref, e.by) == (
            "granted", "on_join", "contractorRole", "BuyerAgency")
    # each in its declared state: the incident duty waits for an incident
    assert _state(rt, "incidentNotificationBurden", "SupplierA") == "pending"
    assert _state(rt, "keepPublicLiability", "SupplierA") == "active"


def test_only_one_award(spec):
    rt = _awarded_to_a(spec)
    assert _fillers(rt, "contractorRole") == ["SupplierA"]
    # the winner holds its bid and the contractor's duties: no award notice
    assert _held(rt, "SupplierA") == {"supplierAContractBurden"} | CONTRACTOR_DUTIES
    record = rt.advance("awardToSupplierB", "BuyerAgency", facts=BID_COVER_B)
    assert record.outcome == "blocked"
    assert "awardMadeEmbargo" in record.reason


def test_a_second_award_is_refused_by_the_filled_role_without_the_embargo(tmp_path):
    spec = _variant(tmp_path, "            effect activate awardMadeEmbargo\n", "")
    rt = _awarded_to_a(spec)
    assert _state(rt, "awardMadeEmbargo", "BuyerAgency") == "pending"
    record = rt.advance("awardToSupplierB", "BuyerAgency", facts=BID_COVER_B)
    assert record.outcome == "blocked"
    assert record.reason == "role 'contractorRole' is already filled by 'SupplierA'"
    assert _fillers(rt, "contractorRole") == ["SupplierA"]
    assert _held(rt, "SupplierB") == {"supplierBContractBurden"}


def test_the_panel_chair_cannot_be_made_the_contractor(tmp_path):
    spec = _variant(tmp_path, "effect fill contractorRole with SupplierB",
                    "effect fill contractorRole with PanelChair")
    rt = _signed_off(spec)
    record = rt.advance("awardToSupplierB", "BuyerAgency", facts=BID_COVER_B)
    assert record.outcome == "blocked"
    assert record.reason == ("'PanelChair' fills 'evaluationPanelRole', which the "
                             "assignment policy of 'contractorRole' excludes")
    # the whole act is refused: no fill, no duties, the embargo not activated
    assert _fillers(rt, "contractorRole") == []
    assert not CONTRACTOR_DUTIES & _held(rt, "PanelChair")
    assert _state(rt, "awardMadeEmbargo", "BuyerAgency") == "pending"


def test_the_other_bidder_holds_no_contractor_duties(spec):
    rt = _awarded_to_a(spec)
    assert _held(rt, "SupplierB") == {"supplierBContractBurden"}


# ── Acceptance ─────────────────────────────────────────────────────────────────

def test_unawarded_bidder_cannot_accept(spec):
    rt = _awarded_to_a(spec)
    record = rt.claim("supplierBContractBurden", "SupplierB")
    assert record.outcome == "blocked"
    assert "does not fill role 'contractorRole'" in record.reason
    assert _state(rt, "supplierBContractBurden", "SupplierB") == "claimable"


def test_acceptance_claims_the_contract_and_lapses_the_other_bid(spec):
    rt = _awarded_to_a(spec)
    record = rt.claim("supplierAContractBurden", "SupplierA")
    assert record.outcome == "ok"
    assert _state(rt, "supplierAContractBurden", "SupplierA") == "active"
    assert _state(rt, "supplierBContractBurden", "SupplierB") == "lapsed"
    assert rt.advance("performContract", "SupplierA").outcome == "ok"
    assert _state(rt, "supplierAContractBurden", "SupplierA") == "discharged"


def test_award_needs_cover_at_submission(spec):
    rt = _signed_off(spec)
    record = rt.advance("awardToSupplierA", "BuyerAgency")
    assert record.outcome == "blocked"
    assert "not reported" in record.reason
    below = {"Supplier A public liability cover at submission": "15000000.00 AUD"}
    assert rt.advance("awardToSupplierA", "BuyerAgency", facts=below).outcome == "blocked"
    assert rt.advance("awardToSupplierA", "BuyerAgency", facts=BID_COVER_A).outcome == "ok"


# ── Public liability cover for the term ────────────────────────────────────────

def test_cover_duty_starts_at_the_award(spec):
    rt = _signed_off(spec)
    assert not any(t.token_name == "keepPublicLiability" for t in rt.current_state().tokens)
    rt.advance("awardToSupplierA", "BuyerAgency", facts=BID_COVER_A)
    assert _state(rt, "keepPublicLiability", "SupplierA") == "active"


def test_cover_kept_then_a_lapse_is_breached_and_remediated(spec):
    rt = _awarded_to_a(spec)
    record = rt.check_live_violations(as_at=_at(15), facts=COVER_KEPT)
    assert record.outcome == "ok"
    assert any(e.startswith("kept 'keepPublicLiability'") for e in record.effects)
    record = rt.check_live_violations(as_at=_at(16), facts=COVER_LAPSED)
    assert record.outcome == "violation"
    assert _state(rt, "keepPublicLiability", "SupplierA") == "violated"
    rt.fire_violation_responses()
    assert _state(rt, "coverLapseReviewBurden", "BuyerAgency") == "active"


def test_acceptance_does_not_end_the_cover_term_and_certified_completion_does(spec):
    rt = _awarded_to_a(spec)
    assert rt.claim("supplierAContractBurden", "SupplierA").outcome == "ok"
    assert rt.advance("performContract", "SupplierA").outcome == "ok"
    assert _state(rt, "keepPublicLiability", "SupplierA") == "active"
    assert rt.check_live_violations(as_at=_at(15), facts=COVER_KEPT).outcome == "ok"
    assert rt.advance("certifyCompletion", "BuyerAgency").outcome == "ok"
    assert _state(rt, "keepPublicLiability", "SupplierA") == "discharged"
    assert rt.check_live_violations(as_at=_at(20), facts=COVER_LAPSED).outcome == "ok"


# ── Incident notification ──────────────────────────────────────────────────────

def test_incident_clock_starts_at_the_incident_not_the_award(spec):
    rt = _awarded_to_a(spec)
    rt.advance_clock(2 * INCIDENT_DEADLINE_STEPS)
    assert rt.check_live_violations().outcome == "ok"
    assert _state(rt, "incidentNotificationBurden", "SupplierA") == "pending"


def test_unawarded_bidder_cannot_report_an_incident(spec):
    rt = _awarded_to_a(spec)
    record = rt.advance("reportIncident", "SupplierB")
    assert record.outcome == "blocked"
    assert "does not fill role 'contractorRole'" in record.reason
    assert _state(rt, "incidentNotificationBurden", "SupplierA") == "pending"


def test_timely_notification_discharges(spec):
    rt = _awarded_to_a(spec)
    rt.advance("reportIncident", "SupplierA")
    assert _state(rt, "incidentNotificationBurden", "SupplierA") == "active"
    rt.advance_clock(60)
    assert rt.advance("notifyIncident", "SupplierA").outcome == "ok"
    assert _state(rt, "incidentNotificationBurden", "SupplierA") == "discharged"
    rt.advance_clock(2 * INCIDENT_DEADLINE_STEPS)
    assert rt.check_live_violations().outcome == "ok"


def test_late_notification_is_violated_and_escalated(spec):
    rt = _awarded_to_a(spec)
    rt.advance("reportIncident", "SupplierA")
    rt.advance_clock(INCIDENT_DEADLINE_STEPS + 1)
    assert rt.check_live_violations().outcome == "violation"
    assert _state(rt, "incidentNotificationBurden", "SupplierA") == "violated"
    rt.fire_violation_responses()
    assert _state(rt, "incidentFollowUpBurden", "BuyerAgency") == "active"


# ── Subcontracting ─────────────────────────────────────────────────────────────

def test_no_subcontracting_before_award(spec):
    rt = _runtime(spec)
    record = rt.advance("subcontractCivilWorks", "SupplierA")
    assert record.outcome == "blocked"
    assert "does not fill role 'contractorRole'" in record.reason


def test_subcontracting_needs_approval_and_stops_on_revocation(spec):
    rt = _awarded_to_a(spec)
    record = rt.advance("subcontractCivilWorks", "SupplierA")
    assert record.outcome == "blocked"
    assert "subcontractApproval" in record.reason
    rt = _approved(rt, spec)
    assert rt.advance("subcontractCivilWorks", "SupplierA").outcome == "ok"
    rt.revoke_authorization("subcontractApprovalForContractor")
    assert _state(rt, "subcontractEmbargo", "SupplierA") == "active"
    record = rt.advance("subcontractCivilWorks", "SupplierA")
    assert record.outcome == "blocked"
    assert "subcontractEmbargo" in record.reason
