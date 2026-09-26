"""
AM-110 — deadline scale factor k (Layer 4, both Kripke builders).

Every enforceable deadline d becomes ceil(d / k) when a model is built
with deadline_scale=k; one step then stands for k unscaled steps. k is
stated per build (default 1) and reported on the model, every verdict,
the T2 label and the summary.

  - Soundness cross-checks: a model at scale k and horizon 10 gives the
    same verdicts as one at scale k/m and horizon 10m, which reaches the
    same deadlines in m times as many steps (erequesting_claiming static and
    hybrid, gp_referral static, public data portal static). Before AM-111
    (one step per minute) the finer model could be unscaled; with deadlines
    now 240 to 20160 steps, k/m replaces k = 1.
  - The terms-of-engagement reading at k = 480 (its configured k since
    AM-111; 40 before), static: recording is compelled; review and
    notification fail with a deadline-violation counterexample.
  - k = 1 leaves every model unchanged; only enforceable deadlines scale;
    hybrid mode re-anchors a seeded activation to the exact remainder
    ceil((d - e) / k).
"""
import contextlib
import io
from pathlib import Path

import pytest

import el_api
from el_api import _SCENARIO_BUILDERS, _SCENARIO_PATHS
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_kripke import (
    NOT_RESOLVED_WITHIN_HORIZON,
    build_kripke_from_runtime,
    build_kripke_model,
    suggest_deadline_scale,
)
from el_parser import parse
from el_runtime import Runtime


_REPO = Path(__file__).resolve().parent.parent
_TOE_DIR = _REPO / "scenarios" / "terms_of_engagement"
_PORTAL = _TOE_DIR / "public_data_portal_scenario.el"
_AGENT_ACCESS = _TOE_DIR / "external_agent_access_scenario.el"

_PORTAL_ACTORS = ["DataAgency", "AgencySecurityContact", "AgencyGateway",
                  "AgentOperator", "ExternalAIAgent"]
_PORTAL_GRANTS = [
    ("refusalRecordBurden", "AgencyGateway"),
    ("refusalReviewBurden", "AgencySecurityContact"),
    ("incidentNotificationBurden", "AgentOperator"),
    ("publishedDatasetReadPermit", "ExternalAIAgent"),
    ("aggregateQueryPermit", "ExternalAIAgent"),
    ("outsideScopeEmbargo", "ExternalAIAgent"),
    ("noCircumventionEmbargo", "ExternalAIAgent"),
]


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _spec(path):
    result = _quiet(parse, path, validate=False)
    assert result.ok, result.errors
    return result.model


def _portal_runtime() -> Runtime:
    spec = _spec(_PORTAL)
    state = initial_state()
    for actor in _PORTAL_ACTORS:
        state = enroll(state, actor)
    for token, holder in _PORTAL_GRANTS:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    return Runtime(state, spec)


def _verdicts(km):
    """AF (or bounded response) outcome, EF discharged, bounded response
    outcome, EF violated — per obligation."""
    out = {}
    for oid in sorted(km.obligation_descriptors):
        af, br = km.check_obligation(oid), km.check_response(oid)
        out[oid] = (
            af.status or af.satisfied,
            km.EF(km.initial, f"discharged:{oid}"),
            br.status or br.satisfied,
            km.EF(km.initial, f"violated:{oid}"),
        )
    return out


# ── Soundness cross-checks: scaled at H = 10 ≡ unscaled at a larger horizon ──

def test_cross_check_erequesting_claiming_static():
    """"4 hours" = 240 steps: 9 at k = 27, 27 at k = 9."""
    spec = _spec(_SCENARIO_PATHS["erequesting_claiming"])
    scaled = _quiet(build_kripke_model, spec, horizon=10, deadline_scale=27)
    wide = _quiet(build_kripke_model, spec, horizon=30, deadline_scale=9)
    assert _verdicts(scaled) == _verdicts(wide)
    assert _verdicts(scaled)["providerAClaimBurden"] == (False, True, False, True)


def test_cross_check_erequesting_claiming_hybrid():
    build = _SCENARIO_BUILDERS["erequesting_claiming"]
    scaled = _quiet(build_kripke_from_runtime, _quiet(build), horizon=10, deadline_scale=27)
    wide = _quiet(build_kripke_from_runtime, _quiet(build), horizon=30, deadline_scale=9)
    assert _verdicts(scaled) == _verdicts(wide)
    for oid in ("providerAClaimBurden", "providerBClaimBurden"):
        assert _verdicts(scaled)[oid] == (False, True, False, True), oid


