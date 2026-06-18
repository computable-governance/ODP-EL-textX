"""
el_kripke.py
============
Layer 4 — Kripke Semantics for ODP-EL / ISO 15414:2015

Implements Annex C of ISO/IEC 15414:2015 as a Python module.

Annex C specifies:
  C.1 — Why labelled transition systems are insufficient for obligations:
         a transition system can record what happened but cannot express
         "must eventually be discharged." Kripke models can.
  C.2 — Kripke frames: worlds W, reachability relation R ⊆ W×W,
         satisfaction relation ⊨ between worlds and behavioural formulae.
  C.3 — Utility function u: W → ℝ assigns a preference value to each world,
         weighted by modeller-specified obligation priority (AM-15).
  C.4 — Utility-weighted path prioritisation: expected_future_utility() over
         all reachable worlds from a given state; recommend_action() ranks
         available actions by expected future utility; walk_recommended_path()
         follows the best recommendation step by step — the BDI planner.

The modal operators implemented are (CTL-style over finite horizon H):
  AF φ  (inevitably φ)  — φ holds on ALL maximal paths eventually
                          → used for OBLIGATION verification
  EF φ  (possibly φ)    — φ holds on SOME path eventually
                          → used for PERMISSION verification
  AG φ  (always φ)      — φ holds in ALL reachable worlds
                          → used for INVARIANT checking

This module answers the Layer 4 question:
  "Across all possible futures, will obligation O eventually be discharged?"

Relationship to other layers
-----------------------------
  Layer 1 — computable-governance grammar (Igor Dejanovic)
  Layer 2 — el_grammar.tx + el_validator.py + el_reasoner.py
  Layer 3 — Sepanosian runtime: WorldState, transitions, ledger
  Layer 4 — THIS MODULE

The reachability relation R is built from the DSL-EL delegation structure
alone — obligations, deadlines, and actor assignments generate the full
branching tree of possible futures. This is the primary and complete mode
of Layer 4 verification: it asks "across all conceivable futures, does the
obligation inevitably discharge?" before anything has happened at runtime.

An optional HYBRID mode (not yet implemented) would allow a Sepanosian
Layer 3 transition ledger to anchor the initial world to the current runtime
state and prune branches that are no longer reachable. This would support
post-hoc verification: "given what has already happened, is the obligation
still guaranteed to discharge from here?" The ledger supplements Layer 4;
it is not required for it.

Validation scenario (from position paper §6.4):
  Does GPPracticeParty → SpecialistAgent → AIDiagnosticAgent guarantee
  eventual discharge of seekConsentObligation?

Usage
-----
    from el_parser import parse
    from el_kripke import build_kripke_model, check_obligation, check_permission

    result = parse("my_spec.el")
    km     = build_kripke_model(result.model, horizon=10)

    report = km.check_obligation("seekConsentObligation")
    print(report.render())

    report = km.check_permission("seekConsentObligation")
    print(report.render())

    # Utility-ranked worlds from the initial world
    for w, u in km.ranked_reachable(km.initial):
        print(f"  step={w.step}  utility={u:.2f}  {dict(w.obligation_states)}")

Standalone test (consent scenario)
-----------------------------------
    python el_kripke.py
"""

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Set, Tuple


# ══════════════════════════════════════════════════════════════════════════════
# §C.1  —  Why we need Kripke models
# (Documented here as a comment; the code below embodies the alternative)
#
# A labelled transition system records whether a specific trace of actions
# conforms to a specification. It cannot express:
#
#   "For ALL possible sequences of future events, obligation O will
#    eventually be discharged."
#
# This is the AF□ operator in CTL, which requires quantification over the
# entire branching tree of futures — exactly what a Kripke model provides.
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# §C.2  —  Worlds and the reachability relation
# ══════════════════════════════════════════════════════════════════════════════

class ObligationState(Enum):
    """
    The deontic lifecycle of a single obligation in one world.

    Corresponds to the deontic token states in ISO 15414 Annex A
    (Figure A.6: pending → active → discharged / violated / expired).
    """
    PENDING    = auto()   # obligation is active and awaiting discharge
    DISCHARGED = auto()   # obligation has been fulfilled — the goal state
    VIOLATED   = auto()   # deadline elapsed without discharge
    EXPIRED    = auto()   # context no longer applies (actor left community etc.)
    SUPERSEDED = auto()   # a sibling in the same TokenGroup discharged first;
                          # this obligation's purpose is fulfilled — not a failure.
                          # Excluded from utility() numerator and denominator (P3).
    WAITING    = auto()   # triggered_by event has not yet fired; not eligible for
                          # T1 discharge or T2 violation. Transitions to PENDING
                          # when its trigger event fires (P6 cascade).


class ActorStatus(Enum):
    """
    Whether a given actor (party or agent) is currently active in its role.
    Actors can become INACTIVE through revocation or community departure.
    """
    ACTIVE   = auto()
    INACTIVE = auto()


# Immutable alias types used in World
_ObligStates = FrozenSet[Tuple[str, ObligationState]]   # (obligation_id, state)
_ActorStates = FrozenSet[Tuple[str, ActorStatus]]       # (actor_name, status)


@dataclass(frozen=True)
class World:
    """
    A single possible world in the Kripke model.

    §C.2(a): "a set of worlds W, expressed in terms of arbitrarily many
    propositional variables."

    We represent a world as:
      - obligation_states : the deontic state of every tracked obligation
      - actor_states      : the active/inactive status of every tracked actor
      - step              : discrete time step (0 = initial)

    Frozen so that worlds are hashable and can appear in sets/dict keys.
    The tuple representation makes equality and hashing unambiguous.
    """
    obligation_states: _ObligStates   # frozenset of (obligation_id, ObligationState)
    actor_states: _ActorStates        # frozenset of (actor_name, ActorStatus)
    step: int

    # ── Convenience accessors ─────────────────────────────────────────────────

    def get_obligation(self, obligation_id: str) -> ObligationState:
        """Return the state of a named obligation in this world."""
        for oid, state in self.obligation_states:
            if oid == obligation_id:
                return state
        raise KeyError(f"Obligation '{obligation_id}' not tracked in this model")

    def get_actor(self, actor_name: str) -> ActorStatus:
        """Return the status of a named actor in this world."""
        for name, status in self.actor_states:
            if name == actor_name:
                return status
        raise KeyError(f"Actor '{actor_name}' not tracked in this model")

    def obligation_dict(self) -> Dict[str, ObligationState]:
        return dict(self.obligation_states)

    def actor_dict(self) -> Dict[str, ActorStatus]:
        return dict(self.actor_states)

    def all_discharged(self) -> bool:
        """True iff every obligation in this world is DISCHARGED or SUPERSEDED.

        SUPERSEDED obligations had their purpose fulfilled by a group sibling,
        so they count as resolved for the all_discharged test.
        """
        return all(
            s in (ObligationState.DISCHARGED, ObligationState.SUPERSEDED)
            for _, s in self.obligation_states
        )

    def any_violated(self) -> bool:
        """True iff any obligation in this world is VIOLATED."""
        return any(s == ObligationState.VIOLATED for _, s in self.obligation_states)

    def __repr__(self) -> str:
        obl = ", ".join(f"{k}={v.name}" for k, v in sorted(self.obligation_states))
        return f"World(step={self.step}, [{obl}])"


def _make_world(
    obligation_states: Dict[str, ObligationState],
    actor_states: Dict[str, ActorStatus],
    step: int,
) -> World:
    """Convenience constructor from plain dicts."""
    return World(
        obligation_states=frozenset(obligation_states.items()),
        actor_states=frozenset(actor_states.items()),
        step=step,
    )


# ── Obligation descriptor ─────────────────────────────────────────────────────

@dataclass
class ObligationDescriptor:
    """
    Metadata about one obligation extracted from the DSL-EL spec.
    Used by the reachability builder to generate transitions.
    """
    obligation_id: str        # burden name from the DSL (e.g. "paymentProcessingObligation")
    obligation_text: str      # natural language text (e.g. "Process all customer payments…")
    deadline_steps: int       # finite horizon; parsed from deadline string or defaulted
    holder: str               # actor currently responsible (leaf of delegation chain)
    chain: List[str]          # full chain [root_party, …, current_holder]
    revocable: bool
    sub_delegation_allowed: bool
    discharge_mode: str = "eventual"
    # "eventual" (default) — holder may delay; TICK available; AF may not hold
    # "strict"             — holder must act at first opportunity; TICK removed; AF holds
    priority_weight: float = 0.5
    # Numeric weight derived from PriorityLevel (AM-15):
    #   critical → 1.00   high → 0.75   normal → 0.50   low → 0.25
    # Used by the weighted utility function (§C.3) to reflect modeller-specified
    # importance ordering across obligations.
    triggered_by: Optional[str] = None
    # Event name (from DeonticToken.triggered_by) whose firing moves this
    # obligation from WAITING → PENDING. None means obligation starts PENDING.
    fires_event: Optional[str] = None
    # Event name (from DeonticToken.discharged_by) emitted when this obligation
    # is discharged. Bidirectional convention: discharging this obligation fires
    # this event, which may cascade to trigger other WAITING obligations (P6).


