"""
T5 (exercise) requires every permit the action requires, in both builders.

The engine's Step 6 performs an action only when the actor holds every
permit named by its requires_permit clauses, each active. T6 (examine)
already read the whole list; T5 checked only the permit being exercised,
so a model could exercise a permit for an action the engine refuses
(EF falsely true). Fixture: one action `act` requiring permits `p` and
`q`; Worker fills the role and holds `p`.

  - Hybrid: no exercise edge when `q` is not granted, pending, or held by
    another actor; the edge when Worker holds both; the edge follows the
    per-world state of `q` through a revoke and a reinstate.
  - Static: no exercise edge when `q` is pending in the specification.
  - Sweep: over the fixture states, an exercise edge for an actor exists
    exactly when the engine accepts that actor's act.
  - T5 and T6 read the same rule: with a burden gated on `act`, exercise
    and examine edges are present or absent together.
"""
import contextlib
import dataclasses
import io

import pytest

from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _spec(src):
    result = parse_string(src, validate=False)
    assert result.ok, result.errors
    return result.model


_TWO_PERMITS = """
enterprise specification TwoPermitProbe

agent Worker { holds p }
agent Other { }

permit p { for_action: "act" state: active }
permit q { for_action: "act" state: {q_state} }
{extra_tokens}
community ProbeCommunity {
    objective: "probe an action that requires two permits"
    Worker fills workerRole
    Other fills workerRole
    role workerRole {
        action act { actor: workerRole requires_permit p requires_permit q }
    }
}
{extra_elements}
"""


def _src(q_state="active", worker_holds_q=False, extra_tokens="", extra_elements=""):
    src = (_TWO_PERMITS.replace("{q_state}", q_state)
           .replace("{extra_tokens}", extra_tokens)
           .replace("{extra_elements}", extra_elements))
    if worker_holds_q:
        src = src.replace("agent Worker { holds p }", "agent Worker { holds p holds q }")
    return src


# State name -> (holder of q or None, state q is granted in)
_STATES = {
    "q not granted": (None, None),
    "q pending": ("Worker", "pending"),
    "q held by other": ("Other", "active"),
    "both held": ("Worker", "active"),
}


def _runtime(spec, q_holder, q_state, extra_grants=()):
    state = initial_state()
    for actor in ("Worker", "Other"):
        state = enroll(state, actor, role_name="workerRole")
    state = grant_token(state, token_from_spec(spec, "p", "Worker", 0))
    if q_holder is not None:
        token = token_from_spec(spec, "q", q_holder, 0)
        state = grant_token(state, dataclasses.replace(token, state=q_state))
    for token_name, holder in extra_grants:
        state = grant_token(state, token_from_spec(spec, token_name, holder, 0))
    return Runtime(state, spec)


def _exercise_edges(km, world=None):
    """Labels of the exercise edges for `act` leaving `world` (default w0)."""
    world = km.initial if world is None else world
    return {
        km.labels[(world, s)] for s in km.successors(world)
        if km.labels[(world, s)].startswith("exercise:")
        and km.labels[(world, s)].endswith(" → act")
    }


def _hybrid(spec, rt, horizon=3):
    return _quiet(build_kripke_from_runtime, rt, horizon=horizon)


@pytest.fixture(scope="module")
def spec():
    return _spec(_src())


# ── Hybrid ─────────────────────────────────────────────────────────────────

def test_hybrid_t5_refuses_when_second_permit_not_granted(spec):
    rt = _runtime(spec, *_STATES["q not granted"])
    assert _exercise_edges(_hybrid(spec, rt)) == set()
    rec = rt.advance("act", "Worker")
    assert rec.outcome == "blocked"
    assert "'q'" in rec.reason


def test_hybrid_t5_refuses_when_second_permit_pending(spec):
    rt = _runtime(spec, *_STATES["q pending"])
    assert _exercise_edges(_hybrid(spec, rt)) == set()
    rec = rt.advance("act", "Worker")
    assert rec.outcome == "blocked"
    assert "'q'" in rec.reason


