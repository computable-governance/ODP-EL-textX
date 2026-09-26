"""
AM-108 — deadlines with no elapsed-time magnitude: T2 skip, T2b, [W-24].

A burden whose deadline has no elapsed-time magnitude (prose such as
"referral episode", a bare number, or none) is never violated by the
engine's clock (check_live_violations() requires
_has_deadline_magnitude()). Before AM-108 both Kripke builders' T2 violated
it at the parser's default of 5 steps. Now T2 skips it, and T2b mirrors the
engine's other path: an eventual such burden is violated when its opted-in
satisfaction group (on_objective_achieved) concludes around it (DN_010
option b). [W-24] flags an eventual such burden that has neither path.

Also pins the consent scenario's recommended order and values, so the
figures used in writing have a reproducible source.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_api import _SCENARIO_BUILDERS
from el_kripke import (
    NOT_RESOLVED_WITHIN_HORIZON,
    ObligationState,
    build_kripke_from_runtime,
    build_kripke_model,
)
from el_parser import parse, parse_string
from el_runtime import Runtime

_ROOT = Path(__file__).resolve().parent.parent


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _labels(km, oid):
    return {label for label in km.labels.values() if label.startswith(f"violate:{oid}")}


# ── T2 skip ───────────────────────────────────────────────────────────────

_PROSE_PROBE = """
enterprise specification ProseDeadlineProbe

party Holder {{
    holds proseBurden
}}

burden proseBurden {{ for_action: "act" state: active deadline: "{deadline}" discharge_mode: {mode} }}
commitment C {{ by: Holder obligation: "act" creates_burden: proseBurden }}
"""


def _prose_models(deadline="end of session", mode="eventual"):
    model = _quiet(parse_string, _PROSE_PROBE.format(deadline=deadline, mode=mode),
                   validate=False).model
    return model, {
        "static": _quiet(build_kripke_model, model, horizon=10),
        "hybrid": _quiet(build_kripke_from_runtime, _quiet(Runtime.build_from_spec, model), horizon=10),
    }


@pytest.mark.parametrize("builder", ["static", "hybrid"])
@pytest.mark.parametrize("deadline", ["end of session", "10"])
def test_no_magnitude_deadline_never_clock_violated(builder, deadline):
    """Prose or a bare number: no violation edge, so AF is not resolved
    within the horizon (before AM-108: violated at 5 steps, AF false)."""
    _, models = _prose_models(deadline)
    km = models[builder]
    assert "proseBurden" not in km.enforceable_deadlines
    assert km.obligation_descriptors["proseBurden"].deadline_steps == 5  # descriptor unchanged
    assert km.EF(km.initial, "violated:proseBurden") is False
    verdict = km.check_obligation("proseBurden")
    assert verdict.satisfied is False and verdict.status == NOT_RESOLVED_WITHIN_HORIZON
    assert "deadline=none" in km.render_summary()


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_magnitude_deadline_still_violated(builder):
    _, models = _prose_models("1 hour")
    km = models[builder]
    assert "proseBurden" in km.enforceable_deadlines
    assert km.EF(km.initial, "violated:proseBurden") is True
    assert "deadline=5 steps" in km.render_summary()


# ── T2b: episode conclusion ───────────────────────────────────────────────

_EPISODE_PROBE = """
enterprise specification EpisodeConclusionProbe

party Holder {
    holds mainBurden
    holds tailBurden
    holds strictTail
}

burden mainBurden { for_action: "doMain" state: active deadline: "1 week" discharge_mode: eventual }
burden tailBurden { for_action: "doTail" state: active deadline: "episode" discharge_mode: eventual }
burden strictTail { for_action: "doStrict" state: active deadline: "episode" discharge_mode: strict }

commitment C1 { by: Holder obligation: "main" creates_burden: mainBurden }
commitment C2 { by: Holder obligation: "tail" creates_burden: tailBurden }
commitment C3 { by: Holder obligation: "strict tail" creates_burden: strictTail }

token_group episodeGroup {
    member: mainBurden
    member: tailBurden
    member: strictTail
}