# ══════════════════════════════════════════════════════════════════════════════
# §C.2  —  The Kripke model
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class KripkeModel:
    """
    A finite Kripke model M = (W, R, V, w₀) where:
      W  — set of worlds (all reachable from w₀ within horizon H)
      R  — reachability relation  (dict: world → set of successor worlds)
      V  — valuation function     (world → set of true propositions)
      w₀ — initial world

    §C.2(b): "a reachability relation R on the members of W, which is a binary
    relation indicating whether one world can be reached from (i.e., evolve
    into) another."

    §C.2(c): "a satisfaction relation between the members of W and a formula
    expressing the intended behaviour."

    We also carry:
      obligation_descriptors — metadata indexed by obligation_id
      horizon                — maximum step depth used during construction
      labels                 — transition labels (world, world) → action description
    """
    initial: World
    worlds: Set[World]
    edges: Dict[World, Set[World]]                  # R
    propositions: Dict[World, Set[str]]             # V (valuation)
    labels: Dict[Tuple[World, World], str]          # edge labels (for explanation)
    obligation_descriptors: Dict[str, ObligationDescriptor]
    horizon: int
    group_index: Dict[str, List[str]] = field(default_factory=dict)
    # group_index: {group_name: [obligation_id, ...]} built from TokenGroup
    # declarations.  Used by T1 (P6) to find siblings for SUPERSEDED
    # transitions, and by _build_propositions (P5) for objective_satisfied
    # propositions.  Empty dict is safe for all existing callers.
    satisfaction_conditions: Dict[str, Tuple[str, List[str]]] = field(default_factory=dict)
    # satisfaction_conditions: {community_name: (operator, [member_ids])}
    # built from Community/Federation Objective.satisfaction clauses (AM-27).
    # operator is 'all_discharged' or 'any_discharged'.
    # Used by _build_propositions to emit objective_satisfied:<community>.

    # ── Satisfaction relation ──────────────────────────────────────────────────

    def satisfies(self, world: World, proposition: str) -> bool:
        """
        §C.2(c): world ⊨ proposition iff proposition ∈ V(world).

        Named propositions we use:
          "discharged:<obligation_id>"  — obligation is DISCHARGED in this world
          "pending:<obligation_id>"     — obligation is PENDING
          "violated:<obligation_id>"    — obligation is VIOLATED
          "active:<actor_name>"         — actor is ACTIVE
          "all_discharged"              — all obligations are DISCHARGED
          "any_violated"                — at least one obligation is VIOLATED
        """
        return proposition in self.propositions.get(world, set())

    # ── Reachability ──────────────────────────────────────────────────────────

    def successors(self, world: World) -> Set[World]:
        """Direct successors of world under R."""
        return self.edges.get(world, set())

    def reachable(self, world: World) -> Set[World]:
        """
        All worlds reachable from world under R* (reflexive-transitive closure).
        BFS over the finite graph.
        """
        visited: Set[World] = set()
        queue: deque[World] = deque([world])
        while queue:
            w = queue.popleft()
            if w in visited:
                continue
            visited.add(w)
            for succ in self.successors(w):
                if succ not in visited:
                    queue.append(succ)
        return visited

    # ── Modal operators ────────────────────────────────────────────────────────

    def AF(self, world: World, proposition: str) -> bool:
        """
        AF φ  — inevitably φ.

        §C.2: "behaviour obliged to occur: for all worlds reachable from the
        given world, the behaviour will be observed eventually."

        Implementation: DFS/BFS over the reachability graph. AF φ holds at w
        iff every maximal path from w eventually visits a world satisfying φ.

        We handle cycles (lasso paths) by detecting worlds already on the
        current DFS stack — if a cycle exists that never reaches φ, AF φ
        is FALSE (there is a path that never discharges the obligation).
        """
        return self._AF(world, proposition, visited=set(), on_stack=set())

    def _AF(
        self,
        w: World,
        prop: str,
        visited: Set[World],
        on_stack: Set[World],
    ) -> bool:
        # Base case: w satisfies φ
        if self.satisfies(w, prop):
            return True

        # Cycle detected on DFS stack and φ not satisfied → obligation can be
        # deferred forever on this path → AF φ is FALSE
        if w in on_stack:
            return False

        # No successors (maximal path ends here without satisfying φ) → FALSE
        succs = self.successors(w)
        if not succs:
            return False

        on_stack.add(w)

        # AF φ holds at w iff it holds at ALL successors
        result = all(
            self._AF(s, prop, visited, on_stack)
            for s in succs
        )

        on_stack.discard(w)
        return result

    def EF(self, world: World, proposition: str) -> bool:
        """
        EF φ  — possibly φ.

        §C.2: "behaviours observed in some reachable worlds are said to be
        permitted."

        Implementation: BFS — does any reachable world satisfy φ?
        """
        for w in self.reachable(world):
            if self.satisfies(w, proposition):
                return True
        return False

    def AG(self, world: World, proposition: str) -> bool:
        """
        AG φ  — always φ.

        φ must hold in every world reachable from world (including world itself).
        Used for invariant checking.
        """
        return all(
            self.satisfies(w, proposition)
            for w in self.reachable(world)
        )

    # ── High-level obligation / permission checks ─────────────────────────────

    def check_obligation(self, obligation_id: str) -> "ObligationVerdict":
        """
        §C.2 OBLIGATION:
          An obligation O is satisfied iff for ALL paths from the initial world,
          obligation_id is eventually DISCHARGED.

        Returns an ObligationVerdict with full explanation.
        """
        prop = f"discharged:{obligation_id}"
        satisfied = self.AF(self.initial, prop)
        counterexample = None if satisfied else self._find_AF_counterexample(
            self.initial, prop
        )

        desc = self.obligation_descriptors.get(obligation_id)
        return ObligationVerdict(
            obligation_id=obligation_id,
            obligation_text=desc.obligation_text if desc else obligation_id,
            modal_operator="AF",
            satisfied=satisfied,
            worlds_checked=len(self.worlds),
            counterexample_path=counterexample,
            holder=desc.holder if desc else "unknown",
            chain=desc.chain if desc else [],
        )

    def check_permission(self, obligation_id: str) -> "ObligationVerdict":
        """
        §C.2 PERMISSION:
          A permission P is satisfied iff SOME path from the initial world
          eventually discharges it.

        Equivalently: permitted ↔ not obliged-not-to-occur.
        """
        prop = f"discharged:{obligation_id}"
        satisfied = self.EF(self.initial, prop)
        witness = None
        if satisfied:
            witness = self._find_EF_witness(self.initial, prop)

        desc = self.obligation_descriptors.get(obligation_id)
        return ObligationVerdict(
            obligation_id=obligation_id,
            obligation_text=desc.obligation_text if desc else obligation_id,
            modal_operator="EF",
            satisfied=satisfied,
            worlds_checked=len(self.worlds),
            counterexample_path=None,
            witness_path=witness,
            holder=desc.holder if desc else "unknown",
            chain=desc.chain if desc else [],
        )

    # ── §C.3 / §C.4  —  Utility ───────────────────────────────────────────────

    def utility(self, world: World) -> float:
        """
        §C.3: utility function u: W → ℝ  (weighted by obligation priority, AM-15)

        Assigns a numeric preference value to a world based on the deontic
        states of its obligations, weighted by the modeller-specified priority
        of each obligation.

        The weighting is the key addition over a naive binary satisfaction
        relation. §C.3 motivates this by noting that when an objective cannot
        be fully satisfied, the utility function must guide the system toward
        the best partial approximation — which requires knowing which
        obligations matter most.

        Per-obligation outcome scores:
          DISCHARGED  → +1.0   (goal achieved)
          PENDING     → +0.3   (progress still possible)
          EXPIRED     →  0.0   (neutral — context removed)
          VIOLATED    → -1.0   (obligation breached — worst outcome)

        Priority weights (from AM-15 PriorityLevel, default normal=0.5):
          critical=1.0, high=0.75, normal=0.5, low=0.25

        Weighted utility = Σ(score_i × weight_i) / Σ(weight_i)

        Result is normalised to [-1, +1]. A world where all obligations are
        discharged scores +1.0 regardless of priority; priority only matters
        when obligations have mixed outcomes.

        Example — two obligations, one critical, one low:
          consent=DISCHARGED (w=1.0), reporting=VIOLATED (w=0.25):
            utility = (1.0×1.0 + -1.0×0.25) / (1.0+0.25) = 0.75/1.25 = +0.60
          consent=VIOLATED (w=1.0), reporting=DISCHARGED (w=0.25):
            utility = (-1.0×1.0 + 1.0×0.25) / (1.0+0.25) = -0.75/1.25 = -0.60
        """
        outcome_scores = {
            ObligationState.DISCHARGED: +1.0,
            ObligationState.PENDING:    +0.3,
            ObligationState.EXPIRED:     0.0,
            ObligationState.VIOLATED:   -1.0,
        }
        obl_dict = dict(world.obligation_states)
        # Exclude SUPERSEDED and WAITING obligations from both numerator and
        # denominator. SUPERSEDED: purpose fulfilled by a group sibling.
        # WAITING: trigger not yet fired; obligation not yet in play.
        _excluded = (ObligationState.SUPERSEDED, ObligationState.WAITING)
        active_items = [
            (oid, desc)
            for oid, desc in self.obligation_descriptors.items()
            if obl_dict.get(oid) not in _excluded
        ]
        total_weight = sum(desc.priority_weight for _, desc in active_items)
        if total_weight == 0:
            return 0.0
        weighted_sum = sum(
            outcome_scores.get(obl_dict.get(oid, ObligationState.PENDING), 0.0)
            * desc.priority_weight
            for oid, desc in active_items
        )
        return weighted_sum / total_weight

    def utility_for_objective(self, community_name: str, world: World) -> float:
        """
        Level 2 — Kripke + scoped utility (coordination_design_note_v3.md §12.2).

        Scores a world using only the members of `community_name`'s satisfaction
        TokenGroup, rather than all tracked obligations globally. Differentiates
        within the space of "objective satisfied" worlds — a world where the
        high-priority burden is DISCHARGED and the low-priority one is PENDING
        scores differently than the reverse.

        SUPERSEDED members are excluded entirely (consistent with all_discharged
        treating SUPERSEDED as a pass — see §5.1 of the design note). WAITING
        members score 0.0 (neutral — trigger not yet fired, distinct from
        PENDING's +0.3).

        Returns 0.0 if community_name has no entry in satisfaction_conditions,
        or if the referenced group has no members (defensive — should not happen
        for a validly-built model). Returns +1.0 if every trackable member is
        SUPERSEDED (objective achieved via group sibling discharge — the
        maximally-good outcome for an any_discharged group).
        """
        outcome_scores = {
            ObligationState.DISCHARGED: +1.0,
            ObligationState.PENDING:    +0.3,
            ObligationState.WAITING:     0.0,
            ObligationState.EXPIRED:     0.0,
            ObligationState.VIOLATED:   -1.0,
            # SUPERSEDED intentionally absent — handled by exclusion below
        }

        cond = self.satisfaction_conditions.get(community_name)
        if cond is None:
            return 0.0
        _operator, member_ids = cond  # (operator, [obligation_id, ...])
        if not member_ids:
            return 0.0

        obl_dict = world.obligation_dict()
        total_weight = 0.0
        weighted_sum = 0.0
        any_superseded = False

        for oid in member_ids:
            state = obl_dict.get(oid)
            if state is None:
                continue  # obligation not tracked in this world — skip
            if state == ObligationState.SUPERSEDED:
                any_superseded = True
                continue  # excluded from scoring and denominator
            desc = self.obligation_descriptors.get(oid)
            weight = desc.priority_weight if desc else 0.5
            weighted_sum += outcome_scores.get(state, 0.0) * weight
            total_weight += weight

        if total_weight == 0.0:
            # Every trackable member was SUPERSEDED (objective achieved via
            # group sibling discharge) — return +1.0. If no member was
            # trackable at all (data gap), return 0.0.
            return 1.0 if any_superseded else 0.0

        return weighted_sum / total_weight

    def ranked_reachable(
        self,
        world: World,
        descending: bool = True,
    ) -> List[Tuple[World, float]]:
        """
        §C.4: rank all worlds reachable from world by utility, highest first.

        Returns list of (World, utility_score) pairs, sorted by utility.
        This supports the 'use utility to prioritise possible behaviours'
        requirement from §C.4.
        """
        pairs = [(w, self.utility(w)) for w in self.reachable(world)]
        pairs.sort(key=lambda x: x[1], reverse=descending)
        return pairs

    # ── §C.4  —  Path utility and action recommendation ───────────────────────

    def expected_future_utility(self, world: World) -> float:
        """
        §C.4: Expected utility of the future accessible from world.

        Computed as the mean utility over ALL worlds reachable from world
        (including world itself via reflexive closure). This captures the
        long-run quality of being in world w — not just the immediate snapshot,
        but the average quality of all futures w makes accessible.

        §C.4 motivates this by noting that "judging a course of action on the
        basis of the desirability of its outcome" (a single terminal world) is
        insufficient. The expected future utility averages over the entire
        reachable subtree, which reflects the real decision-theoretic value of
        choosing an action that leads to world w.

        For terminal worlds (no successors), returns utility(world) — the
        immediate outcome is the only outcome.
        """
        reachable = self.reachable(world)
        if not reachable:
            return self.utility(world)
        return sum(self.utility(w) for w in reachable) / len(reachable)

    def recommend_action(self, world: World) -> List["ActionRecommendation"]:
        """
        §C.4: Recommend which available action to take from world.

        For each outgoing transition (w → w' via action a), computes:
          - immediate_utility      : utility(w')
          - expected_future_utility: mean utility over all worlds reachable from w'

        Actions are ranked by expected_future_utility (descending).
        Rank 1 is the recommended action — the one that opens up the
        highest-utility future.

        This is the BDI planner connection:
          Beliefs  = current world w  (what is known about the state)
          Desires  = utility function  (what outcomes are valued, with priorities)
          Intention = rank-1 action    (what to do next)

        Returns an empty list if world has no outgoing transitions (terminal).
        """
        recommendations = []
        for successor in self.successors(world):
            label = self.labels.get((world, successor), "→")
            recommendations.append(ActionRecommendation(
                rank=0,  # set after sorting
                action_label=label,
                successor_world=successor,
                immediate_utility=self.utility(successor),
                expected_future_utility=self.expected_future_utility(successor),
            ))

        # Primary sort: expected future utility (descending)
        # Secondary sort: immediate utility (descending) — tiebreaker
        recommendations.sort(
            key=lambda r: (r.expected_future_utility, r.immediate_utility),
            reverse=True,
        )
        for i, r in enumerate(recommendations):
            r.rank = i + 1

        return recommendations

    def walk_recommended_path(
        self,
        world: Optional[World] = None,
        max_steps: int = 20,
    ) -> List[Tuple[World, str, "ActionRecommendation"]]:
        """
        §C.4: Follow the greedy best-action path from world.

        At each step, calls recommend_action() and follows the rank-1
        recommendation. Stops when:
          - a terminal world is reached (no successors), or
          - the recommended path cycles back to a visited world, or
          - max_steps is reached.

        Returns a list of (world, action_label, recommendation) triples
        describing the recommended sequence of actions.

        This is the complete §C.4 output: a step-by-step plan for an agent
        that wants to maximise expected future utility, given the current
        governance structure and obligation priorities.
        """
        if world is None:
            world = self.initial

        path: List[Tuple[World, str, ActionRecommendation]] = []
        visited: Set[World] = {world}
        current = world

        for _ in range(max_steps):
            recommendations = self.recommend_action(current)
            if not recommendations:
                break  # terminal world

            best = recommendations[0]
            path.append((current, best.action_label, best))

            next_world = best.successor_world
            if next_world in visited:
                break  # cycle detected — stop
            visited.add(next_world)
            current = next_world

        return path

    # ── §C.4 Level 3 — Bellman value iteration ────────────────────────────────

    def bellman_values(self, gamma: float = 0.9) -> Dict[World, float]:
        """
        §C.4 Level 3: compute V*(w) for every world via backward induction.

        The world-graph is a DAG (deontic states are monotone — obligations
        only advance forward: PENDING→DISCHARGED/VIOLATED/etc — so no cycles
        exist). However, same-step action-discharge transitions (step N→N)
        co-exist with tick transitions (step N→N+1), so step-order processing
        alone is insufficient. Kahn's topological sort gives the correct
        reverse-processing order for exact backward induction.

        γ is applied uniformly to all edges, including same-step transitions.
        The rationale: γ discounts per decision point, not per calendar time
        unit. Every edge — whether a same-step action discharge or a tick —
        represents one decision. A two-rate model (γ_action=1.0, γ_tick<1)
        would require annotating edges by type, which the current model does
        not support, and is deferred pending a concrete scenario that motivates
        it (design note §13.1f).

        Reward per transition:
          r(w → w') = utility(w')

        Applied per-transition (not only at terminal worlds) so intermediate
        bad states incur real cost — avoiding the perverse incentive of
        endpoint-only rewards (design note §12.2).

        Value equations:
          V*(terminal w)     = utility(w)
          V*(non-terminal w) = max over w' in successors(w) of
                                 [utility(w') + γ · V*(w')]

        Parameters
        ----------
        gamma : discount factor in (0, 1]. Default 0.9.

        Returns
        -------
        Dict[World, float] — V* for every world in self.worlds.
        """
        # Kahn's algorithm: BFS-based topological sort.
        in_degree: Dict[World, int] = {w: 0 for w in self.worlds}
        for w in self.worlds:
            for succ in self.successors(w):
                in_degree[succ] += 1

        queue: deque = deque(w for w in self.worlds if in_degree[w] == 0)
        topo_order: List[World] = []
        while queue:
            w = queue.popleft()
            topo_order.append(w)
            for succ in self.successors(w):
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        # Backward induction in reverse topological order.
        V: Dict[World, float] = {}
        for w in reversed(topo_order):
            succs = self.successors(w)
            if not succs:
                V[w] = self.utility(w)
            else:
                V[w] = max(
                    self.utility(w_prime) + gamma * V[w_prime]
                    for w_prime in succs
                )
        return V

    def optimal_path(
        self,
        world: Optional[World] = None,
        gamma: float = 0.9,
        max_steps: int = 20,
    ) -> List["BellmanStep"]:
        """
        §C.4 Level 3: follow the Bellman-optimal path from world.

        Computes V* via bellman_values(), then greedily follows
        argmax_a Q(w, a) at each step:
          Q(w, a) = utility(w') + γ · V*(w')  where w' = successor via a

        Stops when a terminal world is reached, a cycle is detected,
        or max_steps is exhausted. Returns one BellmanStep per step
        taken (not including the starting world — mirrors
        walk_recommended_path convention).
        """
        if world is None:
            world = self.initial

        V = self.bellman_values(gamma=gamma)

        path: List[BellmanStep] = []
        visited: Set[World] = {world}
        current = world

        for _ in range(max_steps):
            succs = self.successors(current)
            if not succs:
                break
            best = max(
                succs,
                key=lambda wp: self.utility(wp) + gamma * V.get(wp, 0.0),
            )
            imm = self.utility(best)
            v_b = V.get(best, 0.0)
            path.append(BellmanStep(
                action_label=self.labels.get((current, best), "→"),
                successor_world=best,
                immediate_reward=imm,
                v_star=v_b,
                q_value=imm + gamma * v_b,
            ))
            if best in visited:
                break
            visited.add(best)
            current = best

        return path

    def render_optimal_path(
        self,
        world: Optional[World] = None,
        gamma: float = 0.9,
    ) -> str:
        """§C.4 Level 3: human-readable Bellman-optimal path report."""
        if world is None:
            world = self.initial

        V = self.bellman_values(gamma=gamma)
        path = self.optimal_path(world=world, gamma=gamma)

        lines = [
            "─" * 60,
            f"§C.4 Level 3 — Bellman-Optimal Path  (γ={gamma})",
            "─" * 60,
            f"  Starting world : {world}",
            f"  V*(start)      : {V.get(world, 0.0):+.4f}",
            f"  utility(start) : {self.utility(world):+.4f}",
            "",
        ]
        if not path:
            lines.append("  (Terminal world — no actions available)")
            return "\n".join(lines)

        for i, step in enumerate(path, 1):
            lines += [
                f"  Step {i}:",
                f"    Action : {step.action_label}",
                f"    World  : {step.successor_world}",
                f"    r      : {step.immediate_reward:+.4f}",
                f"    V*(w') : {step.v_star:+.4f}",
                f"    Q      : {step.q_value:+.4f}",
                "",
            ]

        final = path[-1].successor_world
        lines += [
            f"  Final world   : {final}",
            f"  Final utility : {self.utility(final):+.4f}",
            f"  Final V*      : {V.get(final, 0.0):+.4f}",
        ]
        if not self.successors(final):
            lines.append("  (Terminal — no further actions)")
        return "\n".join(lines)

    def render_recommended_path(self, world: Optional[World] = None) -> str:
        """
        §C.4: Render the recommended action path as a human-readable report.

        Shows each step: the current world, the recommended action, its
        expected future utility, and why it was preferred over alternatives.
        """
        if world is None:
            world = self.initial

        path = self.walk_recommended_path(world)

        lines = [
            "─" * 60,
            "§C.4 — Recommended Action Path (BDI Planner)",
            "─" * 60,
            f"  Starting world : {world}",
            f"  Initial utility: {self.utility(world):+.3f}",
            f"  Initial EFU    : {self.expected_future_utility(world):+.3f}",
            "",
        ]

        if not path:
            lines.append("  (Terminal world — no actions available)")
            return "\n".join(lines)

        for step_num, (w, label, rec) in enumerate(path, 1):
            all_recs = self.recommend_action(w)
            lines.append(f"  Step {step_num}:")
            lines.append(f"    World  : {w}")
            lines.append(f"    Action : ★ {label}")
            lines.append(f"    EFU    : {rec.expected_future_utility:+.3f}")

            # Show alternatives if there were any
            alternatives = [r for r in all_recs if r.rank > 1]
            if alternatives:
                lines.append(f"    Alternatives considered ({len(alternatives)}):")
                for alt in alternatives[:3]:  # show up to 3
                    lines.append(
                        f"      [{alt.rank}] {alt.action_label}"
                        f"  (EFU={alt.expected_future_utility:+.3f})"
                    )
            lines.append("")

        # Final world
        final_world = path[-1][2].successor_world
        lines.append(f"  Final world    : {final_world}")
        lines.append(f"  Final utility  : {self.utility(final_world):+.3f}")
        final_recs = self.recommend_action(final_world)
        if not final_recs:
            lines.append("  (Terminal — no further actions)")
        else:
            lines.append(
                f"  (Further actions available — "
                f"best EFU: {final_recs[0].expected_future_utility:+.3f})"
            )

        return "\n".join(lines)

    # ── Explanation helpers ───────────────────────────────────────────────────

    def _find_AF_counterexample(
        self,
        start: World,
        prop: str,
    ) -> Optional[List[Tuple[World, str]]]:
        """
        Find a path from start that NEVER satisfies prop (AF counterexample).
        Returns list of (world, label) pairs tracing the path, or None.
        Uses DFS, following edges that do not lead to satisfaction.
        """
        path: List[Tuple[World, str]] = []
        on_stack: Set[World] = set()

        def dfs(w: World) -> bool:
            if self.satisfies(w, prop):
                return False   # this branch satisfies φ — not a counterexample
            if w in on_stack:
                path.append((w, "↺ cycle — obligation never discharged"))
                return True    # lasso: we found an infinite path avoiding φ
            succs = self.successors(w)
            if not succs:
                path.append((w, "✗ dead-end — obligation not discharged"))
                return True    # maximal path ends without satisfying φ
            on_stack.add(w)
            for s in succs:
                label = self.labels.get((w, s), "→")
                if not self._AF(s, prop, set(), set()):
                    # s is on a bad path — follow it
                    path.append((w, label))
                    if dfs(s):
                        on_stack.discard(w)
                        return True
            on_stack.discard(w)
            return False

        dfs(start)
        return path if path else None

    def _find_EF_witness(
        self,
        start: World,
        prop: str,
    ) -> Optional[List[Tuple[World, str]]]:
        """
        BFS to find the shortest path from start to a world satisfying prop.
        Returns list of (world, label) pairs.
        """
        parent: Dict[World, Tuple[World, str]] = {}
        queue: deque[World] = deque([start])
        visited: Set[World] = {start}

        while queue:
            w = queue.popleft()
            if self.satisfies(w, prop):
                # Reconstruct path
                path: List[Tuple[World, str]] = []
                cur = w
                while cur in parent:
                    prev, label = parent[cur]
                    path.append((prev, label))
                    cur = prev
                path.reverse()
                path.append((w, "✓ discharged"))
                return path
            for s in self.successors(w):
                if s not in visited:
                    visited.add(s)
                    parent[s] = (w, self.labels.get((w, s), "→"))
                    queue.append(s)
        return None

    # ── Summary render ────────────────────────────────────────────────────────

    def render_summary(self) -> str:
        lines = [
            "═" * 60,
            "Kripke Model Summary",
            "═" * 60,
            f"  Worlds         : {len(self.worlds)}",
            f"  Edges (R)      : {sum(len(v) for v in self.edges.values())}",
            f"  Horizon (steps): {self.horizon}",
            f"  Obligations    : {len(self.obligation_descriptors)}",
            "",
            "  Obligations tracked:",
        ]
        for oid, desc in sorted(self.obligation_descriptors.items()):
            chain_str = " → ".join(desc.chain) if desc.chain else desc.holder
            priority_label = {1.0: "critical", 0.75: "high",
                              0.5: "normal", 0.25: "low"}.get(
                desc.priority_weight, f"{desc.priority_weight:.2f}")
            lines.append(
                f"    [{oid}]  priority={priority_label}"
                f"  mode={desc.discharge_mode}"
                f"  deadline={desc.deadline_steps} steps"
                f"  chain: {chain_str}"
            )
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# §C.2  —  Reachability builder
# ══════════════════════════════════════════════════════════════════════════════

