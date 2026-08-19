"""
Layer 4 — end-to-end tests for GET /kripke/witness (el_api.get_witness_path()),
commit ad02f1e ("Add Kripke witness-path endpoint (Visualizer Track B, first
piece)"). These exercise the endpoint function itself -- scenario/mode
selection, the extract_witness_path() call, and response shaping -- not
extract_witness_path() or _find_EF_witness() called directly, which are
already covered as building blocks (el_kripke.py's own module tests and the
T5/T6 EF assertions elsewhere in this suite).

Follows test_token_governance_endpoint.py's convention: fresh-reload the api
module per test via the `api` fixture, pin the runtime explicitly rather than
relying on the module's default.

Three cases:

1. T6 Embargo-guard fixture, through the endpoint. Reuses the exact same-
   holder / different-holder specs as
   tests/test_hybrid_t6_examine_embargo_guard.py (the T6 hybrid-mode
   Embargo-guard fixture landed this morning, commit 8876270) -- proposition
   "discharged:gatedBurden". Confirms witness_path is [] when the Embargo is
   active and held by the same actor as the gated Burden, and non-empty
   (one-hop, "examine:gatedBurden -> performExamine") when the Embargo is
   held by a different actor -- i.e. does not block this holder.

2. Real-scenario match. referral_scenario.el, hybrid mode (the module
   default), proposition "discharged:aiExaminationBurden" -- chosen over
   "occurred:conductAIExamination" because T6's discharge and occurrence are
   fused into a single edge (el_kripke.py's T6 block: `new_occurred =
   occurred | {desc.for_action}` and `new_obligs[oid] = DISCHARGED` in the
   same transition), so both propositions hold on the identical resulting
   world -- and "discharged:aiExaminationBurden" is the one already
   independently verified via check_permission() in
   tests/test_referral_kripke_t6_permit_gate.py's
   test_ai_examination_burden_ef_true_when_permit_active. Ground truth
   below was captured by calling build_kripke_from_runtime() +
   km._find_EF_witness() directly against a fresh _build_referral_runtime()
   (the same already-proven primitive extract_witness_path() delegates to),
   independently of the endpoint under test:

     w0 (initial): all five Burdens PENDING, all six actors ACTIVE,
                   occurred_actions = [], no incoming edge.
     w1 (target):  aiExaminationBurden DISCHARGED (all other Burdens
                   still PENDING), all six actors still ACTIVE,
                   occurred_actions = ["conductAIExamination"],
                   edge_from_previous = "examine:aiExaminationBurden -> conductAIExamination".

   One edge, two worlds -- a direct one-hop path from the initial world.

3. Unreachable-proposition case. Same referral_scenario.el hybrid runtime,
   proposition "discharged:nonexistentTokenXYZ" -- syntactically valid
   (matches the "discharged:<id>" proposition grammar) but names a token
   that does not exist anywhere in the scenario, so it is never a member of
   any world's proposition set (KripkeModel.satisfies() is plain set
   membership -- no lookup/KeyError path exists for an unknown id). Confirms
   the endpoint's documented contract ("witness_path is [] (200, not an
   error) if the proposition is never satisfied on any reachable world") by
   confirming the call returns normally (no HTTPException, no other
   exception) with witness_path == [].
"""
import importlib

from el_parser import parse_string
from el_runtime import Runtime


import pytest


@pytest.fixture
def api():
    """Fresh el_api module (rebuilds the _runtime singleton from initial state)."""
    import el_api
    importlib.reload(el_api)
    return el_api


# ── Case 1: T6 Embargo-guard fixture, through the endpoint ─────────────────

_T6_EMBARGO_SAME_HOLDER = """
enterprise specification T6EmbargoSameHolderProbe

party Holder {
    holds gatedBurden
    holds accessPermit
    holds blockingEmbargo
}

burden gatedBurden {
    for_action: "performExamine"
    state: active
}

permit accessPermit {
    for_action: "performExamine"
    state: active
}

embargo blockingEmbargo {
    state: active
}

commitment gatedCommitment {
    by: Holder
    obligation: "Perform the gated examine action"
    creates_burden: gatedBurden
}

community ProbeCommunity {
    objective: "probe T6 embargo guard suppression"
    role holderRole {
        action performExamine {
            requires_permit accessPermit
            inhibited_by_embargo blockingEmbargo
        }
    }
}
"""

