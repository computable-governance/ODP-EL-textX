"""
Layer 4 — Rule T6 (Examine) Embargo guard.

Finding logged 2026-08-19 (docs/CONCEPTS_INDEX.md, "T6 (Examine) has no
Embargo guard — discharges a gated Burden even while a same-actor Embargo
blocks the action"): T5's Exercise rule has an actor-scoped Embargo guard
(el_kripke.py, verified against el_reasoner.can_perform()), but T6 never
inherited it -- its all_active check only looked at permit_descriptors,
with no call to embargo_inhibition_index/embargo_holder_index anywhere in
its block, in either build mode. Confirmed via a minimal running fixture
before the fix landed: T6 discharged the gated Burden even with an active,
same-holder Embargo blocking the exact same action.

Minimal inline specs via parse_string(), following the same
throwaway-fixture pattern as tests/test_t5_exercise_embargo_guard.py --
kept small and self-contained, mirroring that file's three-case structure
(fire / suppressed-same-holder / not-suppressed-different-holder) but for
T6's requires_permit-gated Burden discharge instead of T5's Permit
occurrence.
"""
from el_kripke import build_kripke_model
from el_parser import parse_string


_T6_EMBARGO_SAME_HOLDER = """
enterprise specification T6EmbargoSameHolderProbe

party Holder {
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


def test_t6_suppressed_by_active_embargo_held_by_same_actor():
    """gatedBurden requires accessPermit (active, held by Holder) for its
    action, AND that same action is inhibited_by_embargo blockingEmbargo
    (active, held by the SAME Holder). Before the fix, T6 discharged the
    Burden anyway -- ignoring the Embargo entirely. With the guard, the
    discharge edge must be suppressed: EF(discharged:gatedBurden) is False."""
    result = parse_string(_T6_EMBARGO_SAME_HOLDER, validate=True)
    assert result.ok, result.errors

    km = build_kripke_model(result.model, horizon=5)
    assert km.EF(km.initial, "discharged:gatedBurden") is False


_T6_EMBARGO_DIFFERENT_HOLDER = """
enterprise specification T6EmbargoDifferentHolderProbe

party Holder {
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


def test_t6_not_suppressed_when_embargo_held_by_different_actor():
    """Same Embargo/linkage as the suppression test, but blockingEmbargo is
    held by OtherActor, not by Holder (the Burden's holder and the
    Permit's holder). The guard must NOT suppress the discharge -- confirms
    it is genuinely actor-scoped, not accidentally blocking on Embargo
    existence anywhere in the model. Mirrors T5's own actor-scoping test
    (test_t5_not_suppressed_when_embargo_held_by_different_actor)."""
    result = parse_string(_T6_EMBARGO_DIFFERENT_HOLDER, validate=True)
    assert result.ok, result.errors

    km = build_kripke_model(result.model, horizon=5)
    assert km.EF(km.initial, "discharged:gatedBurden") is True