# Helpers mirroring el_reasoner._collect / _obj_name so this module is
# self-contained and does not create a circular import.

def _cls(obj: Any) -> str:
    return type(obj).__name__


def _collect(model: Any, cls_name: str) -> List[Any]:
    return [e for e in model.elements if _cls(e) == cls_name]


def _obj_name(ref: Any) -> Optional[str]:
    if ref is None:
        return None
    return getattr(ref, "name", None)


def _priority_weight(priority_str: Optional[str]) -> float:
    """
    §C.3: Convert a PriorityLevel string (AM-15) to a numeric weight.

    The weights establish an importance ordering across obligations so
    that the utility function reflects modeller intent — a world where
    a 'critical' obligation is DISCHARGED is worth more than one where
    only a 'low' obligation is DISCHARGED.

      critical → 1.00   (must not be violated under any circumstances)
      high     → 0.75   (strongly preferred to discharge)
      normal   → 0.50   (default — equal weight)
      low      → 0.25   (desirable but not critical)
    """
    return {
        "critical": 1.00,
        "high":     0.75,
        "normal":   0.50,
        "low":      0.25,
    }.get(priority_str or "normal", 0.50)


def _parse_deadline_steps(deadline_str: Optional[str], default: int = 5) -> int:
    """
    Convert a natural-language deadline string to a finite step count.

    The mapping is necessarily approximate because the DSL deadline is
    expressed in domain time (seconds, days, etc.) while our step model
    is abstract. The goal is to preserve the relative ordering of deadlines.

    Heuristics:
      "… second …"        → 2 steps   (very tight)
      "… minute …"        → 3 steps
      "… hour …"          → 5 steps
      "… day …"           → 8 steps
      "… week …"          → 12 steps
      "… month …"         → 20 steps
      anything else       → default
    """
    if not deadline_str:
        return default
    s = deadline_str.lower()
    if "second" in s:
        return 2
    if "minute" in s:
        return 3
    if "hour"   in s:
        return 5
    if "day"    in s:
        return 8
    if "week"   in s:
        return 12
    if "month"  in s:
        return 20
    return default


