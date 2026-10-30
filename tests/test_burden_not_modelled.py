"""
Layer 2 — [W-burden-not-modelled]: a burden with no root.

A top-level burden is rooted when el_engine._build_obligation_descriptors()
gives it a descriptor: a Commitment, a ViolationResponse creates_burden, an
Authorization creates_burden_on_authority, or a Delegation's
transfers_token_group. Any other burden has no obligation in the
pre-execution model, so the verifier gives no verdict on it; the rule warns
(advisory, never affects .ok), with at most one hint naming why the runtime
might still see it. Standing duties are out of scope, and so are role-body
inline burdens (InlineToken).
"""
from el_parser import parse_string

_TAG = "[W-burden-not-modelled]"


def _flagged(result):
    return [w for w in result.warnings if w.startswith(_TAG)]


def _flagged_names(result):
    return sorted(w.split("'")[1] for w in _flagged(result))


def _parse(spec):
    result = parse_string(spec, validate=True)
    assert result.ok, result.errors
    return result


# ── Rooted: no warning ─────────────────────────────────────────────────────

def test_commitment_is_a_root():
    result = _parse("""
enterprise specification CommitmentRoot
party Holder {}
burden b1 { state: active deadline: "1 hour" }
commitment c1 { by: Holder obligation: "do it" creates_burden: b1 }
""")
    assert _flagged(result) == []


def test_violation_response_creates_burden_is_a_root():
    result = _parse("""
enterprise specification ResponseRoot
party Holder {}
party Responder {}
burden b1 { state: active deadline: "1 hour" }
burden remedy { state: pending deadline: "1 day" }
commitment c1 { by: Holder obligation: "do it" creates_burden: b1 }
violation_response r1 {
    on_violation_of: b1
    obligates: Responder
    response_kind: remediate
    creates_burden: remedy
}
""")
    assert _flagged(result) == []


def test_authorization_creates_burden_on_authority_is_a_root():
    result = _parse("""
enterprise specification AuthorizationRoot
party Authority {}
party Agent {}
permit p1 { state: active }
burden facilitate { state: active deadline: "1 day" }
authorization a1 {
    authority: Authority
    to_agent: Agent
    grants_permit: p1
    creates_burden_on_authority: facilitate
}
""")
    assert _flagged(result) == []


def test_delegation_token_group_is_a_root():
    # The role's holds satisfies V-15's origin check but is not a root, so
    # the Delegation alone roots b1.
    result = _parse("""
enterprise specification DelegationGroupRoot
party Principal {}
party Agent {}
burden b1 { state: active deadline: "1 hour" }
token_group g1 { member: b1 }
community Probe {
    objective: "probe"
    role worker description: "worker" {
        holds b1
    }
}
delegation d1 {
    from: Principal
    to: Agent
    obligation: "do it"
    transfers_token_group: g1
}
""")
    assert _flagged(result) == []


def test_standing_burden_is_out_of_scope():
    result = _parse("""
enterprise specification StandingOutOfScope
policy ContractEnd : instant { initial_value: 2027-06-30T17:00+10:00 }
party Supplier { holds keepCover }
burden keepCover {
    standing
    keeps: "insurance cover" >= 20000000 AUD
    ends_at: ContractEnd
    state: active
}
""")
    assert _flagged(result) == []


# ── Not rooted: a warning, with its hint ───────────────────────────────────

def test_burden_mentioned_nowhere_warns_with_exact_message():
    result = _parse("""
enterprise specification Unmentioned
burden orphan { state: active deadline: "1 hour" }
""")
    assert _flagged(result) == [
        "[W-burden-not-modelled] Burden 'orphan' has no root: no Commitment or "
        "other construct creates it for a holder, so the pre-execution model has "
        "no obligation for it and the verifier gives no verdict on it. Add a "
        "Commitment by the object accountable for it. (§7.8.7, §6.4.1, §7.10.3)"
    ]


def test_object_holds_only_warns_with_its_hint():
    result = _parse("""
enterprise specification ObjectHolds
party Supplier { holds b1 }
burden b1 { state: active deadline: "1 hour" }
""")
    [w] = _flagged(result)
    assert ("Object 'Supplier' holds it, so the runtime grants it and only a "
            "hybrid model sees it.") in w


def test_role_holds_only_warns_with_its_hint():
    result = _parse("""
enterprise specification RoleHolds
burden b1 { state: active deadline: "1 hour" }
community Probe {
    objective: "probe"
    role worker description: "worker" {
        holds b1
    }
}
""")
    [w] = _flagged(result)
    assert ("Role 'worker' holds it, but the runtime never grants a role's "
            "holds; give the role's filler a Commitment.") in w
    assert "on_join" not in w


def test_effect_create_only_warns_with_its_hint():
    result = _parse("""
enterprise specification EffectCreate
party Actor {}
burden b1 { state: active deadline: "1 hour" }
community Probe {
    objective: "probe"
    role worker description: "worker" {
        action open {
            actor: Actor
            effect create b1
        }
    }
}
""")
    [w] = _flagged(result)
    assert ("Action 'open' creates it (effect create), so only a hybrid model "
            "sees it once it exists.") in w


def test_response_to_an_unfilled_role_warns():
    result = _parse("""
enterprise specification UnfilledResponseRole
party Holder {}
party Responder {}
burden b1 { state: active deadline: "1 hour" }
burden remedy { state: pending deadline: "1 day" }
commitment c1 { by: Holder obligation: "do it" creates_burden: b1 }
community Probe {
    objective: "probe"
    role reviewer description: "reviewer" {}
}
violation_response r1 {
    on_violation_of: b1
    obligates: Responder
    response_kind: remediate
    creates_burden: remedy
    creates_burden_for_role: reviewer
}
""")
    assert _flagged_names(result) == ["remedy"]
