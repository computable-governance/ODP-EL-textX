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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from el_engine import enroll, grant_token, initial_state, token_from_spec, TransitionRecord
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
      SpecialistClinician fills specialistRole (declared at SpecialistCommunity
        line 319; same gap — no fills_role declaration, inferred from holds +
        delegated_from + assignment_policy).
      SpecialistAIAgent does not fill a community role; it is delegated_from
        SpecialistClinician (AM-30b) and receives patientRecordAccessPermit
        directly, matching patientDataAuthorization.to_agent in the scenario.
      GPPracticeParty and SpecialistParty are parties (principals), not role-fillers.

    Token grants:
      GPClinician         — referralInitiationBurden, clinicalHandoverBurden
      SpecialistParty     — assessmentSchedulingBurden
      SpecialistClinician — referralResponseBurden
      SpecialistAIAgent   — patientRecordAccessPermit

    NOTE: the actor name string literals below are hardcoded, not resolved
    against `spec` — they must be kept in sync by hand with
    scenarios/gp_referral/gp_referral_scenario.el whenever its party/agent
    declarations change. This is the model/runtime drift CLAUDE.md §6.1
    warns against ("two parallel representations of the standard that have
    to be kept in sync manually"). AM-30b (2026-07-02) is the first time
    this drift actually occurred, when SpecialistClinicianAgent was renamed
    to SpecialistClinician in the scenario file without this builder being
    updated at the same time.
    """
    result = parse(_SCENARIO, validate=False)
    if not result.ok:
        raise RuntimeError(f"GP-referral parse failed: {result.errors}")

    spec = result.model
    state = initial_state()

    state = enroll(state, "GPPracticeParty")
    state = enroll(state, "GPClinician",         role_name="gpClinicianRole")
    state = enroll(state, "SpecialistParty")
    state = enroll(state, "SpecialistClinician",  role_name="specialistRole")
    state = enroll(state, "SpecialistAIAgent")

    for token_name, holder in [
        ("referralInitiationBurden",   "GPClinician"),
        ("clinicalHandoverBurden",     "GPClinician"),
        ("assessmentSchedulingBurden", "SpecialistParty"),
        ("referralResponseBurden",     "SpecialistClinician"),
        ("patientRecordAccessPermit",  "SpecialistAIAgent"),
    ]:
        state = grant_token(state, token_from_spec(spec, token_name, holder))

    return Runtime(state, spec)


_EREFERRAL_SCENARIO = _REPO_ROOT / "scenarios" / "ereferral" / "ereferral_model.el"


def _build_ereferral_runtime() -> Runtime:
    """
    Parse the eReferral scenario and initialise a Runtime with actors enrolled
    and tokens granted to their actual holders.

    Role assignments:
      GPClinician fills referringClinicianRole
      SpecialistClinician fills referredToSpecialistRole
      SpecialistAIAgent fills aiExaminationRole

    Token grants:
      GPClinician         — referralBurden (strict)
      SpecialistClinician — examinationBurden (eventual)
      SpecialistAIAgent   — aiExaminationBurden (eventual),
                            patientRecordAccessPermit
    """
    result = parse(_EREFERRAL_SCENARIO, validate=False)
    if not result.ok:
        raise RuntimeError(f"eReferral parse failed: {result.errors}")

    spec = result.model
    state = initial_state()

    state = enroll(state, "GPPractice")
    state = enroll(state, "GPClinician",         role_name="referringClinicianRole")
    state = enroll(state, "SpecialistPractice")
    state = enroll(state, "SpecialistClinician",  role_name="referredToSpecialistRole")
    state = enroll(state, "SpecialistAIAgent",    role_name="aiExaminationRole")

    for token_name, holder in [
        ("referralBurden",            "GPClinician"),
        ("acknowledgementBurden",     "SpecialistClinician"),
        ("examinationBurden",         "SpecialistClinician"),
        ("aiExaminationBurden",       "SpecialistAIAgent"),
        ("patientRecordAccessPermit", "SpecialistAIAgent"),
    ]:
        state = grant_token(state, token_from_spec(spec, token_name, holder))

    return Runtime(state, spec)


# Scenario registry — maps scenario name to its builder function
_SCENARIO_BUILDERS = {
    "gp_referral": _build_gp_referral_runtime,
    "ereferral":   _build_ereferral_runtime,
}

# Active scenario name and community name for objective queries
_active_scenario: str = "gp_referral"
_active_community: str = "ReferralFederation"

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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


class AlternativeAction(BaseModel):
    action_label: str
    q_value: float
    immediate_reward: float
    v_star_successor: float


class RecommendedActionResponse(BaseModel):
    community: str
    current_world: dict
    recommended_action: str
    q_value: float
    immediate_reward: float
    v_star_successor: float
    alternatives: List[AlternativeAction]
    gamma: float


class ExecuteActionRequest(BaseModel):
    action_name: str
    facts: dict = {}


class ExecuteActionResponse(BaseModel):
    tick: int
    actor_name: str
    action_name: str
    outcome: str
    discharged: List[str]
    effects: List[str]
    violations: List[str]
    reason: Optional[str]
    updated_world: dict
    new_recommended_action: str
    new_q_value: float
    new_objective_score: float
    objective_reachable: bool


class ScenarioSwitchResponse(BaseModel):
    active_scenario: str
    community: str
    message: str


class ScenarioListResponse(BaseModel):
    available_scenarios: List[str]
    active_scenario: str
    active_community: str


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


# ── Endpoint 4: GET /communities/{community_name}/recommended-action ──────────

@app.get(
    "/communities/{community_name}/recommended-action",
    response_model=RecommendedActionResponse,
    summary="Return the Bellman-optimal recommended first action for a community",
    description=(
        "Builds a Kripke model anchored to the current Layer 3 runtime state "
        "(hybrid mode: build_kripke_from_runtime) and runs Bellman value iteration "
        "(§C.4, Level 3). Returns the greedy-optimal first action from the current "
        "world, its Q-value, and all alternative first actions ranked by Q-value. "
        "recommended_action='' means no actions are available from the current world "
        "(terminal state). gamma is the discount factor applied per decision step. "
        "404 for an unknown community name."
    ),
)
def get_recommended_action(
    community_name: str,
    gamma: float = 0.9,
) -> RecommendedActionResponse:
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

    current_world = {
        "step": km.initial.step,
        "obligations": {
            oid: state.name
            for oid, state in sorted(km.initial.obligation_states)
        },
        "actors": {
            actor: status.name
            for actor, status in sorted(km.initial.actor_states)
        },
    }

    V = km.bellman_values(gamma=gamma)

    candidates = []
    for succ in km.successors(km.initial):
        label = km.labels.get((km.initial, succ), "→")
        imm = km.utility(succ)
        v_s = V.get(succ, 0.0)
        candidates.append((label, imm + gamma * v_s, imm, v_s))

    if not candidates:
        return RecommendedActionResponse(
            community=community_name,
            current_world=current_world,
            recommended_action="",
            q_value=0.0,
            immediate_reward=0.0,
            v_star_successor=0.0,
            alternatives=[],
            gamma=gamma,
        )

    candidates.sort(key=lambda x: x[1], reverse=True)
    recommended_label, q_val, imm_reward, v_star_succ = candidates[0]

    alternatives = [
        AlternativeAction(
            action_label=c[0], q_value=c[1],
            immediate_reward=c[2], v_star_successor=c[3],
        )
        for c in candidates[1:]
    ]

    return RecommendedActionResponse(
        community=community_name,
        current_world=current_world,
        recommended_action=recommended_label,
        q_value=q_val,
        immediate_reward=imm_reward,
        v_star_successor=v_star_succ,
        alternatives=alternatives,
        gamma=gamma,
    )


# ── Endpoint 5: POST /actors/{actor_name}/execute-action ──────────────────────

@app.post(
    "/actors/{actor_name}/execute-action",
    response_model=ExecuteActionResponse,
    summary="Execute an action for an actor and advance the runtime state",
    description=(
        "Calls Runtime.advance(action_name, actor_name, facts) to mutate "
        "the singleton runtime state, then re-queries the Kripke model to "
        "return the updated world state, new recommended action, new "
        "objective score, and whether the objective is still reachable. "
        "outcome is 'ok', 'blocked', or 'violation'."
    ),
)
def execute_action(
    actor_name: str,
    body: ExecuteActionRequest,
) -> ExecuteActionResponse:
    tr = _runtime.advance(body.action_name, actor_name, body.facts or {})

    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)

    updated_world = {
        "step": km.initial.step,
        "obligations": {
            oid: state.name
            for oid, state in sorted(km.initial.obligation_states)
        },
        "actors": {
            actor: status.name
            for actor, status in sorted(km.initial.actor_states)
        },
    }

    V = km.bellman_values(gamma=0.9)
    candidates = []
    for succ in km.successors(km.initial):
        label = km.labels.get((km.initial, succ), "→")
        imm = km.utility(succ)
        v_s = V.get(succ, 0.0)
        candidates.append((label, imm + 0.9 * v_s, imm, v_s))

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        new_rec = candidates[0][0]
        new_q = candidates[0][1]
    else:
        new_rec = ""
        new_q = 0.0

    score = km.utility_for_objective(_active_community, km.initial)

    prop = f"objective_satisfied:{_active_community}"
    reachable = km.EF(km.initial, prop)

    return ExecuteActionResponse(
        tick=tr.tick,
        actor_name=tr.actor_name,
        action_name=tr.action_name,
        outcome=tr.outcome,
        discharged=list(tr.discharged),
        effects=list(tr.effects),
        violations=list(tr.violations),
        reason=tr.reason,
        updated_world=updated_world,
        new_recommended_action=new_rec,
        new_q_value=round(new_q, 4),
        new_objective_score=round(score, 4),
        objective_reachable=reachable,
    )


# ── Endpoint 6: POST /reset ───────────────────────────────────────────────────

@app.post(
    "/reset",
    summary="Reset the runtime to the initial GP-referral scenario state",
    description="Re-parses the GP-referral scenario and re-enrols all "
                "actors, returning the runtime to its initial state.",
)
def reset_runtime() -> dict:
    global _runtime
    _runtime = _SCENARIO_BUILDERS[_active_scenario]()
    return {
        "status": "reset",
        "message": f"Runtime reset to initial '{_active_scenario}' state",
    }


# ── Endpoint 7: GET /scenarios ────────────────────────────────────────────────

@app.get(
    "/scenarios",
    response_model=ScenarioListResponse,
    summary="List available scenarios and the currently active one",
)
def list_scenarios() -> ScenarioListResponse:
    return ScenarioListResponse(
        available_scenarios=list(_SCENARIO_BUILDERS.keys()),
        active_scenario=_active_scenario,
        active_community=_active_community,
    )


# ── Endpoint 8: POST /scenario/{scenario_name} ────────────────────────────────

_COMMUNITY_FOR_SCENARIO = {
    "gp_referral": "ReferralFederation",
    "ereferral":   "ReferralEpisodeCommunity",
}


# ── Debug: GET /debug/tokens ──────────────────────────────────────────────────

@app.get("/debug/tokens", summary="Return all current runtime token states")
def debug_tokens():
    return [
        {
            "holder": t.holder,
            "kind": t.kind,
            "token_name": t.token_name,
            "state": t.state,
            "for_action": t.for_action,
        }
        for t in _runtime.current_state().tokens
    ]


@app.post(
    "/scenario/{scenario_name}",
    response_model=ScenarioSwitchResponse,
    summary="Switch the active scenario and reset the runtime",
    description=(
        "Rebuilds the singleton runtime from the named scenario's builder. "
        "Known scenarios: gp_referral, ereferral. "
        "Returns 404 for an unknown scenario name."
    ),
)
def switch_scenario(scenario_name: str) -> ScenarioSwitchResponse:
    global _runtime, _active_scenario, _active_community
    if scenario_name not in _SCENARIO_BUILDERS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scenario '{scenario_name}'. "
                   f"Available: {list(_SCENARIO_BUILDERS.keys())}",
        )
    _runtime = _SCENARIO_BUILDERS[scenario_name]()
    _active_scenario = scenario_name
    _active_community = _COMMUNITY_FOR_SCENARIO[scenario_name]
    return ScenarioSwitchResponse(
        active_scenario=_active_scenario,
        community=_active_community,
        message=f"Runtime switched to '{scenario_name}' scenario.",
    )