def _build_obligation_descriptors(model: Any) -> Dict[str, ObligationDescriptor]:
    """
    Extract ObligationDescriptor for each burden that appears in at least
    one CommitmentDecl or DelegationDecl.

    Algorithm:
    1. Index all BurdenDecl elements by name.
    2. For each CommitmentDecl, find its creates_burden reference.
    3. Walk the delegation graph forward to find the current holder.
    4. Record the full accountability chain.
    """
    # Index burdens by name.
    # The grammar uses DeonticToken for all token kinds (burden/permit/embargo);
    # we filter by kind == "burden". (AM-18 renamed DeonticTokenDecl → DeonticToken)
    burdens: Dict[str, Any] = {
        t.name: t
        for t in _collect(model, "DeonticToken")
        if getattr(t, "kind", None) == "burden"
    }

    # Build delegation graph: from_name → list of (to_name, obligation_text)
    # (duplicates el_reasoner.delegation_graph but avoids import)
    del_graph: Dict[str, List[Tuple[str, str, bool, bool]]] = {}
    for d in _collect(model, "Delegation"):  # AM-18: DelegationDecl → Delegation
        from_name = _obj_name(d.delegator)
        to_name   = _obj_name(d.delegate)
        if from_name and to_name:
            del_graph.setdefault(from_name, []).append((
                to_name,
                d.obligation,
                getattr(d, "sub_delegation_allowed", False),
                getattr(d, "revocable", False),
            ))

    def walk_chain(start: str, obl_text: str) -> List[str]:
        """DFS to leaf; returns [start, …, leaf]."""
        chain = [start]
        visited: Set[str] = {start}
        current = start
        while True:
            outgoing = [
                (to, oblt, sda, rev)
                for to, oblt, sda, rev in del_graph.get(current, [])
                if obl_text.lower() in oblt.lower()
            ]
            if not outgoing or outgoing[0][0] in visited:
                break
            to, oblt, sda, rev = outgoing[0]
            chain.append(to)
            visited.add(to)
            current = to
        return chain

    descriptors: Dict[str, ObligationDescriptor] = {}

    for c in _collect(model, "Commitment"):  # AM-18: CommitmentDecl → Commitment
        burden_ref = getattr(c, "burden", None)
        burden_name = _obj_name(burden_ref)
        actor_name  = _obj_name(getattr(c, "actor", None))
        if not burden_name or not actor_name:
            continue
        burden = burdens.get(burden_name)
        if burden is None:
            continue

        obl_text     = getattr(c, "obligation", burden_name)
        deadline_str = getattr(burden, "deadline", None)
        chain        = walk_chain(actor_name, obl_text)
        holder       = chain[-1]

        # Use sub_delegation_allowed / revocable from the LAST delegation link
        # that terminates at holder, if any
        sda, rev = False, False
        for d in _collect(model, "Delegation"):  # AM-18: DelegationDecl → Delegation
            if _obj_name(d.delegate) == holder:
                sda = getattr(d, "sub_delegation_allowed", False)
                rev = getattr(d, "revocable", False)

        # P6: extract event wiring from the burden token
        triggered_by = _obj_name(getattr(burden, "triggered_by", None))
        fires_event  = _obj_name(getattr(burden, "discharged_by", None))
        # fires_event convention: DeonticToken.discharged_by names the event that
        # fires when this obligation is discharged (bidirectional: the same event
        # that the holder's action emits). Used by T1 cascade to activate WAITING
        # obligations whose triggered_by matches this event name.

        descriptors[burden_name] = ObligationDescriptor(
            obligation_id=burden_name,
            obligation_text=obl_text,
            deadline_steps=_parse_deadline_steps(deadline_str),
            holder=holder,
            chain=chain,
            revocable=rev,
            sub_delegation_allowed=sda,
            discharge_mode=getattr(burden, "discharge_mode", "") or "eventual",
            priority_weight=_priority_weight(getattr(burden, "priority", None)),
            triggered_by=triggered_by,
            fires_event=fires_event,
        )

    return descriptors