def test_cross_check_gp_referral_static():
    """k = 2240 at horizon 10 (197 worlds) against k = 56 at horizon 400
    (133,674 worlds) — the largest deadline, "14 days" = 20160 steps, is 9
    and 360 scaled steps. Before AM-111: k = 27 at 10 against k = 1 at 250."""
    spec = _spec(_SCENARIO_PATHS["gp_referral"])
    scaled = _quiet(build_kripke_model, spec, horizon=10, deadline_scale=2240)
    wide = _quiet(build_kripke_model, spec, horizon=400, deadline_scale=56)
    assert _verdicts(scaled) == _verdicts(wide)
    assert _verdicts(scaled)["referralResponseBurden"] == (False, False, False, True)


def test_cross_check_public_data_portal_static():
    """k = 480 at horizon 10 against k = 120 at horizon 40: the 4320-step
    notification deadline is 9 and 36 steps respectively."""
    spec = _spec(_PORTAL)
    scaled = _quiet(build_kripke_model, spec, horizon=10, deadline_scale=480)
    finer = _quiet(build_kripke_model, spec, horizon=40, deadline_scale=120)
    assert _verdicts(scaled) == _verdicts(finer)


# ── The terms-of-engagement reading at k = 480 (static) ──────────────────────

@pytest.mark.parametrize("path", [_PORTAL, _AGENT_ACCESS], ids=lambda p: p.stem)
def test_terms_of_engagement_reading_at_k480(path):
    spec = _spec(path)
    assert suggest_deadline_scale(spec, 10) == 480
    km = _quiet(build_kripke_model, spec, horizon=10, deadline_scale=480)

    record = km.check_obligation("refusalRecordBurden")
    assert (record.satisfied, record.status) == (True, None)

    for oid, scaled, unscaled in (("refusalReviewBurden", 3, 1440),
                                  ("incidentNotificationBurden", 9, 4320)):
        v = km.check_obligation(oid)
        assert (v.satisfied, v.status, v.deadline_scale) == (False, None, 480), oid
        labels = [label for _, label in v.counterexample_path]
        assert labels[-2] == (f"violate:{oid} (deadline={scaled} steps "
                              f"at k=480; {unscaled} unscaled)"), oid
        assert labels[-1].startswith("✗ violated"), oid
        assert f"discharge:{oid}" not in " ".join(labels), oid
        assert km.EF(km.initial, f"discharged:{oid}"), oid  # detectable


def test_notification_not_resolved_unscaled():
    """The k = 1 baseline the scale factor moves (AM-109)."""
    km = _quiet(build_kripke_model, _spec(_PORTAL), horizon=10)
    v = km.check_obligation("incidentNotificationBurden")
    assert (v.satisfied, v.status) == (False, NOT_RESOLVED_WITHIN_HORIZON)
    assert not km.EF(km.initial, "violated:incidentNotificationBurden")


# ── k = 1 leaves every model unchanged ───────────────────────────────────────

def _signature(km):
    return (km.initial, frozenset(km.worlds), dict(km.labels),
            {o: d.deadline_steps for o, d in km.obligation_descriptors.items()})


@pytest.mark.parametrize("name", sorted(_SCENARIO_PATHS))
def test_k1_static_unchanged(name):
    spec = _spec(_SCENARIO_PATHS[name])
    default = _quiet(build_kripke_model, spec, horizon=10)
    explicit = _quiet(build_kripke_model, spec, horizon=10, deadline_scale=1)
    assert _signature(default) == _signature(explicit)
    assert default.deadline_scale == 1
    assert "Deadline scale" not in default.render_summary()


@pytest.mark.parametrize("name", sorted(_SCENARIO_BUILDERS))
def test_k1_hybrid_unchanged(name):
    build = _SCENARIO_BUILDERS[name]
    default = _quiet(build_kripke_from_runtime, _quiet(build), horizon=10)
    explicit = _quiet(build_kripke_from_runtime, _quiet(build), horizon=10, deadline_scale=1)
    assert _signature(default) == _signature(explicit)


# ── What scales, and how k is chosen ─────────────────────────────────────────

def test_only_enforceable_deadlines_scale():
    km = _quiet(build_kripke_model, _spec(_PORTAL), horizon=10, deadline_scale=480)
    steps = {o: d.deadline_steps for o, d in km.obligation_descriptors.items()}
    assert steps == {"refusalRecordBurden": 5,        # no magnitude: untouched
                     "refusalReviewBurden": 3,        # ceil(1440 / 480)
                     "incidentNotificationBurden": 9}  # ceil(4320 / 480)
    assert km.unscaled_deadlines == {"refusalReviewBurden": 1440,
                                     "incidentNotificationBurden": 4320}
    summary = km.render_summary()
    assert "Deadline scale : k=480" in summary
    assert "deadline=9 steps (4320 unscaled, k=480)" in summary
    assert "mode=strict  deadline=none" in summary


