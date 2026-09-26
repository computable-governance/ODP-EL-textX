"""
AM-102 — one embargo blocking rule for the engine and the verifier.

el_engine._embargo_coverage(): an embargo covers the Actions that name it
via inhibited_by_embargo; else its for_action; else every action of its
holder. The engine's Step 5, el_api's available-actions and both Kripke
builders' embargo guards (T1, T5, T6, T9, T11) all read it. Before AM-102
the engine read only the embargo's for_action and the verifier only the
naming Actions (T5/T6 only), so the layers blocked different actions.

  - Parity fixture, one actor per case, classes b (for_action, named by
    nothing), c (named by an Action other than its for_action) and d
    (general): each case's action is blocked by the engine iff neither
    builder has its T5 or T1 edge at w0 — including discharging actions.
  - T11 and T9 (actions any enrolled actor may perform): the edge goes
    only when every performer is embargoed, as the engine refuses only
    the embargoed actor.
  - available-actions follows the same rule.
  - [W-18] flags exactly the class c embargoes, and no tracked scenario.
"""
import contextlib
import io
from pathlib import Path

import pytest

import el_api
import el_engine
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse, parse_string
from el_validator import validate_spec
from el_runtime import Runtime


_REPO = Path(__file__).resolve().parent.parent


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _spec(src):
    result = parse_string(src, validate=False)
    assert result.ok, result.errors
    return result.model


def _runtime(spec, actors, grants):
    state = initial_state()
    for actor, role in actors:
        state = enroll(state, actor, role_name=role)
    for token, holder in grants:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    return Runtime(state, spec)


def _models(spec, rt, horizon=3):
    return {
        "static": _quiet(build_kripke_model, spec, horizon=horizon),
        "hybrid": _quiet(build_kripke_from_runtime, rt, horizon=horizon),
    }


# ── Parity fixture: classes b, c, d; exercises and discharges ────────────────

_CLASSES = """
enterprise specification EmbargoParityProbe

agent WorkerB { holds permitB holds embargoB }
agent WorkerC { holds permitSubmit holds permitRetry holds embargoC }
agent WorkerD { holds permitD holds burdenD holds embargoD }
agent WorkerE { holds burdenE holds embargoE }
agent WorkerF { holds burdenF holds burdenLogF holds embargoF }

permit permitB      { for_action: "doB"    state: active }
permit permitSubmit { for_action: "submit" state: active }
permit permitRetry  { for_action: "retry"  state: active }
permit permitD      { for_action: "doD"    state: active }

burden burdenD    { for_action: "fileD" state: active discharge_mode: eventual }
burden burdenE    { for_action: "fileE" state: active discharge_mode: eventual }
burden burdenF    { for_action: "fileF" state: active discharge_mode: eventual }
burden burdenLogF { for_action: "logF"  state: active discharge_mode: eventual }

// (b) for_action set, named by no Action
embargo embargoB { for_action: "doB"   state: active }
embargo embargoE { for_action: "fileE" state: active }
// (c) named by an Action other than its for_action
embargo embargoC { for_action: "retry" state: active }
embargo embargoF { for_action: "logF"  state: active }
// (d) general: no for_action, named by nothing
embargo embargoD { state: active }

community ProbeCommunity {
    objective: "probe the shared embargo blocking rule"
    role workerRole {
        action doB    { actor: workerRole requires_permit permitB }
        action submit { actor: workerRole requires_permit permitSubmit inhibited_by_embargo embargoC }
        action retry  { actor: workerRole requires_permit permitRetry }
        action doD    { actor: workerRole requires_permit permitD }
        action fileD  { actor: workerRole }
        action fileE  { actor: workerRole }
        action fileF  { actor: workerRole inhibited_by_embargo embargoF }
        action logF   { actor: workerRole }
    }
}

commitment DFiles  { by: WorkerD obligation: "file D"  creates_burden: burdenD }
commitment EFiles  { by: WorkerE obligation: "file E"  creates_burden: burdenE }
commitment FFiles  { by: WorkerF obligation: "file F"  creates_burden: burdenF }
commitment FLogs   { by: WorkerF obligation: "log F"   creates_burden: burdenLogF }
"""

