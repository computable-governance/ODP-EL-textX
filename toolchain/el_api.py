"""
el_api.py
=========
Agent-facing coordination query API (Layer 3/4 bridge).

Endpoints implemented:
  GET /actors/{actor_name}/available-actions
  GET /communities/{community_name}/objective-reachable
  GET /communities/{community_name}/objective-score
  GET /obligations/{token_name}/status
  GET /tokens/{token_name}/governance
  POST /authorizations/{authorization_name}/revoke
  POST /fhir/consent-events
  GET /kripke/witness

Design reference: coordination_design_note_v3.md §9 (agent-facing query surface)
Standard reference: ISO/IEC 15414:2015 §6.4, §6.6, Annex C
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from el_engine import enroll, grant_token, initial_state, token_from_spec, TransitionRecord
from el_kripke import (
    build_kripke_from_runtime,
    build_kripke_model,
    extract_witness_path,
    find_normative_policies_for_token,
)
from el_parser import parse
from el_runtime import Runtime
from fhir_event_handler import handle_consent_event, PATIENT_DATA_AUTHORIZATION
from fhir_mapper import EncounterContext


# ── Runtime initialisation ────────────────────────────────────────────────────

_SCENARIO = _REPO_ROOT / "scenarios" / "gp_referral" / "gp_referral_scenario.el"
_KRIPKE_HORIZON = 10


def _serialize_path(path: Optional[list]) -> Optional[List[PathStep]]:
    if not path:
        return None
    return [
        PathStep(
            step=world.step,
            label=label,
            obligation_states={k: v.name for k, v in world.obligation_dict().items()},
            actor_states={k: v.name for k, v in world.actor_dict().items()},
        )
        for world, label in path
    ]


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
        SpecialistClinician (AM-30b) and receives
        patientRecordAccessPermitByAuthorization directly, matching
        patientDataAuthorization.to_agent in the scenario (AM-31b split the
        permit; SpecialistClinician separately receives
        patientRecordAccessPermitByRole below).
      GPPracticeParty and SpecialistParty are parties (principals), not role-fillers.

    Token grants:
      GPClinician         — referralInitiationBurden, clinicalHandoverBurden
      SpecialistParty     — assessmentSchedulingBurden
      SpecialistClinician — referralResponseBurden, patientRecordAccessPermitByRole
      SpecialistAIAgent   — patientRecordAccessPermitByAuthorization

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
        ("referralResponseBurden",              "SpecialistClinician"),
        ("patientRecordAccessPermitByRole",     "SpecialistClinician"),
        ("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent"),
    ]:
        state = grant_token(state, token_from_spec(spec, token_name, holder, state.tick))

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
        state = grant_token(state, token_from_spec(spec, token_name, holder, state.tick))

    return Runtime(state, spec)


_REFERRAL_SCENARIO = _REPO_ROOT / "scenarios" / "referral" / "referral_scenario.el"


def _build_referral_runtime(encounter_context: Optional[EncounterContext] = None) -> Runtime:
    """
    Parse the unified referral scenario (candidate reference scenario,
    scenarios/README.md) and initialise a Runtime with actors enrolled and
    tokens granted to their actual holders.

    Two actors fill TWO roles each, in different communities simultaneously
    (GPClinician: standing gpClinicianRole in GPPracticeCommunity + episode
    referringRole in ReferralEpisodeCommunity; SpecialistClinician: standing
    specialistRole in SpecialistPracticeCommunity + episode referredToRole).
    Patient fills THREE roles concurrently (patientRole in both standing
    communities, episodePatientRole in the episode) — confirmed safe:
    get_available_actions() below works purely off token.holder, never
    role_name, so multiple ActorState entries per actor_name do not
    interfere with any existing endpoint.

    Role assignments:
      GPClinician         fills gpClinicianRole (GPPracticeCommunity, standing)
                          and referringRole (ReferralEpisodeCommunity, episode)
      SpecialistClinician fills specialistRole (SpecialistPracticeCommunity,
                          standing) and referredToRole (ReferralEpisodeCommunity,
                          episode)
      SpecialistAIAgent   fills aiExaminationRole (ReferralEpisodeCommunity)
      Patient             fills patientRole in BOTH standing communities and
                          episodePatientRole (ReferralEpisodeCommunity)
      GPPractice is a party (principal), not a role-filler. SpecialistPractice
      fills practiceOversightRole (SpecialistPracticeCommunity, standing) —
      its own organisational escalation/notification role, distinct from
      specialistRole (SpecialistClinician's clinical membership). Added
      2026-08-20 so notify_gp_of_non_response has a role to attach to
      (§6.3/§7.8.1 — an Action only exists inside a RoleDecl; see
      docs/CONCEPTS_INDEX.md's role-attachment conformance-check finding).

    Token grants:
      GPClinician         — referralInitiationBurden, clinicalHandoverBurden
      SpecialistClinician — referralResponseBurden, assessmentSchedulingBurden,
                            patientRecordAccessPermitByRole
      SpecialistAIAgent   — patientRecordAccessPermitByAuthorization,
                            aiExaminationBurden

    NOTE: same drift risk as the other two builders (CLAUDE.md §6.1) — these
    actor/token name string literals must be kept in sync by hand with
    scenarios/referral/referral_scenario.el. Covered by
    tests/test_scenario_builders.py once registered below.

    NOTE: ReferralNetworkFederation (the standing federation) has no
    satisfaction condition declared — objective-reachable will correctly
    report has_satisfaction_condition=False for it, not a failure.
    ReferralEpisodeCommunity does have one (all_discharged(referralBurdenGroup)).

    encounter_context: optional [R26-R29] grounding from a FHIR Encounter
    (see fhir_mapper.extract_encounter_context). When provided,
    referring_practitioner/gp_practice below are taken from it instead of
    the "GPClinician"/"GPPractice" scenario defaults — grounding the GP
    side of the referral only; SpecialistClinician, SpecialistAIAgent,
    SpecialistPractice, and Patient are unaffected (Encounter scopes the
    referring/GP side per R26-R29, not the specialist side).
    """
    result = parse(_REFERRAL_SCENARIO, validate=False)
    if not result.ok:
        raise RuntimeError(f"Referral scenario parse failed: {result.errors}")

    spec = result.model
    state = initial_state()

    referring_practitioner = (
        encounter_context.referring_practitioner if encounter_context
        else "GPClinician"
    )
    gp_practice = (
        encounter_context.gp_practice if encounter_context
        else "GPPractice"
    )

    state = enroll(state, gp_practice)
    state = enroll(state, referring_practitioner, role_name="gpClinicianRole")
    state = enroll(state, referring_practitioner, role_name="referringRole")
    state = enroll(state, "SpecialistPractice",  role_name="practiceOversightRole")
    state = enroll(state, "SpecialistClinician", role_name="specialistRole")
    state = enroll(state, "SpecialistClinician", role_name="referredToRole")
    state = enroll(state, "SpecialistAIAgent",   role_name="aiExaminationRole")
    state = enroll(state, "Patient",             role_name="patientRole")
    state = enroll(state, "Patient",             role_name="episodePatientRole")

    for token_name, holder in [
        ("referralInitiationBurden",   referring_practitioner),
        ("clinicalHandoverBurden",     referring_practitioner),
        ("referralResponseBurden",     "SpecialistClinician"),
        ("assessmentSchedulingBurden", "SpecialistClinician"),
        ("patientRecordAccessPermitByRole",          "SpecialistClinician"),
        ("patientRecordAccessPermitByAuthorization", "SpecialistAIAgent"),
        ("aiExaminationBurden",        "SpecialistAIAgent"),
    ]:
        state = grant_token(state, token_from_spec(spec, token_name, holder, state.tick))

    return Runtime(state, spec)


# Scenario registry — maps scenario name to its builder function
_SCENARIO_BUILDERS = {
    "gp_referral": _build_gp_referral_runtime,
    "ereferral":   _build_ereferral_runtime,
    "referral":    _build_referral_runtime,
}

# Scenario registry — maps scenario name to its .el file path, for
# spec-only mode (build_kripke_model over the parsed model directly,
# no live Runtime). _SCENARIO/_EREFERRAL_SCENARIO/_REFERRAL_SCENARIO are
# the same path constants each builder above already parses from.
_SCENARIO_PATHS = {
    "gp_referral": _SCENARIO,
    "ereferral":   _EREFERRAL_SCENARIO,
    "referral":    _REFERRAL_SCENARIO,
}

# Active scenario name and community name for objective queries
_active_scenario: str = "referral"
_active_community: str = "ReferralEpisodeCommunity"

_runtime = _build_referral_runtime()

# Board-display side-store (AM-34 follow-up): fhir_provenance is stamped onto
# ConsentEventResponse per-call but never persisted on WorldState/TokenInstance
# (TokenInstance is a fixed-field frozen dataclass — see el_engine.py). Keyed
# by embargo token_name so GET /debug/tokens can surface which revocation, if
# any, was FHIR-triggered. Reset alongside _runtime in reset_runtime() /
# switch_scenario().
_fhir_provenance_by_token: Dict[str, str] = {}


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


class PathStep(BaseModel):
    step: int
    label: str
    obligation_states: Dict[str, str]
    actor_states: Dict[str, str]


class ObligationStatusResponse(BaseModel):
    token_name: str
    holder: str
    chain: List[str]
    obligation_text: str
    compelled: bool               # AF satisfied — architecturally guaranteed
    detectable: bool              # EF satisfied — possible on at least one path
    worlds_checked: int
    counterexample_path: Optional[List[PathStep]] = None  # present iff not compelled
    witness_path: Optional[List[PathStep]] = None          # present iff detectable


class NormativePolicyEnforcementInfo(BaseModel):
    mode: Optional[str] = None     # EnforcementMode: 'optimistic' | 'pessimistic' | None (unset)
    unpoliced: bool = False


class NormativePolicyInfo(BaseModel):
    name: str
    description: Optional[str] = None
    source: str                    # citation — mandatory on NormativePolicy
    url: Optional[str] = None      # AM-43 — optional link for the citation
    kind: str                      # legislation | regulation | standard | guideline | contractual
    enforcement: Optional[NormativePolicyEnforcementInfo] = None


class TokenGovernanceResponse(BaseModel):
    token_name: str
    governing_element: Optional[str] = None   # Community/Domain/Federation name, or None if unresolved
    normative_policies: List[NormativePolicyInfo]


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


class RevokeAuthorizationResponse(BaseModel):
    tick: int
    authority: str                 # the party that revoked (auth.authority.name)
    authorization_name: str
    outcome: str
    effects: List[str]             # e.g. ["superseded permit 'X'", "activated embargo 'Y'"]
    updated_world: dict
    new_objective_score: float
    objective_reachable: bool


class ReinstateAuthorizationResponse(BaseModel):
    tick: int
    authority: str                 # the party that reinstated (auth.authority.name)
    authorization_name: str
    outcome: str
    effects: List[str]             # e.g. ["activated permit 'X'", "lifted embargo 'Y'"] — empty if already active
    updated_world: dict
    new_objective_score: float
    objective_reachable: bool


class CheckViolationsResponse(BaseModel):
    tick: int
    outcome: str                   # 'violation' | 'ok'
    violations: List[str]          # Burden names transitioned to 'violated' this call
    effects: List[str]
    updated_world: dict
    new_objective_score: float
    objective_reachable: bool


class FireViolationResponsesResponse(BaseModel):
    tick: int
    fired: List[str]                # ViolationResponse names fired this call
    effects: List[str]
    updated_world: dict
    new_objective_score: float
    objective_reachable: bool


class AdvanceClockRequest(BaseModel):
    ticks: int


class AdvanceClockResponse(BaseModel):
    tick: int
    effects: List[str]              # single line, e.g. "clock advanced 8 tick(s): 0 → 8"
    updated_world: dict
    new_objective_score: float
    objective_reachable: bool


class ConsentEventResponse(BaseModel):
    fhir_consent_id: str
    fhir_status: str
    fhir_provenance: str
    action_taken: str              # "revoked" | "reinstated" | "already_active" | "no_op"
    message: str
    # populated only when action_taken in ("revoked", "reinstated", "already_active") (mirrors RevokeAuthorizationResponse)
    tick: Optional[int] = None
    authority: Optional[str] = None
    authorization_name: Optional[str] = None
    outcome: Optional[str] = None
    effects: Optional[List[str]] = None
    updated_world: Optional[dict] = None
    new_objective_score: Optional[float] = None
    objective_reachable: Optional[bool] = None


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

    # Dedupe by action name. The specific cause this was written for
    # (scenario-builder pre-seed + grammar `create` effect both granting the
    # same burden to the same holder) is now fixed at the source — see the
    # idempotency guard in el_engine.py's `create` handler and the
    # 2026-08-20 CONCEPTS_INDEX.md finding. Kept deliberately as
    # defense-in-depth: any other path that grants the same (token_name,
    # holder) pair twice — e.g. a duplicated tuple in a builder's own
    # token-grant list, or build_from_federation()'s Commitment/Delegation
    # auto-grant walking reaching the same delegate twice — would still go
    # through this endpoint's token loop, not the create-effect guard.
    # First occurrence wins.
    seen_actions: set[str] = set()
    deduped: List[AvailableAction] = []
    for a in actions:
        if a.action in seen_actions:
            continue
        seen_actions.add(a.action)
        deduped.append(a)

    return AvailableActionsResponse(actor=actor_name, available_actions=deduped)


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


# ── Endpoint: GET /obligations/{token_name}/status ────────────────────────────

@app.get(
    "/obligations/{token_name}/status",
    response_model=ObligationStatusResponse,
    summary="Check whether an obligation is compelled (AF) or merely detectable (EF)",
    description=(
        "Builds a Kripke model anchored to the current Layer 3 runtime state "
        "and runs both check_obligation (AF) and check_permission (EF) on the "
        "named burden token. 'compelled' means the obligation is guaranteed to "
        "discharge on every possible future path — architecturally enforced, "
        "violation unreachable. 'detectable' means it can discharge on at "
        "least one path, but is not guaranteed — the system will observe "
        "failure if it happens, but cannot by itself prevent it. Only applies "
        "to burden-kind tokens (obligations); 400 for permit/embargo tokens, "
        "404 for an unknown token name."
    ),
)
def get_obligation_status(token_name: str) -> ObligationStatusResponse:
    tokens = _runtime.current_state().tokens
    matching = [t for t in tokens if t.token_name == token_name]
    if not matching:
        raise HTTPException(
            status_code=404,
            detail=f"Token '{token_name}' is not present in the current runtime state.",
        )
    tok = matching[0]
    if tok.kind != "burden":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Token '{token_name}' is a {tok.kind}, not a burden — "
                "compelled/detectable status only applies to obligations."
            ),
        )

    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    af_verdict = km.check_obligation(token_name)
    ef_verdict = km.check_permission(token_name)

    return ObligationStatusResponse(
        token_name=token_name,
        holder=af_verdict.holder,
        chain=af_verdict.chain,
        obligation_text=af_verdict.obligation_text,
        compelled=af_verdict.satisfied,
        detectable=ef_verdict.satisfied,
        worlds_checked=af_verdict.worlds_checked,
        counterexample_path=_serialize_path(af_verdict.counterexample_path) if not af_verdict.satisfied else None,
        witness_path=_serialize_path(ef_verdict.witness_path) if ef_verdict.satisfied else None,
    )


# ── Endpoint: GET /tokens/{token_name}/governance ──────────────────────────────

@app.get(
    "/tokens/{token_name}/governance",
    response_model=TokenGovernanceResponse,
    summary="Return the NormativePolicy citations governing a token, if any",
    description=(
        "Resolves the Community/Domain/Federation that governs the named "
        "token, and returns that element's normative_policies (AM-28/AM-41) "
        "— citations of externally-grounded instruments: legislation, "
        "regulation, standard, guideline, contractual. Two resolution paths "
        "are tried in order: (1) the role-action favoured_by traversal, for "
        "burden tokens; (2) a fallback for a token that is the "
        "grants_permit or on_revocation_embargo target of some "
        "Authorization, resolved via that Authorization's domain_scope. "
        "Most tokens will still not resolve to a governing element or any "
        "citation — a burden with no favoured_by reference, or a "
        "permit/embargo referenced by no Authorization (e.g. only via a "
        "role action's requires_permit/inhibited_by_embargo — see "
        "el_kripke.find_normative_policies_for_token's KNOWN LIMITATION) — "
        "both yield an empty normative_policies list. That is a normal "
        "outcome, not an error — 404 is reserved for a token name that "
        "does not exist in the current runtime state at all."
    ),
)
def get_token_governance(token_name: str) -> TokenGovernanceResponse:
    tokens = _runtime.current_state().tokens
    if not any(t.token_name == token_name for t in tokens):
        raise HTTPException(
            status_code=404,
            detail=f"Token '{token_name}' is not present in the current runtime state.",
        )

    element, policies = find_normative_policies_for_token(_runtime._spec, token_name)

    return TokenGovernanceResponse(
        token_name=token_name,
        governing_element=getattr(element, "name", None),
        normative_policies=[
            NormativePolicyInfo(
                name=p.name,
                description=getattr(p, "description", None),
                source=p.source,
                url=getattr(p, "url", None),
                kind=p.kind,
                enforcement=(
                    NormativePolicyEnforcementInfo(
                        mode=getattr(p.enforcement, "mode", None),
                        unpoliced=getattr(p.enforcement, "unpoliced", False),
                    )
                    if getattr(p, "enforcement", None) is not None
                    else None
                ),
            )
            for p in policies
        ],
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


# ── Endpoint: POST /authorizations/{authorization_name}/revoke ────────────────

@app.post(
    "/authorizations/{authorization_name}/revoke",
    response_model=RevokeAuthorizationResponse,
    summary="Revoke a revocable authorization and advance the runtime state",
    description=(
        "Calls Runtime.revoke_authorization(authorization_name) to withdraw a "
        "revocable authorization: supersedes the permit it granted, and "
        "activates its on_revocation embargo, blocking further use of the "
        "permitted action by its former holder. Then re-queries the Kripke "
        "model for the updated world state, objective score, and reachability. "
        "This is the runtime enactment of patient consent withdrawal in the "
        "GP-referral scenario (PatientParty revoking patientDataAuthorization). "
        "404 if the authorization is not declared; 400 if it has no "
        "on_revocation embargo (i.e. is not meaningfully revocable)."
    ),
)
def revoke_authorization_endpoint(authorization_name: str) -> RevokeAuthorizationResponse:
    # 404 check: authorization must be declared in the current spec
    known_auths = {
        el.name
        for el in _runtime._spec.elements
        if type(el).__name__ == "Authorization"
    }
    if authorization_name not in known_auths:
        raise HTTPException(
            status_code=404,
            detail=f"Authorization '{authorization_name}' is not declared in the current spec.",
        )

    try:
        tr = _runtime.revoke_authorization(authorization_name)
    except KeyError as e:
        # revoke_authorization raises KeyError if there's no on_revocation embargo
        raise HTTPException(
            status_code=400,
            detail=f"Authorization '{authorization_name}' is not revocable: {e}",
        )

    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    updated_world = {
        "step": km.initial.step,
        "obligations": {
            oid: state.name for oid, state in sorted(km.initial.obligation_states)
        },
        "actors": {
            actor: status.name for actor, status in sorted(km.initial.actor_states)
        },
    }
    score = km.utility_for_objective(_active_community, km.initial)
    prop = f"objective_satisfied:{_active_community}"
    reachable = km.EF(km.initial, prop)

    return RevokeAuthorizationResponse(
        tick=tr.tick,
        authority=tr.actor_name,   # revoke_authorization sets actor_name = auth.authority.name
        authorization_name=authorization_name,
        outcome=tr.outcome,
        effects=list(tr.effects),
        updated_world=updated_world,
        new_objective_score=round(score, 4),
        objective_reachable=reachable,
    )


@app.post(
    "/authorizations/{authorization_name}/reinstate",
    response_model=ReinstateAuthorizationResponse,
    summary="Reinstate a revocable authorization and advance the runtime state",
    description=(
        "Calls Runtime.reinstate_authorization(authorization_name) to (re-)establish "
        "a revocable authorization: (re-)activates the permit it grants — reusing the "
        "existing token if previously revoked, or granting fresh if none exists yet — "
        "and lifts its on_revocation embargo if one is currently active. Mirrors "
        "POST /authorizations/{authorization_name}/revoke in reverse, including the "
        "Kripke re-verification step (updated world state, objective score, "
        "reachability). Idempotent: calling this when the permit is already active "
        "returns outcome='ok' with an empty effects list rather than raising or "
        "no-op'ing silently. This is the direct-call counterpart to "
        "POST /fhir/consent-events with status='active' (R30 Option B) — same "
        "Runtime.reinstate_authorization() engine path, no FHIR envelope. 404 if the "
        "authorization is not declared; 400 if it has no on_revocation embargo (i.e. "
        "is not meaningfully revocable/reinstatable)."
    ),
)
def reinstate_authorization_endpoint(authorization_name: str) -> ReinstateAuthorizationResponse:
    # 404 check: authorization must be declared in the current spec
    known_auths = {
        el.name
        for el in _runtime._spec.elements
        if type(el).__name__ == "Authorization"
    }
    if authorization_name not in known_auths:
        raise HTTPException(
            status_code=404,
            detail=f"Authorization '{authorization_name}' is not declared in the current spec.",
        )

    try:
        tr = _runtime.reinstate_authorization(authorization_name)
    except KeyError as e:
        # reinstate_authorization raises KeyError if there's no on_revocation embargo
        raise HTTPException(
            status_code=400,
            detail=f"Authorization '{authorization_name}' is not reinstatable: {e}",
        )

    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    updated_world = {
        "step": km.initial.step,
        "obligations": {
            oid: state.name for oid, state in sorted(km.initial.obligation_states)
        },
        "actors": {
            actor: status.name for actor, status in sorted(km.initial.actor_states)
        },
    }
    score = km.utility_for_objective(_active_community, km.initial)
    prop = f"objective_satisfied:{_active_community}"
    reachable = km.EF(km.initial, prop)

    return ReinstateAuthorizationResponse(
        tick=tr.tick,
        authority=tr.actor_name,   # reinstate_authorization sets actor_name = auth.authority.name
        authorization_name=authorization_name,
        outcome=tr.outcome,
        effects=list(tr.effects),
        updated_world=updated_world,
        new_objective_score=round(score, 4),
        objective_reachable=reachable,
    )


# ── Endpoint: POST /check-violations ───────────────────────────────────────────

@app.post(
    "/check-violations",
    response_model=CheckViolationsResponse,
    summary="Sweep active, discharge_mode: eventual Burdens for elapsed deadlines",
    description=(
        "Calls Runtime.check_live_violations() to detect and transition to "
        "'violated' any active, discharge_mode: eventual Burden whose elapsed "
        "time (current tick minus granted_at_tick) has reached or passed its "
        "deadline_steps. deadline_steps is resolved via the same "
        "Commitment-derived two-tier lookup build_kripke_from_runtime() uses "
        "(Commitment-derived ObligationDescriptor first, bare DeonticToken "
        "deadline-string fallback second). discharge_mode: strict Burdens are "
        "never checked or transitioned here, regardless of elapsed time — "
        "strict enforcement is a separate, still-open live-runtime gap (see "
        "docs/CONCEPTS_INDEX.md). This is an explicit trigger, not automatic: "
        "nothing else in the runtime calls it, so callers decide when a "
        "deadline sweep happens. Then re-queries the Kripke model for the "
        "updated world state, objective score, and reachability, mirroring "
        "POST /authorizations/{authorization_name}/revoke."
    ),
)
def check_violations_endpoint() -> CheckViolationsResponse:
    tr = _runtime.check_live_violations()

    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    updated_world = {
        "step": km.initial.step,
        "obligations": {
            oid: state.name for oid, state in sorted(km.initial.obligation_states)
        },
        "actors": {
            actor: status.name for actor, status in sorted(km.initial.actor_states)
        },
    }
    score = km.utility_for_objective(_active_community, km.initial)
    prop = f"objective_satisfied:{_active_community}"
    reachable = km.EF(km.initial, prop)

    return CheckViolationsResponse(
        tick=tr.tick,
        outcome=tr.outcome,
        violations=list(tr.violations),
        effects=list(tr.effects),
        updated_world=updated_world,
        new_objective_score=round(score, 4),
        objective_reachable=reachable,
    )


# ── Endpoint: POST /fire-violation-responses ───────────────────────────────────

@app.post(
    "/fire-violation-responses",
    response_model=FireViolationResponsesResponse,
    summary="Fire declared ViolationResponses for currently-violated Burdens",
    description=(
        "Calls Runtime.fire_violation_responses() to fire each declared "
        "ViolationResponse whose on_violation_of Burden is currently VIOLATED "
        "(set by a prior POST /check-violations call — this endpoint never "
        "detects violations itself, only responds to ones already detected; "
        "kept as a separate, deliberate beat rather than folded into "
        "check-violations, so detection stays a pure, poll-safe operation). "
        "For each firing: grants creates_burden to obligates via the same "
        "general-purpose token_from_spec() path every other fresh-grant call "
        "uses, and logs an informational escalate_to entry (no token/event "
        "fired for it — emits/§8.4 outbound notification stays deferred, see "
        "docs/CONCEPTS_INDEX.md). Idempotent: fires exactly once per "
        "violation, never again — even after its created burden is "
        "discharged. Tick only advances when at least one response actually "
        "fires. Then re-queries the Kripke model for the updated world "
        "state, objective score, and reachability, mirroring the other "
        "mutating endpoints."
    ),
)
def fire_violation_responses_endpoint() -> FireViolationResponsesResponse:
    tr = _runtime.fire_violation_responses()

    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    updated_world = {
        "step": km.initial.step,
        "obligations": {
            oid: state.name for oid, state in sorted(km.initial.obligation_states)
        },
        "actors": {
            actor: status.name for actor, status in sorted(km.initial.actor_states)
        },
    }
    score = km.utility_for_objective(_active_community, km.initial)
    prop = f"objective_satisfied:{_active_community}"
    reachable = km.EF(km.initial, prop)

    return FireViolationResponsesResponse(
        tick=tr.tick,
        fired=list(tr.fired_responses),
        effects=list(tr.effects),
        updated_world=updated_world,
        new_objective_score=round(score, 4),
        objective_reachable=reachable,
    )


# ── Endpoint: POST /advance-clock ──────────────────────────────────────────────

@app.post(
    "/advance-clock",
    response_model=AdvanceClockResponse,
    summary="Let simulated time pass by N ticks, with no domain action",
    description=(
        "Calls Runtime.advance_clock(ticks) to advance WorldState.tick by "
        "exactly `ticks` — no token transitions, no discharge, no grants, no "
        "event triggering. This is the 'time passes' primitive that "
        "deadline-based violation detection needs: drive the clock forward "
        "with this, then call POST /check-violations to sweep for anything "
        "now overdue. Deliberately has no action semantics of its own — the "
        "honest alternative to burning ticks via unrelated no-op actions "
        "(e.g. N repeated /authorizations/{name}/reinstate calls), which "
        "would pollute the ledger with events that never really happened. "
        "400 if ticks < 1. Then re-queries the Kripke model for the updated "
        "world state, objective score, and reachability, mirroring the "
        "other mutating endpoints."
    ),
)
def advance_clock_endpoint(body: AdvanceClockRequest) -> AdvanceClockResponse:
    try:
        tr = _runtime.advance_clock(body.ticks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    updated_world = {
        "step": km.initial.step,
        "obligations": {
            oid: state.name for oid, state in sorted(km.initial.obligation_states)
        },
        "actors": {
            actor: status.name for actor, status in sorted(km.initial.actor_states)
        },
    }
    score = km.utility_for_objective(_active_community, km.initial)
    prop = f"objective_satisfied:{_active_community}"
    reachable = km.EF(km.initial, prop)

    return AdvanceClockResponse(
        tick=tr.tick,
        effects=list(tr.effects),
        updated_world=updated_world,
        new_objective_score=round(score, 4),
        objective_reachable=reachable,
    )


# ── Endpoint: POST /fhir/consent-events ────────────────────────────────────

@app.post(
    "/fhir/consent-events",
    response_model=ConsentEventResponse,
    summary="Ingest a FHIR Consent resource event (R30/R31)",
    description=(
        "Accepts a FHIR R4 Consent resource. status='inactive' (R31) revokes "
        "patientDataAuthorization via Runtime.revoke_authorization() — the same "
        "engine path as POST /authorizations/{name}/revoke. status='active' "
        "(R30 Option B) (re-)establishes it via Runtime.reinstate_authorization() "
        "— (re-)activates the permit, lifting its on_revocation embargo if one "
        "is currently active. Both stamp the Consent.id as fhir_provenance on "
        "the result; see fhir_event_handler.py's module docstring (AM-34). 400 "
        "if the Consent resource is missing id/status, or the target "
        "authorization has no on_revocation embargo. 404 if the target "
        "authorization is not declared in the active spec at all."
    ),
)
def consent_event(consent: dict) -> ConsentEventResponse:
    # 404 check: mirrors revoke_authorization_endpoint's known_auths check —
    # the FHIR bridge is wired to a single fixed authorization name; if it
    # isn't declared in the active spec at all, that's "not found," not
    # "declared but not revocable" (which stays a 400 below).
    known_auths = {
        el.name
        for el in _runtime._spec.elements
        if type(el).__name__ == "Authorization"
    }
    if PATIENT_DATA_AUTHORIZATION not in known_auths:
        raise HTTPException(
            status_code=404,
            detail=f"Authorization '{PATIENT_DATA_AUTHORIZATION}' is not declared in the current spec.",
        )

    try:
        result = handle_consent_event(consent, _runtime)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        # handle_consent_event raises KeyError if the authorization has no
        # on_revocation embargo (declared but not meaningfully revocable).
        raise HTTPException(
            status_code=400,
            detail=f"Consent event could not be applied: {e}",
        )

    if result.action_taken not in ("revoked", "reinstated", "already_active"):
        return ConsentEventResponse(
            fhir_consent_id=result.fhir_consent_id,
            fhir_status=result.fhir_status,
            fhir_provenance=result.fhir_provenance,
            action_taken=result.action_taken,
            message=result.message,
        )

    # Stash fhir_provenance against the token GET /debug/tokens should
    # attribute this event to — the embargo for a revoke (the token that
    # newly became active), the permit for a reinstate or already_active
    # (the token this event targets, whether or not it actually changed
    # state). The plain POST /authorizations/{name}/revoke path never
    # writes here, so a non-FHIR revoke/reinstate shows no provenance
    # (by design).
    auth_el = next(
        (el for el in _runtime._spec.elements
         if type(el).__name__ == "Authorization" and el.name == result.authorization_name),
        None,
    )
    if result.action_taken == "revoked":
        target_token_name = getattr(auth_el, "on_revocation_embargo", "") if auth_el else ""
    else:
        target_token_name = auth_el.permit.name if auth_el else ""
    if target_token_name:
        _fhir_provenance_by_token[target_token_name] = result.fhir_provenance

    tr = result.transition
    km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    updated_world = {
        "step": km.initial.step,
        "obligations": {
            oid: state.name for oid, state in sorted(km.initial.obligation_states)
        },
        "actors": {
            actor: status.name for actor, status in sorted(km.initial.actor_states)
        },
    }
    score = km.utility_for_objective(_active_community, km.initial)
    prop = f"objective_satisfied:{_active_community}"
    reachable = km.EF(km.initial, prop)

    return ConsentEventResponse(
        fhir_consent_id=result.fhir_consent_id,
        fhir_status=result.fhir_status,
        fhir_provenance=result.fhir_provenance,
        action_taken=result.action_taken,
        message=result.message,
        tick=tr.tick,
        authority=tr.actor_name,
        authorization_name=result.authorization_name,
        outcome=tr.outcome,
        effects=list(tr.effects),
        updated_world=updated_world,
        new_objective_score=round(score, 4),
        objective_reachable=reachable,
    )


# ── Endpoint 6: POST /reset ───────────────────────────────────────────────────

@app.post(
    "/reset",
    summary="Reset the runtime to the initial state of the active scenario",
    description="Re-parses the currently active scenario (see _SCENARIO_BUILDERS"
                "[_active_scenario]) and re-enrols all actors, returning the "
                "runtime to its initial state.",
)
def reset_runtime() -> dict:
    global _runtime
    _runtime = _SCENARIO_BUILDERS[_active_scenario]()
    _fhir_provenance_by_token.clear()
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
    "referral":    "ReferralEpisodeCommunity",
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
            "fhir_provenance": _fhir_provenance_by_token.get(t.token_name),
        }
        for t in _runtime.current_state().tokens
    ]


@app.post(
    "/scenario/{scenario_name}",
    response_model=ScenarioSwitchResponse,
    summary="Switch the active scenario and reset the runtime",
    description=(
        "Rebuilds the singleton runtime from the named scenario's builder. "
        "Known scenarios: gp_referral, ereferral, referral. "
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
    _fhir_provenance_by_token.clear()
    return ScenarioSwitchResponse(
        active_scenario=_active_scenario,
        community=_active_community,
        message=f"Runtime switched to '{scenario_name}' scenario.",
    )


# ── Endpoint 9: GET /kripke/witness ─────────────────────────────────────────

@app.get(
    "/kripke/witness",
    summary="Extract the shortest witness path to a proposition, for the active scenario",
    description=(
        "Builds a KripkeModel for the currently active scenario (see GET "
        "/scenarios / POST /scenario/{name} to change it) -- hybrid (default) "
        "via build_kripke_from_runtime() over the shared _runtime singleton, "
        "same as every other endpoint in this API, or spec-only via "
        "build_kripke_model() over the active scenario's parsed .el file. "
        "Returns extract_witness_path()'s shortest BFS path from the initial "
        "world to the first world satisfying `proposition` (e.g. "
        "'discharged:aiExaminationBurden', 'occurred:conductAIExamination'). "
        "witness_path is [] (200, not an error) if the proposition is never "
        "satisfied on any reachable world within the horizon. 400 for an "
        "unknown mode. scenario_name in the response reports whichever "
        "scenario was actually active for this request, since (unlike every "
        "other parameter here) it isn't something the caller supplied."
    ),
)
def get_witness_path(proposition: str, mode: str = "hybrid") -> Dict:
    if mode not in ("hybrid", "spec"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown mode '{mode}'. Must be 'hybrid' or 'spec'.",
        )

    if mode == "hybrid":
        km = build_kripke_from_runtime(_runtime, horizon=_KRIPKE_HORIZON)
    else:
        result = parse(_SCENARIO_PATHS[_active_scenario], validate=False)
        if not result.ok:
            raise RuntimeError(f"{_active_scenario} parse failed: {result.errors}")
        km = build_kripke_model(result.model, horizon=_KRIPKE_HORIZON)

    return {
        "scenario_name": _active_scenario,
        "witness_path": extract_witness_path(km, target_proposition=proposition),
    }