@pytest.mark.parametrize("rel, k", [
    ("scenarios/terms_of_engagement/public_data_portal_scenario.el", 480),
    ("scenarios/referral/referral_scenario.el", 2240),
    ("scenarios/gp_referral/gp_referral_scenario.el", 2240),
    ("scenarios/erequesting_claiming/erequesting_claiming_scenario.el", 27),
    ("scenarios/industrial_procedure/industrial_procedure_scenario.el", 2),
    ("scenarios/specialist_pool/specialist_pool_scenario.el", 14),
    ("scenarios/consent/consent_scenario.el", 1),
])
def test_suggest_deadline_scale(rel, k):
    assert suggest_deadline_scale(_spec(_REPO / rel), 10) == k


@pytest.mark.parametrize("bad", [0, -1, 2.5, True])
def test_invalid_scale_rejected(bad):
    with pytest.raises(ValueError):
        _quiet(build_kripke_model, _spec(_PORTAL), horizon=10, deadline_scale=bad)


# ── Hybrid: exact remainder for a burden already PENDING at w0 ───────────────

def _first_violation_step(km, oid):
    steps = {w.step for (_, w), label in km.labels.items()
             if label.startswith(f"violate:{oid}")}
    return min(steps) if steps else None


def _notified_runtime(elapsed: int) -> Runtime:
    """Portal runtime with incidentNotificationBurden PENDING for exactly
    `elapsed` raw ticks (detectIncident itself advances the tick by one)."""
    rt = _portal_runtime()
    assert rt.advance("detectIncident", "AgentOperator").outcome == "ok"
    state = rt.current_state()
    tok = next(t for t in state.tokens if t.token_name == "incidentNotificationBurden")
    already = state.tick - tok.activated_at_tick
    if elapsed > already:
        rt.advance_clock(elapsed - already)
    return rt


def test_hybrid_exact_remainder():
    """d = 4320, k = 500, e = 450: ceil(3870 / 500) = 8 scaled steps remain.
    The floor approximation (ceil(4320/500) - floor(450/500) = 9) would be
    one step late."""
    rt = _notified_runtime(450)
    state = rt.current_state()
    tok = next(t for t in state.tokens if t.token_name == "incidentNotificationBurden")
    e = state.tick - tok.activated_at_tick
    assert e == 450
    km = _quiet(build_kripke_from_runtime, rt, horizon=10, deadline_scale=500)
    assert km.obligation_descriptors["incidentNotificationBurden"].deadline_steps == 9
    assert _first_violation_step(km, "incidentNotificationBurden") == state.tick + 8


def test_hybrid_overdue_violable_at_w0():
    """e >= d: the violation is available at w0, scaled or not."""
    rt = _notified_runtime(4400)  # past the 4320-step deadline
    tick = rt.current_state().tick
    for k in (1, 480):
        km = _quiet(build_kripke_from_runtime, rt, horizon=10, deadline_scale=k)
        assert _first_violation_step(km, "incidentNotificationBurden") == tick, k


def test_hybrid_label_names_both_deadlines():
    rt = _notified_runtime(1)
    km = _quiet(build_kripke_from_runtime, rt, horizon=10, deadline_scale=480)
    labels = {label for label in km.labels.values()
              if label.startswith("violate:incidentNotificationBurden")}
    assert labels == {"violate:incidentNotificationBurden "
                      "(deadline=9 steps at k=480; 4320 unscaled)"}
    unscaled = _quiet(build_kripke_from_runtime, rt, horizon=10)
    assert _first_violation_step(unscaled, "incidentNotificationBurden") is None


# ── API: k is a per-request parameter, echoed in the response ────────────────

@pytest.fixture
def referral_api(monkeypatch):
    """Pin the API's shared runtime and active scenario: other tests switch
    or advance them."""
    monkeypatch.setattr(el_api, "_runtime", _quiet(_SCENARIO_BUILDERS["referral"]))
    monkeypatch.setattr(el_api, "_active_scenario", "referral")
    return el_api


def test_status_and_witness_endpoints_report_k(referral_api):
    status = el_api.get_obligation_status("referralResponseBurden")
    assert status.deadline_scale == 1
    scaled = el_api.get_obligation_status("referralResponseBurden", deadline_scale=2240)
    assert scaled.deadline_scale == 2240

    witness = el_api.get_witness_path("violated:referralResponseBurden")
    assert (witness["deadline_scale"], witness["witness_path"]) == (1, [])
    witness = el_api.get_witness_path("violated:referralResponseBurden", deadline_scale=2240)
    assert witness["deadline_scale"] == 2240
    assert witness["witness_path"][-1]["edge_from_previous"].startswith(
        "violate:referralResponseBurden (deadline=5 steps at k=2240; 10080 unscaled)")


def test_endpoints_reject_scale_below_one(referral_api):
    from fastapi import HTTPException
    for call in (lambda: el_api.get_obligation_status("referralResponseBurden", deadline_scale=0),
                 lambda: el_api.get_witness_path("discharged:x", deadline_scale=0)):
        with pytest.raises(HTTPException) as exc:
            call()
        assert exc.value.status_code == 400
