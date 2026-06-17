"""
el_api.py
=========
Agent-facing coordination query API (Layer 3/4 bridge).

Endpoints implemented:
  GET /actors/{actor_name}/available-actions
  GET /communities/{community_name}/objective-reachable
  GET /communities/{community_name}/objective-score

Design reference: coordination_design_note_v3.md §9 (agent-facing query surface)
Standard reference: ISO/IEC 15414:2015 §6.4, §6.6, Annex C
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_kripke import build_kripke_from_runtime
from el_parser import parse
from el_runtime import Runtime


# ── Runtime initialisation ────────────────────────────────────────────────────

_SCENARIO = _REPO_ROOT / "scenarios" / "gp_referral" / "gp_referral_scenario.el"
_KRIPKE_HORIZON = 10


def _build_gp_referral_runtime() -> Runtime:
    """
    Parse the GP-referral scenario and initialise a Runtime with actors enrolled
    and tokens granted to their actual holders.

    build_from_federation() is not used: ReferralFederation's members are
    Community elements, not Domain elements, so its actor-collection step
    produces nothing and no tokens are granted. build_from_spec() has a
    documented gap for Commitment/Delegation-assigned tokens. We enrol
    explicitly, matching the scenario's accountability structure.

    Role assignments:
      GPClinician fills gpClinicianRole (declared at GPPracticeCommunity line 250;
        confirmed against the file — no explicit fills_role declaration exists,
        only assignment_policy requirements and on_join/on_leave effects).
      SpecialistClinicianAgent fills specialistRole (declared at SpecialistCommunity
        line 319; same gap — no fills_role declaration, inferred from holds +
        delegated_from + assignment_policy).
      GPPracticeParty and SpecialistParty are parties (principals), not role-fillers.

    Token grants:
      GPClinician           — referralInitiationBurden, clinicalHandoverBurden
      SpecialistParty       — assessmentSchedulingBurden
      SpecialistClinicianAgent — referralResponseBurden, patientRecordAccessPermit
    """
    result = parse(_SCENARIO, validate=False)
    if not result.ok:
        raise RuntimeError(f"GP-referral parse failed: {result.errors}")

    spec = result.model
    state = initial_state()

    state = enroll(state, "GPPracticeParty")
    state = enroll(state, "GPClinician",              role_name="gpClinicianRole")
    state = enroll(state, "SpecialistParty")
    state = enroll(state, "SpecialistClinicianAgent",  role_name="specialistRole")

    for token_name, holder in [
        ("referralInitiationBurden",   "GPClinician"),
        ("clinicalHandoverBurden",     "GPClinician"),
        ("assessmentSchedulingBurden", "SpecialistParty"),
        ("referralResponseBurden",     "SpecialistClinicianAgent"),
        ("patientRecordAccessPermit",  "SpecialistClinicianAgent"),
    ]:
        state = grant_token(state, token_from_spec(spec, token_name, holder))

    return Runtime(state, spec)


_runtime = _build_gp_referral_runtime()


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(
    title="ODP-EL Agent Coordination API",
    description=(
        "Read-only coordination query endpoints for agents operating under "
        "ODP Enterprise Language governance (ISO/IEC 15414:2015)."
    ),
    version="0.1.0",
)


# ── Response models ───────────────────────────────────────────────────────────

class AvailableAction(BaseModel):
    action: str
    reason: str            # "obligated" | "permitted"
    token: str             # burden or permit name that makes this action available
    deadline: Optional[str] = None


class AvailableActionsResponse(BaseModel):
    actor: str
    available_actions: List[AvailableAction]


class ObjectiveReachableResponse(BaseModel):
    community: str
    objective_reachable: bool
    has_satisfaction_condition: bool  # False means spec declares no condition; EF result is vacuously false
    worlds_checked: int
    proposition: str   # "objective_satisfied:<community_name>"
    modal_operator: str  # always "EF"
    horizon: int


class ScoredObligation(BaseModel):
    obligation: str
    state: str           # DISCHARGED | PENDING | VIOLATED | EXPIRED | SUPERSEDED | WAITING
    priority_weight: float


class ObjectiveScoreResponse(BaseModel):
    community: str
    objective_score: Optional[float]  # null when has_satisfaction_condition=false
    has_satisfaction_condition: bool
    breakdown: List[ScoredObligation]
    worlds_checked: int
    horizon: int


# ── Endpoint 1: GET /actors/{actor_name}/available-actions ────────────────────

@app.get(
    "/actors/{actor_name}/available-actions",
    response_model=AvailableActionsResponse,
    summary="Return the actions an actor can take right now",
    description=(
        "Synthesises available actions from the actor's current permits, "
        "embargoes, and active obligations. Each entry is tagged 'obligated' "
        "(an active burden requires the action) or 'permitted' (a permit grants "
        "it and no embargo blocks it). Reads directly from the current Layer 3 "
        "runtime state — no Kripke model is needed for this endpoint."
    ),
)
def get_available_actions(actor_name: str) -> AvailableActionsResponse:
    state = _runtime.current_state()

    # 404 if actor is not enrolled in the current runtime
    enrolled = {a.actor_name for a in state.actors}
    if actor_name not in enrolled:
        raise HTTPException(
            status_code=404,
            detail=f"Actor '{actor_name}' is not enrolled in the current runtime.",
        )

    # Collect the actor's active embargoes.
    # for_action=None means the embargo blocks all actions; a named for_action
    # blocks only that specific action (mirrors el_engine.py step 5 logic).
    active_embargoes: set[Optional[str]] = set()
    for tok in state.tokens:
        if tok.holder == actor_name and tok.kind == "embargo" and tok.state == "active":
            active_embargoes.add(tok.for_action)

    def _is_embargoed(action_name: str) -> bool:
        return None in active_embargoes or action_name in active_embargoes

    actions: List[AvailableAction] = []

    for tok in state.tokens:
        if tok.holder != actor_name:
            continue
        if tok.state != "active":
            continue
        if not tok.for_action:
            continue  # token carries no action association — nothing to surface

        if tok.kind == "burden":
            actions.append(AvailableAction(
                action=tok.for_action,
                reason="obligated",
                token=tok.token_name,
                deadline=tok.deadline,
            ))
        elif tok.kind == "permit":
            if not _is_embargoed(tok.for_action):
                actions.append(AvailableAction(
                    action=tok.for_action,
                    reason="permitted",
                    token=tok.token_name,
                    deadline=None,
                ))

    return AvailableActionsResponse(actor=actor_name, available_actions=actions)


# ── Endpoint 2: GET /communities/{community_name}/objective-reachable ─────────

@app.get(
    "/communities/{community_name}/objective-reachable",
    response_model=ObjectiveReachableResponse,
    summary="Check whether a community's objective is still reachable from current runtime state",
    description=(
        "Builds a Kripke model anchored to the current Layer 3 runtime state "
        "(hybrid mode: build_kripke_from_runtime) and runs EF on "
        "objective_satisfied:<community_name>. Returns whether the community's "
        "declared satisfaction condition can still be met on at least one future "
        "path from here. has_satisfaction_condition=false means the spec declares "
        "no SatisfactionCondition for this community — the EF result is vacuously "
        "false, not a reachability failure. 404 for an unknown community name."
    ),
)
def get_objective_reachable(community_name: str) -> ObjectiveReachableResponse:
    # Collect all declared community-type elements for 404 check
    known_communities = {
        el.name
        for el in _runtime._spec.elements
        if type(el).__name__ in ("Community", "Federation", "Domain")
    }
    if community_name not in known_communities:
        raise HTTPException(
            status_code=404,
            detail=f"Community '{community_name}' is not declared in the current spec.",
        )

    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    prop = f"objective_satisfied:{community_name}"
    has_condition = community_name in km.satisfaction_conditions
    reachable = km.EF(km.initial, prop)

    return ObjectiveReachableResponse(
        community=community_name,
        objective_reachable=reachable,
        has_satisfaction_condition=has_condition,
        worlds_checked=len(km.worlds),
        proposition=prop,
        modal_operator="EF",
        horizon=_KRIPKE_HORIZON,
    )


# ── Endpoint 3: GET /communities/{community_name}/objective-score ─────────────

@app.get(
    "/communities/{community_name}/objective-score",
    response_model=ObjectiveScoreResponse,
    summary="Score a community's objective against the current runtime state",
    description=(
        "Builds a Kripke model anchored to the current Layer 3 runtime state "
        "(hybrid mode: build_kripke_from_runtime) and evaluates "
        "utility_for_objective(community_name, initial_world). Returns a "
        "weighted score in [-1.0, +1.0] reflecting obligation outcomes in the "
        "current world, plus a per-obligation breakdown showing each member's "
        "state and priority weight. has_satisfaction_condition=false means the "
        "spec declares no SatisfactionCondition for this community — "
        "objective_score is null (not a failure; the objective is simply "
        "unscored). 404 for an unknown community name."
    ),
)
def get_objective_score(community_name: str) -> ObjectiveScoreResponse:
    known_communities = {
        el.name
        for el in _runtime._spec.elements
        if type(el).__name__ in ("Community", "Federation", "Domain")
    }
    if community_name not in known_communities:
        raise HTTPException(
            status_code=404,
            detail=f"Community '{community_name}' is not declared in the current spec.",
        )

    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    has_condition = community_name in km.satisfaction_conditions

    if not has_condition:
        return ObjectiveScoreResponse(
            community=community_name,
            objective_score=None,
            has_satisfaction_condition=False,
            breakdown=[],
            worlds_checked=len(km.worlds),
            horizon=_KRIPKE_HORIZON,
        )

    score = km.utility_for_objective(community_name, km.initial)
    _operator, member_ids = km.satisfaction_conditions[community_name]
    obl_dict = km.initial.obligation_dict()

    breakdown: List[ScoredObligation] = []
    for oid in member_ids:
        state = obl_dict.get(oid)
        if state is None:
            continue  # obligation not tracked in the initial world
        desc = km.obligation_descriptors.get(oid)
        weight = desc.priority_weight if desc else 0.5
        breakdown.append(ScoredObligation(
            obligation=oid,
            state=state.name,
            priority_weight=weight,
        ))

    return ObjectiveScoreResponse(
        community=community_name,
        objective_score=score,
        has_satisfaction_condition=True,
        breakdown=breakdown,
        worlds_checked=len(km.worlds),
        horizon=_KRIPKE_HORIZON,
    )