_T6_EMBARGO_DIFFERENT_HOLDER = """
enterprise specification T6EmbargoDifferentHolderProbe

party Holder {
    holds gatedBurden
    holds accessPermit
}

party OtherActor {
    holds blockingEmbargo
}

burden gatedBurden {
    for_action: "performExamine"
    state: active
}

permit accessPermit {
    for_action: "performExamine"
    state: active
}

embargo blockingEmbargo {
    state: active
}

commitment gatedCommitment {
    by: Holder
    obligation: "Perform the gated examine action"
    creates_burden: gatedBurden
}

community ProbeCommunity {
    objective: "probe T6 embargo guard actor-scoping"
    role holderRole {
        action performExamine {
            requires_permit accessPermit
            inhibited_by_embargo blockingEmbargo
        }
    }
}
"""


def test_witness_endpoint_empty_when_same_holder_embargo_active(api):
    """Same-holder Embargo blocks T6's discharge edge entirely -- the
    endpoint must report witness_path: [] (unreachable), not raise."""
    result = parse_string(_T6_EMBARGO_SAME_HOLDER, validate=True)
    assert result.ok, result.errors
    api._runtime = Runtime.build_from_spec(result.model)

    resp = api.get_witness_path("discharged:gatedBurden")

    assert resp["witness_path"] == []


def test_witness_endpoint_nonempty_when_embargo_held_by_different_actor(api):
    """Same fixture, Embargo held by a different actor than gatedBurden's
    holder -- the guard does not block this holder, so the endpoint must
    return the one-hop T6 witness path, not []."""
    result = parse_string(_T6_EMBARGO_DIFFERENT_HOLDER, validate=True)
    assert result.ok, result.errors
    api._runtime = Runtime.build_from_spec(result.model)

    resp = api.get_witness_path("discharged:gatedBurden")

    assert resp["witness_path"] != []
    assert len(resp["witness_path"]) == 2
    assert resp["witness_path"][-1]["edge_from_previous"] == "examine:gatedBurden → performExamine"
    assert resp["witness_path"][-1]["obligations"]["gatedBurden"] == "DISCHARGED"


# ── Case 2: real-scenario match against a manually-traced path ─────────────

def test_witness_endpoint_matches_manually_traced_referral_path(api):
    """referral_scenario.el, hybrid mode (module default), proposition
    discharged:aiExaminationBurden. Asserts against the ground truth
    recaptured directly via km._find_EF_witness() (see module docstring)."""
    api._runtime = api._SCENARIO_BUILDERS["referral"]()

    resp = api.get_witness_path("discharged:aiExaminationBurden")
    path = resp["witness_path"]

    assert resp["scenario_name"] == "referral"
    assert len(path) == 2

    w0, w1 = path
    assert w0["edge_from_previous"] is None
    assert w0["occurred_actions"] == []
    assert w0["obligations"]["aiExaminationBurden"] == "PENDING"
    assert set(w0["actors"]) == {
        "GPClinician", "GPPractice", "Patient",
        "SpecialistAIAgent", "SpecialistClinician", "SpecialistPractice",
    }
    assert all(state == "ACTIVE" for state in w0["actors"].values())

    assert w1["edge_from_previous"] == "examine:aiExaminationBurden → conductAIExamination"
    assert w1["occurred_actions"] == ["conductAIExamination"]
    assert w1["obligations"]["aiExaminationBurden"] == "DISCHARGED"
    # every other Burden is untouched by this single fused T6 transition
    for oid, state in w1["obligations"].items():
        if oid != "aiExaminationBurden":
            assert state == "PENDING"
    assert all(state == "ACTIVE" for state in w1["actors"].values())


# ── Case 3: unreachable / nonexistent proposition ───────────────────────────

def test_witness_endpoint_returns_empty_path_not_error_for_unknown_proposition(api):
    """discharged:nonexistentTokenXYZ is syntactically valid but names no
    token that exists anywhere in referral_scenario.el -- it can never be a
    member of any world's proposition set. Per the endpoint's documented
    contract, this must return 200 with witness_path: [], not raise."""
    api._runtime = api._SCENARIO_BUILDERS["referral"]()

    resp = api.get_witness_path("discharged:nonexistentTokenXYZ")

    assert resp["scenario_name"] == "referral"
    assert resp["witness_path"] == []