def _build_group_index(model: Any) -> Dict[str, List[str]]:
    """
    Build a group membership index from all TokenGroup declarations in the spec.

    Returns {group_name: [obligation_id, ...]} where obligation_ids are the
    names of the DeonticToken members of each group.  Only groups whose
    token refs resolved (non-None name) are included.

    Used by:
      - T1 extension (P6): find sibling obligations to mark SUPERSEDED when
        one group member discharges.
      - _build_propositions (P5): derive objective_satisfied:<community>
        proposition from any_discharged / all_discharged over a named group.
    """
    index: Dict[str, List[str]] = {}
    for el in model.elements:
        if type(el).__name__ != "TokenGroup":
            continue
        member_ids = [
            _obj_name(tok)
            for tok in getattr(el, "tokens", [])
            if _obj_name(tok)
        ]
        if member_ids:
            index[el.name] = member_ids
    return index


def _build_any_discharged_groups(model: Any) -> Set[str]:
    """
    Return the set of TokenGroup names whose satisfaction operator is
    'any_discharged' in at least one Community/Federation objective.

    P6b (SUPERSEDED sibling suppression) is semantically correct only for
    these groups: when one member discharges, the group's purpose is fulfilled
    and siblings are no longer needed.  For 'all_discharged' groups every
    member must independently discharge; applying SUPERSEDED there would
    incorrectly prevent siblings from being evaluated.
    """
    result: Set[str] = set()
    for el in model.elements:
        if type(el).__name__ not in ("Community", "Federation", "Domain"):
            continue
        obj = getattr(el, "objective", None)
        if obj is None:
            continue
        sat = getattr(obj, "satisfaction", None)
        if sat is None:
            continue
        if getattr(sat, "operator", None) == "any_discharged":
            group = getattr(sat, "group", None)
            if group is not None:
                gname = _obj_name(group)
                if gname:
                    result.add(gname)
    return result


def _build_satisfaction_conditions(
    model: Any,
) -> Dict[str, Tuple[str, List[str]]]:
    """
    Extract objective satisfaction conditions from Community/Federation/Domain
    declarations that carry a SatisfactionCondition on their objective (AM-27).

    Returns {community_name: (operator, [member_ids])} where:
      operator   — 'all_discharged' or 'any_discharged'
      member_ids — names of the DeonticToken members of the referenced TokenGroup

    Used by _build_propositions() to emit objective_satisfied:<community_name>
    when the condition holds in a given world.
    """
    conditions: Dict[str, Tuple[str, List[str]]] = {}
    for el in model.elements:
        if type(el).__name__ not in ("Community", "Federation", "Domain"):
            continue
        obj = getattr(el, "objective", None)
        if obj is None:
            continue
        sat = getattr(obj, "satisfaction", None)
        if sat is None:
            continue
        group = getattr(sat, "group", None)
        if group is None:
            continue
        member_ids = [
            _obj_name(tok)
            for tok in getattr(group, "tokens", [])
            if _obj_name(tok)
        ]
        if member_ids:
            conditions[el.name] = (sat.operator, member_ids)
    return conditions


