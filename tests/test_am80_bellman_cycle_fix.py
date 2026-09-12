"""
Layer 4 — AM-80 (2026-09-09): `bellman_values()`'s cycle-handling crash.

docs/design_notes/DN_015_bellman_cycle_fix.md.

Root problem: `bellman_values()` computed V*(w) via Kahn's-topological-sort
backward induction, which assumes the world graph is a DAG. Every transition
rule before T7/T8 (AM-79) is monotone (PENDING->DISCHARGED/VIOLATED/etc, never
back), so no cycle could previously arise. T7 (Authorization Revoke) / T8
(Authorization Reinstate) are the first genuinely reversible pair -- revoke
then reinstate, with nothing else changed in between, returns to a world
indistinguishable from a prior one -- creating a real cycle. Under Kahn's
algorithm, worlds caught in a cycle never reach in-degree zero, never enter
the topological order, and are silently skipped, so an already-processed
world looking one up as a successor raises `KeyError`.

AM-80 replaces the one-pass backward induction with standard iterative value
iteration, which converges to the same fixed point on a DAG and also handles
cycles correctly (contraction mapping, gamma < 1).

This file exercises the exact live-crash scenario (all discharge-able
referral burdens DISCHARGED, exposing a revoke/reinstate 2-cycle reachable
from w0) plus a convergence-equivalence check against the old algorithm on a
genuinely acyclic sub-scenario (fresh runtime, before any revoke/reinstate is
reachable -- see test_hybrid_t7_t8_authorization_revoke_reinstate.py's own
guard test for why no revoke/reinstate edge exists from a fresh w0).
"""
from collections import deque
from types import SimpleNamespace

from el_api import _build_referral_runtime
from el_engine import discharge_burden
from el_kripke import KripkeModel, build_kripke_from_runtime
from el_runtime import Runtime

REFERRAL_BURDENS = [
    "referralInitiationBurden",
    "clinicalHandoverBurden",
    "referralResponseBurden",
    "assessmentSchedulingBurden",
    "aiExaminationBurden",
]


def _discharge_all_referral_burdens():
    """Builds the exact live-crash state: every discharge-able referral
    burden DISCHARGED, which (per AM-79) leaves patientDataAuthorization's
    permit/embargo pair free to revoke/reinstate with no strict burden
    left to block it -- and, since T7/T8 depend only on permit state, not
    obligation completion, a revoke/reinstate/revoke... cycle is reachable
    even from this fully-discharged world."""
    rt = _build_referral_runtime()
    state, spec = rt.current_state(), rt._spec
    for burden in REFERRAL_BURDENS:
        state, record = discharge_burden(state, spec, burden)
        assert record.outcome == "ok", (burden, record)
    return Runtime(state, spec)


