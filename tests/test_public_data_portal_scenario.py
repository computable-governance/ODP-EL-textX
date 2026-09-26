"""
Public data portal scenario — sibling of the terms-of-engagement referral
scenario, modelled on the 2026 Medicare portal incident: an external AI
agent READING a public statistics portal, where the harm was reaching
non-public files.

Pins the same reading as the referral scenario, from both builders:
recording refusals is guaranteed (bounded response property holds);
reviewing refusals and notifying incidents are only detectable. Also pins
the engine side: non-public files are blocked from entry, a refusal blocks
everything until recorded, and afterwards only the workaround is blocked.
"""
import contextlib
import io

import pytest

from el_api import _PUBLIC_DATA_PORTAL_SCENARIO as _SCENARIO
from el_api import _build_public_data_portal_runtime as _runtime
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse


_EXPECTED = {
    "refusalRecordBurden": True,
    "refusalReviewBurden": False,
    "incidentNotificationBurden": False,
}


@pytest.fixture(scope="module")
def spec():
    result = parse(_SCENARIO)
    assert result.ok, result.errors
    # AM-103: [W-19]/[W-20] on refusalRecordBurden (no measurable deadline,
    # no ViolationResponse) are known deployment gaps, pending the
    # violation-declaration amendment; so is AM-104's [W-22] on
    # missedReviewResponse (escalate, no creates_burden), pending that
    # amendment's scenario edits. Any other warning is unexpected.
    others = [w for w in result.warnings if not w.startswith(("[W-19]", "[W-20]", "[W-22]"))]
    assert not others, others
    return result.model


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def test_static_verdicts(spec):
    km = _quiet(build_kripke_model, spec, horizon=10)
    for oid, expected in _EXPECTED.items():
        v = km.check_obligation(oid)
        assert v.satisfied is expected, oid
        if not expected:
            assert km.EF(km.initial, f"discharged:{oid}"), oid


def test_hybrid_verdicts_after_refusal_match_static(spec):
    rt = _runtime(spec)
    assert rt.advance("refuseRequest", "AgencyGateway").outcome == "ok"
    km = _quiet(build_kripke_from_runtime, rt, horizon=10)
    for oid, expected in _EXPECTED.items():
        assert km.check_obligation(oid).satisfied is expected, oid
    assert all(dict(w.embargo_states).get("noCircumventionEmbargo") == "active"
               for w in km.worlds)


def test_accountability_chains(spec):
    km = _quiet(build_kripke_model, spec, horizon=10)
    assert km.check_obligation("refusalRecordBurden").chain == ["DataAgency", "AgencyGateway"]
    assert km.check_obligation("refusalReviewBurden").chain == ["DataAgency", "AgencySecurityContact"]
    assert km.check_obligation("incidentNotificationBurden").chain == ["AgentOperator"]


def test_engine_blocks_non_public_files_from_entry(spec):
    rt = _runtime(spec)
    assert rt.advance("accessNonPublicFile", "ExternalAIAgent").outcome == "blocked"
    assert rt.advance("readPublishedDataset", "ExternalAIAgent").outcome == "ok"


def test_engine_refusal_blocks_all_until_recorded_then_only_workaround(spec):
    rt = _runtime(spec)
    assert rt.advance("refuseRequest", "AgencyGateway").outcome == "ok"
    assert rt.advance("readPublishedDataset", "ExternalAIAgent").outcome == "blocked"
    assert rt.advance("recordRefusal", "AgencyGateway").outcome == "ok"
    assert rt.advance("readPublishedDataset", "ExternalAIAgent").outcome == "ok"
    assert rt.advance("runAggregateQuery", "ExternalAIAgent").outcome == "ok"
    assert rt.advance("retryByOtherRoute", "ExternalAIAgent").outcome == "blocked"
    assert rt.advance("accessNonPublicFile", "ExternalAIAgent").outcome == "blocked"
