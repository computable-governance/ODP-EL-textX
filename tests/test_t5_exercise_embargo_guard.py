"""
Layer 4 — Rule T5 (Exercise) and its Embargo guard.

Design finalized in chat 2026-08-10 (T5 permit-occurrence rule, Embargo
guard, Burden<->Embargo validator rule — the last of which is separate,
later work). T5 landed in three reviewed diffs against el_kripke.py:
  Diff 1 — PermitDescriptor / _build_permit_descriptors() (data extraction).
  Diff 2 — the T5 edge-generation rule itself (no guard).
  Diff 3 — the Embargo guard, actor-scoped to mirror el_reasoner.
           can_perform()'s held_token_names check (el_reasoner.py:367-371,
           404-406) — an Embargo only blocks if the SAME actor performing
           the action also holds it, not if it exists anywhere in the model.
A fourth, small addition (_build_propositions emitting "occurred:<action>")
was required alongside Diff 3's tests: T5 wrote occurred_actions but nothing
made that fact queryable via the model's actual satisfies()/AF/EF/AG
interface until this landed. These tests are what first exercise T5's
edge-generation path and the guard at all — none of the pre-existing 89
tests touch an active Permit with a resolvable holder and a for_action.

Minimal inline specs via parse_string(), following the throwaway-fixture
pattern in test_am41_community_normative_policy.py, not a full scenario
file — kept small and self-contained so the three cases are easy to
reason about in isolation.
"""
from el_kripke import build_kripke_model
from el_parser import parse_string


_T5_FIRE = """
enterprise specification T5FireProbe

party Operator {
    holds accessPermit
}

permit accessPermit {
    for_action: "performAccess"
    state: active
}
"""


def test_t5_fires_and_action_reaches_occurred_via_ef():
    """Core edge-generation path: one ACTIVE Permit, holder resolvable via
    HoldsToken (the simpler tier), explicit for_action, no competing
    Embargo at all. EF(occurred:performAccess) must hold from w0 — proving
    T5 actually runs and produces the right fact, not just that it
    doesn't crash."""
    result = parse_string(_T5_FIRE, validate=True)
    assert result.ok, result.errors

    km = build_kripke_model(result.model, horizon=5)
    assert km.EF(km.initial, "occurred:performAccess") is True


_T5_EMBARGO_SAME_HOLDER = """
enterprise specification T5EmbargoSameHolderProbe

party Operator {
    holds accessPermit
    holds blockingEmbargo
}

permit accessPermit {
    for_action: "performAccess"
    state: active
}

embargo blockingEmbargo {
    state: active
}

community ProbeCommunity {
    objective: "probe embargo guard suppression"
    role operatorRole {
        action performAccess {
            inhibited_by_embargo blockingEmbargo
        }
    }
}
"""


def test_t5_suppressed_by_active_embargo_held_by_same_actor():
    """Same Permit as the fire test, plus an Embargo: state active, held by
    the SAME actor as the Permit, linked to the Action via the real
    Action-scoped inhibited_by_embargo requirement (not the dead
    DeonticToken-level STRING field). The exercise edge must be suppressed
    entirely — performAccess never appears in occurred_actions in any
    reachable world."""
    result = parse_string(_T5_EMBARGO_SAME_HOLDER, validate=True)
    assert result.ok, result.errors

    km = build_kripke_model(result.model, horizon=5)
    assert km.EF(km.initial, "occurred:performAccess") is False


_T5_EMBARGO_DIFFERENT_HOLDER = """
enterprise specification T5EmbargoDifferentHolderProbe

party Operator {
    holds accessPermit
}

party OtherActor {
    holds blockingEmbargo
}

permit accessPermit {
    for_action: "performAccess"
    state: active
}

embargo blockingEmbargo {
    state: active
}

community ProbeCommunity {
    objective: "probe embargo guard actor-scoping"
    role operatorRole {
        action performAccess {
            inhibited_by_embargo blockingEmbargo
        }
    }
}
"""


def test_t5_not_suppressed_when_embargo_held_by_different_actor():
    """Same Embargo/linkage as the suppression test, but blockingEmbargo is
    held by OtherActor, not by Operator (the Permit's holder). The guard
    must NOT suppress the edge — confirms it is genuinely actor-scoped,
    not accidentally blocking on Embargo existence anywhere in the model."""
    result = parse_string(_T5_EMBARGO_DIFFERENT_HOLDER, validate=True)
    assert result.ok, result.errors

    km = build_kripke_model(result.model, horizon=5)
    assert km.EF(km.initial, "occurred:performAccess") is True