community EpisodeCommunity {
    objective: "probe episode conclusion"
        satisfaction: all_discharged(episodeGroup)
    lifecycle {
        terminating {
            on_objective_achieved: true
        }
    }
}
"""


def _episode_models():
    model = _quiet(parse_string, _EPISODE_PROBE, validate=False).model
    return model, {
        "static": _quiet(build_kripke_model, model, horizon=10),
        "hybrid": _quiet(build_kripke_from_runtime, _quiet(Runtime.build_from_spec, model), horizon=10),
    }


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_t2b_violates_on_episode_conclusion_only(builder):
    """tailBurden is violated only once every other group member is
    resolved, labelled "episode concluded"; the strict member never."""
    _, models = _episode_models()
    km = models[builder]
    edges = [(w, s) for (w, s), label in km.labels.items()
             if label == "violate:tailBurden (episode concluded)"]
    assert edges
    resolved = (ObligationState.DISCHARGED, ObligationState.SUPERSEDED)
    for w, s in edges:
        assert dict(w.obligation_states)["mainBurden"] in resolved
        assert dict(w.obligation_states)["strictTail"] in resolved
        assert s.step == w.step
    assert _labels(km, "tailBurden") == {"violate:tailBurden (episode concluded)"}
    assert _labels(km, "strictTail") == set()


def test_t2b_matches_engine():
    """The engine violates tailBurden in check_live_violations() exactly when
    the other members are resolved — the condition T2b models."""
    model, _ = _episode_models()
    rt = _quiet(Runtime.build_from_spec, model)
    assert rt.check_live_violations().violations == ()
    rt.discharge_burden("mainBurden")
    assert rt.check_live_violations().violations == ()
    rt.discharge_burden("strictTail")
    assert rt.check_live_violations().violations == ("tailBurden",)


def test_referral_violations_come_only_from_t2b():
    """referral's two "referral episode" burdens: in the hybrid model their
    only violations are T2b's; in the static model none (before AM-108,
    T2's default 5 steps violated both). Static: the rest of the episode
    does not conclude within horizon 10."""
    hybrid = _quiet(build_kripke_from_runtime, _quiet(_SCENARIO_BUILDERS["referral"]), horizon=10)
    static = _quiet(build_kripke_model,
                    _quiet(parse, _ROOT / "scenarios/referral/referral_scenario.el", validate=False).model,
                    horizon=10)
    for oid in ("aiExaminationBurden", "clinicalHandoverBurden"):
        assert _labels(hybrid, oid) == {f"violate:{oid} (episode concluded)"}
        assert _labels(static, oid) == set()


def test_gp_referral_clinical_handover_never_violated():
    """In gp_referral, clinicalHandoverBurden ("referral episode") is only
    in ReferralFederation's group, which does not opt in: no path."""
    km = _quiet(build_kripke_model,
                _quiet(parse, _ROOT / "scenarios/gp_referral/gp_referral_scenario.el", validate=False).model,
                horizon=10)
    assert km.EF(km.initial, "violated:clinicalHandoverBurden") is False


# ── [W-24] ────────────────────────────────────────────────────────────────

_EXPECTED_W24 = {
    "scenarios/consent/consent_scenario.el": {"reportingObligation"},
    "scenarios/ereferral/ereferral_model.el": {"acknowledgementBurden"},
    "scenarios/gp_referral/gp_referral_scenario.el": {"clinicalHandoverBurden"},
    "scenarios/probes/transfer_probe.el": {"probeBurden", "noFromRoleBurden",
                                           "ambiguousFromBurden", "unfilledToBurden"},
    "scenarios/referral/referral_scenario.el": set(),
    "scenarios/terms_of_engagement/public_data_portal_scenario.el": set(),
}


@pytest.mark.parametrize("rel", sorted(_EXPECTED_W24))
def test_w24_in_tracked_scenarios(rel):
    """Fires on eventual no-magnitude burdens with no conclusion path; not on
    referral's aiExaminationBurden/clinicalHandoverBurden (opted-in group),
    and not on strict burdens ([W-19]'s)."""
    result = _quiet(parse, _ROOT / rel)
    named = {w.split("'")[1] for w in result.warnings if w.startswith("[W-24]")}
    assert named == _EXPECTED_W24[rel]


def test_w24_message():
    result = _quiet(parse_string, _PROSE_PROBE.format(deadline="end of session", mode="eventual"))
    assert [w for w in result.warnings if w.startswith("[W-24]")] == [
        "[W-24] Eventual burden 'proseBurden' has no enforceable deadline "
        "('end of session') and no episode-conclusion path: it is never "
        "violated, at runtime or in the verifier. Give it a deadline with a "
        "time unit, or put it in a satisfaction group whose community opts in "
        "with on_objective_achieved. (§6.4.3, §7.8.7)"
    ]


# ── consent: recommended order and values, reproducible ───────────────────

def test_consent_recommended_order_and_values():
    """Static model of scenarios/consent/consent_scenario.el, horizon 10,
    gamma 0.9 (the API's discount).

    - recommend_action(w0): immediate utility and expected future utility
      (mean utility over worlds reachable from the successor, §C.4).
    - Bellman Q(w0, a) = utility(successor) + 0.9 * V*(successor), as the
      API's /recommended-action computes it (§C.4 value iteration).

    Seeking consent ranks first under both. AM-108 changed only
    seekConsentObligation's expected future utility, 0.8593 -> 0.93 (the
    fictional violation of reportingObligation, "end of session", is gone;
    it is now 0.93 at any horizon). The EDOC 2026 figures (+0.980 / +0.920)
    are not reproducible from this code at HEAD before or after AM-108 and
    have no source in the repository; the order they illustrate holds."""
    model = _quiet(parse, _ROOT / "scenarios/consent/consent_scenario.el", validate=False).model
    km = _quiet(build_kripke_model, model, horizon=10)

    recs = [(r.action_label, round(r.immediate_utility, 4), round(r.expected_future_utility, 4))
            for r in km.recommend_action(km.initial)]
    assert recs == [
        ("discharge:seekConsentObligation by AIDiagnosticAgent", 0.86, 0.93),
        ("discharge:reportingObligation by GPPracticeParty", 0.44, 0.72),
    ]

    gamma = 0.9
    V = km.bellman_values(gamma=gamma)
    q = sorted(((km.labels[(km.initial, s)], round(km.utility(s) + gamma * V.get(s, 0.0), 4))
                for s in km.ordered_successors(km.initial)), key=lambda x: (-x[1], x[0]))
    assert q == [
        ("discharge:seekConsentObligation by AIDiagnosticAgent", 6.4975),
        ("discharge:reportingObligation by GPPracticeParty", 2.15),
    ]
