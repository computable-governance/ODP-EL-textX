"""
AM-101 — Rule T5 (Exercise) strict-mode guard, both Kripke builders.

The engine's Step 3.5 (AM-78) refuses an action that discharges nothing
while a discharge_mode: strict burden is actionable. Exercising a permit
discharges nothing unless its action also discharges a burden the actor
holds (Step 3's `dischargeable`: a destroy effect, a matching for_action,
or an emitted event that is the burden's discharged_by). Before AM-101
neither builder's T5 had this guard, so the verifier explored exercises
the engine refuses.

  - Parity, inline fixture: from a state where a strict burden is
    actionable, each permit's exercise edge exists in both builders iff
    the engine accepts the action — refused when it discharges nothing,
    kept for each of the three `dischargeable` arms.
  - Parity, real scenario: after a refusal in the terms-of-engagement
    scenario, the engine refuses both exercises and neither builder has
    a T5 edge from that state.
  - Invariant over the scenarios the guard changed (AM-101 Phase 1): no
    T5 edge leaves a strict-blocked world, in either builder. None of
    their exercised actions discharges anything (verified in Phase 1),
    so the unconditional form of the invariant is the right one.

No world/edge counts are pinned; the Phase 1 before/after table is in
the AM-101 entry of docs/el_grammar_amendments.md.
"""
import contextlib
import io
from pathlib import Path

import pytest

from el_api import _SCENARIO_BUILDERS
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_kripke import (
    ActorStatus,
    ObligationState,
    build_kripke_from_runtime,
    build_kripke_model,
)
from el_parser import parse, parse_string
from el_runtime import Runtime

import test_am99b_hybrid_event_model as toe_tests
import test_public_data_portal_scenario as pdp_tests


_REPO = Path(__file__).resolve().parent.parent


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _exercise_actions(km, w):
    """Actions exercised on T5 edges leaving w."""
    return {
        km.labels[(w, s)].split(" → ", 1)[1]
        for s in km.successors(w)
        if km.labels[(w, s)].startswith("exercise:")
    }


def _strict_blocked(km, w):
    """Some PENDING strict obligation has an ACTIVE holder. The holder is
    the T9 override if any, else the descriptor's; no rule makes an actor
    INACTIVE, so a revoked delegation's delegator reads the same way."""
    obligs, actors = w.obligation_dict(), w.actor_dict()
    overrides = w.holder_override_dict()
    return any(
        obligs.get(oid) == ObligationState.PENDING
        and d.discharge_mode == "strict"
        and actors.get(overrides.get(oid, d.holder)) == ActorStatus.ACTIVE
        for oid, d in km.obligation_descriptors.items()
    )


# ── Parity: inline fixture covering each `dischargeable` arm ────────────────

_PROBE = """
enterprise specification StrictT5Probe

agent Gate {
    holds recordBurden
}

agent Worker {
    holds readPermit
    holds notePermit
    holds purgePermit
    holds closePermit
    holds noteBurden
    holds cacheBurden
    holds ticketBurden
}

burden recordBurden {
    for_action: "recordIt"
    state: active
    discharge_mode: strict
}

permit readPermit {
    for_action: "readData"
    state: active
}

permit notePermit {
    for_action: "fileNote"
    state: active
}

permit purgePermit {
    for_action: "purgeCache"
    state: active
}

permit closePermit {
    for_action: "closeTicket"
    state: active
}

burden noteBurden {
    for_action: "fileNote"
    state: active
    discharge_mode: eventual
}

burden cacheBurden {
    for_action: "clearCache"
    state: active
    discharge_mode: eventual
}

burden ticketBurden {
    for_action: "handleTicket"
    state: active
    discharged_by: ticketClosed
    discharge_mode: eventual
}

community ProbeCommunity {
    objective: "probe the T5 strict guard"
    event ticketClosed

    role gateRole {
        action recordIt {
            actor: gateRole
        }
    }

    role workerRole {
        action readData {
            actor: workerRole
            requires_permit readPermit
        }
        action fileNote {
            actor: workerRole
            requires_permit notePermit
        }
        action purgeCache {
            actor: workerRole
            requires_permit purgePermit
            effect destroy cacheBurden
        }
        action closeTicket {
            actor: workerRole
            requires_permit closePermit
            emits: ticketClosed
        }
    }
}

commitment GateRecords {
    by: Gate
    obligation: "record promptly"
    creates_burden: recordBurden
}

commitment WorkerNotes {
    by: Worker
    obligation: "file a note"
    creates_burden: noteBurden
}

commitment WorkerClearsCache {
    by: Worker
    obligation: "clear the cache"
    creates_burden: cacheBurden
}

commitment WorkerHandlesTicket {
    by: Worker
    obligation: "handle the ticket"
    creates_burden: ticketBurden
}
"""

_PROBE_GRANTS = [
    ("recordBurden", "Gate"),
    ("readPermit", "Worker"), ("notePermit", "Worker"),
    ("purgePermit", "Worker"), ("closePermit", "Worker"),
    ("noteBurden", "Worker"), ("cacheBurden", "Worker"), ("ticketBurden", "Worker"),
]

# action -> engine accepts it while recordBurden is actionable
_PROBE_EXPECTED = {
    "readData": False,     # discharges nothing: refused
    "fileNote": True,      # matches noteBurden's for_action
    "purgeCache": True,    # destroy effect on cacheBurden
    "closeTicket": True,   # emits ticketBurden's discharged_by
}


@pytest.fixture(scope="module")
def probe_spec():
    result = parse_string(_PROBE, validate=False)
    assert result.ok, result.errors
    return result.model