def _graph_has_cycle(km) -> bool:
    """Plain DFS cycle check, independent of bellman_values() itself."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {w: WHITE for w in km.worlds}

    def visit(w):
        color[w] = GRAY
        for s in km.successors(w):
            if color[s] == GRAY:
                return True
            if color[s] == WHITE and visit(s):
                return True
        color[w] = BLACK
        return False

    return any(color[w] == WHITE and visit(w) for w in km.worlds)


def _bellman_values_topo_sort(km, gamma: float = 0.9):
    """The pre-AM-80 algorithm, reimplemented here (not imported) so this
    test keeps working as a regression check even after el_kripke.py's
    own bellman_values() moves on. Correct only on a DAG -- callers must
    not use it on a graph containing a cycle."""
    in_degree = {w: 0 for w in km.worlds}
    for w in km.worlds:
        for succ in km.successors(w):
            in_degree[succ] += 1

    queue = deque(w for w in km.worlds if in_degree[w] == 0)
    topo_order = []
    while queue:
        w = queue.popleft()
        topo_order.append(w)
        for succ in km.successors(w):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    V = {}
    for w in reversed(topo_order):
        succs = km.successors(w)
        if not succs:
            V[w] = km.utility(w)
        else:
            V[w] = max(
                km.utility(w_prime) + gamma * V[w_prime] for w_prime in succs
            )
    return V


def test_all_referral_burdens_discharged_graph_contains_a_genuine_cycle():
    """Sanity check on the fixture itself: confirms this reproduction
    actually exercises a cycle (not just a graph that happens not to
    crash the old algorithm), independent of bellman_values()."""
    rt = _discharge_all_referral_burdens()
    km = build_kripke_from_runtime(rt, horizon=10)
    assert _graph_has_cycle(km)


def test_bellman_values_completes_and_covers_every_world_on_cyclic_graph():
    """The direct reproduction: the exact live-crash scenario (all five
    discharge-able referral burdens DISCHARGED) must no longer raise
    KeyError, and must return a value for every world in km.worlds --
    including the ones caught in the revoke/reinstate cycle, which the
    pre-AM-80 algorithm silently dropped from topo_order."""
    rt = _discharge_all_referral_burdens()
    km = build_kripke_from_runtime(rt, horizon=10)

    V = km.bellman_values(gamma=0.9)

    assert set(V.keys()) == km.worlds
    assert all(isinstance(v, float) for v in V.values())


def test_bellman_values_matches_old_algorithm_on_synthetic_acyclic_dag():
    """Convergence-equivalence check, DN_015 §5: on a genuinely acyclic
    graph, AM-80's iterative value iteration must converge to the same
    V* the old one-pass topological backward induction produced. Proves
    this isn't just "doesn't crash" but "still correct where it used to
    be correct."

    Uses a small synthetic DAG (plain strings as worlds) rather than a
    real-scenario subgraph: the real referral scenario turns out to have
    revoke/reinstate cycles reachable at modest horizon even from a
    fresh w0 (once referralInitiationBurden clears down some path), so
    "acyclic real subgraph" is not a stable fixture to build a
    regression test on. bellman_values() only touches self.worlds,
    self.successors(w) and self.utility(w), so a duck-typed stand-in
    exercises the identical code path.
    """
    worlds = {"A", "B", "C", "D"}
    edges = {"A": {"B", "C"}, "B": {"D"}, "C": {"D"}, "D": set()}
    utilities = {"A": 0.0, "B": 1.0, "C": 2.0, "D": 5.0}

    fake_km = SimpleNamespace(
        worlds=worlds,
        successors=lambda w: edges[w],
        utility=lambda w: utilities[w],
    )
    assert not _graph_has_cycle(fake_km)

    v_old = _bellman_values_topo_sort(fake_km, gamma=0.9)
    v_new = KripkeModel.bellman_values(fake_km, gamma=0.9)

    assert set(v_old.keys()) == set(v_new.keys()) == worlds
    for w in worlds:
        assert abs(v_old[w] - v_new[w]) < 1e-6


def test_bellman_values_satisfies_fixed_point_equation_on_real_cyclic_graph():
    """Correctness check on the actual crashing graph: since the old
    algorithm cannot run on a cyclic graph at all (that's the bug), the
    equivalence check for this fixture is the Bellman fixed-point
    equation itself -- V*(w) = utility(w) for a terminal world, or
    max over successors of [utility(w') + gamma*V*(w')] otherwise --
    holding for every world AM-80's value iteration produced."""
    rt = _discharge_all_referral_burdens()
    km = build_kripke_from_runtime(rt, horizon=10)
    gamma = 0.9

    V = km.bellman_values(gamma=gamma)

    for w in km.worlds:
        succs = km.successors(w)
        if not succs:
            expected = km.utility(w)
        else:
            expected = max(
                km.utility(w_prime) + gamma * V[w_prime] for w_prime in succs
            )
        assert abs(V[w] - expected) < 1e-4


def test_bellman_values_converges_within_default_epsilon():
    """Regression guard on the new epsilon/max_iterations parameters: on
    the cyclic graph, iteration must actually converge (not silently
    bottom out at max_iterations with a still-changing value)."""
    rt = _discharge_all_referral_burdens()
    km = build_kripke_from_runtime(rt, horizon=10)

    v_tight = km.bellman_values(gamma=0.9, epsilon=1e-6, max_iterations=1000)
    v_looser = km.bellman_values(gamma=0.9, epsilon=1e-3, max_iterations=1000)

    for w in km.worlds:
        assert abs(v_tight[w] - v_looser[w]) < 1e-2


def test_optimal_path_still_works_after_am80():
    """optimal_path() depends on bellman_values() succeeding first; its
    own cycle handling (visited-set check while walking) is unmodified
    by AM-80, but this confirms the two compose correctly post-fix."""
    rt = _discharge_all_referral_burdens()
    km = build_kripke_from_runtime(rt, horizon=10)

    path = km.optimal_path(gamma=0.9, max_steps=20)
    assert isinstance(path, list)