def _build_propositions(
    world: World,
    satisfaction_conditions: Optional[Dict[str, Tuple[str, List[str]]]] = None,
) -> Set[str]:
    """
    Compute the set of true propositions V(world) — the valuation function.

    Named propositions:
      "discharged:<id>"             ↔  obligation_states[id] == DISCHARGED
      "pending:<id>"                ↔  obligation_states[id] == PENDING
      "violated:<id>"               ↔  obligation_states[id] == VIOLATED
      "expired:<id>"                ↔  obligation_states[id] == EXPIRED
      "superseded:<id>"             ↔  obligation_states[id] == SUPERSEDED
      "active:<actor>"              ↔  actor_states[actor]   == ACTIVE
      "inactive:<actor>"            ↔  actor_states[actor]   == INACTIVE
      "all_discharged"              ↔  every obligation is DISCHARGED/SUPERSEDED
      "any_violated"                ↔  at least one obligation is VIOLATED
      "any_pending"                 ↔  at least one obligation is PENDING
      "objective_satisfied:<name>"  ↔  community <name> satisfaction condition holds (AM-27)
    """
    props: Set[str] = set()

    state_tags = {
        ObligationState.DISCHARGED: "discharged",
        ObligationState.PENDING:    "pending",
        ObligationState.VIOLATED:   "violated",
        ObligationState.EXPIRED:    "expired",
        ObligationState.SUPERSEDED: "superseded",
        ObligationState.WAITING:    "waiting",
    }
    obl_dict: Dict[str, ObligationState] = {}
    for oid, state in world.obligation_states:
        props.add(f"{state_tags[state]}:{oid}")
        obl_dict[oid] = state

    actor_tags = {
        ActorStatus.ACTIVE:   "active",
        ActorStatus.INACTIVE: "inactive",
    }
    for aname, status in world.actor_states:
        props.add(f"{actor_tags[status]}:{aname}")

    if world.all_discharged():
        props.add("all_discharged")
    if world.any_violated():
        props.add("any_violated")
    if any(s == ObligationState.PENDING for _, s in world.obligation_states):
        props.add("any_pending")
    if any(s == ObligationState.WAITING for _, s in world.obligation_states):
        props.add("any_waiting")

    # AM-27: objective_satisfied:<community_name> propositions
    if satisfaction_conditions:
        discharged_or_superseded = {ObligationState.DISCHARGED, ObligationState.SUPERSEDED}
        for community_name, (operator, member_ids) in satisfaction_conditions.items():
            if operator == "all_discharged":
                satisfied = all(
                    obl_dict.get(mid) in discharged_or_superseded
                    for mid in member_ids
                )
            else:  # any_discharged
                satisfied = any(
                    obl_dict.get(mid) == ObligationState.DISCHARGED
                    for mid in member_ids
                )
            if satisfied:
                props.add(f"objective_satisfied:{community_name}")

    return props


def build_kripke_model(model: Any, horizon: int = 10) -> KripkeModel:
    """
    Build a finite Kripke model M = (W, R, V, w₀) from a parsed DSL-EL spec.

    §C.2: The model is constructed by:
      1. Extracting obligation descriptors from burdens + commitment/delegation
         structure.
      2. Creating the initial world w₀: all obligations PENDING, all actors
         ACTIVE.
      3. Expanding the reachability relation R by BFS up to horizon steps,
         applying the following transition rules at each world w:

         Rule T1 — DISCHARGE:
           For each PENDING obligation O held by an ACTIVE actor A,
           add an edge w → w' where w' is identical to w except
           obligation O is DISCHARGED. This models the actor performing
           the obligated action.

         Rule T2 — DEADLINE EXPIRY:
           If w.step >= desc.deadline_steps and O is still PENDING,
           add an edge w → w'' where O is VIOLATED. This models the
           obligation breaching its deadline.

         Rule T3 — TICK (time passes):
           Add an edge w → w_tick where step increments by 1 and all
           PENDING obligations remain PENDING. This allows the model to
           represent legitimate delay before discharge.

         Rule T4 — REVOCATION (optional):
           If the delegation is revocable, add an edge w → w_revoke
           where the holder's ActorStatus becomes INACTIVE and the
           obligation reverts to PENDING on the delegator.
           (Not yet implemented — placeholder for hybrid mode.)

    Parameters
    ----------
    model   : parsed EnterpriseSpec (output of el_parser.parse)
    horizon : maximum number of steps to expand (default 10)

    Returns
    -------
    KripkeModel with all worlds, edges, propositions, and descriptors populated.
    """
    descriptors = _build_obligation_descriptors(model)
    group_index = _build_group_index(model)
    any_discharged_groups = _build_any_discharged_groups(model)
    satisfaction_conditions = _build_satisfaction_conditions(model)

    if not descriptors:
        # No obligations found — return trivial model
        w0_obligs = frozenset()
        w0_actors = frozenset()
        w0 = World(obligation_states=w0_obligs, actor_states=w0_actors, step=0)
        props = {w0: _build_propositions(w0, satisfaction_conditions)}
        props[w0].add("all_discharged")  # vacuously true
        return KripkeModel(
            initial=w0,
            worlds={w0},
            edges={},
            propositions=props,
            labels={},
            obligation_descriptors={},
            horizon=horizon,
            group_index=group_index,
            satisfaction_conditions=satisfaction_conditions,
        )

    # Collect all actors appearing in any chain
    all_actors: Set[str] = set()
    for desc in descriptors.values():
        all_actors.update(desc.chain)

    # Build initial world: obligations with triggered_by start WAITING (trigger
    # not yet fired); all others start PENDING. All actors start ACTIVE.
    init_obligs = {
        oid: (ObligationState.WAITING if desc.triggered_by else ObligationState.PENDING)
        for oid, desc in descriptors.items()
    }
    init_actors = {actor: ActorStatus.ACTIVE for actor in all_actors}
    w0 = _make_world(init_obligs, init_actors, step=0)

    # BFS expansion
    worlds: Set[World]                       = {w0}
    edges: Dict[World, Set[World]]           = {}
    labels: Dict[Tuple[World, World], str]   = {}
    queue: deque[World]                      = deque([w0])

    _iter_count = 0
    while queue:
        w = queue.popleft()
        _iter_count += 1
        current_obligs = w.obligation_dict()
        current_actors = w.actor_dict()

        successors_for_w: Set[World] = set()

        # ── Rule T1: DISCHARGE (one obligation per transition) ────────────────
        for oid, desc in descriptors.items():
            if current_obligs.get(oid) != ObligationState.PENDING:
                continue
            if current_actors.get(desc.holder) != ActorStatus.ACTIVE:
                continue

            # Holder discharges this obligation
            new_obligs = dict(current_obligs)
            new_obligs[oid] = ObligationState.DISCHARGED

            # P6a — triggered_by cascade: if this obligation fires an event,
            # any WAITING obligation with triggered_by = that event becomes PENDING.
            # Applied before SUPERSEDED suppression so P6b can override P6a when
            # the same token is both a group sibling and a cascade target.
            if desc.fires_event:
                for other_oid, other_desc in descriptors.items():
                    if (other_desc.triggered_by == desc.fires_event
                            and new_obligs.get(other_oid) == ObligationState.WAITING):
                        new_obligs[other_oid] = ObligationState.PENDING

            # P6b — SUPERSEDED sibling suppression (any_discharged groups only).
            # When a member of an any_discharged group discharges, the remaining
            # siblings are superseded — their purpose is fulfilled by the
            # discharged member.  SUPERSEDED overrides any P6a activation.
            # Skipped for all_discharged groups: every member must independently
            # discharge; suppressing siblings would prevent the group condition
            # from ever being fully satisfied.
            for group_name, group_members in group_index.items():
                if group_name not in any_discharged_groups:
                    continue
                if oid in group_members:
                    for sibling_oid in group_members:
                        if sibling_oid == oid:
                            continue
                        sibling_state = new_obligs.get(sibling_oid)
                        if sibling_state in (ObligationState.PENDING,
                                             ObligationState.WAITING):
                            new_obligs[sibling_oid] = ObligationState.SUPERSEDED

            w_prime = _make_world(new_obligs, current_actors, w.step)
            label   = f"discharge:{oid} by {desc.holder}"

            if w_prime not in worlds:
                worlds.add(w_prime)
                if w_prime.step < horizon:
                    queue.append(w_prime)

            edges.setdefault(w, set()).add(w_prime)
            labels[(w, w_prime)] = label
            successors_for_w.add(w_prime)

        # ── Rule T2: DEADLINE VIOLATION ───────────────────────────────────────
        for oid, desc in descriptors.items():
            if current_obligs.get(oid) != ObligationState.PENDING:
                continue
            if w.step < desc.deadline_steps:
                continue

            new_obligs = dict(current_obligs)
            new_obligs[oid] = ObligationState.VIOLATED

            w_viol  = _make_world(new_obligs, current_actors, w.step)
            label   = f"violate:{oid} (deadline={desc.deadline_steps} steps)"

            if w_viol not in worlds:
                worlds.add(w_viol)
                # Violated worlds are terminal — do not enqueue further
            edges.setdefault(w, set()).add(w_viol)
            labels[(w, w_viol)] = label
            successors_for_w.add(w_viol)

        # ── Rule T3: TICK (time passes, nothing yet discharged) ───────────────
        # TICK is available only when:
        #   (a) at least one PENDING obligation has discharge_mode == 'eventual'
        #       (there is something that legitimately may be delayed), AND
        #   (b) NO PENDING strict obligation has an ACTIVE holder
        #       (a strict obligation that CAN be discharged right now MUST be —
        #        time may not pass while the holder is able to act).
        #
        # This ensures strict obligations are always discharged before any tick
        # can occur, even when other eventual obligations are also pending.
        # Consequence: once all strict obligations are discharged (or their
        # holder is inactive), time can tick freely for the eventual ones.
        if w.step < horizon:
            has_eventual_pending = any(
                current_obligs.get(oid) == ObligationState.PENDING
                and descriptors[oid].discharge_mode == "eventual"
                for oid in descriptors
            )
            has_strict_pending_dischargeable = any(
                current_obligs.get(oid) == ObligationState.PENDING
                and descriptors[oid].discharge_mode == "strict"
                and current_actors.get(descriptors[oid].holder) == ActorStatus.ACTIVE
                for oid in descriptors
            )
            if has_eventual_pending and not has_strict_pending_dischargeable:
                w_tick = _make_world(current_obligs, current_actors, w.step + 1)
                label  = "tick (time passes)"

                if w_tick not in worlds:
                    worlds.add(w_tick)
                    queue.append(w_tick)

                edges.setdefault(w, set()).add(w_tick)
                labels[(w, w_tick)] = label
                successors_for_w.add(w_tick)

    print(f"[Kripke] Converged in {_iter_count} iterations")

    # Build proposition sets for every world
    propositions = {w: _build_propositions(w, satisfaction_conditions) for w in worlds}

    return KripkeModel(
        initial=w0,
        worlds=worlds,
        edges=edges,
        propositions=propositions,
        labels=labels,
        obligation_descriptors=descriptors,
        horizon=horizon,
        group_index=group_index,
        satisfaction_conditions=satisfaction_conditions,
    )