_CLASS_GRANTS = [
    ("permitB", "WorkerB"), ("embargoB", "WorkerB"),
    ("permitSubmit", "WorkerC"), ("permitRetry", "WorkerC"), ("embargoC", "WorkerC"),
    ("permitD", "WorkerD"), ("burdenD", "WorkerD"), ("embargoD", "WorkerD"),
    ("burdenE", "WorkerE"), ("embargoE", "WorkerE"),
    ("burdenF", "WorkerF"), ("burdenLogF", "WorkerF"), ("embargoF", "WorkerF"),
]

# (class, actor, action, engine accepts) — the engine side of the parity
_CASES = [
    ("b", "WorkerB", "doB", False),     # exercise under a for_action embargo
    ("c", "WorkerC", "submit", False),  # named Action wins ...
    ("c", "WorkerC", "retry", True),    # ... its for_action is not blocked
    ("d", "WorkerD", "doD", False),     # general embargo: exercise
    ("d", "WorkerD", "fileD", False),   # general embargo: discharge
    ("b", "WorkerE", "fileE", False),   # discharge under a for_action embargo
    ("c", "WorkerF", "fileF", False),   # discharge under a naming embargo
    ("c", "WorkerF", "logF", True),     # discharge of its for_action allowed
]


@pytest.fixture(scope="module")
def class_spec():
    return _spec(_CLASSES)


def _class_runtime(spec):
    actors = [(a, "workerRole") for a in ("WorkerB", "WorkerC", "WorkerD", "WorkerE", "WorkerF")]
    return _runtime(spec, actors, _CLASS_GRANTS)


def _w0_actions(km):
    """Actions performable from w0 via T5 (exercise) or T1 (discharge)."""
    acts = set()
    for s in km.successors(km.initial):
        label = km.labels[(km.initial, s)]
        if label.startswith("exercise:"):
            acts.add(label.split(" → ", 1)[1])
        elif label.startswith("discharge:"):
            oid = label[len("discharge:"):].split(" by ", 1)[0]
            acts.add(km.obligation_descriptors[oid].for_action)
    return acts


def test_coverage_rule(class_spec):
    assert el_engine._embargo_coverage(class_spec) == {
        "embargoB": frozenset({"doB"}),
        "embargoE": frozenset({"fileE"}),
        "embargoC": frozenset({"submit"}),
        "embargoF": frozenset({"fileF"}),
        "embargoD": None,
    }


@pytest.mark.parametrize("cls,actor,action,accepted", _CASES)
def test_engine_outcome(class_spec, cls, actor, action, accepted):
    rec = _class_runtime(class_spec).advance(action, actor)
    assert (rec.outcome == "ok") is accepted, rec.reason
    if not accepted:
        assert "embargo" in rec.reason


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_builders_match_engine(class_spec, builder):
    km = _models(class_spec, _class_runtime(class_spec))[builder]
    engine_ok = {action for _, _, action, accepted in _CASES if accepted}
    case_actions = {action for _, _, action, _ in _CASES}
    assert _w0_actions(km) & case_actions == engine_ok


def test_available_actions_follow_rule(class_spec, monkeypatch):
    monkeypatch.setattr(el_api, "_runtime", _class_runtime(class_spec))

    def permitted(actor):
        resp = el_api.get_available_actions(actor)
        return {a.action for a in resp.available_actions if a.reason == "permitted"}

    assert permitted("WorkerB") == set()
    assert permitted("WorkerC") == {"retry"}
    assert permitted("WorkerD") == set()


def test_w18_flags_class_c_only(class_spec):
    result = parse_string(_CLASSES)
    w18 = sorted(w for w in result.warnings if w.startswith("[W-18]"))
    assert len(w18) == 2
    assert "Embargo 'embargoC' has for_action 'retry'" in w18[0]
    assert "Embargo 'embargoF' has for_action 'logF'" in w18[1]


def test_w18_silent_on_tracked_scenarios():
    for path in sorted((_REPO / "scenarios").glob("**/*.el")):
        result = _quiet(parse, path, validate=False)
        if result.model is None:
            continue  # ecommerce_scenario.el does not parse
        assert not [m for m in validate_spec(result.model) if m.startswith("[W-18]")], path


# ── T11: any enrolled actor may perform an ungated emitting action ───────────

