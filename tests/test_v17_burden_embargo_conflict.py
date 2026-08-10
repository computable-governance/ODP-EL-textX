"""
Layer 2 — V-17: Burden/Embargo for_action conflict validator rule.

Design finalized in chat 2026-08-10, following T5 (Exercise). Specification-
time check: an ACTIVE Burden's for_action must not match an ACTIVE
Embargo's for_action — an obligation to perform the one action that is
simultaneously prohibited (§6.4.3, §6.4.4). Consistent with the
specification_time_assurance conflict-resolution strategy already used at
the federation level (§7.9.1 NOTE 3), rather than letting the Kripke
builder (el_kripke.py) silently mask or resolve the conflict at
model-construction time.

Deliberately distinct from T5's Embargo guard (el_kripke.py): that guard
checks whether a specific Permit is blocked by an Action-scoped
inhibited_by_embargo linkage, actor-scoped. This rule checks a simpler,
direct thing — for_action-to-for_action string collision between an
active Burden and an active Embargo — with no Action-scoped traversal and
no actor-scoping at all.

Minimal inline specs via parse_string(), same throwaway-fixture pattern as
test_t5_exercise_embargo_guard.py and test_am41_community_normative_policy.py.
"""
from el_parser import parse_string


_V17_CONFLICT = """
enterprise specification V17ConflictProbe

burden restrictedActionBurden {
    for_action: "performRestrictedAction"
    state: active
}

embargo restrictedActionEmbargo {
    for_action: "performRestrictedAction"
    state: active
}
"""


def test_v17_fires_on_matching_active_for_action():
    """An active Burden and an active Embargo sharing the same for_action
    must be flagged — direct normative conflict."""
    result = parse_string(_V17_CONFLICT, validate=True)
    assert not result.ok
    assert any('V-17' in e for e in result.errors)


_V17_NO_CONFLICT_PENDING_EMBARGO = """
enterprise specification V17NoConflictPendingEmbargoProbe

burden restrictedActionBurden {
    for_action: "performRestrictedAction"
    state: active
}

embargo restrictedActionEmbargo {
    for_action: "performRestrictedAction"
    state: pending
}
"""

_V17_NO_CONFLICT_DIFFERENT_ACTION = """
enterprise specification V17NoConflictDifferentActionProbe

burden restrictedActionBurden {
    for_action: "performActionA"
    state: active
}

embargo restrictedActionEmbargo {
    for_action: "performActionB"
    state: active
}
"""


def test_v17_does_not_fire_when_state_or_action_differs():
    """Two cheap variants confirming the rule checks BOTH state and
    for_action match, not just one:
      (i)  same for_action, but the Embargo is 'pending' not 'active' —
           no standing prohibition yet, so no conflict.
      (ii) both 'active', but for_action values differ — no collision.
    """
    result_pending = parse_string(_V17_NO_CONFLICT_PENDING_EMBARGO, validate=True)
    assert result_pending.ok, result_pending.errors
    assert not any('V-17' in e for e in result_pending.errors)

    result_different_action = parse_string(_V17_NO_CONFLICT_DIFFERENT_ACTION, validate=True)
    assert result_different_action.ok, result_different_action.errors
    assert not any('V-17' in e for e in result_different_action.errors)