# ══════════════════════════════════════════════════════════════════════════════
# §C.4  —  Action recommendation dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ActionRecommendation:
    """
    §C.4: The result of evaluating one available action from a given world.

    An action corresponds to a single transition w → w' in the Kripke model.
    The recommendation scores it by expected future utility — the mean utility
    over all worlds reachable from the successor state w'. This captures the
    quality of the entire future opened up by taking the action, not just the
    immediate outcome.

    Attributes
    ----------
    rank                   : 1 = best available action from the current world
    action_label           : transition label (e.g. "discharge:seekConsentObligation
                             by AIDiagnosticAgent")
    successor_world        : world reached by taking this action
    immediate_utility      : utility(successor_world) — the one-step outcome
    expected_future_utility: mean utility over all worlds reachable from
                             successor_world — the long-run quality of this choice
    """
    rank: int
    action_label: str
    successor_world: World
    immediate_utility: float
    expected_future_utility: float

    def render(self) -> str:
        marker = "★" if self.rank == 1 else f" {self.rank}"
        obl_str = ", ".join(
            f"{k}={v.name}" for k, v in sorted(self.successor_world.obligation_states)
        )
        return (
            f"  [{marker}] {self.action_label}\n"
            f"       → {self.successor_world}\n"
            f"       immediate utility    : {self.immediate_utility:+.3f}\n"
            f"       expected future util : {self.expected_future_utility:+.3f}"
        )


@dataclass
class BellmanStep:
    """
    One step along the Bellman-optimal path (Level 3, §C.4).

    Attributes
    ----------
    action_label     : transition label ("discharge:X by Y")
    successor_world  : world reached by this action
    immediate_reward : r(w → successor_world) = utility(successor_world)
    v_star           : V*(successor_world) — Bellman-optimal value of successor
    q_value          : Q(w, action) = immediate_reward + γ · V*(successor_world)
    """
    action_label: str
    successor_world: World
    immediate_reward: float
    v_star: float
    q_value: float


# ══════════════════════════════════════════════════════════════════════════════
# Verdict dataclass — structured output from modal checks
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ObligationVerdict:
    """
    The result of a modal operator check on a single obligation.

    Attributes
    ----------
    obligation_id      : burden name from DSL
    obligation_text    : natural-language obligation text
    modal_operator     : "AF" (obligation) or "EF" (permission)
    satisfied          : True iff the modal property holds from the initial world
    worlds_checked     : total worlds in the model (gives a sense of model size)
    counterexample_path: for AF, the path that never discharges (if not satisfied)
    witness_path       : for EF, the shortest path that discharges (if satisfied)
    holder             : actor currently holding the obligation
    chain              : full delegation chain [root → holder]
    """
    obligation_id: str
    obligation_text: str
    modal_operator: str          # "AF" or "EF"
    satisfied: bool
    worlds_checked: int
    holder: str
    chain: List[str]
    counterexample_path: Optional[List[Tuple[World, str]]] = None
    witness_path: Optional[List[Tuple[World, str]]] = None

    def render(self) -> str:
        verdict_sym = "✓" if self.satisfied else "✗"
        verdict_str = "SATISFIED" if self.satisfied else "NOT SATISFIED"

        lines = [
            "─" * 60,
            f"{verdict_sym} {self.modal_operator} — {verdict_str}",
            "─" * 60,
            f"  Obligation : '{self.obligation_text}'",
            f"  Burden ID  : {self.obligation_id}",
            f"  Holder     : {self.holder}",
        ]
        if self.chain:
            lines.append(f"  Chain      : {' → '.join(self.chain)}")
        lines.append(f"  Worlds     : {self.worlds_checked} explored")

        if self.modal_operator == "AF":
            if self.satisfied:
                lines.append(
                    "  Verdict    : Obligation WILL be discharged on every "
                    "possible future path (§C.2 AF satisfied)."
                )
            else:
                lines.append(
                    "  Verdict    : Obligation CANNOT be guaranteed to discharge — "
                    "at least one path avoids it (§C.2 AF violated)."
                )
                if self.counterexample_path:
                    lines.append("  Counterexample path:")
                    for world, label in self.counterexample_path:
                        lines.append(f"    {world}  [{label}]")

        else:  # EF
            if self.satisfied:
                lines.append(
                    "  Verdict    : Obligation CAN be discharged on at least one "
                    "path — permission verified (§C.2 EF satisfied)."
                )
                if self.witness_path:
                    lines.append("  Witness path:")
                    for world, label in self.witness_path:
                        lines.append(f"    {world}  [{label}]")
            else:
                lines.append(
                    "  Verdict    : No path exists on which this obligation is "
                    "discharged — effectively prohibited."
                )

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Hybrid mode bridge: Layer 3 (Runtime/WorldState) → Layer 4 (Kripke)
# ══════════════════════════════════════════════════════════════════════════════

def _delegation_chain_for_token(spec: Any, token_name: str, holder: str) -> List[str]:
    """Walk DelegationDecl back-links to build [root, …, holder] for a token."""
    parent: Dict[str, str] = {}
    for d in _collect(spec, "Delegation"):  # AM-18: DelegationDecl → Delegation
        b = getattr(d, "burden", None)
        if b and _obj_name(b) == token_name:
            frm, to = _obj_name(d.delegator), _obj_name(d.delegate)
            if frm and to:
                parent[to] = frm
    chain, cur = [holder], holder
    while cur in parent:
        cur = parent[cur]
        if cur in chain:
            break
        chain.insert(0, cur)
    return chain


def build_kripke_from_runtime(runtime: Any, horizon: int) -> KripkeModel:
    """
    Hybrid mode (ISO 15414 Annex C): KripkeModel anchored to runtime.current_state().

    burden/active→PENDING, /discharged or in ledger→DISCHARGED, /violated→VIOLATED.
    Actors from WorldState→ACTIVE. BFS expansion uses the same T1/T2/T3 rules.
    """
    state, spec, ledger = runtime.current_state(), runtime._spec, runtime._ledger
    group_index = _build_group_index(spec)
    satisfaction_conditions = _build_satisfaction_conditions(spec)
    discharged_in_ledger: Set[str] = {n for r in ledger for n in r.discharged}
    init_obligs: Dict[str, ObligationState] = {}
    descriptors: Dict[str, ObligationDescriptor] = {}

    for tok in state.tokens:
        if tok.kind != "burden":
            continue
        obl_st = (
            ObligationState.DISCHARGED
            if tok.state in ("discharged", "terminated") or tok.token_name in discharged_in_ledger
            else ObligationState.VIOLATED if tok.state == "violated"
            else ObligationState.PENDING
        )
        init_obligs[tok.token_name] = obl_st
        spec_tok = next(
            (e for e in spec.elements
             if type(e).__name__ == "DeonticToken" and e.name == tok.token_name), None
        )
        dl = getattr(spec_tok, "deadline", None)
        try:
            steps = int(dl) if dl else 5
        except (ValueError, TypeError):
            steps = _parse_deadline_steps(dl, default=5)
        chain = _delegation_chain_for_token(spec, tok.token_name, tok.holder)
        descriptors[tok.token_name] = ObligationDescriptor(
            obligation_id=tok.token_name, obligation_text=tok.token_name,
            deadline_steps=steps, holder=tok.holder, chain=chain,
            revocable=False, sub_delegation_allowed=False,
            discharge_mode=tok.discharge_mode or "eventual",
            priority_weight=_priority_weight(tok.priority),
        )

    init_actors: Dict[str, ActorStatus] = {a.actor_name: ActorStatus.ACTIVE for a in state.actors}
    for desc in descriptors.values():
        for m in desc.chain:
            if m not in init_actors:
                init_actors[m] = ActorStatus.ACTIVE
    w0 = _make_world(init_obligs, init_actors, step=state.tick)
    worlds, edges, labels, queue = {w0}, {}, {}, deque([w0])

    while queue:
        w = queue.popleft()
        obligs, actors = w.obligation_dict(), w.actor_dict()
        for oid, desc in descriptors.items():
            if obligs.get(oid) == ObligationState.PENDING:
                if actors.get(desc.holder) == ActorStatus.ACTIVE:
                    wd = _make_world({**obligs, oid: ObligationState.DISCHARGED}, actors, w.step)
                    if wd not in worlds:
                        worlds.add(wd)
                        if wd.step < horizon:
                            queue.append(wd)
                    edges.setdefault(w, set()).add(wd)
                    labels[(w, wd)] = f"discharge:{oid} by {desc.holder}"
                if w.step >= desc.deadline_steps:
                    wv = _make_world({**obligs, oid: ObligationState.VIOLATED}, actors, w.step)
                    if wv not in worlds:
                        worlds.add(wv)
                    edges.setdefault(w, set()).add(wv)
                    labels[(w, wv)] = f"violate:{oid}"
        if w.step < horizon and any(
            obligs.get(o) == ObligationState.PENDING
            and descriptors[o].discharge_mode == "eventual"
            for o in descriptors
        ) and not any(
            obligs.get(o) == ObligationState.PENDING
            and descriptors[o].discharge_mode == "strict"
            and actors.get(descriptors[o].holder) == ActorStatus.ACTIVE
            for o in descriptors
        ):
            wt = _make_world(obligs, actors, w.step + 1)
            if wt not in worlds:
                worlds.add(wt)
                queue.append(wt)
            edges.setdefault(w, set()).add(wt)
            labels[(w, wt)] = "tick"

    props = {w: _build_propositions(w, satisfaction_conditions) for w in worlds}
    return KripkeModel(
        initial=w0, worlds=worlds, edges=edges, propositions=props,
        labels=labels, obligation_descriptors=descriptors, horizon=horizon,
        group_index=group_index,
        satisfaction_conditions=satisfaction_conditions,
    )