def test_hybrid_t5_refuses_when_second_permit_held_by_other_actor(spec):
    rt = _runtime(spec, *_STATES["q held by other"])
    assert _exercise_edges(_hybrid(spec, rt)) == set()
    assert rt.advance("act", "Worker").outcome == "blocked"
    assert rt.advance("act", "Other").outcome == "blocked"


def test_hybrid_t5_keeps_edge_when_every_permit_held(spec):
    rt = _runtime(spec, *_STATES["both held"])
    assert _exercise_edges(_hybrid(spec, rt)) != set()
    assert rt.advance("act", "Worker").outcome == "ok"


def test_hybrid_t5_follows_per_world_permit_state():
    # q is granted by a revocable authorization; revoking it (T7)
    # supersedes q, reinstating it (T8) makes it active again. The
    # revocation embargo covers an unrelated action, so only q's state
    # decides the exercise edge.
    spec = _spec(_src(
        extra_tokens='embargo qRevoked { for_action: "unrelated" state: pending }',
        extra_elements=(
            "authorization QGrant {\n"
            "    authority: Other\n"
            "    to_agent: Worker\n"
            "    grants_permit: q\n"
            "    revocable: true\n"
            "    on_revocation: activate qRevoked\n"
            "}\n"
        ),
    ))
    km = _hybrid(spec, _runtime(spec, "Worker", "active"))
    assert _exercise_edges(km) != set()

    def follow(world, label):
        [nxt] = [s for s in km.successors(world) if km.labels[(world, s)] == label]
        return nxt

    revoked = follow(km.initial, "revoke:QGrant")
    assert revoked.permit_dict()["q"] == "superseded"
    assert _exercise_edges(km, revoked) == set()

    reinstated = follow(revoked, "reinstate:QGrant")
    assert reinstated.permit_dict()["q"] == "active"
    assert _exercise_edges(km, reinstated) != set()


# ── Static ─────────────────────────────────────────────────────────────────

def test_static_t5_refuses_when_second_permit_inactive():
    pending = _spec(_src(q_state="pending", worker_holds_q=True))
    assert _exercise_edges(_quiet(build_kripke_model, pending, horizon=3)) == set()

    active = _spec(_src(q_state="active", worker_holds_q=True))
    assert _exercise_edges(_quiet(build_kripke_model, active, horizon=3)) != set()


# ── Engine parity ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("state_name", sorted(_STATES))
def test_t5_edge_iff_engine_accepts(spec, state_name):
    # The fixture has no preconditions and no embargoes, so Step 6 and the
    # role check are the only rules that can refuse the act.
    q_holder, q_state = _STATES[state_name]
    holders = {"p": "Worker"}
    if q_holder is not None:
        holders["q"] = q_holder
    km = _hybrid(spec, _runtime(spec, q_holder, q_state))
    edge_actors = {
        holders[label[len("exercise:"):].split(" → ", 1)[0]]
        for label in _exercise_edges(km)
    }
    for actor in ("Worker", "Other"):
        rec = _runtime(spec, q_holder, q_state).advance("act", actor)
        assert (actor in edge_actors) is (rec.outcome == "ok"), (actor, rec.reason)


_GATED = 'burden b { for_action: "act" state: active discharge_mode: eventual }'
_GATED_COMMITMENT = 'commitment WorkerActs { by: Worker obligation: "act" creates_burden: b }'


@pytest.mark.parametrize("state_name", sorted(_STATES))
def test_t5_and_t6_read_the_same_permit_rule(state_name):
    spec = _spec(_src(extra_tokens=_GATED, extra_elements=_GATED_COMMITMENT))
    km = _hybrid(spec, _runtime(spec, *_STATES[state_name], extra_grants=[("b", "Worker")]))
    w0 = km.initial
    labels = {km.labels[(w0, s)] for s in km.successors(w0)}
    exercised = any(l.startswith("exercise:") and l.endswith(" → act") for l in labels)
    examined = "examine:b → act" in labels
    assert exercised is examined
    assert exercised is (state_name == "both held")
