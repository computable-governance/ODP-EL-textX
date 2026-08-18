"""
Layer 4 — hybrid-mode Rule T6 (Examine) Embargo guard.

Hybrid-mode counterpart to tests/test_t6_examine_embargo_guard.py -- same
two minimal specs, exercised through the hybrid pipeline
(Runtime.build_from_spec() -> build_kripke_from_runtime()) instead of
build_kripke_model() directly, proving the ported guard (docs/
CONCEPTS_INDEX.md, "T6 (Examine) has no Embargo guard...", 2026-08-19)
produces the same verdicts as pre-exec, not just that it doesn't crash.
Mirrors tests/test_hybrid_t5_exercise_embargo_guard.py's structure.

Unlike the pre-exec specs, gatedBurden must also be explicitly `holds`
by Holder: build_kripke_from_runtime() sources its obligation descriptors
by iterating runtime.current_state().tokens (live WorldState), not the
spec's Commitments directly (el_kripke.py:2470, "for tok in state.tokens:
if tok.kind == 'burden' ..."). Runtime.build_from_spec()'s auto-grant
only instantiates a token into state.tokens from a `holds` clause; a
Burden that exists only via a Commitment (with no `holds`) never reaches
state.tokens and is silently invisible to hybrid mode -- confirmed by
running the fixture without `holds gatedBurden` first: obligation_
descriptors came back empty and both cases read EF False for the wrong
reason (no obligation existed to discharge, not because the guard fired).
"""
from el_kripke import build_kripke_from_runtime
from el_parser import parse_string
from el_runtime import Runtime


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


def test_hybrid_t6_suppressed_by_active_embargo_held_by_same_actor():
    """Same fixture as pre-exec's test_t6_suppressed_by_active_embargo_
    held_by_same_actor, run through the hybrid pipeline.
    EF(discharged:gatedBurden) must be False."""
    result = parse_string(_T6_EMBARGO_SAME_HOLDER, validate=True)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)

    km = build_kripke_from_runtime(rt, horizon=5)
    assert km.EF(km.initial, "discharged:gatedBurden") is False


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


def test_hybrid_t6_not_suppressed_when_embargo_held_by_different_actor():
    """Same fixture as pre-exec's test_t6_not_suppressed_when_embargo_
    held_by_different_actor, run through the hybrid pipeline.
    EF(discharged:gatedBurden) must stay True -- confirms the ported guard
    is actor-scoped in the hybrid path too."""
    result = parse_string(_T6_EMBARGO_DIFFERENT_HOLDER, validate=True)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)

    km = build_kripke_from_runtime(rt, horizon=5)
    assert km.EF(km.initial, "discharged:gatedBurden") is True