def _probe_runtime(spec) -> Runtime:
    state = initial_state()
    for actor in ("Gate", "Worker"):
        state = enroll(state, actor)
    for token, holder in _PROBE_GRANTS:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    return Runtime(state, spec)


@pytest.mark.parametrize("action", sorted(_PROBE_EXPECTED))
def test_probe_engine_outcomes(probe_spec, action):
    rec = _probe_runtime(probe_spec).advance(action, "Worker")
    assert (rec.outcome == "ok") is _PROBE_EXPECTED[action], rec.reason
    if not _PROBE_EXPECTED[action]:
        assert "strict burden 'recordBurden'" in rec.reason


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_probe_t5_edges_match_engine(probe_spec, builder):
    if builder == "static":
        km = _quiet(build_kripke_model, probe_spec, horizon=5)
    else:
        km = _quiet(build_kripke_from_runtime, _probe_runtime(probe_spec), horizon=5)
    assert _strict_blocked(km, km.initial)
    engine_ok = set()
    for action in _PROBE_EXPECTED:
        if _probe_runtime(probe_spec).advance(action, "Worker").outcome == "ok":
            engine_ok.add(action)
    assert _exercise_actions(km, km.initial) == engine_ok


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_probe_exercise_returns_after_strict_discharge(probe_spec, builder):
    """Control: once recordBurden is discharged, readData is exercisable
    in the model, and the engine accepts it."""
    if builder == "static":
        km = _quiet(build_kripke_model, probe_spec, horizon=5)
    else:
        km = _quiet(build_kripke_from_runtime, _probe_runtime(probe_spec), horizon=5)
    (w,) = [s for s in km.successors(km.initial)
            if km.labels[(km.initial, s)].startswith("discharge:recordBurden")]
    assert "readData" in _exercise_actions(km, w)

    rt = _probe_runtime(probe_spec)
    assert rt.advance("recordIt", "Gate").outcome == "ok"
    assert rt.advance("readData", "Worker").outcome == "ok"


# ── Parity: terms-of-engagement scenario after a refusal ─────────────────────

def test_toe_after_refusal_parity():
    spec = _quiet(parse, toe_tests._TOE).model
    rt = toe_tests._after_refusal(spec)
    for action in ("submitServiceRequest", "readPatientDemographics"):
        probe = toe_tests._after_refusal(spec)
        rec = probe.advance(action, "VendorReferralAgent")
        assert rec.outcome == "blocked"
        assert "strict burden 'refusalRecordBurden'" in rec.reason

    hybrid = _quiet(build_kripke_from_runtime, rt, horizon=10)
    assert _strict_blocked(hybrid, hybrid.initial)
    assert _exercise_actions(hybrid, hybrid.initial) == set()

    # Static: every world with the same obligation states as the engine's
    # post-refusal state (refusalRecordBurden pending, the rest waiting).
    static = _quiet(build_kripke_model, spec, horizon=10)
    target = {oid: ObligationState.WAITING for oid in static.obligation_descriptors}
    target["refusalRecordBurden"] = ObligationState.PENDING
    matches = [w for w in static.worlds if w.obligation_dict() == target]
    assert matches
    for w in matches:
        assert _exercise_actions(static, w) == set()


# ── Invariant over the scenarios AM-101 changed ──────────────────────────────

def _static(rel):
    result = _quiet(parse, _REPO / rel, validate=False)  # gp_referral fails V-NEW-10
    assert result.ok, result.errors
    return _quiet(build_kripke_model, result.model, horizon=10)


def _hybrid_toe():
    spec = _quiet(parse, toe_tests._TOE).model
    return _quiet(build_kripke_from_runtime, toe_tests._toe_runtime(spec), horizon=10)


def _hybrid_pdp():
    spec = _quiet(parse, pdp_tests._SCENARIO).model
    return _quiet(build_kripke_from_runtime, pdp_tests._runtime(spec), horizon=10)


_STATIC_CASES = [
    "scenarios/referral/referral_scenario.el",
    "scenarios/gp_referral/gp_referral_scenario.el",
    "scenarios/ereferral/ereferral_model.el",
    "scenarios/terms_of_engagement/external_agent_access_scenario.el",
    "scenarios/terms_of_engagement/public_data_portal_scenario.el",
    "scenarios/fhir/generated_governance.el",
]

_HYBRID_CASES = {
    "referral": lambda: _quiet(build_kripke_from_runtime, _SCENARIO_BUILDERS["referral"](), horizon=10),
    "gp_referral": lambda: _quiet(build_kripke_from_runtime, _SCENARIO_BUILDERS["gp_referral"](), horizon=10),
    "ereferral": lambda: _quiet(build_kripke_from_runtime, _SCENARIO_BUILDERS["ereferral"](), horizon=10),
    "external_agent_access": _hybrid_toe,
    "public_data_portal": _hybrid_pdp,
}


def _assert_no_blocked_exercise(km):
    bad = sorted({
        km.labels[(w, s)]
        for w in km.worlds if _strict_blocked(km, w)
        for s in km.successors(w)
        if km.labels[(w, s)].startswith("exercise:")
    })
    assert bad == []


@pytest.mark.parametrize("rel", _STATIC_CASES)
def test_static_no_t5_edge_from_strict_blocked_world(rel):
    _assert_no_blocked_exercise(_static(rel))


@pytest.mark.parametrize("name", sorted(_HYBRID_CASES))
def test_hybrid_no_t5_edge_from_strict_blocked_world(name):
    _assert_no_blocked_exercise(_HYBRID_CASES[name]())