_T11 = """
enterprise specification EmbargoT11Probe

agent Pinger { holds pingEmbargo }
agent Other  { holds handleBurden }

burden handleBurden {
    for_action: "handle"
    state: pending
    triggered_by: pinged
    discharge_mode: eventual
}

embargo pingEmbargo { state: active }

community ProbeCommunity {
    objective: "probe T11 under an embargo"
    event pinged
    role workerRole {
        action ping   { actor: workerRole emits: pinged inhibited_by_embargo pingEmbargo }
        action handle { actor: workerRole }
    }
}

commitment OtherHandles { by: Other obligation: "handle the ping" creates_burden: handleBurden }
"""


@pytest.fixture(scope="module")
def t11_spec():
    return _spec(_T11)


def _t11_runtime(spec, actors):
    return _runtime(spec, [(a, "workerRole") for a in actors],
                    [("pingEmbargo", "Pinger"), ("handleBurden", "Other")])


def _fires(km):
    return any(km.labels[(km.initial, s)].startswith("fire:pinged")
               for s in km.successors(km.initial))


def test_t11_engine(t11_spec):
    both = ["Pinger", "Other"]
    assert _t11_runtime(t11_spec, both).advance("ping", "Pinger").outcome == "blocked"
    assert _t11_runtime(t11_spec, both).advance("ping", "Other").outcome == "ok"
    assert _t11_runtime(t11_spec, ["Pinger"]).advance("ping", "Pinger").outcome == "blocked"


def test_t11_kept_while_an_actor_is_not_embargoed(t11_spec):
    models = _models(t11_spec, _t11_runtime(t11_spec, ["Pinger", "Other"]))
    assert _fires(models["static"]) and _fires(models["hybrid"])


def test_t11_suppressed_when_every_performer_is_embargoed(t11_spec):
    km = _quiet(build_kripke_from_runtime, _t11_runtime(t11_spec, ["Pinger"]), horizon=3)
    assert not _fires(km)


# ── T9: the carrying action of a transfer ────────────────────────────────────

_T9 = """
enterprise specification EmbargoT9Probe

party Giver { holds carryBurden holds giverEmbargo }
party Taker { holds takerEmbargo }

burden carryBurden { state: active discharge_mode: eventual }

embargo giverEmbargo { state: active }
embargo takerEmbargo { state: active }

community ProbeCommunity {
    objective: "probe T9 under an embargo"
    role giverRole {
        action performTransfer {
            actor: giverRole
            effect transfer carryBurden from giverRole to takerRole
            inhibited_by_embargo giverEmbargo
            inhibited_by_embargo takerEmbargo
        }
    }
    role takerRole {
        action acknowledge { actor: takerRole }
    }
}

commitment GiverCarries { by: Giver obligation: "carry the burden" creates_burden: carryBurden }
"""

_T9_ACTORS = [("Giver", "giverRole"), ("Taker", "takerRole")]


@pytest.fixture(scope="module")
def t9_spec():
    return _spec(_T9)


def _transfers(km):
    return any(km.labels[(km.initial, s)].startswith("transfer:")
               for s in km.successors(km.initial))


def test_t9_suppressed_when_every_performer_is_embargoed(t9_spec):
    grants = [("carryBurden", "Giver"), ("giverEmbargo", "Giver"), ("takerEmbargo", "Taker")]
    for actor, _ in _T9_ACTORS:
        rt = _runtime(t9_spec, _T9_ACTORS, grants)
        assert rt.advance("performTransfer", actor).outcome == "blocked"
    km = _quiet(build_kripke_from_runtime, _runtime(t9_spec, _T9_ACTORS, grants), horizon=3)
    assert not _transfers(km)


def test_t9_kept_while_an_actor_is_not_embargoed(t9_spec):
    grants = [("carryBurden", "Giver"), ("giverEmbargo", "Giver")]
    rt = _runtime(t9_spec, _T9_ACTORS, grants)
    assert rt.advance("performTransfer", "Giver").outcome == "blocked"
    rt = _runtime(t9_spec, _T9_ACTORS, grants)
    assert rt.advance("performTransfer", "Taker").outcome == "ok"
    km = _quiet(build_kripke_from_runtime, _runtime(t9_spec, _T9_ACTORS, grants), horizon=3)
    assert _transfers(km)