def _run_hybrid_smoke_test() -> None:
    """Hybrid mode smoke test: Runtime → KripkeModel with AF/EF checks."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from el_parser import parse
    from el_runtime import Runtime
    from el_engine import grant_token, token_from_spec

    scenario = Path(__file__).parent.parent / "scenarios" / "consent" / "consent_scenario.el"
    result = parse(scenario, validate=False)
    if not result.ok:
        print(f"[hybrid] Parse failed: {result.errors}"); return

    rt = Runtime.build_from_spec(result.model)
    if not rt.current_state().tokens:        # fallback: grant tokens manually
        for name, holder in [("seekConsentObligation", "AIDiagnosticAgent"),
                              ("aiAnalysisPermit",      "AIDiagnosticAgent")]:
            rt._state = grant_token(rt._state, token_from_spec(result.model, name, holder))

    rt.advance("seek_patient_consent", "AIDiagnosticAgent")   # one step forward

    km = build_kripke_from_runtime(rt, horizon=5)
    print(f"\n{'═' * 60}")
    print("Consent Scenario — Hybrid Kripke Model (anchored to Runtime state)")
    print(f"{'═' * 60}")
    print(f"  Worlds: {len(km.worlds)}  Tick: {km.initial.step}  Initial: {km.initial}")
    for oid in km.obligation_descriptors:
        vaf, vef = km.check_obligation(oid), km.check_permission(oid)
        print(f"  {oid}:")
        print(f"    AF (obligation) : {'✓ SATISFIED' if vaf.satisfied else '✗ NOT SATISFIED'}")
        print(f"    EF (permission) : {'✓ SATISFIED' if vef.satisfied else '✗ NOT SATISFIED'}")


# ══════════════════════════════════════════════════════════════════════════════
# Standalone: consent scenario synthetic test
# (runs without a parsed spec; validates the module independently)
# ══════════════════════════════════════════════════════════════════════════════

def _run_consent_scenario() -> None:
    """
    Synthetic Kripke model for the digital health consent scenario.

    Delegation chain: GPPracticeParty → SpecialistAgent → AIDiagnosticAgent
    Obligation: seekConsentObligation
    Deadline: 3 steps (representing a clinical session window)

    Question: Does AF(discharged:seekConsentObligation) hold?

    Expected answer: YES — because:
      1. AIDiagnosticAgent (the leaf holder) is ACTIVE.
      2. The obligation is PENDING.
      3. Rule T1 adds a DISCHARGE edge before the deadline.
      4. Every path either discharges or hits VIOLATED — but the
         DISCHARGE edge is always available before deadline.
    """
    print("\n" + "═" * 60)
    print("Consent Scenario — Synthetic Kripke Model")
    print("(Validation case from position paper §6.4)")
    print("═" * 60)

    DESC = ObligationDescriptor(
        obligation_id="seekConsentObligation",
        obligation_text="Seek informed consent before AI diagnostic analysis",
        deadline_steps=3,
        holder="AIDiagnosticAgent",
        chain=["GPPracticeParty", "SpecialistAgent", "AIDiagnosticAgent"],
        revocable=True,
        sub_delegation_allowed=False,
    )

    # Build the model manually (no DSL parser available in this test)
    actors     = {"GPPracticeParty", "SpecialistAgent", "AIDiagnosticAgent"}
    descriptors = {DESC.obligation_id: DESC}

    init_obligs = {"seekConsentObligation": ObligationState.PENDING}
    init_actors = {a: ActorStatus.ACTIVE for a in actors}
    w0 = _make_world(init_obligs, init_actors, step=0)

    worlds: Set[World]                     = {w0}
    edges: Dict[World, Set[World]]         = {}
    labels: Dict[Tuple[World, World], str] = {}
    queue: deque[World]                    = deque([w0])
    horizon = 5

    _iter_count = 0
    while queue:
        w = queue.popleft()
        _iter_count += 1
        obligs = w.obligation_dict()
        act    = w.actor_dict()

        # T1: Discharge
        if obligs.get("seekConsentObligation") == ObligationState.PENDING \
                and act.get("AIDiagnosticAgent") == ActorStatus.ACTIVE:
            new_o = {**obligs, "seekConsentObligation": ObligationState.DISCHARGED}
            wd = _make_world(new_o, act, w.step)
            if wd not in worlds:
                worlds.add(wd)
            edges.setdefault(w, set()).add(wd)
            labels[(w, wd)] = "discharge:seekConsentObligation by AIDiagnosticAgent"

        # T2: Violation
        if obligs.get("seekConsentObligation") == ObligationState.PENDING \
                and w.step >= DESC.deadline_steps:
            new_o = {**obligs, "seekConsentObligation": ObligationState.VIOLATED}
            wv = _make_world(new_o, act, w.step)
            if wv not in worlds:
                worlds.add(wv)
            edges.setdefault(w, set()).add(wv)
            labels[(w, wv)] = f"violate:seekConsentObligation (deadline={DESC.deadline_steps})"

        # T3: Tick
        if w.step < horizon \
                and obligs.get("seekConsentObligation") == ObligationState.PENDING:
            wt = _make_world(obligs, act, w.step + 1)
            if wt not in worlds:
                worlds.add(wt)
                queue.append(wt)
            edges.setdefault(w, set()).add(wt)
            labels[(w, wt)] = "tick (time passes)"

    print(f"[Kripke] Converged in {_iter_count} iterations")

    props = {w: _build_propositions(w) for w in worlds}

    km = KripkeModel(
        initial=w0,
        worlds=worlds,
        edges=edges,
        propositions=props,
        labels=labels,
        obligation_descriptors=descriptors,
        horizon=horizon,
        group_index={},
        satisfaction_conditions={},
    )

    print(km.render_summary())
    print()

    # AF check — obligation
    verdict_af = km.check_obligation("seekConsentObligation")
    print(verdict_af.render())
    print()

    # EF check — permission
    verdict_ef = km.check_permission("seekConsentObligation")
    print(verdict_ef.render())
    print()

    # Utility ranking
    print("[Diagnostic] Actual outcome score mapping in utility() (§C.3):")
    print("  DISCHARGED → +1.0  |  PENDING → +0.3  |  EXPIRED →  0.0  |  VIOLATED → -1.0")
    print("  (paper claims PENDING=0; implementation uses +0.3 — explains utility=+0.30 for PENDING worlds)")
    print()
    print("§C.3/C.4 — Utility-ranked reachable worlds from w₀:")
    for w, u in km.ranked_reachable(km.initial):
        obl_str = ", ".join(
            f"{k}={v.name}" for k, v in sorted(w.obligation_states)
        )
        print(f"  step={w.step:2d}  utility={u:+.2f}  [{obl_str}]")

    # Explain why AF does/does not hold
    print()
    if not verdict_af.satisfied:
        print("AF counterexample path:")
        if verdict_af.counterexample_path:
            for ww, lbl in verdict_af.counterexample_path:
                print(f"  {ww}  [{lbl}]")
        else:
            print("  (no counterexample path recorded)")
    else:
        print("AF holds — verifying with EF witness path:")
        if verdict_ef.witness_path:
            for ww, lbl in verdict_ef.witness_path:
                print(f"  {ww}  [{lbl}]")


if __name__ == "__main__":
    _run_consent_scenario()
    _run_hybrid_smoke_test()
